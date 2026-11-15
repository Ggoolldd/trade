# Deterministic local demo data

TAI-025 adds explicit seed v1; it never runs at startup. In the configured local
PAPER/FIXTURE backend container, after migrating:

```text
docker compose --env-file infrastructure/.env -f infrastructure/compose.yaml run --rm backend python -m app.demo_seed --confirm-fixture
```

Use the isolated Docker config described in infrastructure README on this Windows
machine. The real command has been executed twice; see the development evidence.
No users, passwords, API keys, account grants or trading profiles are created.

Seed-owned UUIDs derive from a fixed namespace and version; catalog creation times
are fixed at 2026-11-15T00:00:00Z. Existing EUR currency is shared if display scale
matches. A synthetic DEMO_FIXTURE UTC venue contains suspended BTC/EUR and ETH/EUR,
FIXTURE aliases and seven full-day weekly sessions. This is a fictional 24/7 demo
calendar, not a real venue holiday calendar or market-data entitlement.
TAI-026 will separately implement actual venue mapping and tick/lot metadata.

The LOCAL PAPER account Demo fixture v1 remains disabled. Its exact Decimal
initial_cash_eur=10000 is scenario configuration, **not spendable cash, a deposit,
a balance or a ledger entry**. Existing accounts migrate with zero scenario input.
A later ledger task must implement auditable initial funding before using it.

One transaction and a transaction-scoped advisory lock serialize concurrent seeds.
Repetition reuses identities and audit event. Matching rows are preserved; changed
fixture fields raise SeedConflict and the transaction rolls back. Natural-key
collisions also roll back instead of overwriting data. No update/reset/delete
option exists. A deterministic append-only ACCOUNT_CHANGED audit record marks
fixture initialization, with real recorded timestamp.

The schema enforces a nonnegative NUMERIC(38,18) initial value; all application
money binding rejects floats. No default operator account or permission is added.
Downgrade removes only this configuration column; no development downgrade was run.

Validation evidence: [TAI-025 report](reports/TAI-025.md), full real PostgreSQL/Redis
suite including seed rollback, four concurrent callers, repeatability, owner-edit
conflict, nonfixture feed rejection, and exact/nonnegative scenario cash.
