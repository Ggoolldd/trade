import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from app.domain_types import EntityId, FinancialDecimal, OrderSide, UtcTimestamp


class Example(BaseModel):
    id: EntityId
    amount: FinancialDecimal
    created_at: UtcTimestamp
    side: OrderSide = OrderSide.BUY


def test_precise_scalar_roundtrip() -> None:
    value = Example(
        amount="12345678901234567890.123456789012345678", created_at="2026-11-15T13:00:00+01:00"
    )
    assert isinstance(value.id, UUID)
    assert value.created_at == datetime(2026, 11, 15, 12, tzinfo=UTC)
    raw = json.loads(value.model_dump_json())
    assert raw["amount"] == "12345678901234567890.123456789012345678"
    assert raw["created_at"] == "2026-11-15T12:00:00Z"
    assert raw["side"] == "BUY"
    assert Example.model_validate_json(value.model_dump_json()) == value


@pytest.mark.parametrize(
    "amount", [0.1, 1, True, "NaN", "Infinity", "-Infinity", "1e-19", "1e20", "invalid"]
)
def test_bad_financial_scalars_rejected(amount: object) -> None:
    with pytest.raises(ValidationError):
        Example.model_validate({"amount": amount, "created_at": "2026-11-15T00:00:00Z"})


def test_negative_ledger_amount_allowed_and_ids_unique() -> None:
    a = Example(amount=Decimal("-0.00000001"), created_at=datetime.now(UTC))
    b = Example(amount="0.00", created_at=datetime.now(UTC))
    assert a.id != b.id
    assert json.loads(a.model_dump_json())["amount"] == "-0.00000001"


def test_naive_timestamp_and_unknown_enum_rejected() -> None:
    with pytest.raises(ValidationError):
        Example(amount="1", created_at=datetime(2026, 11, 15))
    with pytest.raises(ValidationError):
        Example(amount="1", created_at=datetime.now(UTC), side="SHORT")
