"""Explicit local fixture seed: atomic, repeatable and never enables trading."""

import argparse
from datetime import UTC, datetime, time
from decimal import Decimal
from uuid import UUID, uuid5

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.audit import append_event
from app.database import Base, Database
from app.domain_types import InstrumentKind, InstrumentStatus, TradingMode
from app.models import Instrument, InstrumentAlias, PaperAccount, QuoteCurrency, TradingHours, Venue
from app.models.accounts import DevelopmentEnvironment
from app.models.audit import AuditEvent, AuditType
from app.settings import FeedProvider, Settings, load_settings

NAMESPACE = UUID("3971fc60-7271-4d26-b7e5-6502d7ad82c2")
FIXTURE_TIME = datetime(2026, 11, 15, tzinfo=UTC)


class SeedConflict(ValueError):
    """Fixture identity/content conflicts; existing data must not be overwritten."""


def identity(name: str) -> UUID:
    return uuid5(NAMESPACE, "demo-v1/" + name)


def ensure[Model: Base](
    session: Session, model: type[Model], fixture_key: str, **values: object
) -> Model:
    key = identity(fixture_key)
    existing = session.get(model, key)
    if existing is not None:
        if any(getattr(existing, field) != value for field, value in values.items()):
            raise SeedConflict("Demo fixture differs; no data was overwritten")
        return existing
    row = model(id=key, created_at=FIXTURE_TIME, **values)
    session.add(row)
    session.flush()
    return row


def seed_demo(session: Session, settings: Settings) -> UUID:
    """Caller owns transaction. Fixed advisory lock also serializes concurrent seeds."""
    if (
        settings.trading_mode is not TradingMode.PAPER
        or settings.feed_provider is not FeedProvider.FIXTURE
    ):
        raise SeedConflict("Demo seed requires PAPER and FIXTURE settings")
    session.execute(text("SELECT pg_advisory_xact_lock(250025)"))
    currency = session.scalar(select(QuoteCurrency).where(QuoteCurrency.code == "EUR"))
    if currency is None:
        currency = ensure(session, QuoteCurrency, "EUR", code="EUR", display_scale=2)
    elif currency.display_scale != 2:
        raise SeedConflict("Existing EUR definition differs")
    venue = ensure(
        session,
        Venue,
        "venue",
        code="DEMO_FIXTURE",
        name="Synthetic 24/7 demo venue",
        timezone="UTC",
    )
    for symbol in ["BTC/EUR", "ETH/EUR"]:
        instrument = ensure(
            session,
            Instrument,
            symbol,
            venue_id=venue.id,
            quote_currency_id=currency.id,
            symbol=symbol,
            name="Synthetic " + symbol,
            kind=InstrumentKind.SPOT_CRYPTO,
            status=InstrumentStatus.SUSPENDED,
            isin=None,
        )
        ensure(
            session,
            InstrumentAlias,
            symbol + "/alias",
            instrument_id=instrument.id,
            venue_id=venue.id,
            provider="FIXTURE",
            alias=symbol,
        )
    # This synthetic UTC 24/7 weekly calendar is not an exchange holiday calendar.
    for weekday in range(7):
        ensure(
            session,
            TradingHours,
            f"calendar/{weekday}",
            venue_id=venue.id,
            weekday=weekday,
            opens_at=time(0),
            closes_at=time(0),
            closes_next_day=True,
        )
    account = ensure(
        session,
        PaperAccount,
        "account",
        name="Demo fixture v1",
        account_mode=TradingMode.PAPER,
        environment=DevelopmentEnvironment.LOCAL,
        enabled=False,
        initial_cash_eur=Decimal("10000.00"),
    )
    event = session.get(AuditEvent, identity("audit"))
    if event is None:
        append_event(
            session,
            event_type=AuditType.ACCOUNT_CHANGED,
            correlation_id=identity("seed"),
            entity_id=account.id,
            event_id=identity("audit"),
        )
    elif (
        event.entity_id != account.id
        or event.correlation_id != identity("seed")
        or event.event_type is not AuditType.ACCOUNT_CHANGED
    ):
        raise SeedConflict("Demo audit identity conflict")
    return account.id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-fixture", action="store_true", required=True)
    parser.parse_args()
    settings = load_settings()
    database = Database(settings)
    try:
        with database.transaction() as session:
            account_id = seed_demo(session, settings)
        print(
            f"Demo fixture ready: {account_id}; disabled PAPER; "
            "scenario input 10000 EUR, not ledger cash"
        )
    finally:
        database.close()


if __name__ == "__main__":
    main()
