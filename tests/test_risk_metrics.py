"""Tests for portfolio risk metrics (WRK-324).

Covers: historical VaR, CVaR, parametric VaR, Sharpe ratio,
Sortino ratio, max drawdown, Calmar ratio, PortfolioRisk class,
DrawdownResult (with dates), and position_risk convenience function.
"""
import math
import pytest
import numpy as np
import pandas as pd
from assethold.risk_metrics import (
    historical_var,
    historical_cvar,
    parametric_var,
    sharpe_ratio,
    sortino_ratio,
    max_drawdown,
    max_drawdown_with_dates,
    calmar_ratio,
    position_risk,
    PortfolioRisk,
    DrawdownResult,
)


@pytest.fixture
def daily_returns():
    """Synthetic daily returns for testing (1 year, ~N(0.001, 0.02))."""
    np.random.seed(42)
    return pd.Series(np.random.normal(0.001, 0.02, 252))


@pytest.fixture
def positive_returns():
    """Returns with high positive mean so Sharpe and Calmar are > 0.

    Uses a normal distribution with mean well above zero so that the
    annualised return is positive and there is at least a small drawdown
    (sigma is large enough to produce occasional negative days).
    """
    np.random.seed(7)
    return pd.Series(np.random.normal(0.003, 0.015, 252))


@pytest.fixture
def multi_asset_returns():
    """Two-asset daily returns DataFrame."""
    np.random.seed(42)
    return pd.DataFrame({
        "AAPL": np.random.normal(0.001, 0.02, 252),
        "MSFT": np.random.normal(0.0008, 0.018, 252),
    })


# ---------------------------------------------------------------------------
# historical_var
# ---------------------------------------------------------------------------

class TestHistoricalVar:
    def test_returns_negative_value(self, daily_returns):
        var_95 = historical_var(daily_returns, confidence=0.95)
        assert var_95 < 0, "VaR should be a negative number (a loss)"

    def test_bounded_for_normal_returns(self, daily_returns):
        var_95 = historical_var(daily_returns, confidence=0.95)
        assert var_95 > -0.20, "VaR should not exceed 20% for low-vol returns"

    def test_higher_confidence_gives_worse_var(self, daily_returns):
        var_95 = historical_var(daily_returns, confidence=0.95)
        var_99 = historical_var(daily_returns, confidence=0.99)
        assert var_99 <= var_95, "99% VaR must be at least as bad as 95% VaR"

    def test_default_confidence_is_95(self, daily_returns):
        assert historical_var(daily_returns) == historical_var(
            daily_returns, confidence=0.95
        )

    def test_raises_on_empty_series(self):
        with pytest.raises(ValueError):
            historical_var(pd.Series(dtype=float))

    def test_raises_on_invalid_confidence(self, daily_returns):
        with pytest.raises(ValueError):
            historical_var(daily_returns, confidence=1.5)


# ---------------------------------------------------------------------------
# historical_cvar
# ---------------------------------------------------------------------------

class TestHistoricalCVar:
    def test_cvar_at_least_as_bad_as_var(self, daily_returns):
        var_95 = historical_var(daily_returns, 0.95)
        cvar_95 = historical_cvar(daily_returns, 0.95)
        assert cvar_95 <= var_95, "CVaR must be <= VaR (a worse or equal loss)"

    def test_returns_negative_value(self, daily_returns):
        assert historical_cvar(daily_returns, 0.95) < 0

    def test_raises_on_empty_series(self):
        with pytest.raises(ValueError):
            historical_cvar(pd.Series(dtype=float))


# ---------------------------------------------------------------------------
# parametric_var
# ---------------------------------------------------------------------------

