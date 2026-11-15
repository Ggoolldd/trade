"""Explicit snapshot update; inspect its Git diff before accepting a contract change."""

import json
from pathlib import Path

from app.main import create_app

target = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures" / "openapi.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(
    json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print("Updated backend/tests/fixtures/openapi.json; review the schema diff explicitly")
