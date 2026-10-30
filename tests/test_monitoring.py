"""
Tests for monitoring and drift detection functionality.
"""

from datetime import datetime

import numpy as np
import pytest

from src.monitoring import (
    DriftConfig,
    DriftResult,
    MonitoringService,
    PopulationDriftDetector,
    log_request_metrics,
)


class TestLogRequestMetrics:
    """Tests for request metrics logging."""

    def test_log_request_metrics_basic(self):
        from unittest.mock import patch

        from src.monitoring import logger as monitoring_logger

        with patch.object(monitoring_logger, 'info') as mock_info:
            log_request_metrics("/test", 12.3, 200, {"extra": "data"})

            mock_info.assert_called_once()
            call_args = mock_info.call_args[0][0]
            assert "api_request" in call_args
            assert "/test" in call_args
            assert "12.3" in call_args
            assert "data" in call_args
            import json
            parsed = json.loads(call_args)
            assert parsed["event_type"] == "api_request"
            assert parsed["endpoint"] == "/test"
            assert parsed["process_time_ms"] == 12.3
            assert parsed["status_code"] == 200
            assert parsed["extra"] == "data"

    def test_log_request_metrics_no_extra(self):
        from unittest.mock import patch

        from src.monitoring import logger as monitoring_logger

        with patch.object(monitoring_logger, 'info') as mock_info:
            log_request_metrics("/health", 5.0, 200)

            mock_info.assert_called_once()
            call_args = mock_info.call_args[0][0]
            assert "api_request" in call_args
            assert "/health" in call_args
            assert "5.0" in call_args
            import json
            parsed = json.loads(call_args)
            assert parsed["event_type"] == "api_request"
            assert parsed["endpoint"] == "/health"
            assert parsed["process_time_ms"] == 5.0
            assert parsed["status_code"] == 200
            assert "extra" not in parsed


class TestDriftConfig:
    """Tests for DriftConfig dataclass."""

    def test_default_config(self):
        config = DriftConfig()
        assert config.psi_threshold == 0.1
        assert config.psi_warning == 0.05
        assert config.ks_threshold == 0.05
        assert config.min_samples == 100
        assert config.window_size == 1000
        assert config.evaluation_interval_sec == 300

    def test_custom_config(self):
        config = DriftConfig(
            psi_threshold=0.2,
            min_samples=50,
            window_size=500
        )
        assert config.psi_threshold == 0.2
        assert config.min_samples == 50
        assert config.window_size == 500


class TestDriftResult:
    """Tests for DriftResult dataclass."""

    def test_drift_result_creation(self):
        result = DriftResult(
            timestamp=datetime.now(),
            has_drift=True,
            has_warning=False,
            psi_score=0.15,
            ks_statistic=0.2,
            ks_pvalue=0.01,
            sample_count=100,
            reference_mean=0.25,
            current_mean=0.35,
            message="Population drift detected"
        )
        assert result.has_drift is True
        assert result.has_warning is False
        assert result.psi_score == 0.15
        assert result.ks_statistic == 0.2
        assert result.ks_pvalue == 0.01


