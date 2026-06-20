# ABOUTME: Portfolio performance benchmark vs SPY — TWR, Sharpe, max drawdown, cumulative-vs-benchmark (#27)
# ABOUTME: Pure-compute, offline. Reuses risk_metrics (Sharpe/drawdown) + projection cache loaders.
"""
Performance-metrics module for assethold (issue #27).

Answers "Am I beating the index?" with textbook, fully-offline metrics:

* **Time-weighted return (TWR)** — geometric linking of per-period returns,
  ``prod(1 + r_t) - 1``. TWR neutralises the timing/size of external cash
  flows, so it measures the *manager's* return rather than the dollar-
  weighted investor return. When period returns are derived from a single
  price series (as here), TWR equals the simple total price return.
* **Annualised Sharpe ratio** — reuses :func:`risk_metrics.sharpe_ratio`.
  Risk-free assumption: ``rf = 0.04`` (4 % annual) by default, consistent
  with the rest of the assethold risk stack; pass ``risk_free_rate=0.0``
  for the textbook zero-rf variant. Annualised with ``periods`` (252/yr).
* **Max drawdown** — peak-to-trough, reuses :func:`risk_metrics.max_drawdown`
  / :func:`risk_metrics.max_drawdown_with_dates`.
* **Cumulative-return series** — ``cumprod(1 + r) - 1`` aligned to the
  return index, for plotting an equity curve.
* **Cumulative-return-vs-benchmark** — aligns a portfolio and a benchmark
  return series on common dates and reports both cumulative curves plus the
  excess (active) return.

Benchmark / SPY handling
------------------------
SPY is **not** present in the local cache. Therefore the benchmark is a
**parameter** (any cached ticker). :func:`benchmark_comparison_from_cache`
defaults its benchmark to ``"SPY"`` but raises a clear, actionable
``FileNotFoundError`` if the ``SPY_ohlcv.csv`` cache is absent — it never
fetches. ``VOO`` (Vanguard S&P 500 ETF) is cached and tracks the same index,
so it is the recommended offline stand-in for SPY here. To enable true
SPY comparison, drop a ``data/stocks/cache/SPY_ohlcv.csv`` into the cache.

No network access. Historical data is read only from the local OHLCV cache
CSVs via the loaders already provided by :mod:`assethold.projection`.

Public API
----------
time_weighted_return       -- Geometric TWR over a return series
cumulative_returns         -- Per-step cumulative return Series
annualized_return          -- Geometric-mean annualised return
performance_summary        -- TWR + Sharpe + max drawdown + cum-return dict
benchmark_comparison       -- Align two return Series -> BenchmarkComparison
benchmark_comparison_from_cache -- Load portfolio + benchmark from cache CSVs
BenchmarkComparison        -- Dataclass: aligned cumulative curves + stats
DEFAULT_RISK_FREE_RATE     -- 0.04 (documented rf assumption)
DEFAULT_BENCHMARK          -- "SPY" (parameterisable)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd

# Reuse existing, tested helpers — do NOT duplicate.
from assethold.risk_metrics import (
    max_drawdown,
    max_drawdown_with_dates,
    sharpe_ratio,
)
from assethold.projection import (
    TRADING_DAYS_PER_YEAR,
    load_cached_returns,
    portfolio_returns,
)

# Documented default risk-free assumption (annual). Matches risk_metrics.
DEFAULT_RISK_FREE_RATE = 0.04

# Default benchmark ticker. SPY is the canonical S&P 500 proxy but is NOT
# cached here — callers should pass a cached ticker (e.g. "VOO") for offline use.
DEFAULT_BENCHMARK = "SPY"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkComparison:
    """Cumulative-return comparison of a portfolio vs a benchmark.

    Attributes
    ----------
    portfolio_name / benchmark_name:
        Labels for reporting.
    index:
        Common (aligned) index of the two return series.
    portfolio_cumulative / benchmark_cumulative:
        Cumulative-return Series ``cumprod(1+r)-1`` on the common index.
    excess_cumulative:
        portfolio_cumulative - benchmark_cumulative (active cumulative
        return; >0 means the portfolio is ahead of the benchmark).
    portfolio_twr / benchmark_twr:
        Total time-weighted return over the common window.
    excess_twr:
        portfolio_twr - benchmark_twr (total out/under-performance).
    """

    portfolio_name: str
    benchmark_name: str
    index: pd.Index
    portfolio_cumulative: pd.Series
    benchmark_cumulative: pd.Series
    excess_cumulative: pd.Series
    portfolio_twr: float
    benchmark_twr: float
    excess_twr: float
    meta: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_returns(returns: pd.Series, label: str = "returns") -> None:
    if returns is None or len(returns) == 0:
        raise ValueError(f"{label} must not be empty")


# ---------------------------------------------------------------------------
# Core return metrics
# ---------------------------------------------------------------------------

def time_weighted_return(returns: pd.Series) -> float:
    """Time-weighted return: geometric linking of period returns.

    TWR = prod_t (1 + r_t) - 1.

    Parameters
    ----------
    returns:
        Per-period (e.g. daily) *simple* return series. NaNs are dropped.

    Returns
    -------
    float
        Total time-weighted return over the whole series (0.0 == flat).
    """
    _validate_returns(returns, "returns")
    r = pd.Series(returns).dropna()
    _validate_returns(r, "returns")
    return float(np.prod(1.0 + r.values) - 1.0)


def cumulative_returns(returns: pd.Series) -> pd.Series:
    """Per-step cumulative return series: cumprod(1 + r) - 1.

    The last value equals :func:`time_weighted_return`. Index is preserved.
    """
    _validate_returns(returns, "returns")
    r = pd.Series(returns).dropna()
    _validate_returns(r, "returns")
    cum = (1.0 + r).cumprod() - 1.0
    cum.name = getattr(returns, "name", None) or "cumulative_return"
    return cum


def annualized_return(
    returns: pd.Series,
    periods: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Geometric annualised return implied by the period returns.

    ``(1 + TWR) ** (periods / n_obs) - 1`` where ``n_obs`` is the number of
    observed periods. Uses the actual observation count so a partial-year
    sample is scaled up to an annual figure.
    """
    _validate_returns(returns, "returns")
    r = pd.Series(returns).dropna()
    _validate_returns(r, "returns")
    twr = time_weighted_return(r)
    n = len(r)
    if n == 0:
        raise ValueError("returns must not be empty")
    return float((1.0 + twr) ** (periods / n) - 1.0)


