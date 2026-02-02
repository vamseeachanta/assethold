"""Unit tests for the disk caching layer.

Tests cache key generation, cache hit/miss, TTL expiry,
no-op degradation when diskcache is not installed, and
the fetch_with_fallback orchestrator.
"""

import hashlib
import os

import pytest
from unittest.mock import patch, MagicMock, call

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _expected_md5(raw: str) -> str:
    """Compute MD5 hex digest for a raw key string."""
    return hashlib.md5(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# TestMakeCacheKey
# ---------------------------------------------------------------------------

class TestMakeCacheKey:
    """Tests for make_cache_key() deterministic key generation."""

    def test_deterministic_key(self):
        """Same inputs produce the same key every time."""
        from assethold.modules.stocks.cache import make_cache_key

        key1 = make_cache_key("ohlcv", "AAPL", period="1y")
        key2 = make_cache_key("ohlcv", "AAPL", period="1y")
        assert key1 == key2

    def test_different_tickers_different_keys(self):
        """Different ticker symbols produce different keys."""
        from assethold.modules.stocks.cache import make_cache_key

        key_aapl = make_cache_key("ohlcv", "AAPL")
        key_msft = make_cache_key("ohlcv", "MSFT")
        assert key_aapl != key_msft

    def test_kwargs_affect_key(self):
        """Adding kwargs changes the resulting key."""
        from assethold.modules.stocks.cache import make_cache_key

        key_plain = make_cache_key("ohlcv", "AAPL")
        key_with_period = make_cache_key("ohlcv", "AAPL", period="1y")
        assert key_plain != key_with_period

    def test_key_format(self):
        """Key starts with prefix and contains a valid MD5 hex digest."""
        from assethold.modules.stocks.cache import make_cache_key

        key = make_cache_key("ohlcv", "AAPL", period="1y")
        prefix, md5_hex = key.split(":", 1)
        assert prefix == "ohlcv"
        assert len(md5_hex) == 32
        # Verify it is valid hex
        int(md5_hex, 16)

    def test_kwargs_order_independent(self):
        """Kwargs in different order produce the same key (sorted internally)."""
        from assethold.modules.stocks.cache import make_cache_key

        key1 = make_cache_key("ohlcv", "AAPL", period="1y", interval="1d")
        key2 = make_cache_key("ohlcv", "AAPL", interval="1d", period="1y")
        assert key1 == key2


# ---------------------------------------------------------------------------
# TestGetCache
# ---------------------------------------------------------------------------

class TestGetCache:
    """Tests for get_cache() singleton with optional diskcache."""

    def setup_method(self):
        """Reset the module-level singleton before each test."""
        import assethold.modules.stocks.cache as cache_mod
        cache_mod._cache_instance = None
        cache_mod._cache_initialized = False

    def test_returns_cache_instance_when_diskcache_available(self):
        """When diskcache is installed, get_cache() returns a Cache object."""
        mock_cache_cls = MagicMock()
        mock_cache_obj = MagicMock()
        mock_cache_cls.return_value = mock_cache_obj

        mock_diskcache = MagicMock()
        mock_diskcache.Cache = mock_cache_cls

        with patch.dict("sys.modules", {"diskcache": mock_diskcache}):
            from assethold.modules.stocks.cache import get_cache
            result = get_cache()

        assert result is mock_cache_obj
        mock_cache_cls.assert_called_once()

    def test_returns_none_when_diskcache_missing(self):
        """When diskcache is not installed, get_cache() returns None."""
        import assethold.modules.stocks.cache as cache_mod

        with patch.object(cache_mod, "_try_import_diskcache", return_value=None):
            cache_mod._cache_instance = None
            cache_mod._cache_initialized = False
            result = cache_mod.get_cache()

        assert result is None

    def test_respects_env_var_for_cache_dir(self):
        """ASSETHOLD_CACHE_DIR env var overrides the default cache directory."""
        custom_dir = "/tmp/test_assethold_cache"
        mock_cache_cls = MagicMock()
        mock_diskcache = MagicMock()
        mock_diskcache.Cache = mock_cache_cls

        with patch.dict("sys.modules", {"diskcache": mock_diskcache}), \
             patch.dict(os.environ, {"ASSETHOLD_CACHE_DIR": custom_dir}):
            from assethold.modules.stocks.cache import get_cache
            get_cache()

        mock_cache_cls.assert_called_once_with(custom_dir)

    def test_singleton_returns_same_instance(self):
        """Calling get_cache() twice returns the same object."""
        mock_cache_cls = MagicMock()
        mock_cache_obj = MagicMock()
        mock_cache_cls.return_value = mock_cache_obj

        mock_diskcache = MagicMock()
        mock_diskcache.Cache = mock_cache_cls

        with patch.dict("sys.modules", {"diskcache": mock_diskcache}):
            from assethold.modules.stocks.cache import get_cache
            first = get_cache()
            second = get_cache()

        assert first is second
        # Cache constructor called only once
        mock_cache_cls.assert_called_once()


# ---------------------------------------------------------------------------
# TestFetchWithFallback
# ---------------------------------------------------------------------------

class TestFetchWithFallback:
    """Tests for fetch_with_fallback() orchestrator."""

    def setup_method(self):
        """Reset cache singleton before each test."""
        import assethold.modules.stocks.cache as cache_mod
        cache_mod._cache_instance = None
        cache_mod._cache_initialized = False

    def test_cache_hit_returns_cached_value(self):
        """When the key exists in cache, return it without calling primary_fn."""
        from assethold.modules.stocks.cache import fetch_with_fallback

        mock_cache = MagicMock()
        mock_cache.get.return_value = "cached_data"

        primary_fn = MagicMock()

        with patch("assethold.modules.stocks.cache.get_cache", return_value=mock_cache):
            result = fetch_with_fallback("test:key", 3600, primary_fn)

        assert result == "cached_data"
        primary_fn.assert_not_called()

    def test_cache_miss_calls_primary(self):
        """On cache miss, primary_fn is called and result is cached."""
        from assethold.modules.stocks.cache import fetch_with_fallback

        _SENTINEL = object()
        mock_cache = MagicMock()
        mock_cache.get.return_value = _SENTINEL

        primary_fn = MagicMock(return_value="fresh_data")

        with patch("assethold.modules.stocks.cache.get_cache", return_value=mock_cache), \
             patch("assethold.modules.stocks.cache._SENTINEL", _SENTINEL):
            result = fetch_with_fallback("test:key", 3600, primary_fn)

        assert result == "fresh_data"
        primary_fn.assert_called_once()
        mock_cache.set.assert_called_once_with("test:key", "fresh_data", expire=3600)

    def test_primary_failure_calls_fallback(self):
        """When primary_fn raises, fallback_fn is called and result cached."""
        from assethold.modules.stocks.cache import fetch_with_fallback

        _SENTINEL = object()
        mock_cache = MagicMock()
        mock_cache.get.return_value = _SENTINEL

        primary_fn = MagicMock(side_effect=ConnectionError("timeout"))
        fallback_fn = MagicMock(return_value="fallback_data")

        with patch("assethold.modules.stocks.cache.get_cache", return_value=mock_cache), \
             patch("assethold.modules.stocks.cache._SENTINEL", _SENTINEL):
            result = fetch_with_fallback("test:key", 3600, primary_fn, fallback_fn)

        assert result == "fallback_data"
        fallback_fn.assert_called_once()
        mock_cache.set.assert_called_once_with("test:key", "fallback_data", expire=3600)

    def test_both_fail_raises(self):
        """When both primary and fallback fail, the fallback exception is raised."""
        from assethold.modules.stocks.cache import fetch_with_fallback

        _SENTINEL = object()
        mock_cache = MagicMock()
        mock_cache.get.return_value = _SENTINEL

        primary_fn = MagicMock(side_effect=ConnectionError("primary fail"))
        fallback_fn = MagicMock(side_effect=ValueError("fallback fail"))

        with patch("assethold.modules.stocks.cache.get_cache", return_value=mock_cache), \
             patch("assethold.modules.stocks.cache._SENTINEL", _SENTINEL):
            with pytest.raises(ValueError, match="fallback fail"):
                fetch_with_fallback("test:key", 3600, primary_fn, fallback_fn)

    def test_fallback_none_skips_fallback(self):
        """When fallback_fn is None and primary fails, the primary exception is raised."""
        from assethold.modules.stocks.cache import fetch_with_fallback

        _SENTINEL = object()
        mock_cache = MagicMock()
        mock_cache.get.return_value = _SENTINEL

        primary_fn = MagicMock(side_effect=ConnectionError("primary fail"))

        with patch("assethold.modules.stocks.cache.get_cache", return_value=mock_cache), \
             patch("assethold.modules.stocks.cache._SENTINEL", _SENTINEL):
            with pytest.raises(ConnectionError, match="primary fail"):
                fetch_with_fallback("test:key", 3600, primary_fn, fallback_fn=None)

    def test_no_cache_still_works(self):
        """When diskcache is missing (cache=None), primary_fn is called and returns."""
        from assethold.modules.stocks.cache import fetch_with_fallback

        primary_fn = MagicMock(return_value="direct_data")

        with patch("assethold.modules.stocks.cache.get_cache", return_value=None):
            result = fetch_with_fallback("test:key", 3600, primary_fn)

        assert result == "direct_data"
        primary_fn.assert_called_once()

    def test_no_cache_primary_fails_tries_fallback(self):
        """When cache is None and primary fails, fallback is still attempted."""
        from assethold.modules.stocks.cache import fetch_with_fallback

        primary_fn = MagicMock(side_effect=ConnectionError("no connection"))
        fallback_fn = MagicMock(return_value="fallback_data")

        with patch("assethold.modules.stocks.cache.get_cache", return_value=None):
            result = fetch_with_fallback("test:key", 3600, primary_fn, fallback_fn)

        assert result == "fallback_data"
        fallback_fn.assert_called_once()
