"""Durable work identity and failure evidence; Redis is transport, not truth."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.domain_types import TradingMode, utc_now
from app.orm_types import EntityColumns, UtcDateTime


class JobKind(StrEnum):
    AUDIT_CHECKPOINT = "audit_checkpoint"


class JobStatus(StrEnum):
    READY = "READY"
    RETRY = "RETRY"
    SUCCEEDED = "SUCCEEDED"
    DEAD = "DEAD"


class Job(EntityColumns, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        CheckConstraint(
            "queue_name ~ '^[A-Za-z0-9][A-Za-z0-9:-]{0,99}$'", name="queue_name_format"
        ),
        CheckConstraint("mode = 'PAPER'", name="paper_only"),
        CheckConstraint("attempts >= 0 AND attempts <= max_attempts", name="attempt_bounds"),
        CheckConstraint("max_attempts BETWEEN 1 AND 10", name="max_attempts_bounds"),
    )
    idempotency_key: Mapped[UUID] = mapped_column(nullable=False)
    queue_name: Mapped[str] = mapped_column(String(100), default="trading-ai", nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column()
    kind: Mapped[JobKind] = mapped_column(
        Enum(
            JobKind,
            name="job_kind",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
            validate_strings=True,
        ),
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            name="job_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=JobStatus.READY,
        nullable=False,
    )
    mode: Mapped[TradingMode] = mapped_column(
        Enum(
            TradingMode,
            name="job_mode",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=TradingMode.PAPER,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), default=utc_now, nullable=False
    )
    dispatch_after: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(32))


class DeadLetter(EntityColumns, Base):
    __tablename__ = "dead_letters"
    __table_args__ = (
        UniqueConstraint("job_id"),
        CheckConstraint("attempts > 0", name="positive_attempts"),
        CheckConstraint("error_code = 'HANDLER_FAILED'", name="error_code_allowed"),
    )
    job_id: Mapped[UUID] = mapped_column(ForeignKey("trading.jobs.id"), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str] = mapped_column(String(32), nullable=False)
