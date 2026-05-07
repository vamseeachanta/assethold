# Issue #32 Plan — Complete skeletal modules (fixed_interest, multifamily, net_lease)

**Issue:** [vamseeachanta/assethold#32](https://github.com/vamseeachanta/assethold/issues/32)
**Tier:** T3 (multi-module feature work)
**Date:** 2026-05-05

## Context

Issue #32 calls three modules "skeletal":
1. **fixed_interest** (`src/assethold/modules/fixed_interest/fd.py`) — body says "Empty class with `pass` methods", but **direct inspection of the file shows it is already substantially implemented**: `FixedDeposit.calculate_interest()`, `compare_rates()`, `maturity_ladder()`, plus standalone `simple_interest()` / `compound_interest()` helpers, ~200 LOC, fully type-annotated and docstringed. This bullet's premise is stale.
2. **multifamily** (`src/assethold/modules/multifamily/`) — 901 LOC including `multifamily_analysis.py` (770 LOC); body says main analysis loop has a TODO.
3. **net_lease** (`src/assethold/modules/net_lease/`) — model exists at 293 LOC; minimal analysis layer.

Issue #36 has already been spun off from #32 to track multifamily sensitivity / waterfall extensions, so the multifamily-specific extensions are out of scope here. Body declares dependency on #29 (merge conflicts) and #31 (test coverage).

**Recommendation in plan:** narrow scope to (a) verify fixed_interest is complete and add tests, (b) close out the multifamily main-loop TODO if one still exists (else close that bullet), (c) flesh out net_lease analysis.

## Plan

1. **Audit fixed_interest** (`src/assethold/modules/fixed_interest/fd.py`):
   - File appears complete based on direct read. Verify there are no remaining `pass`/`#TODO` markers; close that bullet of #32.
   - Add `tests/modules/fixed_interest/test_fd.py` covering: simple interest math, compound interest math, `compare_rates` ranking, `maturity_ladder` rung values for known inputs.
2. **Multifamily main loop**:
   - Inspect `src/assethold/modules/multifamily/multifamily_analysis.py` — locate the documented TODO. If the TODO is for sensitivity (issue #36 scope), defer.
   - If a non-#36 TODO exists in the main loop, complete it: typically end-to-end pipeline glue (load YAML → build cash flow → compute waterfall → emit report). Add an integration test loading `tests/fixtures/multifamily_2.yaml`.
3. **Net lease analysis** (`src/assethold/modules/net_lease/analysis.py`):
   - Add `tenant_credit_score(tenant_data) -> CreditScore` (S&P/Moody's mapping or simplified A/B/C bucketing if rating data unavailable).
   - Add `lease_expiration_timeline(leases) -> DataFrame` with WALT (weighted-average lease term), expirations by year.
   - Add `nnn_vs_modified_gross_comparison(scenario_a, scenario_b) -> ComparisonReport` showing landlord-net-cash-flow under each lease structure.
   - Add `cap_rate_sensitivity(model, exit_caps=[0.05, 0.06, 0.07, 0.08]) -> DataFrame` re-running terminal-value calc across cap-rate band.
4. **Tests** at `tests/net_lease/test_analysis.py`: WALT computation against hand-calc, NNN-vs-MG cash-flow delta, cap-rate sensitivity returning monotonically-decreasing terminal values.
5. **Docstrings**: each module's `__init__.py` gets a one-paragraph purpose statement.

Smoke: `uv run pytest tests/modules/fixed_interest/ tests/net_lease/ tests/integration/test_multifamily_e2e.py -v`.

## Acceptance Criteria

- `src/assethold/modules/fixed_interest/fd.py` has no `pass`/`#TODO` markers (verified by grep); test suite covers all four public methods.
- Multifamily main loop runs end-to-end on bundled `multifamily_2.yaml` and returns a non-empty `MultifamilyResult` (or its TODO is documented as #36-scope and that bullet is removed from #32).
- Net lease analysis exposes the four functions above with type annotations + docstrings; tests cover the WALT and cap-rate-sensitivity outputs.
- Each module's `__init__.py` has a docstring describing purpose and the primary public entry point.
- Body's stale "skeleton only" claim about fixed_interest is corrected via an issue comment after audit.

## Open questions

- Tenant credit data source: free CSV mapping, paid API (Moody's/S&P), or user-supplied? Default user-supplied for v1; document the column schema.
- Should `nnn_vs_modified_gross_comparison` model recoveries (e.g., CAM reimbursement caps)? Default: simple net-vs-gross only; recoveries are a follow-up.
