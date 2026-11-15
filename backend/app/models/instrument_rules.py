"""Versioned public spot rules, without trading permission or feed entitlement."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.orm_types import EntityColumns, FinancialNumeric, UtcDateTime


class InstrumentRules(EntityColumns, Base):
    __tablename__ = "instrument_rules"
    __table_args__ = (
        UniqueConstraint("instrument_id", "source_sha256"),
        CheckConstraint(
            "tick_size > 0 AND quantity_step > 0 AND min_quantity > 0 AND min_notional_eur > 0",
            name="positive_rules",
        ),
        CheckConstraint("source_sha256 ~ '^[a-f0-9]{64}$'", name="source_hash"),
    )
    instrument_id: Mapped[UUID] = mapped_column(
        ForeignKey("trading.instruments.id"), nullable=False
    )
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    tick_size: Mapped[Decimal] = mapped_column(FinancialNumeric(), nullable=False)
    quantity_step: Mapped[Decimal] = mapped_column(FinancialNumeric(), nullable=False)
    min_quantity: Mapped[Decimal] = mapped_column(FinancialNumeric(), nullable=False)
    min_notional_eur: Mapped[Decimal] = mapped_column(FinancialNumeric(), nullable=False)
