# Issue #17 Plan — Dividend yield forecasting (Gordon, H-model, multi-stage DDM)

**Issue:** [vamseeachanta/assethold#17](https://github.com/vamseeachanta/assethold/issues/17)
**Tier:** T3 (module-feature)
**Date:** 2026-05-05

## Context

Issue #17 (WRK-1198) requests dividend yield projection using three growth models: Gordon constant-growth, H-model (linearly fading growth from initial to terminal), and multi-stage DDM (explicit stage-by-stage growth then terminal). The repo already has `src/assethold/dividend_forecast.py` (file exists, 358 LOC region per #31) and tests at `tests/test_dividend_forecast.py`. Need to confirm whether the existing module already implements these models or only stubs them.

The issue body uses the WRK-template skeleton (Mission only, Final Plan = "Not yet available"). Acceptance criteria are inferred from the Mission line: implement all three DDMs and integrate into portfolio income forecasting (issue #7's dividend cash-flow consumer is a natural caller).

## Plan

1. **Audit existing `src/assethold/dividend_forecast.py`**: read current public API, confirm which models exist. If Gordon is already implemented, skip step 2; if not, implement.
2. **Implement missing growth models**:
   - `gordon_growth(d0, growth_rate, discount_rate) -> float` — terminal value via `D1 / (r - g)` with `r > g` precondition check.
   - `h_model(d0, initial_growth, terminal_growth, fade_years, discount_rate) -> float` — linear fade from `initial_growth` to `terminal_growth` over `fade_years`, then Gordon thereafter.
   - `multi_stage_ddm(d0, stages: list[Stage], discount_rate) -> float` where `Stage = (years, growth_rate)`; final stage uses Gordon for terminal value.
3. **Forecasted-yield helper**: `project_yield(symbol, model, params, horizon_years) -> pd.Series` returning year-by-year dividend per share + projected yield-on-cost given current price.
4. **Wire to portfolio**: extend `src/assethold/portfolio/dividends.py` (or create) so `portfolio.value_simulator` (issue #7) can consume forecasted dividend cash flows for forward-looking simulations.
5. **Tests** at `tests/test_dividend_forecast.py`: per-model parametrize tests with hand-computed expected values (e.g., Gordon with d0=2, g=0.05, r=0.10 → present value = 42.0); H-model boundary cases (initial=terminal collapses to Gordon); multi-stage with single stage equals Gordon.

Smoke: `uv run pytest tests/test_dividend_forecast.py -v` and `uv run python -c "from assethold.dividend_forecast import gordon_growth; print(gordon_growth(2.0, 0.05, 0.10))"`.

## Acceptance Criteria

- All three models (`gordon_growth`, `h_model`, `multi_stage_ddm`) live in `src/assethold/dividend_forecast.py` with type-annotated signatures.
- Hand-computed-expectation tests pass for each model (at least 2 cases per model including a degenerate-collapses-to-Gordon check).
- `r <= g` raises `ValueError` in Gordon and the terminal stage of H-model / multi-stage; tested.
- `project_yield()` produces a year-indexed `pd.Series` covering `horizon_years` periods.
- Existing dividend_forecast tests still pass; no regression.

## Open questions

- Should models accept absolute dollar dividends (D0) or yield-on-cost percentage? Default to absolute D0 — yield is a derived quantity.
- Discount rate source: hardcoded user input, CAPM-derived, or pulled from `risk_metrics.py`? Default to user input for v1; CAPM integration is a follow-up.
