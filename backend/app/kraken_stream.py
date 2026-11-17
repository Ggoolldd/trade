"""Explicit public ticker stream with liveness, ordering and bounded reconnect."""

import argparse
import asyncio
import json
import logging
import random
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, aclosing, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from app.crypto_catalog import PAIRS, catalog_id
from app.domain_types import financial_decimal, require_utc, utc_now
from app.market_data import (
    BarPage,
    HealthStatus,
    MarketQuote,
    ProviderCode,
    ProviderError,
    ProviderHealth,
)
from app.market_data_client import MarketDataClient, RateGate
from app.settings import load_settings

logger = logging.getLogger(__name__)
PUBLIC_WS = "wss://ws.kraken.com/v2"
MAX_FRAME = 65536


class Socket(Protocol):
    async def send(self, message: str) -> None: ...
    async def recv(self) -> str | bytes: ...
    async def close(self) -> None: ...


class StreamPolicy(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )
    open_timeout: float = Field(default=5.0, gt=0, le=30)
    subscribe_timeout: float = Field(default=5.0, gt=0, le=30)
    heartbeat_timeout: float = Field(default=3.0, gt=0, le=30)
    ping_interval: float = Field(default=15.0, gt=0, le=120)
    pong_timeout: float = Field(default=3.0, gt=0, le=30)
    close_timeout: float = Field(default=1.0, gt=0, le=10)
    max_quote_age: float = Field(default=60.0, gt=0, le=300)
    reconnects: int = Field(default=3, ge=0, le=8)
    base_backoff: float = Field(default=1.0, gt=0, le=10)
    max_backoff: float = Field(default=30.0, gt=0, le=60)


@dataclass
class StreamState:
    active: bool = False
    connected: bool = False
    ready: bool = False
    connections: int = 0
    disconnects: int = 0
    heartbeats: int = 0
    pongs: int = 0
    messages: int = 0
    duplicates: int = 0
    out_of_order: int = 0
    invalid_frames: int = 0
    quotes: int = 0
    last_frame_at: datetime | None = None
    last_quote_at: datetime | None = None
    last_quote: MarketQuote | None = None


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate JSON key")
        result[name] = value
    return result


def invalid_constant(value: str) -> None:
    raise ValueError("nonfinite JSON number")


def decode_frame(raw: str | bytes) -> dict[str, object]:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_FRAME:
        raise ProviderError(ProviderCode.INVALID_DATA)
    try:
        value: object = json.loads(
            raw,
            parse_float=Decimal,
            parse_constant=invalid_constant,
            object_pairs_hook=unique_object,
        )
        if not isinstance(value, dict):
            raise ValueError("object required")
        return value
    except (ValueError, TypeError, RecursionError):
        raise ProviderError(ProviderCode.INVALID_DATA) from None


def wire_money(value: object) -> Decimal:
    if type(value) is int:
        return financial_decimal(Decimal(value))
    if isinstance(value, Decimal):
        return financial_decimal(value)
    raise ValueError("exact JSON number required")


def ticker_quote(
    message: dict[str, object], symbol: str, instrument_id: UUID, observed: datetime
) -> MarketQuote:
    try:
        rows = message.get("data")
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValueError("one subscribed ticker required")
        row = rows[0]
        if row.get("symbol") != symbol or not isinstance(row.get("timestamp"), str):
            raise ValueError("wrong ticker identity/time")
        timestamp = require_utc(datetime.fromisoformat(row["timestamp"]))
        return MarketQuote(
            instrument_id=instrument_id,
            provider="KRAKEN_WS_V2",
            bid=wire_money(row.get("bid")),
            ask=wire_money(row.get("ask")),
            exchange_at=timestamp,
            observed_at=observed,
            usable_at=observed,
        )
    except (ValueError, TypeError, ValidationError):
        raise ProviderError(ProviderCode.INVALID_DATA) from None


