import pytest
from fastapi.testclient import TestClient

from src.api import app


# We use TestClient as a context manager to trigger lifespan events
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
    # Missing required field 'gender'
    bad_payload = {"customerID": "bad"}
    response = client.post("/predict", json=bad_payload)
    assert response.status_code == 422 # Pydantic validation error
