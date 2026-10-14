from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.monitoring import check_drift_thresholds, log_request_metrics


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as client:
        yield client

@pytest.fixture
def sample_payload():
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
        "TechSupport": "Yes",
        "StreamingTV": "No",
        "StreamingMovies": "No",
        "Contract": "Month-to-month",
        "PaperlessBilling": "Yes",
        "PaymentMethod": "Electronic check",
        "MonthlyCharges": 50.0,
        "TotalCharges": "600.0"
    }

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_ready(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

def test_model_info(client):
    response = client.get("/model/info")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "threshold" in data
    assert "features" in data
    assert isinstance(data["features"], list)

def test_predict(client, sample_payload):
    response = client.post("/predict", json=sample_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["customerID"] == "1111-TEST"
    assert "churn_probability" in data
    assert "churn_prediction" in data
    assert data["churn_prediction"] in [0, 1]
    assert "risk_segment" in data

def test_predict_batch(client, sample_payload):
    payload = {"customers": [sample_payload, sample_payload]}
    response = client.post("/predict/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "predictions" in data
    assert len(data["predictions"]) == 2

def test_explain(client, sample_payload):
    response = client.post("/explain", json=sample_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["customerID"] == "1111-TEST"
    assert "base_value" in data
    assert "features" in data
    assert len(data["features"]) > 0
    assert "name" in data["features"][0]
    assert "contribution" in data["features"][0]

def test_retention_recommendation(client, sample_payload):
    response = client.post("/retention-recommendation", json=sample_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["customerID"] == "1111-TEST"
    assert "risk_segment" in data
    assert "annual_revenue_exposure" in data
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)

def test_predict_invalid_schema(client):
    bad_payload = {"customerID": "bad"}
    response = client.post("/predict", json=bad_payload)
    assert response.status_code == 422

@patch("src.api.app_state")
def test_api_predict_exception(mock_state, client, sample_payload):
    mock_state["preprocessor"].transform.side_effect = Exception("Transformation failed")

    response = client.post("/predict", json=sample_payload)
    assert response.status_code == 400
    assert "Transformation failed" in response.json()["detail"]

@patch("src.api.app_state")
def test_api_predict_batch_exception(mock_state, client, sample_payload):
    response = client.post("/predict/batch", json={"customers": []})
    assert response.status_code == 400
    assert "Empty customer list" in response.json()["detail"]

    mock_state["preprocessor"].transform.side_effect = Exception("Transformation failed")
    response2 = client.post("/predict/batch", json={"customers": [sample_payload]})
    assert response2.status_code == 400
    assert "Transformation failed" in response2.json()["detail"]

@patch("src.api.app_state")
def test_api_explain_exception(mock_state, client, sample_payload):
    mock_state["preprocessor"].transform.side_effect = Exception("Transformation failed")
    response = client.post("/explain", json=sample_payload)
    assert response.status_code == 400
    assert "Transformation failed" in response.json()["detail"]

@patch("src.api.app_state")
def test_api_retention_exception(mock_state, client, sample_payload):
    mock_state["preprocessor"].transform.side_effect = Exception("Transformation failed")
    response = client.post("/retention-recommendation", json=sample_payload)
    assert response.status_code == 400
    assert "Transformation failed" in response.json()["detail"]

def test_api_ready_not_loaded(client):
    with patch("src.api.app_state", {}):
        response = client.get("/ready")
        assert response.status_code == 503

def test_api_model_info_not_loaded(client):
    with patch("src.api.app_state", {}):
        response = client.get("/model/info")
        assert response.status_code == 503

def test_log_request_metrics(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="churn_metrics"):
        log_request_metrics("/test", 12.3, 200, {"extra": "data"})
    assert "api_request" in caplog.text
    assert "/test" in caplog.text
    assert "12.3" in caplog.text
    assert "data" in caplog.text

def test_check_drift_thresholds(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="churn_metrics"):
        res = check_drift_thresholds(0.3)
        assert res is False
        assert "drift_alert" not in caplog.text

        res2 = check_drift_thresholds(0.9)
        assert res2 is True
        assert "drift_alert" in caplog.text
