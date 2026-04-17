"""ABOUTME: NYSE regular-session calendar wrapping pandas_market_calendars.
ABOUTME: Provides is_market_open / next_open / next_close with naive-as-UTC contract."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd


_CALENDAR = None


def _get_calendar():
    """Lazy-load the NYSE calendar singleton."""
    global _CALENDAR
    if _CALENDAR is None:
        import pandas_market_calendars as mcal
        _CALENDAR = mcal.get_calendar("XNYS")
    return _CALENDAR


def _normalize(ts: Optional[datetime]) -> pd.Timestamp:
    """Return a TZ-aware ET pd.Timestamp.

    Naive ts is treated as UTC. None becomes 'now in UTC'.
    """
    if ts is None:
        ts = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return pd.Timestamp(ts).tz_convert("America/New_York")


def is_market_open(ts: Optional[datetime] = None) -> bool:
    """Return True iff NYSE regular session is open at `ts`.

    Regular session = 9:30am–16:00 ET, weekdays, excluding NYSE holidays.
    Half-day closes are honored via the calendar's per-day schedule
    (e.g. Black Friday and Christmas Eve typically close at 13:00 ET).

    Parameters
    ----------
    ts : datetime, optional
        Timestamp to check. May be timezone-aware (any zone) or naive.
        If naive, interpreted as UTC. If None, uses datetime.now(timezone.utc).

    Returns
    -------
    bool
    """
    et = _normalize(ts)
    cal = _get_calendar()
    schedule = cal.schedule(start_date=et.date(), end_date=et.date())
    if schedule.empty:
        return False
    open_ts = schedule.iloc[0]["market_open"]
    close_ts = schedule.iloc[0]["market_close"]
    return bool(open_ts <= et < close_ts)


def next_open(ts: Optional[datetime] = None) -> datetime:
    """Return the next NYSE regular-session opening strictly after `ts`.

    Returns a TZ-aware datetime in America/New_York. Searches up to 14 days
    forward; raises ValueError if no opening is found in that window.
    """
    et = _normalize(ts)
    cal = _get_calendar()
    schedule = cal.schedule(
        start_date=et.date(),
        end_date=(et + pd.Timedelta(days=14)).date(),
    )
    for _, row in schedule.iterrows():
        if row["market_open"] > et:
            return row["market_open"].tz_convert("America/New_York").to_pydatetime()
    raise ValueError(f"No NYSE market open found within 14 days of {ts}")


def next_close(ts: Optional[datetime] = None) -> datetime:
    """Return the next NYSE regular-session close strictly after `ts`.

    Returns a TZ-aware datetime in America/New_York. Searches up to 14 days
    forward; raises ValueError if no close is found in that window.
    """
    et = _normalize(ts)
    cal = _get_calendar()
    schedule = cal.schedule(
        start_date=et.date(),
        end_date=(et + pd.Timedelta(days=14)).date(),
    )
    for _, row in schedule.iterrows():
        if row["market_close"] > et:
            return row["market_close"].tz_convert("America/New_York").to_pydatetime()
    raise ValueError(f"No NYSE market close found within 14 days of {ts}")
