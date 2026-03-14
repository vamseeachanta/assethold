# ABOUTME: Dividend yield forecasting and safety analysis (WRK-1198)
# ABOUTME: Gordon growth model, dividend stream forecast, payout/coverage ratios
"""
Dividend yield forecasting and safety analysis.

Provides the Gordon Growth Model for intrinsic valuation, multi-year
dividend stream forecasting, and safety metrics (payout ratio, dividend
coverage, yield on cost).

References:
    Gordon, M.J. (1959) Dividends, Earnings, and Stock Prices.
    Damodaran -- Investment Valuation, Chapter 13.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GordonGrowthResult:
    """Result of the Gordon Growth Model valuation."""

    fair_value: float
    forward_yield: float
    forward_dividend: float
    growth_rate: float
    required_return: float


@dataclass
class DividendForecastResult:
    """Result of a multi-year dividend forecast."""

    dividends: list[float]
    total: float
    growth_rate: float
    years: int


def gordon_growth_model(
    current_dividend: float,
    growth_rate: float,
    required_return: float,
) -> GordonGrowthResult:
    """Compute intrinsic value using the Gordon Growth Model.

    P = D1 / (r - g), where D1 = current_dividend * (1 + g).

    Args:
        current_dividend: Most recent annual dividend per share.
        growth_rate: Expected constant dividend growth rate (g).
        required_return: Investor's required rate of return (r).

    Returns:
        GordonGrowthResult with fair value and forward yield.

    Raises:
        ValueError: If growth_rate >= required_return.
    """
    if growth_rate >= required_return:
        msg = (
            f"growth rate ({growth_rate:.4f}) must be less than "
            f"required return ({required_return:.4f})"
        )
        raise ValueError(msg)

    if current_dividend == 0.0:
        return GordonGrowthResult(
            fair_value=0.0,
            forward_yield=0.0,
            forward_dividend=0.0,
            growth_rate=growth_rate,
            required_return=required_return,
        )

    forward_dividend = current_dividend * (1.0 + growth_rate)
    fair_value = forward_dividend / (required_return - growth_rate)
    forward_yield = forward_dividend / fair_value

    return GordonGrowthResult(
        fair_value=fair_value,
        forward_yield=forward_yield,
        forward_dividend=forward_dividend,
        growth_rate=growth_rate,
        required_return=required_return,
    )


def forecast_dividends(
    current_dividend: float,
    growth_rate: float,
    years: int,
) -> DividendForecastResult:
    """Forecast a dividend stream over multiple years.

    Each year's dividend = current_dividend * (1 + growth_rate) ** year.

    Args:
        current_dividend: Most recent annual dividend per share.
        growth_rate: Expected constant dividend growth rate.
        years: Number of years to forecast.

    Returns:
        DividendForecastResult with per-year dividends and total.
    """
    dividends = [
        current_dividend * (1.0 + growth_rate) ** yr
        for yr in range(1, years + 1)
    ]
    return DividendForecastResult(
        dividends=dividends,
        total=sum(dividends),
        growth_rate=growth_rate,
        years=years,
    )


def yield_on_cost(
    current_annual_dividend: float,
    purchase_price: float,
) -> float:
    """Compute yield on cost.

    Args:
        current_annual_dividend: Current annual dividend per share.
        purchase_price: Original purchase price per share.

    Returns:
        Yield on cost as a decimal (e.g. 0.06 for 6%).

    Raises:
        ValueError: If purchase_price is zero.
    """
    if purchase_price == 0.0:
        raise ValueError("purchase_price must be non-zero")
    return current_annual_dividend / purchase_price


def payout_ratio(
    annual_dividend: float,
    earnings_per_share: float,
) -> float:
    """Compute dividend payout ratio.

    Args:
        annual_dividend: Annual dividend per share.
        earnings_per_share: Earnings per share (EPS).

    Returns:
        Payout ratio as a decimal (e.g. 0.50 for 50%).

    Raises:
        ValueError: If earnings_per_share is zero.
    """
    if earnings_per_share == 0.0:
        raise ValueError("earnings_per_share must be non-zero")
    return annual_dividend / earnings_per_share


def dividend_coverage(
    earnings_per_share: float,
    annual_dividend: float,
) -> float:
    """Compute dividend coverage ratio (inverse of payout ratio).

    Args:
        earnings_per_share: Earnings per share (EPS).
        annual_dividend: Annual dividend per share.

    Returns:
        Coverage ratio (e.g. 2.0 means EPS covers dividend 2x).

    Raises:
        ValueError: If annual_dividend is zero.
    """
    if annual_dividend == 0.0:
        raise ValueError("annual_dividend must be non-zero")
    return earnings_per_share / annual_dividend
