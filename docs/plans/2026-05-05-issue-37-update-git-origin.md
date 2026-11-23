# Issue #37 Plan — chore: update git origin to vamseeachanta/assethold canonical URL

**Issue:** [vamseeachanta/assethold#37](https://github.com/vamseeachanta/assethold/issues/37)
**Tier:** T1 (single-site chore)
**Date:** 2026-05-05

## Context

Issue #37 reports that local clones still have `origin` pointing at `https://github.com/samdansk2/assethold.git` while the canonical repo has moved to `vamseeachanta/assethold`. Pushes succeed via GitHub redirect but that's fragile. Body lists per-clone `git remote set-url` plus a checklist of in-tree URLs to audit: `pyproject.toml::repository`, `README.md`, `mkdocs.yml::repo_url`, `.github/workflows/`, `CHANGELOG.md`.

This is consistent with the workspace-hub memory note `project_assethold_ownership_transfer.md` (transferred samdansk2 → vamseeachanta). Action is mechanical: sed-style URL rewrite + per-clone remote update.

## Plan

1. **In-tree URL audit + rewrite**:
   - `git grep -l "samdansk2/assethold"` → enumerate every file referencing the old URL.
   - For each match: replace `samdansk2/assethold` with `vamseeachanta/assethold`. Specific known files:
     - `pyproject.toml` — check for `repository`, `homepage`, `documentation` URLs.
     - `README.md` — clone instructions, badges.
     - `mkdocs.yml` — `repo_url`, `repo_name` fields.
     - `CHANGELOG.md` — compare-link footers (if present).
     - `.github/workflows/*.yml` — any hardcoded checkout URLs.
   - Single commit titled `chore: update repo URL references to vamseeachanta/assethold`.
2. **Per-clone remote update** (documented in CONTRIBUTING or commit message, not a code change):
   - `git remote set-url origin https://github.com/vamseeachanta/assethold.git`
   - User runs this on each active clone (Linux + Windows + Mac if any).
3. **Verification commands**:
   - `git remote -v` shows the new URL.
   - `git grep "samdansk2/assethold" | wc -l` returns 0.
   - `mkdocs build --strict` still passes (catches `repo_url` mistakes).

Smoke: `git grep "samdansk2/assethold"` should output empty after edits.

## Acceptance Criteria

- `git grep -i "samdansk2"` returns zero matches across the working tree.
- `pyproject.toml`, `README.md`, `mkdocs.yml` all reference `vamseeachanta/assethold` (verified by manual diff review).
- A single chore commit lands with all URL fixes.
- Issue body's per-clone `git remote set-url` step is documented in commit message body or in `CONTRIBUTING.md` (whichever the repo prefers).
- `mkdocs build --strict` passes after the rewrite.

## Open questions

None — this is mechanical. Per workspace-hub memory `project_assethold_ownership_transfer.md`, the rewrite is correct and unambiguous.
