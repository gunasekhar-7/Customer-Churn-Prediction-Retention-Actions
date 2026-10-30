"""Tests for go/through routing configuration."""

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.database import Base, get_engine


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure database tables exist for go/through tests."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield


def test_go_through_health():
    """Test go/through health endpoint."""
    with TestClient(app) as client:
        response = client.get("/go/through/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "module": "go/through"}


def test_go_through_workflow_status():
    """Test go/through workflow status endpoint."""
    with TestClient(app) as client:
        response = client.get("/go/through/workflow-status")
        assert response.status_code == 200
        data = response.json()
        assert "module" in data
        assert data["module"] == "go/through"
