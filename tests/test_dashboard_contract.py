"""
Contract tests for dashboard API client retry behavior and prediction contracts.

These tests use a mock HTTP server (pytest-httpserver) to simulate various
API responses and verify the client's retry behavior, error handling,
and contract compliance.
"""

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from dashboard.api_client import (
    _get_retry_after,
    _is_idempotent_endpoint,
    _is_permanent_error,
    _is_permanent_exception,
    _is_retryable_exception,
    _is_retryable_status,
    _make_request,
    explain,
    get_health,
    get_model_info,
    get_retention_recommendation,
    predict,
    predict_batch,
)


def make_json_response(data, status=200):
    """Create a JSON response."""
    return Response(str(data).replace("'", '"'), status=status, mimetype="application/json")


def make_text_response(text, status=200):
    """Create a text response."""
    return Response(text, status=status, mimetype="text/plain")


class TestEndpointClassification:
    """Test endpoint idempotency classification."""

    def test_idempotent_endpoints(self):
        """Test that known idempotent endpoints are classified correctly."""
        assert _is_idempotent_endpoint("/health") is True
        assert _is_idempotent_endpoint("/model/info") is True
        assert _is_idempotent_endpoint("/explain") is True
        assert _is_idempotent_endpoint("/model/versions") is True
        assert _is_idempotent_endpoint("/health/check") is True

    def test_non_idempotent_endpoints(self):
        """Test that non-idempotent endpoints are classified correctly."""
        assert _is_idempotent_endpoint("/predict") is False
        assert _is_idempotent_endpoint("/predict/batch") is False
        assert _is_idempotent_endpoint("/retention-recommendation") is False
        assert _is_idempotent_endpoint("/unknown") is False


class TestRetryableStatus:
    """Test retryable status code classification."""

    def test_retryable_status_codes(self):
        """Test that correct status codes are considered retryable."""
        assert _is_retryable_status(429) is True  # Rate limited
        assert _is_retryable_status(500) is True  # Server error
        assert _is_retryable_status(502) is True  # Bad gateway
        assert _is_retryable_status(503) is True  # Service unavailable
        assert _is_retryable_status(504) is True  # Gateway timeout

    def test_non_retryable_status_codes(self):
        """Test that non-retryable status codes are not retryable."""
        assert _is_retryable_status(200) is False
        assert _is_retryable_status(400) is False
        assert _is_retryable_status(401) is False
        assert _is_retryable_status(403) is False
        assert _is_retryable_status(404) is False
        assert _is_retryable_status(422) is False


class TestPermanentError:
    """Test permanent error classification."""

    def test_permanent_errors(self):
        """Test that client errors (except 429) are permanent."""
        assert _is_permanent_error(400) is True
        assert _is_permanent_error(401) is True
        assert _is_permanent_error(403) is True
        assert _is_permanent_error(404) is True
        assert _is_permanent_error(422) is True

    def test_non_permanent_errors(self):
        """Test that server errors and 429 are not permanent."""
        assert _is_permanent_error(429) is False
        assert _is_permanent_error(500) is False
        assert _is_permanent_error(502) is False
        assert _is_permanent_error(503) is False


class TestRetryableException:
    """Test retryable exception classification."""

    def test_timeout_exception_retryable(self):
        """Test that timeout exceptions are retryable."""
        exc = httpx.TimeoutException("Request timed out")
        assert _is_retryable_exception(exc) is True

    def test_network_error_retryable(self):
        """Test that network errors are retryable."""
        exc = httpx.NetworkError("Connection refused")
        assert _is_retryable_exception(exc) is True

    def test_http_status_error_retryable(self):
        """Test that HTTP status errors with retryable status are retryable."""
        response = MagicMock()
        response.status_code = 503
        exc = httpx.HTTPStatusError("Service unavailable", request=MagicMock(), response=response)
        assert _is_retryable_exception(exc) is True

    def test_http_status_error_not_retryable(self):
        """Test that HTTP status errors with non-retryable status are not retryable."""
        response = MagicMock()
        response.status_code = 400
        exc = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=response)
        assert _is_retryable_exception(exc) is False

    def test_non_retryable_exception(self):
        """Test that other exceptions are not retryable."""
        exc = ValueError("Invalid input")
        assert _is_retryable_exception(exc) is False


