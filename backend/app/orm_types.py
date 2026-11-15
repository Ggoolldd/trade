"""Reusable PostgreSQL scalars and UUID/UTC entity columns."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Numeric, Uuid, func
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.domain_types import financial_decimal, require_utc, utc_now


class FinancialNumeric(TypeDecorator[Decimal]):
    impl = Numeric(38, 18, asdecimal=True)
    cache_ok = True

    def process_bind_param(self, value: object, dialect: Dialect) -> Decimal | None:
        return None if value is None else financial_decimal(value)


class UtcDateTime(TypeDecorator[datetime]):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else require_utc(value)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else require_utc(value)


class EntityColumns:
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), default=utc_now, server_default=func.now(), nullable=False
    )
