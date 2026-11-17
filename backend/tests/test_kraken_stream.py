"""Synthetic sockets test recovery; never treated as real feed integration."""

import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import aclosing, asynccontextmanager
from datetime import timedelta
from decimal import Decimal

import pytest

from app.crypto_catalog import catalog_id
from app.domain_types import utc_now
from app.kraken_stream import KrakenTickerProvider, Socket, StreamPolicy, decode_frame, ticker_quote
from app.market_data import HealthStatus, ProviderCode, ProviderError
from app.market_data_client import RateGate

INSTRUMENT = catalog_id("BTC/EUR")
STATUS = json.dumps({"channel": "status", "type": "update", "data": [{"system": "online"}]})
ACK = json.dumps(
    {
        "method": "subscribe",
        "success": True,
        "req_id": 1,
        "result": {"channel": "ticker", "symbol": "BTC/EUR"},
    }
)


def tick(
    timestamp: str,
    kind: str = "snapshot",
    *,
    bid: str = "100.123456789012345678",
    symbol: str = "BTC/EUR",
) -> str:
    raw = json.dumps(
        {
            "channel": "ticker",
            "type": kind,
            "data": [
                {"symbol": symbol, "timestamp": timestamp, "bid": "BID_NUMBER", "ask": "ASK_NUMBER"}
            ],
        }
    )
    return raw.replace('"BID_NUMBER"', bid).replace('"ASK_NUMBER"', "101.123456789012345678")


class FixtureSocket:
    def __init__(self, frames: list[str | Exception], *, pong: bool = False) -> None:
        self.frames: asyncio.Queue[str | Exception] = asyncio.Queue()
        for frame in frames:
            self.frames.put_nowait(frame)
        self.sent: list[dict[str, object]] = []
        self.closed = False
        self.pong = pong

    async def send(self, message: str) -> None:
        body = json.loads(message)
        self.sent.append(body)
        assert body["method"] in {"subscribe", "ping"}
        assert "token" not in message and "add_order" not in message
        if self.pong and body["method"] == "ping":
            self.frames.put_nowait(
                json.dumps({"method": "pong", "success": True, "req_id": body["req_id"]})
            )

    async def recv(self) -> str | bytes:
        item = await self.frames.get()
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self) -> None:
        self.closed = True


class FixtureConnector:
    def __init__(self, sockets: list[FixtureSocket]) -> None:
        self.sockets = sockets
        self.calls = 0

    @asynccontextmanager
    async def __call__(self) -> AsyncGenerator[Socket, None]:
        self.calls += 1
        if self.calls > len(self.sockets):
            raise OSError("synthetic disconnected")
        socket = self.sockets[self.calls - 1]
        try:
            yield socket
        finally:
            await socket.close()


def provider(connector: FixtureConnector, **kwargs: object) -> KrakenTickerProvider:
    policy = StreamPolicy.model_validate(dict(base_backoff=0.001, max_backoff=0.002, **kwargs))
    result = KrakenTickerProvider(policy, connector=connector)
    result.connect_gate = RateGate(0.0)  # Synthetic sockets only, never a real endpoint.
    return result


def test_disconnect_resnapshot_duplicate_never_emits_phantom_tick() -> None:
    async def run() -> None:
        first_time = utc_now() - timedelta(seconds=3)
        second_time = first_time + timedelta(seconds=1)
        one = FixtureSocket(
            [STATUS, ACK, tick(first_time.isoformat()), OSError("synthetic link lost")]
        )
        two = FixtureSocket(
            [STATUS, ACK, tick(first_time.isoformat()), tick(second_time.isoformat(), "update")]
        )
        connector = FixtureConnector([one, two])
        source = provider(connector)
        async with aclosing(source.stream_quotes(INSTRUMENT)) as stream:
            first = await anext(stream)
            second = await anext(stream)
            assert first.exchange_at == first_time and second.exchange_at == second_time
            assert first.bid == Decimal("100.123456789012345678")
            state = source.states[INSTRUMENT]
            assert state.quotes == 2 and state.duplicates == 1 and state.disconnects == 1
            assert connector.calls == 2
            assert (await source.provider_health()).status is HealthStatus.HEALTHY
        assert one.closed and two.closed
        assert (await source.provider_health()).status is HealthStatus.UNAVAILABLE

    asyncio.run(run())


def test_out_of_order_and_same_time_conflict_do_not_emit_quotes() -> None:
    async def run() -> None:
        time = utc_now() - timedelta(seconds=5)
        socket = FixtureSocket(
            [
                STATUS,
                ACK,
                tick(time.isoformat()),
                tick((time - timedelta(seconds=1)).isoformat(), "update"),
                tick(time.isoformat(), "update", bid="100.5"),
                tick((time + timedelta(seconds=1)).isoformat(), "update"),
            ]
        )
        source = provider(FixtureConnector([socket]))
        async with aclosing(source.stream_quotes(INSTRUMENT)) as stream:
            first = await anext(stream)
            second = await anext(stream)
            assert second.exchange_at > first.exchange_at
            assert source.states[INSTRUMENT].out_of_order == 2
            assert source.states[INSTRUMENT].quotes == 2
            assert (await source.provider_health()).status is HealthStatus.DEGRADED

    asyncio.run(run())


