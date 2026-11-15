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

## Configuration (TAI-012)

The app factory validates immutable settings before serving requests. Real environment
variables override optional `.env` in the working directory; defaults follow. The
service performs no network call just by selecting a feed or setting a URL.

| Variable | Default / contract |
| --- | --- |
| TAI_TRADING_MODE | PAPER; LIVE and SHADOW rejected while not implemented |
| TAI_DATABASE_URL | PostgreSQL psycopg URL with user, host and database; see .env.example; no query/fragment |
| TAI_REDIS_URL | redis/rediss URL with host and explicit database index 0–15; no query/fragment |
| TAI_FEED_PROVIDER | FIXTURE (offline); KRAKEN_PUBLIC allowed as configuration only |
| TAI_FEED_MAX_AGE_SECONDS | 60; integer 1–3600 |
| TAI_SERVICE_TIMEOUT_SECONDS | 5; finite number >0 and <=30 |

Copy `.env.example` to ignored `.env` only for local values. No real broker keys
are needed or accepted. Unknown TAI_ variables, invalid URLs and invalid mode fail
startup. Values are not logged; service URLs use SecretStr and are masked in repr
and JSON. Do not log raw ValidationError.errors(), since caller APIs may request
raw input; `load_settings()` exposes only sanitized ConfigurationError.

PostgreSQL/Redis configuration validity is not proof of connectivity. Connection
readiness is introduced in later tasks. LIVE remains forbidden even if extra env
flags are set. Settings cannot be changed after validation.

Official source: [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).

## PostgreSQL and migrations (TAI-014)

SQLAlchemy 2.0 with psycopg 3 owns a lazy engine and sessionmaker. API lifespan
creates/disposes the engine without claiming DB connectivity. `Database.transaction()`
commits on success, rolls back on exception and always closes the session. SQL
parameters are hidden in engine errors and SQL echo is disabled.

Alembic reads validated TAI_DATABASE_URL at execution time; no credentials in ini
or migration source. The initial revision creates the `trading` namespace; future
domain tables live there. Version tracking remains in public.alembic_version.
No cash, order or account data is seeded by a migration. Downgrade drops only an
empty schema, without CASCADE. Do not run downgrade against owner data.

With Compose healthy, an isolated test database is created automatically by:

```powershell
# From repository root; requires local PostgreSQL port 15432 and generated .env
backend/.venv/Scripts/python.exe scripts/run-postgres-checks.py TAI-014
```

The runner names a newly-created database `tai_test_<uuid>`, executes all pytest
tests with a private TEST_DATABASE_URL, and drops only that test-owned DB in finally.
It never accepts a target DB name, never uses DROP FORCE, never deletes a volume
and redacts the generated local password. Missing engine/DB fails the runner.
Plain pytest without TEST_DATABASE_URL explicitly skips integration tests; those
skips are not evidence of migration success. The PostgreSQL runner is mandatory
for migration task acceptance.

To apply the migration to the **development** project database explicitly:

```powershell
docker compose --env-file infrastructure/.env -f infrastructure/compose.yaml exec -T backend alembic upgrade head
```

Run Compose commands from root. Test up/down/up uses an isolated empty database,
not the project database. There are no manual SQL setup steps.

Official references:
[SQLAlchemy sessions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html),
[Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html),
[psycopg](https://www.psycopg.org/psycopg3/docs/basic/install.html).

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
