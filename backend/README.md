# Backend

Python 3.12, FastAPI, Uvicorn. No API keys or external services needed for the
current skeleton. `uv.lock` records exact resolved dependencies.

From this directory, with uv installed:

```powershell
uv sync --locked
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
```

`/health/live` checks process response. `/health/ready` is 503 outside an active
lifespan and 200 after startup, with `scope=process`. It does not yet claim DB,
Redis, feed or broker readiness. `/openapi.json` exposes the API schema.

Current implementation is PAPER only, has no order routes and no broker transport.
The loopback smoke test starts a real Uvicorn server on an ephemeral localhost port
and verifies graceful lifecycle shutdown. It uses no external broker or feed.

Sources reviewed for TAI-011:
[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/),
[TestClient](https://fastapi.tiangolo.com/tutorial/testing/).

## Workspace tooling on Windows

This workspace uses uv 0.13.8 and CPython 3.12.16 downloaded into ignored `tmp/`
directories. No global Python or shell PATH was changed. The filesystem rejected
uv's minor-version directory link, so an explicit interpreter path was used:

```powershell
$env:UV_CACHE_DIR = 'D:\TRADING\tmp\uv-cache'
$env:UV_PYTHON_INSTALL_DIR = 'D:\TRADING\tmp\python'
$env:UV_LINK_MODE = 'copy'
.\tmp\tools\uv\uv.exe sync --project backend --locked --python D:\TRADING\tmp\python\cpython-3.12.16-windows-x86_64-none\python.exe
```

Run that command from the repository root. On a normal filesystem, a standard uv
installation and the commands above are sufficient. Tooling source:
[uv Python management](https://docs.astral.sh/uv/guides/install-python/).
