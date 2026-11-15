"""Versioned scheduled core sessions, never a permission to place orders."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from importlib.metadata import version
from typing import Protocol, cast
from zoneinfo import ZoneInfo

import exchange_calendars as xcals  # type: ignore[import-untyped]

from app.domain_types import require_utc

PINNED_VERSION = "4.13.3"
FIRST_DAY = date(2025, 1, 1)
LAST_DAY = date(2028, 12, 31)
ZONES = {
    "XETR": "Europe/Berlin",
    "XAMS": "Europe/Amsterdam",
    "XNYS": "America/New_York",
    "CRYPTO_24_7": "UTC",
}
REGULAR_CLOSE = {"XETR": time(17, 30), "XAMS": time(17, 30), "XNYS": time(16)}
FINAL_XETRA_2026 = "https://cashmarket.deutsche-boerse.com/resource/blob/5673886/22764993c4b1617c5f465186066344e6/data/Final%20trading%20session%202026.pdf"


class CalendarUnavailable(ValueError):
    """Unknown calendar, unsupported date or provider failure; no open fallback."""


class TimestampLike(Protocol):
    def to_pydatetime(self) -> datetime: ...


class CalendarLike(Protocol):
    def is_session(self, date: str) -> bool: ...
    def session_open(self, session: str) -> TimestampLike: ...
    def session_close(self, session: str) -> TimestampLike: ...


@dataclass(frozen=True, slots=True)
class CoreSession:
    calendar: str
    label: date
    opens_at: datetime
    closes_at: datetime
    early_close: bool
    revision: str


@lru_cache(maxsize=3)
def provider(code: str) -> CalendarLike:
    if version("exchange-calendars") != PINNED_VERSION:
        raise CalendarUnavailable("Calendar dependency differs from reviewed version")
    # Buffer prevents boundary holidays being classified as provider out-of-range.
    return cast(
        CalendarLike, xcals.get_calendar(code, start="2024-01-01", end="2029-12-31", side="left")
    )


def session_for_day(code: str, day: date) -> CoreSession | None:
    if code not in ZONES or type(day) is not date or not FIRST_DAY <= day <= LAST_DAY:
        raise CalendarUnavailable("Unknown calendar or date outside reviewed 2025-2028 coverage")
    revision = "calendar-v1/exchange-calendars-" + PINNED_VERSION
    if code == "CRYPTO_24_7":
        opening = datetime.combine(day, time(0), UTC)
        return CoreSession(code, day, opening, opening + timedelta(days=1), False, revision)
    try:
        calendar = provider(code)
        label = day.isoformat()
        if not calendar.is_session(label):
            return None
        opening = require_utc(calendar.session_open(label).to_pydatetime())
        closing = require_utc(calendar.session_close(label).to_pydatetime())
    except CalendarUnavailable:
        raise
    except (ValueError, KeyError, TypeError, RuntimeError):
        raise CalendarUnavailable("Calendar schedule unavailable; no open fallback") from None
    if code == "XETR" and day == date(2026, 12, 30):
        # Official 14:00 CET start of closing auction; auctions/TAC are excluded.
        closing = datetime(2026, 12, 30, 14, tzinfo=ZoneInfo("Europe/Berlin")).astimezone(UTC)
        revision += "/official-XETR-final-2026"
    if opening >= closing:
        raise CalendarUnavailable("Invalid scheduled session interval")
    local_close = closing.astimezone(ZoneInfo(ZONES[code])).time()
    return CoreSession(code, day, opening, closing, local_close < REGULAR_CLOSE[code], revision)


def is_scheduled_open(code: str, moment: datetime) -> bool:
    instant = require_utc(moment)
    if code not in ZONES:
        raise CalendarUnavailable("Unknown calendar")
    label = instant.astimezone(ZoneInfo(ZONES[code])).date()
    session = session_for_day(code, label)
    # Half-open intervals: opening included, closing excluded, no minute rounding.
    return session is not None and session.opens_at <= instant < session.closes_at
