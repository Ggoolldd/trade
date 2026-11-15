"""Explicit public OHLC reads: bounded history, closed bars, no private endpoint."""

import argparse
import asyncio
import hashlib
import math
import re
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import Self
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.crypto_catalog import PAIRS, catalog_id
from app.domain_types import financial_decimal, require_utc, utc_now
from app.market_data import (
    BarPage,
    DataIssue,
    HealthStatus,
    MarketBar,
    MarketQuote,
    ProviderCode,
    ProviderError,
    ProviderHealth,
)
from app.market_data_client import MarketDataClient, RateGate
from app.settings import load_settings

MAX_RESPONSE = 2_000_000
MAX_ROWS = 721  # Actual public response: up to 720 committed plus current frame.
INTERVALS = {60, 300, 900, 1800, 3600, 14400, 86400}


class PublicResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    error: list[str]
    result: dict[str, object] | None = None


def api_error(errors: list[str]) -> ProviderError:
    for value in errors:
        if value.startswith("EService:") and "Throttled" in value:
            token = value.rsplit(":", 1)[-1].strip()
            if re.fullmatch(r"[0-9]{1,12}", token):
                seconds = max(0.0, int(token) - utc_now().timestamp())
                return ProviderError(
                    ProviderCode.RATE_LIMITED, retry_after=seconds if seconds <= 86400 else 86400.0
                )
            return ProviderError(ProviderCode.RATE_LIMITED, retry_after=86400.0)
    if any(value.startswith("EAPI:Rate limit") for value in errors):
        return ProviderError(ProviderCode.RATE_LIMITED)
    if any(
        value.startswith(
            ("EAPI:Invalid key", "EGeneral:Permission", "EGeneral:Temporary lockout", "EAuth:")
        )
        for value in errors
    ):
        return ProviderError(ProviderCode.AUTH_DENIED)
    if any(value.startswith("EQuery:Unknown asset pair") for value in errors):
        return ProviderError(ProviderCode.UNSUPPORTED)
    if any(
        value.startswith(("EService:Unavailable", "EService:Busy", "EGeneral:Internal error"))
        for value in errors
    ):
        return ProviderError(ProviderCode.UNAVAILABLE)
    return ProviderError(ProviderCode.INVALID_DATA)


def parse_public(raw: bytes) -> dict[str, object]:
    if len(raw) > MAX_RESPONSE:
        raise ProviderError(ProviderCode.INVALID_DATA)
    try:
        body = PublicResponse.model_validate_json(raw)
    except ValidationError:
        raise ProviderError(ProviderCode.INVALID_DATA) from None
    if body.error:
        raise api_error(body.error)
    if body.result is None:
        raise ProviderError(ProviderCode.INVALID_DATA)
    return body.result


