import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.database import Database
from app.history_csv import HistoricalCsvProvider, HistoryManifest, record_import
from app.market_data import MarketDataProvider, ProviderError
from app.models.audit import AuditEvent
from app.models.history import HistoryImport
from app.settings import FeedProvider, Settings

START = datetime(2026, 1, 2, 9, tzinfo=UTC)
END = datetime(2026, 1, 2, 10, tzinfo=UTC)
OBSERVED = datetime(2026, 1, 3, tzinfo=UTC)
INSTRUMENT = UUID("00000000-0000-4000-8000-000000000032")
RAW = (
    b"opened_at,closed_at,open,high,low,close,volume\n"
    b"2026-01-02T09:00:00Z,2026-01-02T10:00:00Z,10.01,11,10,10.5,100\n"
)


def manifest(raw: bytes = RAW) -> HistoryManifest:
    return HistoryManifest(
        provider="SYNTHETIC_HISTORY",
        purpose="SYNTHETIC_TEST_ONLY",
        instrument_id=INSTRUMENT,
        currency="EUR",
        adjustment="UNADJUSTED",
        interval_seconds=3600,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        observed_at=OBSERVED,
        coverage_start=START,
        coverage_end=END,
        license_note="Project-authored artificial test data; no market observations",
    )


def source(raw: bytes = RAW) -> HistoricalCsvProvider:
    return HistoricalCsvProvider(raw, manifest(raw), Settings(), confirm_fixture=True)


def test_exact_decimal_availability_contract_and_sparse_coverage() -> None:
    provider: MarketDataProvider = source()
    page = asyncio.run(provider.fetch_bars(INSTRUMENT, START, END, 3600))
    assert len(page.bars) == 1 and page.bars[0].open == Decimal("10.01")
    assert page.bars[0].usable_at == OBSERVED and not page.coverage_complete
    assert page.source_sha256 == hashlib.sha256(RAW).hexdigest()
    with pytest.raises(ProviderError):
        asyncio.run(provider.fetch_quote(INSTRUMENT))


def test_explicit_fixture_gate_and_no_license_assertion_bypass() -> None:
    with pytest.raises(ProviderError):
        HistoricalCsvProvider(RAW, manifest(), Settings(), confirm_fixture=False)
    with pytest.raises(ValidationError):
        HistoryManifest.model_validate(manifest().model_dump() | {"purpose": "LICENSED"})
    with pytest.raises(ProviderError):
        HistoricalCsvProvider(RAW + b"x", manifest(), Settings(), confirm_fixture=True)
    with pytest.raises(ProviderError):
        HistoricalCsvProvider(
            RAW,
            manifest(),
            Settings(feed_provider=FeedProvider.KRAKEN_PUBLIC),
            confirm_fixture=True,
        )


def test_invalid_decimal_has_sanitized_error() -> None:
    with pytest.raises(ProviderError, match="^INVALID_DATA$"):
        source(RAW.replace(b"10.01", b"not-a-number"))


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"x" * 1_000_001,
        RAW.replace(b"10.01", b"NaN"),
        RAW.replace(b"10.01", b"12"),
        RAW.replace(b"10.01", b"-1"),
        RAW.replace(b"09:00:00Z", b"09:00:00"),
        RAW + RAW.splitlines(keepends=True)[1],
        RAW.replace(b"volume\n", b"volume,extra\n"),
        RAW.replace(b",100\n", b",100,extra\n"),
        RAW.replace(b"10:00:00Z", b"11:00:00Z"),
        b"\xff",
    ],
)
def test_malformed_unsafe_or_out_of_coverage_rows_rejected(raw: bytes) -> None:
    with pytest.raises(ProviderError):
        source(raw)


@pytest.mark.integration
def test_provenance_rollback_concurrent_replay_and_json(database: Database) -> None:
    provider = source()
    with pytest.raises(RuntimeError):
        with database.transaction() as session:
            record_import(session, provider)
            raise RuntimeError("rollback")
    with database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(HistoryImport)) == 0

    def run(_: int) -> UUID:
        with database.transaction() as session:
            return record_import(session, provider)

    with ThreadPoolExecutor(max_workers=4) as pool:
        identities = set(pool.map(run, range(4)))
    assert len(identities) == 1
    with database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(HistoryImport)) == 1
        record = session.get(HistoryImport, next(iter(identities)))
        assert record is not None and record.row_count == 1
        assert record.manifest["purpose"] == "SYNTHETIC_TEST_ONLY"
        assert record.source_sha256 == hashlib.sha256(RAW).hexdigest()
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.correlation_id == record.id)
            )
            == 1
        )
