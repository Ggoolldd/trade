"""Bounded asynchronous read execution, shared rate gate and cancellable streams."""

import asyncio
import logging
import re
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.domain_types import require_utc, utc_now
from app.market_data import (
    BarPage,
    MarketDataProvider,
    MarketQuote,
    ProviderCode,
    ProviderError,
    ProviderHealth,
)

logger = logging.getLogger(__name__)


class ReadPolicy(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )
    attempt_timeout: float = Field(default=5.0, gt=0, le=30)
    total_timeout: float = Field(default=20.0, gt=0, le=120)
    stream_idle_timeout: float = Field(default=60.0, gt=0, le=300)
    close_timeout: float = Field(default=1.0, gt=0, le=30)
    attempts: int = Field(default=3, ge=1, le=5)
    concurrency: int = Field(default=4, ge=1, le=32)
    min_spacing: float = Field(default=0.2, ge=0, le=60)
    base_backoff: float = Field(default=0.25, gt=0, le=5)
    max_backoff: float = Field(default=2.0, gt=0, le=30)

    @model_validator(mode="after")
    def consistent_backoff(self) -> "ReadPolicy":
        if self.base_backoff > self.max_backoff:
            raise ValueError("base backoff exceeds retry cap")
        return self


class RateGate:
    def __init__(
        self,
        spacing: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not 0 <= spacing <= 60:
            raise ValueError("invalid minimum request spacing")
        self.spacing = spacing
        self.clock = clock
        self.sleep = sleep
        self.next_start = self.clock()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self.lock:
                now = self.clock()
                delay = self.next_start - now
                if delay <= 0:
                    self.next_start = now + self.spacing
                    return
            # Do not hold lock while sleeping: a new 429 can extend shared cooldown.
            await self.sleep(delay)

    async def defer(self, seconds: float) -> None:
        async with self.lock:
            self.next_start = max(self.next_start, self.clock() + seconds)


class MarketDataClient:
    def __init__(self, provider: MarketDataProvider, policy: ReadPolicy | None = None) -> None:
        self.provider = provider
        identifier = provider.provider_id
        if (
            not isinstance(identifier, str)
            or re.fullmatch(r"[A-Z][A-Z0-9_]{0,39}", identifier) is None
        ):
            raise ValueError("valid stable provider identity required")
        self.provider_id = identifier
        self.policy = ReadPolicy.model_validate(policy) if policy is not None else ReadPolicy()
        self.rate_gate = RateGate(self.policy.min_spacing)
        self.slots = asyncio.Semaphore(self.policy.concurrency)

    async def _read[T](self, call: Callable[[], Awaitable[T]]) -> T:
        try:
            async with asyncio.timeout(self.policy.total_timeout):
                for attempt in range(self.policy.attempts):
                    try:
                        async with self.slots:
                            await self.rate_gate.acquire()
                            async with asyncio.timeout(self.policy.attempt_timeout):
                                return await call()
                    except TimeoutError:
                        error = ProviderError(ProviderCode.TIMEOUT)
                    except ProviderError as exc:
                        try:
                            error = ProviderError(exc.code, retry_after=exc.retry_after)
                        except ValueError:
                            raise ProviderError(ProviderCode.ADAPTER_ERROR) from None
                    except ValidationError:
                        raise ProviderError(ProviderCode.INVALID_DATA) from None
                    except Exception:
                        raise ProviderError(ProviderCode.ADAPTER_ERROR) from None
                    retryable = error.code in {
                        ProviderCode.TIMEOUT,
                        ProviderCode.UNAVAILABLE,
                        ProviderCode.RATE_LIMITED,
                    }
                    delay = min(self.policy.base_backoff * 2**attempt, self.policy.max_backoff)
                    if error.code is ProviderCode.RATE_LIMITED:
                        delay = max(delay, error.retry_after or 0.0)
                        await self.rate_gate.defer(delay)
                    if (
                        not retryable
                        or attempt + 1 == self.policy.attempts
                        or delay > self.policy.max_backoff
                    ):
                        raise error from None
                    await asyncio.sleep(delay)
        except TimeoutError:
            raise ProviderError(ProviderCode.TIMEOUT) from None
        raise ProviderError(ProviderCode.ADAPTER_ERROR)

    def _quote(self, raw: object, instrument_id: UUID) -> MarketQuote:
        try:
            quote = MarketQuote.model_validate(raw)
            if quote.instrument_id != instrument_id or quote.provider != self.provider_id:
                raise ValueError("quote identity mismatch")
            return quote
        except (ValidationError, ValueError):
            raise ProviderError(ProviderCode.INVALID_DATA) from None

    async def fetch_quote(self, instrument_id: UUID) -> MarketQuote:
        if not isinstance(instrument_id, UUID):
            raise ProviderError(ProviderCode.INVALID_DATA)
        return self._quote(
            await self._read(lambda: self.provider.fetch_quote(instrument_id)), instrument_id
        )

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
        try:
            start, end = require_utc(start), require_utc(end)
            if (
                not isinstance(instrument_id, UUID)
                or not start < end <= utc_now()
                or end - start > timedelta(days=366)
                or type(interval_seconds) is not int
                or not 1 <= interval_seconds <= 86400
                or type(limit) is not int
                or not 1 <= limit <= 5000
                or cursor is not None
                and (not isinstance(cursor, str) or len(cursor) > 128)
            ):
                raise ValueError("invalid bar request")
        except (ValueError, TypeError):
            raise ProviderError(ProviderCode.INVALID_DATA) from None
        raw = await self._read(
            lambda: self.provider.fetch_bars(
                instrument_id, start, end, interval_seconds, cursor=cursor, limit=limit
            )
        )
        try:
            page = BarPage.model_validate(raw)
            if len(page.bars) > limit:
                raise ValueError("page exceeds requested limit")
            previous = start
            for bar in page.bars:
                if (
                    bar.instrument_id != instrument_id
                    or bar.provider != self.provider_id
                    or bar.interval_seconds != interval_seconds
                    or not previous <= bar.opened_at < bar.closed_at <= end
                ):
                    raise ValueError("bar outside identity/interval/window or overlapping")
                previous = bar.closed_at
            if (
                page.coverage_complete
                and page.retention_start is not None
                and page.retention_start > start
            ):
                raise ValueError("retention contradicts complete coverage")
            return page
        except (ValidationError, ValueError):
            raise ProviderError(ProviderCode.INVALID_DATA) from None

    async def provider_health(self) -> ProviderHealth:
        raw = await self._read(self.provider.provider_health)
        try:
            health = ProviderHealth.model_validate(raw)
            if health.provider != self.provider_id:
                raise ValueError("health identity mismatch")
            return health
        except (ValidationError, ValueError):
            raise ProviderError(ProviderCode.INVALID_DATA) from None

    async def stream_quotes(self, instrument_id: UUID) -> AsyncGenerator[MarketQuote, None]:
        if not isinstance(instrument_id, UUID):
            raise ProviderError(ProviderCode.INVALID_DATA)
        stream: AsyncGenerator[MarketQuote, None] | None = None
        acquired = False
        try:
            async with asyncio.timeout(self.policy.total_timeout):
                await self.slots.acquire()
                acquired = True
                await self.rate_gate.acquire()
            stream = self.provider.stream_quotes(instrument_id)
            while True:
                try:
                    async with asyncio.timeout(self.policy.stream_idle_timeout):
                        raw = await anext(stream)
                except StopAsyncIteration:
                    return
                yield self._quote(raw, instrument_id)
        except TimeoutError:
            raise ProviderError(ProviderCode.TIMEOUT) from None
        except ProviderError as exc:
            try:
                error = ProviderError(exc.code, retry_after=exc.retry_after)
            except ValueError:
                raise ProviderError(ProviderCode.ADAPTER_ERROR) from None
            if error.code is ProviderCode.RATE_LIMITED:
                await self.rate_gate.defer(error.retry_after or self.policy.base_backoff)
            raise error from None
        except ValidationError:
            raise ProviderError(ProviderCode.INVALID_DATA) from None
        except Exception:
            raise ProviderError(ProviderCode.ADAPTER_ERROR) from None
        finally:
            try:
                if stream is not None:
                    try:
                        async with asyncio.timeout(self.policy.close_timeout):
                            await stream.aclose()
                    except Exception:
                        logger.warning("market_data_stream_close_failed")
            finally:
                if acquired:
                    self.slots.release()
