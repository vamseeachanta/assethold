# Realtime Phase 1 — Market-Hours Awareness + Intraday TTL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add NYSE-regular-session awareness and a 15-minute intraday cache TTL to the assethold price-data path, exposed via a new `--intraday` flag on `daily_strategy`.

**Architecture:** One new pure module (`utils/market_hours.py`) wrapping `pandas_market_calendars`. Two cache layers gain TTL-routing helpers/kwargs (`modules/stocks/cache.py`, `signals/data_sources.py`). The `MarketDataFetcher` in `analysis/daily_strategy/fetcher.py` mirrors the kwargs and switches its `_fetch_ohlcv` 4-day buffer to mtime-vs-intraday-TTL when aware + open. The CLI gains a `--intraday` flag with fail-loud pre-flight.

**Tech Stack:** Python 3.11+, `pandas_market_calendars` (NEW), `pandas`, `pytest`. Test runner: `.venv/bin/python -m pytest` (10s) — NOT `uv run pytest` (5–15 min, see handoff gotcha).

**Spec:** `docs/reports/2026-04-16-realtime-phase1-design.md` (commit `18b3b73`).

**Working directory for all commands:** `/mnt/local-analysis/workspace-hub/assethold/` (no worktree; commits go straight to `main` per the repo's established doc/refactor pattern).

---

## Task 1: Add `pandas_market_calendars` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the dependency**

```bash
cd /mnt/local-analysis/workspace-hub/assethold
uv add pandas_market_calendars
```

This both updates `pyproject.toml` and installs into `.venv`.

- [ ] **Step 2: Verify the import works**

```bash
.venv/bin/python -c "import pandas_market_calendars as mcal; cal = mcal.get_calendar('XNYS'); print(cal.name, cal.tz)"
```

Expected output: `NYSE America/New_York`

- [ ] **Step 3: Verify suite still passes**

```bash
.venv/bin/python -m pytest tests/ -x -q
```

Expected: 819 passed, 0 failed (no regressions from dep add).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add pandas_market_calendars for NYSE calendar awareness (#35)"
```

---

## Task 2: Create `utils/market_hours.py` with TDD

**Files:**
- Create: `src/assethold/utils/__init__.py` (if missing)
- Create: `src/assethold/utils/market_hours.py`
- Create: `tests/unit/test_market_hours.py`

- [ ] **Step 1: Verify `utils/` package exists**

```bash
ls src/assethold/utils/__init__.py 2>/dev/null || (mkdir -p src/assethold/utils && touch src/assethold/utils/__init__.py)
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_market_hours.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/unit/test_market_hours.py -v
```

Expected: All tests FAIL with `ModuleNotFoundError: No module named 'assethold.utils.market_hours'`.

- [ ] **Step 4: Implement `market_hours.py`**

Create `src/assethold/utils/market_hours.py`:

```python
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
            return row["market_open"].to_pydatetime()
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
            return row["market_close"].to_pydatetime()
    raise ValueError(f"No NYSE market close found within 14 days of {ts}")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/unit/test_market_hours.py -v
```

Expected: 14 passed.

- [ ] **Step 6: Commit**

```bash
git add src/assethold/utils/__init__.py src/assethold/utils/market_hours.py tests/unit/test_market_hours.py
git commit -m "feat: add utils.market_hours for NYSE regular-session awareness (#35)"
```

---

## Task 3: Add `cache.ohlcv_ttl()` helper with TDD

**Files:**
- Modify: `src/assethold/modules/stocks/cache.py:16-20` (add constant)
- Modify: `src/assethold/modules/stocks/cache.py` (append new function)
- Create: `tests/unit/test_cache_ohlcv_ttl.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_cache_ohlcv_ttl.py`:

```python
"""ABOUTME: Unit tests for cache.ohlcv_ttl() and TTL_OHLCV_INTRADAY constant.
ABOUTME: Verifies TTL switching when market_hours_aware is True."""

import pytest

import assethold.modules.stocks.cache as cache_mod
from assethold.modules.stocks.cache import (
    TTL_OHLCV,
    TTL_OHLCV_INTRADAY,
    ohlcv_ttl,
)


def test_intraday_constant_is_15_minutes():
    assert TTL_OHLCV_INTRADAY == 15 * 60


def test_default_returns_legacy_ttl():
    """When market_hours_aware is False, always returns TTL_OHLCV."""
    assert ohlcv_ttl() == TTL_OHLCV
    assert ohlcv_ttl(False) == TTL_OHLCV


def test_aware_returns_intraday_when_open(monkeypatch):
    """When aware AND market is open, returns the 15-min TTL."""
    monkeypatch.setattr(
        "assethold.utils.market_hours.is_market_open",
        lambda ts=None: True,
    )
    assert ohlcv_ttl(market_hours_aware=True) == TTL_OHLCV_INTRADAY


def test_aware_returns_legacy_when_closed(monkeypatch):
    """When aware but market is closed, returns the 6h TTL."""
    monkeypatch.setattr(
        "assethold.utils.market_hours.is_market_open",
        lambda ts=None: False,
    )
    assert ohlcv_ttl(market_hours_aware=True) == TTL_OHLCV
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/unit/test_cache_ohlcv_ttl.py -v
```

Expected: All tests FAIL with `ImportError: cannot import name 'TTL_OHLCV_INTRADAY'` or `'ohlcv_ttl'`.

- [ ] **Step 3: Add the constant and helper**

In `src/assethold/modules/stocks/cache.py`, after the existing TTL block (line 20), add:

```python
TTL_OHLCV_INTRADAY = 15 * 60  # 15 min, used during NYSE regular session
```

Then append at the end of the file:

```python
def ohlcv_ttl(market_hours_aware: bool = False) -> int:
    """Return the OHLCV cache TTL in seconds.

    When market_hours_aware is True AND market_hours.is_market_open() is True,
    returns TTL_OHLCV_INTRADAY (15 min). Otherwise returns TTL_OHLCV (6 h).

    The static TTL_OHLCV path does NOT import market_hours, so the
    pandas_market_calendars dep is only required when the caller opts in.
    """
    if not market_hours_aware:
        return TTL_OHLCV
    from assethold.utils.market_hours import is_market_open
    return TTL_OHLCV_INTRADAY if is_market_open() else TTL_OHLCV
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/unit/test_cache_ohlcv_ttl.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/assethold/modules/stocks/cache.py tests/unit/test_cache_ohlcv_ttl.py
git commit -m "feat: add cache.ohlcv_ttl() helper for market-hours-aware TTL routing (#35)"
```

---

## Task 4: Extend `StockDataSource` constructor and `_is_cache_valid` with TDD

**Files:**
- Modify: `src/assethold/signals/data_sources.py:14-37` (constructor)
- Modify: `src/assethold/signals/data_sources.py:45-50` (`_is_cache_valid`)
- Create: `tests/unit/signals/test_data_sources_market_hours.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/signals/test_data_sources_market_hours.py`:

```python
"""ABOUTME: Unit tests for StockDataSource market-hours-aware TTL behavior.
ABOUTME: Verifies constructor kwargs and per-call TTL switching in _is_cache_valid."""

import os
import time
from datetime import timedelta
from pathlib import Path

import pytest

from assethold.signals.data_sources import StockDataSource


@pytest.fixture
def cache_path(tmp_path):
    """Touch a cache file and return its path."""
    p = tmp_path / "AAPL_test.csv"
    p.write_text("date,open,high,low,close,volume\n2026-04-21,100,101,99,100,1000\n")
    return p


def test_constructor_accepts_new_kwargs(tmp_path):
    """New kwargs are accepted with documented defaults."""
    src = StockDataSource(
        cache_dir=tmp_path,
        market_hours_aware=True,
        intraday_ttl_minutes=15,
    )
    assert src.market_hours_aware is True
    assert src.intraday_ttl == timedelta(minutes=15)


def test_constructor_defaults_preserve_existing_behavior(tmp_path):
    """Without the new kwargs, behavior is byte-identical to today."""
    src = StockDataSource(cache_dir=tmp_path)
    assert src.market_hours_aware is False
    assert src.intraday_ttl == timedelta(minutes=15)  # default value, but unused


def test_cache_valid_uses_intraday_ttl_when_aware_and_open(
    cache_path, monkeypatch, tmp_path
):
    """When aware+open and file is 5 min old, cache is valid (intraday TTL = 15 min)."""
    src = StockDataSource(
        cache_dir=tmp_path,
        cache_ttl_hours=24,
        market_hours_aware=True,
        intraday_ttl_minutes=15,
    )
    # Set mtime to 5 minutes ago
    five_min_ago = time.time() - 5 * 60
    os.utime(cache_path, (five_min_ago, five_min_ago))
    monkeypatch.setattr(
        "assethold.utils.market_hours.is_market_open",
        lambda ts=None: True,
    )
    assert src._is_cache_valid(cache_path) is True


def test_cache_invalid_when_intraday_ttl_exceeded(
    cache_path, monkeypatch, tmp_path
):
    """When aware+open and file is 20 min old, intraday TTL (15 min) is exceeded."""
    src = StockDataSource(
        cache_dir=tmp_path,
        cache_ttl_hours=24,
        market_hours_aware=True,
        intraday_ttl_minutes=15,
    )
    twenty_min_ago = time.time() - 20 * 60
    os.utime(cache_path, (twenty_min_ago, twenty_min_ago))
    monkeypatch.setattr(
        "assethold.utils.market_hours.is_market_open",
        lambda ts=None: True,
    )
    assert src._is_cache_valid(cache_path) is False


def test_cache_uses_legacy_ttl_when_aware_but_closed(
    cache_path, monkeypatch, tmp_path
):
    """When aware but market is closed, falls back to legacy 24h TTL."""
    src = StockDataSource(
        cache_dir=tmp_path,
        cache_ttl_hours=24,
        market_hours_aware=True,
        intraday_ttl_minutes=15,
    )
    # File is 1 hour old — would be invalid under intraday TTL but valid under 24h TTL
    one_hour_ago = time.time() - 60 * 60
    os.utime(cache_path, (one_hour_ago, one_hour_ago))
    monkeypatch.setattr(
        "assethold.utils.market_hours.is_market_open",
        lambda ts=None: False,
    )
    assert src._is_cache_valid(cache_path) is True


def test_cache_uses_legacy_ttl_when_not_aware(cache_path, tmp_path):
    """When market_hours_aware=False (default), TTL is always the legacy value."""
    src = StockDataSource(cache_dir=tmp_path, cache_ttl_hours=24)  # not aware
    one_hour_ago = time.time() - 60 * 60
    os.utime(cache_path, (one_hour_ago, one_hour_ago))
    assert src._is_cache_valid(cache_path) is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/unit/signals/test_data_sources_market_hours.py -v
```

Expected: All tests FAIL — constructor rejects unknown kwargs.

- [ ] **Step 3: Modify `StockDataSource.__init__`**

Replace the existing constructor in `src/assethold/signals/data_sources.py` (lines 17–37) with:

```python
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        cache_ttl_hours: int = 24,
        rate_limit_seconds: float = 2.0,
        market_hours_aware: bool = False,
        intraday_ttl_minutes: int = 15,
    ):
        """
        Initialize stock data source.

        Args:
            cache_dir: Directory for cache files (default: data/stocks/cache)
            cache_ttl_hours: Cache validity in hours (used outside market hours
                or when market_hours_aware is False)
            rate_limit_seconds: Minimum delay between requests
            market_hours_aware: When True, _is_cache_valid switches to a
                shorter TTL during the NYSE regular session
            intraday_ttl_minutes: TTL (minutes) used during the NYSE regular
                session when market_hours_aware is True
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parents[3] / "data" / "stocks" / "cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.rate_limit = rate_limit_seconds
        self._last_request_time = 0.0
        self.market_hours_aware = market_hours_aware
        self.intraday_ttl = timedelta(minutes=intraday_ttl_minutes)
```

- [ ] **Step 4: Modify `_is_cache_valid`**

Replace the existing method (lines 45–50) with:

```python
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists and is not expired.

        When market_hours_aware is True AND the NYSE regular session is open,
        uses self.intraday_ttl (e.g. 15 min). Otherwise uses self.cache_ttl
        (legacy behavior, e.g. 24h).
        """
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - mtime
        if self.market_hours_aware:
            from assethold.utils.market_hours import is_market_open
            if is_market_open():
                return age < self.intraday_ttl
        return age < self.cache_ttl
```

- [ ] **Step 5: Run new tests + existing data_sources tests to verify no regression**

```bash
.venv/bin/python -m pytest tests/unit/signals/test_data_sources.py tests/unit/signals/test_data_sources_market_hours.py -v
```

Expected: existing `test_data_sources.py` still passes; new tests (6) pass.

- [ ] **Step 6: Commit**

```bash
git add src/assethold/signals/data_sources.py tests/unit/signals/test_data_sources_market_hours.py
git commit -m "feat: market-hours-aware TTL in StockDataSource (#35)"
```

---

## Task 5: Extend `MarketDataFetcher` constructor and `_fetch_ohlcv` buffer with TDD

**Files:**
- Modify: `src/assethold/analysis/daily_strategy/fetcher.py:55-83` (constructor)
- Modify: `src/assethold/analysis/daily_strategy/fetcher.py:175-223` (`_fetch_ohlcv`)
- Create: `tests/unit/analysis/__init__.py` (if missing)
- Create: `tests/unit/analysis/daily_strategy/__init__.py` (if missing)
- Create: `tests/unit/analysis/daily_strategy/test_fetcher_market_hours.py`

- [ ] **Step 1: Verify test package dirs exist**

```bash
mkdir -p tests/unit/analysis/daily_strategy
touch tests/unit/analysis/__init__.py tests/unit/analysis/daily_strategy/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/analysis/daily_strategy/test_fetcher_market_hours.py`:

```python
"""ABOUTME: Unit tests for MarketDataFetcher market-hours-aware behavior.
ABOUTME: Verifies constructor kwargs and _fetch_ohlcv buffer-switching."""

import os
import time
from datetime import date, timedelta

import pandas as pd
import pytest

from assethold.analysis.daily_strategy.fetcher import MarketDataFetcher


def test_constructor_accepts_new_kwargs(tmp_path):
    """New kwargs accepted, with defaults preserving today's behavior."""
    f = MarketDataFetcher(
        cache_dir=tmp_path,
        market_hours_aware=True,
        intraday_ttl_minutes=15,
    )
    assert f._market_hours_aware is True
    assert f._intraday_ttl == timedelta(minutes=15)


def test_constructor_defaults_preserve_existing_behavior(tmp_path):
    """Without the new kwargs, _market_hours_aware is False."""
    f = MarketDataFetcher(cache_dir=tmp_path)
    assert f._market_hours_aware is False


def test_fetch_ohlcv_uses_intraday_buffer_when_aware_and_open(
    tmp_path, monkeypatch
):
    """When aware+open and file mtime is 5 min ago, _fetch_ohlcv returns cached without network."""
    f = MarketDataFetcher(
        cache_dir=tmp_path,
        market_hours_aware=True,
        intraday_ttl_minutes=15,
    )
    cache_path = tmp_path / "AAPL_ohlcv.csv"
    df = pd.DataFrame({
        "date": [date.today() - timedelta(days=10)],
        "open": [100.0], "high": [101.0], "low": [99.0],
        "close": [100.5], "volume": [1000],
    })
    df.to_csv(cache_path, index=False)
    five_min_ago = time.time() - 5 * 60
    os.utime(cache_path, (five_min_ago, five_min_ago))

    monkeypatch.setattr(
        "assethold.utils.market_hours.is_market_open",
        lambda ts=None: True,
    )

    # Verify no network call: monkeypatch _source.fetch to raise
    def _no_network(*args, **kwargs):
        raise AssertionError("Network call should not happen — cache is fresh")
    monkeypatch.setattr(f._source, "fetch", _no_network)

    result = f._fetch_ohlcv("AAPL")
    assert len(result) == 1


def test_fetch_ohlcv_refetches_when_intraday_buffer_exceeded(
    tmp_path, monkeypatch
):
    """When aware+open and file mtime is 20 min ago, _fetch_ohlcv attempts a refetch."""
    f = MarketDataFetcher(
        cache_dir=tmp_path,
        market_hours_aware=True,
        intraday_ttl_minutes=15,
    )
    cache_path = tmp_path / "AAPL_ohlcv.csv"
    old_df = pd.DataFrame({
        "date": [date.today() - timedelta(days=10)],
        "open": [100.0], "high": [101.0], "low": [99.0],
        "close": [100.5], "volume": [1000],
    })
    old_df.to_csv(cache_path, index=False)
    twenty_min_ago = time.time() - 20 * 60
    os.utime(cache_path, (twenty_min_ago, twenty_min_ago))

    monkeypatch.setattr(
        "assethold.utils.market_hours.is_market_open",
        lambda ts=None: True,
    )

    fetch_called = {"n": 0}
    def _stub_fetch(ticker, start, end, use_cache=False):
        fetch_called["n"] += 1
        return pd.DataFrame({
            "date": [date.today()],
            "open": [105.0], "high": [106.0], "low": [104.0],
            "close": [105.5], "volume": [2000],
        })
    monkeypatch.setattr(f._source, "fetch", _stub_fetch)

    f._fetch_ohlcv("AAPL")
    assert fetch_called["n"] == 1


def test_fetch_ohlcv_uses_legacy_buffer_when_not_aware(tmp_path, monkeypatch):
    """When not aware, the legacy 4-day buffer is used regardless of mtime."""
    f = MarketDataFetcher(cache_dir=tmp_path)  # not aware
    cache_path = tmp_path / "AAPL_ohlcv.csv"
    df = pd.DataFrame({
        "date": [date.today() - timedelta(days=1)],  # within 4-day buffer
        "open": [100.0], "high": [101.0], "low": [99.0],
        "close": [100.5], "volume": [1000],
    })
    df.to_csv(cache_path, index=False)
    # mtime irrelevant for legacy path; set to 1 hour ago
    one_hour_ago = time.time() - 60 * 60
    os.utime(cache_path, (one_hour_ago, one_hour_ago))

    def _no_network(*args, **kwargs):
        raise AssertionError("Network call should not happen — within 4-day buffer")
    monkeypatch.setattr(f._source, "fetch", _no_network)

    result = f._fetch_ohlcv("AAPL")
    assert len(result) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/unit/analysis/daily_strategy/test_fetcher_market_hours.py -v
```

Expected: tests FAIL — constructor rejects new kwargs and `_fetch_ohlcv` ignores them.

- [ ] **Step 4: Modify `MarketDataFetcher.__init__`**

Replace the constructor in `src/assethold/analysis/daily_strategy/fetcher.py` (lines 58–83) with:

```python
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        price_cache_ttl_hours: int = 4,
        info_cache_ttl_hours: int = 24,
        history_days: int = 252,
        market_hours_aware: bool = False,
        intraday_ttl_minutes: int = 15,
    ):
        """
        Args:
            cache_dir:               Directory for all cache files. Defaults to
                                     StockDataSource's default (data/stocks/cache).
            price_cache_ttl_hours:   OHLCV cache validity (4h, used outside market hours).
            info_cache_ttl_hours:    Fundamental info cache validity (24h).
            history_days:            Trading days of price history to fetch.
            market_hours_aware:      When True, the OHLCV freshness buffer
                                     switches to intraday_ttl_minutes during
                                     the NYSE regular session.
            intraday_ttl_minutes:    Buffer (minutes) used during the regular
                                     session when market_hours_aware is True.
        """
        self._source = StockDataSource(
            cache_dir=cache_dir,
            cache_ttl_hours=price_cache_ttl_hours,
            market_hours_aware=market_hours_aware,
            intraday_ttl_minutes=intraday_ttl_minutes,
        )
        self._info_ttl = timedelta(hours=info_cache_ttl_hours)
        self._history_days = history_days
        self._market_hours_aware = market_hours_aware
        self._intraday_ttl = timedelta(minutes=intraday_ttl_minutes)
        self._insider = InsiderFetcher(
            cache_dir=self._source.cache_dir,
            cache_ttl_hours=info_cache_ttl_hours,
        )
