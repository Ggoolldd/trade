from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Column, Integer, MetaData, Table, inspect, select

from app.database import Database

pytestmark = pytest.mark.integration


def migration_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def test_baseline_up_down_up_on_empty_postgres(database: Database) -> None:
    config = migration_config()
    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert "trading" not in inspect(connection).get_schema_names()
        command.upgrade(config, "head")
        assert "trading" in inspect(connection).get_schema_names()
        assert set(inspect(connection).get_table_names(schema="trading")) == {
            "venues",
            "quote_currencies",
            "instruments",
            "instrument_rules",
            "history_imports",
            "instrument_aliases",
            "trading_hours",
            "paper_accounts",
            "trading_profiles",
            "account_permissions",
            "audit_events",
            "users",
            "sessions",
            "login_throttles",
            "jobs",
            "dead_letters",
            "schedules",
            "scheduled_runs",
        }
        command.check(config)
        command.downgrade(config, "base")
        assert "trading" not in inspect(connection).get_schema_names()
        command.upgrade(config, "head")
        assert "trading" in inspect(connection).get_schema_names()


def test_session_commit_and_rollback(database: Database) -> None:
    # Test-owned transient table only, not application schema or owner data.
    metadata = MetaData()
    probe = Table("session_probe", metadata, Column("id", Integer, primary_key=True))
    metadata.create_all(database.engine)
    try:
        with database.transaction() as session:
            session.execute(probe.insert().values(id=1))
        with pytest.raises(RuntimeError, match="rollback probe"):
            with database.transaction() as session:
                session.execute(probe.insert().values(id=2))
                raise RuntimeError("rollback probe")
        with database.transaction() as session:
            assert list(session.scalars(select(probe.c.id))) == [1]
    finally:
        metadata.drop_all(database.engine)
