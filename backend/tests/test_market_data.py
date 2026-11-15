"""Fixture-only provider contract tests; never evidence of a real market feed."""

import asyncio
import time
from collections.abc import AsyncGenerator
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.domain_types import utc_now
from app.market_data import (
    BarPage,
    HealthStatus,
    MarketBar,
    MarketQuote,
    ProviderCode,
    ProviderError,
    ProviderHealth,
)
from app.market_data_client import MarketDataClient, RateGate, ReadPolicy


class FixtureProvider:
    provider_id = "FIXTURE"

    def __init__(self) -> None:
        self.instrument = uuid4()
        self.start = utc_now() - timedelta(days=1)
        self.end = self.start + timedelta(minutes=1)
        self.quote = MarketQuote(
            instrument_id=self.instrument,
            provider="FIXTURE",
            bid="100.10",
            ask="100.20",
            exchange_at=self.start,
            observed_at=self.end,
            usable_at=self.end,
        )
        self.bar = MarketBar(
            instrument_id=self.instrument,
            provider="FIXTURE",
            interval_seconds=60,
            opened_at=self.start,
            closed_at=self.end,
            observed_at=self.end,
            usable_at=self.end,
            open="100",
            high="102",
            low="99",
            close="101",
            volume="2.5",
        )
        self.page = BarPage(
            bars=(self.bar,), next_cursor="fixture-next", retention_start=self.start
        )
        self.errors: list[Exception] = []
        self.calls = 0
        self.slow = False
        self.slow_stream = False
        self.closed = False
        self.stream_calls = 0
        self.started = asyncio.Event()

    async def fetch_quote(self, instrument_id: UUID) -> MarketQuote:
        self.calls += 1
        self.started.set()
        if self.errors:
            raise self.errors.pop(0)
        if self.slow:
            await asyncio.sleep(10)
        return self.quote

    async def fetch_bars(
        self,
        instrument_id: UUID,
        start: object,
        end: object,
        interval_seconds: int,
        *,
        cursor: str | None = None,
        limit: int = 1000,
    ) -> BarPage:
        return self.page

    async def provider_health(self) -> ProviderHealth:
        return ProviderHealth(
            provider="FIXTURE", status=HealthStatus.DEGRADED, checked_at=utc_now()
        )

    async def stream_quotes(self, instrument_id: UUID) -> AsyncGenerator[MarketQuote, None]:
        self.stream_calls += 1
        try:
            self.started.set()
            if self.slow_stream:
                await asyncio.sleep(10)
            yield self.quote
        finally:
            self.closed = True


def policy(**values: object) -> ReadPolicy:
    return ReadPolicy.model_validate(
        dict(min_spacing=0.0, base_backoff=0.001, max_backoff=0.01, **values)
    )


def test_fixture_provider_full_contract_and_cleanup() -> None:
    async def run() -> None:
        provider = FixtureProvider()
        client = MarketDataClient(provider, policy())
        quote = await client.fetch_quote(provider.instrument)
        assert quote.bid == Decimal("100.10")
        assert quote.model_dump(mode="json")["bid"] == "100.10"
        page = await client.fetch_bars(provider.instrument, provider.start, provider.end, 60)
        assert page.bars == (provider.bar,) and not page.coverage_complete
        assert (await client.provider_health()).status is HealthStatus.DEGRADED
        assert [item async for item in client.stream_quotes(provider.instrument)] == [quote]
        assert provider.closed and provider.stream_calls == 1

    asyncio.run(run())


@pytest.mark.parametrize(
    "code",
    [
        ProviderCode.AUTH_DENIED,
        ProviderCode.INVALID_DATA,
        ProviderCode.UNSUPPORTED,
        ProviderCode.ADAPTER_ERROR,
    ],
)
def test_permanent_errors_never_retry(code: ProviderCode) -> None:
    async def run() -> None:
        provider = FixtureProvider()
        provider.errors = [ProviderError(code)]
        with pytest.raises(ProviderError) as caught:
            await MarketDataClient(provider, policy()).fetch_quote(provider.instrument)
        assert caught.value.code is code and provider.calls == 1

    asyncio.run(run())


def test_transient_retry_bounded_and_unexpected_text_sanitized() -> None:
    async def run() -> None:
        provider = FixtureProvider()
        provider.errors = [ProviderError(ProviderCode.UNAVAILABLE)] * 2
        assert (
            await MarketDataClient(provider, policy()).fetch_quote(provider.instrument)
            == provider.quote
        )
        assert provider.calls == 3
        provider = FixtureProvider()
        provider.errors = [RuntimeError("SENSITIVE-REMOTE-TEXT")]
        with pytest.raises(ProviderError) as caught:
            await MarketDataClient(provider, policy()).fetch_quote(provider.instrument)
        assert caught.value.code is ProviderCode.ADAPTER_ERROR
        assert "SENSITIVE" not in str(caught.value) and provider.calls == 1

    asyncio.run(run())


def test_attempt_timeout_total_deadline_and_retry_cap() -> None:
    async def run() -> None:
        provider = FixtureProvider()
        provider.slow = True
        client = MarketDataClient(provider, policy(attempt_timeout=0.01, total_timeout=0.5))
        with pytest.raises(ProviderError) as caught:
            await client.fetch_quote(provider.instrument)
        assert caught.value.code is ProviderCode.TIMEOUT and provider.calls == 3
        provider = FixtureProvider()
        provider.slow = True
        with pytest.raises(ProviderError):
            await MarketDataClient(
                provider, policy(attempt_timeout=1.0, total_timeout=0.02)
            ).fetch_quote(provider.instrument)
        assert provider.calls == 1

    asyncio.run(run())


