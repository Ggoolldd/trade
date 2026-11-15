import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.domain_types import FinancialDecimal
from app.main import create_app


def test_404_and_method_errors_share_request_id() -> None:
    requested = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.get("/absent", headers={"X-Request-ID": requested})
        assert response.status_code == 404
        assert response.json()["error"] == {
            "code": "http_404",
            "message": "Request rejected",
            "request_id": requested,
        }
        assert response.headers["x-request-id"] == requested
        rejected = client.post("/health/live")
        assert rejected.status_code == 405
        assert "GET" in rejected.headers["allow"]


@pytest.mark.parametrize(
    "value", ["bad", "x" * 10000, '"quoted"', "00000000-0000-0000-0000-00000000000X"]
)
def test_bad_request_id_replaced(value: str) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/absent", headers={"X-Request-ID": value})
        identity = response.headers["x-request-id"]
        assert UUID(identity)
        assert identity != value
        assert response.json()["error"]["request_id"] == identity


def test_duplicate_request_id_headers_are_replaced() -> None:
    first, second = str(uuid4()), str(uuid4())
    with TestClient(create_app()) as client:
        response = client.get(
            "/health/live", headers=[("X-Request-ID", first), ("X-Request-ID", second)]
        )
        assert response.status_code == 200
        assert UUID(response.headers["x-request-id"])
        assert response.headers["x-request-id"] not in {first, second}


def test_validation_and_exception_details_are_sanitized(caplog: pytest.LogCaptureFixture) -> None:
    application = create_app()
    marker = "synthetic-error-canary"

    class Payload(BaseModel):
        amount: FinancialDecimal

    @application.post("/test/payload")
    def payload(value: Payload) -> Payload:
        return value

    @application.get("/test/reject")
    def reject() -> None:
        raise HTTPException(401, detail=marker, headers={"WWW-Authenticate": "Bearer"})

    @application.get("/test/failure")
    def fail() -> None:
        raise RuntimeError(marker)

    caplog.set_level(logging.ERROR)
    with TestClient(application) as client:
        for path, status in [("/test/reject", 401), ("/test/failure", 500)]:
            response = client.get(path)
            assert response.status_code == status
            assert marker not in response.text
            assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
        invalid = client.post("/test/payload", json={"amount": marker})
        assert invalid.status_code == 422
        assert marker not in invalid.text
        assert invalid.json()["error"]["code"] == "validation_error"
    assert marker not in caplog.text
    assert "request_failed request_id=" in caplog.text


def test_request_ids_are_isolated_across_concurrent_calls() -> None:
    with TestClient(create_app()) as client:

        def call(_: int) -> str:
            response = client.get("/absent")
            assert response.headers["x-request-id"] == response.json()["error"]["request_id"]
            return response.headers["x-request-id"]

        with ThreadPoolExecutor(max_workers=4) as pool:
            identifiers = list(pool.map(call, range(16)))
    assert len(set(identifiers)) == 16
