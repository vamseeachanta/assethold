# Issue #18 Plan — Fama-French factor model (3-factor + 5-factor)

**Issue:** [vamseeachanta/assethold#18](https://github.com/vamseeachanta/assethold/issues/18)
**Tier:** T3 (module-feature)
**Date:** 2026-05-05

## Context

Issue #18 (WRK-1199) requests Fama-French 3-factor (Mkt-RF, SMB, HML) and 5-factor (adds RMW, CMA) regression for alpha decomposition and risk attribution. Body uses the WRK template skeleton with no concrete acceptance criteria. The repo has `src/assethold/risk_metrics.py` for general risk math and `tests/test_risk_metrics.py` for coverage; this is a natural sibling module.

Factor data is published by Kenneth French's data library (https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) as monthly CSVs. The standard Python approach is `pandas_datareader.famafrench` or direct CSV download. No live API key required.

## Plan

1. **Create `src/assethold/factor_models/`** package with:
   - `data.py`: download + cache Fama-French factor CSVs (3-factor and 5-factor monthly) under `data/cache/famafrench/`. Use `pandas_datareader.famafrench` if available; fall back to direct CSV pull from the public URL.
   - `regression.py`: `fit_3_factor(returns: pd.Series, factors: pd.DataFrame) -> FactorFit` and `fit_5_factor(...)` returning alpha, betas, t-stats, R², residual std using OLS (`statsmodels` is already a transitive dep via pandas; if not, add to `pyproject.toml`).
   - `attribution.py`: decompose total return into factor contributions (`return = alpha + beta_mkt * Mkt-RF + beta_smb * SMB + ...`).
2. **Portfolio integration**: extend `src/assethold/portfolio/reports.py` to optionally include a "Factor Attribution" section showing alpha and factor exposures for the aggregate portfolio return series.
3. **CLI entry**: `python -m assethold.factor_models --returns data/portfolio/returns.csv --model 5-factor --output reports/factor_attribution.html`.
4. **Tests** at `tests/factor_models/`: regression-result test against a known textbook example (e.g., Fama-French 1993 SMB beta ≈ ... for a published example portfolio); R² sanity check (factor-tracking ETF should produce R² > 0.95 on the corresponding factors).
5. **Docstrings + reference**: cite the data source URL in module docstring; add a one-paragraph explainer to `docs/index.md` linking the new module.

Smoke: `uv run pytest tests/factor_models/ -v` and `uv run python -m assethold.factor_models --returns tests/fixtures/sample_returns.csv --model 3-factor --dry-run`.

## Acceptance Criteria

- Fama-French monthly factors download to `data/cache/famafrench/` and a re-run within 30 days serves from cache.
- `fit_3_factor()` and `fit_5_factor()` return alpha + per-factor beta + t-stat + R² for a 60-month synthetic returns series.
- An equally-weighted SPY-only fixture yields a market-beta close to 1.0 (within ±0.05) and SMB/HML betas near 0 (within ±0.15).
- Factor data ingestion handles the common CSV header artifacts (multi-row header, "Annual" trailing block) without crashing.
- `tests/factor_models/` reports passing.

## Open questions

- 5-factor data starts July 1963; some early portfolio histories will not have full factor coverage. Default behavior: warn + return result limited to the overlap window. Surface as `coverage_window` in the result object.
- Use `statsmodels.OLS` (richer stats output, already common dep) or `scipy.stats.linregress` (lighter)? Default to `statsmodels` for the t-stats and confidence intervals it provides for free.
