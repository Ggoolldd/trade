# Configurable stock and UCITS candidates

TAI-027 supplies [candidate JSON](../backend/config/security_candidates.json): ten
ordinary-share research candidates and two issuer-described UCITS ETF candidates.
This is metadata for development, not a recommendation, liquidity guarantee,
broker contract lookup, Croatian distribution approval or live trading universe.
Broker availability and HR retail eligibility are UNKNOWN; liquidity is UNVERIFIED.
Every imported instrument stays SUSPENDED. No eligibility or account grant is created.

## Identity

ISIN identifies a share class; ticker identifies a listing only in its MIC/venue.
The importer uses deterministic MIC+ISIN UUIDs and venue-scoped ticker uniqueness.
A same-venue conflicting ticker is rejected; the same ticker on two venues remains
two different instruments. Current supported MICs are XETR and XAMS with explicit
Europe/Berlin and Europe/Amsterdam zones. Default candidates use only XETR.
[ISO MIC reference](https://www.iso20022.org/market-identifier-codes).
ISIN syntax and Luhn check digit are validated; syntax is not listing proof.

Quote currency EUR is separate from ETF share-class currency USD. UCITS is an
issuer product classification, not proof that a Croatian retail account may buy it.
No KID language/distribution entitlement, live quote permission or spread/volume
threshold is inferred. All those future gates must be checked separately.

## Reviewed source references

Each JSON row has primary issuer URLs. Review time records when this candidate
configuration was assembled, not when every source document was issued. Some
references are historical; they do not certify present venue/broker availability.
The large-cap research shortlist is deliberately unranked; current execution
liquidity must still be measured. Existing historical backtests must not use this
current candidate list as a point-in-time historical universe.

| Ticker | ISIN | Primary source |
| --- | --- | --- |
| SAP | DE0007164600 | [SAP](https://www.sap.com/investors/en/stock/basic-data.html) |
| SIE | DE0007236101 | [Siemens](https://www.siemens.com/de-de/company/investor-relations/share-bonds-rating/basic-data-key-share-figures/) |
| ALV | DE0008404005 | [Allianz](https://www.allianz.com/en/investor_relations/share/share-information.html/) |
| DTE | DE0005557508 | [Telekom](https://www.telekom.com/en/investor-relations/share) |
| BMW | DE0005190003 | [BMW ordinary shares](https://www.bmwgroup.com/en/investor-relations/bmw-shares.html) |
| BAS | DE000BASF111 | [BASF](https://www.basf.com/global/en/investors/calendar-and-publications/service-for-shareholders/faq/share-and-dividend) |
| MBG | DE0007100000 | [Mercedes-Benz](https://group.mercedes-benz.com/investors/share/) |
| DHL | DE0005552004 | [DHL](https://group.dhl.com/en/investors/shares/share-performance.html) |
| BAYN | DE000BAY0017 | [Bayer ISIN reference](https://www.bayer.com/sites/default/files/managers-transactions-in-fiscal-year-2026-as-of-05-03.pdf) |
| ADS | DE000A1EWWW0 | [adidas](https://www.adidas-group.com/de/investoren/aktie/aktien-basisinformationen) |
| EUNL | IE00B4L5Y983 | [iShares](https://www.ishares.com/uk/individual/en/products/251882/ishares-msci-world-ucits-etf-acc-fund) |
| VUSA | IE00B3XXRP09 | [Vanguard](https://www.vanguard.co.uk/professional/product/etf/equity/9503/sp-500-ucits-etf) |

Bayer's historical issuer prospectus ticker reference is also retained in JSON.
The iShares and Vanguard product/listing pages separate USD class from EUR listing.

## Import and limits

The CLI requires an explicit file and performs no network requests. Reconfigure
JSON to 10-20 stocks and 2-3 UCITS candidates; invalid identities, duplicates,
unsupported MIC/currency/product kind or availability claims fail before DB writes.
Source references require public HTTPS without embedded credentials; URLs are not
executed/fetched by this importer. Unknown fields cannot enable trading.

After building the local image:

```text
docker compose --env-file infrastructure/.env -f infrastructure/compose.yaml run --rm backend python -m app.security_candidates --file /app/config/security_candidates.json
```

Only this public JSON is allowed through the Docker context whitelist. Sources,
review time and uncertainty flags stay versioned in JSON; the audit correlation
UUID derives from its raw-byte SHA256. No new DB table or API contract is needed.
The catalog persists ISIN/ticker/venue/quote currency/product kind and suspension.
Import is atomic, serialized and repeatable; conflicts never overwrite operator
edits. Metadata changes require explicit reconciliation, not a reset option.

Evidence: [TAI-027 report](reports/TAI-027.md). Synthetic cross-venue collision test
rows are confined to the isolated test DB, not claims of actual XAMS listings.
