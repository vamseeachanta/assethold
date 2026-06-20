"""Tests for the Monte Carlo projection module (issue #28).

Covers: percentile ordering (P10 < P50 < P90), wider bands for longer
horizons, deterministic zero-vol input, shape/percentile correctness,
seed reproducibility, bootstrap model, fan-chart spec structure, and a
smoke test over one cached OHLCV CSV.

All randomness is seeded for determinism. No network access.
"""
import os

import numpy as np
import pandas as pd
import pytest

from assethold.projection import (
    HORIZON_TRADING_DAYS,
    ProjectionResult,
    daily_log_returns,
    fan_chart_spec,
    load_cached_prices,
    load_cached_returns,
    portfolio_returns,
    project_horizons,
    project_value,
    simulate_paths,
)

# Repo root = two levels up from this test file (tests/test_projection.py).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(REPO_ROOT, "data", "stocks", "cache")


@pytest.fixture
def synthetic_returns():
    """Small synthetic daily-return series, fixed for exactness."""
    rng = np.random.default_rng(7)
    # mean ~0.0005/day, vol ~1.5%/day, 252 obs
    return pd.Series(rng.normal(0.0005, 0.015, 252))


# ---------------------------------------------------------------------------
# Percentile ordering
# ---------------------------------------------------------------------------

def test_percentile_ordering_terminal(synthetic_returns):
    res = project_value(
        synthetic_returns, horizon_days=252, start_value=1000.0,
        n_paths=2000, seed=42,
    )
    assert res.terminal[10.0] < res.terminal[50.0] < res.terminal[90.0]


def test_percentile_ordering_every_step(synthetic_returns):
    res = project_value(
        synthetic_returns, horizon_days=126, start_value=500.0,
        n_paths=2000, seed=1,
    )
    p10, p50, p90 = res.bands[10.0], res.bands[50.0], res.bands[90.0]
    # Strictly ordered from step 1 onward (step 0 is the shared start value).
    assert np.all(p10[1:] < p50[1:])
    assert np.all(p50[1:] < p90[1:])
    # Step 0 equals start_value for all bands.
    assert p10[0] == pytest.approx(500.0)
    assert p90[0] == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# Longer horizon -> wider bands
# ---------------------------------------------------------------------------

def test_longer_horizon_wider_bands():
    # Use a mildly positive-drift series so terminal dollar dispersion grows
    # with horizon. (Under GBM a strongly negative drift squeezes the whole
    # distribution toward zero, shrinking the *absolute* spread even as the
    # log-spread widens; that is an expected multiplicative-scale effect.)
    rng = np.random.default_rng(21)
    pos = pd.Series(rng.normal(0.0004, 0.012, 504))
    short = project_value(pos, horizon_days=63, start_value=1000.0, n_paths=3000, seed=99)
    long = project_value(pos, horizon_days=756, start_value=1000.0, n_paths=3000, seed=99)
    short_spread = short.terminal[90.0] - short.terminal[10.0]
    long_spread = long.terminal[90.0] - long.terminal[10.0]
    assert long_spread > short_spread


def test_band_widens_monotonically(synthetic_returns):
    res = project_value(synthetic_returns, horizon_days=252, n_paths=3000, seed=5)
    spread = res.bands[90.0] - res.bands[10.0]
    # Spread at the end is much wider than near the start.
    assert spread[-1] > spread[1]
    assert spread[0] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Zero-volatility -> deterministic path
# ---------------------------------------------------------------------------

def test_zero_vol_deterministic_gbm():
    # Constant daily return -> zero std of log returns -> deterministic.
    const_r = pd.Series([0.001] * 100)
    res = project_value(const_r, horizon_days=50, start_value=1000.0,
                        n_paths=500, seed=3, model="gbm")
    # All bands collapse onto the single deterministic trajectory.
    assert res.terminal[10.0] == pytest.approx(res.terminal[90.0])
    assert res.terminal[50.0] == pytest.approx(res.terminal[10.0])
    # Closed-form: 1000 * (1.001)^50
    expected = 1000.0 * (1.001 ** 50)
    assert res.terminal[50.0] == pytest.approx(expected, rel=1e-9)


def test_zero_vol_deterministic_bootstrap():
    const_r = pd.Series([0.002] * 80)
    res = project_value(const_r, horizon_days=30, start_value=100.0,
                        n_paths=400, seed=2, model="bootstrap")
    # Resampling a constant series is also deterministic.
    expected = 100.0 * (1.002 ** 30)
    assert res.terminal[10.0] == pytest.approx(expected, rel=1e-9)
    assert res.terminal[90.0] == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# Shape / percentile correctness
# ---------------------------------------------------------------------------

def test_simulate_paths_shape_and_start():
    r = pd.Series([0.01, -0.005, 0.002, 0.0])
    paths = simulate_paths(r, horizon_days=20, n_paths=37, seed=1, start_value=250.0)
    assert paths.shape == (37, 21)
    assert np.all(paths[:, 0] == 250.0)


