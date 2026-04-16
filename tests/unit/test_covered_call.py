# ABOUTME: Unit tests for the covered call options analysis module.
# ABOUTME: Covers scalar calculators, chain filtering, table building, and edge cases.

from datetime import date

import pandas as pd
import pytest

from assethold.options.covered_call import (
    calculate_premium_yield_annual,
    calculate_downside_protection,
    calculate_break_even,
    calculate_if_called_return_annual,
    filter_option_chain,
    build_covered_call_table,
)


# ---------------------------------------------------------------------------
# Scalar calculator tests
# ---------------------------------------------------------------------------

class TestCalculatePremiumYieldAnnual:
    """Tests for the annualised premium yield calculator."""

    def test_basic_calculation(self):
        # premium=5, price=100, 30 DTE => (5/100)*(365/30) = 0.6083
        result = calculate_premium_yield_annual(5.0, 100.0, 30)
        assert result == pytest.approx(0.6083, rel=1e-3)

    def test_one_year_dte(self):
        # premium=10, price=200, 365 DTE => (10/200)*(365/365) = 0.05
        result = calculate_premium_yield_annual(10.0, 200.0, 365)
        assert result == pytest.approx(0.05)

    def test_zero_dte_raises(self):
        with pytest.raises(ValueError, match="days_to_expiry must be non-zero"):
            calculate_premium_yield_annual(5.0, 100.0, 0)

    def test_zero_price_raises(self):
        with pytest.raises(ZeroDivisionError):
            calculate_premium_yield_annual(5.0, 0.0, 30)

    def test_zero_premium_returns_zero(self):
        result = calculate_premium_yield_annual(0.0, 100.0, 30)
        assert result == pytest.approx(0.0)


class TestCalculateDownsideProtection:
    """Tests for the downside protection calculator."""

    def test_basic_calculation(self):
        # premium=3, price=150 => 0.02
        result = calculate_downside_protection(3.0, 150.0)
        assert result == pytest.approx(0.02)

    def test_zero_price_raises(self):
        with pytest.raises(ValueError, match="current_price must be non-zero"):
            calculate_downside_protection(5.0, 0.0)

    def test_zero_premium(self):
        result = calculate_downside_protection(0.0, 100.0)
        assert result == pytest.approx(0.0)


class TestCalculateBreakEven:
    """Tests for the break-even price calculator."""

    def test_basic_calculation(self):
        assert calculate_break_even(150.0, 5.0) == pytest.approx(145.0)

    def test_zero_premium(self):
        assert calculate_break_even(200.0, 0.0) == pytest.approx(200.0)

    def test_large_premium(self):
        # Premium can theoretically exceed price for deep ITM
        assert calculate_break_even(100.0, 110.0) == pytest.approx(-10.0)


class TestCalculateIfCalledReturnAnnual:
    """Tests for the annualised if-called return calculator."""

    def test_otm_strike(self):
        # strike=105, price=100, premium=3, 30 DTE
        # raw = (105-100+3)/100 = 0.08
        # annualised = 0.08 * (365/30) = 0.9733
        result = calculate_if_called_return_annual(105.0, 100.0, 3.0, 30)
        assert result == pytest.approx(0.9733, rel=1e-3)

    def test_atm_strike(self):
        # strike=100, price=100, premium=5, 365 DTE => (0+5)/100 * 1 = 0.05
        result = calculate_if_called_return_annual(100.0, 100.0, 5.0, 365)
        assert result == pytest.approx(0.05)

    def test_itm_strike_negative_return(self):
        # strike=90, price=100, premium=2, 30 DTE
        # raw = (90-100+2)/100 = -0.08 => annualised negative
        result = calculate_if_called_return_annual(90.0, 100.0, 2.0, 30)
        assert result < 0

    def test_zero_dte_raises(self):
        with pytest.raises(ValueError, match="days_to_expiry must be non-zero"):
            calculate_if_called_return_annual(105.0, 100.0, 3.0, 0)


# ---------------------------------------------------------------------------
# Filter helper tests
# ---------------------------------------------------------------------------

