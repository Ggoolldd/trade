# Kraken public ticker stream

TAI-031 adds an explicit, read-only WebSocket v2 adapter for BTC/EUR and ETH/EUR.
Run `python -m app.kraken_stream --public --quotes 3 --seconds 15` from the
configured backend environment. This does not enable a background feed or orders.
Prices are omitted from the sample output.

The fixed public endpoint is `wss://ws.kraken.com/v2`. The adapter subscribes to
ticker snapshots and best-bid/offer changes. WebSocket v2 uses BTC/EUR, separate
from the legacy XBT/EUR mapping. Numeric JSON prices decode directly to Decimal.
Online status, successful matching subscription acknowledgement and a snapshot
are required before updates. Server timestamps remain unchanged; future quotes
are rejected rather than adjusted to the local clock.

Heartbeats establish transport liveness; application ping/pong has a separate
deadline that continuing heartbeats cannot conceal. Neither produces a quote.
Identical timestamps and prices are duplicates; older timestamps or changed
prices at the same timestamp are discarded and degrade health. Message counts
are local diagnostics, not exchange sequence numbers or proof of gap-free data.

Disconnects use bounded reconnect attempts, jittered exponential backoff and a
shared per-instance connection gate. A new connection requires a fresh snapshot.
Previously accepted quotes are retained only to check ordering, never emitted as
replacement ticks. There is no replay or guarantee of recovering missed changes.
Invalid data fails closed. HTTP handshake throttling freezes the instance;
reconstruction requires an explicit operator decision. Limits are not distributed
across processes or machines. Cancellation closes the socket and releases locks.

## Actual environment observation

The real public endpoint returned online status, a successful subscription and
a ticker snapshot. Its timestamp was 2026-11-15T21:13:05.412843Z while Windows
received it at 21:10:50.077171Z. The adapter correctly refused this future quote.
Independent Microsoft NTP stripchart samples measured Windows approximately
136.21 seconds behind; Windows Time was stopped with Manual startup. Kraken's
public Time endpoint independently showed the same discrepancy. Raw price frames
remain ignored under tmp and are not published.

On 2026-11-17 the owner explicitly approved system clock synchronization.
Windows Time was started using an administrator helper, retaining the existing
Microsoft peer configuration and Manual startup. The first resync reported no
data; a subsequent administrator resync succeeded, with Leap Indicator 0 and
three measured offsets below two milliseconds. Actual host and Linux samples
then accepted three ticks each without timestamp adjustment. The Linux sample
also discarded two duplicate frames. See the TAI-031 clock, public and development
evidence. This confirms connectivity and timestamp acceptance at sampling time;
it does not establish continuous uptime or gap-free market data.

## Primary references

- [Kraken ticker v2](https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/ticker)
- [Kraken heartbeat v2](https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/heartbeat)
- [Kraken application ping](https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/ping)
- [Kraken server time](https://docs.kraken.com/api-reference/market-data/get-server-time)
- [websockets client](https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html)
