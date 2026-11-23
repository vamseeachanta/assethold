"""
Stock data acquisition from Yahoo Finance with local caching.
"""

import hashlib
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class StockDataSource:
    """Fetch stock data from Yahoo Finance with local file cache."""

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

    def _get_cache_path(self, ticker: str, start_date: str, end_date: str) -> Path:
        """Generate cache file path for given ticker and date range."""
        cache_key = f"{ticker}_{start_date}_{end_date}"
        # sha256 (not for security) + 16 hex chars (64 bits) to keep the
        # collision probability negligible across per-ticker/date-range
        # entries; an 8-hex (32-bit) digest collides at ~50% by ~80k entries.
        cache_hash = hashlib.sha256(
            cache_key.encode(), usedforsecurity=False
        ).hexdigest()[:16]
        return self.cache_dir / f"{ticker}_{cache_hash}.csv"

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

    def _apply_rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    def fetch(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            use_cache: Whether to use cached data if available

        Returns:
            DataFrame with columns: date, open, high, low, close, volume

        Raises:
            ValueError: If ticker is invalid or dates are malformed
            ConnectionError: If network request fails
        """
        ticker = ticker.upper().strip()
        if not ticker:
            raise ValueError("Ticker symbol cannot be empty")

        # Validate date format
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format, use YYYY-MM-DD: {e}")

        cache_path = self._get_cache_path(ticker, start_date, end_date)

        # Try cache first
        if use_cache and self._is_cache_valid(cache_path):
            df = pd.read_csv(cache_path, parse_dates=["date"])
            return df

        # Fetch from Yahoo Finance
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError(
                "yfinance library is required. Install with: pip install yfinance"
            )

        self._apply_rate_limit()

        try:
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)

            if df.empty:
                raise ValueError(f"No data returned for ticker {ticker}")

            # Standardize column names
            df = df.reset_index()
            df = df.rename(
                columns={
                    "Date": "date",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )

            # Keep only required columns
            df = df[["date", "open", "high", "low", "close", "volume"]]

            # Cache the result
            df.to_csv(cache_path, index=False)

            return df

        except Exception as e:
            raise ConnectionError(f"Failed to fetch data for {ticker}: {e}")

    def fetch_batch(
        self,
        tickers: list[str],
        start_date: str,
        end_date: str,
        use_cache: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch data for multiple tickers with rate limiting.

        Args:
            tickers: List of ticker symbols
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            use_cache: Whether to use cached data if available

        Returns:
            Dictionary mapping ticker to DataFrame
        """
        results = {}
        for ticker in tickers:
            try:
                results[ticker] = self.fetch(ticker, start_date, end_date, use_cache)
            except (ValueError, ConnectionError) as e:
                # Log error but continue with other tickers. Surfacing the
                # bound exception lets callers distinguish a delisted ticker
                # from a transient network failure.
                logger.warning("fetch failed for %s: %s", ticker, e)
                results[ticker] = None
        return results

    def clear_cache(self, ticker: Optional[str] = None) -> int:
        """
        Clear cache files.

        Args:
            ticker: Clear only files for this ticker (None = clear all)

        Returns:
            Number of files deleted
        """
        if ticker is None:
            pattern = "*.csv"
        else:
            pattern = f"{ticker.upper()}_*.csv"

        deleted = 0
        for cache_file in self.cache_dir.glob(pattern):
            cache_file.unlink()
            deleted += 1
        return deleted
