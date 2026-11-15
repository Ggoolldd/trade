# Backend

Python 3.12, FastAPI, Uvicorn. Health endpoints start without API keys; auth and
domain storage require local PostgreSQL. `uv.lock` records exact dependencies.

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
docker compose --env-file infrastructure/.env -f infrastructure/compose.yaml --profile tools run --rm migrate
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
identity only; it does not approve risk or submit any order. TAI-020 binds principal
UUIDs to verified users; account grants remain independent of global roles.
No account mutation API is exposed by this task. Allowed scopes exclude withdrawals,
transfers and LIVE trading. Initial cash/ledger is a later task, not stored here.

## Append-only metadata audit (TAI-018)

Revision 0004_audit creates audit_events with UUID, correlation/actor/entity IDs,
checked event/reason enums, PAPER mode, UTC timestamp, sequence, previous hash and
SHA-256 event hash. No arbitrary payload, free text, headers or credential field
exists. Financial/domain payloads remain separately versioned; audit references
their UUIDs. Never encode a secret in an identity field.

PostgreSQL BEFORE INSERT serializes appends with a transaction advisory lock,
assigns sequence/previous hash and hashes a canonical pipe-separated set of typed
fields (UTC with six fractional digits). It ignores caller-supplied chain values.
Rollback does not consume a sequence. Unique event UUID prevents duplicate effects;
duplicate insert is an explicit conflict, not silently accepted with different data.
Append in the caller's financial transaction; acquire domain locks before the audit
lock consistently to avoid future lock-order inversions.

UPDATE/DELETE/TRUNCATE are blocked by triggers. Actual local backend uses
trading_ai_app (non-owner, no admin/DDL privileges), with audit SELECT/INSERT only.
An opt-in tools/migrate service holds the separate admin DSN. Configure permissions
after migrations with scripts/bootstrap-runtime-db.py; generated admin/runtime
passwords remain in ignored infrastructure/.env. See
[infrastructure startup](../infrastructure/README.md) for ordering.

`verify_chain()` requires trusted expected_head and expected_count, detects content
changes, reordered/missing events and tail removal against that checkpoint. A
checkpoint read from the same compromised DB is not an independent trust anchor.
Off-host signed exports/checkpoint storage belong to TAI-171; a DB administrator
could disable triggers and rewrite a local chain. pgcrypto is retained on downgrade
because it may predate the project. No cryptographic signature or remote audit
immutability is claimed by this task.

## Local authentication (TAI-019)

Revision 0005_auth adds users, sessions and durable login_throttles. Passwords use
pwdlib Argon2id; users default disabled unless explicitly created/enabled by a local
operator. There is no public registration, default password or automatically created
owner. Login returns a cryptographically random 256-bit opaque bearer token valid
for 15 minutes; only its SHA256 hash is stored. Every request checks expiry,
revocation and user enabled state in PostgreSQL. Logout revokes the current session.
No refresh token exists; expiry requires a new login.

Routes: POST /api/v1/auth/login (username/password JSON), GET /api/v1/auth/me and
POST /api/v1/auth/logout (Bearer Authorization). All auth responses use no-store;
errors follow the canonical envelope. Login errors do not disclose whether a username
exists, and unknown users execute a dummy Argon2 verification. Brute-force protection
allows five failed attempts per 15-minute fixed window, checked for both normalized
username and server-observed client source. Buckets are hashed, durable and locked
transactionally; the sixth attempt returns 429/Retry-After. Forwarded headers are
not used to choose the source. Failed counters/audit commit before HTTP rejection.

Create a local user interactively after migration and runtime-role bootstrap:

```powershell
docker compose --env-file infrastructure/.env -f infrastructure/compose.yaml exec backend python -m app.manage_users myuser
```

The command prompts twice through getpass (15–128 characters); do not put passwords
in shell arguments, Git or chat. It grants no account trading permission. Role/owner
assignment is TAI-020. No real operator user was created by the agent in TAI-019.
For local tooling outside a container, use the same module with a validated DB env.

