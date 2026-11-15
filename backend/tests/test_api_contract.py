import copy
import json
from pathlib import Path

import pytest

from app.main import create_app


def assert_contract(actual: dict[str, object], expected: dict[str, object]) -> None:
    assert actual == expected, "OpenAPI contract changed; review before updating snapshot"


def test_openapi_matches_reviewed_snapshot() -> None:
    snapshot = json.loads(
        (Path(__file__).parent / "fixtures" / "openapi.json").read_text(encoding="utf-8")
    )
    assert_contract(create_app().openapi(), snapshot)


def test_contract_gate_rejects_removed_endpoint() -> None:
    original = create_app().openapi()
    changed = copy.deepcopy(original)
    del changed["paths"]["/api/v1/jobs"]
    with pytest.raises(AssertionError, match="contract changed"):
        assert_contract(changed, original)
