"""Unit tests for cache+fallback wiring in GetStockData.

Verifies that get_daily_data_by_ticker, get_company_data_by_ticker,
get_insider_information, get_options_data, and get_yf_institutions
use the cache/fallback pipeline correctly.
"""

import inspect
import re

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, call

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stock_data_instance():
    """Create a GetStockData instance with minimal cfg."""
    from assethold.modules.stocks.get_stock_data import GetStockData

    cfg = {"data": {"period": "2y"}, "input": {"ticker": "AAPL"}}
    return GetStockData(cfg)


def _sample_ohlcv_df():
    """Return a small OHLCV DataFrame for test assertions."""
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "High": [105.0, 106.0, 107.0, 108.0, 109.0],
            "Low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "Close": [104.0, 105.0, 106.0, 107.0, 108.0],
            "Volume": [1000, 1100, 1200, 1300, 1400],
        }
    )


# ---------------------------------------------------------------------------
# TestGetDailyDataCaching
# ---------------------------------------------------------------------------

class TestGetDailyDataCaching:
    """get_daily_data_by_ticker should route through fetch_with_fallback."""

    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    def test_cache_hit_skips_yfinance_call(self, mock_fwf):
        """When fetch_with_fallback returns cached data, yfinance is not called."""
        cached_df = _sample_ohlcv_df()
        mock_fwf.return_value = cached_df

        instance = _make_stock_data_instance()
        cfg = {"data": {"period": "2y"}}

        with patch("assethold.modules.stocks.get_stock_data.yf") as mock_yf:
            result = instance.get_daily_data_by_ticker(cfg, "AAPL")

        assert result["status"] is True
        pd.testing.assert_frame_equal(result["data"], cached_df)
        mock_yf.Ticker.assert_not_called()

    @patch("assethold.modules.stocks.get_stock_data.finnhub_provider")
    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    @patch("assethold.modules.stocks.get_stock_data.make_cache_key")
    def test_calls_fetch_with_fallback_with_correct_args(
        self, mock_make_key, mock_fwf, mock_finnhub
    ):
        """fetch_with_fallback is called with correct cache_key, TTL, and callables."""
        from assethold.modules.stocks.cache import TTL_OHLCV

        mock_make_key.return_value = "ohlcv:abc123"
        mock_fwf.return_value = _sample_ohlcv_df()
        mock_finnhub.is_available.return_value = True

        instance = _make_stock_data_instance()
        cfg = {"data": {"period": "1y"}}
        instance.get_daily_data_by_ticker(cfg, "MSFT")

        mock_make_key.assert_called_once_with("ohlcv", "MSFT", period="1y")
        args, kwargs = mock_fwf.call_args
        assert args[0] == "ohlcv:abc123"
        assert args[1] == TTL_OHLCV
        # primary_fn and fallback_fn should both be callables
        assert callable(args[2])
        assert callable(args[3])

    @patch("assethold.modules.stocks.get_stock_data.finnhub_provider")
    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    def test_fallback_is_none_when_finnhub_unavailable(self, mock_fwf, mock_finnhub):
        """When finnhub is not available, fallback_fn should be None."""
        mock_fwf.return_value = _sample_ohlcv_df()
        mock_finnhub.is_available.return_value = False

        instance = _make_stock_data_instance()
        cfg = {"data": {"period": "2y"}}
        instance.get_daily_data_by_ticker(cfg, "AAPL")

        args, kwargs = mock_fwf.call_args
        assert args[3] is None  # fallback_fn is None

    @patch("assethold.modules.stocks.get_stock_data.finnhub_provider")
    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    def test_rate_limit_triggers_fallback_chain(self, mock_fwf, mock_finnhub):
        """When fetch_with_fallback raises an error, it propagates up."""

        class YFRateLimitError(Exception):
            """Stand-in for yfinance rate-limit error (yfinance is mocked in conftest)."""

        mock_finnhub.is_available.return_value = True
        mock_fwf.side_effect = YFRateLimitError("rate limited")

        instance = _make_stock_data_instance()
        cfg = {"data": {"period": "2y"}}

        with pytest.raises(YFRateLimitError):
            instance.get_daily_data_by_ticker(cfg, "AAPL")

        # Verify fetch_with_fallback was called (it just propagated the error)
        mock_fwf.assert_called_once()


# ---------------------------------------------------------------------------
# TestGetCompanyDataCaching
# ---------------------------------------------------------------------------

