"""Tests for go/through routing configuration."""

from fastapi.testclient import TestClient


def test_go_through_health():
    """Test go/through health endpoint."""
    from src.api import app

    client = TestClient(app)
    response = client.get("/go/through/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "module": "go/through"}


def test_go_through_workflow_status():
    """Test go/through workflow status endpoint."""
    from src.api import app

    client = TestClient(app)
    response = client.get("/go/through/workflow-status")
    assert response.status_code == 200
    data = response.json()
    assert "module" in data
    assert data["module"] == "go/through"