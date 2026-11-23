"""
Insider transaction trend analysis.

Fetches SEC Form 4 filings via yfinance, classifies open-market buys and
sells, and summarises the trend for the last 90 days.

Transaction type classification:
    Bullish (open-market conviction):  "Buy", "Purchase"
    Bearish (open-market selling):     "Sell", "Sale"
    Neutral (compensation/noise):      "Grant", "Option Exercise", "Gift", "Award"

ETFs (like VOO) have no corporate insiders — trend is returned as "N/A".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd

try:
    import yfinance as yf  # type: ignore[import]
except ImportError:
    yf = None  # type: ignore[assignment]


# Open-market transaction type keywords
_BUY_TYPES = frozenset({"buy", "purchase"})
_SELL_TYPES = frozenset({"sell", "sale"})

# Default lookback window (days)
_DEFAULT_WINDOW_DAYS = 90


@dataclass
class InsiderTrend:
    """Summary of recent insider transaction activity."""

    ticker: str
    buys_90d: int            # number of open-market buy transactions
    sells_90d: int           # number of open-market sell transactions
    net_shares_90d: float    # shares bought minus shares sold (open-market only)
    trend: str               # BULLISH | BEARISH | MIXED | NEUTRAL | N/A
    last_activity_days: Optional[int]   # days since most recent transaction
    summary: str             # human-readable one-liner


class InsiderFetcher:
    """Fetch and summarise insider transaction trends for a ticker."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        cache_ttl_hours: int = 24,
        window_days: int = _DEFAULT_WINDOW_DAYS,
    ):
        """
        Args:
            cache_dir:        Directory for JSON sidecar cache files.
            cache_ttl_hours:  How long cached insider data is considered fresh.
            window_days:      Lookback window for recent-activity classification.
        """
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._window_days = window_days
        self._cache_dir = cache_dir

    def fetch(self, ticker: str) -> InsiderTrend:
        """
        Return an InsiderTrend for the given ticker.

        Gracefully returns trend="N/A" for ETFs or when data is unavailable.
        """
        ticker = ticker.upper().strip()
        raw = self._get_transactions(ticker)

        if raw is None or raw.empty:
            return InsiderTrend(
                ticker=ticker,
                buys_90d=0,
                sells_90d=0,
                net_shares_90d=0.0,
                trend="N/A",
                last_activity_days=None,
                summary="No insider transaction data available (ETF or data unavailable).",
            )

        return self._summarise(ticker, raw)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_transactions(self, ticker: str) -> Optional[pd.DataFrame]:
        """Return raw insider transaction DataFrame, using cache when valid."""
        cache_path = self._cache_path(ticker)

        if cache_path and self._is_cache_valid(cache_path):
            return self._load_cache(cache_path)

        df = self._fetch_from_yfinance(ticker)

        if cache_path is not None and df is not None and not df.empty:
            self._save_cache(df, cache_path)

        return df

    def _fetch_from_yfinance(self, ticker: str) -> Optional[pd.DataFrame]:
        """Call yfinance to get insider transactions DataFrame."""
        if yf is None:
            return None
        try:
            t = yf.Ticker(ticker)
            df = t.insider_transactions
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                return None
            return df
        except Exception:
            return None

    def _summarise(self, ticker: str, df: pd.DataFrame) -> InsiderTrend:
        """Compute trend metrics from a raw transactions DataFrame."""
        df = df.copy()

        # Normalise column names (yfinance may vary across versions)
        df.columns = [str(c).strip() for c in df.columns]

        # Find date column (may be "Start Date", "startDate", "Date")
        date_col = self._find_col(df, ["Start Date", "startDate", "Date", "date"])
        type_col = self._find_col(df, ["Type", "type", "Transaction", "transaction"])
        shares_col = self._find_col(df, ["Shares", "shares", "#Shares", "Value"])

        if not date_col or not type_col:
            return InsiderTrend(
                ticker=ticker,
                buys_90d=0,
                sells_90d=0,
                net_shares_90d=0.0,
                trend="N/A",
                last_activity_days=None,
                summary="Insider data format unrecognised.",
            )

        # Parse dates
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])

        # Compute days since last transaction
        now = datetime.now()
        cutoff = now - timedelta(days=self._window_days)

        if df[date_col].dt.tz is not None:
            cutoff_ts = pd.Timestamp(cutoff).tz_localize(df[date_col].dt.tz)
        else:
            cutoff_ts = pd.Timestamp(cutoff)

        recent = df[df[date_col] >= cutoff_ts].copy()

        last_activity_days: Optional[int] = None
        if not df.empty:
            latest = df[date_col].max()
            if pd.notna(latest):
                delta = now - latest.replace(tzinfo=None)
                last_activity_days = delta.days

        # Classify rows
        type_lower = recent[type_col].astype(str).str.lower().str.strip()
        is_buy = type_lower.apply(lambda t: any(k in t for k in _BUY_TYPES))
        is_sell = type_lower.apply(lambda t: any(k in t for k in _SELL_TYPES))

        buy_rows = recent[is_buy]
        sell_rows = recent[is_sell]

        buys_90d = len(buy_rows)
        sells_90d = len(sell_rows)

        # Net shares (open-market only)
        # Guard: filtering an empty DataFrame with an empty boolean mask can drop
        # all columns in some pandas backends (ArrowStringArray), so verify the
        # column still exists before accessing it.
        net_shares = 0.0
        if shares_col and shares_col in buy_rows.columns:
            buy_shares = pd.to_numeric(buy_rows[shares_col], errors="coerce").fillna(0).sum()
            sell_shares = pd.to_numeric(sell_rows[shares_col], errors="coerce").fillna(0).sum()
            net_shares = float(buy_shares - sell_shares)

        trend = self._classify_trend(buys_90d, sells_90d)
        summary = self._build_summary(buys_90d, sells_90d, net_shares, last_activity_days)

        return InsiderTrend(
            ticker=ticker,
            buys_90d=buys_90d,
            sells_90d=sells_90d,
            net_shares_90d=net_shares,
            trend=trend,
            last_activity_days=last_activity_days,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _cache_path(self, ticker: str) -> Optional[Path]:
        if self._cache_dir is None:
            return None
        return self._cache_dir / f"{ticker}_insider.json"

    def _is_cache_valid(self, path: Path) -> bool:
        if not path.exists():
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    @staticmethod
    def _load_cache(path: Path) -> Optional[pd.DataFrame]:
        try:
            data = json.loads(path.read_text())
            return pd.DataFrame(data)
        except Exception:
            return None

    @staticmethod
    def _save_cache(df: pd.DataFrame, path: Path) -> None:
        try:
            path.write_text(df.to_json(orient="records", date_format="iso"))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_trend(buys: int, sells: int) -> str:
        if buys == 0 and sells == 0:
            return "NEUTRAL"
        if buys > 0 and sells == 0:
            return "BULLISH"
        if sells > 0 and buys == 0:
            return "BEARISH"
        # Both present
        if buys >= sells * 2:
            return "BULLISH"
        if sells >= buys * 2:
            return "BEARISH"
        return "MIXED"

    @staticmethod
    def _find_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
        """Return first matching column name from a list of candidates."""
        for c in candidates:
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _build_summary(buys: int, sells: int, net_shares: float, days_ago: Optional[int]) -> str:
        parts = []
        if buys > 0:
            parts.append(f"{buys} open-market buy{'s' if buys > 1 else ''}")
        if sells > 0:
            parts.append(f"{sells} open-market sell{'s' if sells > 1 else ''}")
        if not parts:
            parts.append("No open-market transactions")
        summary = "; ".join(parts)
        if net_shares != 0:
            direction = "net bought" if net_shares > 0 else "net sold"
            summary += f" ({direction} {abs(net_shares):,.0f} shares)"
        if days_ago is not None:
            summary += f"; last activity {days_ago}d ago"
        return summary
