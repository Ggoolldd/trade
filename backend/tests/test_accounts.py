from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.accounts import AccountAccessDenied, resolve_paper_account
from app.auth import create_user
from app.database import Database
from app.domain_types import TradingMode
from app.models.accounts import (
    AccountPermission,
    AccountScope,
    DevelopmentEnvironment,
    PaperAccount,
    TradingProfile,
)
from app.models.auth import User, UserRole

pytestmark = pytest.mark.integration


def create_principal(database: Database) -> UUID:
    with database.transaction() as session:
        user = create_user(
            session,
            username="account_" + uuid4().hex,
            password=SecretStr("synthetic-account-password"),
            enabled=True,
        )
        user.role = UserRole.OWNER
        return user.id


def test_paper_resolution_requires_identity_mode_environment_and_permission(
    database: Database,
) -> None:
    principal = create_principal(database)
    with database.transaction() as session:
        account = PaperAccount(
            name="paper-" + uuid4().hex, environment=DevelopmentEnvironment.LOCAL
        )
        session.add(account)
        session.flush()
        assert account.account_mode is TradingMode.PAPER
        assert account.enabled is False
        arguments = dict(
            account_id=account.id,
            principal_id=principal,
            intent_mode=TradingMode.PAPER,
            environment=DevelopmentEnvironment.LOCAL,
        )
        with pytest.raises(AccountAccessDenied):
            resolve_paper_account(session, **arguments)
        account.enabled = True
        session.flush()
        with pytest.raises(AccountAccessDenied):
            resolve_paper_account(session, **arguments)
        session.add(
            AccountPermission(
                account_id=account.id,
                environment=DevelopmentEnvironment.LOCAL,
                principal_id=principal,
                scope=AccountScope.PAPER_TRADE,
            )
        )
        session.flush()
        assert resolve_paper_account(session, **arguments).id == account.id
        user = session.get(User, principal)
        assert user is not None
        user.role = UserRole.READONLY
        session.flush()
        with pytest.raises(AccountAccessDenied):
            resolve_paper_account(session, **arguments)
        user.role = UserRole.OWNER
        session.flush()
        for overrides in [
            {"intent_mode": TradingMode.LIVE},
            {"intent_mode": TradingMode.SHADOW},
            {"environment": DevelopmentEnvironment.STAGING},
            {"principal_id": uuid4()},
            {"account_id": uuid4()},
        ]:
            with pytest.raises(AccountAccessDenied):
                resolve_paper_account(session, **(arguments | overrides))
        # Even an unpersisted/in-memory LIVE identity cannot be resolved for PAPER.
        account.account_mode = TradingMode.LIVE
        with pytest.raises(AccountAccessDenied):
            resolve_paper_account(session, **arguments)
        account.account_mode = TradingMode.PAPER


def test_live_and_production_storage_are_forbidden(database: Database) -> None:
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                PaperAccount(
                    name="forbidden-live",
                    environment=DevelopmentEnvironment.LOCAL,
                    account_mode=TradingMode.LIVE,
                )
            )
    with database.transaction() as session:
        account = PaperAccount(
            name="isolated-" + uuid4().hex, environment=DevelopmentEnvironment.LOCAL
        )
        session.add(account)
        session.flush()
        identity = account.id
    for column, value in [("account_mode", "LIVE"), ("environment", "PROD")]:
        with pytest.raises(IntegrityError):
            with database.transaction() as session:
                # Column names come only from the fixed test list, never API input.
                session.execute(
                    text(f"UPDATE trading.paper_accounts SET {column}=:value WHERE id=:id"),
                    {"value": value, "id": identity},
                )
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                TradingProfile(
                    account_id=identity,
                    environment=DevelopmentEnvironment.STAGING,
                    name="wrong-env",
                )
            )
    with database.transaction() as session:
        profile = TradingProfile(
            account_id=identity, environment=DevelopmentEnvironment.LOCAL, name="same"
        )
        session.add(profile)
        session.flush()
        assert profile.enabled is False
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                TradingProfile(
                    account_id=identity, environment=DevelopmentEnvironment.LOCAL, name="same"
                )
            )


def test_permissions_are_unique_and_never_withdrawal(database: Database) -> None:
    principal = create_principal(database)
    with database.transaction() as session:
        account = PaperAccount(
            name="permissions-" + uuid4().hex, environment=DevelopmentEnvironment.LOCAL
        )
        session.add(account)
        session.flush()
        identity = account.id
        grant = AccountPermission(
            account_id=identity,
            environment=DevelopmentEnvironment.LOCAL,
            principal_id=principal,
            scope=AccountScope.READ,
        )
        session.add(grant)
        session.flush()
        grant_id = grant.id
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                AccountPermission(
                    account_id=identity,
                    environment=DevelopmentEnvironment.LOCAL,
                    principal_id=principal,
                    scope=AccountScope.READ,
                )
            )
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(
                text("UPDATE trading.account_permissions SET scope='WITHDRAW' WHERE id=:id"),
                {"id": grant_id},
            )
