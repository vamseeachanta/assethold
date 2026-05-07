# Issue #27 Plan — Portfolio performance benchmark vs SPY

**Issue:** [vamseeachanta/assethold#27](https://github.com/vamseeachanta/assethold/issues/27)
**Tier:** T2 (focused feature)
**Date:** 2026-05-05

## Context

Issue #27 wants time-weighted return (TWR) calculation accounting for cash flows, monthly/annual portfolio-vs-SPY comparison, Sharpe ratio + max drawdown, cumulative-return chart, and factor attribution (allocation vs stock-selection). Depends on #21 Phase 1 (transaction history, complete) and #21 Phase 4 (returns infrastructure scoped in #21 plan).

This is an extension of `src/assethold/risk_metrics.py` (which already exists) plus the performance module scoped in #21. Factor attribution overlaps with #18 (Fama-French) — use #18's regression module if available; otherwise implement a simpler 2-factor decomposition (allocation vs selection, the Brinson model).

## Plan

1. **TWR engine** at `src/assethold/portfolio/performance.py`:
   - `time_weighted_return(values: pd.Series, cash_flows: pd.Series) -> pd.Series` using daily sub-period chaining: `r_t = (V_t - CF_t) / V_{t-1} - 1`, cumulative product.
   - `total_twr(values, cash_flows, start, end) -> float`.
2. **Benchmark comparator** at `src/assethold/portfolio/benchmark.py`:
   - `fetch_benchmark_returns('SPY', start, end)` via cached yfinance.
   - `compare(portfolio_twr, benchmark_returns) -> ComparisonReport` with monthly + annual buckets, alpha, beta (regression slope), tracking error.
3. **Risk metrics extension** at `src/assethold/risk_metrics.py`:
   - `sharpe_ratio(returns, rf=0.045) -> float` (configurable risk-free rate).
   - `max_drawdown(values) -> tuple[float, date, date]` returning depth + peak/trough dates.
4. **Brinson attribution** at `src/assethold/portfolio/attribution.py`:
   - `brinson_decomposition(weights, returns, benchmark_weights, benchmark_returns) -> AttributionReport` with allocation effect, selection effect, interaction effect per sector/symbol.
   - If `assethold.factor_models` (#18) is present, delegate to multi-factor attribution instead.
5. **Visualization** at `src/assethold/portfolio/charts.py`:
   - `cumulative_return_chart(portfolio_twr, benchmark_returns) -> Plotly Figure` with portfolio + SPY lines, drawdown shaded region, key-event markers.
6. **Tests** at `tests/portfolio/test_performance.py`, `test_benchmark.py`, `test_attribution.py` with synthetic returns where the expected TWR / Sharpe / max-DD are known by hand.

Smoke: `uv run pytest tests/portfolio/test_performance.py tests/portfolio/test_benchmark.py -v` and `uv run python -m assethold.portfolio.daily_report --include-benchmark --dry-run`.

## Acceptance Criteria

- TWR computed for a buy-and-hold portfolio with one dividend re-injection matches the hand-computed expected value within 0.01%.
- SPY benchmark fetcher returns daily returns covering the portfolio's date range; mismatched length raises a clear error.
- Sharpe ratio for a returns series with mean 0.10/yr, stdev 0.15/yr, rf=0.045 yields ≈ 0.367 (within 0.01).
- Max drawdown for a known peak-trough path (100 → 80 → 120) returns 0.20 with correct dates.
- Brinson attribution output sums to total active return within rounding error.
- Cumulative-return chart renders for a 252-day fixture without errors; saves to PNG and HTML.

## Open questions

- TWR vs MWR (money-weighted): body says TWR; stick with TWR for benchmark comparison (industry standard). MWR/IRR is a follow-up if user wants personal-rate-of-return view.
- Risk-free rate source: hardcoded config or fetched (e.g., 13-week T-bill via FRED)? Default to config knob; FRED integration is a follow-up.
