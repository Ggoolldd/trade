"""Periodic UTC scheduling cursor and durable occurrence-to-job lineage."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.jobs import JobKind
from app.orm_types import EntityColumns, UtcDateTime


class Schedule(EntityColumns, Base):
    __tablename__ = "schedules"
    __table_args__ = (
        UniqueConstraint("name"),
        CheckConstraint("name ~ '^[A-Za-z0-9][A-Za-z0-9:-]{0,99}$'", name="name_format"),
        CheckConstraint(
            "queue_name ~ '^[A-Za-z0-9][A-Za-z0-9:-]{0,99}$'", name="queue_name_format"
        ),
        CheckConstraint("interval_seconds BETWEEN 1 AND 86400", name="interval_bounds"),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    queue_name: Mapped[str] = mapped_column(String(100), default="trading-ai", nullable=False)
    kind: Mapped[JobKind] = mapped_column(
        Enum(
            JobKind,
            name="schedule_job_kind",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
            validate_strings=True,
        ),
        nullable=False,
    )
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ScheduledRun(EntityColumns, Base):
    __tablename__ = "scheduled_runs"
    __table_args__ = (
        UniqueConstraint("schedule_id", "scheduled_at"),
        UniqueConstraint("job_id"),
    )
    schedule_id: Mapped[UUID] = mapped_column(ForeignKey("trading.schedules.id"), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("trading.jobs.id"), nullable=False)