def parse_ohlc(
    raw: bytes,
    instrument_id: UUID,
    start: datetime,
    end: datetime,
    interval_seconds: int,
    observed_at: datetime,
    *,
    since: int,
    limit: int,
) -> BarPage:
    symbols = {catalog_id(symbol): symbol for symbol in PAIRS}
    if instrument_id not in symbols or interval_seconds not in INTERVALS:
        raise ProviderError(ProviderCode.UNSUPPORTED)
    try:
        start, end, observed_at = require_utc(start), require_utc(end), require_utc(observed_at)
        if (
            not start < end <= observed_at <= utc_now()
            or type(limit) is not int
            or not 1 <= limit <= 5000
            or type(since) is not int
            or since < 0
        ):
            raise ValueError("invalid window")
        result = parse_public(raw)
        key = PAIRS[symbols[instrument_id]][0]
        if set(result) != {key, "last"}:
            raise ValueError("unexpected pair identity")
        native = result["last"]
        rows = result[key]
        if (
            type(native) is not int
            or native < 0
            or native > 253402300799
            or not isinstance(rows, list)
            or not 1 <= len(rows) <= MAX_ROWS
        ):
            raise ValueError("invalid bounded response")
        decoded: list[tuple[datetime, tuple[Decimal, ...]]] = []
        previous = -1
        for row in rows:
            if (
                not isinstance(row, list)
                or len(row) != 8
                or type(row[0]) is not int
                or row[0] <= previous
                or row[0] % interval_seconds
                or type(row[7]) is not int
                or row[7] < 0
            ):
                raise ValueError("invalid/duplicate/unsorted candle")
            if any(not isinstance(value, str) for value in row[1:7]):
                raise ValueError("API monetary strings required")
            raw_prices = tuple(str(value) for value in row[1:7])
            values = [financial_decimal(value) for value in raw_prices]
            if (
                min(values[:4]) <= 0
                or values[4] < 0
                or values[5] < 0
                or not values[2]
                <= min(values[0], values[3])
                <= max(values[0], values[3])
                <= values[1]
            ):
                raise ValueError("invalid OHLCV")
            previous = row[0]
            decoded.append((datetime.fromtimestamp(row[0], UTC), tuple(values)))
        issues = {DataIssue.UNCOMMITTED_DROPPED}
        retention = decoded[0][0] if len(decoded) >= 720 else None
        if retention is not None and retention > start:
            issues.add(DataIssue.RETENTION_GAP)
        # Drop last row regardless of wall clock: API defines it as uncommitted.
        committed = decoded[:-1]
        if (
            any(
                opened + timedelta(seconds=interval_seconds) > observed_at
                for opened, _ in committed
            )
            or any(opened > observed_at for opened, _ in decoded)
            or native > int(observed_at.timestamp())
        ):
            issues.add(DataIssue.PROVIDER_TIME_AHEAD)
        selected = []
        for opened, prices in committed:
            closed = opened + timedelta(seconds=interval_seconds)
            if (
                opened < start
                or int(opened.timestamp()) < since
                or closed > end
                or closed > observed_at
            ):
                continue
            selected.append(
                MarketBar(
                    instrument_id=instrument_id,
                    provider="KRAKEN_PUBLIC",
                    interval_seconds=interval_seconds,
                    opened_at=opened,
                    closed_at=closed,
                    observed_at=observed_at,
                    usable_at=observed_at,
                    open=prices[0],
                    high=prices[1],
                    low=prices[2],
                    close=prices[3],
                    volume=prices[5],
                )
            )
        # Only interval-aligned completed candles wholly inside the requested window.
        first = math.ceil(start.timestamp() / interval_seconds) * interval_seconds
        last = math.floor(end.timestamp() / interval_seconds) * interval_seconds
        expected = max(0, (last - first) // interval_seconds)
        if len(selected) != expected:
            issues.add(DataIssue.MISSING_BARS)
        if len(selected) > limit:
            issues.add(DataIssue.PAGE_LIMIT)
        page = tuple(selected[:limit])
        next_cursor = str(int(page[-1].closed_at.timestamp())) if page else None
        complete = not issues.intersection(
            {
                DataIssue.PROVIDER_TIME_AHEAD,
                DataIssue.RETENTION_GAP,
                DataIssue.MISSING_BARS,
                DataIssue.PAGE_LIMIT,
            }
        )
        return BarPage(
            bars=page,
            next_cursor=next_cursor,
            retention_start=retention,
            coverage_complete=complete,
            provider_cursor=str(native),
            source_sha256=hashlib.sha256(raw).hexdigest(),
            issues=tuple(sorted(issues)),
        )
    except (ValueError, TypeError, OverflowError, OSError):
        raise ProviderError(ProviderCode.INVALID_DATA) from None


class KrakenPublicProvider:
    provider_id = "KRAKEN_PUBLIC"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.http = httpx.AsyncClient(
            base_url="https://api.kraken.com",
            transport=transport,
            timeout=5.0,
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "TRADING-AI-public-data"},
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
        )
        self.blocked_throttle = False
        self.rate_gate = RateGate(1.0)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.http.aclose()

    def _retry_after(self, header: str | None) -> float | None:
        if header is None:
            return None
        try:
            if len(header) > 128:
                raise ValueError
            try:
                seconds = float(header)
            except ValueError:
                seconds = max(
                    0.0, (require_utc(parsedate_to_datetime(header)) - utc_now()).total_seconds()
                )
            if not math.isfinite(seconds) or not 0 <= seconds <= 86400:
                raise ValueError
            return seconds
        except (ValueError, TypeError, OverflowError):
            # Cannot safely interpret a throttle: freeze this instance, never retry early.
            self.blocked_throttle = True
            return 86400.0

    async def _request(
        self, endpoint: str, params: dict[str, str] | None = None
    ) -> tuple[bytes, datetime]:
        if endpoint not in {"OHLC", "SystemStatus"}:
            raise ProviderError(ProviderCode.UNSUPPORTED)
        if self.blocked_throttle:
            raise ProviderError(ProviderCode.RATE_LIMITED, retry_after=86400.0)
        await self.rate_gate.acquire()
        try:
            async with self.http.stream("GET", "/0/public/" + endpoint, params=params) as response:
                status = response.status_code
                if status == 429:
                    delay = self._retry_after(response.headers.get("Retry-After"))
                    await self.rate_gate.defer(max(1.0, delay or 1.0))
                    raise ProviderError(ProviderCode.RATE_LIMITED, retry_after=delay)
                if status in {401, 403}:
                    raise ProviderError(ProviderCode.AUTH_DENIED)
                if status >= 500:
                    raise ProviderError(ProviderCode.UNAVAILABLE)
                if status != 200:
                    raise ProviderError(ProviderCode.INVALID_DATA)
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > MAX_RESPONSE:
                        raise ProviderError(ProviderCode.INVALID_DATA)
                    body.extend(chunk)
                raw = bytes(body)
                try:
                    parse_public(raw)
                except ProviderError as error:
                    if error.code is ProviderCode.RATE_LIMITED:
                        await self.rate_gate.defer(max(1.0, error.retry_after or 1.0))
                        if error.retry_after == 86400.0:
                            self.blocked_throttle = True
                    raise
                return raw, utc_now()
        except httpx.TimeoutException:
            raise ProviderError(ProviderCode.TIMEOUT) from None
        except httpx.TransportError:
            raise ProviderError(ProviderCode.UNAVAILABLE) from None

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
        symbols = {catalog_id(symbol): symbol for symbol in PAIRS}
        if (
            instrument_id not in symbols
            or type(interval_seconds) is not int
            or interval_seconds not in INTERVALS
        ):
            raise ProviderError(ProviderCode.UNSUPPORTED)
        try:
            start, end = require_utc(start), require_utc(end)
            if (
                not start < end <= utc_now()
                or end - start > timedelta(days=366)
                or type(limit) is not int
                or not 1 <= limit <= 5000
            ):
                raise ValueError
            if cursor is not None and (
                not isinstance(cursor, str) or re.fullmatch(r"[0-9]{1,12}", cursor) is None
            ):
                raise ValueError
            since = int(cursor) if cursor is not None else int(start.timestamp())
            if since < 0 or since > int(end.timestamp()):
                raise ValueError
        except (ValueError, TypeError):
            raise ProviderError(ProviderCode.INVALID_DATA) from None
        pair = PAIRS[symbols[instrument_id]][1]
        raw, observed = await self._request(
            "OHLC", {"pair": pair, "interval": str(interval_seconds // 60), "since": str(since)}
        )
        return parse_ohlc(
            raw, instrument_id, start, end, interval_seconds, observed, since=since, limit=limit
        )

    async def fetch_quote(self, instrument_id: UUID) -> MarketQuote:
        raise ProviderError(ProviderCode.UNSUPPORTED)

    def stream_quotes(self, instrument_id: UUID) -> AsyncGenerator[MarketQuote, None]:
        raise ProviderError(ProviderCode.UNSUPPORTED)

    async def provider_health(self) -> ProviderHealth:
        raw, observed = await self._request("SystemStatus")
        result = parse_public(raw)
        status = result.get("status")
        if not isinstance(status, str) or status not in {
            "online",
            "maintenance",
            "cancel_only",
            "post_only",
        }:
            raise ProviderError(ProviderCode.INVALID_DATA)
        return ProviderHealth(
            provider=self.provider_id,
            status=HealthStatus.HEALTHY if status == "online" else HealthStatus.DEGRADED,
            checked_at=observed,
        )


async def sample(symbol: str, minutes: int) -> None:
    end = utc_now() - timedelta(minutes=5)
    start = end - timedelta(minutes=minutes)
    async with KrakenPublicProvider() as provider:
        page = await MarketDataClient(provider).fetch_bars(catalog_id(symbol), start, end, 60)
    print(
        f"Public closed OHLC sample: pair={symbol}, bars={len(page.bars)}, "
        f"complete={page.coverage_complete}, checkpoint={page.next_cursor}, "
        f"native={page.provider_cursor}, issues={[item.value for item in page.issues]}, "
        f"source_sha256={page.source_sha256}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", action="store_true", required=True)
    parser.add_argument("--symbol", choices=list(PAIRS), default="BTC/EUR")
    parser.add_argument("--minutes", type=int, choices=range(1, 721), default=60)
    args = parser.parse_args()
    load_settings()  # PAPER-only config validation before any network request.
    asyncio.run(sample(args.symbol, args.minutes))


if __name__ == "__main__":
    main()
