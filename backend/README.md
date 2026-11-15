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

## Canonical types and errors (TAI-015)

`domain_types.py` defines UUID entity IDs, UTC-aware timestamps, mode/side/instrument
enums and financial Decimal scalars. Financial input accepts only decimal strings
or Decimal instances, never float/int/bool; it rejects non-finite numbers and
values beyond NUMERIC(38,18). JSON emits a decimal string without float conversion.
Signed values are allowed for ledger use; order positivity is a separate domain rule.

`orm_types.py` provides the same finite/precision checks before binding, UTC
normalization on bind/read, and UUID/created_at mixin columns. PostgreSQL roundtrip
tests prove 38-digit decimal precision and rollback after invalid input. No domain
tables are added by these shared types; future models consume the mixin.

Each HTTP response includes X-Request-ID. A single valid UUID header is retained;
invalid/duplicate/missing values get a new UUID. Error responses use:

```json
{"error":{"code":"validation_error","message":"Request validation failed","request_id":"00000000-0000-0000-0000-000000000001"}}
```

404/405/HTTP errors, request validation and unexpected exceptions use this shape.
Raw request inputs, exception text and traceback are not logged or exposed by the
error middleware. Status-specific WWW-Authenticate/Retry-After/Allow headers are
preserved. Health readiness uses its separate typed health body with scope=process.
Request IDs correlate requests; they are not authentication or idempotency keys.

References: [Pydantic types](https://docs.pydantic.dev/latest/concepts/types/),
[FastAPI errors](https://fastapi.tiangolo.com/tutorial/handling-errors/),
[SQLAlchemy custom types](https://docs.sqlalchemy.org/en/20/core/custom_types.html).

## Catalog storage (TAI-016)

Revision 0002_catalog adds trading.venues, quote_currencies, instruments,
instrument_aliases and trading_hours. Every entity has UUID/UTC columns.
Venue code and currency code are unique; instrument symbol is unique per venue;
provider aliases are unique per venue/provider and carry a composite FK so they
cannot refer to an instrument from another venue. Aliases preserve provider case.

Instrument status is a checked enum (ACTIVE/SUSPENDED/DELISTED), default SUSPENDED.
STOCK/UCITS_ETF/SPOT_CRYPTO describes kind, not market-data entitlement, UCITS
eligibility evidence or trading permission. Catalog tables contain no seeded
real-world instruments in this task. ISIN shape is checked, not its checksum.

Trading hours store weekday 0=Monday through 6=Sunday, venue-local open/close and
an explicit next-day flag. Full-day sessions use equal open/close with next-day true.
Holidays, DST calendar expansion and overlap detection belong to TAI-028; stored
hours alone are not an exchange calendar. ORM venue timezones validate IANA names;
direct DB writers still must use the service boundary for semantic timezone checks.

DB connections explicitly use UTC and public search_path, while domain tables use
schema-qualified trading names. Alembic version tracking is explicitly public and
excluded from domain autogeneration; no generated version-table deletion is accepted.
Each integration fixture applies migrations independently of test collection order.

## PAPER accounts and profiles (TAI-017)

Revision 0003_accounts adds virtual paper_accounts, trading_profiles and scoped
account_permissions. Accounts/profiles default disabled. DB constraints permit
PAPER mode and LOCAL/STAGING environments only; LIVE/PROD identities cannot be
stored here. No broker account ID or private broker credential is represented.
Composite profile/permission foreign keys prevent mixing environment identities.

`resolve_paper_account()` requires exact PAPER mode, enabled account, matching
environment and PAPER_TRADE grant for the principal. It rejects unknown accounts,
wrong principal, wrong environment, SHADOW/LIVE and missing grants. It resolves
identity only; it does not approve risk or submit any order. Principal IDs are
opaque UUIDs until authentication/authorization tasks bind them to verified users.
No account mutation API is exposed by this task. Allowed scopes exclude withdrawals,
transfers and LIVE trading. Initial cash/ledger is a later task, not stored here.

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
