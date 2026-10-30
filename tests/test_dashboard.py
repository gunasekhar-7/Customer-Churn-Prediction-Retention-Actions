from unittest.mock import Mock, patch

from dashboard.api_client import get_health, predict


@patch("dashboard.api_client._make_request")
def test_api_client_health_success(mock_make_request):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_make_request.return_value = mock_response

    assert get_health() is True


@patch("dashboard.api_client._make_request")
def test_api_client_health_failure(mock_make_request):
    # Simulate connection error
    import httpx
    mock_make_request.side_effect = httpx.NetworkError("Connection Error")

    assert get_health() is False


@patch("dashboard.api_client._make_request")
def test_api_client_predict(mock_make_request):
    mock_response = Mock()
    mock_response.json.return_value = {"churn_probability": 0.8}
    mock_make_request.return_value = mock_response

    # Using dummy data, as the client just passes the dict
    result = predict({"customerID": "123"})

    assert "churn_probability" in result
    assert result["churn_probability"] == 0.8
    mock_make_request.assert_called_once()
