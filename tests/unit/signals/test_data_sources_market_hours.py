"""ABOUTME: Unit tests for StockDataSource market-hours-aware TTL behavior.
ABOUTME: Verifies constructor kwargs and per-call TTL switching in _is_cache_valid."""

import os
import time
from datetime import timedelta

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
