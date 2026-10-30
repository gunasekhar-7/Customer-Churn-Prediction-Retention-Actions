"""
Monitoring and drift detection for the Customer Churn Prediction platform.

This module provides:
1. Request metrics logging (API latency, status codes)
2. Population-level drift detection using PSI and KS test
3. Background monitoring task for production deployment
4. Drift alert webhook notifications

Drift detection is deliberately kept OUT of the request hot path.
Use the MonitoringService for background population-level monitoring.
"""

import hashlib
import hmac
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
import numpy as np
from scipy import stats

logger = logging.getLogger("churn_metrics")


def send_drift_webhook(
    webhook_url: str,
    drift_result: 'DriftResult',
    secret: Optional[str] = None,
    timeout: int = 5
) -> bool:
    """
    Send drift alert to webhook URL.

    Args:
        webhook_url: Target webhook URL (Slack, PagerDuty, generic HTTP)
        drift_result: DriftResult to send
        secret: Optional HMAC-SHA256 secret for signature verification
        timeout: Request timeout in seconds

    Returns:
        True if successful, False otherwise
    """
    if not webhook_url:
        return False

    payload = {
        "timestamp": drift_result.timestamp.isoformat(),
        "has_drift": drift_result.has_drift,
        "has_warning": drift_result.has_warning,
        "psi_score": drift_result.psi_score,
        "ks_statistic": drift_result.ks_statistic,
        "ks_pvalue": drift_result.ks_pvalue,
        "sample_count": drift_result.sample_count,
        "reference_mean": drift_result.reference_mean,
        "current_mean": drift_result.current_mean,
        "message": drift_result.message,
        "feature_drift": drift_result.feature_drift,
    }

    headers = {"Content-Type": "application/json"}

    # Add HMAC signature if secret provided
    if secret:
        body = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Drift-Signature"] = f"sha256={signature}"

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(webhook_url, json=payload, headers=headers)
            response.raise_for_status()
        logger.info(f"Drift webhook sent successfully to {webhook_url}")
        return True
    except Exception as e:
        logger.error(f"Failed to send drift webhook to {webhook_url}: {e}")
        return False


