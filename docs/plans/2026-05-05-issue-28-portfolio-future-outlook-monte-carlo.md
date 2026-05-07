# Issue #28 Plan — Portfolio future outlook (probabilistic Monte Carlo bands, 3mo-10yr)

**Issue:** [vamseeachanta/assethold#28](https://github.com/vamseeachanta/assethold/issues/28)
**Tier:** T3 (module-feature)
**Date:** 2026-05-05

## Context

Issue #28 specifies Monte Carlo projection of portfolio value over 3mo / 6mo / 1yr / 3yr / 5yr / 10yr horizons with P10/P50/P90 confidence bands, a fan-chart Plotly visualization with individual paths visible, milestone reference lines ($1.5M / $2M / $3M / $5M), and 10-year-specific modeling considerations: mean reversion via rolling 3-year sampling windows, optional DCA continuation, dividend reinvestment compounding, block bootstrap (6-month blocks) to preserve autocorrelation, and modeled position-evolution events (e.g., RIG exit). Output: terminal table + interactive Plotly chart + static PNG + caveats.

Depends on #21 Phase 1 (positions, complete) and #27 (returns infrastructure). Uses numpy random sampling — no new dependency beyond what Plotly + numpy already provide.

## Plan

1. **Return-distribution sampler** at `src/assethold/projection/sampler.py`:
   - `block_bootstrap(returns, block_months=6, n_paths=1000, horizon_months=120) -> np.ndarray` of shape `(n_paths, horizon_months)`.
   - `rolling_window_sampler(returns, window_years=3) -> Generator` yielding 3-year overlapping samples for regime-aware draws.
2. **Monte Carlo engine** at `src/assethold/projection/monte_carlo.py`:
   - `project_portfolio(initial_value, returns_history, horizon_months, n_paths=1000, dca_amount_monthly=0, dividend_yield_annual=0) -> ProjectionResult` returning the path matrix + percentile bands (P10/P25/P50/P75/P90).
   - DCA continuation: append `dca_amount` to each path's cash bucket monthly, then apply that month's drawn return.
   - Dividend reinvestment: add `dividend_yield_annual / 12 × portfolio_value` to each path each month before applying market return.
3. **Position-evolution rules** at `src/assethold/projection/events.py`:
   - `apply_position_evolution(paths, events: list[PositionEvent])` where events like `RIGExit(threshold_price=4.58, reallocation={'VOO': 0.55, 'BRKB': 0.45})` mutate per-path holdings when a draw crosses the threshold.
4. **Visualization** at `src/assethold/projection/fan_chart.py`:
   - `fan_chart(result, milestones=[1_500_000, 2_000_000, 3_000_000, 5_000_000]) -> Plotly Figure` with: 50 sampled translucent paths, P10-P90 fill, P25-P75 fill, P50 bold line, milestone horizontal dashed lines, current-value marker.
   - Static PNG export via `kaleido` (already a Plotly companion).
5. **Terminal table renderer** matching the issue body example: 6 horizons × 3 percentiles + variance-driver section ranking symbols by annual stdev contribution.
6. **CLI entry** at `src/assethold/projection/__main__.py`: `python -m assethold.projection --horizons 3m,6m,1y,3y,5y,10y --paths 1000 --output reports/projection.html`.
7. **Tests** at `tests/projection/test_sampler.py` (block bootstrap preserves block-level mean), `test_monte_carlo.py` (zero-volatility input → all paths converge to deterministic compound growth), `test_fan_chart.py` (figure renders without error, percentile bands present).

Smoke: `uv run pytest tests/projection/ -v` and `uv run python -m assethold.projection --horizon 1y --paths 100 --dry-run`.

## Acceptance Criteria

- Block-bootstrap output preserves the 6-month block-level mean within ±0.001 of the source distribution mean (statistical, ≥1000 paths).
- Zero-volatility synthetic returns (constant 0.005/month) → all 1000 paths produce identical final value matching `initial × 1.005^horizon`.
- Fan chart contains P10, P50, P90 traces and at least 50 individual path traces in the figure JSON.
- Terminal table prints all 6 horizons × 3 percentiles + variance-drivers section with at least 3 symbols ranked.
- DCA continuation: adding $1000/month over 12 months increases each path's final value by exactly the DCA-injection-without-returns floor amount in the zero-volatility check.
- Caveat block ("past performance does not predict...") appears in CLI output and HTML report.

## Open questions

- 10-year monthly vs daily resolution: body says monthly. Stick. Daily is computationally heavier and offers no precision gain at 10-year horizons.
- Should mean-reversion be rolling-window-only or include a regime-switching model (e.g., bull/bear states)? Default to rolling-window for v1; regime-switching is a follow-up.