class TestParametricVar:
    def test_returns_negative_value(self, daily_returns):
        pvar = parametric_var(daily_returns, confidence=0.95)
        assert pvar < 0

    def test_close_to_historical_for_normal_data(self, daily_returns):
        hvar = historical_var(daily_returns, 0.95)
        pvar = parametric_var(daily_returns, 0.95)
        # Both methods should agree within 1 percentage point for normal data
        assert abs(hvar - pvar) < 0.01

    def test_higher_confidence_gives_worse_var(self, daily_returns):
        pvar_95 = parametric_var(daily_returns, 0.95)
        pvar_99 = parametric_var(daily_returns, 0.99)
        assert pvar_99 <= pvar_95


# ---------------------------------------------------------------------------
# sharpe_ratio
# ---------------------------------------------------------------------------

class TestSharpeRatio:
    def test_positive_for_positive_mean_returns(self, positive_returns):
        sr = sharpe_ratio(positive_returns, risk_free_rate=0.04)
        assert sr > 0

    def test_returns_float(self, daily_returns):
        assert isinstance(sharpe_ratio(daily_returns), float)

    def test_higher_return_gives_higher_sharpe(self):
        np.random.seed(1)
        low = pd.Series(np.random.normal(0.0005, 0.02, 252))
        high = pd.Series(np.random.normal(0.003, 0.02, 252))
        assert sharpe_ratio(high) > sharpe_ratio(low)

    def test_raises_on_zero_std(self):
        constant = pd.Series([0.001] * 252)
        with pytest.raises(ValueError):
            sharpe_ratio(constant)


# ---------------------------------------------------------------------------
# sortino_ratio
# ---------------------------------------------------------------------------

class TestSortinoRatio:
    def test_returns_float(self, daily_returns):
        assert isinstance(sortino_ratio(daily_returns), float)

    def test_positive_for_positive_mean_returns(self, positive_returns):
        sr = sortino_ratio(positive_returns, risk_free_rate=0.04)
        assert sr > 0

    def test_sortino_gte_sharpe_for_skewed_up_returns(self):
        # When upside volatility >> downside, Sortino should be >= Sharpe
        np.random.seed(0)
        base = np.random.normal(0.002, 0.01, 252)
        # Add large positive outliers — increases std but not downside std
        base[::10] += 0.05
        ret = pd.Series(base)
        assert sortino_ratio(ret) >= sharpe_ratio(ret)


# ---------------------------------------------------------------------------
# max_drawdown
# ---------------------------------------------------------------------------

