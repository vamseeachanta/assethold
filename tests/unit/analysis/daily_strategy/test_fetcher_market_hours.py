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
