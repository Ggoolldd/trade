"""Synthetic HTTP fixtures; real public smoke is recorded separately, without prices."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from uuid import uuid4

import httpx
import pytest

from app.crypto_catalog import catalog_id
from app.domain_types import utc_now
from app.kraken_ohlc import MAX_RESPONSE, KrakenPublicProvider, parse_ohlc
from app.market_data import DataIssue, HealthStatus, ProviderCode, ProviderError
from app.market_data_client import MarketDataClient, RateGate, ReadPolicy

BASE = datetime(2026, 1, 10, tzinfo=UTC)
INSTRUMENT = catalog_id("BTC/EUR")


def body(count: int = 10) -> dict[str, object]:
    rows = [
        [int(BASE.timestamp()) + 60 * index, "100.0", "102.0", "99.0", "101.0", "100.5", "2.0", 3]
        for index in range(count)
    ]
    return {
        "error": [],
        "result": {"XXBTZEUR": rows, "last": int(BASE.timestamp()) + 60 * (count - 1)},
    }


def encoded(count: int = 10) -> bytes:
    return json.dumps(body(count)).encode()


def parsed(
    raw: bytes,
    *,
    start: datetime = BASE,
    end: datetime = BASE + timedelta(minutes=5),
    observed: datetime = BASE + timedelta(days=1),
    limit: int = 1000,
    since: int | None = None,
):
    return parse_ohlc(
        raw,
        INSTRUMENT,
        start,
        end,
        60,
        observed,
        since=int(start.timestamp()) if since is None else since,
        limit=limit,
    )


def test_exact_closed_sample_and_native_vs_bounded_checkpoint() -> None:
    raw = encoded()
    page = parsed(raw)
    assert len(page.bars) == 5 and page.coverage_complete
    assert page.bars[0].model_dump(mode="json")["open"] == "100.0"
    assert page.next_cursor == str(int((BASE + timedelta(minutes=5)).timestamp()))
    assert page.provider_cursor == str(int((BASE + timedelta(minutes=9)).timestamp()))
    assert page.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert page.issues == (DataIssue.UNCOMMITTED_DROPPED,)


def test_last_row_never_promoted_to_committed_by_later_wall_clock() -> None:
    page = parsed(encoded(1))
    assert not page.bars and not page.coverage_complete and page.next_cursor is None
    assert DataIssue.MISSING_BARS in page.issues


def test_720_committed_plus_current_retention_and_no_old_history_claim() -> None:
    page = parsed(encoded(721), start=BASE - timedelta(days=1), end=BASE + timedelta(hours=12))
    assert len(page.bars) == 720
    assert page.retention_start == BASE and not page.coverage_complete
    assert DataIssue.RETENTION_GAP in page.issues
    with pytest.raises(ProviderError):
        parsed(encoded(722))


def test_future_provider_rows_never_usable_and_partial_status_explicit() -> None:
    observed = BASE + timedelta(minutes=7, seconds=30)
    page = parsed(encoded(), end=BASE + timedelta(minutes=7), observed=observed)
    assert len(page.bars) == 7 and not page.coverage_complete
    assert DataIssue.PROVIDER_TIME_AHEAD in page.issues
    assert all(bar.closed_at <= bar.usable_at <= observed for bar in page.bars)


def test_page_limit_checkpoint_advances_without_duplicates() -> None:
    first = parsed(encoded(), limit=2)
    second = parsed(encoded(), limit=2, since=int(first.next_cursor))
    assert DataIssue.PAGE_LIMIT in first.issues and not first.coverage_complete
    assert first.bars[-1].closed_at == second.bars[0].opened_at
    assert set(bar.opened_at for bar in first.bars).isdisjoint(bar.opened_at for bar in second.bars)
    assert int(second.next_cursor) > int(first.next_cursor)


@pytest.mark.parametrize(
    "field,value",
    [(0, True), (0, 1.5), (1, 100.0), (1, "NaN"), (1, "0"), (2, "90"), (6, "-1"), (7, True)],
)
def test_bad_candle_types_and_invariants_rejected(field: int, value: object) -> None:
    payload = body()
    payload["result"]["XXBTZEUR"][0][field] = value
    with pytest.raises(ProviderError) as caught:
        parsed(json.dumps(payload).encode())
    assert caught.value.code is ProviderCode.INVALID_DATA


def test_wrong_pair_unsorted_duplicate_missing_and_invalid_json_rejected() -> None:
    payload = body()
    payload["result"]["XXBTZEUR"][1][0] = payload["result"]["XXBTZEUR"][0][0]
    for raw in [
        json.dumps(payload).encode(),
        b"not JSON",
        b" " * (MAX_RESPONSE + 1),
        b'{"error":[],"result":{}}',
    ]:
        with pytest.raises(ProviderError):
            parsed(raw)
    payload = body()
    payload["result"]["XETHZEUR"] = payload["result"].pop("XXBTZEUR")
    with pytest.raises(ProviderError):
        parsed(json.dumps(payload).encode())


@pytest.mark.parametrize(
    "message,code",
    [
        ("EQuery:Unknown asset pair", ProviderCode.UNSUPPORTED),
        ("EAPI:Rate limit exceeded", ProviderCode.RATE_LIMITED),
        ("EGeneral:Permission denied", ProviderCode.AUTH_DENIED),
        ("EService:Unavailable", ProviderCode.UNAVAILABLE),
        ("SECRET-UNKNOWN", ProviderCode.INVALID_DATA),
    ],
)
def test_api_envelope_error_normalization(message: str, code: ProviderCode) -> None:
    with pytest.raises(ProviderError) as caught:
        parsed(json.dumps({"error": [message]}).encode())
    assert caught.value.code is code and message not in str(caught.value)


def test_mocked_http_success_contract_request_and_health() -> None:
    async def run() -> None:
        requests = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            assert request.method == "GET" and request.url.host == "api.kraken.com"
            assert not any(
                name in request.headers for name in ["API-Key", "API-Sign", "Authorization"]
            )
            if request.url.path.endswith("SystemStatus"):
                return httpx.Response(
                    200,
                    json={"error": [], "result": {"status": "maintenance", "timestamp": "fixture"}},
                )
            assert request.url.params["pair"] == "XBTEUR" and request.url.params["interval"] == "1"
            assert request.url.params["since"] == str(int(BASE.timestamp()))
            return httpx.Response(200, content=encoded())

        async with KrakenPublicProvider(transport=httpx.MockTransport(respond)) as provider:
            provider.rate_gate = RateGate(0.0)  # Synthetic transport only; no real requests.
            client = MarketDataClient(provider, ReadPolicy(min_spacing=0.0))
            page = await client.fetch_bars(INSTRUMENT, BASE, BASE + timedelta(minutes=5), 60)
            assert len(page.bars) == 5
            assert (await client.provider_health()).status is HealthStatus.DEGRADED
            with pytest.raises(ProviderError):
                await provider.fetch_quote(INSTRUMENT)
            with pytest.raises(ProviderError):
                provider.stream_quotes(INSTRUMENT)
        assert len(requests) == 2

    asyncio.run(run())


@pytest.mark.parametrize(
    "status,code",
    [
        (301, ProviderCode.INVALID_DATA),
        (401, ProviderCode.AUTH_DENIED),
        (403, ProviderCode.AUTH_DENIED),
        (429, ProviderCode.RATE_LIMITED),
        (503, ProviderCode.UNAVAILABLE),
    ],
)
def test_http_error_status_normalized_without_response_text(
    status: int, code: ProviderCode
) -> None:
    async def run() -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status,
                content=b"SENSITIVE-RESPONSE",
                headers={"Retry-After": "20", "Location": "https://example.invalid"},
            )

        async with KrakenPublicProvider(transport=httpx.MockTransport(respond)) as provider:
            with pytest.raises(ProviderError) as caught:
                await provider.fetch_bars(INSTRUMENT, BASE, BASE + timedelta(minutes=5), 60)
            assert caught.value.code is code and "SENSITIVE" not in str(caught.value)
            if status == 429:
                assert caught.value.retry_after == 20.0

    asyncio.run(run())


def test_http_date_retry_and_malformed_throttle_freezes_instance() -> None:
    async def run() -> None:
        requests = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(429, headers={"Retry-After": "NaN"})

        async with KrakenPublicProvider(transport=httpx.MockTransport(respond)) as provider:
            for _ in range(2):
                with pytest.raises(ProviderError) as caught:
                    await provider.fetch_bars(INSTRUMENT, BASE, BASE + timedelta(minutes=5), 60)
                assert caught.value.code is ProviderCode.RATE_LIMITED
            assert provider.blocked_throttle and len(requests) == 1
        date_header = format_datetime(utc_now() + timedelta(seconds=30), usegmt=True)
        async with KrakenPublicProvider(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(429, headers={"Retry-After": date_header})
            )
        ) as provider:
            with pytest.raises(ProviderError) as caught:
                await provider.fetch_bars(INSTRUMENT, BASE, BASE + timedelta(minutes=5), 60)
            assert 20 < caught.value.retry_after <= 31

    asyncio.run(run())


def test_timeout_unknown_request_cursor_and_size_fail_closed() -> None:
    async def run() -> None:
        calls = []

        def timeout(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            raise httpx.ReadTimeout("SENSITIVE-TIMEOUT", request=request)

        async with KrakenPublicProvider(transport=httpx.MockTransport(timeout)) as provider:
            with pytest.raises(ProviderError) as caught:
                await provider.fetch_bars(INSTRUMENT, BASE, BASE + timedelta(minutes=5), 60)
            assert caught.value.code is ProviderCode.TIMEOUT
            for kwargs in [{"cursor": "not-a-cursor"}, {"cursor": "999999999999"}]:
                with pytest.raises(ProviderError):
                    await provider.fetch_bars(
                        INSTRUMENT, BASE, BASE + timedelta(minutes=5), 60, **kwargs
                    )
            with pytest.raises(ProviderError):
                await provider.fetch_bars(uuid4(), BASE, BASE + timedelta(minutes=5), 60)
            with pytest.raises(ProviderError):
                await provider._request("Balance")
            assert len(calls) == 1
        async with KrakenPublicProvider(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=b" " * (MAX_RESPONSE + 1))
            )
        ) as provider:
            with pytest.raises(ProviderError) as caught:
                await provider.fetch_bars(INSTRUMENT, BASE, BASE + timedelta(minutes=5), 60)
            assert caught.value.code is ProviderCode.INVALID_DATA

    asyncio.run(run())
