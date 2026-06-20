# Issue #46 Reconciliation Memo — duplicate non-package reporting `path_utils` helper

**Date:** 2026-06-19
**Issue:** [vamseeachanta/assethold#46](https://github.com/vamseeachanta/assethold/issues/46)
**Type:** Dead-code reconciliation — evidence-based, **advisory only** (no code deleted)
**Companion plan:** `docs/plans/2026-05-05-issue-46-reconcile-duplicate-path-utils.md`
**Method:** WIDE repo-wide grep (incl. tests/config/docs/CI), dynamic-dispatch checks, packaging-config inspection

---

## 1. Scope

Issue #46 names exactly **one** dead/duplicate-code candidate (it is not a multi-candidate
sweep): the root-level, non-package copy of the reporting path helper.

| | Path | Bytes |
|---|---|---|
| Candidate (root, non-package) | `modules/reporting/utils/path_utils.py` | 4228 |
| Canonical (installable package) | `src/assethold/modules/reporting/utils/path_utils.py` | 4081 |

Both files define the same public surface: `get_project_root`, `get_data_path`,
`get_report_path`, `ensure_report_dir`, `relative_path_from_report`.
Because the **function names are shared**, a name-only grep cannot distinguish the two copies —
references were classified strictly by **import path / file path**, not function name.

## 2. Evidence (wide grep)

Reconciliation table — candidate vs. every whole-repo reference found:

| Candidate | References found (file:line) | Verdict | Rationale |
|---|---|---|---|
| `modules/reporting/utils/path_utils.py` (root, non-package copy) | **No consumer of the root copy.** All concrete references point to the *package* copy: `tests/unit/modules/reporting/utils/test_path_utils.py:7` (`from assethold.modules.reporting.utils.path_utils import ...`); `.github/workflows/python-tests.yml:108` (mypy on `src/assethold/...`); `scripts/ci/verify_python_tests_workflow.py:18` (`src/assethold/...`); `tests/unit/scripts/test_verify_python_tests_workflow.py:50` (`src/assethold/...`). The bare path `modules/reporting/utils/path_utils` appears **only** in this issue's own plan doc `docs/plans/2026-05-05-issue-46-...md`. | **SAFE-TO-REMOVE** *(advisory; not deleted in this task)* | See §3 — zero live consumers, not packaged, not importable, no dynamic-dispatch risk, and the copy is additionally **buggy**. |

### Grep commands run (whole repo, incl. tests/config/docs)

- `grep -rIn "modules\.reporting" . --include='*.py'` (excluding `src/assethold`) → only the **test**, which imports `from assethold.modules.reporting...` (the package, not the root copy).
- `grep -rIn "modules/reporting/utils/path_utils" .` (no `--include`, all file types) → CI workflow, CI verifier script, its test, and this issue's plan doc. Every non-doc hit names `src/assethold/...`.
- `grep -rInE "(from|import)[[:space:]]+modules\b" . --include='*.py'` → only `.agent-os/commands/organize_structure.py:402`, an f-string literal `"# Import from modules"` (generated-code text, **not** an import of this module).
- `grep -rInE "__all__|getattr|importlib|__import__|import_module" . --include='*.py'` filtered to `path_util|reporting` → **none**. No dynamic import / string-dispatch / `__all__` re-export path reaches the root copy.

## 3. Why the root copy is non-live (corroborating facts)

1. **Not packaged.** `pyproject.toml:120-122` → `[tool.setuptools.packages.find]` with `where = ["src"]`, `include = ["assethold*"]`. The root-level `modules/` tree is outside the packaged surface and is never installed.
2. **Not importable as a package.** The root-level `modules/` tree has **no `__init__.py`** (`find modules -name __init__.py` → empty). `import modules.reporting...` cannot resolve.
3. **No `sys.path` exposure.** No `sys.path.insert/append` in the repo adds the repo root in a way that would surface `modules.reporting.*` as an import (the existing `sys.path` inserts target `.agent-os/commands` and `scripts/` tooling, unrelated).
4. **Live copy is the package copy.** The single test and all CI/type-check references target `assethold.modules.reporting.utils.path_utils` (the `src/` copy).
5. **The root copy is buggy** (further evidence it is frozen/abandoned, not maintained): its `relative_path_from_report` `except` branch calls `os.path.commonprefix(...)` but the file **omits `import os`** → would raise `NameError` if that branch ran. It also misuses `commonprefix` on path `.parts` tuples. The package copy fixes both: it `import os` and uses the correct `os.path.commonpath([str(...), str(...)])`. (`modules/...path_utils.py:125` vs package `:9` import and `:` commonpath.)

## 4. Verdict summary

| Verdict | Count | Candidates |
|---|---|---|
| KEEP | 0 | — |
| SAFE-TO-REMOVE | 1 | `modules/reporting/utils/path_utils.py` (root non-package copy) |
| NEEDS-HUMAN | 0 | — |

**Confidence:** High that the root copy has zero live consumers and is safe to delete. The
SAFE-TO-REMOVE call rests on: zero whole-repo import references, not-packaged + no `__init__.py`
(unimportable), no dynamic-dispatch/`__all__`/`importlib` path, and a latent `NameError` bug
showing the copy is unmaintained. This memo is **advisory** — per task rules no code is deleted.

## 5. Recommendation (for the implementer / human)

1. Delete `modules/reporting/utils/path_utils.py` (the issue's plan already proposes `git rm`).
2. Sibling files under the root `modules/` tree (`automation/*.sh`, `config/*.json`,
   `reporting/templates/plotly_report_template.py`) were **out of scope** for #46 and were **not**
   reconciled here — they need their own audit before any broader root-`modules/` cleanup.
   Treat that as NEEDS-HUMAN / separate issue, not part of this candidate.
3. Add the shadow-detection CI guard from the plan (§Plan step 6) to prevent future
   package-vs-root duplicate drift once CI lint/type scope narrows to `src/`.

## 6. Spot-check (memo self-verification)

- `pyproject.toml:120-122` → `where = ["src"]`, `include = ["assethold*"]` — verified.
- `tests/unit/modules/reporting/utils/test_path_utils.py:7` imports `from assethold.modules.reporting.utils.path_utils` (package) — verified.
- Root copy line 125 uses `os.path.commonprefix` with no `import os` in the file — verified
  (`grep -n "import os\|commonprefix" modules/reporting/utils/path_utils.py` shows the call but no import).
