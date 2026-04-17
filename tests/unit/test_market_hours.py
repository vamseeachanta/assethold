"""ABOUTME: Unit tests for utils.market_hours module.
ABOUTME: Covers regular session, holidays, half-days, TZ contract, boundary cases."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from assethold.utils.market_hours import is_market_open, next_open, next_close


def _et(year, month, day, hour=12, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/New_York"))


def test_tuesday_10am_open():
    assert is_market_open(_et(2026, 4, 21, 10, 0)) is True


def test_tuesday_pre_market_closed():
    assert is_market_open(_et(2026, 4, 21, 8, 0)) is False


def test_tuesday_after_hours_closed():
    assert is_market_open(_et(2026, 4, 21, 17, 0)) is False


def test_saturday_closed():
    assert is_market_open(_et(2026, 4, 18, 12, 0)) is False


def test_sunday_closed():
    assert is_market_open(_et(2026, 4, 19, 12, 0)) is False


def test_memorial_day_closed():
    """Mon 25 May 2026 is Memorial Day — full closure."""
    assert is_market_open(_et(2026, 5, 25, 10, 0)) is False


def test_black_friday_before_early_close():
    """Fri 27 Nov 2026 (Black Friday) closes early at 13:00 ET; 12:00 is open."""
    assert is_market_open(_et(2026, 11, 27, 12, 0)) is True


def test_black_friday_after_early_close():
    """Fri 27 Nov 2026 at 14:00 ET — early close honored."""
    assert is_market_open(_et(2026, 11, 27, 14, 0)) is False


def test_naive_treated_as_utc():
    """Naive ts is treated as UTC. 14:00 UTC on a trading Tuesday in April = 10:00 EDT → open."""
    naive = datetime(2026, 4, 21, 14, 0)
    assert is_market_open(naive) is True


def test_aware_pst_converted_to_et():
    """7:00 PDT on a trading Tuesday in April = 10:00 EDT → open."""
    pst = datetime(2026, 4, 21, 7, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert is_market_open(pst) is True


def test_next_open_returns_aware_et():
    """From Sunday 12:00 ET, next open is Mon 09:30 ET (TZ-aware)."""
    result = next_open(_et(2026, 4, 19, 12, 0))
    assert result.tzinfo is not None
    assert (result.year, result.month, result.day) == (2026, 4, 20)
    assert (result.hour, result.minute) == (9, 30)


def test_next_open_at_bell_returns_following_session():
    """At exactly 09:30:00 ET on Tue, next_open is Wed 09:30 (strict greater-than)."""
    bell = _et(2026, 4, 21, 9, 30)
    result = next_open(bell)
    assert result.day == 22


def test_next_close_returns_aware_et():
    """At 10:00 ET on Tue, next_close is same day 16:00 ET."""
    result = next_close(_et(2026, 4, 21, 10, 0))
    assert result.tzinfo is not None
    assert (result.day, result.hour, result.minute) == (21, 16, 0)


def test_out_of_range_raises_when_schedule_empty(monkeypatch):
    """When the calendar returns an empty schedule, next_open raises ValueError."""
    import assethold.utils.market_hours as mh

    class _StubCal:
        def schedule(self, start_date, end_date):
            return pd.DataFrame(columns=["market_open", "market_close"])

    monkeypatch.setattr(mh, "_get_calendar", lambda: _StubCal())
    with pytest.raises(ValueError):
        next_open(datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc))
