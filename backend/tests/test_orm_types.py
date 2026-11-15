from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.database import Database
from app.orm_types import EntityColumns, FinancialNumeric

pytestmark = pytest.mark.integration


class ProbeBase(DeclarativeBase):
    pass


class Probe(EntityColumns, ProbeBase):
    __tablename__ = "entity_probe"
    amount: Mapped[Decimal] = mapped_column(FinancialNumeric(), nullable=False)


def test_uuid_utc_and_numeric_real_postgres(database: Database) -> None:
    ProbeBase.metadata.create_all(database.engine)
    try:
        original = Decimal("12345678901234567890.123456789012345678")
        with database.transaction() as session:
            row = Probe(amount=original)
            session.add(row)
            session.flush()
            identity = row.id
            assert isinstance(identity, UUID)
            assert row.created_at.tzinfo is UTC
        with database.transaction() as session:
            stored = session.scalars(select(Probe)).one()
            assert stored.id == identity
            assert stored.amount == original
            assert stored.created_at.utcoffset().total_seconds() == 0
        for invalid in [0.1, Decimal("NaN"), Decimal("1e-19"), Decimal("1e20")]:
            with pytest.raises(StatementError):
                with database.transaction() as session:
                    session.add(Probe(amount=invalid))
        with pytest.raises(StatementError):
            with database.transaction() as session:
                session.add(Probe(amount=Decimal("1"), created_at=datetime(2026, 11, 15)))
        with database.transaction() as session:
            assert len(list(session.scalars(select(Probe)))) == 1
    finally:
        ProbeBase.metadata.drop_all(database.engine)
