"""Disk caching layer for stock data with optional diskcache dependency.

All operations degrade gracefully to no-ops when diskcache is not installed.
"""

import hashlib
import logging
import os
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TTL Constants (seconds)
# ---------------------------------------------------------------------------
TTL_OHLCV = 6 * 3600  # 6 hours
TTL_COMPANY_INFO = 24 * 3600  # 24 hours
TTL_INSIDER = 7 * 86400  # 7 days
TTL_OPTIONS = 4 * 3600  # 4 hours
TTL_INSTITUTIONS = 30 * 86400  # 30 days

# ---------------------------------------------------------------------------
# Sentinel for cache miss detection
# ---------------------------------------------------------------------------
_SENTINEL = object()

# ---------------------------------------------------------------------------
# Singleton state
# ---------------------------------------------------------------------------
_cache_instance = None
_cache_initialized = False


def _try_import_diskcache():
    """Attempt to import diskcache and return the module, or None."""
    try:
        import diskcache
        return diskcache
    except ImportError:
        return None


def get_cache():
    """Return a diskcache.Cache singleton, or None if diskcache is unavailable.

    The cache directory defaults to ``~/.assethold/cache`` but can be
    overridden via the ``ASSETHOLD_CACHE_DIR`` environment variable.
    """
    global _cache_instance, _cache_initialized

    if _cache_initialized:
        return _cache_instance

    diskcache = _try_import_diskcache()
    if diskcache is None:
        logger.debug("diskcache not installed; caching disabled")
        _cache_initialized = True
        _cache_instance = None
        return None

    cache_dir = os.environ.get(
        "ASSETHOLD_CACHE_DIR",
        os.path.expanduser("~/.assethold/cache"),
    )
    _cache_instance = diskcache.Cache(cache_dir)
    _cache_initialized = True
    return _cache_instance


def make_cache_key(prefix: str, ticker: str, **kwargs: Any) -> str:
    """Build a deterministic cache key from prefix, ticker, and kwargs.

    Parameters
    ----------
    prefix : str
        Logical namespace (e.g. ``"ohlcv"``, ``"company_info"``).
    ticker : str
        Stock ticker symbol.
    **kwargs
        Additional discriminators sorted by key for determinism.

    Returns
    -------
    str
        ``"{prefix}:{md5_hex}"`` where the MD5 is computed over the
        full ``prefix:ticker:k1=v1:k2=v2`` raw string.
    """
    parts = [prefix, ticker]
    for k in sorted(kwargs):
        parts.append(f"{k}={kwargs[k]}")
    raw = ":".join(parts)
    md5_hex = hashlib.md5(raw.encode()).hexdigest()
    return f"{prefix}:{md5_hex}"


def fetch_with_fallback(
    cache_key: str,
    ttl: int,
    primary_fn: Callable[[], Any],
    fallback_fn: Optional[Callable[[], Any]] = None,
) -> Any:
    """Fetch data with caching, primary source, and optional fallback.

    1. Check cache (if available) -- return on hit.
    2. Call *primary_fn* -- cache and return on success.
    3. On primary failure, call *fallback_fn* (if provided) -- cache and return.
    4. If everything fails, raise the last exception.

    Parameters
    ----------
    cache_key : str
        Key produced by :func:`make_cache_key`.
    ttl : int
        Time-to-live in seconds for cached entries.
    primary_fn : callable
        Zero-arg callable that fetches fresh data.
    fallback_fn : callable or None
        Zero-arg callable used when *primary_fn* fails.

    Returns
    -------
    Any
        The fetched (or cached) data.

    Raises
    ------
    Exception
        The exception from *fallback_fn* (if provided and both fail),
        or from *primary_fn* (if no fallback).
    """
    cache = get_cache()

    # 1. Cache lookup
    if cache is not None:
        cached = cache.get(cache_key, default=_SENTINEL)
        if cached is not _SENTINEL:
            logger.debug("Cache hit for %s", cache_key)
            return cached

    # 2. Primary fetch
    try:
        result = primary_fn()
    except Exception as primary_exc:
        # 3. Fallback
        if fallback_fn is not None:
            logger.warning(
                "Primary fetch failed for %s (%s), trying fallback",
                cache_key,
                primary_exc,
            )
            result = fallback_fn()  # let this raise if it fails
            if cache is not None:
                cache.set(cache_key, result, expire=ttl)
            return result
        raise
    else:
        if cache is not None:
            cache.set(cache_key, result, expire=ttl)
        return result