class TestPermanentException:
    """Test permanent exception classification."""

    def test_http_status_error_permanent(self):
        """Test that HTTP status errors with permanent status are permanent."""
        response = MagicMock()
        response.status_code = 403
        exc = httpx.HTTPStatusError("Forbidden", request=MagicMock(), response=response)
        assert _is_permanent_exception(exc) is True

    def test_http_status_error_not_permanent(self):
        """Test that HTTP status errors with non-permanent status are not permanent."""
        response = MagicMock()
        response.status_code = 500
        exc = httpx.HTTPStatusError("Server error", request=MagicMock(), response=response)
        assert _is_permanent_exception(exc) is False

    def test_non_http_exception_not_permanent(self):
        """Test that non-HTTP exceptions are not permanent."""
        exc = ValueError("Invalid input")
        assert _is_permanent_exception(exc) is False


class TestRetryAfterHeader:
    """Test Retry-After header parsing."""

    def test_valid_retry_after_seconds(self):
        """Test parsing valid Retry-After header in seconds."""
        response = MagicMock()
        response.headers = {"Retry-After": "30"}
        assert _get_retry_after(response) == 30.0

    def test_invalid_retry_after(self):
        """Test that invalid Retry-After returns None."""
        response = MagicMock()
        response.headers = {"Retry-After": "invalid"}
        assert _get_retry_after(response) is None

    def test_missing_retry_after(self):
        """Test that missing Retry-After returns None."""
        response = MagicMock()
        response.headers = {}
        assert _get_retry_after(response) is None


