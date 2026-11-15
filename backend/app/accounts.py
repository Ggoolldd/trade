"""Fail-closed virtual account resolution; this does not approve or submit orders."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain_types import TradingMode
from app.models.accounts import (
    AccountPermission,
    AccountScope,
    DevelopmentEnvironment,
    PaperAccount,
)
from app.models.auth import User, UserRole


class AccountAccessDenied(PermissionError):
    pass


def resolve_paper_account(
    session: Session,
    *,
    account_id: UUID,
    principal_id: UUID,
    intent_mode: TradingMode,
    environment: DevelopmentEnvironment,
) -> PaperAccount:
    if intent_mode is not TradingMode.PAPER:
        raise AccountAccessDenied("Only PAPER account resolution is implemented")
    principal = session.get(User, principal_id)
    if (
        principal is None
        or not principal.enabled
        or principal.role
        not in {
            UserRole.OWNER,
            UserRole.SYSTEM_WORKER,
        }
    ):
        raise AccountAccessDenied("Verified trading principal required")
    account = session.get(PaperAccount, account_id)
    if (
        account is None
        or not account.enabled
        or account.account_mode is not TradingMode.PAPER
        or account.environment != environment
    ):
        raise AccountAccessDenied("Account unavailable for this PAPER environment")
    permission = session.scalar(
        select(AccountPermission.id).where(
            AccountPermission.account_id == account_id,
            AccountPermission.environment == environment,
            AccountPermission.principal_id == principal_id,
            AccountPermission.scope == AccountScope.PAPER_TRADE,
        )
    )
    if permission is None:
        raise AccountAccessDenied("PAPER_TRADE permission required")
    return account
