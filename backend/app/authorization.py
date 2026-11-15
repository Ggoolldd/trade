"""Server-side role guards; no claim that future trading endpoints already exist."""

from collections.abc import Callable
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.audit import append_event
from app.auth import AuthService, Identity
from app.auth_api import current_identity, service
from app.models.audit import AuditReason, AuditType
from app.models.auth import UserRole


class Permission(StrEnum):
    STATUS_READ = "status:read"
    PORTFOLIO_READ = "portfolio:read"
    ORDERS_READ = "orders:read"
    RISK_READ = "risk:read"
    CONFIG_WRITE = "config:write"
    ORDER_INTENT = "orders:intent"
    ORDER_CANCEL = "orders:cancel"
    RISK_WRITE = "risk:write"
    STOP = "control:stop"
    RESUME = "control:resume"


READ_PERMISSIONS = frozenset(
    {
        Permission.STATUS_READ,
        Permission.PORTFOLIO_READ,
        Permission.ORDERS_READ,
        Permission.RISK_READ,
    }
)
PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.OWNER: frozenset(Permission),
    UserRole.READONLY: READ_PERMISSIONS,
    UserRole.SYSTEM_WORKER: READ_PERMISSIONS | {Permission.ORDER_INTENT, Permission.ORDER_CANCEL},
}


def require_permission(permission: Permission) -> Callable[..., Identity]:
    def guard(
        request: Request,
        identity: Annotated[Identity, Depends(current_identity)],
        auth: Annotated[AuthService, Depends(service)],
    ) -> Identity:
        if permission not in PERMISSIONS.get(identity.role, frozenset()):
            with auth.database.transaction() as session:
                append_event(
                    session,
                    event_type=AuditType.AUTHORIZATION,
                    correlation_id=request.state.request_id,
                    actor_id=identity.user_id,
                    reason=AuditReason.AUTH_FAILURE,
                )
            raise HTTPException(403, detail="Permission denied")
        return identity

    return guard


class Capabilities(BaseModel):
    role: UserRole
    permissions: list[Permission]


router = APIRouter(prefix="/api/v1", tags=["authorization"])


@router.get("/capabilities", response_model=Capabilities)
def capabilities(identity: Annotated[Identity, Depends(current_identity)]) -> Capabilities:
    return Capabilities(
        role=identity.role, permissions=sorted(PERMISSIONS.get(identity.role, frozenset()))
    )
