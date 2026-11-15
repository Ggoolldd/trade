"""Typed read-only market-data contract; no trading or financial mutation methods."""

import math
from collections.abc import AsyncGenerator
from datetime import datetime
from enum import StrEnum
from typing import Protocol, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain_types import FinancialDecimal, UtcTimestamp, utc_now


class ProviderCode(StrEnum):
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    UNAVAILABLE = "UNAVAILABLE"
    AUTH_DENIED = "AUTH_DENIED"
    UNSUPPORTED = "UNSUPPORTED"
    INVALID_DATA = "INVALID_DATA"
    ADAPTER_ERROR = "ADAPTER_ERROR"


class ProviderError(Exception):
    def __init__(self, code: ProviderCode, *, retry_after: float | None = None) -> None:
        if not isinstance(code, ProviderCode):
            raise ValueError("typed provider error code required")
        if retry_after is not None and (
            code is not ProviderCode.RATE_LIMITED
            or isinstance(retry_after, bool)
            or not isinstance(retry_after, (int, float))
            or not math.isfinite(retry_after)
            or not 0 <= retry_after <= 86400
        ):
            raise ValueError("finite rate-limit retry delay required")
        self.code = code
        self.retry_after = retry_after
        # Raw remote bodies, URLs, credentials or adapter exception text are excluded.
        super().__init__(code.value)


class DataModel(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", revalidate_instances="always"
    )


class MarketQuote(DataModel):
    instrument_id: UUID
    provider: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,39}$")
    bid: FinancialDecimal = Field(gt=0)
    ask: FinancialDecimal = Field(gt=0)
    exchange_at: UtcTimestamp
    observed_at: UtcTimestamp
    usable_at: UtcTimestamp

    @model_validator(mode="after")
    def valid_quote(self) -> Self:
        if (
            self.bid > self.ask
            or not self.exchange_at <= self.observed_at <= self.usable_at <= utc_now()
        ):
            raise ValueError("crossed quote or unavailable/future timestamps")
        return self


class MarketBar(DataModel):
    instrument_id: UUID
    provider: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,39}$")
    interval_seconds: int = Field(gt=0, le=86400)
    opened_at: UtcTimestamp
    closed_at: UtcTimestamp
    observed_at: UtcTimestamp
    usable_at: UtcTimestamp
    open: FinancialDecimal = Field(gt=0)
    high: FinancialDecimal = Field(gt=0)
    low: FinancialDecimal = Field(gt=0)
    close: FinancialDecimal = Field(gt=0)
    volume: FinancialDecimal = Field(ge=0)

    @model_validator(mode="after")
    def completed_bar(self) -> Self:
        if not self.opened_at < self.closed_at <= self.observed_at <= self.usable_at <= utc_now():
            raise ValueError("only completed, observed and usable bars accepted")
        if (self.closed_at - self.opened_at).total_seconds() > self.interval_seconds:
            raise ValueError("bar exceeds declared interval")
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("inconsistent OHLC")
        return self


class BarPage(DataModel):
    bars: tuple[MarketBar, ...] = Field(max_length=5000)
    next_cursor: str | None = Field(default=None, max_length=128)
    retention_start: UtcTimestamp | None = None
    coverage_complete: bool = False


class HealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class ProviderHealth(DataModel):
    provider: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,39}$")
    status: HealthStatus
    checked_at: UtcTimestamp

    @model_validator(mode="after")
    def known_health(self) -> Self:
        if self.checked_at > utc_now():
            raise ValueError("health observation cannot be future")
        return self


class MarketDataProvider(Protocol):
    @property
    def provider_id(self) -> str: ...
    async def fetch_bars(
        self,
        instrument_id: UUID,
        start: datetime,
        end: datetime,
        interval_seconds: int,
        *,
        cursor: str | None = None,
        limit: int = 1000,
    ) -> BarPage: ...
    async def fetch_quote(self, instrument_id: UUID) -> MarketQuote: ...
    def stream_quotes(self, instrument_id: UUID) -> AsyncGenerator[MarketQuote, None]: ...
    async def provider_health(self) -> ProviderHealth: ...
