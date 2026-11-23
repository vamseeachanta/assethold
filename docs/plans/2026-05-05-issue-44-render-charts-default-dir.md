# Issue #44 Plan — Decide --render-charts default dir (fail-loud vs ./dashboard-charts/)

**Issue:** [vamseeachanta/assethold#44](https://github.com/vamseeachanta/assethold/issues/44)
**Tier:** T1 (single-site CLI ergonomics)
**Date:** 2026-05-05

## Context

Issue #44 is a deliberate design-decision tracker from #39's open questions. Current behavior: `--render-charts` requires explicit `--charts-dir PATH`; CLI exits 2 with stderr message if not. Two options on the table:
- **Option A (current, fail-loud):** explicit `--charts-dir` required. No surprise file writes.
- **Option B (default dir):** `--render-charts` without `--charts-dir` writes to `./dashboard-charts/` or `data/dashboards/<date>/`. Friendlier; risk of surprise file creation in CWD.

Body asks for a one-paragraph decision note recorded in `docs/reports/realtime-phase1-design.md` (or new note under `docs/reports/`), implementation matching the decision, and tests confirming the chosen behavior. Test `test_cli_render_charts_without_dir_exits_2` in scope: either confirm exit-2 still fires, or replace with default-dir test.

**Recommendation:** Option B with default `data/dashboards/<YYYY-MM-DD>/`. Rationale: workspace-hub convention (rule `.claude/rules/coding-style.md::Path Handling`) discourages CWD-relative paths; using `data/dashboards/<date>/` keeps the file-write inside repo data conventions and uses date partitioning to avoid silent overwrite of prior runs. This is friendlier than fail-loud while avoiding the "files appear in `pwd`" surprise that fueled Option A's fail-loud preference.

## Plan

1. **Decision note** at `docs/reports/render-charts-default-dir.md` (new):
   - One paragraph stating the decision (Option B with `data/dashboards/<date>/` default).
   - Rationale: workspace-hub path-handling rule, date partitioning prevents overwrite, repo `data/` is gitignored.
   - User-override path: explicit `--charts-dir` always wins; `--no-default-charts-dir` reverts to fail-loud Option A behavior for users who prefer it.
2. **Implementation** in `src/assethold/signals/watchlist_runner.py::main()`:
   - When `--render-charts` is passed without `--charts-dir`, default to `Path("data/dashboards") / date.today().isoformat()`.
   - Create the directory with `mkdir(parents=True, exist_ok=True)`.
   - Update `--render-charts` help text to document the default path.
   - Add `--no-default-charts-dir` flag for users who want the old fail-loud behavior.
3. **Update tests** at `tests/unit/signals/test_watchlist_runner.py`:
   - Replace `test_cli_render_charts_without_dir_exits_2` with `test_cli_render_charts_uses_default_dir` asserting `data/dashboards/<today>/` is created and used.
   - Add `test_cli_render_charts_no_default_exits_2` verifying the opt-out flag preserves Option A behavior.
   - Continue stubbing `dashboard.save_chart` (no real chart files in unit tests, per body).
4. **Help text + docs**:
   - Update `--render-charts` and `--charts-dir` help strings.
   - Add a one-line note in `docs/index.md` or `docs/reports/realtime-phase1-design.md` cross-referencing the new design note.

Smoke: `uv run pytest tests/unit/signals/test_watchlist_runner.py -v` and `uv run python -m assethold.signals.watchlist_runner --render-charts --dry-run` (verify dir is reported in dry-run output).

## Acceptance Criteria

- Decision recorded as a one-paragraph note at `docs/reports/render-charts-default-dir.md` referencing this issue.
- `--render-charts` without `--charts-dir` writes to `data/dashboards/<YYYY-MM-DD>/`; directory auto-created.
- `--render-charts --no-default-charts-dir` (without `--charts-dir`) exits 2 with stderr message (Option A preserved as opt-in).
- Help text mentions the default path.
- Tests confirm both code paths; `dashboard.save_chart` continues to be stubbed.
- No real chart files written in unit tests.

## Open questions

- Option A vs B is the core decision. Plan recommends Option B with date-partitioned default; user can override the recommendation in plan-review.
- Default dir name: `data/dashboards/` or `dashboard-charts/`? Plan recommends `data/dashboards/` to match repo `data/` gitignore convention.