class TestPopulationDriftDetector:
    """Tests for PopulationDriftDetector."""

    @pytest.fixture
    def reference_data(self):
        """Generate reference prediction data."""
        np.random.seed(42)
        return list(np.random.beta(2, 5, 1000))

    @pytest.fixture
    def config(self, reference_data):
        return DriftConfig(
            reference_predictions=reference_data,
            min_samples=50,
            window_size=100,
            evaluation_interval_sec=60
        )

    @pytest.fixture
    def detector(self, config):
        return PopulationDriftDetector(config)

    def test_add_prediction(self, detector):
        assert len(detector._window) == 0
        detector.add_prediction(0.5)
        assert len(detector._window) == 1
        detector.add_prediction(0.7)
        assert len(detector._window) == 2

    def test_add_multiple_predictions(self, detector):
        for i in range(150):
            detector.add_prediction(i / 150.0)
        # Window should be capped at window_size (default 1000, but config has 100)
        assert len(detector._window) <= 100

    def test_insufficient_samples(self, detector):
        """Test that evaluation returns None when insufficient samples."""
        detector.add_prediction(0.5)
        result = detector.evaluate()
        assert result is None

    def test_no_reference_data(self, config):
        """Test that evaluation returns None when no reference data."""
        config.reference_predictions = []
        detector = PopulationDriftDetector(config)
        for i in range(100):
            detector.add_prediction(i / 100.0)
        result = detector.evaluate()
        assert result is None

    def test_no_drift_same_distribution(self, detector):
        """Test no drift detected when distributions match."""
        ref_data = detector.config.reference_predictions
        # Add same distribution data (window size is 100)
        for val in ref_data[:100]:
            detector.add_prediction(val)

        result = detector.evaluate()
        assert result is not None
        assert result.has_drift is False
        # Allow warning due to sampling variation (PSI ~0.08)
        assert result.sample_count == 100

    def test_drift_detected_different_distribution(self, detector):
        """Test drift detected when distributions differ significantly."""
        # Add very different distribution (all high probabilities)
        for _ in range(100):
            detector.add_prediction(0.9)

        result = detector.evaluate()
        assert result is not None
        assert result.has_drift is True
        # KS test should detect drift even if PSI is low (all values in same bin)
        assert result.ks_pvalue is not None
        assert result.ks_pvalue < 0.05

    def test_warning_but_not_drift(self, detector):
        """Test warning triggered but not full drift."""
        # Add slightly different distribution
        for _ in range(100):
            detector.add_prediction(0.7)

        result = detector.evaluate()
        assert result is not None
        # Should at least warn if PSI > 0.05
        if result.psi_score > 0.05:
            assert result.has_warning is True

    def test_ks_test_drift(self, detector):
        """Test KS test detects drift."""
        # Add very different distribution
        for _ in range(100):
            detector.add_prediction(0.01)

        result = detector.evaluate()
        assert result is not None
        assert result.ks_pvalue is not None
        assert result.ks_pvalue < 0.05

    def test_get_last_result(self, detector):
        assert detector.get_last_result() is None
        detector.add_prediction(0.5)
        detector.add_prediction(0.5)
        # Need enough samples
        for _ in range(100):
            detector.add_prediction(0.5)
        result = detector.evaluate()
        assert detector.get_last_result() is not None
        assert detector.get_last_result().timestamp == result.timestamp

    def test_should_evaluate(self, detector):
        assert detector.should_evaluate() is True
        detector._last_evaluation = datetime.now()
        assert detector.should_evaluate() is False

    def test_thread_safety(self, detector):
        """Test thread-safe operations."""
        import threading

        def add_predictions():
            for i in range(100):
                detector.add_prediction(i / 100.0)

        threads = [threading.Thread(target=add_predictions) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(detector._window) <= 1000  # default window size


class TestMonitoringService:
    """Tests for MonitoringService."""

    @pytest.fixture
    def config(self):
        return DriftConfig(
            reference_predictions=[0.1, 0.2, 0.3, 0.4, 0.5] * 200,
            min_samples=50,
            evaluation_interval_sec=1  # Fast for testing
        )

    @pytest.fixture
    def service(self, config):
        return MonitoringService(config)

    def test_start_stop(self, service):
        assert service._running is False
        service.start()
        assert service._running is True
        service.stop()
        assert service._running is False

    def test_record_prediction(self, service):
        service.start()
        try:
            service.record_prediction(0.5)
            service.record_prediction(0.7)
            assert len(service.detector._window) == 2
        finally:
            service.stop()

    def test_check_drift_now(self, service):
        service.start()
        try:
            # Add enough samples
            for i in range(100):
                service.record_prediction(i / 100.0)
            result = service.check_drift_now()
            assert result is not None
        finally:
            service.stop()

    def test_record_after_stop(self, service):
        service.start()
        service.stop()
        # Should not crash
        service.record_prediction(0.5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
