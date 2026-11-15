# Canonical EUR spot metadata

TAI-026 maps BTC/EUR and ETH/EUR to Kraken spot identities. Canonical symbols are
exact and case-sensitive; XBT/EUR is a venue WebSocket alias, not the canonical
application input. Deterministic venue-scoped UUIDs are stable across imports.
REST internal symbols, alternate symbols and WebSocket aliases are separate rows.
The synthetic DEMO_FIXTURE catalog from TAI-025 remains separate.

The fixed unauthenticated endpoint is
[Kraken AssetPairs](https://api.kraken.com/0/public/AssetPairs?pair=XBTEUR,ETHEUR).
[Official contract](https://docs.kraken.com/api-reference/market-data/get-tradable-asset-pairs)
was reviewed on 2026-11-15; current public response was actually fetched.
Legacy internal asset keys are requested without assetVersion. Unexpected identity,
quote, status or schema drift fails closed instead of guessing a mapping.

Only the two expected EUR currency/unit spot records with online status are
accepted. Monetary fields must be finite positive decimal strings within
NUMERIC(38,18); float inputs are rejected. Tick size comes from tick_size.
Quantity step is 10^-lot_decimals after checking integer precision, unit lots and
lot_multiplier=1. Minimum quantity and EUR notional come from ordermin/costmin.
These are observations of venue rules, not promises of current availability.
Margin/leverage fields in the public response do not enable margin trading.

InstrumentRules stores exact rules with source SHA256 and aware UTC observation.
Each new response hash creates new rule versions; earlier rows are not overwritten
by the importer. Identical bytes reuse the first observation time, conservatively
preserving provenance instead of relabeling a replay as fresh data. Historical
imports need actual observed-at and cannot have future or naive timestamps.
Freshness, point-in-time selection and risk/order use must be implemented by later
tasks before consuming these values in any execution path.

Imports are transactional and serialized with a transaction advisory lock. Owner
identity/rule conflicts are rejected. Both instruments always remain SUSPENDED;
no account permission, feed activation, secret or trading endpoint is created.

After the development migration, explicit public read-only import:

```text
docker compose --env-file infrastructure/.env -f infrastructure/compose.yaml run --rm backend python -m app.crypto_catalog --public
```

Offline mode takes --file and mandatory --observed-at ISO UTC timestamp; it does
not substitute the time of replay. Files/network responses are size bounded;
network requests have a fixed HTTPS URL and 20-second timeout. Public import was
actually executed twice on the local PAPER stack; the captured fixture is a separate
historical response with URL, capture time and exact raw-byte SHA256 in tests/fixtures.
Fixture tests are not proof of an authenticated broker connection or entitlement.

Evidence: [task report](reports/TAI-026.md). Test suite covers aliases, absent/unknown
pairs, error responses, identity mixups, bad precision/lot rules, float/nonfinite/
negative values, rollback, four concurrent importers, replay and version retention.
