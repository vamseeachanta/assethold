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


def gordon_growth_value(
    forward_dividend: float,
    required_return: float,
    growth_rate: float,
) -> float:
    """Intrinsic value via the single-stage Gordon Growth Model (direct form).

    Formula:
        P0 = D1 / (r - g)

    This is the textbook constant-growth dividend-discount form that takes the
    *next-period* dividend D1 directly (unlike :func:`gordon_growth_model`,
    which grows the current dividend D0 by g first). It assumes dividends grow
    forever at a single constant rate g < r.

    Args:
        forward_dividend: Next-period (year-1) dividend per share, D1.
        required_return: Investor's required rate of return, r (decimal).
        growth_rate: Constant perpetual dividend growth rate, g (decimal).

    Returns:
        Intrinsic value per share, P0.

    Raises:
        ValueError: If required_return <= growth_rate (value diverges).

    Example:
        >>> gordon_growth_value(2.0, 0.10, 0.05)
        40.0
    """
    if required_return <= growth_rate:
        msg = (
            f"required return ({required_return:.4f}) must exceed "
            f"growth rate ({growth_rate:.4f})"
        )
        raise ValueError(msg)
    return forward_dividend / (required_return - growth_rate)


def h_model_value(
    current_dividend: float,
    required_return: float,
    g_long: float,
    g_short: float,
    half_life_years: float,
) -> float:
    """Intrinsic value via the two-stage H-model.

    The H-model (Fuller & Hsia, 1984) approximates a dividend stream whose
    growth starts at an elevated short-run rate ``g_short`` and declines
    *linearly* to a stable long-run rate ``g_long`` over ``2H`` years, where
    ``H = half_life_years`` is the half-life of the high-growth phase.

    Formula:
        P0 = [ D0 * (1 + g_long) + D0 * H * (g_short - g_long) ] / (r - g_long)

    The first term is the value of the stable-growth component (a perpetuity at
    g_long); the second term is the extra value from the linearly-fading excess
    growth (g_short - g_long).

    Args:
        current_dividend: Most recent annual dividend per share, D0.
        required_return: Required rate of return, r (decimal).
        g_long: Stable long-run growth rate, g_long (decimal).
        g_short: Initial short-run growth rate, g_short (decimal).
        half_life_years: Half-life H of the high-growth period, in years
            (total high-growth phase spans 2H years).

    Returns:
        Intrinsic value per share, P0.

    Raises:
        ValueError: If required_return <= g_long, or half_life_years < 0.
    """
    if required_return <= g_long:
        msg = (
            f"required return ({required_return:.4f}) must exceed "
            f"long-run growth ({g_long:.4f})"
        )
        raise ValueError(msg)
    if half_life_years < 0.0:
        raise ValueError("half_life_years must be non-negative")

    stable = current_dividend * (1.0 + g_long)
    excess = current_dividend * half_life_years * (g_short - g_long)
    return (stable + excess) / (required_return - g_long)


def multi_stage_ddm(
    current_dividend: float,
    stage_growths_and_years: list[tuple[float, int]],
    terminal_growth: float,
    required_return: float,
) -> float:
    """Intrinsic value via a multi-stage dividend-discount model.

    Each explicit stage applies a constant growth rate for a given number of
    years. Dividends are grown sequentially across stages and discounted to
    present value at ``required_return``. After the final explicit stage, a
    Gordon terminal value (perpetuity growing at ``terminal_growth``) is
    computed from the last stage's ending dividend and discounted back.

    Formula:
        PV(dividends) = sum_t D_t / (1 + r)^t   over all explicit years t
        TV at year N  = D_N * (1 + g_term) / (r - g_term)
        P0 = PV(dividends) + TV / (1 + r)^N

    Args:
        current_dividend: Most recent annual dividend per share, D0.
        stage_growths_and_years: Ordered list of (growth_rate, years) tuples,
            each a constant-growth stage; growth_rate and years are decimal /
            integer. years must be >= 1.
        terminal_growth: Perpetual growth rate after the last stage, g_term.
        required_return: Required rate of return, r (decimal).

    Returns:
        Intrinsic value per share, P0.

    Raises:
        ValueError: If required_return <= terminal_growth, no stages are given,
            or any stage has years < 1.
    """
    if not stage_growths_and_years:
        raise ValueError("at least one growth stage is required")
    if required_return <= terminal_growth:
        msg = (
            f"required return ({required_return:.4f}) must exceed "
            f"terminal growth ({terminal_growth:.4f})"
        )
        raise ValueError(msg)

    pv_dividends = 0.0
    dividend = current_dividend
    year = 0
    for growth_rate, years in stage_growths_and_years:
        if years < 1:
            raise ValueError("each stage must span at least 1 year")
        for _ in range(years):
            year += 1
            dividend *= 1.0 + growth_rate
            pv_dividends += dividend / (1.0 + required_return) ** year

    # dividend now holds D_N (last explicit dividend); year == N.
    terminal_value = (
        dividend * (1.0 + terminal_growth) / (required_return - terminal_growth)
    )
    pv_terminal = terminal_value / (1.0 + required_return) ** year
    return pv_dividends + pv_terminal


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
