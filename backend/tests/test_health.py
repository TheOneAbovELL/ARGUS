"""Tests for the ARGUS health endpoint."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    """The health endpoint should confirm that the API process is responsive."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