Auth fixtures use synthetic passwords, a controlled clock and a real isolated
PostgreSQL database. Tests cover expiry exactly at 15 minutes, logout, disabled
users, unknown/malformed tokens, durable counters, concurrent attempts and rollback
of session creation when audit storage fails. They do not claim MFA or LIVE unlock.
TLS and broader endpoint abuse limits are later infrastructure tasks; keep this
development server on localhost. A trusted proxy needs an explicit source policy
before non-local deployment. Throttle windows are a private-app development policy,
not a substitute for network-level DoS protection.

Reviewed sources:
[FastAPI password hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/),
[OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html),
[OWASP sessions](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
Opaque server-side sessions were chosen instead of JWTs for immediate DB revocation.

## Roles and permission guards (TAI-020)

Revision 0006_authorization adds checked user roles, default readonly for existing
and new users, and links account permission principals to verified users by FK.
No migration elevates an existing user. Roles are fetched from DB on every bearer
verification; downgrading a role affects the next request for the same token.
X-Role or other client-provided role headers have no authority.

| Role | Read status/portfolio/orders/risk | PAPER intents/cancel | Config/risk edit | STOP/resume |
| --- | --- | --- | --- | --- |
| owner | Yes | Yes | Yes | Yes |
| readonly | Yes | No | No | No |
| system_worker | Yes | Yes | No | No |

Use `Depends(require_permission(Permission...))` at server routes. Denials return
403 and append typed authorization audit metadata; missing/invalid bearer is 401.
`/api/v1/capabilities` reports the authenticated role and permissions. There are no
config/risk/order/STOP mutation APIs yet: their later implementations must use these
guards plus account-level scope, mode, risk and lifecycle validation. Integration
tests use explicitly named synthetic probe routes to verify HTTP denial; they do
not claim an implemented STOP engine or order execution.

The PAPER resolver additionally requires an enabled verified owner/system_worker,
a per-account PAPER_TRADE grant and the environment/mode conditions. A readonly
user cannot trade even if mistakenly given that account grant. Worker-triggered
automatic safety HALT is an internal risk responsibility, separate from owner-only
interactive STOP/resume control permissions.

Local operator creation supports `--role owner|readonly|system_worker`, default
readonly. For example, append `--role owner` to the hidden-password creation command
above when explicitly provisioning the private owner. No user/role was auto-created
or elevated by this task. No role grants LIVE or bypasses risk/MFA/unlock requirements.

## Redis queue and worker (TAI-021)

Revision 0007_jobs adds jobs and dead_letters. PostgreSQL owns status, retry due
times, attempts, UUID idempotency keys, queue identity and correlation IDs. Redis
Streams is at-least-once transport with consumer groups and pending-message reclaim.
Only the registered audit_checkpoint handler exists; it appends an actual SYSTEM
audit event using the job UUID. There is no arbitrary task import/pickle/payload,
broker operation or financial handler.

Enqueue is idempotent for the same key and semantic fields; a different kind/entity/
queue/attempt policy with that key is a conflict. Dispatcher publishes due jobs with
bounded SKIP LOCKED batches and a 60-second re-publication cooldown. A lost publish
response can duplicate delivery; it cannot duplicate the transactional effect.
Worker locks the DB job, runs its handler in a savepoint, and commits status/effect
before ACK. Retries back off 1, 2, 4... seconds capped at 60; default max attempts 3.
Exhaustion commits a unique DB dead-letter row with sanitized code and trace IDs.

ACKed messages are removed; abandoned pending deliveries are reclaimed after 60 s.
Malformed/unknown/cross-queue references are discarded with a sanitized warning and
never create a DB job. The DB remains the authoritative source; such transport
poison is not reported as a failed business handler. Redis RESP2 is explicit for
stable stream response parsing. Test namespace cleanup deletes only the exact
test-owned stream in Redis DB15, never FLUSHDB or owner keys.

Handlers currently perform DB-only effects in the caller's transaction. This is
not an exactly-once guarantee for external HTTP/broker operations; those need their
own idempotency/reconciliation design and later gates. Running a long external
operation while holding this job transaction is outside the current handler contract.
Audit/job logs contain UUID tracing and fixed codes, no exception payload or secrets.

Sources: [Redis streams](https://redis.io/docs/latest/develop/data-types/streams/),
[XAUTOCLAIM](https://redis.io/docs/latest/commands/xautoclaim/),
[redis-py streams](https://redis.readthedocs.io/en/stable/examples/redis-stream-example.html).

## Scheduler and restart safety (TAI-022)

Revision 0008_schedules adds schedules and scheduled_runs. Schedules default disabled;
no live/strategy/import schedule is created automatically. Worker polls Scheduler.tick
before queue dispatch. It takes a row lock with SKIP LOCKED and a transaction-scoped
PostgreSQL advisory lock derived from schedule UUID. Both release on commit/rollback
or connection loss; no stale Redis lease needs to be trusted.

A UTC interval slot has a stable UUID5 idempotency key. Job enqueue, occurrence
lineage and next-run cursor advance commit in one DB transaction. Parallel starts
or restart in the same slot produce one job. After downtime, the explicit v1 policy
coalesces missed slots to the latest due one, then advances to the next interval;
it does not silently generate an unbounded backfill. Future import/research jobs
must define whether this policy is suitable for them before registration.

Intervals are 1–86400 seconds, UTC and fixed duration. This is not an exchange
calendar or local-time/DST cron implementation. Actual import/evaluation handlers
are not yet registered. Tests prove concurrent starts, held-lock skip/release,
disabled scheduling and rollback after an injected pre-commit enqueue crash on
real PostgreSQL. Worker idempotency remains the final defense against transport
redelivery; advisory locking alone is not an external exactly-once guarantee.

References: [PostgreSQL advisory locks](https://www.postgresql.org/docs/17/explicit-locking.html#ADVISORY-LOCKS),
[advisory lock functions](https://www.postgresql.org/docs/17/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS).

## API contracts, filters and pagination (TAI-023)

Domain routes use /api/v1; unversioned /health/* are operational checks. Breaking
domain changes require deliberate version/contract review. All /api/v1 responses
are no-store and carry X-Request-ID; errors use the shared error envelope. Input
validation and malformed cursor both return 422/validation_error without raw input.
401/403/422/500 models and Bearer security are recorded in OpenAPI.

GET /api/v1/jobs is authenticated read-only status monitoring (status:read guard).
It returns Page[JobView]: items, limit, has_more and next_cursor. PageQuery defaults
limit=50, bounds 1–100, and rejects unknown query fields. Supported filters are
status (checked JobStatus) and queue_name (bounded ASCII queue identity). Offset
and arbitrary sort/filter expressions are unsupported and rejected.

Keyset order is created_at then UUID, ascending. Pass the returned opaque cursor
with the same filters to fetch the next page; changing page size is allowed within
bounds. Cursor version 1 contains UTC position and filter identity; malformed,
oversized, unsupported-version and filter-mismatched cursors fail validation.
Cursors are positions, not signed auth tokens; every page still checks bearer/role.
No raw job payload, credentials or password/session hashes are exposed.

Concurrent state changes can alter membership of a filtered live view. Pagination
does not promise a frozen dataset or total count; use a future immutable dataset/
export contract for reproducible research. No order-write API is introduced here.

Contract tests compare the whole generated schema with tests/fixtures/openapi.json;
a negative test proves endpoint removal is rejected. Tests never rewrite fixtures.
For an intentional reviewed update from repo root:

```powershell
$env:PYTHONPATH = 'D:\TRADING\backend'
backend/.venv/Scripts/python.exe scripts/update-openapi.py
git diff -- backend/tests/fixtures/openapi.json
```

Inspect schema diff and compatibility before committing it; updating a snapshot is
not itself approval for a breaking change. Dependency versions remain locked so
schema generation is reproducible.

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

## Demo fixture

Explicit deterministic local seed and its limits are documented in
[demo data](../docs/DEMO_DATA.md). It creates a disabled PAPER account and synthetic
catalog; starting cash is configuration only, not an implemented ledger.
