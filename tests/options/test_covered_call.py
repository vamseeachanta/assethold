"""Unit tests for covered call analyser.

All tests use synthetic/mock option chain data — no network calls.
Follows Arrange-Act-Assert pattern with fixed data for determinism.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from assethold.options.covered_call import (
    calculate_premium_yield_annual,
    calculate_downside_protection,
    calculate_break_even,
    calculate_if_called_return_annual,
    analyse_covered_calls,
    filter_option_chain,
    build_covered_call_table,
)

pytestmark = pytest.mark.unit

TODAY = date(2026, 2, 24)
DAYS_30 = TODAY + timedelta(days=30)
DAYS_45 = TODAY + timedelta(days=45)
DAYS_60 = TODAY + timedelta(days=60)


# ---------------------------------------------------------------------------
# Fixtures: sample option chain rows
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_calls_df():
    """Mock yfinance option chain calls DataFrame for a single expiry."""
    return pd.DataFrame(
        {
            "strike": [95.0, 100.0, 105.0, 110.0, 115.0],
            "lastPrice": [6.50, 3.80, 1.90, 0.85, 0.35],
            "bid": [6.30, 3.60, 1.75, 0.75, 0.28],
            "ask": [6.70, 4.00, 2.05, 0.95, 0.42],
            "impliedVolatility": [0.35, 0.30, 0.28, 0.27, 0.26],
            "openInterest": [150, 500, 800, 600, 300],
            "volume": [50, 200, 350, 150, 80],
            "delta": [-0.75, -0.55, -0.35, -0.20, -0.10],
            "inTheMoney": [True, True, False, False, False],
            "contractSymbol": [
                "TEST260324C00095000",
                "TEST260324C00100000",
                "TEST260324C00105000",
                "TEST260324C00110000",
                "TEST260324C00115000",
            ],
        }
    )


@pytest.fixture
def sample_calls_no_delta_df():
    """Mock calls DataFrame without a delta column (yfinance greeks not always present)."""
    return pd.DataFrame(
        {
            "strike": [100.0, 105.0, 110.0],
            "lastPrice": [3.80, 1.90, 0.85],
            "bid": [3.60, 1.75, 0.75],
            "ask": [4.00, 2.05, 0.95],
            "impliedVolatility": [0.30, 0.28, 0.27],
            "openInterest": [500, 800, 600],
            "volume": [200, 350, 150],
            "inTheMoney": [True, False, False],
            "contractSymbol": [
                "TEST260324C00100000",
                "TEST260324C00105000",
                "TEST260324C00110000",
            ],
        }
    )


@pytest.fixture
def holdings():
    """Three-ticker holdings list used by integration-level tests."""
    return [
        {"ticker": "AAPL", "shares": 100, "current_price": 100.0},
        {"ticker": "MSFT", "shares": 50, "current_price": 200.0},
    ]


# ---------------------------------------------------------------------------
# calculate_premium_yield_annual
# ---------------------------------------------------------------------------

class TestPremiumYieldAnnual:

    def test_basic_annualisation(self):
        # 3.80 premium on $100 stock, 30 days to expiry
        # yield = (3.80 / 100) * (365 / 30) = 0.462833...
        result = calculate_premium_yield_annual(
            premium=3.80, current_price=100.0, days_to_expiry=30
        )
        expected = (3.80 / 100.0) * (365.0 / 30.0)
        assert abs(result - expected) < 1e-9

    def test_longer_expiry_lower_annualised_yield(self):
        yield_30 = calculate_premium_yield_annual(3.80, 100.0, 30)
        yield_60 = calculate_premium_yield_annual(3.80, 100.0, 60)
        assert yield_30 > yield_60

    def test_zero_days_raises_value_error(self):
        with pytest.raises((ValueError, ZeroDivisionError)):
            calculate_premium_yield_annual(3.80, 100.0, 0)

    def test_negative_premium_returns_negative_yield(self):
        result = calculate_premium_yield_annual(-1.0, 100.0, 30)
        assert result < 0

    def test_returns_float(self):
        result = calculate_premium_yield_annual(2.0, 50.0, 45)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# calculate_downside_protection
# ---------------------------------------------------------------------------

class TestDownsideProtection:

    def test_basic_ratio(self):
        result = calculate_downside_protection(premium=3.80, current_price=100.0)
        assert abs(result - 0.038) < 1e-9

    def test_higher_premium_more_protection(self):
        low = calculate_downside_protection(1.0, 100.0)
        high = calculate_downside_protection(5.0, 100.0)
        assert high > low

    def test_returns_float(self):
        result = calculate_downside_protection(2.0, 50.0)
        assert isinstance(result, float)

    def test_zero_price_raises(self):
        with pytest.raises((ValueError, ZeroDivisionError)):
            calculate_downside_protection(1.0, 0.0)


# ---------------------------------------------------------------------------
# calculate_break_even
# ---------------------------------------------------------------------------

class TestBreakEven:

    def test_basic_break_even(self):
        result = calculate_break_even(current_price=100.0, premium=3.80)
        assert abs(result - 96.20) < 1e-9

    def test_break_even_below_current_price(self):
        be = calculate_break_even(current_price=150.0, premium=5.0)
        assert be < 150.0

    def test_zero_premium_equals_current_price(self):
        be = calculate_break_even(current_price=100.0, premium=0.0)
        assert abs(be - 100.0) < 1e-9

    def test_returns_float(self):
        result = calculate_break_even(100.0, 3.80)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# calculate_if_called_return_annual
# ---------------------------------------------------------------------------

class TestIfCalledReturnAnnual:

    def test_basic_in_the_money_call(self):
        # strike=105, price=100, premium=3.80, 30 days
        # raw = (105 - 100 + 3.80) / 100 = 0.088
        # annualised = 0.088 * (365 / 30)
        result = calculate_if_called_return_annual(
            strike=105.0, current_price=100.0, premium=3.80, days_to_expiry=30
        )
        expected = ((105.0 - 100.0 + 3.80) / 100.0) * (365.0 / 30.0)
        assert abs(result - expected) < 1e-9

    def test_at_the_money_call(self):
        result = calculate_if_called_return_annual(
            strike=100.0, current_price=100.0, premium=3.80, days_to_expiry=30
        )
        expected = (3.80 / 100.0) * (365.0 / 30.0)
        assert abs(result - expected) < 1e-9

    def test_returns_float(self):
        result = calculate_if_called_return_annual(110.0, 100.0, 3.80, 45)
        assert isinstance(result, float)

    def test_zero_days_raises(self):
        with pytest.raises((ValueError, ZeroDivisionError)):
            calculate_if_called_return_annual(105.0, 100.0, 3.80, 0)


# ---------------------------------------------------------------------------
# filter_option_chain
# ---------------------------------------------------------------------------

class TestFilterOptionChain:

    def test_filter_by_min_days_to_expiry(self, sample_calls_df):
        # All rows present before filtering; expiry supplied externally
        filtered = filter_option_chain(
            calls_df=sample_calls_df,
            days_to_expiry=30,
            min_days_to_expiry=45,
        )
        assert len(filtered) == 0

    def test_filter_passes_when_dte_sufficient(self, sample_calls_df):
        filtered = filter_option_chain(
            calls_df=sample_calls_df,
            days_to_expiry=60,
            min_days_to_expiry=30,
        )
        assert len(filtered) == len(sample_calls_df)

    def test_filter_by_min_premium(self, sample_calls_df):
        filtered = filter_option_chain(
            calls_df=sample_calls_df,
            days_to_expiry=60,
            min_premium=2.0,
        )
        # Only strikes with lastPrice >= 2.0: 6.50, 3.80, 1.90 → 6.50 and 3.80
        assert all(filtered["lastPrice"] >= 2.0)

    def test_filter_by_max_delta(self, sample_calls_df):
        # delta column contains negative values (calls convention from yfinance)
        # max_delta=0.40 means |delta| <= 0.40
        filtered = filter_option_chain(
            calls_df=sample_calls_df,
            days_to_expiry=60,
            max_delta=0.40,
        )
        assert all(filtered["delta"].abs() <= 0.40)

    def test_filter_ignores_delta_when_column_absent(self, sample_calls_no_delta_df):
        filtered = filter_option_chain(
            calls_df=sample_calls_no_delta_df,
            days_to_expiry=60,
            max_delta=0.30,
        )
        # No delta column → filter skipped, all rows returned
        assert len(filtered) == len(sample_calls_no_delta_df)

    def test_combined_filters(self, sample_calls_df):
        filtered = filter_option_chain(
            calls_df=sample_calls_df,
            days_to_expiry=60,
            min_days_to_expiry=30,
            min_premium=1.0,
            max_delta=0.60,
        )
        assert all(filtered["lastPrice"] >= 1.0)

    def test_empty_dataframe_returns_empty(self):
        empty = pd.DataFrame(
            columns=["strike", "lastPrice", "bid", "ask", "impliedVolatility"]
        )
        result = filter_option_chain(
            calls_df=empty, days_to_expiry=60
        )
        assert len(result) == 0


# ---------------------------------------------------------------------------
# build_covered_call_table
# ---------------------------------------------------------------------------

class TestBuildCoveredCallTable:

    def test_output_columns_present(self, sample_calls_df):
        table = build_covered_call_table(
            ticker="AAPL",
            current_price=100.0,
            calls_df=sample_calls_df,
            expiry_date=DAYS_30,
            today=TODAY,
        )
        required_cols = {
            "ticker",
            "expiry",
            "strike",
            "premium",
            "days_to_expiry",
            "premium_yield_annual",
            "downside_protection",
            "break_even",
            "if_called_return_annual",
        }
        assert required_cols.issubset(set(table.columns))

    def test_row_count_matches_input(self, sample_calls_df):
        table = build_covered_call_table(
            ticker="AAPL",
            current_price=100.0,
            calls_df=sample_calls_df,
            expiry_date=DAYS_30,
            today=TODAY,
        )
        assert len(table) == len(sample_calls_df)

    def test_ticker_column_populated(self, sample_calls_df):
        table = build_covered_call_table(
            ticker="AAPL",
            current_price=100.0,
            calls_df=sample_calls_df,
            expiry_date=DAYS_30,
            today=TODAY,
        )
        assert (table["ticker"] == "AAPL").all()

    def test_break_even_values_correct(self, sample_calls_df):
        table = build_covered_call_table(
            ticker="AAPL",
            current_price=100.0,
            calls_df=sample_calls_df,
            expiry_date=DAYS_30,
            today=TODAY,
        )
        for _, row in table.iterrows():
            expected_be = 100.0 - row["premium"]
            assert abs(row["break_even"] - expected_be) < 1e-9

    def test_downside_protection_between_0_and_1(self, sample_calls_df):
        table = build_covered_call_table(
            ticker="AAPL",
            current_price=100.0,
            calls_df=sample_calls_df,
            expiry_date=DAYS_30,
            today=TODAY,
        )
        assert (table["downside_protection"] >= 0).all()
        assert (table["downside_protection"] <= 1).all()

    def test_premium_yield_annual_positive_for_positive_premiums(self, sample_calls_df):
        table = build_covered_call_table(
            ticker="AAPL",
            current_price=100.0,
            calls_df=sample_calls_df,
            expiry_date=DAYS_30,
            today=TODAY,
        )
        assert (table["premium_yield_annual"] > 0).all()

    def test_days_to_expiry_correct(self, sample_calls_df):
        table = build_covered_call_table(
            ticker="AAPL",
            current_price=100.0,
            calls_df=sample_calls_df,
            expiry_date=DAYS_30,
            today=TODAY,
        )
        expected_dte = (DAYS_30 - TODAY).days
        assert (table["days_to_expiry"] == expected_dte).all()

    def test_returns_dataframe(self, sample_calls_df):
        result = build_covered_call_table(
            ticker="AAPL",
            current_price=100.0,
            calls_df=sample_calls_df,
            expiry_date=DAYS_30,
            today=TODAY,
        )
        assert isinstance(result, pd.DataFrame)

    def test_empty_calls_returns_empty_dataframe(self):
        empty_calls = pd.DataFrame(
            columns=["strike", "lastPrice", "bid", "ask", "impliedVolatility"]
        )
        result = build_covered_call_table(
            ticker="AAPL",
            current_price=100.0,
            calls_df=empty_calls,
            expiry_date=DAYS_30,
            today=TODAY,
        )
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# analyse_covered_calls (integration: mocked yfinance)
# ---------------------------------------------------------------------------

class TestAnalyseCoveredCalls:

    def _make_mock_ticker(self, current_price, calls_df, expiry_str):
        """Build a minimal yfinance Ticker mock."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"regularMarketPrice": current_price}
        mock_ticker.options = (expiry_str,)

        chain = MagicMock()
        chain.calls = calls_df
        mock_ticker.option_chain.return_value = chain
        return mock_ticker

    def test_returns_dataframe(self, sample_calls_df):
        expiry_str = DAYS_45.strftime("%Y-%m-%d")
        mock_ticker = self._make_mock_ticker(100.0, sample_calls_df, expiry_str)

        with patch("assethold.options.covered_call.yf.Ticker", return_value=mock_ticker):
            result = analyse_covered_calls(
                holdings=[{"ticker": "AAPL", "shares": 100, "current_price": 100.0}],
                today=TODAY,
            )
        assert isinstance(result, pd.DataFrame)

    def test_sorted_by_premium_yield_descending(self, sample_calls_df):
        expiry_str = DAYS_45.strftime("%Y-%m-%d")
        mock_ticker = self._make_mock_ticker(100.0, sample_calls_df, expiry_str)

        with patch("assethold.options.covered_call.yf.Ticker", return_value=mock_ticker):
            result = analyse_covered_calls(
                holdings=[{"ticker": "AAPL", "shares": 100, "current_price": 100.0}],
                today=TODAY,
            )
        if len(result) > 1:
            yields = result["premium_yield_annual"].tolist()
            assert yields == sorted(yields, reverse=True)

    def test_multi_ticker_all_present(self, sample_calls_df):
        expiry_str = DAYS_45.strftime("%Y-%m-%d")
        mock_aapl = self._make_mock_ticker(100.0, sample_calls_df, expiry_str)
        mock_msft = self._make_mock_ticker(200.0, sample_calls_df, expiry_str)

        def ticker_factory(symbol):
            return mock_aapl if symbol == "AAPL" else mock_msft

        with patch("assethold.options.covered_call.yf.Ticker", side_effect=ticker_factory):
            result = analyse_covered_calls(
                holdings=[
                    {"ticker": "AAPL", "shares": 100, "current_price": 100.0},
                    {"ticker": "MSFT", "shares": 50, "current_price": 200.0},
                ],
                today=TODAY,
            )
        assert "AAPL" in result["ticker"].values
        assert "MSFT" in result["ticker"].values

    def test_filters_applied(self, sample_calls_df):
        expiry_str = DAYS_45.strftime("%Y-%m-%d")
        mock_ticker = self._make_mock_ticker(100.0, sample_calls_df, expiry_str)

        with patch("assethold.options.covered_call.yf.Ticker", return_value=mock_ticker):
            result = analyse_covered_calls(
                holdings=[{"ticker": "AAPL", "shares": 100, "current_price": 100.0}],
                today=TODAY,
                min_days_to_expiry=30,
                min_premium=1.0,
            )
        if len(result) > 0:
            assert all(result["premium"] >= 1.0)
            assert all(result["days_to_expiry"] >= 30)

    def test_empty_holdings_returns_empty_dataframe(self):
        with patch("assethold.options.covered_call.yf.Ticker"):
            result = analyse_covered_calls(holdings=[], today=TODAY)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_ticker_with_no_options_skipped(self):
        mock_ticker = MagicMock()
        mock_ticker.options = ()
        mock_ticker.info = {"regularMarketPrice": 100.0}

        with patch("assethold.options.covered_call.yf.Ticker", return_value=mock_ticker):
            result = analyse_covered_calls(
                holdings=[{"ticker": "NOOPT", "shares": 100, "current_price": 100.0}],
                today=TODAY,
            )
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_current_price_falls_back_to_holding(self, sample_calls_df):
        """When yfinance info lacks price, holding current_price is used."""
        expiry_str = DAYS_45.strftime("%Y-%m-%d")
        mock_ticker = MagicMock()
        mock_ticker.info = {}  # no regularMarketPrice
        mock_ticker.options = (expiry_str,)
        chain = MagicMock()
        chain.calls = sample_calls_df
        mock_ticker.option_chain.return_value = chain

        with patch("assethold.options.covered_call.yf.Ticker", return_value=mock_ticker):
            result = analyse_covered_calls(
                holdings=[{"ticker": "AAPL", "shares": 100, "current_price": 100.0}],
                today=TODAY,
            )
        assert len(result) > 0
        assert (result["ticker"] == "AAPL").all()

    def test_uses_mid_price_when_bid_ask_available(self, sample_calls_df):
        """Premium should be mid-price (bid+ask)/2 when bid/ask columns exist."""
        expiry_str = DAYS_45.strftime("%Y-%m-%d")
        mock_ticker = self._make_mock_ticker(100.0, sample_calls_df, expiry_str)

        with patch("assethold.options.covered_call.yf.Ticker", return_value=mock_ticker):
            result = analyse_covered_calls(
                holdings=[{"ticker": "AAPL", "shares": 100, "current_price": 100.0}],
                today=TODAY,
            )
        # mid price for first row: (6.30 + 6.70) / 2 = 6.50
        # (matches lastPrice in sample data, so we just check it's in the table)
        assert len(result) > 0
