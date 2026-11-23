"""
Unit tests for InsiderFetcher and InsiderTrend.

All yfinance calls are mocked; no network or SEC access required.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Register a yfinance stub before the module is imported.
if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = MagicMock()

from assethold.analysis.daily_strategy.insider import (  # noqa: E402
    InsiderFetcher,
    InsiderTrend,
    _BUY_TYPES,
    _SELL_TYPES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fetcher(tmp_path: Path, window_days: int = 90) -> InsiderFetcher:
    return InsiderFetcher(cache_dir=tmp_path, cache_ttl_hours=24, window_days=window_days)


def _tx_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal transactions DataFrame from a list of row dicts."""
    return pd.DataFrame(rows)


def _recent_date(days_ago: int = 10) -> str:
    """ISO date string N days before today."""
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def _old_date(days_ago: int = 120) -> str:
    """ISO date string well outside the 90-day window."""
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# _classify_trend
# ---------------------------------------------------------------------------


class TestClassifyTrend:
    def test_no_transactions_is_neutral(self):
        assert InsiderFetcher._classify_trend(0, 0) == "NEUTRAL"

    def test_only_buys_is_bullish(self):
        assert InsiderFetcher._classify_trend(3, 0) == "BULLISH"

    def test_only_sells_is_bearish(self):
        assert InsiderFetcher._classify_trend(0, 4) == "BEARISH"

    def test_buys_dominate_twox_is_bullish(self):
        # buys >= sells * 2
        assert InsiderFetcher._classify_trend(4, 2) == "BULLISH"

    def test_sells_dominate_twox_is_bearish(self):
        # sells >= buys * 2
        assert InsiderFetcher._classify_trend(2, 4) == "BEARISH"

    def test_balanced_is_mixed(self):
        assert InsiderFetcher._classify_trend(2, 3) == "MIXED"

    def test_exactly_2x_ratio_buys(self):
        assert InsiderFetcher._classify_trend(6, 3) == "BULLISH"

    def test_exactly_2x_ratio_sells(self):
        assert InsiderFetcher._classify_trend(3, 6) == "BEARISH"


# ---------------------------------------------------------------------------
# _build_summary
# ---------------------------------------------------------------------------


class TestBuildSummary:
    def test_no_transactions(self):
        s = InsiderFetcher._build_summary(0, 0, 0.0, None)
        assert "No open-market transactions" in s

    def test_single_buy(self):
        s = InsiderFetcher._build_summary(1, 0, 0.0, None)
        assert "1 open-market buy" in s

    def test_plural_buys(self):
        s = InsiderFetcher._build_summary(3, 0, 0.0, None)
        assert "3 open-market buys" in s

    def test_single_sell(self):
        s = InsiderFetcher._build_summary(0, 1, 0.0, None)
        assert "1 open-market sell" in s

    def test_plural_sells(self):
        s = InsiderFetcher._build_summary(0, 2, 0.0, None)
        assert "2 open-market sells" in s

    def test_net_shares_positive(self):
        s = InsiderFetcher._build_summary(2, 0, 1000.0, None)
        assert "net bought" in s
        assert "1,000" in s

    def test_net_shares_negative(self):
        s = InsiderFetcher._build_summary(0, 1, -500.0, None)
        assert "net sold" in s
        assert "500" in s

    def test_days_ago_included(self):
        s = InsiderFetcher._build_summary(1, 0, 100.0, 15)
        assert "15d ago" in s

    def test_days_ago_none_excluded(self):
        s = InsiderFetcher._build_summary(1, 0, 0.0, None)
        assert "ago" not in s


# ---------------------------------------------------------------------------
# _find_col
# ---------------------------------------------------------------------------


class TestFindCol:
    def test_first_candidate_found(self):
        df = pd.DataFrame({"Start Date": [], "Shares": []})
        assert InsiderFetcher._find_col(df, ["Start Date", "Date"]) == "Start Date"

    def test_second_candidate_found(self):
        df = pd.DataFrame({"Date": [], "Shares": []})
        assert InsiderFetcher._find_col(df, ["Start Date", "Date"]) == "Date"

    def test_no_candidate_returns_none(self):
        df = pd.DataFrame({"Foo": []})
        assert InsiderFetcher._find_col(df, ["Date", "Start Date"]) is None


