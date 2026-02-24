# ABOUTME: Portfolio risk metrics — VaR, CVaR, Sharpe, Sortino, max drawdown (WRK-324)
# ABOUTME: Historical simulation and parametric methods for position and portfolio risk
"""
Risk metrics module for assethold.

Provides historical simulation and parametric risk measures for
individual return series and multi-asset portfolios.

Public API
----------
historical_var      -- Historical Value at Risk
historical_cvar     -- Historical Conditional VaR (Expected Shortfall)
parametric_var      -- Parametric (normal) VaR
sharpe_ratio        -- Annualised Sharpe ratio
sortino_ratio       -- Annualised Sortino ratio
max_drawdown        -- Peak-to-trough maximum drawdown
calmar_ratio        -- Annualised return / |max drawdown|
PortfolioRisk       -- Aggregated portfolio metrics class
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_returns(returns: pd.Series, label: str = "returns") -> None:
    """Raise ValueError when returns series is empty."""
    if returns.empty:
        raise ValueError(f"{label} must not be empty")


def _validate_confidence(confidence: float) -> None:
    """Raise ValueError for out-of-range confidence levels."""
    if not (0.0 < confidence < 1.0):
        raise ValueError(
            f"confidence must be in (0, 1), got {confidence}"
        )


# ---------------------------------------------------------------------------
# Historical simulation
# ---------------------------------------------------------------------------

def historical_var(
    returns: pd.Series,
    confidence: float = 0.95,
) -> float:
    """Return the historical VaR as a negative loss figure.

    Parameters
    ----------
    returns:
        Daily (or periodic) return series.
    confidence:
        Confidence level, e.g. 0.95 for 95% VaR.

    Returns
    -------
    float
        Negative value representing the loss threshold.
    """
    _validate_returns(returns, "returns")
    _validate_confidence(confidence)
    return float(np.quantile(returns, 1.0 - confidence))


def historical_cvar(
    returns: pd.Series,
    confidence: float = 0.95,
) -> float:
    """Return the historical CVaR (Expected Shortfall).

    CVaR is the mean of all returns that fall at or below the VaR
    threshold, giving the expected loss in the worst (1-confidence)
    fraction of outcomes.

    Parameters
    ----------
    returns:
        Daily (or periodic) return series.
    confidence:
        Confidence level.

    Returns
    -------
    float
        Negative value; always <= historical_var at the same confidence.
    """
    _validate_returns(returns, "returns")
    _validate_confidence(confidence)
    var = historical_var(returns, confidence)
    tail = returns[returns <= var]
    return float(tail.mean())


# ---------------------------------------------------------------------------
# Parametric (normal distribution)
# ---------------------------------------------------------------------------

def parametric_var(
    returns: pd.Series,
    confidence: float = 0.95,
) -> float:
    """Return parametric VaR assuming normally distributed returns.

    Formula: mu - z * sigma, where z is the inverse-normal quantile.

    Parameters
    ----------
    returns:
        Daily (or periodic) return series.
    confidence:
        Confidence level.

    Returns
    -------
    float
        Negative value representing the loss threshold.
    """
    _validate_returns(returns, "returns")
    _validate_confidence(confidence)
    mu = float(returns.mean())
    sigma = float(returns.std(ddof=1))
    z = scipy_stats.norm.ppf(1.0 - confidence)
    return float(mu + z * sigma)


# ---------------------------------------------------------------------------
# Ratio metrics
# ---------------------------------------------------------------------------

def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.04,
    periods: int = 252,
) -> float:
    """Return the annualised Sharpe ratio.

    Parameters
    ----------
    returns:
        Daily return series.
    risk_free_rate:
        Annual risk-free rate (e.g. 0.04 for 4%).
    periods:
        Number of periods per year used for annualisation.

    Returns
    -------
    float

    Raises
    ------
    ValueError
        When the standard deviation of returns is zero.
    """
    _validate_returns(returns, "returns")
    daily_rf = risk_free_rate / periods
    excess = returns - daily_rf
    sigma = float(excess.std(ddof=1))
    if math.isclose(sigma, 0.0, abs_tol=1e-12):
        raise ValueError(
            "Standard deviation of returns is zero; Sharpe ratio is undefined."
        )
    return float(excess.mean() / sigma * math.sqrt(periods))


def sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.04,
    periods: int = 252,
) -> float:
    """Return the annualised Sortino ratio (uses downside deviation).

    Parameters
    ----------
    returns:
        Daily return series.
    risk_free_rate:
        Annual risk-free rate.
    periods:
        Number of periods per year.

    Returns
    -------
    float
    """
    _validate_returns(returns, "returns")
    daily_rf = risk_free_rate / periods
    excess = returns - daily_rf
    downside = excess[excess < 0]
    if downside.empty:
        # No negative excess returns — ratio is effectively infinite;
        # return the Sharpe equivalent instead.
        return sharpe_ratio(returns, risk_free_rate, periods)
    downside_std = float(np.sqrt((downside ** 2).mean()))
    if math.isclose(downside_std, 0.0, abs_tol=1e-12):
        return sharpe_ratio(returns, risk_free_rate, periods)
    return float(excess.mean() / downside_std * math.sqrt(periods))


# ---------------------------------------------------------------------------
# Drawdown metrics
# ---------------------------------------------------------------------------

def max_drawdown(returns: pd.Series) -> float:
    """Return the maximum peak-to-trough drawdown.

    Parameters
    ----------
    returns:
        Daily return series (not price series).

    Returns
    -------
    float
        Non-positive value in [-1, 0].  0 means no drawdown.
    """
    _validate_returns(returns, "returns")
    cumulative = (1.0 + returns).cumprod()
    running_max = cumulative.cummax()
    # Guard against division by zero when price reaches 0 (total loss).
    # Where running_max == 0 the portfolio is already worthless: drawdown = -1.
    safe_max = running_max.replace(0.0, np.nan)
    drawdown = (cumulative - running_max) / safe_max
    drawdown = drawdown.fillna(-1.0)
    return float(drawdown.min())


def calmar_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.04,
    periods: int = 252,
) -> float:
    """Return the Calmar ratio: annualised return / |max drawdown|.

    Parameters
    ----------
    returns:
        Daily return series.
    risk_free_rate:
        Annual risk-free rate (unused in standard Calmar but kept for
        API consistency).
    periods:
        Periods per year for annualisation.

    Returns
    -------
    float

    Raises
    ------
    ValueError
        When max drawdown is zero (no peak-to-trough loss observed).
    """
    _validate_returns(returns, "returns")
    mdd = max_drawdown(returns)
    if math.isclose(mdd, 0.0, abs_tol=1e-12):
        raise ValueError(
            "Max drawdown is zero; Calmar ratio is undefined."
        )
    ann_return = float((1.0 + returns.mean()) ** periods - 1.0)
    return float(ann_return / abs(mdd))


# ---------------------------------------------------------------------------
# Portfolio aggregation
# ---------------------------------------------------------------------------

class PortfolioRisk:
    """Compute and report risk metrics for a weighted multi-asset portfolio.

    Parameters
    ----------
    returns:
        DataFrame where each column is an asset's daily return series.
    weights:
        Dict mapping column name to portfolio weight. Weights must sum
        to 1.0 (tolerance 1e-6).

    Raises
    ------
    ValueError
        When weights do not sum to 1.0.
    """

    _WEIGHT_TOL = 1e-6

    def __init__(
        self,
        returns: pd.DataFrame,
        weights: dict[str, float],
    ) -> None:
        total = sum(weights.values())
        if not math.isclose(total, 1.0, abs_tol=self._WEIGHT_TOL):
            raise ValueError(
                f"Weights must sum to 1.0; got {total:.6f}."
            )
        self._returns = returns
        self._weights = weights

    def portfolio_returns(self) -> pd.Series:
        """Return the weighted portfolio daily return series.

        Raises
        ------
        KeyError
            When a weight key is not present in the returns DataFrame.
        """
        series = sum(
            self._returns[ticker] * weight
            for ticker, weight in self._weights.items()
        )
        return series

    def compute(self, risk_free_rate: float = 0.04) -> dict:
        """Compute all risk metrics for the portfolio.

        Parameters
        ----------
        risk_free_rate:
            Annual risk-free rate passed to ratio metrics.

        Returns
        -------
        dict
            Keys: var_95, var_99, cvar_95, cvar_99, sharpe, sortino,
            max_drawdown, calmar.
        """
        port = self.portfolio_returns()
        mdd = max_drawdown(port)
        try:
            calmar = calmar_ratio(port, risk_free_rate)
        except ValueError:
            calmar = float("nan")

        return {
            "var_95": historical_var(port, 0.95),
            "var_99": historical_var(port, 0.99),
            "cvar_95": historical_cvar(port, 0.95),
            "cvar_99": historical_cvar(port, 0.99),
            "sharpe": sharpe_ratio(port, risk_free_rate),
            "sortino": sortino_ratio(port, risk_free_rate),
            "max_drawdown": mdd,
            "calmar": calmar,
        }

    def report(self, risk_free_rate: float = 0.04) -> str:
        """Return a formatted text summary of portfolio risk metrics.

        Parameters
        ----------
        risk_free_rate:
            Annual risk-free rate passed to compute().

        Returns
        -------
        str
        """
        m = self.compute(risk_free_rate)
        tickers = ", ".join(
            f"{t} {w:.0%}" for t, w in self._weights.items()
        )
        lines = [
            "Portfolio Risk Report",
            "=" * 40,
            f"Composition : {tickers}",
            "-" * 40,
            f"VaR  95%    : {m['var_95']:>10.4f}",
            f"VaR  99%    : {m['var_99']:>10.4f}",
            f"CVaR 95%    : {m['cvar_95']:>10.4f}",
            f"CVaR 99%    : {m['cvar_99']:>10.4f}",
            "-" * 40,
            f"Sharpe      : {m['sharpe']:>10.4f}",
            f"Sortino     : {m['sortino']:>10.4f}",
            f"Calmar      : {m['calmar']:>10.4f}",
            "-" * 40,
            f"Max Drawdown: {m['max_drawdown']:>10.4f}",
            "=" * 40,
        ]
        return "\n".join(lines)