def performance_summary(
    returns: pd.Series,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    periods: int = TRADING_DAYS_PER_YEAR,
) -> dict:
    """Textbook performance metrics for a single return series.

    Returns a dict with: twr, annualized_return, sharpe, max_drawdown,
    drawdown_detail (DrawdownResult), cumulative (Series).

    Sharpe / drawdown reuse :mod:`assethold.risk_metrics`. Sharpe is
    undefined for zero-volatility input, so it is reported as NaN there
    rather than raising (keeps the summary usable for flat series).
    """
    _validate_returns(returns, "returns")
    r = pd.Series(returns).dropna()
    _validate_returns(r, "returns")
    try:
        sharpe = sharpe_ratio(r, risk_free_rate=risk_free_rate, periods=periods)
    except ValueError:
        sharpe = float("nan")
    return {
        "twr": time_weighted_return(r),
        "annualized_return": annualized_return(r, periods=periods),
        "sharpe": sharpe,
        "max_drawdown": max_drawdown(r),
        "drawdown_detail": max_drawdown_with_dates(r),
        "cumulative": cumulative_returns(r),
        "risk_free_rate": float(risk_free_rate),
        "n_periods": int(len(r)),
    }


# ---------------------------------------------------------------------------
# Benchmark comparison
# ---------------------------------------------------------------------------

