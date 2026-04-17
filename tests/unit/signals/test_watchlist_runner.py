"""ABOUTME: Unit tests for WatchlistRunner orchestrator (#39).
ABOUTME: Covers __init__ invariants, _date_range clock injection, run() per-ticker
pipeline, chart rendering, and CLI precedence (--intraday/--no-intraday/config)."""

import logging
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from assethold.signals.watchlist import Watchlist
from assethold.signals.watchlist_runner import (
    WatchlistRunner,
    _build_arg_parser,
    main,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ohlcv_df(rows: int = 60) -> pd.DataFrame:
    """Synthetic uptrend OHLCV frame long enough for TrendDetector (needs >= 51)."""
    dates = pd.date_range("2026-01-01", periods=rows)
    close = [100.0 + i * 0.5 for i in range(rows)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": [c - 0.5 for c in close],
            "high": [c + 1.0 for c in close],
            "low": [c - 1.0 for c in close],
            "close": close,
            "volume": [1_000_000] * rows,
        }
    )


@pytest.fixture
def watchlist_yaml(tmp_path):
    """Minimal watchlist YAML with two tickers and a settings block."""
    path = tmp_path / "watchlist.yml"
    path.write_text(
        """
stocks:
  - ticker: AAPL
    alert_thresholds: {rsi_oversold: 30, rsi_overbought: 70}
    monitoring_frequency: daily
  - ticker: MSFT
    alert_thresholds: {rsi_oversold: 30, rsi_overbought: 70}
    monitoring_frequency: daily

settings:
  default_monitoring_frequency: daily
  cache_ttl_hours: 24
  rate_limit_seconds: 2.0
  market_hours_aware: false
  intraday_ttl_minutes: 15
  lookback_days: 90
""".strip()
    )
    return path


@pytest.fixture
def watchlist(watchlist_yaml):
    return Watchlist(config_path=watchlist_yaml)


@pytest.fixture
def fixed_today():
    return lambda: date(2026, 4, 17)


# ---------------------------------------------------------------------------
# __init__ tests (Group A)
# ---------------------------------------------------------------------------


def test_init_constructs_real_stock_data_source(watchlist, tmp_path):
    """WatchlistRunner builds a real StockDataSource with the passed kwargs."""
    runner = WatchlistRunner(
        watchlist=watchlist,
        market_hours_aware=True,
        intraday_ttl_minutes=15,
        cache_ttl_hours=24,
        cache_dir=tmp_path,
    )
    assert runner._source.market_hours_aware is True
    assert runner._source.intraday_ttl == timedelta(minutes=15)
    assert runner._source.cache_ttl == timedelta(hours=24)


def test_init_raises_if_render_charts_without_dir(watchlist, tmp_path):
    """render_charts=True without charts_output_dir is invalid at construction time."""
    with pytest.raises(ValueError, match="charts_output_dir"):
        WatchlistRunner(
            watchlist=watchlist,
            render_charts=True,
            charts_output_dir=None,
            cache_dir=tmp_path,
        )


def test_init_warns_when_insider_provider_missing(watchlist, tmp_path, caplog):
    """Default construction (no insider provider) logs exactly one WARNING."""
    with caplog.at_level(logging.WARNING, logger="assethold.signals.watchlist_runner"):
        WatchlistRunner(watchlist=watchlist, cache_dir=tmp_path)
    matching = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and "insider_flags_provider" in r.getMessage()
    ]
    assert len(matching) == 1


def test_init_no_warn_when_insider_provider_set(watchlist, tmp_path, caplog):
    """When an insider provider is passed, no WARNING about it should fire."""
    with caplog.at_level(logging.WARNING, logger="assethold.signals.watchlist_runner"):
        WatchlistRunner(
            watchlist=watchlist,
            insider_flags_provider=lambda ticker: [],
            cache_dir=tmp_path,
        )
    matching = [
        r for r in caplog.records if "insider_flags_provider" in r.getMessage()
    ]
    assert matching == []


# ---------------------------------------------------------------------------
# _date_range tests (Group A)
# ---------------------------------------------------------------------------


