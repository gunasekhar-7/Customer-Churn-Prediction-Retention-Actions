import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional

import httpx
from tenacity import (
    RetryError,
    after_log,
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY", "")
API_KEY_HEADER = os.getenv("API_KEY_HEADER", "X-API-Key")

MAX_RETRIES = 3
BASE_TIMEOUT = 10.0

# Endpoints that are safe to retry (idempotent HTTP methods + GET)
IDEMPOTENT_ENDPOINTS = {
    "/health",
    "/model/info",
}

# Non-idempotent endpoints that should NOT be retried automatically
NON_IDEMPOTENT_ENDPOINTS = {
    "/predict",
    "/predict/batch",
    "/retention-recommendation",
}


def _is_idempotent_endpoint(endpoint: str) -> bool:
    """Check if an endpoint is safe to retry (idempotent)."""
    if endpoint in IDEMPOTENT_ENDPOINTS:
        return True
    if endpoint.startswith("/model/") or endpoint.startswith("/health"):
        return True
    return False


def _is_retryable_status(status_code: int) -> bool:
    """Determine if an HTTP status code indicates a retryable error."""
    return status_code in (429, 500, 502, 503, 504)


def _is_retryable_result(result: httpx.Response) -> bool:
    """Check if we should retry based on the response."""
    return _is_retryable_status(result.status_code)


def _is_permanent_error(status_code: int) -> bool:
    """Determine if an HTTP status code indicates a permanent error that should not be retried."""
    return 400 <= status_code < 500 and status_code != 429


def _is_retryable_exception(exc: BaseException) -> bool:
    """Determine if an exception is retryable."""
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.NetworkError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return _is_retryable_status(exc.response.status_code)
    return False


def _is_permanent_exception(exc: BaseException) -> bool:
    """Determine if an exception represents a permanent error that should not be retried."""
    if isinstance(exc, httpx.HTTPStatusError):
        return _is_permanent_error(exc.response.status_code)
    return False


def _get_retry_after(response: httpx.Response) -> Optional[float]:
    """Extract Retry-After header value in seconds."""
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return None
    try:
        return float(retry_after)
    except ValueError:
        return None


def _make_retry_decorator(
    max_attempts: int = MAX_RETRIES,
    endpoint: str = "",
    is_idempotent: bool = False,
) -> Callable:
    """Create a tenacity retry decorator with appropriate configuration."""
    if not is_idempotent:
        return lambda func: func

    def _retry_if_retryable(retry_state: Any) -> bool:
        exc = retry_state.outcome.exception()
        if exc is None:
            return False
        if _is_permanent_exception(exc):
            return False
        return _is_retryable_exception(exc)

    # max_attempts is the number of retries, so total attempts = max_attempts + 1
    total_attempts = max_attempts + 1
    return retry(
        reraise=True,
        stop=stop_after_attempt(total_attempts),
        wait=wait_exponential_jitter(initial=1.0, max=10.0, jitter=0.5),
        retry=_retry_if_retryable,
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO),
    )


_http_client: Optional[httpx.Client] = None


def _get_client() -> httpx.Client:
    """Get or create the global HTTP client with connection pooling."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=httpx.Timeout(BASE_TIMEOUT, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return _http_client


def close_client() -> None:
    """Close the global HTTP client."""
    global _http_client
    if _http_client is not None:
        _http_client.close()
        _http_client = None


def _do_request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    timeout: float,
    json: Optional[Dict[str, Any]] = None,
    max_retries: int = MAX_RETRIES,
    endpoint: str = "",
    is_idempotent: bool = False,
    headers: Optional[Dict[str, str]] = None,
) -> httpx.Response:
    """Execute a request with retry logic applied."""
    retry_decorator = _make_retry_decorator(
        max_attempts=max_retries,
        endpoint=endpoint,
        is_idempotent=is_idempotent,
    )

    @retry_decorator
    def _do_request() -> httpx.Response:
        request_kwargs: Dict[str, Any] = {
            "method": method,
            "url": url,
            "timeout": timeout,
        }
        if json is not None:
            request_kwargs["json"] = json
        if headers:
            request_kwargs["headers"] = headers

        response = client.request(**request_kwargs)

        if response.status_code == 429:
            retry_after = _get_retry_after(response)
            if retry_after:
                logger.warning(f"Rate limited, waiting {retry_after}s before retry")
                time.sleep(min(retry_after, 60))

        if _is_permanent_error(response.status_code):
            response.raise_for_status()

        # For retryable status codes, raise to trigger retry
        if _is_retryable_status(response.status_code):
            response.raise_for_status()

        return response

    try:
        return _do_request()  # type: ignore[no-any-return]
    except RetryError as e:
        last_exception = e.last_attempt.exception()
        if last_exception:
            raise last_exception from None
        raise


def _make_request(
    method: str,
    endpoint: str,
    *,
    json: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
    max_retries: int = MAX_RETRIES,
) -> httpx.Response:
    """Make an HTTP request with retries and proper error handling.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint path
        json: Optional JSON body for POST/PUT requests
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts

    Returns:
        httpx.Response object

    Raises:
        httpx.HTTPStatusError: For permanent HTTP errors
        httpx.TimeoutException: If request times out after retries
        httpx.NetworkError: For network-level errors after retries
    """
    client = _get_client()
    timeout = timeout or BASE_TIMEOUT
    endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    is_idempotent = _is_idempotent_endpoint(endpoint)

    headers = {}
    if API_KEY:
        headers[API_KEY_HEADER] = API_KEY

    # Ensure no double slashes in URL
    base_url = API_URL.rstrip("/")
    url = f"{base_url}{endpoint}"

    return _do_request_with_retry(
        client=client,
        method=method,
        url=url,
        timeout=timeout,
        json=json,
        max_retries=max_retries,
        endpoint=endpoint,
        is_idempotent=is_idempotent,
        headers=headers,
    )


def get_health() -> bool:
    """Check API health with retries for transient failures.

    Returns:
        True if API is healthy, False otherwise
    """
    try:
        response = _make_request("GET", "/health", timeout=5.0, max_retries=2)
        return response.status_code == 200
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
        return False


def get_model_info() -> Dict[str, Any]:
    """Get model information with retries.

    Returns:
        Model information dictionary

    Raises:
        httpx.HTTPStatusError: For HTTP errors
        httpx.TimeoutException: If request times out after retries
        httpx.NetworkError: For network errors after retries
    """
    response = _make_request("GET", "/model/info", timeout=5.0)
    return response.json()  # type: ignore[no-any-return]


def predict(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Make a single prediction.

    NOTE: This is a NON-IDEMPOTENT operation (POST to /predict).
    Retries are NOT performed for this endpoint to avoid duplicate predictions.

    Args:
        customer_data: Customer feature data

    Returns:
        Prediction response dictionary

    Raises:
        httpx.HTTPStatusError: For HTTP errors
        httpx.TimeoutException: If request times out
        httpx.NetworkError: For network errors
    """
    response = _make_request(
        "POST",
        "/predict",
        json=customer_data,
        timeout=10.0,
        max_retries=0,
    )
    return response.json()  # type: ignore[no-any-return]


