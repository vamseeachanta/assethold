# Issue #11 Plan — Repo guidelines

**Issue:** [vamseeachanta/assethold#11](https://github.com/vamseeachanta/assethold/issues/11)
**Tier:** T1 (doc + small config)
**Date:** 2026-05-05

## Context

Issue #11 is a five-item bullet checklist of repo conventions: tests outside `src/` (already done), git-bash migration, VS Code launch configs, "ai tools", and "interactive charts". Four of the five remaining items are one-line phrases without acceptance criteria. The first item is already complete (`tests/` is sibling to `src/`, verified via `git ls-files`).

**Recommendation:** close as too broad. Each remaining bullet either belongs in a separate concrete issue ("add VS Code `launch.json` for the daily-strategy CLI") or duplicates work already happening elsewhere ("ai tools" = the agent harness in `.agent-os/`, which has its own tracking). The interactive-charts item overlaps with #5, #21, #28 which all already specify Plotly outputs.

## Plan

If user keeps the issue open:

1. **Convert each remaining bullet into its own narrow issue or close as duplicate.**
   - `Migrate to gitbash from powershell and command prompt` → file separate issue if Windows tooling work is genuinely needed; otherwise close (Linux-first repo, contributors choose their shell).
   - `vs code launch` → file narrow issue: "Add `.vscode/launch.json` configurations for daily_strategy, watchlist_runner, multifamily_analysis CLIs".
   - `ai tools` → close as duplicate; covered by `.agent-os/` infrastructure already in repo.
   - `interactive charts` → close as duplicate; covered by Plotly work in #21 / #28 / #5.

2. **No source code changes.** Issue conversion + close is the work product.

3. **Optional:** add a one-paragraph "Conventions" section to `docs/index.md` recording the durable rule that survived ("tests live outside `src/`") so future contributors find it.

Smoke: `mkdocs build --strict` if docs are touched.

## Acceptance Criteria

- Either #11 is closed with comments pointing at the five replacement issues / duplicates, OR a single follow-up issue is filed with concrete acceptance criteria for each remaining bullet.
- No half-completed work left in #11 — the running checklist pattern actively decays without conversion.
- If `docs/index.md` is updated, mkdocs build passes.
- No source code changes.

## Recommendation

**Close as too broad** after splitting into focused follow-ups (or marking as duplicates of existing work). Running-checklist issues are a known anti-pattern in this repo (see also #8, #12).
