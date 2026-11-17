"""Bounded synthetic history adapter; real-source entitlement is unresolved."""

import csv
import hashlib
import io
import json
from collections.abc import AsyncGenerator
from datetime import datetime
from decimal import Decimal, DecimalException
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.audit import append_event
from app.domain_types import UtcTimestamp, require_utc, utc_now
from app.market_data import (
    BarPage,
    DataModel,
    HealthStatus,
    MarketBar,
    MarketQuote,
    ProviderCode,
    ProviderError,
    ProviderHealth,
)
from app.models.audit import AuditType
from app.models.history import HistoryImport
from app.settings import Settings

COLUMNS = ["opened_at", "closed_at", "open", "high", "low", "close", "volume"]
MAX_BYTES = 1_000_000


class HistoryManifest(DataModel):
    provider: Literal["SYNTHETIC_HISTORY"]
    purpose: Literal["SYNTHETIC_TEST_ONLY"]
    instrument_id: UUID
    currency: Literal["EUR"]
    adjustment: Literal["UNADJUSTED"]
    interval_seconds: int = Field(gt=0, le=86400)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_at: UtcTimestamp
    coverage_start: UtcTimestamp
    coverage_end: UtcTimestamp
    license_note: Literal["Project-authored artificial test data; no market observations"]

    @model_validator(mode="after")
    def known_times(self) -> "HistoryManifest":
        if not self.coverage_start < self.coverage_end <= self.observed_at <= utc_now():
            raise ValueError("completed historical coverage required")
        return self


class HistoricalCsvProvider:
    """No remote URLs or accepted production-license assertions in this adapter."""

    provider_id = "SYNTHETIC_HISTORY"

    def __init__(
        self, raw: bytes, manifest: HistoryManifest, settings: Settings, *, confirm_fixture: bool
    ) -> None:
        self.manifest = HistoryManifest.model_validate(manifest)
        if confirm_fixture is not True or settings.feed_provider.value != "FIXTURE":
            raise ProviderError(ProviderCode.AUTH_DENIED)
        if (
            not raw
            or len(raw) > MAX_BYTES
            or hashlib.sha256(raw).hexdigest() != manifest.source_sha256
        ):
            raise ProviderError(ProviderCode.INVALID_DATA)
        try:
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True)
            if reader.fieldnames != COLUMNS:
                raise ValueError("exact CSV columns required")
            bars: list[MarketBar] = []
            for row in reader:
                if len(bars) >= 5000 or None in row or any(value is None for value in row.values()):
                    raise ValueError("bounded exact row required")
                bar = MarketBar(
                    instrument_id=manifest.instrument_id,
                    provider=self.provider_id,
                    interval_seconds=manifest.interval_seconds,
                    opened_at=datetime.fromisoformat(row["opened_at"]),
                    closed_at=datetime.fromisoformat(row["closed_at"]),
                    observed_at=manifest.observed_at,
                    # Ingest time is availability; historical publication is not invented.
                    usable_at=manifest.observed_at,
                    **{name: Decimal(row[name]) for name in COLUMNS[2:]},
                )
                if (
                    bar.opened_at < manifest.coverage_start
                    or bar.closed_at > manifest.coverage_end
                    or (bars and bar.opened_at < bars[-1].closed_at)
                ):
                    raise ValueError("coverage or ordering mismatch")
                bars.append(bar)
            if not bars:
                raise ValueError("nonempty history required")
        except (ValueError, TypeError, csv.Error, UnicodeError, DecimalException):
            raise ProviderError(ProviderCode.INVALID_DATA) from None
        self.bars = tuple(bars)

    async def fetch_bars(
        self,
        instrument_id: UUID,
        start: datetime,
        end: datetime,
        interval_seconds: int,
        *,
        cursor: str | None = None,
        limit: int = 1000,
    ) -> BarPage:
        start, end = require_utc(start), require_utc(end)
        if (
            instrument_id != self.manifest.instrument_id
            or interval_seconds != self.manifest.interval_seconds
        ):
            raise ProviderError(ProviderCode.UNSUPPORTED)
        if (
            cursor is not None
            or not start < end <= utc_now()
            or type(limit) is not int
            or not 1 <= limit <= 5000
        ):
            raise ProviderError(ProviderCode.INVALID_DATA)
        bars = tuple(bar for bar in self.bars if start <= bar.opened_at and bar.closed_at <= end)
        return BarPage(
            bars=bars[:limit],
            source_sha256=self.manifest.source_sha256,
            # Sparse synthetic files cannot prove complete venue/session coverage.
            coverage_complete=False,
        )

    async def fetch_quote(self, instrument_id: UUID) -> MarketQuote:
        raise ProviderError(ProviderCode.UNSUPPORTED)

    async def stream_quotes(self, instrument_id: UUID) -> AsyncGenerator[MarketQuote, None]:
        raise ProviderError(ProviderCode.UNSUPPORTED)
        yield  # pragma: no cover - typed async-generator contract

    async def provider_health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.provider_id, status=HealthStatus.HEALTHY, checked_at=utc_now()
        )


def record_import(session: Session, provider: HistoricalCsvProvider) -> UUID:
    """Record validated fixture provenance atomically; canonical bars belong to TAI-033."""
    manifest = HistoryManifest.model_validate(provider.manifest)
    canonical = manifest.model_dump_json()
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    identity = uuid5(NAMESPACE_URL, "trading-ai:history-import:" + digest)
    session.execute(text("SELECT pg_advisory_xact_lock(320032)"))
    existing = session.scalar(select(HistoryImport).where(HistoryImport.id == identity))
    if existing is None:
        session.add(
            HistoryImport(
                id=identity,
                manifest_sha256=digest,
                source_sha256=manifest.source_sha256,
                manifest=json.loads(canonical),
                row_count=len(provider.bars),
            )
        )
        session.flush()
        append_event(
            session, event_type=AuditType.SYSTEM, correlation_id=identity, entity_id=identity
        )
    return identity