# ---------------------------------------------------------------------------
# fetch() — empty / missing data
# ---------------------------------------------------------------------------


class TestFetchEmptyData:
    def test_returns_na_when_yfinance_returns_none(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=None):
            trend = fetcher.fetch("VOO")
        assert trend.trend == "N/A"
        assert trend.ticker == "VOO"
        assert trend.buys_90d == 0
        assert trend.sells_90d == 0

    def test_returns_na_when_yfinance_returns_empty_df(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=pd.DataFrame()):
            trend = fetcher.fetch("VOO")
        assert trend.trend == "N/A"

    def test_ticker_normalised_to_upper(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=None):
            trend = fetcher.fetch("voo")
        assert trend.ticker == "VOO"

    def test_na_trend_has_descriptive_summary(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=None):
            trend = fetcher.fetch("VOO")
        assert len(trend.summary) > 0


# ---------------------------------------------------------------------------
# fetch() — with transaction data
# ---------------------------------------------------------------------------


class TestFetchWithData:
    def _tx(self, action: str, shares: int, days_ago: int = 10) -> dict:
        return {
            "Start Date": _recent_date(days_ago),
            "Type": action,
            "Shares": shares,
        }

    def test_only_buys_returns_bullish(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        df = _tx_df([self._tx("Buy", 100), self._tx("Buy", 200)])
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=df):
            trend = fetcher.fetch("BRKB")
        assert trend.trend == "BULLISH"
        assert trend.buys_90d == 2
        assert trend.sells_90d == 0

    def test_only_sells_returns_bearish(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        df = _tx_df([self._tx("Sale", 300), self._tx("Sell", 100)])
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=df):
            trend = fetcher.fetch("XOM")
        assert trend.trend == "BEARISH"
        assert trend.buys_90d == 0
        assert trend.sells_90d == 2

    def test_mixed_with_more_sells_returns_bearish(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        df = _tx_df([
            self._tx("Buy", 100),
            self._tx("Sale", 500),
            self._tx("Sale", 500),
        ])
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=df):
            trend = fetcher.fetch("XOM")
        assert trend.trend == "BEARISH"

    def test_mixed_balanced_returns_mixed(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        df = _tx_df([
            self._tx("Buy", 100),
            self._tx("Buy", 100),
            self._tx("Sale", 100),
            self._tx("Sale", 100),
            self._tx("Sale", 100),
        ])
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=df):
            trend = fetcher.fetch("XOM")
        assert trend.trend == "MIXED"

    def test_net_shares_computed(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        df = _tx_df([self._tx("Buy", 500), self._tx("Sale", 200)])
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=df):
            trend = fetcher.fetch("BRKB")
        assert trend.net_shares_90d == pytest.approx(300.0)

    def test_old_transactions_excluded_from_window(self, tmp_path):
        fetcher = _make_fetcher(tmp_path, window_days=90)
        df = _tx_df([
            {"Start Date": _old_date(120), "Type": "Buy", "Shares": 1000},
            {"Start Date": _recent_date(10), "Type": "Sale", "Shares": 50},
        ])
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=df):
            trend = fetcher.fetch("BRKB")
        # Old buy should be excluded; only recent sell counts
        assert trend.buys_90d == 0
        assert trend.sells_90d == 1

    def test_grant_type_ignored(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        df = _tx_df([
            self._tx("Grant", 1000),
            self._tx("Option Exercise", 500),
            self._tx("Award", 200),
        ])
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=df):
            trend = fetcher.fetch("BRKB")
        assert trend.buys_90d == 0
        assert trend.sells_90d == 0
        assert trend.trend == "NEUTRAL"

    def test_last_activity_days_computed(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        df = _tx_df([self._tx("Buy", 100, days_ago=5)])
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=df):
            trend = fetcher.fetch("BRKB")
        assert trend.last_activity_days is not None
        assert 4 <= trend.last_activity_days <= 6  # allow ±1 for timing

    def test_purchase_keyword_classified_as_buy(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        df = _tx_df([self._tx("Purchase", 100)])
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=df):
            trend = fetcher.fetch("BRKB")
        assert trend.buys_90d == 1

    def test_unrecognised_column_names_returns_na(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        # DataFrame with no recognisable date or type columns
        df = pd.DataFrame({"x": ["Buy"], "y": ["2025-01-01"]})
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=df):
            trend = fetcher.fetch("XOM")
        assert trend.trend == "N/A"


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------


