"""
Phase 1 API tests – health check endpoints.
Updated for Phase 2 dynamic database readiness.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a synchronous TestClient."""
    return TestClient(app)


def test_root_endpoint(client: TestClient):
    """Root should return API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "VisionTrace AI" in data["message"]


def test_health_check(client: TestClient):
    """Health endpoint returns 200 with status ok."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "VisionTrace AI"
    assert "version" in data
    assert "timestamp" in data
    assert "uptime_seconds" in data


def test_health_check_detailed(client: TestClient):
    """
    Detailed health endpoint returns subsystem statuses.
    Status is 'ok' when DB is running, or 'degraded' when DB is offline.
    """
    response = client.get("/api/v1/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert "subsystems" in data
    assert data["subsystems"]["api"]["status"] == "ok"
    assert data["subsystems"]["database"]["status"] in ("ok", "unreachable")
    assert "runtime" in data
    assert "python" in data["runtime"]


def test_openapi_schema(client: TestClient):
    """OpenAPI schema endpoint is accessible."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "VisionTrace AI"


def test_docs_endpoint(client: TestClient):
    """Swagger UI docs are accessible."""
    response = client.get("/docs")
    assert response.status_code == 200
