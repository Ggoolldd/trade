from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select

from app.auth import AuthenticationDenied, AuthService, create_user, digest
from app.auth_api import service
from app.database import Database
from app.domain_types import utc_now
from app.main import create_app
from app.models.auth import AuthSession, User

pytestmark = pytest.mark.integration
PASSWORD = "synthetic-fixture-password-123"


@dataclass
class Clock:
    now: datetime

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def auth_setup(database: Database) -> Iterator[tuple[AuthService, Clock, str, TestClient]]:
    username = "fixture_" + uuid4().hex
    clock = Clock(utc_now())
    with database.transaction() as session:
        create_user(session, username=username, password=SecretStr(PASSWORD), enabled=True)
    auth = AuthService(database, clock)
    app = create_app()
    app.dependency_overrides[service] = lambda: auth
    with TestClient(app, client=("fixture-" + uuid4().hex, 50000)) as client:
        yield auth, clock, username, client


def login(client: TestClient, username: str, password: str = PASSWORD) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    return response.json()["access_token"]


def test_session_hashing_expiry_and_logout(
    database: Database, auth_setup: tuple[AuthService, Clock, str, TestClient]
) -> None:
    auth, clock, username, client = auth_setup
    raw = login(client, username)
    header = {"Authorization": "Bearer " + raw}
    assert client.get("/api/v1/auth/me", headers=header).json()["username"] == username
    with database.transaction() as session:
        user = session.scalar(select(User).where(User.username == username))
        assert user is not None and user.password_hash.startswith("$argon2id$")
        assert PASSWORD not in user.password_hash
        stored = session.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
        assert stored is not None and stored.token_hash == digest(raw)
        assert raw not in stored.token_hash
    assert client.post("/api/v1/auth/logout", headers=header).status_code == 204
    assert client.get("/api/v1/auth/me", headers=header).status_code == 401
    renewed = login(client, username)
    clock.now += timedelta(minutes=15)
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + renewed}).status_code
        == 401
    )
    with pytest.raises(AuthenticationDenied):
        auth.identify(SecretStr(raw))


def test_bruteforce_counters_commit_and_expire(
    auth_setup: tuple[AuthService, Clock, str, TestClient],
) -> None:
    _, clock, username, client = auth_setup
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/auth/login", json={"username": username, "password": "wrong"}
            ).status_code
            == 401
        )
    blocked = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "900"
    clock.now += timedelta(minutes=15, seconds=1)
    assert login(client, username)


def test_concurrent_failed_logins_do_not_bypass_limit(
    auth_setup: tuple[AuthService, Clock, str, TestClient],
) -> None:
    auth, _, username, _ = auth_setup
    source = "concurrent-" + uuid4().hex

    def attempt(_: int) -> int:
        try:
            auth.login(
                username=username,
                password=SecretStr("wrong"),
                source=source,
                correlation_id=uuid4(),
            )
            return 200
        except AuthenticationDenied as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(attempt, range(8)))
    assert results.count(401) == 5
    assert results.count(429) == 3


def test_missing_malformed_tokens_and_disabled_user_rejected(
    database: Database, auth_setup: tuple[AuthService, Clock, str, TestClient]
) -> None:
    _, _, username, client = auth_setup
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"}).status_code
        == 401
    )
    token = login(client, username)
    with database.transaction() as session:
        user = session.scalar(select(User).where(User.username == username))
        assert user is not None
        user.enabled = False
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code
        == 401
    )


def test_unknown_user_and_wrong_password_have_same_public_error(
    auth_setup: tuple[AuthService, Clock, str, TestClient],
) -> None:
    _, _, username, client = auth_setup
    bodies = []
    for name in [username, "missing_" + uuid4().hex]:
        response = client.post("/api/v1/auth/login", json={"username": name, "password": "wrong"})
        assert response.status_code == 401
        body = response.json()["error"]
        bodies.append((body["code"], body["message"]))
        assert "wrong" not in response.text
    assert bodies[0] == bodies[1]


def test_audit_failure_cannot_issue_a_session(
    database: Database,
    auth_setup: tuple[AuthService, Clock, str, TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, username, client = auth_setup
    with database.transaction() as session:
        count = session.scalar(select(func.count()).select_from(AuthSession))

    def audit_failed(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic audit storage failure")

    monkeypatch.setattr("app.auth.append_event", audit_failed)
    response = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 500
    assert "access_token" not in response.text
    assert PASSWORD not in response.text
    assert response.headers["cache-control"] == "no-store"
    with database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(AuthSession)) == count


def test_user_creation_rejects_short_password(database: Database) -> None:
    with database.transaction() as session:
        with pytest.raises(ValueError, match="password length"):
            create_user(session, username="fixture_" + uuid4().hex, password=SecretStr("short"))