class TestCache:
    def _insider_rows(self) -> list[dict]:
        return [{"Start Date": _recent_date(5), "Type": "Buy", "Shares": 100}]

    def test_valid_cache_avoids_yfinance(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        # Pre-populate cache
        cache_path = tmp_path / "BRKB_insider.json"
        df = _tx_df(self._insider_rows())
        cache_path.write_text(df.to_json(orient="records", date_format="iso"))

        mock_yf = MagicMock()
        with patch("assethold.analysis.daily_strategy.insider.yf", mock_yf, create=True):
            trend = fetcher.fetch("BRKB")

        mock_yf.Ticker.assert_not_called()
        assert trend.trend == "BULLISH"

    def test_stale_cache_triggers_refresh(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        cache_path = tmp_path / "BRKB_insider.json"
        df = _tx_df(self._insider_rows())
        cache_path.write_text(df.to_json(orient="records", date_format="iso"))
        # Age the cache file to 25 hours old
        old_mtime = (datetime.now() - timedelta(hours=25)).timestamp()
        os.utime(cache_path, (old_mtime, old_mtime))

        # Fresh yfinance returns sells-only → BEARISH
        fresh_df = _tx_df([{"Start Date": _recent_date(3), "Type": "Sale", "Shares": 200}])
        mock_ticker = MagicMock()
        mock_ticker.insider_transactions = fresh_df
        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        with patch("assethold.analysis.daily_strategy.insider.yf", mock_yf, create=True):
            trend = fetcher.fetch("BRKB")

        assert trend.trend == "BEARISH"

    def test_no_cache_dir_still_works(self):
        fetcher = InsiderFetcher(cache_dir=None)
        df = _tx_df([{"Start Date": _recent_date(5), "Type": "Buy", "Shares": 100}])
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=df):
            trend = fetcher.fetch("BRKB")
        assert trend.trend == "BULLISH"

    def test_cache_path_is_none_when_no_cache_dir(self):
        fetcher = InsiderFetcher(cache_dir=None)
        assert fetcher._cache_path("BRKB") is None

    def test_cache_is_written_after_fetch(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        df = _tx_df(self._insider_rows())
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=df):
            fetcher.fetch("BRKB")
        cache_path = tmp_path / "BRKB_insider.json"
        assert cache_path.exists()


# ---------------------------------------------------------------------------
# InsiderTrend dataclass
# ---------------------------------------------------------------------------


class TestInsiderTrend:
    def test_fields_accessible(self):
        t = InsiderTrend(
            ticker="XOM",
            buys_90d=2,
            sells_90d=1,
            net_shares_90d=500.0,
            trend="BULLISH",
            last_activity_days=7,
            summary="2 open-market buys; last activity 7d ago",
        )
        assert t.ticker == "XOM"
        assert t.buys_90d == 2
        assert t.sells_90d == 1
        assert t.net_shares_90d == 500.0
        assert t.trend == "BULLISH"
        assert t.last_activity_days == 7


# ---------------------------------------------------------------------------
# Type constants sanity
# ---------------------------------------------------------------------------


def test_buy_type_keywords():
    assert "buy" in _BUY_TYPES
    assert "purchase" in _BUY_TYPES


def test_sell_type_keywords():
    assert "sell" in _SELL_TYPES
    assert "sale" in _SELL_TYPES
