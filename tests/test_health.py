"""Health endpoint smoke tests."""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "ai-agent-system"
    assert "version" in body
    assert "env" in body


def test_version_endpoint(client: TestClient) -> None:
    response = client.get("/version")
    assert response.status_code == 200
    body = response.json()
    assert "version" in body
    assert "env" in body


def test_health_no_auth_required(client: TestClient) -> None:
    """Health endpoint must not require X-Internal-Key (used by Docker probes)."""
    response = client.get("/health")  # no headers
    assert response.status_code == 200
