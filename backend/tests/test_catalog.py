from datetime import time
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.database import Database
from app.domain_types import InstrumentKind, InstrumentStatus
from app.models import Instrument, InstrumentAlias, QuoteCurrency, TradingHours, Venue

pytestmark = pytest.mark.integration


def seed_catalog(database: Database) -> tuple[Venue, QuoteCurrency, Instrument]:
    with database.transaction() as session:
        venue = Venue(code="TEST_" + uuid4().hex[:8].upper(), name="Fixture venue", timezone="UTC")
        currency = session.scalars(select(QuoteCurrency).where(QuoteCurrency.code == "EUR")).first()
        if currency is None:
            currency = QuoteCurrency(code="EUR", display_scale=2)
            session.add(currency)
        session.add(venue)
        session.flush()
        instrument = Instrument(
            venue_id=venue.id,
            quote_currency_id=currency.id,
            symbol="BTC/EUR",
            name="Synthetic BTC",
            kind=InstrumentKind.SPOT_CRYPTO,
        )
        session.add(instrument)
        session.flush()
    return venue, currency, instrument


def test_catalog_identity_and_unique_constraints(database: Database) -> None:
    venue, currency, instrument = seed_catalog(database)
    assert instrument.status is InstrumentStatus.SUSPENDED
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(Venue(code=venue.code, name="duplicate", timezone="UTC"))
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(QuoteCurrency(code="EUR", display_scale=2))
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                Instrument(
                    venue_id=venue.id,
                    quote_currency_id=currency.id,
                    symbol="BTC/EUR",
                    name="duplicate",
                    kind=InstrumentKind.SPOT_CRYPTO,
                )
            )
    with database.transaction() as session:
        session.add(
            InstrumentAlias(
                instrument_id=instrument.id, venue_id=venue.id, provider="FIXTURE", alias="XBTEUR"
            )
        )
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                InstrumentAlias(
                    instrument_id=instrument.id,
                    venue_id=venue.id,
                    provider="FIXTURE",
                    alias="XBTEUR",
                )
            )
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                InstrumentAlias(
                    instrument_id=instrument.id, venue_id=uuid4(), provider="FIXTURE", alias="wrong"
                )
            )


def test_db_checks_apply_even_without_orm_validation(database: Database) -> None:
    venue, _, instrument = seed_catalog(database)
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(
                text("UPDATE trading.instruments SET status='UNKNOWN' WHERE id=:id"),
                {"id": instrument.id},
            )
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(QuoteCurrency(code="eur", display_scale=2))
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                TradingHours(venue_id=venue.id, weekday=7, opens_at=time(9), closes_at=time(17))
            )
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                TradingHours(venue_id=venue.id, weekday=0, opens_at=time(17), closes_at=time(9))
            )
    with database.transaction() as session:
        session.add(
            TradingHours(
                venue_id=venue.id,
                weekday=0,
                opens_at=time(22),
                closes_at=time(6),
                closes_next_day=True,
            )
        )
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                TradingHours(
                    venue_id=venue.id,
                    weekday=0,
                    opens_at=time(22),
                    closes_at=time(6),
                    closes_next_day=True,
                )
            )
    with pytest.raises(ValueError, match="IANA"):
        Venue(code="BAD_TZ", name="fixture", timezone="Not/A_Zone")