class TestGetCompanyDataCaching:
    """get_company_data_by_ticker should route through fetch_with_fallback."""

    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    def test_cache_hit_returns_cached_info(self, mock_fwf):
        """When fetch_with_fallback returns cached dict, it is wrapped correctly."""
        cached_info = {"longName": "Apple Inc.", "marketCap": 3e12}
        mock_fwf.return_value = cached_info

        instance = _make_stock_data_instance()
        result = instance.get_company_data_by_ticker("AAPL")

        assert result == {"data": cached_info, "status": True}

    @patch("assethold.modules.stocks.get_stock_data.finnhub_provider")
    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    @patch("assethold.modules.stocks.get_stock_data.make_cache_key")
    def test_calls_fetch_with_fallback_with_correct_ttl(
        self, mock_make_key, mock_fwf, mock_finnhub
    ):
        """fetch_with_fallback is called with TTL_COMPANY_INFO."""
        from assethold.modules.stocks.cache import TTL_COMPANY_INFO

        mock_make_key.return_value = "company_info:xyz789"
        mock_fwf.return_value = {"longName": "Test Corp"}
        mock_finnhub.is_available.return_value = True

        instance = _make_stock_data_instance()
        instance.get_company_data_by_ticker("TEST")

        args, _ = mock_fwf.call_args
        assert args[0] == "company_info:xyz789"
        assert args[1] == TTL_COMPANY_INFO
        assert callable(args[2])
        assert callable(args[3])


# ---------------------------------------------------------------------------
# TestGetInsiderInformationCaching
# ---------------------------------------------------------------------------

class TestGetInsiderInformationCaching:
    """get_insider_information should route through fetch_with_fallback."""

    @patch("assethold.modules.stocks.get_stock_data.finnhub_provider")
    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    @patch("assethold.modules.stocks.get_stock_data.make_cache_key")
    def test_calls_fetch_with_fallback_with_correct_ttl(
        self, mock_make_key, mock_fwf, mock_finnhub
    ):
        """fetch_with_fallback is called with TTL_INSIDER."""
        from assethold.modules.stocks.cache import TTL_INSIDER

        mock_make_key.return_value = "insider:abc"
        mock_fwf.return_value = pd.DataFrame()
        mock_finnhub.is_available.return_value = True

        instance = _make_stock_data_instance()
        cfg = {"data": {"period": "2y"}}
        instance.get_insider_information(cfg, "AAPL")

        args, _ = mock_fwf.call_args
        assert args[0] == "insider:abc"
        assert args[1] == TTL_INSIDER

    @patch("assethold.modules.stocks.get_stock_data.finnhub_provider")
    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    def test_original_finviz_plus_sec_still_used_as_primary(
        self, mock_fwf, mock_finnhub
    ):
        """The primary_fn wraps the original finviz+SEC logic."""
        mock_finnhub.is_available.return_value = False
        mock_fwf.return_value = pd.DataFrame({"col": [1, 2]})

        instance = _make_stock_data_instance()
        cfg = {"data": {"period": "2y"}}
        instance.get_insider_information(cfg, "AAPL")

        # Grab the primary_fn that was passed
        args, _ = mock_fwf.call_args
        primary_fn = args[2]

        # Calling the primary should invoke get_insider_information_from_finviz
        # and get_sec_data (we mock them at the instance level)
        instance.get_insider_information_from_finviz = MagicMock(
            return_value=pd.DataFrame()
        )
        instance.get_sec_data = MagicMock(return_value={"sec_form4": []})

        result = primary_fn()
        instance.get_insider_information_from_finviz.assert_called_once_with(cfg, "AAPL")
        instance.get_sec_data.assert_called_once_with("AAPL")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0  # both sources empty -> empty df

    @patch("assethold.modules.stocks.get_stock_data.finnhub_provider")
    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    def test_returns_status_false_for_empty_dataframe(self, mock_fwf, mock_finnhub):
        """When fetch returns empty DataFrame, status should be False."""
        mock_fwf.return_value = pd.DataFrame()
        mock_finnhub.is_available.return_value = False

        instance = _make_stock_data_instance()
        cfg = {"data": {"period": "2y"}}
        result = instance.get_insider_information(cfg, "AAPL")

        assert result["status"] is False
        assert len(result["data"]) == 0


# ---------------------------------------------------------------------------
# TestGetOptionsDataCaching
# ---------------------------------------------------------------------------