def test_date_range_uses_today_minus_lookback_days(watchlist, fixed_today, tmp_path):
    """Injected clock drives _date_range deterministically."""
    runner = WatchlistRunner(
        watchlist=watchlist,
        lookback_days=90,
        now=fixed_today,
        cache_dir=tmp_path,
    )
    start, end = runner._date_range()
    assert end == "2026-04-17"
    assert start == "2026-01-17"  # 90 days prior


def test_date_range_custom_lookback(watchlist, fixed_today, tmp_path):
    """Different lookback_days values are honored."""
    runner = WatchlistRunner(
        watchlist=watchlist,
        lookback_days=30,
        now=fixed_today,
        cache_dir=tmp_path,
    )
    start, end = runner._date_range()
    assert end == "2026-04-17"
    assert start == "2026-03-18"


# ---------------------------------------------------------------------------
# run() pipeline tests (Group B)
# ---------------------------------------------------------------------------


def test_run_per_ticker_pipeline(watchlist, fixed_today, tmp_path, monkeypatch):
    """For each ticker, fetch→TrendDetector.analyze→AlertEngine.build_alerts flows end-to-end."""
    calls = []

    def fake_fetch(self, ticker, start_date, end_date, use_cache=True):
        calls.append((ticker, start_date, end_date))
        return _ohlcv_df(60)

    monkeypatch.setattr(
        "assethold.signals.data_sources.StockDataSource.fetch",
        fake_fetch,
        raising=True,
    )

    runner = WatchlistRunner(
        watchlist=watchlist,
        lookback_days=90,
        now=fixed_today,
        cache_dir=tmp_path,
    )
    results = runner.run()

    assert set(results.keys()) == {"AAPL", "MSFT"}
    assert all(isinstance(v, list) for v in results.values())
    # fetch was called once per ticker with correct dates
    assert len(calls) == 2
    for ticker, start, end in calls:
        assert ticker in {"AAPL", "MSFT"}
        assert end == "2026-04-17"
        assert start == "2026-01-17"


def test_run_skips_empty_dataframe(watchlist, fixed_today, tmp_path, monkeypatch):
    """Empty df → results[ticker] = []; no exception."""

    def fake_fetch(self, ticker, start_date, end_date, use_cache=True):
        return pd.DataFrame()

    monkeypatch.setattr(
        "assethold.signals.data_sources.StockDataSource.fetch",
        fake_fetch,
        raising=True,
    )
    runner = WatchlistRunner(
        watchlist=watchlist, now=fixed_today, cache_dir=tmp_path
    )
    results = runner.run()
    assert results == {"AAPL": [], "MSFT": []}


def test_run_skips_none_dataframe(watchlist, fixed_today, tmp_path, monkeypatch):
    """None df → results[ticker] = []; no exception."""

    def fake_fetch(self, ticker, start_date, end_date, use_cache=True):
        return None

    monkeypatch.setattr(
        "assethold.signals.data_sources.StockDataSource.fetch",
        fake_fetch,
        raising=True,
    )
    runner = WatchlistRunner(
        watchlist=watchlist, now=fixed_today, cache_dir=tmp_path
    )
    results = runner.run()
    assert results == {"AAPL": [], "MSFT": []}


def test_run_uses_insider_provider_when_set(
    watchlist, fixed_today, tmp_path, monkeypatch
):
    """If insider_flags_provider is provided, it is invoked per ticker."""
    seen = []

    def fake_fetch(self, ticker, start_date, end_date, use_cache=True):
        return _ohlcv_df(60)

    def provider(ticker):
        seen.append(ticker)
        return [
            {
                "type": "unusual_insider_activity",
                "transaction_date": "2026-04-10",
                "ticker": ticker,
            }
        ]

    monkeypatch.setattr(
        "assethold.signals.data_sources.StockDataSource.fetch",
        fake_fetch,
        raising=True,
    )
    runner = WatchlistRunner(
        watchlist=watchlist,
        insider_flags_provider=provider,
        now=fixed_today,
        cache_dir=tmp_path,
    )
    runner.run()
    assert sorted(seen) == ["AAPL", "MSFT"]


