# TRADING-AI

PAPER-first trading research project. TAI-001 through TAI-028 are implemented and
verified: FastAPI health/auth/roles, PostgreSQL catalog/accounts/audit, Redis worker,
scheduler and a versioned read API. No broker transport, strategy execution, ledger
or order execution exists yet. A minimal Android Compose app supplies real CI
test/lint/debug builds; full client functionality remains future work.

Development starts in PAPER mode. LIVE requires separate owner authorization and
the evidence gates in [ROADMAP.md](ROADMAP.md); completing development tasks does
not authorize real orders.

## Layout

| Directory | Purpose |
| --- | --- |
| android | Minimal Compose app with genuine Gradle checks |
| backend | FastAPI backend, migrations and automated checks |
| docs | Decisions, specifications, and task evidence |
| infrastructure | Local PAPER Compose stack and prepared CI configuration |
| research | Reproducible research and experiments |
| cursor_tasks | Supplied individual task definitions |

## Source and progress

The specifications and all 189 task definitions were imported from the supplied
TRADING-AI-CURSOR-BACKLOG/TRADING-AI-CURSOR folder without editing.
See [STATUS.md](STATUS.md) for implementation status.
The owner's request authorizes continuation through tasks;
the supplied template's per-task stopping text does not cancel that request.

License selection is pending: [docs/LICENSE_DECISION.md](docs/LICENSE_DECISION.md).

## Run and verify

Start with [backend setup](backend/README.md) and
[local infrastructure](infrastructure/README.md). The local backend binds
127.0.0.1:18000; health readiness currently covers process lifecycle. PostgreSQL,
Redis, backend and worker have separate healthchecks. Generated local-only DB/Redis
passwords are ignored; there are no default operator credentials or broker keys.

Current full integration suite: 159 tests passing on real PostgreSQL/Redis, plus
lint/type/contract checks. Evidence and exact commands are in [STATUS.md](STATUS.md).
[CI quality](docs/CI.md) runs on GitHub: backend and Android checks, workflow lint,
secret scan and an always-run required-quality gate. The public repository has
active main-branch enforcement; an unchecked test push was actually rejected.
