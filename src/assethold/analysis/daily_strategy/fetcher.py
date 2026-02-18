"""
Market data fetcher for daily strategy analysis.

Wraps StockDataSource (OHLCV + cache) and adds fundamental data from
yfinance Ticker.info (P/E, price-to-book, 52-week range).

Fundamental info is cached as a JSON sidecar next to the OHLCV cache with a
longer TTL (24 h by default) because fundamentals update infrequently.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd

try:
    import yfinance as yf  # type: ignore[import]
except ImportError:
    yf = None  # type: ignore[assignment]

from assethold.stocks.data_sources import StockDataSource
from assethold.stocks.indicators import calculate_rsi, calculate_sma
from assethold.analysis.daily_strategy.insider import InsiderFetcher, InsiderTrend


@dataclass
class MarketSnapshot:
    """Current market data for a single ticker."""

    ticker: str
    current_price: float
    week52_high: float
    week52_low: float
    pct_from_52w_low: float    # 0–100 % relative to 52-week range
    pct_from_52w_high: float   # 0–100 % distance below the 52-week high
    rsi_14: Optional[float]
    sma_50: Optional[float]
    sma_200: Optional[float]
    pe_ratio: Optional[float]
    price_to_book: Optional[float]
    insider_trend: Optional[InsiderTrend] = None
    forward_pe: Optional[float] = None
    dividend_yield: Optional[float] = None
    market_cap: Optional[float] = None
    beta: Optional[float] = None
    analyst_rating: Optional[str] = None


class MarketDataFetcher:
    """Fetch OHLCV + fundamentals for a list of tickers."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        price_cache_ttl_hours: int = 4,
        info_cache_ttl_hours: int = 24,
        history_days: int = 252,
    ):
        """
        Args:
            cache_dir:              Directory for all cache files.  Defaults to
                                    StockDataSource's default (data/stocks/cache).
            price_cache_ttl_hours:  OHLCV cache validity (4 h for intraday freshness).
            info_cache_ttl_hours:   Fundamental info cache validity (24 h).
            history_days:           Trading days of price history to fetch for
                                    indicator calculations.
        """
        self._source = StockDataSource(
            cache_dir=cache_dir,
            cache_ttl_hours=price_cache_ttl_hours,
        )
        self._info_ttl = timedelta(hours=info_cache_ttl_hours)
        self._history_days = history_days
        self._insider = InsiderFetcher(
            cache_dir=self._source.cache_dir,
            cache_ttl_hours=info_cache_ttl_hours,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, ticker: str) -> MarketSnapshot:
        """
        Fetch a complete MarketSnapshot for one ticker.

        Args:
            ticker: Upper-case stock symbol (e.g. "BRKB").

        Returns:
            MarketSnapshot with price, indicator, and fundamental data.

        Raises:
            ValueError: If ticker is invalid or data cannot be fetched.
        """
        ticker = ticker.upper().strip()

        price_df = self._fetch_ohlcv(ticker)
        price_df = calculate_rsi(price_df, period=14)
        price_df = calculate_sma(price_df, window=50)
        price_df = calculate_sma(price_df, window=200)

        current_price = float(price_df["close"].iloc[-1])
        rsi_14 = self._last_valid(price_df, "rsi_14")
        sma_50 = self._last_valid(price_df, "sma_50")
        sma_200 = self._last_valid(price_df, "sma_200")

        info = self._fetch_info(ticker)
        week52_high = float(info.get("fiftyTwoWeekHigh") or info.get("52WeekHigh") or current_price)
        week52_low = float(info.get("fiftyTwoWeekLow") or info.get("52WeekLow") or current_price)
        pe_ratio = self._safe_float(info.get("trailingPE"))
        price_to_book = self._safe_float(info.get("priceToBook"))
        forward_pe = self._safe_float(info.get("forwardPE"))
        dividend_yield = self._safe_float(info.get("dividendYield"))
        market_cap = self._safe_float(info.get("marketCap"))
        beta = self._safe_float(info.get("beta"))
        analyst_rating = info.get("recommendationKey") or None
        if analyst_rating is not None:
            analyst_rating = str(analyst_rating)

        price_range = week52_high - week52_low
        pct_from_low = (
            (current_price - week52_low) / price_range * 100 if price_range > 0 else 50.0
        )
        pct_from_high = (
            (week52_high - current_price) / week52_high * 100 if week52_high > 0 else 0.0
        )

        insider_trend = self._insider.fetch(ticker)

        return MarketSnapshot(
            ticker=ticker,
            current_price=current_price,
            week52_high=week52_high,
            week52_low=week52_low,
            pct_from_52w_low=round(pct_from_low, 2),
            pct_from_52w_high=round(pct_from_high, 2),
            rsi_14=rsi_14,
            sma_50=sma_50,
            sma_200=sma_200,
            pe_ratio=pe_ratio,
            price_to_book=price_to_book,
            insider_trend=insider_trend,
            forward_pe=forward_pe,
            dividend_yield=dividend_yield,
            market_cap=market_cap,
            beta=beta,
            analyst_rating=analyst_rating,
        )

    def fetch_batch(self, tickers: list[str]) -> dict[str, Optional[MarketSnapshot]]:
        """
        Fetch snapshots for multiple tickers.

        Returns a dict mapping ticker → MarketSnapshot, or None on error.
        """
        results: dict[str, Optional[MarketSnapshot]] = {}
        for ticker in tickers:
            try:
                results[ticker] = self.fetch(ticker)
            except Exception:
                results[ticker] = None
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_ohlcv(self, ticker: str) -> pd.DataFrame:
        """
        Return OHLCV price history for *ticker*, fetching only the days not
        already stored on disk.

        The persistent cache is a single per-ticker CSV at
        ``{cache_dir}/{ticker}_ohlcv.csv`` that grows by appending new trading
        days.  A 4-day freshness buffer covers weekends and market holidays —
        if the newest stored date is within 4 calendar days of today the file
        is returned as-is without any network call.
        """
        import datetime as _dt

        cache_path = self._source.cache_dir / f"{ticker}_ohlcv.csv"
        today = _dt.date.today()

        existing: Optional[pd.DataFrame] = None
        if cache_path.exists():
            existing = pd.read_csv(cache_path, parse_dates=["date"])
            existing["date"] = pd.to_datetime(existing["date"]).dt.date
            last_date = existing["date"].max()
            # 4-day buffer: Mon sees last Fri (3 days); post-holiday Mon sees Thu (4 days)
            if last_date >= today - _dt.timedelta(days=4):
                return existing
            fetch_start = (last_date + _dt.timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            start_dt = _dt.date.today() - _dt.timedelta(days=self._history_days + 30)
            fetch_start = start_dt.strftime("%Y-%m-%d")

        fetch_end = today.strftime("%Y-%m-%d")

        try:
            new_df = self._source.fetch(ticker, fetch_start, fetch_end, use_cache=False)
            new_df["date"] = pd.to_datetime(new_df["date"]).dt.date
        except (ValueError, ConnectionError):
            # No new trading days (weekend, holiday, or network error) — use what we have
            if existing is not None:
                return existing
            raise

        if existing is not None and not existing.empty:
            combined = pd.concat([existing, new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["date"], keep="last")
            combined = combined.sort_values("date").reset_index(drop=True)
        else:
            combined = new_df

        combined.to_csv(cache_path, index=False)
        return combined

    def _fetch_info(self, ticker: str) -> dict[str, Any]:
        """Return yfinance .info dict, using a JSON sidecar cache."""
        cache_path = self._source.cache_dir / f"{ticker}_info.json"

        if self._is_info_cache_valid(cache_path):
            with open(cache_path) as f:
                return json.load(f)

        if yf is None:
            return {}

        try:
            info = yf.Ticker(ticker).info or {}
            with open(cache_path, "w") as f:
                json.dump(info, f)
            return info
        except Exception:
            return {}

    def _is_info_cache_valid(self, path: Path) -> bool:
        """Return True if the JSON sidecar exists and is within TTL."""
        if not path.exists():
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - mtime < self._info_ttl

    @staticmethod
    def _last_valid(df: pd.DataFrame, col: str) -> Optional[float]:
        """Return the last non-NaN value in a column, or None."""
        if col not in df.columns:
            return None
        series = df[col].dropna()
        return float(series.iloc[-1]) if not series.empty else None

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """Convert a value to float, returning None on failure."""
        if value is None:
            return None
        try:
            result = float(value)
            return result if result == result else None  # NaN check
        except (TypeError, ValueError):
            return None
