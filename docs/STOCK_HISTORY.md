# Historical stock source and coverage decision

TAI-032 is PARTIAL. The owner confirmed there is no permitted historical stock
source yet. No subscription was purchased, credentials requested, external stock
history downloaded or production entitlement asserted. No free feed is hardcoded.
The existing read-only MarketDataProvider contract remains the abstraction.

## Implemented development path

HistoricalCsvProvider accepts only explicitly confirmed project-authored synthetic
CSV data in FIXTURE configuration. Its manifest rejects production or licensed
purpose assertions. This is a test adapter, not a connection to a licensed stock
provider. The inline artificial EUR sample in test_history_csv.py contains no
market observations or actual security identity.

The exact CSV columns are opened_at, closed_at, open, high, low, close, volume.
Financial values parse directly to Decimal. Timestamps require aware UTC and
completed bars; records must be ordered, nonoverlapping and inside declared
coverage. Input is limited to 1 MB and 5000 rows, with an exact source SHA-256.
Duplicate timestamps, malformed rows, nonfinite values and inconsistent OHLC fail
closed. There are no quote/stream capabilities, remote URLs, scheduler jobs or
automatic catalog changes.

The manifest records provider, synthetic purpose, instrument ID, EUR currency,
unadjusted convention, interval, source hash, observed time, coverage bounds and
the artificial-data statement. usable_at is the declared observation/import time;
the adapter does not invent historical publication availability. Sparse fixture
coverage is always incomplete: first/last rows do not establish exchange session,
holiday, delisting or missing-bar coverage. Canonical bar storage remains TAI-033.

Migration 0011_history_imports stores the canonical manifest, its own SHA-256,
source SHA-256 and row count in PostgreSQL. A deterministic UUID plus unique hash
and transaction lock make replay idempotent; caller rollback removes the record.
The database explicitly rejects missing or nonsynthetic purpose. This table is
provenance for fixture imports, not evidence of a third-party data license.

## Remaining prerequisite for a real source

Select a provider or licensed local dataset and supply its source identity and
documented permission for the intended use. The review must establish storage,
research/backtesting and any redistribution limits, applicable instruments and
venues, coverage dates, timestamp semantics, corporate-action adjustment, delay,
revision history and expiry/revocation handling. These are unresolved requirements,
not claims about a vendor's terms. Credentials remain in ignored local settings.

Only after that decision should a real adapter and entitlement configuration be
implemented and exercised against the authorized source. Fixture tests cannot
substitute for that evidence. TAI-032 must remain PARTIAL until this prerequisite
is resolved; dependent TAI-033 work is held under the project continuation rule.
