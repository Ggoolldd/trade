# Bounded Kraken public OHLC adapter

TAI-030 implements explicit read-only OHLC and public SystemStatus methods for
canonical BTC/EUR and ETH/EUR. Only fixed api.kraken.com public GET paths are
reachable; no API key, signature, account/order endpoint, redirect or default feed
is configured. Quote/stream methods explicitly return UNSUPPORTED until the
streaming task. The HTTP client is owned by an async context and always closed.
Existing locked HTTPX 0.28.1 is now a runtime dependency, without version upgrade.

## Retention and checkpoints

The [official OHLC contract](https://docs.kraken.com/api-reference/market-data/get-ohlc-data)
states bounded recent history and an uncommitted final element regardless of since.
That final element is always dropped, even if a replay's wall clock is later.
One real response contained 721 records, consistent with 720 committed plus the
current frame; the parser accepts at most 721 and flags/fails larger shape changes.
Changing since does not recover expired history. It is not a backwards paginator.

| Interval | Approximate maximum recent span at 720 bars |
| --- | --- |
| 1 minute | 12 hours |
| 5 minutes | 2.5 days |
| 15 minutes | 7.5 days |
| 30 minutes | 15 days |
| 1 hour | 30 days |
| 4 hours | 120 days |
| 1 day | 720 days |

These are upper-bound estimates, not guarantees of gap-free data. This adapter
supports the listed REST intervals through daily; weekly/longer intervals are
explicitly unsupported by the current common contract. Each request is also
bounded by the common 366-day window and 5000-record limit.

BarPage.provider_cursor retains the server's last value. next_cursor is a separate
bounded page checkpoint derived from the final returned closed bar, so a server
cursor beyond the requested end cannot skip that window's remaining bars.
Truncation advances the checkpoint; empty pages have no next checkpoint. No
unbounded automatic pagination occurs. A detected capped response beginning after
the request reports RETENTION_GAP. Smaller responses do not invent a global
retention-start observation.

## Validation and uncertainty

Raw JSON is bounded to 2 MB. Pair identity, array width/order/alignment, positive
finite decimal-string OHLC, nonnegative volume/VWAP and integer trade counts are
validated. Duplicate/unsorted or mismatched pair rows fail closed. Completed bars
are filtered to the requested window and cannot close after local receipt time.
They retain the current observed/usable time; no historical usable timestamp is
fabricated. Later historical replay needs an explicit publication/availability
policy, not a backdated ingestion receipt.

Page diagnostics distinguish expected UNCOMMITTED_DROPPED from PROVIDER_TIME_AHEAD,
RETENTION_GAP, MISSING_BARS and PAGE_LIMIT. All material issues force incomplete
coverage; a validated subset is not presented as a full history or fresh feed.
Missing grid bars are not filled with invented prices/zero-volume candles.

Actual public research and host/Linux CLI calls observed source times slightly
ahead of the local clock. The real sample returned 59 eligible closed bars with
PROVIDER_TIME_AHEAD and coverage_complete=false. See observation/public/development
logs; no raw prices were committed. No claim of quality-approved realtime pricing
or authenticated broker/market-data entitlement follows from these reads.

## Rate/error handling

The provider adds a shared per-instance one-second start gate, independent of the
common client's gate. Multiple processes/instances still need a shared IP-level
limit. HTTP 429/Retry-After (delta or HTTP date), service throttles, timeout/network,
auth denial, server and malformed responses map to typed sanitized errors.
Long Retry-After is not shortened to the retry cap. Uninterpretable or greater-than-
one-day throttles freeze that provider instance and block further HTTP calls until
explicit reconstruction; they do not trigger an early fallback retry. There is no
auth/key fallback. Reuse one provider/client per event loop.

Sources: [Kraken error format](https://docs.kraken.com/exchange/guides/general/errors),
[rate limits](https://docs.kraken.com/exchange/guides/rest/ratelimits),
[HTTPX async response ownership](https://www.python-httpx.org/async/).
SystemStatus health is a source status observation, not candle-quality approval.

## Explicit sample and older history

```text
python -m app.kraken_ohlc --public --minutes 60 --symbol BTC/EUR
```

Run with the configured backend Python/PYTHONPATH or in the backend container.
The sample ends five minutes behind receipt, prints only count/cursors/issues/hash,
and does not enable a scheduler job or store canonical OHLC in the DB (TAI-033).
All catalog instruments remain suspended. PAPER settings are validated first.

For older crypto history, Kraken publishes
[historical OHLCVT archives](https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data)
and [time-and-sales archives](https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales-).
Review coverage, license/use rights, archive manifest/checksums, gaps and timestamp
semantics before importing. Multi-GB archives were not downloaded here. Alternative
licensed sources require their own evidence; REST retention cannot substitute for
them. Stock history remains separate; the owner confirmed no licensed stock feed yet.

Evidence: [TAI-030 report](reports/TAI-030.md). Synthetic HTTP fixtures and actual
public transport samples are explicitly separate.