class TestRetryBehaviorWithMockServer:
    """Test retry behavior using a mock HTTP server."""

    def test_transient_failure_then_success(self, httpserver: HTTPServer):
        """Test that transient failures are retried and eventually succeed for idempotent endpoints."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return Response("Service Unavailable", status=503)
            return Response('{"status": "ok"}', status=200, mimetype="application/json")

        httpserver.expect_request("/health").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            response = _make_request("GET", "/health", timeout=5.0, max_retries=3)

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert call_count == 3  # Initial + 2 retries

    def test_retry_exhaustion(self, httpserver: HTTPServer):
        """Test that retry exhaustion raises the last exception for idempotent endpoints."""
        def handler(request):
            return Response("Service Unavailable", status=503)

        httpserver.expect_request("/health").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                _make_request("GET", "/health", timeout=5.0, max_retries=3)

        assert exc_info.value.response.status_code == 503

    def test_non_idempotent_no_retry_on_failure(self, httpserver: HTTPServer):
        """Test that non-idempotent endpoints are not retried on failure."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            return Response("Internal Server Error", status=500)

        httpserver.expect_request("/predict").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                _make_request("POST", "/predict", json={"test": "data"}, timeout=5.0, max_retries=3)

        assert exc_info.value.response.status_code == 500
        assert call_count == 1  # No retries for non-idempotent

    def test_retry_after_header_respected(self, httpserver: HTTPServer):
        """Test that Retry-After header is respected."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return Response("Rate Limited", status=429, headers={"Retry-After": "1"})
            return Response('{"status": "ok"}', status=200, mimetype="application/json")

        httpserver.expect_request("/health").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            response = _make_request("GET", "/health", timeout=5.0, max_retries=3)

        assert response.status_code == 200
        assert call_count == 2

    @pytest.mark.slow
    def test_retry_after_capped_at_60_seconds(self, httpserver: HTTPServer):
        """Test that Retry-After is capped at 60 seconds."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return Response("Rate Limited", status=429, headers={"Retry-After": "120"})
            return Response('{"status": "ok"}', status=200, mimetype="application/json")

        httpserver.expect_request("/health").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            start = time.time()
            response = _make_request("GET", "/health", timeout=5.0, max_retries=3)
            elapsed = time.time() - start

        assert response.status_code == 200
        # Should wait ~60 seconds (capped), not 120
        assert 55 <= elapsed <= 70

    def test_permanent_error_not_retried(self, httpserver: HTTPServer):
        """Test that permanent errors (4xx except 429) are not retried."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            return Response("Bad Request", status=400)

        httpserver.expect_request("/health").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                _make_request("GET", "/health", timeout=5.0, max_retries=3)

        assert exc_info.value.response.status_code == 400
        assert call_count == 1  # No retries for permanent errors

    def test_auth_failure_not_retried(self, httpserver: HTTPServer):
        """Test that authentication failures (401, 403) are not retried."""
        for status in [401, 403]:
            call_count = 0
            httpserver.clear_all_handlers()

            def handler(request, status=status):
                nonlocal call_count
                call_count += 1
                return Response("Unauthorized", status=status)

            httpserver.expect_request("/health").respond_with_handler(handler)

            base_url = httpserver.url_for("")
            with patch("dashboard.api_client.API_URL", base_url):
                with pytest.raises(httpx.HTTPStatusError) as exc_info:
                    _make_request("GET", "/health", timeout=5.0, max_retries=3)

            assert exc_info.value.response.status_code == status
            assert call_count == 1  # No retries for auth failures


class TestPredictionContracts:
    """Test single and batch prediction contracts with mock server."""

    @pytest.fixture
    def sample_customer(self):
        return {
            "customerID": "1111-TEST",
            "gender": "Female",
            "SeniorCitizen": 0,
            "Partner": "Yes",
            "Dependents": "No",
            "tenure": 12,
            "PhoneService": "Yes",
            "MultipleLines": "No",
            "InternetService": "DSL",
            "OnlineSecurity": "No",
            "OnlineBackup": "Yes",
            "DeviceProtection": "No",
            "TechSupport": "No",
            "StreamingTV": "No",
            "StreamingMovies": "No",
            "Contract": "Month-to-month",
            "PaperlessBilling": "Yes",
            "PaymentMethod": "Electronic check",
            "MonthlyCharges": 50.0,
            "TotalCharges": "600.0"
        }

    def test_single_prediction_success(self, httpserver: HTTPServer, sample_customer):
        """Test successful single prediction request."""
        def handler(request):
            return Response(
                '{"customerID": "1111-TEST", "churn_probability": 0.75, "churn_prediction": 1, "risk_segment": "High", "model_version": "1.0.0"}',
                status=200, mimetype="application/json"
            )

        httpserver.expect_request("/predict", method="POST").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            result = predict(sample_customer)

        assert result["customerID"] == "1111-TEST"
        assert result["churn_probability"] == 0.75
        assert result["churn_prediction"] == 1
        assert result["risk_segment"] == "High"

    def test_batch_prediction_success(self, httpserver: HTTPServer, sample_customer):
        """Test successful batch prediction request."""
        def handler(request):
            return Response(
                '{"predictions": [{"customerID": "1111-TEST", "churn_probability": 0.75, "churn_prediction": 1, "risk_segment": "High", "model_version": "1.0.0"}, {"customerID": "1111-TEST-2", "churn_probability": 0.25, "churn_prediction": 0, "risk_segment": "Low", "model_version": "1.0.0"}]}',
                status=200, mimetype="application/json"
            )

        httpserver.expect_request("/predict/batch", method="POST").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            result = predict_batch([sample_customer, {**sample_customer, "customerID": "1111-TEST-2"}])

        assert len(result["predictions"]) == 2
        assert result["predictions"][0]["customerID"] == "1111-TEST"
        assert result["predictions"][1]["customerID"] == "1111-TEST-2"

    def test_batch_prediction_empty_list_rejected(self, httpserver: HTTPServer):
        """Test that empty batch is rejected by server."""
        def handler(request):
            return Response("Empty customer list", status=400)

        httpserver.expect_request("/predict/batch", method="POST").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                predict_batch([])

        assert exc_info.value.response.status_code == 400

    def test_invalid_single_prediction_rejected(self, httpserver: HTTPServer):
        """Test that invalid single prediction is rejected."""
        def handler(request):
            return Response("Validation error", status=422)

        httpserver.expect_request("/predict", method="POST").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                predict({"invalid": "data"})

        assert exc_info.value.response.status_code == 422

    def test_batch_not_retried_on_failure(self, httpserver: HTTPServer, sample_customer):
        """Test that batch prediction failures are not retried."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            return Response("Internal Server Error", status=500)

        httpserver.expect_request("/predict/batch", method="POST").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                predict_batch([sample_customer])

        assert exc_info.value.response.status_code == 500
        assert call_count == 1  # No retries for non-idempotent

    def test_single_prediction_not_retried_on_failure(self, httpserver: HTTPServer, sample_customer):
        """Test that single prediction failures are not retried."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            return Response("Internal Server Error", status=500)

        httpserver.expect_request("/predict", method="POST").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                predict(sample_customer)

        assert exc_info.value.response.status_code == 500
        assert call_count == 1  # No retries for non-idempotent

    def test_explain_retried_on_failure(self, httpserver: HTTPServer, sample_customer):
        """Test that explain endpoint is retried on failure (idempotent)."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return Response("Service Unavailable", status=503)
            return Response(
                '{"customerID": "1111-TEST", "base_value": 0.1, "features": [{"name": "tenure", "contribution": 0.05}]}',
                status=200, mimetype="application/json"
            )

        httpserver.expect_request("/explain", method="POST").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            result = explain(sample_customer)

        assert result["customerID"] == "1111-TEST"
        assert call_count == 2  # Initial + 1 retry

    def test_retention_recommendation_not_retried(self, httpserver: HTTPServer, sample_customer):
        """Test that retention recommendation is not retried."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            return Response("Internal Server Error", status=500)

        httpserver.expect_request("/retention-recommendation", method="POST").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                get_retention_recommendation(sample_customer)

        assert exc_info.value.response.status_code == 500
        assert call_count == 1


class TestAuthenticationHandling:
    """Test authentication header handling."""

    def test_api_key_header_sent(self, httpserver: HTTPServer):
        """Test that API key header is sent with requests."""
        received_headers = {}

        def handler(request):
            received_headers.update(dict(request.headers))
            return Response('{"status": "ok"}', status=200, mimetype="application/json")

        httpserver.expect_request("/health").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url), \
             patch("dashboard.api_client.API_KEY", "test-api-key-123"), \
             patch("dashboard.api_client.API_KEY_HEADER", "X-API-Key"):
            response = _make_request("GET", "/health", timeout=5.0)

        assert response.status_code == 200
        # Headers are case-insensitive, normalize to lowercase for comparison
        normalized_headers = {k.lower(): v for k, v in received_headers.items()}
        assert normalized_headers.get("x-api-key") == "test-api-key-123"

    def test_no_api_key_header_when_not_configured(self, httpserver: HTTPServer):
        """Test that no API key header is sent when not configured."""
        received_headers = {}

        def handler(request):
            received_headers.update(dict(request.headers))
            return Response('{"status": "ok"}', status=200, mimetype="application/json")

        httpserver.expect_request("/health").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url), \
             patch("dashboard.api_client.API_KEY", ""), \
             patch("dashboard.api_client.API_KEY_HEADER", "X-API-Key"):
            response = _make_request("GET", "/health", timeout=5.0)

        assert response.status_code == 200
        # Headers are case-insensitive, normalize to lowercase for comparison
        normalized_headers = {k.lower(): v for k, v in received_headers.items()}
        assert "x-api-key" not in normalized_headers


class TestHealthAndModelInfo:
    """Test health and model info endpoints."""

    def test_get_health_success(self, httpserver: HTTPServer):
        """Test health check success."""
        httpserver.expect_request("/health").respond_with_json({"status": "ok"})

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            assert get_health() is True

    def test_get_health_failure(self, httpserver: HTTPServer):
        """Test health check failure returns False."""
        httpserver.expect_request("/health").respond_with_data("Service Unavailable", status=503)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            assert get_health() is False

    def test_get_model_info_success(self, httpserver: HTTPServer):
        """Test model info retrieval."""
        model_info = {
            "version": "1.0.0",
            "threshold": 0.65,
            "features": ["tenure", "MonthlyCharges"]
        }
        httpserver.expect_request("/model/info").respond_with_json(model_info)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            result = get_model_info()
            assert result == model_info


class TestConnectionHandling:
    """Test connection pooling and client lifecycle."""

    def test_client_reuse(self):
        """Test that HTTP client is reused."""
        # Clear global client first
        import dashboard.api_client as api_client_module
        api_client_module._http_client = None

        client1 = api_client_module._get_client()
        client2 = api_client_module._get_client()
        assert client1 is client2

    def test_client_close(self):
        """Test client close functionality."""
        import dashboard.api_client as api_client_module
        api_client_module._http_client = None

        api_client_module._get_client()
        assert api_client_module._http_client is not None
        api_client_module.close_client()
        assert api_client_module._http_client is None

    def test_timeout_configuration(self, httpserver: HTTPServer):
        """Test that timeout is properly configured."""
        def handler(request):
            time.sleep(2)  # Simulate slow response
            return Response('{"status": "ok"}', status=200, mimetype="application/json")

        httpserver.expect_request("/health").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url), \
             patch("dashboard.api_client.BASE_TIMEOUT", 0.5):
            with pytest.raises(httpx.TimeoutException):
                _make_request("GET", "/health", timeout=0.5, max_retries=0)


class TestRetryExhaustionBehavior:
    """Test retry exhaustion behavior."""

    def test_retry_exhaustion_preserves_last_exception(self, httpserver: HTTPServer):
        """Test that retry exhaustion preserves the last exception."""
        def handler(request):
            return Response("Service Unavailable", status=503)

        httpserver.expect_request("/health").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                _make_request("GET", "/health", timeout=5.0, max_retries=3)

        assert exc_info.value.response.status_code == 503

    def test_max_retries_configurable(self, httpserver: HTTPServer):
        """Test that max_retries parameter controls retry count."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            return Response("Service Unavailable", status=503)

        httpserver.expect_request("/health").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            with pytest.raises(httpx.HTTPStatusError):
                _make_request("GET", "/health", timeout=5.0, max_retries=2)

        assert call_count == 3  # Initial + 2 retries = 3 attempts


