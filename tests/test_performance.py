"""Tests for the performance-benchmark module (issue #27).

Covers: TWR geometric linking (hand-computed exact value), cumulative-
return series (last == TWR), annualised return, Sharpe sign / zero-vol
behaviour (reused from risk_metrics), max drawdown on a constructed
peak-trough series (exact value), benchmark-comparison shape + alignment,
and an offline smoke test over cached OHLCV CSVs (VOO as SPY stand-in).

All series are deterministic / hand-constructed. No network access.
"""
import math
import os

import numpy as np
import pandas as pd
import pytest

from assethold.performance import (
    DEFAULT_BENCHMARK,
    DEFAULT_RISK_FREE_RATE,
    BenchmarkComparison,
    annualized_return,
    benchmark_comparison,
    benchmark_comparison_from_cache,
    cumulative_returns,
    performance_summary,
    time_weighted_return,
)

# Repo root = two levels up (tests/test_performance.py).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(REPO_ROOT, "data", "stocks", "cache")


# ---------------------------------------------------------------------------
# Time-weighted return — exact, hand-computed
# ---------------------------------------------------------------------------

def test_twr_geometric_linking_exact():
    # 1.10 * 0.95 * 1.20 - 1 = 0.254 exactly.
    r = pd.Series([0.10, -0.05, 0.20])
    assert time_weighted_return(r) == pytest.approx(0.254, abs=1e-12)


def test_twr_flat_series_is_zero():
    r = pd.Series([0.0, 0.0, 0.0])
    assert time_weighted_return(r) == pytest.approx(0.0, abs=1e-15)


def test_twr_drops_nan():
    r = pd.Series([0.10, np.nan, -0.05, 0.20])
    # NaN dropped -> same as the clean three-period series.
    assert time_weighted_return(r) == pytest.approx(0.254, abs=1e-12)


def test_twr_empty_raises():
    with pytest.raises(ValueError):
        time_weighted_return(pd.Series([], dtype=float))


# ---------------------------------------------------------------------------
# Cumulative return series
# ---------------------------------------------------------------------------

def test_cumulative_returns_values_and_last_equals_twr():
    r = pd.Series([0.10, -0.05, 0.20])
    cum = cumulative_returns(r)
    # cumprod-1: [0.10, 1.10*0.95-1=0.045, 0.254]
    expected = [0.10, 0.045, 0.254]
    assert list(cum.round(12).values) == pytest.approx(expected, abs=1e-12)
    assert cum.iloc[-1] == pytest.approx(time_weighted_return(r), abs=1e-12)


def test_cumulative_preserves_index():
    idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
    r = pd.Series([0.10, -0.05, 0.20], index=idx)
    cum = cumulative_returns(r)
    assert list(cum.index) == list(idx)


# ---------------------------------------------------------------------------
# Annualised return
# ---------------------------------------------------------------------------

def test_annualized_return_full_year_equals_twr():
    # n == periods -> exponent 1 -> annualised == TWR.
    r = pd.Series([0.001] * 252)
    twr = time_weighted_return(r)
    assert annualized_return(r, periods=252) == pytest.approx(twr, abs=1e-12)


def test_annualized_scales_partial_window_up():
    # 3 obs scaled to 252/3 = 84 compounding blocks: (1.254)**84 - 1.
    r = pd.Series([0.10, -0.05, 0.20])
    expected = (1.254) ** (252 / 3) - 1.0
    assert annualized_return(r, periods=252) == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# Sharpe — sign / zero-vol behaviour (reused from risk_metrics)
# ---------------------------------------------------------------------------

def test_sharpe_positive_for_strong_uptrend():
    rng = np.random.default_rng(11)
    # Strong positive drift, modest vol -> positive Sharpe at rf=0.
    r = pd.Series(rng.normal(0.003, 0.005, 252))
    s = performance_summary(r, risk_free_rate=0.0)["sharpe"]
    assert s > 0


def test_sharpe_negative_for_downtrend():
    rng = np.random.default_rng(11)
    r = pd.Series(rng.normal(-0.003, 0.005, 252))
    s = performance_summary(r, risk_free_rate=0.0)["sharpe"]
    assert s < 0


def test_sharpe_nan_for_zero_volatility():
    # Constant return -> zero vol -> Sharpe undefined -> reported NaN.
    r = pd.Series([0.001] * 50)
    assert math.isnan(performance_summary(r)["sharpe"])


# ---------------------------------------------------------------------------
# Max drawdown — exact, constructed peak-trough series
# ---------------------------------------------------------------------------

def test_max_drawdown_exact_peak_trough():
    # cum value: 1.5 -> 0.9. running max 1.5. drawdown = (0.9-1.5)/1.5 = -0.40.
    r = pd.Series([0.50, -0.40])
    summ = performance_summary(r)
    assert summ["max_drawdown"] == pytest.approx(-0.40, abs=1e-12)


