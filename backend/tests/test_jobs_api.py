from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.auth import AuthService, create_user
from app.auth_api import service
from app.database import Database
from app.job_queue import enqueue
from app.main import create_app
from app.models.jobs import JobStatus

pytestmark = pytest.mark.integration


@pytest.fixture
def jobs_client(database: Database) -> Iterator[tuple[TestClient, dict[str, str], str]]:
    namespace = "page-" + uuid4().hex
    username, password = "page_" + uuid4().hex, "synthetic-pagination-password"
    with database.transaction() as session:
        create_user(session, username=username, password=SecretStr(password), enabled=True)
        for position in range(3):
            job = enqueue(
                session, idempotency_key=uuid4(), correlation_id=uuid4(), queue_name=namespace
            )
            job.created_at = datetime(2026, 1, 1, tzinfo=UTC)
            if position == 2:
                job.status = JobStatus.SUCCEEDED
    application = create_app()
    application.dependency_overrides[service] = lambda: AuthService(database)
    with TestClient(application, client=("page-" + uuid4().hex, 50000)) as client:
        token = client.post(
            "/api/v1/auth/login", json={"username": username, "password": password}
        ).json()["access_token"]
        yield client, {"Authorization": "Bearer " + token}, namespace


def test_keyset_pages_no_duplicate_tied_timestamps_and_filters(
    jobs_client: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, namespace = jobs_client
    request = {"queue_name": namespace, "limit": 2}
    first = client.get("/api/v1/jobs", headers=headers, params=request)
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    body = first.json()
    assert len(body["items"]) == 2 and body["has_more"] is True
    second = client.get(
        "/api/v1/jobs", headers=headers, params=request | {"cursor": body["next_cursor"]}
    ).json()
    assert (
        len(second["items"]) == 1 and second["has_more"] is False and second["next_cursor"] is None
    )
    identities = [row["id"] for row in body["items"] + second["items"]]
    assert len(set(identities)) == 3
    ready = client.get(
        "/api/v1/jobs", headers=headers, params={"queue_name": namespace, "status": "READY"}
    ).json()
    assert len(ready["items"]) == 2 and all(row["status"] == "READY" for row in ready["items"])
    assert client.get("/api/v1/jobs").status_code == 401
    mismatch = client.get(
        "/api/v1/jobs",
        headers=headers,
        params=request | {"cursor": body["next_cursor"], "status": "DEAD"},
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"limit": "bad"},
        {"status": "UNKNOWN"},
        {"cursor": "!!!"},
        {"cursor": "A"},
        {"cursor": "a" * 1025},
        {"queue_name": "bad/name"},
        {"offset": 1},
        {"unknown_filter": "ignored-is-forbidden"},
    ],
)
def test_invalid_pagination_returns_canonical_422(
    jobs_client: tuple[TestClient, dict[str, str], str], params: dict[str, object]
) -> None:
    client, headers, _ = jobs_client
    response = client.get("/api/v1/jobs", headers=headers, params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