class TestBackoffBehavior:
    """Test exponential backoff with jitter."""

    @pytest.mark.slow
    def test_backoff_timing(self, httpserver: HTTPServer):
        """Test that exponential backoff with jitter is applied."""
        call_times = []

        def handler(request):
            call_times.append(time.time())
            return Response("Service Unavailable", status=503)

        httpserver.expect_request("/health").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            with pytest.raises(httpx.HTTPStatusError):
                _make_request("GET", "/health", timeout=5.0, max_retries=2)

        # Should have 3 calls (initial + 2 retries)
        assert len(call_times) == 3

        # Check intervals are growing (exponential backoff)
        interval1 = call_times[1] - call_times[0]
        interval2 = call_times[2] - call_times[1]

        # Second interval should be larger (exponential backoff)
        # With jitter, we allow some variance
        assert interval1 >= 0.5  # initial ~1.0 with jitter
        assert interval2 >= 1.0  # second ~2.0 with jitter


class TestClientErrors:
    """Test client error handling."""

    def test_connection_error(self, httpserver: HTTPServer):
        """Test handling of connection errors."""
        httpserver.expect_request("/health").respond_with_data(b"", status=502)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            with pytest.raises(httpx.HTTPStatusError):
                _make_request("GET", "/health", timeout=5.0, max_retries=1)

    def test_invalid_json_response(self, httpserver: HTTPServer):
        """Test handling of invalid JSON responses."""
        def handler(request):
            return Response("not valid json", status=200, mimetype="application/json")

        httpserver.expect_request("/health").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            response = _make_request("GET", "/health", timeout=5.0, max_retries=0)
            # Should still return response even with invalid JSON
            assert response.status_code == 200

    def test_non_json_content_type(self, httpserver: HTTPServer):
        """Test handling of non-JSON content type."""
        def handler(request):
            return Response("OK", status=200, mimetype="text/plain")

        httpserver.expect_request("/health").respond_with_handler(handler)

        base_url = httpserver.url_for("")
        with patch("dashboard.api_client.API_URL", base_url):
            response = _make_request("GET", "/health", timeout=5.0, max_retries=0)
            assert response.status_code == 200


# Run tests when executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
