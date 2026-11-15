import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.database import Database
from app.models import Instrument, InstrumentAlias
from app.security_candidates import (
    CandidateError,
    candidate_id,
    import_candidates,
    parse_candidates,
)
from app.settings import Settings

CONFIG = Path(__file__).resolve().parents[1] / "config" / "security_candidates.json"


def test_default_candidate_identities_and_currency_separation() -> None:
    universe = parse_candidates(CONFIG.read_bytes())
    assert len([row for row in universe.candidates if row.kind == "STOCK"]) == 10
    etfs = [row for row in universe.candidates if row.kind == "UCITS_ETF"]
    assert len(etfs) == 2
    assert all(row.quote_currency == "EUR" and row.share_class_currency == "USD" for row in etfs)
    assert all(
        row.broker_availability == row.hr_retail_eligibility == "UNKNOWN"
        for row in universe.candidates
    )
    assert candidate_id("XETR", "DE0007164600") != candidate_id("XAMS", "DE0007164600")


@pytest.mark.parametrize(
    "field,value",
    [
        ("isin", "DE0007164601"),
        ("isin", "SAP"),
        ("ticker", "XETR:SAP"),
        ("mic", "SAP"),
        ("quote_currency", "USD"),
        ("kind", "DERIVATIVE"),
        ("issuer_ucits", True),
        ("broker_availability", "AVAILABLE"),
        ("hr_retail_eligibility", "APPROVED"),
        ("liquidity_status", "VERIFIED"),
        ("source_urls", ["http://example.invalid"]),
        ("source_urls", []),
    ],
)
def test_bad_or_overclaimed_metadata_rejected(field: str, value: object) -> None:
    body = json.loads(CONFIG.read_bytes())
    body["candidates"][0][field] = value
    with pytest.raises(CandidateError):
        parse_candidates(json.dumps(body).encode())


def test_duplicate_listing_collision_wrong_size_and_boolean_version() -> None:
    original = json.loads(CONFIG.read_bytes())
    for body in [
        dict(original, version=True),
        dict(original, candidates=original["candidates"][:2]),
    ]:
        with pytest.raises(CandidateError):
            parse_candidates(json.dumps(body).encode())
    body = copy.deepcopy(original)
    body["candidates"][1]["ticker"] = body["candidates"][0]["ticker"]
    with pytest.raises(CandidateError):
        parse_candidates(json.dumps(body).encode())
    body = copy.deepcopy(original)
    body["candidates"][1] = body["candidates"][0]
    with pytest.raises(CandidateError):
        parse_candidates(json.dumps(body).encode())
    with pytest.raises(CandidateError):
        parse_candidates(b" " * 200001)


@pytest.mark.integration
def test_atomic_repeatable_import_and_cross_exchange_ticker_collision(database: Database) -> None:
    raw = CONFIG.read_bytes()
    with pytest.raises(RuntimeError, match="rollback"):
        with database.transaction() as session:
            import_candidates(session, raw, Settings())
            raise RuntimeError("rollback")
    with database.transaction() as session:
        assert session.get(Instrument, candidate_id("XETR", "DE0007164600")) is None

    def run(_: int) -> object:
        with database.transaction() as session:
            return import_candidates(session, raw, Settings())

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert len({tuple(result) for result in pool.map(run, range(4))}) == 1
    with database.transaction() as session:
        import_candidates(session, raw, Settings())
        count = session.scalar(
            select(func.count())
            .select_from(InstrumentAlias)
            .where(InstrumentAlias.provider == "SECURITY_CANDIDATE")
        )
        assert count == 12
        assert session.get(Instrument, candidate_id("XETR", "DE0007164600")).isin == "DE0007164600"

    # Synthetic isolated test listing: this is not a claim of a real XAMS listing.
    body = json.loads(raw)
    collision = copy.deepcopy(body["candidates"][4])
    collision.update(
        mic="XAMS",
        ticker="SAP",
        name="Synthetic cross-venue collision fixture",
        source_urls=["https://example.invalid/fixture"],
    )
    body["candidates"].append(collision)
    with database.transaction() as session:
        import_candidates(session, json.dumps(body).encode(), Settings())
        first = session.get(Instrument, candidate_id("XETR", "DE0007164600"))
        second = session.get(Instrument, candidate_id("XAMS", "DE0005190003"))
        assert first.symbol == second.symbol == "SAP"
        assert first.id != second.id and first.venue_id != second.venue_id
        assert first.isin != second.isin
        assert first.status.value == second.status.value == "SUSPENDED"
