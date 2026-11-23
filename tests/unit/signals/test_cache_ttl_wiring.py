"""ABOUTME: Regression tests for issue #42 — settings.cache_ttl_hours wiring.
ABOUTME: Asserts watchlist.yml:settings.cache_ttl_hours reaches
StockDataSource.cache_ttl via watchlist_runner.main, plus a TTL-boundary
stale/fresh flip on a controlled-mtime cache file. No network access."""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from assethold.signals.data_sources import StockDataSource
from assethold.signals.watchlist import Watchlist
from assethold.signals import watchlist_runner
from assethold.signals.watchlist_runner import main


def _write_watchlist(path: Path, cache_ttl_hours: int) -> Path:
    path.write_text(
        "stocks:\n"
        "  - ticker: AAPL\n"
        "    monitoring_frequency: daily\n"
        "settings:\n"
        f"  cache_ttl_hours: {cache_ttl_hours}\n"
    )
    return path


def test_settings_cache_ttl_hours_reaches_source_via_main(tmp_path, monkeypatch):
    """settings.cache_ttl_hours in watchlist.yml -> runner._source.cache_ttl.

    Acceptance criterion for #42: modifying settings.cache_ttl_hours in a test
    YAML is reflected in the runner's self._source.cache_ttl. We capture the
    real WatchlistRunner that main() constructs and read its source.
    """
    yaml_path = _write_watchlist(tmp_path / "watchlist.yml", cache_ttl_hours=7)

    # Point the default Watchlist() at our temp YAML.
    def fake_init(self, config_path=None):
        self.config_path = yaml_path
        self._data = None

    monkeypatch.setattr(Watchlist, "__init__", fake_init)

    # Capture the real runner without executing its (network-touching) run().
    captured = {}
    RealRunner = watchlist_runner.WatchlistRunner

    class CapturingRunner(RealRunner):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured["runner"] = self

        def run(self):
            return {}

    monkeypatch.setattr(watchlist_runner, "WatchlistRunner", CapturingRunner)

    rc = main([])
    assert rc == 0
    assert captured["runner"]._source.cache_ttl == timedelta(hours=7)


def test_settings_default_preserved_when_absent(tmp_path, monkeypatch):
    """Missing settings.cache_ttl_hours falls back to the 24h default."""
    yaml_path = tmp_path / "watchlist.yml"
    yaml_path.write_text(
        "stocks:\n  - ticker: AAPL\n    monitoring_frequency: daily\n"
    )

    def fake_init(self, config_path=None):
        self.config_path = yaml_path
        self._data = None

    monkeypatch.setattr(Watchlist, "__init__", fake_init)

    captured = {}
    RealRunner = watchlist_runner.WatchlistRunner

    class CapturingRunner(RealRunner):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured["runner"] = self

        def run(self):
            return {}

    monkeypatch.setattr(watchlist_runner, "WatchlistRunner", CapturingRunner)

    rc = main([])
    assert rc == 0
    assert captured["runner"]._source.cache_ttl == timedelta(hours=24)


def test_cache_freshness_flips_at_ttl_boundary(tmp_path):
    """A cached file's stale/fresh decision flips at the cache_ttl boundary.

    No network: we hand-write a cache file and set its mtime, then assert
    _is_cache_valid honors cache_ttl (derived from cache_ttl_hours).
    """
    source = StockDataSource(cache_dir=tmp_path, cache_ttl_hours=10)
    assert source.cache_ttl == timedelta(hours=10)

    cache_file = tmp_path / "AAPL_deadbeef.csv"
    cache_file.write_text("date,open,high,low,close,volume\n")

    now = datetime.now()

    # 9h old -> within 10h TTL -> fresh (valid).
    fresh_mtime = (now - timedelta(hours=9)).timestamp()
    os.utime(cache_file, (fresh_mtime, fresh_mtime))
    assert source._is_cache_valid(cache_file) is True

    # 11h old -> beyond 10h TTL -> stale (invalid).
    stale_mtime = (now - timedelta(hours=11)).timestamp()
    os.utime(cache_file, (stale_mtime, stale_mtime))
    assert source._is_cache_valid(cache_file) is False


def test_smaller_ttl_makes_same_file_stale(tmp_path):
    """Lowering cache_ttl_hours re-classifies the same cache file as stale."""
    cache_file = tmp_path / "AAPL_deadbeef.csv"
    cache_file.write_text("date,open,high,low,close,volume\n")
    five_h_ago = (datetime.now() - timedelta(hours=5)).timestamp()
    os.utime(cache_file, (five_h_ago, five_h_ago))

    fresh_source = StockDataSource(cache_dir=tmp_path, cache_ttl_hours=24)
    stale_source = StockDataSource(cache_dir=tmp_path, cache_ttl_hours=1)

    assert fresh_source._is_cache_valid(cache_file) is True
    assert stale_source._is_cache_valid(cache_file) is False
