# Issue #31 Plan — Enforce quality gates (test coverage, mypy, loguru initialization)

**Issue:** [vamseeachanta/assethold#31](https://github.com/vamseeachanta/assethold/issues/31)
**Tier:** T2 (cross-cutting CI fix)
**Date:** 2026-05-05

## Context

Issue #31 documents three concrete gaps: (1) mypy in CI runs with `continue-on-error: true` so type errors degrade silently, (2) several modules have zero test coverage (`fundamentals.py`, `dividend_forecast.py`, `appliances/`, `net_lease/`, `multifamily/`, `options/covered_call.py`) — the 80% coverage gate in `pyproject.toml` is therefore not actually enforced, (3) `loguru` is imported but never centrally configured. The body lists known dependencies on #29 (merge conflicts) and #30 (module consolidation).

The repo-wide tier-1 baseline is ~360 ruff + ~351 mypy errors per the workspace-hub task brief. Flipping mypy to fail-the-build will require a substantial cleanup before it can land — that's a separate scope. This plan tightens the loop *without* breaking the build today: it adds the test scaffolding, ships loguru config, and stages mypy as warning-only-in-tier-2 with a path to fail-closed once #45 / #46 / surrounding cleanup land.

## Plan

1. **Add unit tests for high-value untested modules** (smoke-level, not exhaustive):
   - `tests/test_fundamentals.py` (file exists; verify it covers the public API; extend if not).
   - `tests/test_dividend_forecast.py` (extend with smoke tests of the public API per issue #17 plan).
   - `tests/modules/test_appliances_smoke.py` — instantiate `ApplianceInventory`, run lifecycle calculator on one fixture appliance.
   - `tests/modules/test_net_lease_smoke.py` — instantiate `NetLeaseModel`, run `analyze()` on a fixture lease.
   - `tests/modules/test_multifamily_smoke.py` — load `multifamily_2.yaml` fixture, run `multifamily_analysis.run()` end-to-end.
   - `tests/options/test_covered_call_smoke.py` — instantiate, run `compute_premium()` on one fixture.
2. **Loguru central config** at `src/assethold/logging_config.py` (file already exists — audit and complete):
   - Console sink with INFO default, format `{time:HH:mm:ss} | {level} | {name}:{function}:{line} | {message}`.
   - Optional rotating file sink at `data/logs/assethold.log`, 10 MB rotation, 7-day retention, when `ASSETHOLD_LOG_FILE=1`.
   - `init_logging(level=None)` callable invoked from each `__main__.py` entry.
3. **mypy gate progression** in `.github/workflows/python-tests.yml`:
   - Keep `continue-on-error: true` for now (do not break build with ~351 errors live).
   - Add a `mypy --strict src/assethold/portfolio src/assethold/utils` blocking job that gates *only the cleaned subset* — establishes the pattern, prevents regressions in fixed modules.
   - File a follow-up issue tracking each remaining package's strict-mypy onboarding.
4. **Coverage threshold reality check**: run `uv run pytest --cov=src/assethold --cov-report=term-missing` and record the baseline. If <80%, lower the `pyproject.toml` `--cov-fail-under` to the floor + 5 pts, with a docstring TODO targeting 80% over time. Avoid silently-failing gates.
5. **Tests** for `logging_config.init_logging`: assert handler count, level, format string.

Smoke: `uv run pytest tests/ --cov=src/assethold --cov-report=term-missing` and `uv run mypy src/assethold/portfolio src/assethold/utils --strict`.

## Acceptance Criteria

- All listed modules have at least one smoke test that instantiates the primary class and exercises one public method.
- `pyproject.toml::tool.coverage` `--cov-fail-under` reflects a real, enforceable threshold (no silent-pass gate).
- `python-tests.yml` contains a blocking mypy job for `portfolio/` and `utils/` (at minimum) with `continue-on-error: false`.
- `init_logging()` is called from each `__main__.py` entry; verified by grep + integration test asserting log output format.
- Follow-up issue filed listing each module pending strict-mypy onboarding.
- Existing test suite continues to pass.

## Open questions

- Should we revisit the 80% target now that the codebase is bigger? Default: keep 80% as the long-term target, gate at the current floor +5pp, document the ramp.
- File-sink rotation: 7 days vs 30 days? Default 7 — sized for personal-use logs.

## Notes

- Body lists `#29` and `#30` as dependencies; this plan does not block on either since the listed test additions are independent of merge conflicts and module consolidation. If those land first, integrate; if not, ship the smoke tests now.
- Items #45 (broken `.agent-os/` Python files) and #46 (duplicate `path_utils.py`) are tributary to this plan's mypy/lint progression.