def test_heartbeat_and_matching_ping_pong_are_not_ticks() -> None:
    async def run() -> None:
        socket = FixtureSocket(
            [
                STATUS,
                ACK,
                json.dumps({"channel": "heartbeat"}),
                tick((utc_now() - timedelta(seconds=1)).isoformat()),
            ],
            pong=True,
        )
        source = provider(
            FixtureConnector([socket]),
            heartbeat_timeout=0.01,
            ping_interval=0.01,
            pong_timeout=0.02,
        )
        async with aclosing(source.stream_quotes(INSTRUMENT)) as stream:
            await anext(stream)
            pending = asyncio.create_task(anext(stream))
            await asyncio.sleep(0.06)
            assert source.states[INSTRUMENT].quotes == 1
            assert source.states[INSTRUMENT].heartbeats == 1
            assert source.states[INSTRUMENT].pongs >= 1
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
        assert socket.closed

    asyncio.run(run())


def test_missing_pong_and_disconnect_reconnect_budget_are_bounded() -> None:
    async def run() -> None:
        socket = FixtureSocket([STATUS, ACK])
        connector = FixtureConnector([socket])
        source = provider(
            connector,
            reconnects=1,
            heartbeat_timeout=0.01,
            pong_timeout=0.01,
            subscribe_timeout=0.1,
        )
        with pytest.raises(ProviderError) as caught:
            await anext(source.stream_quotes(INSTRUMENT))
        assert caught.value.code is ProviderCode.UNAVAILABLE
        assert connector.calls == 2 and source.states[INSTRUMENT].quotes == 0
        assert socket.closed

    asyncio.run(run())


@pytest.mark.parametrize(
    "raw", ['{"bid":1,"bid":2}', '{"channel":"ticker","data":[NaN]}', "not JSON", "[]", b"{}"]
)
def test_malformed_duplicate_nonfinite_or_binary_frame_rejected(raw: str | bytes) -> None:
    with pytest.raises(ProviderError) as caught:
        decode_frame(raw)
    assert caught.value.code is ProviderCode.INVALID_DATA


def test_wrong_symbol_and_future_time_do_not_get_rebased() -> None:
    now = utc_now()
    for raw in [
        tick(now.isoformat(), symbol="ETH/EUR"),
        tick((now + timedelta(minutes=1)).isoformat()),
    ]:
        with pytest.raises(ProviderError) as caught:
            ticker_quote(decode_frame(raw), "BTC/EUR", INSTRUMENT, now)
        assert caught.value.code is ProviderCode.INVALID_DATA


def test_update_before_snapshot_bad_ack_and_invalid_data_are_permanent() -> None:
    async def run() -> None:
        stamp = (utc_now() - timedelta(seconds=1)).isoformat()
        cases = [
            [STATUS, ACK, tick(stamp, "update")],
            [STATUS, json.dumps({"method": "subscribe", "success": False, "req_id": 1})],
            [STATUS, ACK, tick(stamp, bid="NaN")],
        ]
        for frames in cases:
            socket = FixtureSocket(frames)
            connector = FixtureConnector([socket])
            source = provider(connector)
            with pytest.raises(ProviderError):
                await anext(source.stream_quotes(INSTRUMENT))
            assert connector.calls == 1 and socket.closed and source.states[INSTRUMENT].quotes == 0

    asyncio.run(run())


def test_cancel_does_not_reconnect_or_hold_active_lock() -> None:
    async def run() -> None:
        socket = FixtureSocket([STATUS, ACK])
        connector = FixtureConnector([socket])
        source = provider(connector)
        task = asyncio.create_task(anext(source.stream_quotes(INSTRUMENT)))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert connector.calls == 1 and socket.closed
        assert not source.locks[INSTRUMENT].locked() and not source.states[INSTRUMENT].active

    asyncio.run(run())


def test_heartbeats_do_not_hide_missing_pong_deadline() -> None:
    async def run() -> None:
        socket = FixtureSocket([STATUS, ACK, tick((utc_now() - timedelta(seconds=1)).isoformat())])
        source = provider(
            FixtureConnector([socket]),
            reconnects=0,
            heartbeat_timeout=0.1,
            ping_interval=0.01,
            pong_timeout=0.02,
        )

        async def heartbeats() -> None:
            while True:
                await asyncio.sleep(0.002)
                socket.frames.put_nowait(json.dumps({"channel": "heartbeat"}))

        async with aclosing(source.stream_quotes(INSTRUMENT)) as stream:
            await anext(stream)
            producer = asyncio.create_task(heartbeats())
            try:
                with pytest.raises(ProviderError) as caught:
                    await anext(stream)
                assert caught.value.code is ProviderCode.UNAVAILABLE
            finally:
                producer.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await producer
        assert socket.closed and source.states[INSTRUMENT].quotes == 1

    asyncio.run(run())
