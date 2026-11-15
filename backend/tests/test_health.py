import logging

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_lifecycle_health_and_shutdown(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.main")
    application = create_app()
    assert application.state.ready is False
    with TestClient(application) as client:
        assert client.get("/health/live").json() == {
            "status": "alive",
            "mode": "PAPER",
            "scope": "process",
        }
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"
    assert application.state.ready is False
    assert "backend_ready" in caplog.text
    assert "backend_stopped" in caplog.text


def test_readiness_fails_closed_without_started_lifespan() -> None:
    client = TestClient(create_app())
    assert client.get("/health/live").status_code == 200
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_openapi_and_absence_of_execution_routes() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]
        assert {"/health/live", "/health/ready"}.issubset(paths)
        assert "/api/v1/orders" not in paths
        assert "503" in paths["/health/ready"]["get"]["responses"]
        assert client.post("/api/v1/orders", json={}).status_code == 404


def test_shutdown_on_context_exception() -> None:
    application = create_app()
    with pytest.raises(RuntimeError, match="synthetic failure"):
        with TestClient(application):
            raise RuntimeError("synthetic failure")
    assert application.state.ready is False


def test_app_instances_do_not_share_readiness() -> None:
    first, second = create_app(), create_app()
    with TestClient(first):
        assert first.state.ready is True
        assert second.state.ready is False
