import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.crypto_catalog import CatalogError, catalog_id, import_pairs, parse_pairs, resolve_pair
from app.database import Database
from app.domain_types import utc_now
from app.models import Instrument, InstrumentAlias, InstrumentRules
from app.settings import Settings

FIXTURE = Path(__file__).parent / "fixtures" / "kraken_asset_pairs.json"


def test_actual_captured_pair_mapping_and_exact_steps() -> None:
    raw = FIXTURE.read_bytes()
    provenance = json.loads(FIXTURE.with_suffix(".provenance.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == provenance["sha256"]
    pairs = parse_pairs(raw)
    assert set(pairs) == {"BTC/EUR", "ETH/EUR"}
    assert pairs["BTC/EUR"].altname == "XBTEUR"
    assert pairs["BTC/EUR"].tick_size == Decimal("0.1")
    assert pairs["ETH/EUR"].tick_size == Decimal("0.01")
    assert Decimal(1).scaleb(-pairs["BTC/EUR"].lot_decimals) == Decimal("0.00000001")
    assert resolve_pair(raw, "BTC/EUR") == pairs["BTC/EUR"]
    with pytest.raises(CatalogError):
        resolve_pair(raw, "DOGE/EUR")
    with pytest.raises(CatalogError):
        resolve_pair(raw, "XBT/EUR")  # Venue alias is not a canonical symbol.


@pytest.mark.parametrize(
    "field,value",
    [
        ("quote", "ZUSD"),
        ("base", "XETH"),
        ("altname", "XBTUSD"),
        ("wsname", "XBT/USD"),
        ("lot", "contract"),
        ("lot_multiplier", 2),
        ("lot_multiplier", True),
        ("lot_decimals", -1),
        ("lot_decimals", 19),
        ("lot_decimals", 8.0),
        ("pair_decimals", False),
        ("tick_size", 0.1),
        ("tick_size", "NaN"),
        ("tick_size", "0"),
        ("tick_size", "0.01"),
        ("ordermin", "-1"),
        ("costmin", "0"),
        ("status", "offline"),
    ],
)
def test_invalid_or_nonspot_pair_metadata_rejected(field: str, value: object) -> None:
    body = json.loads(FIXTURE.read_bytes())
    body["result"]["XXBTZEUR"][field] = value
    with pytest.raises(CatalogError):
        parse_pairs(json.dumps(body).encode())


def test_missing_error_unknown_and_oversized_response_rejected() -> None:
    raw = FIXTURE.read_bytes()
    for body in [
        {"error": ["EQuery:Unknown asset pair"], "result": {}},
        {"error": [], "result": {}},
        {"error": []},
    ]:
        with pytest.raises(CatalogError):
            parse_pairs(json.dumps(body).encode())
    body = json.loads(raw)
    body["result"]["XXBTZEUR.d"] = body["result"]["XXBTZEUR"]
    with pytest.raises(CatalogError):
        parse_pairs(json.dumps(body).encode())
    with pytest.raises(CatalogError):
        parse_pairs(b" " * 200001)
    with pytest.raises(CatalogError):
        parse_pairs(b"not JSON")


@pytest.mark.integration
def test_persisted_rules_rollback_replay_and_versioning(database: Database) -> None:
    raw = FIXTURE.read_bytes()
    timestamp = utc_now() - timedelta(minutes=1)
    with pytest.raises(RuntimeError, match="rollback"):
        with database.transaction() as session:
            import_pairs(session, raw, timestamp, Settings())
            raise RuntimeError("rollback")
    with database.transaction() as session:
        assert session.get(Instrument, catalog_id("BTC/EUR")) is None

    def run(_: int) -> object:
        with database.transaction() as session:
            return import_pairs(session, raw, timestamp, Settings())

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert len({tuple(result) for result in pool.map(run, range(4))}) == 1
    with database.transaction() as session:
        import_pairs(session, raw, timestamp + timedelta(seconds=1), Settings())
        assert session.scalar(select(func.count()).select_from(InstrumentRules)) == 2
        assert (
            session.scalar(
                select(func.count())
                .select_from(InstrumentAlias)
                .where(InstrumentAlias.provider == "KRAKEN_REST")
            )
            == 4
        )
        rows = session.scalars(select(InstrumentRules)).all()
        assert all(
            row.observed_at == timestamp and row.quantity_step == Decimal("0.00000001")
            for row in rows
        )
        assert all(
            session.get(Instrument, row.instrument_id).status.value == "SUSPENDED" for row in rows
        )
    newer = json.loads(raw)
    newer["result"]["XXBTZEUR"]["tick_size"] = "0.2"
    with database.transaction() as session:
        import_pairs(
            session, json.dumps(newer).encode(), timestamp + timedelta(seconds=2), Settings()
        )
        assert session.scalar(select(func.count()).select_from(InstrumentRules)) == 4
        previous = session.scalar(
            select(InstrumentRules).where(
                InstrumentRules.source_sha256 == hashlib.sha256(raw).hexdigest(),
                InstrumentRules.instrument_id == catalog_id("BTC/EUR"),
            )
        )
        assert previous.tick_size == Decimal("0.1")
    with pytest.raises(CatalogError):
        with database.transaction() as session:
            import_pairs(session, raw, utc_now() + timedelta(days=1), Settings())
    with pytest.raises(ValueError, match="timezone-aware"):
        with database.transaction() as session:
            import_pairs(session, raw, timestamp.replace(tzinfo=None), Settings())
