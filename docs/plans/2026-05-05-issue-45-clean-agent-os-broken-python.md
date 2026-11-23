# Issue #45 Plan — Clean or retire auxiliary agent-os Python files excluded from package lint gate

**Issue:** [vamseeachanta/assethold#45](https://github.com/vamseeachanta/assethold/issues/45)
**Tier:** T1 (single-site cleanup)
**Date:** 2026-05-05

## Context

Issue #45 names two concrete broken Python files that will be silently hidden once the strict flake8 gate narrows to `src/assethold/`:
- `.agent-os/modules/prompt_enhancement.py` — unterminated triple-quoted string (`E999`)
- `scripts/agent-os/create-spec-enhanced.py` — multiple undefined names (`F821`)

Body asks: decide whether to repair, delete, or move out of Python-linted surfaces; restore parseability if kept; document the maintenance boundary. Files are not in the installable package, so they don't block the immediate post-smoke CI tranche — but leaving broken Python in-tree is bad hygiene.

Both files appear to be agent-os scaffolding artifacts. Per workspace-hub memory, this repo's `.agent-os/` directory is shared template-style scaffolding; the broken files may be vestigial templates that were never repaired.

## Plan

1. **Triage each file**:
   - Read `.agent-os/modules/prompt_enhancement.py` and `scripts/agent-os/create-spec-enhanced.py`.
   - For each, determine: is this referenced anywhere in the repo (`git grep -l "prompt_enhancement\|create-spec-enhanced"`)? If yes, repair. If no, delete.
2. **Repair path** (if file is referenced):
   - For `prompt_enhancement.py`: locate the unterminated triple-quote and close it; ensure the file imports cleanly (`uv run python -c "import importlib.util; spec = importlib.util.spec_from_file_location('m', '.agent-os/modules/prompt_enhancement.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)"`).
   - For `create-spec-enhanced.py`: identify each `F821` undefined name; either add the missing import, or replace with the intended symbol.
3. **Delete path** (if file is unreferenced):
   - `git rm` the file.
   - Confirm no test or workflow references it via `git grep`.
4. **Document maintenance boundary**:
   - If files remain in `.agent-os/`, add a one-paragraph note to `.agent-os/README.md` (or create) saying: "Files under `.agent-os/` are scaffolding for agent harness experiments. They are NOT part of the `src/assethold` package and may be excluded from package CI gates. Maintainers MUST keep them parseable; broken Python here is hygiene debt."
   - If files are deleted, mention the deletion in the commit message and reference this issue.
5. **CI update** (optional): add a separate, non-blocking `flake8 .agent-os/ scripts/` job that catches the regression class without gating package-CI.

Smoke: `uv run python -m py_compile .agent-os/modules/prompt_enhancement.py scripts/agent-os/create-spec-enhanced.py` (or, if deleted, `ls` confirms absence) and `uv run flake8 .agent-os/ scripts/agent-os/ --select=E999,F821`.

## Acceptance Criteria

- `uv run python -m py_compile` succeeds on both files (if kept) OR both files are absent from the working tree (if deleted).
- `flake8 --select=E999,F821 .agent-os/ scripts/agent-os/` returns zero matches.
- A maintenance-boundary note exists explaining `.agent-os/` lint scope (either in `.agent-os/README.md` or in this issue's commit message).
- No regression in `src/assethold/` package CI.
- Decision (repair vs delete) recorded in commit message with rationale.

## Open questions

- Are these files used by any external workspace-hub agent harness? Likely no — body's tone treats them as in-tree-only debt. Confirm via `git grep` before deletion.
- If repair path is chosen, should the maintenance boundary be enforced via a non-blocking `flake8` CI job? Recommend yes — without enforcement, this debt re-accumulates.
