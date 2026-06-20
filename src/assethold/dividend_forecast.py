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

from dataclasses import dataclass, field
from datetime import date, timedelta

# Nominal day-count length of each dividend cadence (period between ex-dates).
# Used to classify an observed median gap and to step ex-dates forward.
_CADENCE_DAYS: dict[str, int] = {
    "monthly": 30,
    "quarterly": 91,
    "semiannual": 182,
    "annual": 365,
}

# Inference bands (inclusive lower / exclusive upper) for the median gap, in
# days. Wide bands absorb the +/- few-day jitter real ex-date calendars show.
_CADENCE_BANDS: list[tuple[float, float, str]] = [
    (20.0, 45.0, "monthly"),
    (75.0, 135.0, "quarterly"),
    (150.0, 225.0, "semiannual"),
    (300.0, 430.0, "annual"),
]


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


# ---------------------------------------------------------------------------
# Ex-dividend date forecasting (issue #26)
#
# Projects future ex-dividend dates and per-share amounts from a holding's
# historical (ex_date, amount) record. Pure calendar + cadence arithmetic:
# no network, no yfinance import -- the caller supplies the history (e.g. from
# yfinance ``ticker.dividends``). Amount projection reuses the growth math in
# :func:`forecast_dividends`.
# ---------------------------------------------------------------------------


@dataclass
class CadenceResult:
    """Inferred payment cadence from a series of historical ex-dates."""

    cadence: str  # one of: monthly, quarterly, semiannual, annual, irregular
    periods_per_year: int  # 0 when irregular
    median_gap_days: float  # median spacing between consecutive ex-dates
    sample_size: int  # number of gaps observed


@dataclass
class ProjectedDividend:
    """A single projected future ex-dividend event."""

    ex_date: date
    amount: float
    period_index: int  # 1-based: 1 = next ex-date, 2 = the one after, ...


@dataclass
class ExDateSchedule:
    """A forward schedule of projected ex-dividend dates and amounts."""

    cadence: CadenceResult
    events: list[ProjectedDividend] = field(default_factory=list)

    @property
    def total_amount(self) -> float:
        """Sum of projected per-share amounts across the schedule."""
        return sum(ev.amount for ev in self.events)


def _median(values: list[float]) -> float:
    """Median of a non-empty list (no numpy dependency)."""
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def infer_cadence(ex_dates: list[date]) -> CadenceResult:
    """Infer the dividend payment cadence from historical ex-dates.

    The cadence is classified from the *median* gap (in days) between
    consecutive, chronologically-sorted ex-dates. The median is robust to the
    occasional missed or doubled payment (an irregular gap) that would skew a
    mean. A gap that falls outside every known band yields ``"irregular"``.

    Args:
        ex_dates: Historical ex-dividend dates. Need not be pre-sorted;
            duplicates are de-duplicated before gaps are measured.

    Returns:
        CadenceResult with the cadence label, payments per year, the observed
        median gap, and the number of gaps used.

    Raises:
        ValueError: If fewer than two distinct ex-dates are supplied (a single
            date gives no gap to measure).
    """
    unique = sorted(set(ex_dates))
    if len(unique) < 2:
        raise ValueError("need at least two distinct ex-dates to infer cadence")

    gaps = [
        (later - earlier).days
        for earlier, later in zip(unique, unique[1:])
    ]
    median_gap = _median([float(g) for g in gaps])

    cadence = "irregular"
    for low, high, label in _CADENCE_BANDS:
        if low <= median_gap < high:
            cadence = label
            break

    periods_per_year = {
        "monthly": 12,
        "quarterly": 4,
        "semiannual": 2,
        "annual": 1,
    }.get(cadence, 0)

    return CadenceResult(
        cadence=cadence,
        periods_per_year=periods_per_year,
        median_gap_days=median_gap,
        sample_size=len(gaps),
    )


def forecast_ex_dates(
    history: list[tuple[date, float]],
    periods: int,
    *,
    growth_rate: float = 0.0,
    cadence_override: str | None = None,
) -> ExDateSchedule:
    """Project the next ``periods`` ex-dividend dates and amounts.

    Cadence is inferred from the history's ex-dates (or forced via
    ``cadence_override``). Each future ex-date steps forward from the last
    historical ex-date by the cadence's nominal day-count, so the projected
    calendar stays anchored to the holding's typical day-of-period rather than
    drifting. Amounts grow off the most-recent historical amount using the same
    compound-growth convention as :func:`forecast_dividends`
    (amount_k = last_amount * (1 + growth_rate) ** k).

    For an irregular history (no recognisable cadence) the function falls back
    to the observed *median* gap so a best-effort schedule is still returned.

    Args:
        history: List of ``(ex_date, amount_per_share)`` tuples. Need not be
            sorted; the most recent ex-date and amount anchor the projection.
        periods: Number of future ex-dates to project (must be >= 1).
        growth_rate: Per-period dividend growth rate (decimal). 0.0 holds the
            last amount flat. Compounds each period.
        cadence_override: Force a cadence label ("monthly"/"quarterly"/
            "semiannual"/"annual") instead of inferring it.

    Returns:
        ExDateSchedule with the inferred cadence and the projected events.

    Raises:
        ValueError: If ``periods`` < 1, history is empty, or
            ``cadence_override`` is not a recognised label.
    """
    if periods < 1:
        raise ValueError("periods must be >= 1")
    if not history:
        raise ValueError("history must contain at least one dividend record")

    ordered = sorted(history, key=lambda rec: rec[0])
    ex_dates = [rec[0] for rec in ordered]
    last_date = ex_dates[-1]
    last_amount = ordered[-1][1]

    if cadence_override is not None:
        if cadence_override not in _CADENCE_DAYS:
            raise ValueError(f"unknown cadence: {cadence_override!r}")
        cadence = CadenceResult(
            cadence=cadence_override,
            periods_per_year={
                "monthly": 12,
                "quarterly": 4,
                "semiannual": 2,
                "annual": 1,
            }[cadence_override],
            median_gap_days=float(_CADENCE_DAYS[cadence_override]),
            sample_size=0,
        )
        step_days = _CADENCE_DAYS[cadence_override]
    elif len(set(ex_dates)) >= 2:
        cadence = infer_cadence(ex_dates)
        # For a recognised cadence use its nominal step; for an irregular
        # history fall back to the observed median gap (rounded to a day).
        step_days = _CADENCE_DAYS.get(
            cadence.cadence, max(1, round(cadence.median_gap_days))
        )
    else:
        # Single distinct ex-date and no override: cannot infer cadence.
        raise ValueError(
            "cannot infer cadence from a single ex-date; pass cadence_override"
        )

    events: list[ProjectedDividend] = []
    current = last_date
    for k in range(1, periods + 1):
        current = current + timedelta(days=step_days)
        amount = last_amount * (1.0 + growth_rate) ** k
        events.append(
            ProjectedDividend(ex_date=current, amount=amount, period_index=k)
        )

    return ExDateSchedule(cadence=cadence, events=events)
