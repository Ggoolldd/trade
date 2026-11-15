# Read-only market-data provider contract

TAI-029 defines MarketDataProvider with fetch_bars, fetch_quote, stream_quotes and
provider_health. No order/account mutation/authentication method exists. The client
is injected explicitly; no default market feed is enabled by importing this module.
The contract suite uses a clearly named FixtureProvider in tests only. It proves
contract behavior, not a real provider connection, entitlement or live trading.

## Data

Frozen, revalidated DTOs carry canonical instrument UUID, provider identifier and
aware UTC timestamps. Financial inputs are finite decimal strings/Decimal, never
binary floats. Quotes require positive noncrossed bid/ask and exchange_at <=
observed_at <= usable_at <= current time. Closed bars require coherent positive
OHLC, nonnegative volume, an integer interval, and close <= observed <= usable.
Partial/in-progress candles cannot masquerade as completed bars.

BarPage has a bounded tuple, optional opaque checkpoint/native provider cursor,
optional raw source hash and typed quality issues (added by TAI-030), optional known retention
start and coverage_complete=false by default. False/unknown coverage must not be
promoted to a complete historical dataset. The client checks requested identity,
provider, interval, limit, ordered nonoverlapping time bounds and retention claims.
It does not infer missing-bar completeness from a count. Pagination and retention
limits remain adapter-specific; no automatic unbounded pagination occurs.

Read requests require UUID, aware ordered nonfuture start/end, at most 366 days,
interval <= one day, limit 1-5000 and cursor <=128 characters. Quote freshness and
market/feed/risk eligibility remain separate future gates. Old but observed data
is not automatically declared fresh just because transport returned it.

## Execution and normalized errors

One MarketDataClient per provider/event loop owns a concurrency semaphore and
monotonic start-spacing gate. Multiple callers share it; separate processes or
separately created clients do not share this in-memory limit. A provider registry
must reuse the same client and add distributed limits if multiple workers fetch.
Defaults: 4 concurrent operations, 0.2-second minimum spacing, 3 total attempts,
5-second per-attempt timeout and 20-second overall read deadline. Queueing,
throttling and retry sleeps count against the overall deadline.

| Code | Adapter meaning | Client behavior |
| --- | --- | --- |
| TIMEOUT | Cancellable read expired | Bounded retry within total deadline |
| RATE_LIMITED | Provider throttle/429 | Shared cooldown; honor Retry-After, never shorten it to retry cap |
| UNAVAILABLE | Transient connectivity/service failure | Bounded exponential retry |
| AUTH_DENIED | Authentication/entitlement denied | No retry or credential fallback |
| UNSUPPORTED | Method/pair unsupported | No retry |
| INVALID_DATA | Schema/identity/numeric/time failure | No retry or fabricated data |
| ADAPTER_ERROR | Unexpected adapter exception | Sanitized error, no retry |

Adapters normalize transport/status/header semantics into these typed codes;
HTTP-specific parsing is not claimed implemented here. Raw remote text, URL,
credentials and exception details never become ProviderError messages. Backoff
starts at 0.25 seconds and caps at 2 seconds by default. A longer Retry-After causes
the read to fail while preserving the shared cooldown; it is not clamped into an
early retry. Policy is validated again at the client boundary, including values
constructed by bypassing ordinary model validation. No infinite retry exists.

Adapters must use nonblocking, cancellable I/O. Asyncio deadlines cannot preempt
blocking event-loop code or an adapter that suppresses cancellation. This limitation
is part of the provider contract, not hidden by claiming a hard OS-level timeout.
Official behavior: [Python asyncio](https://docs.python.org/3.12/library/asyncio-task.html#timeouts).

## Stream ownership

Streaming reserves one concurrency slot until cleanup and acquires the same start
gate under an initial deadline. Quotes are requested one at a time, providing
backpressure without an unbounded queue. Default idle deadline is 60 seconds;
cancellation propagates, does not retry, and closes the underlying generator.
This layer does not reconnect a stream or assume duplicate-free sequence; TAI-031
will implement provider-specific reconnect/heartbeat/order handling explicitly.

Consumers stopping early must close the generator, preferably with
[contextlib.aclosing](https://docs.python.org/3.12/library/contextlib.html#contextlib.aclosing).
Cleanup has a 1-second default deadline; failures produce only the fixed sanitized
market_data_stream_close_failed warning. Cancellation remains cooperative.
Health values remain provider observations; a failed request is not replaced with
a synthetic HEALTHY report.

Evidence: [TAI-029 report](reports/TAI-029.md). The suite covers the four-method
fixture contract, transient/permanent errors, retry cap, deadlines, cooldown,
malformed/bypassed DTOs and policies, candle overlap/identity/retention, stream idle,
queued deadlines, early close and cancellation. No external feed calls were made.
