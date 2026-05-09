# Repository Structure Standard

Issue: [assethold#49](https://github.com/vamseeachanta/assethold/issues/49)

This document defines the Phase 1 repository-structure contract for `assethold`.
It is deliberately conservative: this phase adds a contract, checker, tests, and
enforcement wiring only. It does **not** authorize broad source moves, docs
migration, generated-output deletion, or package-layout reshuffling.

## Canonical roots

The machine-readable source of truth is
[`config/repo_structure.yml`](../../config/repo_structure.yml). The checker uses
that file to validate:

- standard project roots (`src/`, `tests/`, `docs/`, `config/`, `scripts/`,
  `data/`, `modules/`, `examples/`, `bin/`, `dev_tools/`);
- tracked agent/tooling roots already present in this repository;
- approved root files such as `README.md`, `pyproject.toml`, `uv.lock`, and
  repo policy files;
- generated-output roots that require explicit classification before retention,
  deletion, or relocation.

New root-level files or directories are not allowed unless the structure
contract is intentionally updated with review evidence.

## Generated-output and durable-evidence policy

Tracked files under generated-looking roots are not automatically deleted or
moved. They must first be classified as one of:

1. unauthorized generated artifact;
2. durable evidence;
3. temporary durable exception with owner, category, review date, follow-up URL,
   justification, and explicit `allowed_paths` metadata.

For Phase 1, the tracked `reports/` paths are classified as temporary durable
evidence exceptions in `config/repo_structure.yml`. The checker rejects
placeholder metadata and rejects any new unclassified generated-output path.

The checker also rejects deletion or rename/relocation of generated-output paths
observed in `git status --short`, even if the path is otherwise classified. This
prevents silent loss of durable evidence during future cleanup work.

## Enforcement

Run the local checker directly:

```bash
uv run python scripts/maintenance/verify_repo_structure.py
```

The checker is wired into pre-commit as `repo-structure-contract` and into the
Python Tests workflow before the smoke-test step. It validates both `git
ls-files` and non-ignored working-tree paths, so untracked root drift is caught
before staging.

## Phase 1 forbidden actions

Do not perform these actions under issue #49 without a later explicit approval
that expands scope:

- broad source/package moves;
- broad docs tree migration;
- deleting tracked generated-looking files;
- relocating tracked reports/static/deploy artifacts;
- sweeping unrelated dirty data/cache files into a repo-structure commit.

If future cleanup is needed, open or link a follow-up issue and include the
classification and reference-scan proof needed for the move/delete decision.
