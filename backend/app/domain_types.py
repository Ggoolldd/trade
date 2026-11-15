"""Canonical scalar contracts shared by persistence and API boundaries."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import AfterValidator, AwareDatetime, BeforeValidator, Field, PlainSerializer


class TradingMode(StrEnum):
    PAPER = "PAPER"
    SHADOW = "SHADOW"
    LIVE = "LIVE"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class InstrumentKind(StrEnum):
    STOCK = "STOCK"
    UCITS_ETF = "UCITS_ETF"
    SPOT_CRYPTO = "SPOT_CRYPTO"


class InstrumentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELISTED = "DELISTED"


def utc_now() -> datetime:
    return datetime.now(UTC)


def require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(UTC)


def financial_decimal(value: object) -> Decimal:
    if not isinstance(value, (str, Decimal)) or isinstance(value, str) and len(value) > 128:
        raise ValueError("financial values require a decimal string or Decimal")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid decimal string") from None
    if not number.is_finite():
        raise ValueError("finite decimal required")
    digits = number.as_tuple()
    exponent = int(digits.exponent)
    if exponent < -18 or len(digits.digits) + exponent > 20:
        raise ValueError("value exceeds NUMERIC(38,18) bounds")
    return number


FinancialDecimal = Annotated[
    Decimal,
    BeforeValidator(financial_decimal),
    PlainSerializer(lambda value: format(value, "f"), return_type=str),
]
UtcTimestamp = Annotated[AwareDatetime, AfterValidator(require_utc)]
EntityId = Annotated[UUID, Field(default_factory=uuid4)]