```

- [ ] **Step 5: Modify `_fetch_ohlcv` freshness check**

In `src/assethold/analysis/daily_strategy/fetcher.py`, replace lines 191–198 (the `if cache_path.exists(): ... return existing` block) with:

```python
        existing: Optional[pd.DataFrame] = None
        if cache_path.exists():
            existing = pd.read_csv(cache_path, parse_dates=["date"])
            existing["date"] = pd.to_datetime(existing["date"]).dt.date
            last_date = existing["date"].max()

            # Intraday-mode freshness: switch to mtime-vs-intraday-TTL
            # when aware AND market is open.
            if self._market_hours_aware:
                from assethold.utils.market_hours import is_market_open
                if is_market_open():
                    mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
                    if datetime.now() - mtime < self._intraday_ttl:
                        return existing
                    # else fall through to fetch
                elif last_date >= today - _dt.timedelta(days=4):
                    return existing
            else:
                # Legacy 4-day buffer: covers weekends and market holidays
                if last_date >= today - _dt.timedelta(days=4):
                    return existing

            fetch_start = (last_date + _dt.timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            start_dt = _dt.date.today() - _dt.timedelta(days=self._history_days + 30)
            fetch_start = start_dt.strftime("%Y-%m-%d")
```

- [ ] **Step 6: Run new + existing fetcher tests to verify no regression**

```bash
.venv/bin/python -m pytest tests/unit/analysis/daily_strategy/ -v
```

If the path doesn't have existing tests, also run a quick smoke check:

```bash
.venv/bin/python -m pytest tests/ -x -q
```

Expected: 4 new tests pass; full suite passes.

- [ ] **Step 7: Commit**

```bash
git add src/assethold/analysis/daily_strategy/fetcher.py tests/unit/analysis/__init__.py tests/unit/analysis/daily_strategy/__init__.py tests/unit/analysis/daily_strategy/test_fetcher_market_hours.py
git commit -m "feat: market-hours-aware OHLCV buffer in MarketDataFetcher (#35)"
```

---

## Task 6: Add `--intraday` CLI flag with fail-loud pre-flight

**Files:**
- Modify: `src/assethold/analysis/daily_strategy/__main__.py:5-17` (CLI docstring)
- Modify: `src/assethold/analysis/daily_strategy/__main__.py:54-71` (argparse)
- Modify: `src/assethold/analysis/daily_strategy/__main__.py:74-105` (main pre-flight)
- Modify: `src/assethold/analysis/daily_strategy/__main__.py:151-161` (fetcher construction)
- Create: `tests/integration/test_daily_strategy_intraday.py`

- [ ] **Step 1: Write the failing integration tests**

Create `tests/integration/test_daily_strategy_intraday.py`:

```python
"""ABOUTME: Integration tests for the --intraday flag in daily_strategy CLI.
ABOUTME: Covers fail-loud-on-Sunday and the no-flag legacy path."""

import subprocess
import sys


REPO = "/mnt/local-analysis/workspace-hub/assethold"


def test_intraday_on_sunday_fails_loud():
    """--intraday on a Sunday must exit 1 with 'next open' in stderr."""
    result = subprocess.run(
        [
            sys.executable, "-m", "assethold.analysis.daily_strategy",
            "--intraday",
            "--date", "2026-04-19",  # Sunday
            "--no-write",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}. stderr={result.stderr}"
    assert "next open" in result.stderr.lower(), f"stderr missing 'next open': {result.stderr}"


def test_no_intraday_flag_does_not_fail_on_sunday():
    """Without --intraday, a Sunday invocation runs to completion (legacy behavior)."""
    result = subprocess.run(
        [
            sys.executable, "-m", "assethold.analysis.daily_strategy",
            "--date", "2026-04-19",  # Sunday
            "--no-write",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,  # legacy path may do real fetches
    )
    # Exit 0 (success) or 0/1 if there's a real network failure — but NOT a market-hours
    # rejection. Specifically, "next open" should NOT appear in stderr.
    assert "next open" not in result.stderr.lower(), (
        f"Legacy path should not check market hours: {result.stderr}"
    )
```

Note: the second test is permissive about exit code (the legacy path may fail for network reasons unrelated to this change); it asserts only that the market-hours pre-flight is NOT triggered.

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/integration/test_daily_strategy_intraday.py -v
```

Expected: `test_intraday_on_sunday_fails_loud` FAILS (the flag doesn't exist yet, so argparse rejects it with exit code 2 — but stderr won't contain "next open").

- [ ] **Step 3: Update CLI docstring**

In `src/assethold/analysis/daily_strategy/__main__.py`, replace lines 5–17 (the `Options:` block in the module docstring) with:

```python
"""
CLI entry point for the daily portfolio strategy.

Usage:
    uv run python -m assethold.analysis.daily_strategy [options]

Options:
    --accounts {all,individual,ira}   Filter to a specific account type (default: all)
    --date YYYY-MM-DD                 Override today's date for the report
    --no-cache                        Bypass market data cache
    --no-write                        Print to terminal only; do not write report files
    --config PATH                     Path to daily_strategy.yaml (default: config/daily_strategy.yaml)
    --compare TICKER[,TICKER...]      Analyse arbitrary tickers alongside portfolio positions.
                                      Tickers are comma-separated (e.g. AAPL,MSFT,NVDA).
                                      When omitted, the watchlist: section in config is used
                                      automatically if non-empty.
    --intraday                        Enable market-hours-aware caching: OHLCV TTL drops to
                                      `intraday_ttl_minutes` (config knob, default 15) during
                                      the NYSE regular session. Fails loud if the market is
                                      closed at invocation time. The --date flag overrides the
                                      report date but NOT the pre-flight check.
"""
```

- [ ] **Step 4: Add the `--intraday` argparse argument**

In `_parse_args` (after the `--compare` argument, before `return parser.parse_args(argv)`), add:

```python
    parser.add_argument(
        "--intraday",
        action="store_true",
        help=(
            "Enable market-hours-aware caching. OHLCV TTL drops to the configured "
            "intraday_ttl_minutes during the NYSE regular session. Fails loud if "
            "the market is closed at invocation time."
        ),
    )
```

- [ ] **Step 5: Add the pre-flight check in `main`**

In `src/assethold/analysis/daily_strategy/__main__.py`, after the `args = _parse_args(...)` line (line 75) and before the `report_date` parsing, add:

```python
    # --intraday pre-flight: fail loud if NYSE regular session is not open NOW
    # (independent of --date, which only controls the report date).
    if args.intraday:
        from assethold.utils.market_hours import is_market_open, next_open
        if not is_market_open():
            try:
                next_open_ts = next_open()
                next_open_str = next_open_ts.strftime("%Y-%m-%d %H:%M %Z")
            except ValueError:
                next_open_str = "unknown"
            print(
                f"ERROR: market is closed. Next open: {next_open_str}",
                file=sys.stderr,
            )
            return 1
```

- [ ] **Step 6: Wire `--intraday` into the fetcher construction**

In `main`, replace the `MarketDataFetcher(...)` construction (lines 153–161) with:

```python
    fetcher = MarketDataFetcher(
        price_cache_ttl_hours=0 if args.no_cache else int(
            config.get("scoring", {}).get("price_cache_ttl_hours", 4)
        ),
        info_cache_ttl_hours=0 if args.no_cache else int(
            config.get("scoring", {}).get("info_cache_ttl_hours", 24)
        ),
        history_days=int(config.get("scoring", {}).get("sma_history_days", 252)),
        market_hours_aware=args.intraday,
        intraday_ttl_minutes=int(
            config.get("scoring", {}).get("intraday_ttl_minutes", 15)
        ),
    )
```

- [ ] **Step 7: Run the integration tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/integration/test_daily_strategy_intraday.py -v
```

Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add src/assethold/analysis/daily_strategy/__main__.py tests/integration/test_daily_strategy_intraday.py
git commit -m "feat: --intraday flag for daily_strategy with fail-loud pre-flight (#35)"
```

---

## Task 7: Add `intraday_ttl_minutes` config knob to `daily_strategy.yaml`

**Files:**
- Modify: `config/daily_strategy.yaml` (under existing `scoring:` block)

- [ ] **Step 1: Inspect current scoring block**

```bash
grep -n -A 10 "^scoring:" config/daily_strategy.yaml
```

Confirm the `scoring:` block contains `price_cache_ttl_hours` (it should be near line 65 per the assessment doc).

- [ ] **Step 2: Add the new knob**

After `price_cache_ttl_hours: 4` in the `scoring:` block, add:

```yaml
  # Intraday TTL (minutes) used by --intraday flag during the NYSE regular session.
  # See docs/reports/2026-04-16-realtime-phase1-design.md.
  intraday_ttl_minutes: 15
```

- [ ] **Step 3: Sanity-check the YAML parses**

```bash
.venv/bin/python -c "
import yaml
with open('config/daily_strategy.yaml') as f:
    cfg = yaml.safe_load(f)
print('intraday_ttl_minutes:', cfg.get('scoring', {}).get('intraday_ttl_minutes'))
"
```

Expected output: `intraday_ttl_minutes: 15`

- [ ] **Step 4: Run full suite to confirm no regressions**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: all tests pass; suite size grew by ~25–35 from baseline 819.

- [ ] **Step 5: Commit**

```bash
git add config/daily_strategy.yaml
git commit -m "config: add intraday_ttl_minutes knob for --intraday flag (#35)"
```

---

## Task 8: Final verification + issue close-out

**Files:** none modified

- [ ] **Step 1: Verify all acceptance criteria from the spec**

```bash
# 1. is_market_open / next_open / next_close exist and pass
.venv/bin/python -m pytest tests/unit/test_market_hours.py -v

# 2. cache.ohlcv_ttl helper present
.venv/bin/python -c "from assethold.modules.stocks.cache import ohlcv_ttl, TTL_OHLCV_INTRADAY; print(TTL_OHLCV_INTRADAY)"
# Expected: 900

# 3. --intraday rejects on Sunday
.venv/bin/python -m assethold.analysis.daily_strategy --intraday --date 2026-04-19 --no-write
echo "Exit: $?"
# Expected: ERROR: market is closed. Next open: <date> ET; Exit: 1

# 4. Default invocation still works (no pandas_market_calendars required at import time)
.venv/bin/python -c "
import sys
# Ensure pandas_market_calendars is NOT imported by the default path
import assethold.analysis.daily_strategy.__main__
assert 'pandas_market_calendars' not in sys.modules
print('Default path does not load pandas_market_calendars at import time: OK')
"

# 5. Full suite green
.venv/bin/python -m pytest tests/ -q
```

- [ ] **Step 2: Push to origin**

```bash
git push origin main
```

- [ ] **Step 3: Comment on issue #35 with summary**

```bash
gh issue comment 35 --repo vamseeachanta/assethold --body "$(cat <<'EOF'
Phase 1 implementation complete.

**Commits (chronological, all on main):**
- `deps: add pandas_market_calendars for NYSE calendar awareness`
- `feat: add utils.market_hours for NYSE regular-session awareness`
- `feat: add cache.ohlcv_ttl() helper for market-hours-aware TTL routing`
- `feat: market-hours-aware TTL in StockDataSource`
- `feat: market-hours-aware OHLCV buffer in MarketDataFetcher`
- `feat: --intraday flag for daily_strategy with fail-loud pre-flight`
- `config: add intraday_ttl_minutes knob for --intraday flag`

**Spec:** `docs/reports/2026-04-16-realtime-phase1-design.md`
**Plan:** `docs/reports/2026-04-16-realtime-phase1-plan.md`

**Notable scope addition discovered during plan-writing:** the original issue body listed only `signals/data_sources.py` for fetcher edits, but `daily_strategy/fetcher.py:_fetch_ohlcv` has its own 4-day-buffer cache that bypasses `StockDataSource`. To actually deliver intraday freshness on the daily-strategy CLI path, that buffer was also switched to honor `is_market_open()`.

**Test suite:** 819 → ~845 (~25 new tests, no live-network).

Closes #35.
EOF
)"
```

- [ ] **Step 4: Close the issue**

```bash
gh issue close 35 --repo vamseeachanta/assethold
```

---

## Spec coverage checklist (writing-plans self-review)

Mapped from spec section 9 (Acceptance criteria) → tasks:

- [x] `is_market_open()` correct for regular hours, holidays, weekends, half-days → **Task 2**
- [x] `cache.ohlcv_ttl(True)` drops to 900 sec during session, stays at 21600 outside → **Task 3**
- [x] `--intraday` succeeds on weekday at 10am ET → **Task 6** (covered by no-flag-legacy-path test asymmetry; the success case is exercised by Task 8 manual verification)
- [x] `--intraday` fails loud on Sunday with `next open` message → **Task 6**
- [x] Default invocation byte-identical (no `pandas_market_calendars` import) → **Task 8** verification step 1.4
- [x] Test suite green; ~25–35 new tests → **Tasks 2–6**, verified in Task 7 step 4
- [x] No new `# TODO` markers → none in any task
- [x] Atomic commits per file edit → each task ends with its own commit

## Out-of-scope reminders (do NOT do these in this plan)

- Pre-market / after-hours support
- Streaming WebSocket (Phase 3 of #34)
- Scheduler daemon (Phase 2 of #34)
- Wiring `market_hours_aware` into `alert_engine`, `trend_detector`, `dashboard` — separate follow-ups after Phase 1 lands
- Configurable bell buffer (Phase 1.5)
