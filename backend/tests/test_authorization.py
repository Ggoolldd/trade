from typing import Annotated
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import AuthService, Identity, create_user
from app.auth_api import service
from app.authorization import Permission, require_permission
from app.database import Database
from app.main import create_app
from app.models.auth import User, UserRole

pytestmark = pytest.mark.integration
PASSWORD = "synthetic-authorization-password"
EXPECTED = {
    UserRole.OWNER: {permission.value for permission in Permission},
    UserRole.READONLY: {"status:read", "portfolio:read", "orders:read", "risk:read"},
    UserRole.SYSTEM_WORKER: {
        "status:read",
        "portfolio:read",
        "orders:read",
        "risk:read",
        "orders:intent",
        "orders:cancel",
    },
}


def app_with_probes(database: Database) -> TestClient:
    application = create_app()
    auth = AuthService(database)
    application.dependency_overrides[service] = lambda: auth

    for permission in Permission:
        # Synthetic routes exercise the real guard, not fake trading implementations.
        def probe(
            identity: Annotated[Identity, Depends(require_permission(permission))],
        ) -> dict[str, bool]:
            return {"allowed": True}

        application.add_api_route("/test/guard/" + permission.value, probe, methods=["POST"])
    return TestClient(application, client=("authorization-" + uuid4().hex, 50000))


@pytest.mark.parametrize("role", list(UserRole))
def test_role_matrix_through_authenticated_api(database: Database, role: UserRole) -> None:
    username = "roles_" + uuid4().hex
    with database.transaction() as session:
        user = create_user(session, username=username, password=SecretStr(PASSWORD), enabled=True)
        user.role = role
    with app_with_probes(database) as client:
        token = client.post(
            "/api/v1/auth/login", json={"username": username, "password": PASSWORD}
        ).json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        capabilities = client.get("/api/v1/capabilities", headers=headers)
        assert capabilities.status_code == 200
        assert capabilities.json()["role"] == role.value
        assert set(capabilities.json()["permissions"]) == EXPECTED[role]
        for permission in Permission:
            response = client.post("/test/guard/" + permission.value, headers=headers)
            assert response.status_code == (200 if permission.value in EXPECTED[role] else 403)
        assert client.post("/test/guard/config:write").status_code == 401


def test_role_downgrade_takes_effect_for_existing_token(database: Database) -> None:
    username = "downgrade_" + uuid4().hex
    with database.transaction() as session:
        user = create_user(session, username=username, password=SecretStr(PASSWORD), enabled=True)
        user.role = UserRole.OWNER
        identity = user.id
    with app_with_probes(database) as client:
        token = client.post(
            "/api/v1/auth/login", json={"username": username, "password": PASSWORD}
        ).json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        assert client.post("/test/guard/control:stop", headers=headers).status_code == 200
        with database.transaction() as session:
            user = session.get(User, identity)
            assert user is not None
            user.role = UserRole.READONLY
        assert client.post("/test/guard/control:stop", headers=headers).status_code == 403
        spoofed = headers | {"X-Role": "owner"}
        assert client.post("/test/guard/risk:write", headers=spoofed).status_code == 403


def test_unknown_role_rejected_by_database(database: Database) -> None:
    with database.transaction() as session:
        user = create_user(
            session,
            username="invalid_role_" + uuid4().hex,
            password=SecretStr(PASSWORD),
            enabled=True,
        )
        identity = user.id
        assert user.role is UserRole.READONLY
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(
                text("UPDATE trading.users SET role='admin' WHERE id=:id"), {"id": identity}
            )
