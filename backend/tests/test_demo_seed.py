from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.database import Database
from app.demo_seed import SeedConflict, identity, seed_demo
from app.models import AuditEvent, Instrument, InstrumentAlias, PaperAccount, TradingHours, Venue
from app.settings import FeedProvider, Settings

pytestmark = pytest.mark.integration


def test_seed_atomic_rollback_race_and_repeatability(database: Database) -> None:
    with database.transaction() as session:
        previous = [
            session.get(model, identity(name)) is not None
            for model, name in [(Venue, "venue"), (PaperAccount, "account"), (AuditEvent, "audit")]
        ]
    # On the fresh full-suite DB, first attempt creates rows/audit then rolls back.
    with pytest.raises(RuntimeError, match="rollback"):
        with database.transaction() as session:
            seed_demo(session, Settings())
            raise RuntimeError("rollback")
    with database.transaction() as session:
        assert [
            session.get(model, identity(name)) is not None
            for model, name in [(Venue, "venue"), (PaperAccount, "account"), (AuditEvent, "audit")]
        ] == previous

    def run(_: int) -> object:
        with database.transaction() as session:
            return seed_demo(session, Settings())

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert set(pool.map(run, range(4))) == {identity("account")}
    with database.transaction() as session:
        tables = [Venue, Instrument, InstrumentAlias, TradingHours, PaperAccount, AuditEvent]
        before = [session.scalar(select(func.count()).select_from(model)) for model in tables]
        assert seed_demo(session, Settings()) == identity("account")
        assert seed_demo(session, Settings()) == identity("account")
        after = [session.scalar(select(func.count()).select_from(model)) for model in tables]
        assert before == after
        account = session.get(PaperAccount, identity("account"))
        assert account is not None
        assert account.initial_cash_eur == Decimal("10000.00")
        assert account.enabled is False
        instruments = session.scalars(
            select(Instrument).where(Instrument.venue_id == identity("venue"))
        ).all()
        assert {item.symbol for item in instruments} == {"BTC/EUR", "ETH/EUR"}
        assert all(item.status.value == "SUSPENDED" for item in instruments)
        sessions = session.scalars(
            select(TradingHours).where(TradingHours.venue_id == identity("venue"))
        ).all()
        assert len(sessions) == 7
        assert {item.weekday for item in sessions} == set(range(7))
        assert all(item.closes_next_day and item.opens_at == item.closes_at for item in sessions)


def test_seed_refuses_owner_edits_and_nonfixture_feed(database: Database) -> None:
    with database.transaction() as session:
        seed_demo(session, Settings())
    with pytest.raises(SeedConflict):
        with database.transaction() as session:
            seed_demo(session, Settings(feed_provider=FeedProvider.KRAKEN_PUBLIC))
    # Failure must not overwrite operator changes, even before transaction rollback.
    with pytest.raises(RuntimeError, match="rollback"):
        with database.transaction() as session:
            venue = session.get(Venue, identity("venue"))
            assert venue is not None
            venue.name = "Owner edited fixture"
            session.flush()
            with pytest.raises(SeedConflict):
                seed_demo(session, Settings())
            assert venue.name == "Owner edited fixture"
            raise RuntimeError("rollback")


def test_initial_cash_is_exact_and_cannot_be_negative(database: Database) -> None:
    with database.transaction() as session:
        seed_demo(session, Settings())
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(
                text("UPDATE trading.paper_accounts SET initial_cash_eur=-1 WHERE id=:id"),
                {"id": identity("account")},
            )
    with database.transaction() as session:
        assert session.get(PaperAccount, identity("account")).initial_cash_eur == Decimal(
            "10000.00"
        )
