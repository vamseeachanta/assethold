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
