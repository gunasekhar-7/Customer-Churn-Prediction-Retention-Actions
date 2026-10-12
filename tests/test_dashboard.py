from unittest.mock import Mock, patch

from dashboard.api_client import get_health, predict


@patch("dashboard.api_client.httpx.get")
def test_api_client_health_success(mock_get):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    assert get_health() is True

@patch("dashboard.api_client.httpx.get")
def test_api_client_health_failure(mock_get):
    # Simulate connection error
    mock_get.side_effect = Exception("Connection Error")

    assert get_health() is False

@patch("dashboard.api_client.httpx.post")
def test_api_client_predict(mock_post):
    mock_response = Mock()
    mock_response.json.return_value = {"churn_probability": 0.8}
    mock_post.return_value = mock_response

    # Using dummy data, as the client just passes the dict
    result = predict({"customerID": "123"})

    assert "churn_probability" in result
    assert result["churn_probability"] == 0.8
    mock_post.assert_called_once()
