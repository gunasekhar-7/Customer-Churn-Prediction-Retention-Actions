import os

# Use file-based SQLite for better cross-thread sharing
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api import app
from src.database import Base, get_db
from src.monitoring import check_drift_thresholds, log_request_metrics

db_fd, db_path = tempfile.mkstemp(suffix='.db')
TEST_DATABASE_URL = f"sqlite:///{db_path}"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Create tables once for the test module
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    """Override database dependency for testing."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as client:
        yield client

    # Clean up dependency override after tests
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    os.close(db_fd)
    os.unlink(db_path)

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

    # Verify prediction was persisted to database

    from src.models import PredictionRecord

    # Use the test database session directly
    db = TestSessionLocal()
    try:
        # Query the prediction record
        pred_record = db.query(PredictionRecord).filter(
            PredictionRecord.customer_id == "1111-TEST"
        ).first()
        assert pred_record is not None
        assert pred_record.customer_id == "1111-TEST"
        assert pred_record.churn_probability == data["churn_probability"]
        assert pred_record.churn_prediction == data["churn_prediction"]
        assert pred_record.risk_segment == data["risk_segment"]
        assert pred_record.model_version == data["model_version"]
        assert pred_record.raw_features is not None
        # Verify data minimization: customerID is in customer_id column, not raw_features
        assert "customerID" not in pred_record.raw_features
        # Verify minimized fields are present
        assert "tenure" in pred_record.raw_features
        assert pred_record.raw_features["tenure"] == 12
        assert "Contract" in pred_record.raw_features
        assert pred_record.raw_features["Contract"] == "Month-to-month"
        assert "MonthlyCharges" in pred_record.raw_features
        assert pred_record.raw_features["MonthlyCharges"] == 50.0
        assert "InternetService" in pred_record.raw_features
        assert pred_record.raw_features["InternetService"] == "DSL"
        assert "TechSupport" in pred_record.raw_features
        assert pred_record.raw_features["TechSupport"] == "Yes"
        # Verify minimization metadata
        assert pred_record.raw_features["_minimized"] is True
    finally:
        db.close()

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
    # Validate each recommendation has the correct structure (action, reason)
    for rec in data["recommendations"]:
        assert "action" in rec
        assert "reason" in rec
        assert isinstance(rec["action"], str)
        assert isinstance(rec["reason"], str)
        assert len(rec["action"]) > 0
        assert len(rec["reason"]) > 0

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