def test_rate_limit_is_shared_and_long_retry_after_not_clamped() -> None:
    async def run() -> None:
        provider = FixtureProvider()
        provider.errors = [ProviderError(ProviderCode.RATE_LIMITED, retry_after=1.0)]
        client = MarketDataClient(provider, policy(total_timeout=0.02))
        with pytest.raises(ProviderError) as caught:
            await client.fetch_quote(provider.instrument)
        assert caught.value.code is ProviderCode.RATE_LIMITED and provider.calls == 1
        assert client.rate_gate.next_start > time.monotonic()
        with pytest.raises(ProviderError) as caught:
            await client.fetch_quote(provider.instrument)
        assert caught.value.code is ProviderCode.TIMEOUT and provider.calls == 1

    asyncio.run(run())


def test_rate_gate_spacing_and_extended_cooldown_virtual_clock() -> None:
    async def run() -> None:
        clock = [0.0]
        waits = []

        async def sleep(seconds: float) -> None:
            waits.append(seconds)
            clock[0] += seconds
            await asyncio.sleep(0)

        gate = RateGate(0.25, clock=lambda: clock[0], sleep=sleep)
        await gate.acquire()
        await gate.acquire()
        await gate.defer(3.0)
        await gate.acquire()
        assert waits == [0.25, 3.0] and clock[0] == 3.25

    asyncio.run(run())


@pytest.mark.parametrize(
    "change",
    [
        {"bid": Decimal("1000")},
        {"instrument_id": uuid4()},
        {"provider": "OTHER"},
        {"usable_at": utc_now() + timedelta(days=1)},
    ],
)
def test_bypassed_model_validation_rechecked_at_client_boundary(change: dict[str, object]) -> None:
    async def run() -> None:
        provider = FixtureProvider()
        provider.quote = provider.quote.model_copy(update=change)
        with pytest.raises(ProviderError) as caught:
            await MarketDataClient(provider, policy()).fetch_quote(provider.instrument)
        assert caught.value.code is ProviderCode.INVALID_DATA and provider.calls == 1

    asyncio.run(run())


def test_bar_identity_overlap_window_and_retention_claim_rejected() -> None:
    async def run() -> None:
        provider = FixtureProvider()
        client = MarketDataClient(provider, policy())
        invalid = [
            BarPage(bars=(provider.bar.model_copy(update={"instrument_id": uuid4()}),)),
            BarPage(bars=(provider.bar, provider.bar)),
            BarPage(bars=(provider.bar,), coverage_complete=True, retention_start=provider.end),
        ]
        for page in invalid:
            provider.page = page
            with pytest.raises(ProviderError) as caught:
                await client.fetch_bars(provider.instrument, provider.start, provider.end, 60)
            assert caught.value.code is ProviderCode.INVALID_DATA
        with pytest.raises(ProviderError):
            await client.fetch_bars(
                provider.instrument, provider.start.replace(tzinfo=None), provider.end, 60
            )

    asyncio.run(run())


def test_stream_idle_cancel_and_queued_request_deadline_release_resources() -> None:
    async def run() -> None:
        provider = FixtureProvider()
        client = MarketDataClient(
            provider, policy(concurrency=1, total_timeout=0.03, stream_idle_timeout=0.02)
        )
        stream = client.stream_quotes(provider.instrument)
        assert await anext(stream) == provider.quote
        with pytest.raises(ProviderError) as caught:
            await client.fetch_quote(provider.instrument)
        assert caught.value.code is ProviderCode.TIMEOUT and provider.calls == 0
        await stream.aclose()
        assert provider.closed
        assert await client.fetch_quote(provider.instrument) == provider.quote
        provider = FixtureProvider()
        provider.slow_stream = True
        client = MarketDataClient(provider, policy(stream_idle_timeout=0.02))
        with pytest.raises(ProviderError) as caught:
            await anext(client.stream_quotes(provider.instrument))
        assert (
            caught.value.code is ProviderCode.TIMEOUT
            and provider.closed
            and provider.stream_calls == 1
        )
        provider = FixtureProvider()
        provider.slow_stream = True
        client = MarketDataClient(provider, policy())
        task = asyncio.create_task(anext(client.stream_quotes(provider.instrument)))
        await provider.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert provider.closed and provider.stream_calls == 1

    asyncio.run(run())


@pytest.mark.parametrize(
    "change", [{"bid": 0.1}, {"ask": "0"}, {"observed_at": utc_now().replace(tzinfo=None)}]
)
def test_quote_financial_and_time_inputs_fail_closed(change: dict[str, object]) -> None:
    provider = FixtureProvider()
    with pytest.raises(ValidationError):
        MarketQuote.model_validate(dict(provider.quote.model_dump(), **change))


@pytest.mark.parametrize(
    "change",
    [
        {"attempts": 0},
        {"concurrency": 0},
        {"total_timeout": float("nan")},
        {"attempt_timeout": -1.0},
    ],
)
def test_invalid_policy_rejected(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ReadPolicy.model_validate(change)


def test_copied_invalid_policy_cannot_bypass_client_validation() -> None:
    invalid = ReadPolicy().model_copy(update={"total_timeout": float("inf")})
    with pytest.raises(ValidationError):
        MarketDataClient(FixtureProvider(), invalid)
