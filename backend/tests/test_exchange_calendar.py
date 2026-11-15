from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.exchange_calendar import CalendarUnavailable, is_scheduled_open, session_for_day


@pytest.mark.parametrize("code", ["XETR", "XAMS", "XNYS"])
def test_weekends_and_christmas_are_closed(code: str) -> None:
    assert session_for_day(code, date(2026, 11, 15)) is None
    assert session_for_day(code, date(2026, 12, 25)) is None
    assert session_for_day(code, date(2026, 1, 1)) is None


@pytest.mark.parametrize(
    "day",
    [date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 1), date(2026, 12, 24), date(2026, 12, 31)],
)
def test_official_xetra_holidays(day: date) -> None:
    assert session_for_day("XETR", day) is None


@pytest.mark.parametrize("code", ["XETR", "XAMS"])
def test_europe_dst_in_spring_and_autumn(code: str) -> None:
    assert session_for_day(code, date(2026, 3, 27)).opens_at == datetime(2026, 3, 27, 8, tzinfo=UTC)
    assert session_for_day(code, date(2026, 3, 30)).opens_at == datetime(2026, 3, 30, 7, tzinfo=UTC)
    assert session_for_day(code, date(2026, 10, 23)).opens_at.hour == 7
    assert session_for_day(code, date(2026, 10, 26)).opens_at.hour == 8


def test_nyse_distinct_dst_and_actual_early_close() -> None:
    assert session_for_day("XNYS", date(2026, 3, 6)).opens_at.hour == 14
    assert session_for_day("XNYS", date(2026, 3, 9)).opens_at.hour == 13
    assert session_for_day("XNYS", date(2026, 11, 26)) is None
    early = session_for_day("XNYS", date(2026, 11, 27))
    assert early.early_close
    assert early.closes_at == datetime(2026, 11, 27, 18, tzinfo=UTC)
    assert not is_scheduled_open("XNYS", early.closes_at)


def test_official_xetra_final_day_excludes_closing_auction() -> None:
    early = session_for_day("XETR", date(2026, 12, 30))
    assert early.early_close
    assert early.closes_at == datetime(2026, 12, 30, 13, tzinfo=UTC)
    assert "official-XETR" in early.revision
    assert not is_scheduled_open("XETR", early.closes_at)


def test_exact_half_open_boundaries_and_timezone_conversion() -> None:
    session = session_for_day("XETR", date(2026, 11, 16))
    assert not is_scheduled_open("XETR", session.opens_at - timedelta(microseconds=1))
    assert is_scheduled_open("XETR", session.opens_at)
    assert is_scheduled_open("XETR", session.closes_at - timedelta(microseconds=1))
    assert not is_scheduled_open("XETR", session.closes_at)
    assert is_scheduled_open("XETR", session.opens_at.astimezone(ZoneInfo("Europe/Zagreb")))


@pytest.mark.parametrize(
    "day", [date(2026, 11, 15), date(2026, 12, 25), date(2026, 3, 29), date(2026, 10, 25)]
)
def test_crypto_is_24_hours_even_on_holidays_weekends_and_dst(day: date) -> None:
    session = session_for_day("CRYPTO_24_7", day)
    assert session.closes_at - session.opens_at == timedelta(days=1)
    assert not session.early_close
    assert is_scheduled_open("CRYPTO_24_7", session.opens_at)
    assert is_scheduled_open("CRYPTO_24_7", session.closes_at)  # Next day's window.


def test_invalid_calendar_date_and_naive_time_fail_closed() -> None:
    with pytest.raises(CalendarUnavailable):
        session_for_day("UNKNOWN", date(2026, 11, 16))
    for day in [date(2024, 12, 31), date(2029, 1, 1)]:
        with pytest.raises(CalendarUnavailable):
            session_for_day("XETR", day)
    with pytest.raises(ValueError, match="timezone-aware"):
        is_scheduled_open("XETR", datetime(2026, 11, 16, 12))


def test_provider_failure_has_no_open_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import exchange_calendar

    def broken(code: str) -> None:
        raise ValueError("provider unavailable")

    monkeypatch.setattr(exchange_calendar, "provider", broken)
    with pytest.raises(CalendarUnavailable, match="no open fallback"):
        is_scheduled_open("XETR", datetime(2026, 11, 16, 12, tzinfo=UTC))


def test_unreviewed_dependency_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import exchange_calendar

    exchange_calendar.provider.cache_clear()
    monkeypatch.setattr(exchange_calendar, "version", lambda name: "unreviewed")
    with pytest.raises(CalendarUnavailable, match="reviewed version"):
        session_for_day("XETR", date(2026, 11, 16))
    exchange_calendar.provider.cache_clear()
