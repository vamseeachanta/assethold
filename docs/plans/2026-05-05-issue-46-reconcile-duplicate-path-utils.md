# Issue #46 Plan — Reconcile duplicate non-package reporting path_utils helper

**Issue:** [vamseeachanta/assethold#46](https://github.com/vamseeachanta/assethold/issues/46)
**Tier:** T1 (single-site cleanup)
**Date:** 2026-05-05

## Context

Issue #46 documents a duplicate-file drift risk:
- Root-level: `modules/reporting/utils/path_utils.py` (4228 bytes, confirmed present via `ls`).
- Package: `src/assethold/modules/reporting/utils/path_utils.py` (the installable copy).

The package CI hardening tranche will likely narrow lint/type gates to maintained package surfaces, which means the root-level duplicate would stop being checked. Body asks: determine whether the root-level file is dead, generated, or still consumed; either delete it, merge/fix it, or document a separate maintenance boundary; ensure future CI/lint scope does not hide real duplicate-code drift.

This is mechanical: diff the two files, confirm no live consumer of the root-level copy, then delete it (or merge if they have actually drifted in meaningful ways).

## Plan

1. **Diff the two files**:
   - `diff modules/reporting/utils/path_utils.py src/assethold/modules/reporting/utils/path_utils.py` — capture exact divergence.
   - If identical: trivial deletion of the root-level copy.
   - If divergent: identify which copy has the drift (likely the root-level is older and frozen; the package copy is the live one). Merge any unique-to-root content into the package copy if it has value.
2. **Find consumers of the root-level copy**:
   - `git grep -n "from modules.reporting" --include='*.py'` — should match nothing if root-level is dead.
   - `git grep -n "modules/reporting/utils/path_utils" --include='*.py'` — catches relative-path imports.
   - `git grep -n "modules/reporting/utils/path_utils"` (no `--include`) — catches docs and configs that may reference it.
3. **Delete the root-level duplicate**:
   - `git rm modules/reporting/utils/path_utils.py`.
   - If the root-level `modules/` tree contains other dead siblings, evaluate them in this same commit; otherwise leave for a separate cleanup issue.
4. **Verify no breakage**:
   - `uv run pytest tests/ -x` — full test suite must pass.
   - `uv run python -c "from assethold.modules.reporting.utils.path_utils import *"` — package import still works.
5. **Document the new boundary** (optional):
   - Add a sentence to `docs/architecture.md` or `.agent-os/README.md` (per #45 plan) noting that root-level `modules/` is not the canonical path; the canonical surface is `src/assethold/modules/`.
6. **CI safeguard**: add a check (one-liner shell) to a non-blocking CI job that fails if a file under root-level `modules/` shadows a file under `src/assethold/modules/`. Prevents regression.

Smoke: `diff modules/reporting/utils/path_utils.py src/assethold/modules/reporting/utils/path_utils.py` (before deletion); `uv run pytest tests/ -x` (after deletion).

## Acceptance Criteria

- Root-level `modules/reporting/utils/path_utils.py` is deleted (or merged into the package copy with rationale recorded in commit message).
- No `git grep` match for relative imports of the root-level path remains.
- Full test suite passes (`uv run pytest tests/`).
- Package import `from assethold.modules.reporting.utils.path_utils import *` still works.
- Root-level vs package-level shadow-detection guard added to CI (non-blocking ok), or the rationale for not adding it is recorded.

## Open questions

- Are there other duplicate root-level vs package-level files? Quick audit: `for f in $(find modules -name '*.py'); do test -f src/assethold/$f && echo "shadow: $f"; done`. If multiple, expand scope or file follow-up.
- The root-level `modules/` tree may exist because of historical packaging choices. Confirm with the user that deletion is safe.