class KrakenTickerProvider:
    provider_id = "KRAKEN_WS_V2"

    def __init__(
        self,
        policy: StreamPolicy | None = None,
        *,
        connector: Callable[[], AbstractAsyncContextManager[Socket]] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.policy = StreamPolicy.model_validate(policy) if policy is not None else StreamPolicy()
        self.connector = connector or self._connection
        self.sleep = sleep
        self.connect_gate = RateGate(5.0)
        self.states = {catalog_id(symbol): StreamState() for symbol in PAIRS}
        self.locks = {key: asyncio.Lock() for key in self.states}
        self.blocked = False

    @asynccontextmanager
    async def _connection(self) -> AsyncGenerator[Socket, None]:
        async with connect(
            PUBLIC_WS,
            proxy=None,
            open_timeout=self.policy.open_timeout,
            ping_interval=None,
            close_timeout=self.policy.close_timeout,
            max_size=MAX_FRAME,
            max_queue=4,
            compression=None,
            user_agent_header="TRADING-AI-public-stream",
        ) as socket:
            yield socket

    async def _session(
        self, socket: Socket, instrument_id: UUID, symbol: str, state: StreamState
    ) -> AsyncGenerator[MarketQuote, None]:
        await socket.send(
            json.dumps(
                {
                    "method": "subscribe",
                    "params": {
                        "channel": "ticker",
                        "symbol": [symbol],
                        "event_trigger": "bbo",
                        "snapshot": True,
                    },
                    "req_id": 1,
                }
            )
        )
        started = time.monotonic()
        last_frame = started
        next_ping = started + self.policy.ping_interval
        pending_ping: tuple[int, float] | None = None
        ping_id = 100
        subscribed = False
        snapshot = False
        online = False
        fresh = False
        while True:
            now = time.monotonic()
            if not fresh and now >= started + self.policy.subscribe_timeout:
                raise TimeoutError
            if pending_ping is not None and now >= pending_ping[1]:
                raise TimeoutError
            if pending_ping is None and now >= next_ping:
                await socket.send(json.dumps({"method": "ping", "req_id": ping_id}))
                pending_ping = (ping_id, now + self.policy.pong_timeout)
                ping_id += 1
            deadline = (
                pending_ping[1]
                if pending_ping
                else min(last_frame + self.policy.heartbeat_timeout, next_ping)
            )
            if not fresh:
                deadline = min(deadline, started + self.policy.subscribe_timeout)
            try:
                async with asyncio.timeout(max(0.001, deadline - time.monotonic())):
                    raw = await socket.recv()
            except TimeoutError:
                if pending_ping is not None:
                    raise
                now = time.monotonic()
                await socket.send(json.dumps({"method": "ping", "req_id": ping_id}))
                pending_ping = (ping_id, now + self.policy.pong_timeout)
                ping_id += 1
                continue
            message = decode_frame(raw)
            observed = utc_now()
            state.messages += 1
            channel = message.get("channel")
            method = message.get("method")
            if channel == "heartbeat":
                state.heartbeats += 1
            elif method == "pong":
                if (
                    pending_ping is None
                    or message.get("success") is not True
                    or type(message.get("req_id")) is not int
                    or message["req_id"] != pending_ping[0]
                ):
                    raise ProviderError(ProviderCode.INVALID_DATA)
                pending_ping = None
                next_ping = time.monotonic() + self.policy.ping_interval
                state.pongs += 1
            elif channel == "status":
                data = message.get("data")
                if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
                    raise ProviderError(ProviderCode.INVALID_DATA)
                if data[0].get("system") != "online":
                    raise ProviderError(ProviderCode.UNAVAILABLE)
                online = True
            elif method == "subscribe":
                result = message.get("result")
                if message.get("success") is not True:
                    raise ProviderError(ProviderCode.UNSUPPORTED)
                if (
                    type(message.get("req_id")) is not int
                    or message["req_id"] != 1
                    or not isinstance(result, dict)
                    or result.get("channel") != "ticker"
                    or result.get("symbol") != symbol
                ):
                    raise ProviderError(ProviderCode.INVALID_DATA)
                subscribed = True
            elif channel == "ticker":
                if (
                    not subscribed
                    or not online
                    or message.get("type") not in {"snapshot", "update"}
                ):
                    raise ProviderError(ProviderCode.INVALID_DATA)
                if not snapshot and message["type"] != "snapshot":
                    raise ProviderError(ProviderCode.INVALID_DATA)
                snapshot = True
                quote = ticker_quote(message, symbol, instrument_id, observed)
                previous = state.last_quote
                if previous is not None and quote.exchange_at <= previous.exchange_at:
                    if quote.exchange_at == previous.exchange_at and (quote.bid, quote.ask) == (
                        previous.bid,
                        previous.ask,
                    ):
                        state.duplicates += 1
                    else:
                        state.out_of_order += 1
                        logger.warning("kraken_ws_out_of_order")
                    last_frame = time.monotonic()
                    state.last_frame_at = observed
                    continue
                fresh = True
                state.ready = True
                state.last_quote = quote
                state.last_quote_at = observed
                state.quotes += 1
                last_frame = time.monotonic()
                state.last_frame_at = observed
                yield quote
                continue
            else:
                raise ProviderError(ProviderCode.INVALID_DATA)
            last_frame = time.monotonic()
            state.last_frame_at = observed

    async def stream_quotes(self, instrument_id: UUID) -> AsyncGenerator[MarketQuote, None]:
        symbols = {catalog_id(symbol): symbol for symbol in PAIRS}
        if instrument_id not in symbols:
            raise ProviderError(ProviderCode.UNSUPPORTED)
        if self.blocked:
            raise ProviderError(ProviderCode.RATE_LIMITED, retry_after=86400.0)
        if self.locks[instrument_id].locked():
            raise ProviderError(ProviderCode.UNAVAILABLE)
        state = self.states[instrument_id]
        async with self.locks[instrument_id]:
            state.active = True
            try:
                for attempt in range(self.policy.reconnects + 1):
                    try:
                        await self.connect_gate.acquire()
                        async with self.connector() as socket:
                            state.connected = True
                            state.ready = False
                            state.connections += 1
                            async with aclosing(
                                self._session(socket, instrument_id, symbols[instrument_id], state)
                            ) as source:
                                async for quote in source:
                                    yield quote
                    except InvalidStatus as error:
                        if error.response.status_code in {401, 403}:
                            raise ProviderError(ProviderCode.AUTH_DENIED) from None
                        if error.response.status_code == 429:
                            self.blocked = True
                            raise ProviderError(
                                ProviderCode.RATE_LIMITED, retry_after=86400.0
                            ) from None
                        if error.response.status_code < 500:
                            raise ProviderError(ProviderCode.INVALID_DATA) from None
                        state.disconnects += 1
                    except ProviderError as error:
                        if error.code not in {ProviderCode.UNAVAILABLE, ProviderCode.TIMEOUT}:
                            state.invalid_frames += 1
                            raise
                        state.disconnects += 1
                    except (ConnectionClosed, OSError, TimeoutError):
                        state.disconnects += 1
                    finally:
                        state.connected = False
                        state.ready = False
                    if attempt >= self.policy.reconnects:
                        raise ProviderError(ProviderCode.UNAVAILABLE) from None
                    logger.warning("kraken_ws_disconnected")
                    delay = min(
                        self.policy.max_backoff,
                        self.policy.base_backoff * 2**attempt * random.uniform(0.8, 1.2),
                    )
                    await self.sleep(delay)
            finally:
                state.active = False
                state.connected = False
                state.ready = False

    async def fetch_quote(self, instrument_id: UUID) -> MarketQuote:
        async with aclosing(self.stream_quotes(instrument_id)) as stream:
            return await anext(stream)

    async def fetch_bars(
        self,
        instrument_id: UUID,
        start: datetime,
        end: datetime,
        interval_seconds: int,
        *,
        cursor: str | None = None,
        limit: int = 1000,
    ) -> BarPage:
        raise ProviderError(ProviderCode.UNSUPPORTED)

    async def provider_health(self) -> ProviderHealth:
        active = [state for state in self.states.values() if state.active]
        now = utc_now()
        healthy = all(
            state.connected
            and state.ready
            and state.last_frame_at is not None
            and state.last_quote is not None
            and 0 <= (now - state.last_frame_at).total_seconds() <= self.policy.heartbeat_timeout
            and 0
            <= (now - state.last_quote.exchange_at).total_seconds()
            <= self.policy.max_quote_age
            and state.out_of_order == 0
            for state in active
        )
        status = (
            HealthStatus.UNAVAILABLE
            if not active
            else HealthStatus.HEALTHY
            if healthy
            else HealthStatus.DEGRADED
        )
        return ProviderHealth(provider=self.provider_id, status=status, checked_at=now)


async def sample(symbol: str, count: int, seconds: int) -> None:
    provider = KrakenTickerProvider()
    client = MarketDataClient(provider)
    seen = 0
    async with asyncio.timeout(seconds):
        async with aclosing(client.stream_quotes(catalog_id(symbol))) as stream:
            async for quote in stream:
                seen += 1
                print(
                    f"Public WS tick {seen}: symbol={symbol}, "
                    f"exchange_at={quote.exchange_at.isoformat()}, "
                    f"observed_at={quote.observed_at.isoformat()}; price omitted"
                )
                if seen >= count:
                    break
    state = provider.states[catalog_id(symbol)]
    print(
        f"PASS: actual public WS sample ticks={seen}, connections={state.connections}, "
        f"disconnects={state.disconnects}, duplicate={state.duplicates}, "
        f"out_of_order={state.out_of_order}; stream closed"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", action="store_true", required=True)
    parser.add_argument("--symbol", choices=list(PAIRS), default="BTC/EUR")
    parser.add_argument("--quotes", type=int, default=3)
    parser.add_argument("--seconds", type=int, default=15)
    args = parser.parse_args()
    if not 1 <= args.quotes <= 20 or not 1 <= args.seconds <= 60:
        parser.error("bounded sample requires quotes 1-20 and seconds 1-60")
    load_settings()
    asyncio.run(sample(args.symbol, args.quotes, args.seconds))


if __name__ == "__main__":
    main()