def test_max_drawdown_zero_for_monotonic_gains():
    r = pd.Series([0.05, 0.05, 0.05])
    assert performance_summary(r)["max_drawdown"] == pytest.approx(0.0, abs=1e-12)


def test_drawdown_detail_dates():
    idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
    # gain to peak at day2, trough at day3.
    r = pd.Series([0.50, 0.0, -0.40], index=idx)
    detail = performance_summary(r)["drawdown_detail"]
    assert detail.trough_date == idx[-1]


# ---------------------------------------------------------------------------
# Benchmark comparison — shape, alignment, excess
# ---------------------------------------------------------------------------

def test_benchmark_comparison_shape_and_excess():
    idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
    port = pd.Series([0.10, -0.05, 0.20], index=idx)
    bench = pd.Series([0.05, 0.00, 0.05], index=idx)
    cmp = benchmark_comparison(port, bench, "myport", "VOO")

    assert isinstance(cmp, BenchmarkComparison)
    assert cmp.benchmark_name == "VOO"
    assert len(cmp.portfolio_cumulative) == 3
    assert len(cmp.benchmark_cumulative) == 3
    assert len(cmp.excess_cumulative) == 3

    # port TWR = 0.254 ; bench TWR = 1.05*1.00*1.05 - 1 = 0.1025.
    assert cmp.portfolio_twr == pytest.approx(0.254, abs=1e-12)
    assert cmp.benchmark_twr == pytest.approx(0.1025, abs=1e-12)
    assert cmp.excess_twr == pytest.approx(0.254 - 0.1025, abs=1e-12)

    # excess_cumulative == portfolio_cum - benchmark_cum, elementwise.
    diff = cmp.portfolio_cumulative - cmp.benchmark_cumulative
    assert np.allclose(cmp.excess_cumulative.values, diff.values)


def test_benchmark_comparison_inner_joins_on_common_dates():
    idx_p = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
    idx_b = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-04"])
    port = pd.Series([0.10, -0.05, 0.20], index=idx_p)
    bench = pd.Series([0.01, 0.02, 0.03], index=idx_b)
    cmp = benchmark_comparison(port, bench)
    # Only 2025-01-02 and 2025-01-03 overlap.
    assert len(cmp.index) == 2
    assert list(cmp.index) == list(pd.to_datetime(["2025-01-02", "2025-01-03"]))


def test_benchmark_comparison_no_overlap_raises():
    port = pd.Series([0.1], index=pd.to_datetime(["2025-01-01"]))
    bench = pd.Series([0.1], index=pd.to_datetime(["2025-02-01"]))
    with pytest.raises(ValueError):
        benchmark_comparison(port, bench)


def test_default_benchmark_is_spy():
    assert DEFAULT_BENCHMARK == "SPY"
    assert DEFAULT_RISK_FREE_RATE == 0.04


# ---------------------------------------------------------------------------
# Offline smoke tests over cached CSVs
# ---------------------------------------------------------------------------

def _has_cache(ticker: str) -> bool:
    return os.path.exists(os.path.join(CACHE_DIR, f"{ticker}_ohlcv.csv"))


@pytest.mark.skipif(
    not (_has_cache("AAPL") and _has_cache("VOO")),
    reason="cached AAPL/VOO OHLCV CSVs required",
)
def test_smoke_benchmark_from_cache_voo():
    # VOO stands in for SPY (S&P 500 ETF) in offline mode.
    cmp = benchmark_comparison_from_cache(
        "AAPL", benchmark="VOO", cache_dir=CACHE_DIR, portfolio_name="AAPL"
    )
    assert isinstance(cmp, BenchmarkComparison)
    assert cmp.benchmark_name == "VOO"
    assert len(cmp.index) > 0
    # Cumulative curves are finite numbers.
    assert np.isfinite(cmp.portfolio_twr)
    assert np.isfinite(cmp.benchmark_twr)
    assert cmp.excess_twr == pytest.approx(
        cmp.portfolio_twr - cmp.benchmark_twr, abs=1e-12
    )


@pytest.mark.skipif(not _has_cache("VOO"), reason="cached VOO OHLCV CSV required")
def test_smoke_performance_summary_from_cache():
    from assethold.projection import load_cached_returns

    r = load_cached_returns("VOO", cache_dir=CACHE_DIR)
    summ = performance_summary(r)
    assert "twr" in summ and "sharpe" in summ and "max_drawdown" in summ
    assert -1.0 <= summ["max_drawdown"] <= 0.0
    assert summ["cumulative"].iloc[-1] == pytest.approx(summ["twr"], abs=1e-9)


def test_spy_from_cache_raises_when_absent():
    # SPY is NOT cached -> must raise FileNotFoundError, never fetch.
    if _has_cache("SPY"):
        pytest.skip("SPY cache unexpectedly present")
    with pytest.raises(FileNotFoundError):
        benchmark_comparison_from_cache(
            "AAPL", benchmark="SPY", cache_dir=CACHE_DIR
        )