class TestGetOptionsDataCaching:
    """get_options_data should use cache with no Finnhub fallback."""

    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    def test_options_data_uses_cache_only(self, mock_fwf):
        """fetch_with_fallback called with fallback_fn=None for options."""
        mock_fwf.return_value = {"2024-06-21": {"calls": [], "puts": []}}

        instance = _make_stock_data_instance()
        instance._current_ticker = "AAPL"
        instance.get_options_data()

        args, kwargs = mock_fwf.call_args
        # cache_key, ttl, primary_fn -- no fallback_fn
        assert len(args) == 3 or (len(args) == 4 and args[3] is None)
        # Verify fallback_fn is not provided or is explicitly None
        if len(args) >= 4:
            assert args[3] is None

    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    def test_options_exception_sets_status_false(self, mock_fwf):
        """When fetch_with_fallback raises, options status is False."""
        mock_fwf.side_effect = Exception("yfinance error")

        instance = _make_stock_data_instance()
        instance._current_ticker = "AAPL"
        instance.get_options_data()

        assert instance.status.get("options") is False
        assert instance.option_data == {}


# ---------------------------------------------------------------------------
# TestGetYfInstitutionsCaching
# ---------------------------------------------------------------------------

class TestGetYfInstitutionsCaching:
    """get_yf_institutions should use cache with no Finnhub fallback."""

    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    def test_institutions_uses_cache_only(self, mock_fwf):
        """fetch_with_fallback called without fallback for institutions."""
        mock_fwf.return_value = {
            "institutional": pd.DataFrame({"holder": ["Vanguard"]}),
            "major": pd.DataFrame({"holder": ["Insiders"]}),
        }

        instance = _make_stock_data_instance()
        instance.get_yf_institutions("AAPL")

        args, kwargs = mock_fwf.call_args
        assert len(args) == 3 or (len(args) == 4 and args[3] is None)

    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    def test_institutions_exception_sets_none(self, mock_fwf):
        """When fetch_with_fallback raises, holders are set to None."""
        mock_fwf.side_effect = Exception("yfinance error")

        instance = _make_stock_data_instance()
        instance.get_yf_institutions("AAPL")

        assert instance.institutional_holders is None
        assert instance.major_holders is None

    @patch("assethold.modules.stocks.get_stock_data.fetch_with_fallback")
    def test_institutions_result_unpacked_correctly(self, mock_fwf):
        """Result dict is unpacked into institutional_holders and major_holders."""
        inst_df = pd.DataFrame({"holder": ["Vanguard"]})
        major_df = pd.DataFrame({"holder": ["Insiders"]})
        mock_fwf.return_value = {"institutional": inst_df, "major": major_df}

        instance = _make_stock_data_instance()
        instance.get_yf_institutions("AAPL")

        pd.testing.assert_frame_equal(instance.institutional_holders, inst_df)
        pd.testing.assert_frame_equal(instance.major_holders, major_df)


# ---------------------------------------------------------------------------
# TestSecurityFix
# ---------------------------------------------------------------------------

class TestSecurityFix:
    """Verify dead code with security issues has been removed."""

    def test_get_data_from_tiingo_removed(self):
        """The get_data_from_tiingo method (hardcoded API key) must not exist."""
        from assethold.modules.stocks.get_stock_data import GetStockData

        assert not hasattr(GetStockData, "get_data_from_tiingo")

    def test_no_hardcoded_api_keys(self):
        """Source file must contain no 40-char hex strings (API key pattern)."""
        import assethold.modules.stocks.get_stock_data as mod

        source = inspect.getsource(mod)
        # Match 40-character hex strings that look like API keys
        matches = re.findall(r"['\"][0-9a-f]{40}['\"]", source)
        assert len(matches) == 0, f"Found potential hardcoded API keys: {matches}"

    def test_dead_code_methods_removed(self):
        """All dead code methods marked for deletion must be gone."""
        from assethold.modules.stocks.get_stock_data import GetStockData

        dead_methods = [
            "get_EOD_data_from_yfinance",
            "get_stock_price_data",
            "get_data_from_tiingo",
            "get_screened_stocks",
            "get_data_from_yfinance",
            "get_data_from_morningstar",
            "get_data_from_iex",
            "get_institutional_holders",
            "get_major_holders",
            "add_rolling_averages_to_df",
        ]
        for method_name in dead_methods:
            assert not hasattr(GetStockData, method_name), (
                f"Dead code method '{method_name}' should have been removed"
            )
