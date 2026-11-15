"""Append-only metadata audit; deliberately no arbitrary text/JSON payload."""

from enum import StrEnum
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, Enum, FetchedValue, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.domain_types import TradingMode
from app.orm_types import EntityColumns


class AuditType(StrEnum):
    SYSTEM = "SYSTEM"
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    ACCOUNT_CHANGED = "ACCOUNT_CHANGED"
    POLICY_CHANGED = "POLICY_CHANGED"
    ORDER_INTENT = "ORDER_INTENT"
    RISK_DECISION = "RISK_DECISION"
    ORDER_SUBMIT = "ORDER_SUBMIT"
    ORDER_STATUS = "ORDER_STATUS"
    FILL = "FILL"
    RECONCILIATION = "RECONCILIATION"
    STOP = "STOP"
    RESUME = "RESUME"


class AuditReason(StrEnum):
    SYSTEM_EVENT = "SYSTEM_EVENT"
    USER_ACTION = "USER_ACTION"
    RISK_LIMIT = "RISK_LIMIT"
    STALE_DATA = "STALE_DATA"
    UNKNOWN_ORDER = "UNKNOWN_ORDER"
    AUTH_FAILURE = "AUTH_FAILURE"
    RECOVERY = "RECOVERY"


class AuditEvent(EntityColumns, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("sequence"),
        CheckConstraint("sequence > 0", name="positive_sequence"),
        CheckConstraint("mode = 'PAPER'", name="paper_only"),
        CheckConstraint(
            "previous_hash ~ '^[a-f0-9]{64}$' AND event_hash ~ '^[a-f0-9]{64}$'", name="hash_format"
        ),
    )
    sequence: Mapped[int] = mapped_column(BigInteger, server_default=FetchedValue(), nullable=False)
    event_type: Mapped[AuditType] = mapped_column(
        Enum(
            AuditType,
            name="audit_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    reason: Mapped[AuditReason] = mapped_column(
        Enum(
            AuditReason,
            name="audit_reason",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=AuditReason.SYSTEM_EVENT,
        nullable=False,
    )
    mode: Mapped[TradingMode] = mapped_column(
        Enum(
            TradingMode,
            name="audit_mode",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=TradingMode.PAPER,
        nullable=False,
    )
    correlation_id: Mapped[UUID] = mapped_column(nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column()
    entity_id: Mapped[UUID | None] = mapped_column()
    previous_hash: Mapped[str] = mapped_column(
        String(64), server_default=FetchedValue(), nullable=False
    )
    event_hash: Mapped[str] = mapped_column(
        String(64), server_default=FetchedValue(), nullable=False
    )