def predict_batch(customers_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Make batch predictions.

    NOTE: This is a NON-IDEMPOTENT operation (POST to /predict/batch).
    Retries are NOT performed for this endpoint to avoid duplicate predictions.

    Args:
        customers_data: List of customer feature data

    Returns:
        Batch prediction response

    Raises:
        httpx.HTTPStatusError: For HTTP errors
        httpx.TimeoutException: If request times out
        httpx.NetworkError: For network errors
    """
    response = _make_request(
        "POST",
        "/predict/batch",
        json={"customers": customers_data},
        timeout=30.0,
        max_retries=0,
    )
    return response.json()  # type: ignore[no-any-return]


def explain(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Get SHAP explanation for a customer.

    This is a NON-IDEMPOTENT operation (POST to /explain).
    Retries are NOT performed for this endpoint to avoid duplicate explanations.

    Args:
        customer_data: Customer feature data

    Returns:
        Explanation response dictionary

    Raises:
        httpx.HTTPStatusError: For HTTP errors
        httpx.TimeoutException: If request times out
        httpx.NetworkError: For network errors
    """
    response = _make_request(
        "POST",
        "/explain",
        json=customer_data,
        timeout=10.0,
        max_retries=0,
    )
    return response.json()  # type: ignore[no-any-return]


def get_retention_recommendation(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Get retention recommendations for a customer.

    NOTE: This is a NON-IDEMPOTENT operation (POST to /retention-recommendation).
    Retries are NOT performed for this endpoint to avoid duplicate recommendations.

    Args:
        customer_data: Customer feature data

    Returns:
        Retention recommendation response

    Raises:
        httpx.HTTPStatusError: For HTTP errors
        httpx.TimeoutException: If request times out
        httpx.NetworkError: For network errors
    """
    response = _make_request(
        "POST",
        "/retention-recommendation",
        json=customer_data,
        timeout=10.0,
        max_retries=0,
    )
    return response.json()  # type: ignore[no-any-return]


def get_model_metrics() -> Dict[str, Any]:
    """Get model performance metrics from artifact metadata.

    This is an IDEMPOTENT operation (GET to /model/metrics).
    Retries are performed for transient failures.

    Returns:
        Model metrics response dictionary

    Raises:
        httpx.HTTPStatusError: For HTTP errors
        httpx.TimeoutException: If request times out after retries
        httpx.NetworkError: For network errors after retries
    """
    response = _make_request("GET", "/model/metrics", timeout=10.0)
    return response.json()  # type: ignore[no-any-return]


def get_dashboard_metrics() -> Dict[str, Any]:
    """Get aggregated dashboard metrics.

    This is an IDEMPOTENT operation (GET to /dashboard/metrics).
    Retries are performed for transient failures.

    Returns:
        Dashboard metrics response dictionary

    Raises:
        httpx.HTTPStatusError: For HTTP errors
        httpx.TimeoutException: If request times out after retries
        httpx.NetworkError: For network errors after retries
    """
    response = _make_request("GET", "/dashboard/metrics", timeout=10.0)
    return response.json()  # type: ignore[no-any-return]
