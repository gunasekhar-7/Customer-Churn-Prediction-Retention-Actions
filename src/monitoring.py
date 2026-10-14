import json
import logging
from typing import Any, Dict

logger = logging.getLogger("churn_metrics")

def log_request_metrics(endpoint: str, process_time_ms: float, status_code: int, extra_metadata: Dict[str, Any] = None):
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


def check_drift_thresholds(prediction_prob: float, historical_mean_prob: float = 0.265) -> bool:
    """
    Placeholder logic to alert on severe data/prediction drift at runtime.
    If a batch of predictions deviates wildly from the historical baseline, it logs a warning.
    (In a robust system, this is usually calculated asynchronously over trailing 24h windows).
    """
    # Simply flag if the probability is drastically misaligned with expected distributions
    # E.g. > 3 standard deviations from mean, or pure anomaly
    deviation = abs(prediction_prob - historical_mean_prob)

    if deviation > 0.5:
        drift_alert = {
            "event_type": "drift_alert",
            "message": "Prediction significantly deviates from historical baseline",
            "prediction_prob": prediction_prob,
            "historical_mean": historical_mean_prob
        }
        logger.warning(json.dumps(drift_alert))
        return True

    return False