def test_band_values_match_numpy_percentile():
    r = pd.Series([0.01, -0.01, 0.005, -0.002, 0.003])
    res = project_value(r, horizon_days=10, start_value=1.0, n_paths=500,
                        seed=11, percentiles=(10, 50, 90))
    paths = simulate_paths(r, horizon_days=10, n_paths=500, seed=11, start_value=1.0)
    expected_p50 = np.percentile(paths, 50, axis=0)
    np.testing.assert_allclose(res.bands[50.0], expected_p50)
    assert res.terminal[90.0] == pytest.approx(np.percentile(paths[:, -1], 90))


def test_sample_paths_count_capped():
    r = pd.Series([0.01, -0.01, 0.0])
    res = project_value(r, horizon_days=5, n_paths=20, seed=1, n_sample_paths=50)
    # n_sample_paths requested > n_paths -> capped at n_paths.
    assert res.sample_paths.shape == (20, 6)


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

def test_seed_reproducible(synthetic_returns):
    a = project_value(synthetic_returns, horizon_days=100, n_paths=500, seed=123)
    b = project_value(synthetic_returns, horizon_days=100, n_paths=500, seed=123)
    np.testing.assert_array_equal(a.sample_paths, b.sample_paths)
    assert a.terminal == b.terminal


def test_different_seeds_differ(synthetic_returns):
    a = project_value(synthetic_returns, horizon_days=100, n_paths=500, seed=1)
    b = project_value(synthetic_returns, horizon_days=100, n_paths=500, seed=2)
    assert a.terminal[50.0] != b.terminal[50.0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_daily_log_returns():
    r = np.array([0.0, 0.1, -0.05])
    lg = daily_log_returns(r)
    np.testing.assert_allclose(lg, np.log1p(r))


def test_portfolio_returns_equal_weight():
    s1 = pd.Series([0.01, 0.02, 0.03])
    s2 = pd.Series([0.03, 0.02, 0.01])
    blended = portfolio_returns({"A": s1, "B": s2})
    np.testing.assert_allclose(blended.values, [0.02, 0.02, 0.02])


def test_portfolio_returns_weighted():
    s1 = pd.Series([0.10, 0.10])
    s2 = pd.Series([0.00, 0.00])
    blended = portfolio_returns({"A": s1, "B": s2}, weights={"A": 3, "B": 1})
    # 3:1 weight -> 0.075
    np.testing.assert_allclose(blended.values, [0.075, 0.075])


def test_project_horizons_all_labels(synthetic_returns):
    out = project_horizons(synthetic_returns, start_value=1000.0, n_paths=300, seed=4)
    assert set(out.keys()) == set(HORIZON_TRADING_DAYS.keys())
    for label, res in out.items():
        assert isinstance(res, ProjectionResult)
        assert res.horizon_days == HORIZON_TRADING_DAYS[label]


# ---------------------------------------------------------------------------
# Fan-chart spec
# ---------------------------------------------------------------------------

def test_fan_chart_spec_structure(synthetic_returns):
    res = project_value(synthetic_returns, horizon_days=252, start_value=1000.0,
                        n_paths=500, seed=8, n_sample_paths=10)
    spec = fan_chart_spec(
        res,
        historical_values=[980.0, 990.0, 1000.0],
        milestones=[1500.0, 2000.0],
        title="Test Outlook",
    )
    assert spec["title"] == "Test Outlook"
    assert spec["model"] == "gbm"
    assert spec["seed"] == 8
    assert len(spec["x"]["steps"]) == 253
    assert len(spec["bands"]) == 1
    assert spec["bands"][0]["lower_percentile"] == 10.0
    assert spec["bands"][0]["upper_percentile"] == 90.0
    assert len(spec["bands"][0]["lower"]) == 253
    assert spec["median"]["percentile"] == 50.0
    assert len(spec["sample_paths"]) == 10
    assert spec["current_value_marker"] == {"step": 0, "value": 1000.0}
    assert spec["history"]["steps"] == [-3, -2, -1]
    assert spec["milestones"] == [1500.0, 2000.0]


# ---------------------------------------------------------------------------
# Smoke test over a real cached CSV (offline; file must exist)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.path.exists(os.path.join(CACHE_DIR, "AAPL_ohlcv.csv")),
    reason="AAPL cache CSV not present",
)
def test_smoke_cached_csv():
    prices = load_cached_prices("AAPL", cache_dir=CACHE_DIR)
    assert len(prices) > 50
    returns = load_cached_returns("AAPL", cache_dir=CACHE_DIR)
    assert len(returns) == len(prices) - 1

    start_value = float(prices.iloc[-1])
    res = project_value(returns, horizon_days=HORIZON_TRADING_DAYS["1-year"],
                        start_value=start_value, n_paths=1000, seed=2026)
    assert res.terminal[10.0] < res.terminal[50.0] < res.terminal[90.0]
    spec = fan_chart_spec(res, milestones=[start_value * 2])
    assert spec["horizon_days"] == 252


def test_load_missing_ticker_raises():
    with pytest.raises(FileNotFoundError):
        load_cached_prices("NO_SUCH_TICKER_XYZ", cache_dir=CACHE_DIR)
