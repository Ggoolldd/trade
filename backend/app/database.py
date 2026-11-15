"""PostgreSQL ORM/session ownership with explicit transaction boundaries."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.settings import Settings

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(schema="trading", naming_convention=NAMING_CONVENTION)


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine: Engine = create_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            hide_parameters=True,
            echo=False,
            connect_args={"connect_timeout": max(1, int(settings.service_timeout_seconds))},
        )
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False, autoflush=False)

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Commit once on success; rollback on every exception; always close."""
        with self.sessions.begin() as session:
            yield session

    def close(self) -> None:
        self.engine.dispose()