# ---------------------------------------------------------------------------
# Chart rendering tests (Group C)
# ---------------------------------------------------------------------------


def test_run_creates_charts_dir_and_saves_html(
    watchlist, fixed_today, tmp_path, monkeypatch
):
    """render_charts=True writes one HTML file per ticker under charts_output_dir."""
    fetch_calls = []

    def fake_fetch(self, ticker, start_date, end_date, use_cache=True):
        fetch_calls.append(ticker)
        return _ohlcv_df(60)

    monkeypatch.setattr(
        "assethold.signals.data_sources.StockDataSource.fetch",
        fake_fetch,
        raising=True,
    )
    save_calls = []

    def spy_save(fig, output_path, fmt="html"):
        save_calls.append((output_path, fmt))
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("<html>stub</html>")

    monkeypatch.setattr("assethold.signals.dashboard.save_chart", spy_save)

    charts_dir = tmp_path / "charts-out"
    runner = WatchlistRunner(
        watchlist=watchlist,
        render_charts=True,
        charts_output_dir=charts_dir,
        now=fixed_today,
        cache_dir=tmp_path / "cache",
    )
    results = runner.run()
    assert fetch_calls == ["AAPL", "MSFT"], f"fetch not called as expected: {fetch_calls}"
    assert set(results.keys()) == {"AAPL", "MSFT"}, f"results: {results}"
    assert len(save_calls) == 2, f"save_chart call count: {len(save_calls)} — calls: {save_calls}"
    assert (charts_dir / "AAPL.html").exists()
    assert (charts_dir / "MSFT.html").exists()


# ---------------------------------------------------------------------------
# CLI tests (Group D)
# ---------------------------------------------------------------------------


def test_arg_parser_help_lists_all_flags():
    parser = _build_arg_parser()
    help_text = parser.format_help()
    assert "--intraday" in help_text
    assert "--no-intraday" in help_text
    assert "--lookback-days" in help_text
    assert "--render-charts" in help_text
    assert "--charts-dir" in help_text