def benchmark_comparison(
    portfolio_returns_series: pd.Series,
    benchmark_returns_series: pd.Series,
    portfolio_name: str = "portfolio",
    benchmark_name: str = DEFAULT_BENCHMARK,
) -> BenchmarkComparison:
    """Compare cumulative returns of a portfolio vs a benchmark.

    The two series are aligned on their **common** index (inner join) so the
    comparison is apples-to-apples over the overlapping window. Returns a
    :class:`BenchmarkComparison` with both cumulative curves, the excess
    (active) cumulative curve, and total TWR for each plus the excess TWR.

    Parameters
    ----------
    portfolio_returns_series / benchmark_returns_series:
        Per-period simple-return Series indexed by date.
    portfolio_name / benchmark_name:
        Labels for the result / plotting layer.

    Raises
    ------
    ValueError
        When either series is empty or they share no common dates.
    """
    _validate_returns(portfolio_returns_series, "portfolio_returns_series")
    _validate_returns(benchmark_returns_series, "benchmark_returns_series")

    frame = pd.DataFrame(
        {"p": pd.Series(portfolio_returns_series),
         "b": pd.Series(benchmark_returns_series)}
    ).dropna()
    if frame.empty:
        raise ValueError(
            "portfolio and benchmark return series share no common dates"
        )

    p = frame["p"]
    b = frame["b"]

    p_cum = (1.0 + p).cumprod() - 1.0
    b_cum = (1.0 + b).cumprod() - 1.0
    p_cum.name = portfolio_name
    b_cum.name = benchmark_name

    excess = p_cum - b_cum
    excess.name = f"{portfolio_name}_minus_{benchmark_name}"

    p_twr = float(np.prod(1.0 + p.values) - 1.0)
    b_twr = float(np.prod(1.0 + b.values) - 1.0)

    return BenchmarkComparison(
        portfolio_name=portfolio_name,
        benchmark_name=benchmark_name,
        index=frame.index,
        portfolio_cumulative=p_cum,
        benchmark_cumulative=b_cum,
        excess_cumulative=excess,
        portfolio_twr=p_twr,
        benchmark_twr=b_twr,
        excess_twr=p_twr - b_twr,
        meta={"n_periods": int(len(frame))},
    )


def benchmark_comparison_from_cache(
    portfolio_tickers,
    benchmark: str = DEFAULT_BENCHMARK,
    weights: Optional[Mapping[str, float]] = None,
    cache_dir: Optional[str] = None,
    portfolio_name: str = "portfolio",
) -> BenchmarkComparison:
    """Build a benchmark comparison entirely from local cache CSVs.

    Loads daily returns for ``portfolio_tickers`` (blended with optional
    ``weights`` via :func:`assethold.projection.portfolio_returns`) and for
    the ``benchmark`` ticker, then delegates to :func:`benchmark_comparison`.

    SPY note
    --------
    ``benchmark`` defaults to ``"SPY"``, the canonical S&P 500 proxy. SPY is
    **not** cached in this repo, so this call raises ``FileNotFoundError``
    until ``data/stocks/cache/SPY_ohlcv.csv`` exists. It NEVER fetches. For
    a fully-offline run pass ``benchmark="VOO"`` (cached S&P 500 ETF).

    Parameters
    ----------
    portfolio_tickers:
        A single ticker (str) or an iterable of tickers.
    benchmark:
        Benchmark ticker (default "SPY"; use "VOO" offline).
    weights:
        Optional weight map for multi-ticker portfolios (equal-weight
        otherwise). Ignored for a single ticker.
    cache_dir:
        Override the cache directory (defaults to the projection module's).
    portfolio_name:
        Label for the portfolio leg.
    """
    if isinstance(portfolio_tickers, str):
        tickers = [portfolio_tickers]
    else:
        tickers = list(portfolio_tickers)
    if not tickers:
        raise ValueError("portfolio_tickers must be non-empty")

    load_kw = {} if cache_dir is None else {"cache_dir": cache_dir}

    returns_by_symbol = {
        t: load_cached_returns(t, **load_kw) for t in tickers
    }
    if len(tickers) == 1:
        port = returns_by_symbol[tickers[0]]
        port.name = portfolio_name
    else:
        port = portfolio_returns(returns_by_symbol, weights=weights)

    bench = load_cached_returns(benchmark, **load_kw)

    return benchmark_comparison(
        port,
        bench,
        portfolio_name=portfolio_name,
        benchmark_name=benchmark,
    )
