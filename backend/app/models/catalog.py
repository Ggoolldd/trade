"""Catalog identity and schedule storage, without asserting feed entitlement."""

from datetime import time
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.database import Base
from app.domain_types import InstrumentKind, InstrumentStatus
from app.orm_types import EntityColumns


class Venue(EntityColumns, Base):
    __tablename__ = "venues"
    __table_args__ = (
        UniqueConstraint("code"),
        CheckConstraint("code ~ '^[A-Z0-9_]{2,20}$'", name="code_format"),
        CheckConstraint("length(name) > 0 AND length(timezone) > 0", name="required_text"),
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False)

    @validates("timezone")
    def valid_timezone(self, key: str, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("valid IANA venue timezone required") from None
        return value


class QuoteCurrency(EntityColumns, Base):
    __tablename__ = "quote_currencies"
    __table_args__ = (
        UniqueConstraint("code"),
        CheckConstraint("code ~ '^[A-Z][A-Z0-9]{2,9}$'", name="code_format"),
        CheckConstraint("display_scale BETWEEN 0 AND 18", name="scale_range"),
    )
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    display_scale: Mapped[int] = mapped_column(SmallInteger, default=2, nullable=False)


class Instrument(EntityColumns, Base):
    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint("venue_id", "symbol"),
        UniqueConstraint("id", "venue_id", name="uq_instruments_identity_venue"),
        CheckConstraint("length(symbol) > 0 AND length(name) > 0", name="required_text"),
        CheckConstraint("isin IS NULL OR isin ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'", name="isin_format"),
    )
    venue_id: Mapped[UUID] = mapped_column(ForeignKey("trading.venues.id"), nullable=False)
    quote_currency_id: Mapped[UUID] = mapped_column(
        ForeignKey("trading.quote_currencies.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(12))
    kind: Mapped[InstrumentKind] = mapped_column(
        Enum(
            InstrumentKind,
            name="instrument_kind",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    status: Mapped[InstrumentStatus] = mapped_column(
        Enum(
            InstrumentStatus,
            name="instrument_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=InstrumentStatus.SUSPENDED,
        nullable=False,
    )


class InstrumentAlias(EntityColumns, Base):
    __tablename__ = "instrument_aliases"
    __table_args__ = (
        UniqueConstraint("venue_id", "provider", "alias"),
        ForeignKeyConstraint(
            ["instrument_id", "venue_id"],
            ["trading.instruments.id", "trading.instruments.venue_id"],
            name="fk_instrument_alias_identity_venue",
        ),
        CheckConstraint("length(provider) > 0 AND length(alias) > 0", name="required_text"),
    )
    instrument_id: Mapped[UUID] = mapped_column(nullable=False)
    venue_id: Mapped[UUID] = mapped_column(nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    alias: Mapped[str] = mapped_column(String(80), nullable=False)


class TradingHours(EntityColumns, Base):
    __tablename__ = "trading_hours"
    __table_args__ = (
        UniqueConstraint("venue_id", "weekday", "opens_at"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint(
            "(NOT closes_next_day AND closes_at > opens_at) OR "
            "(closes_next_day AND closes_at <= opens_at)",
            name="session_interval",
        ),
    )
    venue_id: Mapped[UUID] = mapped_column(ForeignKey("trading.venues.id"), nullable=False)
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    opens_at: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    closes_at: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    closes_next_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
