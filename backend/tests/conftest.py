import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr

from app.database import Database
from app.settings import Settings


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Tests are independent of owner environment and local .env files.
    for name in os.environ:
        if name.upper().startswith("TAI_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def database() -> Iterator[Database]:
    url = os.environ.get("TEST_DATABASE_URL")
    if url is None:
        pytest.skip("Run scripts/run-postgres-checks.py for real PostgreSQL evidence")
    database = Database(Settings(database_url=SecretStr(url)))
    try:
        # Every integration test gets migrations regardless of collection order.
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        with database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield database
    finally:
        database.close()