def log_request_metrics(
    endpoint: str,
    process_time_ms: float,
    status_code: int,
    extra_metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Outputs structured JSON logs designed to be ingested by AWS CloudWatch or ELK.
    Tracks API latency and success rates.
    """
    metrics = {
        "event_type": "api_request",
        "endpoint": endpoint,
        "process_time_ms": round(process_time_ms, 2),
        "status_code": status_code
    }

    if extra_metadata:
        metrics.update(extra_metadata)

    # Log as raw JSON string so log aggregators can parse it automatically
    logger.info(json.dumps(metrics))


# ============================================================
# Population-Level Drift Detection (NOT for per-request use)
# ============================================================

@dataclass
class DriftConfig:
    """Configuration for drift detection behavior."""
    # Reference distribution (from training/validation data)
    reference_predictions: List[float] = field(default_factory=list)
    reference_features: Optional[np.ndarray] = None

    # Detection parameters
    psi_threshold: float = 0.1           # PSI > 0.1 indicates drift
    psi_warning: float = 0.05            # PSI > 0.05 warns
    ks_threshold: float = 0.05           # KS test p-value < 0.05 rejects null (drift)
    min_samples: int = 100               # Minimum samples for reliable detection

    # Window configuration
    window_size: int = 1000              # Rolling window size
    evaluation_interval_sec: int = 300   # Check every 5 minutes

    # Feature drift (optional, more expensive)
    feature_names: List[str] = field(default_factory=list)
    feature_psi_threshold: float = 0.1
    feature_ks_threshold: float = 0.05

    # Optional callback for metrics export (e.g., Prometheus)
    on_drift_result: Optional[Callable[['DriftResult'], None]] = None


@dataclass
class DriftResult:
    """Result of a drift detection check."""
    timestamp: datetime
    has_drift: bool
    has_warning: bool
    psi_score: Optional[float]
    ks_statistic: Optional[float]
    ks_pvalue: Optional[float]
    sample_count: int
    reference_mean: float
    current_mean: float
    feature_drift: Dict[str, Dict[str, float]] = field(default_factory=dict)
    message: str = ""


class PopulationDriftDetector:
    """
    Population-level drift detector using PSI and KS test.

    This is designed for BACKGROUND monitoring, NOT per-request use.
    Collects prediction scores in a rolling window and evaluates
    population-level drift against reference distributions.
    """

    def __init__(self, config: DriftConfig):
        self.config = config
        self._window: deque = deque(maxlen=config.window_size)
        self._lock = threading.Lock()
        self._last_evaluation: Optional[datetime] = None
        self._last_result: Optional['DriftResult'] = None

        # Validate reference data
        if not config.reference_predictions:
            logger.warning("DriftConfig has no reference_predictions; drift detection disabled")
        elif len(config.reference_predictions) < config.min_samples:
            logger.warning(
                f"Reference sample size ({len(config.reference_predictions)}) "
                f"below minimum ({config.min_samples}); drift detection may be unreliable"
            )

    def add_prediction(self, probability: float) -> None:
        """Add a prediction score to the rolling window (thread-safe, O(1))."""
        with self._lock:
            self._window.append(probability)

    def should_evaluate(self) -> bool:
        """Check if enough time has passed since last evaluation."""
        if self._last_evaluation is None:
            return True
        return (datetime.now() - self._last_evaluation).total_seconds() >= self.config.evaluation_interval_sec

    def evaluate(self) -> Optional['DriftResult']:
        """
        Evaluate drift on the current window.

        Returns None if insufficient samples or reference data.
        """
        with self._lock:
            if len(self._window) < self.config.min_samples:
                return None
            if not self.config.reference_predictions:
                return None

            current_samples = list(self._window)

        # Compute drift metrics
        psi_score = self._compute_psi(
            self.config.reference_predictions,
            current_samples
        )

        ks_stat, ks_pvalue = self._compute_ks(
            self.config.reference_predictions,
            current_samples
        )

        ref_mean = float(np.mean(self.config.reference_predictions))
        cur_mean = float(np.mean(current_samples))

        has_drift = psi_score > self.config.psi_threshold or (ks_pvalue is not None and ks_pvalue < self.config.ks_threshold)
        has_warning = psi_score > self.config.psi_warning

        result = DriftResult(
            timestamp=datetime.now(),
            has_drift=has_drift,
            has_warning=has_warning,
            psi_score=psi_score,
            ks_statistic=ks_stat,
            ks_pvalue=ks_pvalue,
            sample_count=len(current_samples),
            reference_mean=ref_mean,
            current_mean=cur_mean,
            message=self._format_message(has_drift, has_warning, psi_score, ks_pvalue)
        )

        with self._lock:
            self._last_evaluation = datetime.now()
            self._last_result = result

        # Log result
        if has_drift:
            logger.warning(json.dumps({
                "event_type": "population_drift",
                "drift_type": "prediction_score",
                "psi": psi_score,
                "ks_pvalue": ks_pvalue,
                "ref_mean": ref_mean,
                "cur_mean": cur_mean,
                "sample_count": len(current_samples)
            }))
        elif has_warning:
            logger.info(json.dumps({
                "event_type": "population_drift_warning",
                "psi": psi_score,
                "sample_count": len(current_samples)
            }))
        else:
            logger.debug(json.dumps({
                "event_type": "population_drift_check",
                "psi": psi_score,
                "ks_pvalue": ks_pvalue,
                "sample_count": len(current_samples)
            }))

        # Call optional callback for metrics export
        if self.config.on_drift_result:
            try:
                self.config.on_drift_result(result)
            except Exception as e:
                logger.debug(f"Drift result callback failed: {e}")

        return result

    def get_last_result(self) -> Optional['DriftResult']:
        """Get the last evaluation result (thread-safe)."""
        with self._lock:
            return self._last_result

    def _compute_psi(self, reference: List[float], current: List[float], bins: int = 10) -> float:
        """
        Compute Population Stability Index (PSI).

        PSI = sum((current_pct - reference_pct) * log(current_pct / reference_pct))
        PSI < 0.1: no significant drift
        PSI 0.1-0.25: moderate drift
        PSI > 0.25: significant drift
        """
        ref_arr = np.array(reference)
        cur_arr = np.array(current)

        # Create bins based on reference quantiles
        quantiles = np.linspace(0, 1, bins + 1)
        bin_edges = np.unique(np.quantile(ref_arr, quantiles))

        # Ensure we have at least 2 bins
        if len(bin_edges) < 2:
            return 0.0

        ref_hist, _ = np.histogram(ref_arr, bins=bin_edges, density=True)
        cur_hist, _ = np.histogram(cur_arr, bins=bin_edges, density=True)

        # Convert to proportions
        ref_pct = ref_hist / (np.sum(ref_hist) + 1e-10)
        cur_pct = cur_hist / (np.sum(cur_hist) + 1e-10)

        # Avoid log(0)
        eps = 1e-10
        psi = np.sum((cur_pct - ref_pct) * np.log((cur_pct + eps) / (ref_pct + eps)))
        return float(max(0.0, psi))  # PSI should be non-negative

    def _compute_ks(self, reference: List[float], current: List[float]) -> Tuple[Optional[float], Optional[float]]:
        """
        Compute Kolmogorov-Smirnov two-sample test.

        Returns (ks_statistic, p_value) or (None, None) if test cannot run.
        """
        try:
            ref_arr = np.array(reference)
            cur_arr = np.array(current)
            ks_stat, p_value = stats.ks_2samp(ref_arr, cur_arr, alternative='two-sided', mode='auto')
            return float(ks_stat), float(p_value)
        except Exception as e:
            logger.debug(f"KS test failed: {e}")
            return None, None

    def _format_message(self, has_drift: bool, has_warning: bool, psi: float, ks_pvalue: Optional[float]) -> str:
        if has_drift:
            return f"Population drift detected: PSI={psi:.4f}" + (f", KS p-value={ks_pvalue:.4f}" if ks_pvalue else "")
        elif has_warning:
            return f"Population drift warning: PSI={psi:.4f}"
        else:
            return "No significant drift detected"


class MonitoringService:
    """
    Background monitoring service for production deployment.

    Runs as a background task to periodically evaluate population drift.
    Can be started in FastAPI lifespan or as a separate worker process.
    """

    def __init__(
        self,
        config: Optional['DriftConfig'] = None,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        webhook_timeout: int = 5
    ):
        self.config = config or DriftConfig()
        self.detector = PopulationDriftDetector(self.config)
        self._task: Optional[threading.Thread] = None
        self._running = False
        # Webhook configuration
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret
        self.webhook_timeout = webhook_timeout

    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._running:
            return
        self._running = True
        self._task = threading.Thread(target=self._run_loop, daemon=True)
        self._task.start()
        logger.info("MonitoringService started")

    def stop(self) -> None:
        """Stop the background monitoring thread."""
        self._running = False
        if self._task:
            self._task.join(timeout=10)
        logger.info("MonitoringService stopped")

    def record_prediction(self, probability: float) -> None:
        """Record a prediction score for drift monitoring (call from API)."""
        self.detector.add_prediction(probability)

    def check_drift_now(self) -> Optional['DriftResult']:
        """Manually trigger drift evaluation."""
        return self.detector.evaluate()

    def _run_loop(self) -> None:
        """Background loop for periodic drift evaluation."""
        while self._running:
            try:
                if self.detector.should_evaluate():
                    result = self.detector.evaluate()
                    if result and self.webhook_url:
                        send_drift_webhook(
                            self.webhook_url,
                            result,
                            secret=self.webhook_secret,
                            timeout=self.webhook_timeout
                        )
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
            time.sleep(60)  # Check every minute if evaluation is due



