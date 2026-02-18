"""
Unit tests for MarketDataFetcher.

All yfinance and network calls are mocked; no real market data is used.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Register a yfinance stub before any module under test is imported, so that
# lazy "import yfinance as yf" inside fetcher._fetch_info does not fail on
# systems where yfinance is not installed.
if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = MagicMock()

from assethold.analysis.daily_strategy.fetcher import MarketDataFetcher, MarketSnapshot  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _price_df(n: int = 220, base: float = 300.0) -> pd.DataFrame:
    """Return a synthetic OHLCV DataFrame suitable for indicator calculation."""
    dates = pd.date_range("2024-01-01", periods=n)
    close = [base + i * 0.1 for i in range(n)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": [c - 1.0 for c in close],
            "high": [c + 2.0 for c in close],
            "low": [c - 2.0 for c in close],
            "close": close,
            "volume": [1_000_000] * n,
        }
    )


def _info_dict(**overrides) -> dict:
    defaults = {
        "trailingPE": 20.5,
        "priceToBook": 1.8,
        "fiftyTwoWeekHigh": 350.0,
        "fiftyTwoWeekLow": 250.0,
    }
    defaults.update(overrides)
    return defaults


def _make_fetcher(tmp_path: Path) -> MarketDataFetcher:
    return MarketDataFetcher(
        cache_dir=tmp_path,
        price_cache_ttl_hours=4,
        info_cache_ttl_hours=24,
        history_days=220,
    )


# ---------------------------------------------------------------------------
# MarketSnapshot construction
# ---------------------------------------------------------------------------


class TestFetchSnapshot:
    def test_returns_market_snapshot(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with (
            patch.object(fetcher._source, "fetch", return_value=_price_df()),
            patch.object(fetcher, "_fetch_info", return_value=_info_dict()),
        ):
            snap = fetcher.fetch("BRKB")

        assert isinstance(snap, MarketSnapshot)
        assert snap.ticker == "BRKB"

    def test_current_price_is_last_close(self, tmp_path):
        df = _price_df(n=220, base=300.0)
        fetcher = _make_fetcher(tmp_path)
        with (
            patch.object(fetcher._source, "fetch", return_value=df),
            patch.object(fetcher, "_fetch_info", return_value=_info_dict()),
        ):
            snap = fetcher.fetch("BRKB")

        assert snap.current_price == pytest.approx(df["close"].iloc[-1])

    def test_ticker_normalised_to_upper(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with (
            patch.object(fetcher._source, "fetch", return_value=_price_df()),
            patch.object(fetcher, "_fetch_info", return_value=_info_dict()),
        ):
            snap = fetcher.fetch("brkb")

        assert snap.ticker == "BRKB"

    def test_52_week_range_from_info(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with (
            patch.object(fetcher._source, "fetch", return_value=_price_df()),
            patch.object(
                fetcher,
                "_fetch_info",
                return_value=_info_dict(fiftyTwoWeekHigh=400.0, fiftyTwoWeekLow=200.0),
            ),
        ):
            snap = fetcher.fetch("BRKB")

        assert snap.week52_high == pytest.approx(400.0)
        assert snap.week52_low == pytest.approx(200.0)

    def test_pct_from_52w_low_calculation(self, tmp_path):
        # current_price = last close of _price_df(base=300) ≈ 321.9
        df = _price_df(n=220, base=300.0)
        current = df["close"].iloc[-1]
        fetcher = _make_fetcher(tmp_path)
        with (
            patch.object(fetcher._source, "fetch", return_value=df),
            patch.object(
                fetcher,
                "_fetch_info",
                return_value=_info_dict(fiftyTwoWeekHigh=400.0, fiftyTwoWeekLow=200.0),
            ),
        ):
            snap = fetcher.fetch("BRKB")

        expected = (current - 200.0) / (400.0 - 200.0) * 100
        assert snap.pct_from_52w_low == pytest.approx(expected, abs=0.01)

    def test_rsi_computed(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with (
            patch.object(fetcher._source, "fetch", return_value=_price_df()),
            patch.object(fetcher, "_fetch_info", return_value=_info_dict()),
        ):
            snap = fetcher.fetch("BRKB")

        assert snap.rsi_14 is not None
        assert 0.0 <= snap.rsi_14 <= 100.0

    def test_sma_50_computed(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with (
            patch.object(fetcher._source, "fetch", return_value=_price_df()),
            patch.object(fetcher, "_fetch_info", return_value=_info_dict()),
        ):
            snap = fetcher.fetch("BRKB")

        assert snap.sma_50 is not None
        assert snap.sma_50 > 0

    def test_pe_ratio_from_info(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with (
            patch.object(fetcher._source, "fetch", return_value=_price_df()),
            patch.object(fetcher, "_fetch_info", return_value=_info_dict(trailingPE=25.3)),
        ):
            snap = fetcher.fetch("BRKB")

        assert snap.pe_ratio == pytest.approx(25.3)

    def test_missing_pe_gives_none(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with (
            patch.object(fetcher._source, "fetch", return_value=_price_df()),
            patch.object(
                fetcher, "_fetch_info", return_value=_info_dict(trailingPE=None)
            ),
        ):
            snap = fetcher.fetch("BRKB")

        assert snap.pe_ratio is None


# ---------------------------------------------------------------------------
# Batch fetch
# ---------------------------------------------------------------------------


class TestFetchBatch:
    def test_batch_returns_all_tickers(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with (
            patch.object(fetcher._source, "fetch", return_value=_price_df()),
            patch.object(fetcher, "_fetch_info", return_value=_info_dict()),
        ):
            results = fetcher.fetch_batch(["BRKB", "XOM"])

        assert set(results.keys()) == {"BRKB", "XOM"}

    def test_batch_error_returns_none_for_that_ticker(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)

        def _side_effect(ticker, *args, **kwargs):
            if ticker == "FAIL":
                raise ConnectionError("network error")
            return _price_df()

        with (
            patch.object(fetcher._source, "fetch", side_effect=_side_effect),
            patch.object(fetcher, "_fetch_info", return_value=_info_dict()),
        ):
            results = fetcher.fetch_batch(["BRKB", "FAIL"])

        assert results["BRKB"] is not None
        assert results["FAIL"] is None


# ---------------------------------------------------------------------------
# Info cache
# ---------------------------------------------------------------------------


class TestInfoCache:
    def test_info_cache_hit_avoids_yfinance(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        info = _info_dict()
        cache_path = tmp_path / "BRKB_info.json"
        cache_path.write_text(json.dumps(info))

        # Patch the yf name inside the fetcher module to detect if it's called.
        mock_yf = MagicMock()
        with patch("assethold.analysis.daily_strategy.fetcher.yf", mock_yf, create=True):
            result = fetcher._fetch_info("BRKB")

        mock_yf.Ticker.assert_not_called()
        assert result["trailingPE"] == info["trailingPE"]

    def test_stale_info_cache_triggers_refresh(self, tmp_path):
        import os

        fetcher = _make_fetcher(tmp_path)
        cache_path = tmp_path / "BRKB_info.json"
        cache_path.write_text(json.dumps(_info_dict()))
        # Make the file appear 25 hours old.
        old_mtime = (datetime.now() - timedelta(hours=25)).timestamp()
        os.utime(cache_path, (old_mtime, old_mtime))

        fresh_info = _info_dict(trailingPE=99.0)
        mock_ticker = MagicMock()
        mock_ticker.info = fresh_info
        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        with patch("assethold.analysis.daily_strategy.fetcher.yf", mock_yf, create=True):
            result = fetcher._fetch_info("BRKB")

        assert result["trailingPE"] == pytest.approx(99.0)

    def test_yfinance_error_returns_empty_dict(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        mock_ticker = MagicMock()
        mock_ticker.info = None
        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        with patch("assethold.analysis.daily_strategy.fetcher.yf", mock_yf, create=True):
            result = fetcher._fetch_info("BRKB")

        # Should not crash; returns empty dict.
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Incremental OHLCV cache (_fetch_ohlcv)
# ---------------------------------------------------------------------------


import datetime as _dt


class TestFetchOhlcv:
    """_fetch_ohlcv fetches only days not already stored on disk."""

    def _fresh_df(self, days: int = 252, base: float = 300.0) -> pd.DataFrame:
        """Generate a synthetic OHLCV frame with `days` rows ending today."""
        end = _dt.date.today()
        dates = [end - _dt.timedelta(days=i) for i in range(days - 1, -1, -1)]
        closes = [base + i * 0.1 for i in range(days)]
        return pd.DataFrame(
            {
                "date": dates,
                "open": [c - 1 for c in closes],
                "high": [c + 2 for c in closes],
                "low": [c - 2 for c in closes],
                "close": closes,
                "volume": [1_000_000] * days,
            }
        )

    def test_no_cache_fetches_full_history(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        expected = _price_df()
        with patch.object(fetcher._source, "fetch", return_value=expected) as mock_fetch:
            result = fetcher._fetch_ohlcv("BRKB")

        mock_fetch.assert_called_once()
        assert len(result) == len(expected)

    def test_no_cache_saves_csv(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with patch.object(fetcher._source, "fetch", return_value=_price_df()):
            fetcher._fetch_ohlcv("BRKB")

        assert (tmp_path / "BRKB_ohlcv.csv").exists()

    def test_fresh_cache_skips_network(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        # Write a CSV whose newest row is today.
        df = self._fresh_df(days=252)
        df.to_csv(tmp_path / "BRKB_ohlcv.csv", index=False)

        with patch.object(fetcher._source, "fetch") as mock_fetch:
            result = fetcher._fetch_ohlcv("BRKB")

        mock_fetch.assert_not_called()
        assert len(result) == 252

    def test_stale_cache_fetches_only_delta(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        today = _dt.date.today()
        # Cache ends 10 days ago.
        cutoff = today - _dt.timedelta(days=10)
        old_df = self._fresh_df(days=252)
        old_df["date"] = pd.to_datetime(old_df["date"]).dt.date
        old_df = old_df[old_df["date"] <= cutoff].copy()
        old_df.to_csv(tmp_path / "BRKB_ohlcv.csv", index=False)

        new_rows = self._fresh_df(days=10)  # the missing 10 days
        with patch.object(fetcher._source, "fetch", return_value=new_rows) as mock_fetch:
            result = fetcher._fetch_ohlcv("BRKB")

        # fetch was called with start = cutoff + 1 day
        call_args = mock_fetch.call_args
        start_arg = call_args[0][1]  # second positional arg
        expected_start = (cutoff + _dt.timedelta(days=1)).strftime("%Y-%m-%d")
        assert start_arg == expected_start

        # Result contains the combined data (no duplicates)
        assert len(result) == len(old_df) + len(new_rows)

    def test_stale_cache_deduplicates_overlapping_rows(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        today = _dt.date.today()
        cutoff = today - _dt.timedelta(days=5)

        old_df = self._fresh_df(days=252)
        old_df["date"] = pd.to_datetime(old_df["date"]).dt.date
        old_df = old_df[old_df["date"] <= cutoff].copy()
        old_df.to_csv(tmp_path / "BRKB_ohlcv.csv", index=False)

        # new_rows overlaps the last day of old_df with an updated close price
        overlap_row = old_df.iloc[[-1]].copy()
        overlap_row["date"] = cutoff
        overlap_row["close"] = 999.0
        extra_row = self._fresh_df(days=1)
        new_rows = pd.concat([overlap_row, extra_row], ignore_index=True)

        with patch.object(fetcher._source, "fetch", return_value=new_rows):
            result = fetcher._fetch_ohlcv("BRKB")

        # The overlapping date should appear exactly once with the updated price
        dup = result[result["date"] == cutoff]
        assert len(dup) == 1
        assert float(dup["close"].iloc[0]) == pytest.approx(999.0)

    def test_weekend_or_holiday_returns_existing(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        today = _dt.date.today()
        # Cache ends 6 days ago (stale enough to trigger a fetch attempt)
        cutoff = today - _dt.timedelta(days=6)
        old_df = self._fresh_df(days=252)
        old_df["date"] = pd.to_datetime(old_df["date"]).dt.date
        old_df = old_df[old_df["date"] <= cutoff].copy()
        old_df.to_csv(tmp_path / "BRKB_ohlcv.csv", index=False)

        # Simulate weekend / holiday: source raises ValueError ("no data")
        with patch.object(
            fetcher._source, "fetch", side_effect=ValueError("No data returned")
        ):
            result = fetcher._fetch_ohlcv("BRKB")

        # Should return existing data without crashing
        assert len(result) == len(old_df)

    def test_no_cache_network_error_propagates(self, tmp_path):
        fetcher = _make_fetcher(tmp_path)
        with patch.object(
            fetcher._source, "fetch", side_effect=ConnectionError("network")
        ):
            with pytest.raises(ConnectionError):
                fetcher._fetch_ohlcv("BRKB")

    def test_full_fetch_uses_use_cache_false(self, tmp_path):
        """_fetch_ohlcv bypasses StockDataSource's own cache."""
        fetcher = _make_fetcher(tmp_path)
        with patch.object(fetcher._source, "fetch", return_value=_price_df()) as mock_fetch:
            fetcher._fetch_ohlcv("BRKB")

        assert mock_fetch.call_args.kwargs.get("use_cache") is False
