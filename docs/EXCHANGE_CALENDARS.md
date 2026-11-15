# Versioned scheduled core-session calendars

TAI-028 provides session_for_day and is_scheduled_open for XETR, XAMS, XNYS and
a distinct CRYPTO_24_7 calendar. This is an offline schedule service, not a market
status, instrument eligibility, feed-health or order-permission check.

The reviewed query range is 2025-01-01 through 2028-12-31. Unknown calendars,
unsupported dates, unreviewed library versions and provider failures raise
CalendarUnavailable; they never fall back to weekday/always-open assumptions.
A known weekend/holiday returns no session. Times are aware UTC; labels use each
venue's explicit IANA zone. Crypto uses UTC days of exactly 24 hours, including
weekends, holidays and European DST transitions.

Regular equity core windows exclude pre/post-market and closing auctions. The
window itself is not a guarantee of continuous matching: intraday auctions,
instrument suspensions and ad hoc outages still need separate controls. Interval
semantics are [open, close); microseconds are not rounded to minutes. This does
not include Xetra extended retail early/late service or trade-at-close.

## Source and version

[exchange-calendars 4.13.3](https://pypi.org/project/exchange-calendars/4.13.3/) is
exactly pinned with transitive wheel/source hashes in uv.lock. License expression
Apache-2.0 and Python 3.12 support were verified in project metadata. The project
[calendar documentation](https://github.com/gerrymanoim/exchange_calendars) covers
the selected exchange calendars. A tiny typed protocol contains the third-party
boundary; only that package's untyped import is explicitly acknowledged to mypy.
Application strict checking remains enabled.

Official references reviewed on 2026-11-15:

- [Xetra calendar](https://cashmarket.deutsche-boerse.com/cash-en/trading/trading-calendar-and-trading-hours): selected holidays and possible final-day deviations.
- [Xetra final session 2026](https://cashmarket.deutsche-boerse.com/resource/blob/5673886/22764993c4b1617c5f465186066344e6/data/Final%20trading%20session%202026.pdf): closing auction begins 14:00 CET on 30 December. The core window is explicitly capped there (13:00 UTC); later auction/TAC is excluded.
- [NYSE hours/calendars](https://www.nyse.com/markets/hours-calendars): 27 November 2026 equity early close at 13:00 Eastern, represented as 18:00 UTC.

CoreSession carries calendar revision, UTC endpoints and early-close flag. The
Xetra final-session override has a separate source-specific revision suffix.
Library updates and future circulars require review/tests, not automatic widening
of the schedule or supported date range. Future dates are planned schedules and
may change. This snapshot is not a bitemporal publication history; backtests must
not infer that a later-announced schedule change was known earlier.

## Verified behavior and limits

Tests cover Xetra/Euronext spring and autumn DST, distinct US spring DST,
weekends/Christmas/New Year, Xetra Easter/Labor/Christmas Eve/year-end holidays,
NYSE Thanksgiving/early close, official Xetra final-day override, exact interval
edges, timezone conversions, crypto 24/7 and fail-closed provider/version errors.
Real Linux Docker probe repeats the selected official cases; no network request
is made by the calendar service. Existing candidates and DB revision are preserved.

The full suite passes with upstream warnings: one Starlette TestClient warning
and twelve exchange-calendars/Pandas future-deprecation warnings. UTC output and
DST tests pass; warnings are recorded, not suppressed. No LIVE/real-order path or
API route was introduced. Evidence: [TAI-028 report](reports/TAI-028.md).