def test_cli_render_charts_without_dir_exits_2(
    watchlist_yaml, monkeypatch, capsys, tmp_path
):
    """--render-charts without --charts-dir exits 2 with helpful message."""
    monkeypatch.chdir(tmp_path)

    def fake_watchlist_init(self, config_path=None):
        self.config_path = watchlist_yaml
        self._data = None

    monkeypatch.setattr(Watchlist, "__init__", fake_watchlist_init)
    rc = main(["--render-charts"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "--charts-dir" in err


def test_cli_no_flag_falls_back_to_config(
    watchlist_yaml, tmp_path, monkeypatch
):
    """With no CLI flag, market_hours_aware comes from settings."""
    # Patch watchlist to use our fixture YAML
    def fake_watchlist_init(self, config_path=None):
        self.config_path = watchlist_yaml
        self._data = None

    monkeypatch.setattr(Watchlist, "__init__", fake_watchlist_init)

    captured = {}

    class StubRunner:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            return {}

    monkeypatch.setattr(
        "assethold.signals.watchlist_runner.WatchlistRunner", StubRunner
    )
    # override the YAML to have market_hours_aware=true
    watchlist_yaml.write_text(
        watchlist_yaml.read_text().replace(
            "market_hours_aware: false", "market_hours_aware: true"
        )
    )
    rc = main([])
    assert rc == 0
    assert captured["market_hours_aware"] is True


def test_cli_no_intraday_overrides_config_true(
    watchlist_yaml, tmp_path, monkeypatch
):
    """--no-intraday forces market_hours_aware=False even when config says true."""
    watchlist_yaml.write_text(
        watchlist_yaml.read_text().replace(
            "market_hours_aware: false", "market_hours_aware: true"
        )
    )

    def fake_watchlist_init(self, config_path=None):
        self.config_path = watchlist_yaml
        self._data = None

    monkeypatch.setattr(Watchlist, "__init__", fake_watchlist_init)

    captured = {}

    class StubRunner:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            return {}

    monkeypatch.setattr(
        "assethold.signals.watchlist_runner.WatchlistRunner", StubRunner
    )
    rc = main(["--no-intraday"])
    assert rc == 0
    assert captured["market_hours_aware"] is False


def test_cli_intraday_overrides_config_false(
    watchlist_yaml, tmp_path, monkeypatch
):
    """--intraday forces market_hours_aware=True even when config says false.

    Bypasses the market-hours pre-flight by stubbing is_market_open → True.
    """

    def fake_watchlist_init(self, config_path=None):
        self.config_path = watchlist_yaml
        self._data = None

    monkeypatch.setattr(Watchlist, "__init__", fake_watchlist_init)

    # Stub is_market_open to True so the --intraday pre-flight passes
    import assethold.utils.market_hours as mh

    monkeypatch.setattr(mh, "is_market_open", lambda ts=None: True)

    captured = {}

    class StubRunner:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            return {}

    monkeypatch.setattr(
        "assethold.signals.watchlist_runner.WatchlistRunner", StubRunner
    )
    rc = main(["--intraday"])
    assert rc == 0
    assert captured["market_hours_aware"] is True


def test_cli_intraday_fail_loud_outside_market_hours(
    watchlist_yaml, tmp_path, monkeypatch, capsys
):
    """--intraday returns 1 with next-open msg when market is closed."""

    def fake_watchlist_init(self, config_path=None):
        self.config_path = watchlist_yaml
        self._data = None

    monkeypatch.setattr(Watchlist, "__init__", fake_watchlist_init)

    import assethold.utils.market_hours as mh
    from datetime import datetime, timezone

    monkeypatch.setattr(mh, "is_market_open", lambda ts=None: False)
    monkeypatch.setattr(
        mh,
        "next_open",
        lambda ts=None: datetime(2026, 4, 20, 13, 30, tzinfo=timezone.utc),
    )
    rc = main(["--intraday"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "next open" in err.lower()
    assert "wall-clock" in err.lower() or "pre-flight" in err.lower()


def test_cli_lookback_days_override(watchlist_yaml, tmp_path, monkeypatch):
    """--lookback-days overrides config value for runner construction."""

    def fake_watchlist_init(self, config_path=None):
        self.config_path = watchlist_yaml
        self._data = None

    monkeypatch.setattr(Watchlist, "__init__", fake_watchlist_init)

    captured = {}

    class StubRunner:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            return {}

    monkeypatch.setattr(
        "assethold.signals.watchlist_runner.WatchlistRunner", StubRunner
    )
    rc = main(["--lookback-days", "30"])
    assert rc == 0
    assert captured["lookback_days"] == 30


# ---------------------------------------------------------------------------
# Lazy-import invariant (Group E) — subprocess-isolated per plan v2.1
# ---------------------------------------------------------------------------


def test_default_construction_does_not_import_pandas_market_calendars(tmp_path):
    """Fresh Python: importing watchlist_runner + constructing default runner must NOT load pandas_market_calendars."""
    watchlist_yaml = tmp_path / "watchlist.yml"
    watchlist_yaml.write_text(
        "stocks:\n  - ticker: AAPL\n    monitoring_frequency: daily\nsettings:\n  cache_ttl_hours: 24\n"
    )
    cache_dir = tmp_path / "cache"
    probe = (
        "import sys; "
        "from pathlib import Path; "
        "from assethold.signals.watchlist import Watchlist; "
        "from assethold.signals.watchlist_runner import WatchlistRunner; "
        f"wl = Watchlist(config_path=Path(r'{watchlist_yaml}')); "
        f"r = WatchlistRunner(watchlist=wl, market_hours_aware=False, cache_dir=Path(r'{cache_dir}')); "
        "print('pandas_market_calendars' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"probe stderr: {result.stderr}"
    assert result.stdout.strip() == "False", (
        f"expected 'False' (lazy-import preserved), got: {result.stdout!r} "
        f"(stderr: {result.stderr!r})"
    )
