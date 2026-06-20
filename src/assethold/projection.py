# ABOUTME: Monte Carlo portfolio outlook — P10/P50/P90 projection bands + fan-chart spec (#28)
# ABOUTME: Pure-compute, seedable simulation of future value paths from historical daily returns
"""
Monte Carlo projection module for assethold.

Projects the probable future value range of a holding or weighted
portfolio over multiple horizons (3 months -- 10 years) by simulating
future return paths from a historical daily-return distribution, then
extracting percentile bands (P10 / P50 / P90 by default).

Two simulation models are supported:

* ``"gbm"`` (default) -- Geometric Brownian Motion.  Estimates drift
  (mean) and volatility (std) of historical *log* returns and draws
  i.i.d. normal shocks.  Smooth, parametric, fully reproducible.
* ``"bootstrap"`` -- Historical bootstrap.  Resamples observed daily
  simple returns with replacement.  Non-parametric; preserves fat tails
  and skew of the empirical distribution.

All randomness flows through an explicit ``numpy`` ``Generator`` seeded
by the ``seed`` argument, so results are deterministic for a given seed.

No network access. Historical data is read from the local OHLCV cache
CSVs (``data/stocks/cache/<TICKER>_ohlcv.csv``) via :func:`load_cached_returns`.

Public API
----------
load_cached_prices      -- Read a cached OHLCV CSV -> close-price Series
load_cached_returns     -- Cached CSV -> daily simple-return Series
daily_log_returns       -- Simple-return Series -> daily log returns
portfolio_returns       -- Weighted blend of per-symbol return Series
simulate_paths          -- Core Monte Carlo path simulator (N x steps)
project_value           -- High-level projection -> ProjectionResult
project_horizons        -- Multi-horizon outlook table
fan_chart_spec          -- Structured spec the plotting layer consumes
HORIZON_TRADING_DAYS    -- Standard horizon -> trading-day mapping
ProjectionResult        -- Dataclass with bands, terminal pcts, sample paths
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

import numpy as np
import pandas as pd


# Approx. 252 trading days per year.
TRADING_DAYS_PER_YEAR = 252

# Standard projection horizons -> trading days (issue #28 horizon table).
HORIZON_TRADING_DAYS: dict[str, int] = {
    "3-month": 63,
    "6-month": 126,
    "1-year": 252,
    "3-year": 756,
    "5-year": 1260,
    "10-year": 2520,
}

# Default percentile bands. P10 (bear) / P50 (median) / P90 (bull).
DEFAULT_PERCENTILES: tuple[float, ...] = (10.0, 50.0, 90.0)

# Repo-root-relative default cache location.
_DEFAULT_CACHE_DIR = os.path.join("data", "stocks", "cache")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ProjectionResult:
    """Result of a Monte Carlo projection over a single horizon.

    Attributes
    ----------
    start_value:
        Portfolio / holding value at the projection origin (t=0).
    horizon_days:
        Number of trading-day steps simulated.
    percentiles:
        The requested percentile levels (e.g. (10, 50, 90)).
    terminal:
        Mapping percentile -> terminal value at the final step.
    bands:
        Mapping percentile -> np.ndarray of length ``horizon_days + 1``
        giving the value at each step (index 0 == ``start_value``).
    steps:
        Integer step axis ``0 .. horizon_days`` (length horizon_days+1).
    sample_paths:
        2-D array (n_sample_paths x horizon_days+1) of individual
        simulated trajectories for plotting translucent MC lines.
    model:
        Simulation model used ("gbm" or "bootstrap").
    seed:
        Seed used for the RNG (None if unseeded).
    """

    start_value: float
    horizon_days: int
    percentiles: tuple[float, ...]
    terminal: dict[float, float]
    bands: dict[float, np.ndarray]
    steps: np.ndarray
    sample_paths: np.ndarray
    model: str
    seed: Optional[int] = None
    meta: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Local data loading (cache CSVs only -- NO network)
# ---------------------------------------------------------------------------

def load_cached_prices(
    ticker: str,
    cache_dir: str = _DEFAULT_CACHE_DIR,
) -> pd.Series:
    """Load close prices from a local cached OHLCV CSV.

    The CSV is expected to have columns ``date,open,high,low,close,volume``
    (the flat-file cache format under ``data/stocks/cache/``).

    Returns a float Series indexed by parsed dates, sorted ascending.
    Raises FileNotFoundError if the cache file is absent (never fetches).
    """
    path = os.path.join(cache_dir, f"{ticker}_ohlcv.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No cached OHLCV CSV for {ticker!r} at {path!r}. "
            "Projection is offline-only; populate the cache first."
        )
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    if "close" not in cols or "date" not in cols:
        raise ValueError(
            f"Cache CSV {path!r} missing 'date'/'close' columns; got {list(df.columns)}"
        )
    s = pd.Series(
        df[cols["close"]].astype(float).values,
        index=pd.to_datetime(df[cols["date"]]),
        name=ticker,
    )
    return s.sort_index()


def load_cached_returns(
    ticker: str,
    cache_dir: str = _DEFAULT_CACHE_DIR,
) -> pd.Series:
    """Daily *simple* returns from a cached OHLCV CSV.

    Simple return r_t = P_t / P_{t-1} - 1. Leading NaN is dropped.
    """
    prices = load_cached_prices(ticker, cache_dir=cache_dir)
    return prices.pct_change().dropna()


def daily_log_returns(simple_returns: pd.Series | np.ndarray | Sequence[float]) -> np.ndarray:
    """Convert simple returns to log returns: ln(1 + r)."""
    r = np.asarray(simple_returns, dtype=float)
    return np.log1p(r)


def portfolio_returns(
    returns_by_symbol: Mapping[str, pd.Series],
    weights: Optional[Mapping[str, float]] = None,
) -> pd.Series:
    """Blend per-symbol simple-return Series into a portfolio return Series.

    Returns are aligned on their common dates (inner join). ``weights``
    default to equal weight and are normalised to sum to 1.
    """
    if not returns_by_symbol:
        raise ValueError("returns_by_symbol must be non-empty")

    frame = pd.DataFrame(dict(returns_by_symbol)).dropna()
    symbols = list(frame.columns)

    if weights is None:
        w = np.full(len(symbols), 1.0 / len(symbols))
    else:
        w = np.array([float(weights.get(sym, 0.0)) for sym in symbols], dtype=float)
        total = w.sum()
        if total <= 0:
            raise ValueError("weights must sum to a positive number")
        w = w / total

    blended = frame.values @ w
    return pd.Series(blended, index=frame.index, name="portfolio")


# ---------------------------------------------------------------------------
# Core Monte Carlo simulation
# ---------------------------------------------------------------------------

def simulate_paths(
    historical_returns: pd.Series | np.ndarray | Sequence[float],
    horizon_days: int,
    n_paths: int = 1000,
    model: str = "gbm",
    seed: Optional[int] = None,
    start_value: float = 1.0,
) -> np.ndarray:
    """Simulate Monte Carlo value paths from historical daily returns.

    Parameters
    ----------
    historical_returns:
        Daily *simple* returns (e.g. from :func:`load_cached_returns`).
    horizon_days:
        Number of forward trading-day steps to simulate (>= 1).
    n_paths:
        Number of simulated paths (>= 1).
    model:
        ``"gbm"`` -- normal log-return shocks with drift mu and vol sigma
        estimated from the history. ``"bootstrap"`` -- resample observed
        simple returns with replacement.
    seed:
        RNG seed for reproducibility.
    start_value:
        Value at t=0 (column 0 of the output equals this exactly).

    Returns
    -------
    np.ndarray of shape ``(n_paths, horizon_days + 1)``. Column 0 is
    ``start_value`` for every path; subsequent columns are cumulative
    value along each simulated trajectory.
    """
    if horizon_days < 1:
        raise ValueError("horizon_days must be >= 1")
    if n_paths < 1:
        raise ValueError("n_paths must be >= 1")

    r = np.asarray(historical_returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0:
        raise ValueError("historical_returns has no finite observations")

    rng = np.random.default_rng(seed)

    if model == "gbm":
        log_r = np.log1p(r)
        mu = float(np.mean(log_r))
        # ddof=1 for an unbiased sample std; with a single observation
        # std is 0 -> deterministic path (degenerate but well-defined).
        sigma = float(np.std(log_r, ddof=1)) if log_r.size > 1 else 0.0
        shocks = rng.normal(mu, sigma, size=(n_paths, horizon_days))
        step_growth = np.exp(shocks)  # per-step gross multiplier
    elif model == "bootstrap":
        sampled = rng.choice(r, size=(n_paths, horizon_days), replace=True)
        step_growth = 1.0 + sampled
    else:
        raise ValueError(f"unknown model {model!r}; use 'gbm' or 'bootstrap'")

    cum = np.cumprod(step_growth, axis=1)
    paths = np.empty((n_paths, horizon_days + 1), dtype=float)
    paths[:, 0] = start_value
    paths[:, 1:] = start_value * cum
    return paths


# ---------------------------------------------------------------------------
# High-level projection
# ---------------------------------------------------------------------------

def project_value(
    historical_returns: pd.Series | np.ndarray | Sequence[float],
    horizon_days: int,
    start_value: float = 1.0,
    n_paths: int = 1000,
    percentiles: Sequence[float] = DEFAULT_PERCENTILES,
    model: str = "gbm",
    seed: Optional[int] = None,
    n_sample_paths: int = 50,
) -> ProjectionResult:
    """Project future value with percentile bands over one horizon.

    Returns a :class:`ProjectionResult` carrying, for each requested
    percentile, the terminal value and the per-step band, plus a handful
    of individual sample paths for fan-chart plotting.
    """
    pcts = tuple(float(p) for p in percentiles)

    paths = simulate_paths(
        historical_returns,
        horizon_days=horizon_days,
        n_paths=n_paths,
        model=model,
        seed=seed,
        start_value=start_value,
    )

    # Percentile across paths at every step -> shape (len(pcts), steps).
    band_matrix = np.percentile(paths, pcts, axis=0)
    bands = {p: band_matrix[i] for i, p in enumerate(pcts)}
    terminal = {p: float(band_matrix[i, -1]) for i, p in enumerate(pcts)}

    steps = np.arange(horizon_days + 1)
    n_show = min(n_sample_paths, paths.shape[0])
    sample_paths = paths[:n_show].copy()

    return ProjectionResult(
        start_value=float(start_value),
        horizon_days=int(horizon_days),
        percentiles=pcts,
        terminal=terminal,
        bands=bands,
        steps=steps,
        sample_paths=sample_paths,
        model=model,
        seed=seed,
        meta={"n_paths": int(n_paths)},
    )


def project_horizons(
    historical_returns: pd.Series | np.ndarray | Sequence[float],
    start_value: float = 1.0,
    horizons: Optional[Mapping[str, int]] = None,
    n_paths: int = 1000,
    percentiles: Sequence[float] = DEFAULT_PERCENTILES,
    model: str = "gbm",
    seed: Optional[int] = None,
) -> dict[str, ProjectionResult]:
    """Project across several named horizons (issue #28 outlook table).

    Each horizon uses a fresh RNG seeded with ``seed`` so results are
    reproducible and independent of dict iteration order.
    """
    horizons = dict(horizons) if horizons is not None else dict(HORIZON_TRADING_DAYS)
    out: dict[str, ProjectionResult] = {}
    for label, days in horizons.items():
        out[label] = project_value(
            historical_returns,
            horizon_days=days,
            start_value=start_value,
            n_paths=n_paths,
            percentiles=percentiles,
            model=model,
            seed=seed,
        )
    return out


# ---------------------------------------------------------------------------
# Fan-chart spec (structured data for the plotting layer)
# ---------------------------------------------------------------------------

def fan_chart_spec(
    result: ProjectionResult,
    historical_values: Optional[Sequence[float]] = None,
    milestones: Optional[Sequence[float]] = None,
    title: str = "Portfolio Future Outlook",
) -> dict[str, Any]:
    """Build a plotting-layer-agnostic fan-chart spec from a result.

    The spec is plain JSON-able Python (lists/floats/strings) describing
    the elements the issue's Plotly fan chart needs: shaded P10-P90 band,
    median line, translucent sample paths, the current-value marker, an
    optional trailing-history segment, and milestone lines.

    Step axes are returned as plain int lists; value series as float lists.
    """
    steps = result.steps.tolist()

    # Shaded bands: pair the lowest with the highest available percentile.
    pcts_sorted = sorted(result.percentiles)
    band_specs = []
    if len(pcts_sorted) >= 2:
        lo, hi = pcts_sorted[0], pcts_sorted[-1]
        band_specs.append({
            "label": f"P{int(lo)}-P{int(hi)}",
            "lower_percentile": lo,
            "upper_percentile": hi,
            "lower": result.bands[lo].tolist(),
            "upper": result.bands[hi].tolist(),
            "fill": "light",
        })

    # Median line (P50 if present, else the central requested percentile).
    if 50.0 in result.bands:
        median_p = 50.0
    else:
        median_p = pcts_sorted[len(pcts_sorted) // 2]
    median_line = {
        "label": f"P{int(median_p)} (median)",
        "percentile": median_p,
        "values": result.bands[median_p].tolist(),
    }

    sample_lines = [row.tolist() for row in result.sample_paths]

    spec: dict[str, Any] = {
        "title": title,
        "model": result.model,
        "seed": result.seed,
        "horizon_days": result.horizon_days,
        "start_value": result.start_value,
        "x": {"steps": steps, "unit": "trading_days"},
        "bands": band_specs,
        "median": median_line,
        "sample_paths": sample_lines,
        "current_value_marker": {"step": 0, "value": result.start_value},
        "percentile_terminal": {
            f"P{int(p)}": result.terminal[p] for p in result.percentiles
        },
    }

    if historical_values is not None:
        hist = [float(v) for v in historical_values]
        # History flows in on negative steps ending at -1, transitioning to step 0.
        spec["history"] = {
            "steps": list(range(-len(hist), 0)),
            "values": hist,
        }

    if milestones is not None:
        spec["milestones"] = [float(m) for m in milestones]

    return spec