class TestMaxDrawdown:
    def test_returns_non_positive(self, daily_returns):
        dd = max_drawdown(daily_returns)
        assert dd <= 0

    def test_bounded_below_minus_one(self, daily_returns):
        dd = max_drawdown(daily_returns)
        assert dd >= -1.0

    def test_zero_drawdown_for_monotone_increase(self):
        increasing = pd.Series([0.01] * 252)
        dd = max_drawdown(increasing)
        assert dd == pytest.approx(0.0, abs=1e-9)

    def test_full_loss_scenario(self):
        # Returns that drive value from 1.0 down to 0 (and no recovery)
        returns = pd.Series([-1.0] + [0.0] * 10)
        dd = max_drawdown(returns)
        assert dd == pytest.approx(-1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# DrawdownResult and max_drawdown_with_dates
# ---------------------------------------------------------------------------

class TestMaxDrawdownWithDates:
    def test_returns_drawdown_result_type(self, daily_returns):
        result = max_drawdown_with_dates(daily_returns)
        assert isinstance(result, DrawdownResult)

    def test_drawdown_value_matches_max_drawdown(self, daily_returns):
        result = max_drawdown_with_dates(daily_returns)
        assert result.drawdown == pytest.approx(max_drawdown(daily_returns), abs=1e-10)

    def test_peak_date_before_trough_date(self, daily_returns):
        result = max_drawdown_with_dates(daily_returns)
        assert result.peak_date <= result.trough_date

    def test_dates_are_valid_pandas_timestamps_for_datetime_index(self):
        idx = pd.date_range("2024-01-01", periods=20, freq="B")
        returns = pd.Series(
            [0.01, 0.01, -0.05, -0.03, 0.01, 0.01, -0.02, 0.01] * 2
            + [0.01, 0.01, 0.01, 0.01],
            index=idx,
        )
        result = max_drawdown_with_dates(returns)
        assert result.peak_date is not None
        assert result.trough_date is not None

    def test_known_drawdown_with_integer_index(self):
        # Series with clear peak early, then decline
        returns = pd.Series([0.01, 0.01, -0.1176, -0.0556, 0.0588])
        result = max_drawdown_with_dates(returns)
        assert result.drawdown < 0
        assert result.peak_date <= result.trough_date

    def test_zero_drawdown_both_dates_none(self):
        increasing = pd.Series([0.01] * 10)
        result = max_drawdown_with_dates(increasing)
        # drawdown is 0; peak/trough dates are None
        assert result.drawdown == pytest.approx(0.0, abs=1e-9)
        assert result.peak_date is None
        assert result.trough_date is None

    def test_raises_on_empty_series(self):
        with pytest.raises(ValueError):
            max_drawdown_with_dates(pd.Series(dtype=float))


# ---------------------------------------------------------------------------
# calmar_ratio
# ---------------------------------------------------------------------------

class TestCalmarRatio:
    def test_returns_float(self, daily_returns):
        assert isinstance(calmar_ratio(daily_returns), float)

    def test_positive_for_positive_annualised_return(self, positive_returns):
        cr = calmar_ratio(positive_returns)
        assert cr > 0

    def test_raises_when_max_drawdown_zero(self):
        increasing = pd.Series([0.001] * 252)
        with pytest.raises(ValueError):
            calmar_ratio(increasing)


# ---------------------------------------------------------------------------
# position_risk convenience function
# ---------------------------------------------------------------------------

class TestPositionRisk:
    def test_returns_dict_with_all_keys(self, daily_returns):
        metrics = position_risk(daily_returns)
        for key in (
            "var_95", "var_99", "cvar_95", "cvar_99",
            "parametric_var_95", "parametric_var_99",
            "sharpe", "sortino", "max_drawdown", "calmar",
        ):
            assert key in metrics, f"Missing key: {key}"

    def test_var_values_are_negative(self, daily_returns):
        metrics = position_risk(daily_returns)
        assert metrics["var_95"] < 0
        assert metrics["var_99"] < 0
        assert metrics["cvar_95"] < 0
        assert metrics["cvar_99"] < 0

    def test_custom_risk_free_rate_passed_through(self, positive_returns):
        m_low = position_risk(positive_returns, risk_free_rate=0.0)
        m_high = position_risk(positive_returns, risk_free_rate=0.10)
        # Higher risk-free rate reduces Sharpe
        assert m_low["sharpe"] > m_high["sharpe"]

    def test_returns_drawdown_result_with_dates(self, daily_returns):
        metrics = position_risk(daily_returns)
        assert isinstance(metrics["drawdown_detail"], DrawdownResult)

    def test_positive_returns_give_positive_sharpe(self, positive_returns):
        metrics = position_risk(positive_returns)
        assert metrics["sharpe"] > 0

    def test_calmar_nan_when_no_drawdown(self):
        # Use slightly varying returns (all positive) so Sharpe is defined,
        # but with no peak-to-trough decline so max_drawdown is 0.
        np.random.seed(99)
        always_up = pd.Series(np.abs(np.random.normal(0.002, 0.0001, 252)))
        metrics = position_risk(always_up)
        assert math.isnan(metrics["calmar"])

    def test_raises_on_empty_series(self):
        with pytest.raises(ValueError):
            position_risk(pd.Series(dtype=float))


# ---------------------------------------------------------------------------
# Sortino ratio edge cases (coverage for fallback paths)
# ---------------------------------------------------------------------------

class TestSortinoEdgeCases:
    def test_no_negative_excess_returns_falls_back_to_sharpe(self):
        # All excess returns positive (varying so Sharpe is defined) ->
        # no downside deviation -> Sortino falls back to Sharpe.
        np.random.seed(55)
        # returns all well above daily rf (0.04/252 approx 0.000159)
        always_positive_excess = pd.Series(
            np.abs(np.random.normal(0.005, 0.001, 252))
        )
        sr = sharpe_ratio(always_positive_excess, risk_free_rate=0.04)
        so = sortino_ratio(always_positive_excess, risk_free_rate=0.04)
        assert so == pytest.approx(sr, rel=1e-6)

    def test_downside_deviation_is_not_zero_for_varying_negatives(self):
        # Returns with some negative excess returns: sortino is well defined
        np.random.seed(11)
        mixed = pd.Series(np.random.normal(0.0, 0.01, 252))
        result = sortino_ratio(mixed, risk_free_rate=0.04)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# PortfolioRisk calmar NaN coverage
# ---------------------------------------------------------------------------

class TestPortfolioRiskCalmarNan:
    def test_calmar_is_nan_when_no_drawdown(self):
        # Always-positive varying returns -> max drawdown is 0 -> calmar is nan
        np.random.seed(88)
        always_up = np.abs(np.random.normal(0.002, 0.0001, 252))
        df = pd.DataFrame({
            "A": pd.Series(always_up),
            "B": pd.Series(always_up * 0.99),
        })
        pr = PortfolioRisk(df, {"A": 0.5, "B": 0.5})
        metrics = pr.compute()
        assert math.isnan(metrics["calmar"])


# ---------------------------------------------------------------------------
# PortfolioRisk
# ---------------------------------------------------------------------------

class TestPortfolioRisk:
    def test_compute_returns_all_required_keys(
        self, multi_asset_returns
    ):
        weights = {"AAPL": 0.6, "MSFT": 0.4}
        pr = PortfolioRisk(multi_asset_returns, weights)
        metrics = pr.compute()
        for key in ("var_95", "cvar_95", "sharpe", "max_drawdown",
                    "sortino", "calmar", "var_99", "cvar_99"):
            assert key in metrics, f"Missing metric key: {key}"

    def test_portfolio_returns_weighted_correctly(
        self, multi_asset_returns
    ):
        weights = {"AAPL": 0.6, "MSFT": 0.4}
        pr = PortfolioRisk(multi_asset_returns, weights)
        port_ret = pr.portfolio_returns()
        expected = (
            multi_asset_returns["AAPL"] * 0.6
            + multi_asset_returns["MSFT"] * 0.4
        )
        pd.testing.assert_series_equal(
            port_ret.reset_index(drop=True),
            expected.reset_index(drop=True),
            check_names=False,
        )

    def test_weights_must_sum_to_one(self, multi_asset_returns):
        bad_weights = {"AAPL": 0.7, "MSFT": 0.7}
        with pytest.raises(ValueError):
            PortfolioRisk(multi_asset_returns, bad_weights)

    def test_report_returns_string(self, multi_asset_returns):
        weights = {"AAPL": 0.6, "MSFT": 0.4}
        pr = PortfolioRisk(multi_asset_returns, weights)
        report = pr.report()
        assert isinstance(report, str)
        assert len(report) > 0

    def test_report_contains_metric_labels(self, multi_asset_returns):
        weights = {"AAPL": 0.6, "MSFT": 0.4}
        pr = PortfolioRisk(multi_asset_returns, weights)
        report = pr.report()
        for label in ("VaR", "CVaR", "Sharpe", "Drawdown"):
            assert label in report, f"Report missing label: {label}"

    def test_raises_on_missing_ticker_in_returns(
        self, multi_asset_returns
    ):
        weights = {"AAPL": 0.5, "GOOG": 0.5}
        with pytest.raises(KeyError):
            PortfolioRisk(multi_asset_returns, weights).portfolio_returns()
