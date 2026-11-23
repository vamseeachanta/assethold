"""Tests for dividend yield forecasting."""
import pytest


class TestDividendGrowthModel:
    def test_gordon_growth_model(self):
        """Gordon Growth: P = D1 / (r - g)"""
        from assethold.dividend_forecast import gordon_growth_model
        result = gordon_growth_model(
            current_dividend=2.0,
            growth_rate=0.05,
            required_return=0.10,
        )
        # D1 = 2.0 * 1.05 = 2.10
        # P = 2.10 / (0.10 - 0.05) = 42.0
        assert abs(result.fair_value - 42.0) < 0.01
        assert abs(result.forward_yield - 0.05) < 0.001  # 2.10/42.0

    def test_growth_exceeds_return_raises(self):
        from assethold.dividend_forecast import gordon_growth_model
        with pytest.raises(ValueError, match="growth"):
            gordon_growth_model(
                current_dividend=2.0,
                growth_rate=0.12,
                required_return=0.10,
            )

    def test_zero_dividend(self):
        from assethold.dividend_forecast import gordon_growth_model
        result = gordon_growth_model(
            current_dividend=0.0,
            growth_rate=0.05,
            required_return=0.10,
        )
        assert result.fair_value == 0.0


class TestDividendForecast:
    def test_forecast_5_years(self):
        """Forecast dividend stream for 5 years."""
        from assethold.dividend_forecast import forecast_dividends
        result = forecast_dividends(
            current_dividend=2.0,
            growth_rate=0.05,
            years=5,
        )
        assert len(result.dividends) == 5
        assert abs(result.dividends[0] - 2.10) < 0.01  # year 1
        assert abs(result.dividends[4] - 2.0 * 1.05**5) < 0.01
        assert result.total > sum(result.dividends) * 0.99

    def test_yield_on_cost(self):
        """Yield on cost = current dividend / purchase price."""
        from assethold.dividend_forecast import yield_on_cost
        result = yield_on_cost(
            current_annual_dividend=3.0,
            purchase_price=50.0,
        )
        assert abs(result - 0.06) < 0.001  # 3/50 = 6%

    def test_zero_price_raises(self):
        from assethold.dividend_forecast import yield_on_cost
        with pytest.raises(ValueError):
            yield_on_cost(
                current_annual_dividend=3.0,
                purchase_price=0.0,
            )


class TestDividendSafety:
    def test_payout_ratio(self):
        """Payout ratio = dividend / EPS."""
        from assethold.dividend_forecast import payout_ratio
        result = payout_ratio(
            annual_dividend=2.0,
            earnings_per_share=4.0,
        )
        assert abs(result - 0.50) < 0.001

    def test_dividend_coverage(self):
        """Dividend coverage = EPS / dividend."""
        from assethold.dividend_forecast import dividend_coverage
        result = dividend_coverage(
            earnings_per_share=4.0,
            annual_dividend=2.0,
        )
        assert abs(result - 2.0) < 0.001

    def test_zero_earnings_payout(self):
        from assethold.dividend_forecast import payout_ratio
        with pytest.raises(ValueError):
            payout_ratio(
                annual_dividend=2.0,
                earnings_per_share=0.0,
            )
