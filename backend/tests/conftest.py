import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Tests are independent of owner environment and local .env files.
    for name in os.environ:
        if name.upper().startswith("TAI_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
