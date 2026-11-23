# ABOUTME: Unit tests for dividend yield forecasting and safety analysis.
# ABOUTME: Tests Gordon growth model, forecast, yield-on-cost, payout ratio, coverage.

import pytest
from assethold.dividend_forecast import (
    gordon_growth_model,
    forecast_dividends,
    yield_on_cost,
    payout_ratio,
    dividend_coverage,
    GordonGrowthResult,
    DividendForecastResult,
)


class TestGordonGrowthModel:
    def test_basic_valuation(self):
        result = gordon_growth_model(
            current_dividend=2.0,
            growth_rate=0.05,
            required_return=0.10,
        )
        assert isinstance(result, GordonGrowthResult)
        # D1 = 2.0 * 1.05 = 2.10; P = 2.10 / (0.10 - 0.05) = 42.0
        assert result.forward_dividend == pytest.approx(2.10)
        assert result.fair_value == pytest.approx(42.0)
        assert result.forward_yield == pytest.approx(0.05)

    def test_zero_dividend(self):
        result = gordon_growth_model(
            current_dividend=0.0,
            growth_rate=0.03,
            required_return=0.08,
        )
        assert result.fair_value == 0.0
        assert result.forward_yield == 0.0
        assert result.forward_dividend == 0.0

    def test_growth_equals_return_raises(self):
        with pytest.raises(ValueError, match="growth rate"):
            gordon_growth_model(
                current_dividend=1.0,
                growth_rate=0.10,
                required_return=0.10,
            )

    def test_growth_exceeds_return_raises(self):
        with pytest.raises(ValueError, match="growth rate"):
            gordon_growth_model(
                current_dividend=1.0,
                growth_rate=0.12,
                required_return=0.10,
            )

    def test_low_growth_high_return(self):
        result = gordon_growth_model(
            current_dividend=4.0,
            growth_rate=0.02,
            required_return=0.12,
        )
        # D1 = 4.08; P = 4.08 / 0.10 = 40.80
        assert result.fair_value == pytest.approx(40.80)


class TestForecastDividends:
    def test_basic_forecast(self):
        result = forecast_dividends(
            current_dividend=1.0,
            growth_rate=0.10,
            years=3,
        )
        assert isinstance(result, DividendForecastResult)
        assert result.years == 3
        assert len(result.dividends) == 3
        assert result.dividends[0] == pytest.approx(1.10)
        assert result.dividends[1] == pytest.approx(1.21)
        assert result.dividends[2] == pytest.approx(1.331)
        assert result.total == pytest.approx(sum(result.dividends))

    def test_zero_growth(self):
        result = forecast_dividends(
            current_dividend=2.0,
            growth_rate=0.0,
            years=5,
        )
        assert all(d == pytest.approx(2.0) for d in result.dividends)
        assert result.total == pytest.approx(10.0)

    def test_single_year(self):
        result = forecast_dividends(
            current_dividend=3.0,
            growth_rate=0.05,
            years=1,
        )
        assert len(result.dividends) == 1
        assert result.dividends[0] == pytest.approx(3.15)

    def test_zero_dividend(self):
        result = forecast_dividends(
            current_dividend=0.0,
            growth_rate=0.10,
            years=5,
        )
        assert all(d == 0.0 for d in result.dividends)
        assert result.total == 0.0


class TestYieldOnCost:
    def test_basic_yield(self):
        yoc = yield_on_cost(current_annual_dividend=4.0, purchase_price=100.0)
        assert yoc == pytest.approx(0.04)

    def test_high_yield(self):
        yoc = yield_on_cost(current_annual_dividend=10.0, purchase_price=50.0)
        assert yoc == pytest.approx(0.20)

    def test_zero_purchase_price_raises(self):
        with pytest.raises(ValueError, match="purchase_price"):
            yield_on_cost(current_annual_dividend=1.0, purchase_price=0.0)


class TestPayoutRatio:
    def test_basic_payout(self):
        ratio = payout_ratio(annual_dividend=2.0, earnings_per_share=4.0)
        assert ratio == pytest.approx(0.50)

    def test_full_payout(self):
        ratio = payout_ratio(annual_dividend=5.0, earnings_per_share=5.0)
        assert ratio == pytest.approx(1.0)

    def test_zero_eps_raises(self):
        with pytest.raises(ValueError, match="earnings_per_share"):
            payout_ratio(annual_dividend=1.0, earnings_per_share=0.0)


class TestDividendCoverage:
    def test_basic_coverage(self):
        coverage = dividend_coverage(earnings_per_share=6.0, annual_dividend=3.0)
        assert coverage == pytest.approx(2.0)

    def test_thin_coverage(self):
        coverage = dividend_coverage(earnings_per_share=1.1, annual_dividend=1.0)
        assert coverage == pytest.approx(1.1)

    def test_zero_dividend_raises(self):
        with pytest.raises(ValueError, match="annual_dividend"):
            dividend_coverage(earnings_per_share=5.0, annual_dividend=0.0)
