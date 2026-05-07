# Issue #36 Plan — Multifamily sensitivity and stress-test scenarios (TODOs a-e)

**Issue:** [vamseeachanta/assethold#36](https://github.com/vamseeachanta/assethold/issues/36)
**Tier:** T3 (module extension, multi-item)
**Date:** 2026-05-05

## Context

Issue #36 spins off five extensions to the (already-working) multifamily module from issue #32:
- (a) LP incentive brackets — tiered waterfall logic beyond single preferred return.
- (b) Expense breakdown — per-unit-type, per-category growth rates beyond the 10-category aggregate sum.
- (c) Market research automation — pull comparable cap rates / rent growth from a data source (open question on source).
- (d) Class A / Class B partnership shares — differentiated preferred returns and distribution priorities.
- (e) Financial stress tests — run the sensitivity arrays already declared in `multifamily_2.yaml:149-154` (operating expenses ±20%, renovation costs 0/50/100, NOI growth 0/50, exit cap rate ±20%) and emit stressed IRR / EM / DSCR matrix.

Body recommends starting with (e) since the YAML scaffolding already exists — only the consumer is missing. Existing 30-test coverage in `tests/unit/test_multifamily.py` provides regression safety. Items (a) and (d) require waterfall design work; (c) needs a product-side data-source decision.

Plan implements (e) and (b) — the lowest-risk highest-value subset. Items (a) and (d) get research+design follow-up issues. Item (c) needs user input before any code lands.

## Plan

1. **Item (e) — Stress test runner** at `src/assethold/modules/multifamily/stress_tests.py`:
   - `run_stress_grid(base_config, sensitivity_arrays) -> StressMatrix` — for each combination of perturbation values declared in the YAML's sensitivity arrays, re-run the analysis pipeline and capture IRR / equity multiple / DSCR.
   - Output: `pd.DataFrame` indexed by perturbation tuple, columns = (irr, em, dscr); plus a heatmap renderer.
   - Wire YAML loader to populate the sensitivity arrays from `multifamily_2.yaml:149-154` automatically.
2. **Item (b) — Per-category expense breakdown** in `src/assethold/modules/multifamily/multifamily_analysis.py`:
   - Replace single `expense_growth_rate` with `expense_growth_rates: dict[category, rate]` accepting all 10 categories independently. Keep backwards-compat: a single scalar in YAML still applies to all categories.
   - Add per-unit-type expense allocation if `unit_types` block is present in config.
3. **CLI extension**: `python -m assethold.modules.multifamily --stress` runs the stress grid and emits `reports/multifamily_stress_<timestamp>.html` with the matrix + heatmap.
4. **Tests** at `tests/unit/test_multifamily_stress.py`:
   - Stress grid for a 3×3 perturbation produces 9 result rows.
   - Identity perturbation (all 0% changes) reproduces the base-case result within rounding.
   - Per-category expense growth: setting only `repairs.growth_rate=0.05` while keeping others at 0 changes only the repairs line in the cash-flow output.
5. **Follow-up issues** filed for (a), (c), (d): each cites #36 and contains the design questions identified in the body.

Smoke: `uv run pytest tests/unit/test_multifamily_stress.py tests/unit/test_multifamily.py -v` and `uv run python -m assethold.modules.multifamily --stress --config tests/fixtures/multifamily_2.yaml --dry-run`.

## Acceptance Criteria

- Item (e): stress matrix populated for the full Cartesian grid of `multifamily_2.yaml:149-154` perturbations; identity case matches base-case IRR within 0.001%.
- Item (b): per-category expense growth dict supported; backwards-compat scalar still works (regression test).
- Heatmap output in HTML report visually distinguishes IRR bands (green/yellow/red).
- 3 follow-up issues filed for (a), (c), (d) with cited body content.
- Existing 30 multifamily tests still pass.

## Open questions

- For (e), should DSCR be computed at the worst-case year of the hold period or at year-1? Body doesn't say. Default: minimum DSCR across hold period (most conservative).
- Heatmap library: matplotlib (already a dep) vs Plotly (richer interactivity)? Default Plotly for HTML output, matplotlib PNG fallback.