class TestFilterOptionChain:
    """Tests for the option chain filter function."""

    @pytest.fixture()
    def sample_chain(self) -> pd.DataFrame:
        return pd.DataFrame({
            "strike": [95.0, 100.0, 105.0, 110.0],
            "lastPrice": [8.0, 5.0, 2.5, 0.5],
            "bid": [7.5, 4.8, 2.3, 0.3],
            "ask": [8.5, 5.2, 2.7, 0.7],
        })

    def test_no_filter_returns_all(self, sample_chain):
        result = filter_option_chain(sample_chain, days_to_expiry=30)
        assert len(result) == 4

    def test_min_premium_filter(self, sample_chain):
        result = filter_option_chain(sample_chain, days_to_expiry=30, min_premium=3.0)
        assert len(result) == 2
        assert list(result["strike"]) == [95.0, 100.0]

    def test_dte_below_minimum_returns_empty(self, sample_chain):
        result = filter_option_chain(
            sample_chain, days_to_expiry=5, min_days_to_expiry=30
        )
        assert len(result) == 0

    def test_empty_dataframe_returns_empty(self):
        empty = pd.DataFrame(columns=["strike", "lastPrice"])
        result = filter_option_chain(empty, days_to_expiry=30)
        assert len(result) == 0

    def test_max_delta_filter(self):
        chain = pd.DataFrame({
            "strike": [100.0, 105.0, 110.0],
            "lastPrice": [5.0, 3.0, 1.0],
            "delta": [0.60, 0.40, 0.20],
        })
        result = filter_option_chain(chain, days_to_expiry=30, max_delta=0.45)
        assert len(result) == 2

    def test_delta_column_absent_ignores_max_delta(self, sample_chain):
        # No 'delta' column — max_delta should be silently ignored
        result = filter_option_chain(sample_chain, days_to_expiry=30, max_delta=0.3)
        assert len(result) == 4


# ---------------------------------------------------------------------------
# Table builder tests
# ---------------------------------------------------------------------------

class TestBuildCoveredCallTable:
    """Tests for the per-expiry covered call table builder."""

    def test_basic_table(self):
        calls = pd.DataFrame({
            "strike": [105.0, 110.0],
            "bid": [3.0, 1.5],
            "ask": [3.4, 1.8],
            "lastPrice": [3.2, 1.6],
        })
        result = build_covered_call_table(
            ticker="AAPL",
            current_price=100.0,
            calls_df=calls,
            expiry_date=date(2026, 5, 16),
            today=date(2026, 4, 16),
        )
        assert len(result) == 2
        assert "ticker" in result.columns
        assert "premium_yield_annual" in result.columns
        assert result.iloc[0]["ticker"] == "AAPL"
        # Premium should be mid price: (3.0+3.4)/2 = 3.2
        assert result.iloc[0]["premium"] == pytest.approx(3.2)

    def test_empty_chain_returns_empty_df(self):
        empty = pd.DataFrame(columns=["strike", "lastPrice", "bid", "ask"])
        result = build_covered_call_table(
            ticker="MSFT",
            current_price=400.0,
            calls_df=empty,
            expiry_date=date(2026, 5, 16),
            today=date(2026, 4, 16),
        )
        assert len(result) == 0
        assert "premium_yield_annual" in result.columns

    def test_fallback_to_lastprice_when_bid_ask_zero(self):
        calls = pd.DataFrame({
            "strike": [105.0],
            "bid": [0.0],
            "ask": [0.0],
            "lastPrice": [2.5],
        })
        result = build_covered_call_table(
            ticker="TEST",
            current_price=100.0,
            calls_df=calls,
            expiry_date=date(2026, 5, 16),
            today=date(2026, 4, 16),
        )
        assert result.iloc[0]["premium"] == pytest.approx(2.5)

    def test_no_bid_ask_columns_uses_lastprice(self):
        calls = pd.DataFrame({
            "strike": [105.0],
            "lastPrice": [4.0],
        })
        result = build_covered_call_table(
            ticker="XYZ",
            current_price=100.0,
            calls_df=calls,
            expiry_date=date(2026, 5, 16),
            today=date(2026, 4, 16),
        )
        assert result.iloc[0]["premium"] == pytest.approx(4.0)

    def test_break_even_calculation(self):
        calls = pd.DataFrame({
            "strike": [105.0],
            "lastPrice": [3.0],
        })
        result = build_covered_call_table(
            ticker="T",
            current_price=100.0,
            calls_df=calls,
            expiry_date=date(2026, 5, 16),
            today=date(2026, 4, 16),
        )
        assert result.iloc[0]["break_even"] == pytest.approx(97.0)

    def test_zero_dte_skips_rows(self):
        calls = pd.DataFrame({
            "strike": [105.0],
            "lastPrice": [3.0],
        })
        today = date(2026, 5, 16)
        result = build_covered_call_table(
            ticker="T",
            current_price=100.0,
            calls_df=calls,
            expiry_date=today,
            today=today,
        )
        assert len(result) == 0
