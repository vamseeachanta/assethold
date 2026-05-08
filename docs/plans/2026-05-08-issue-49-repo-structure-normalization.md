# Plan for #49: chore(repo-structure): normalize assethold folder/file structure

> **Status:** ready for `status:plan-review` / user approval; implementation blocked
> **Complexity:** T3
> **Date:** 2026-05-08
> **Issue:** https://github.com/vamseeachanta/assethold/issues/49
> **Review artifact:** `scripts/review/results/2026-05-08-plan-49-repo-structure-review-synthesis.md`
> **Parent anchors:** workspace-hub#1962, workspace-hub#2397

---

## Decision Summary

This plan is a **repo-specific planning gate** for `assethold` folder/file structure normalization. It authorizes only a bounded Phase 1 after approval: inventory-backed structure contract, machine-readable exception policy, checker/test harness, and minimal documentation/index updates required to stop new drift.

No broad file moves, generated artifact deletion, package-source reshuffle, docs migration, or runtime behavior change is authorized until this plan is explicitly approved and Phase 1 tests/checkers exist.



## Resource Intelligence Summary

### Existing assets

- Repository: `vamseeachanta/assethold`
- Current issue: https://github.com/vamseeachanta/assethold/issues/49
- Root directories observed: .agent-os/, .claude/, .codex/, .common/, .drcode/, .gemini/, .git-commands/, .github/, .mypy_cache/, .planning/, .pytest_cache/, .ruff_cache/, .slash-commands/, .venv/, .vscode/, _coding_agents/, agents/, bin/, business/, config/, data/, dev_tools/, docs/, examples/, htmlcov/, modules/, reports/, scripts/, site/, src/, src\assethold\tests\test_data\analysis\Portfolio\results\Data/, tests/
- Root files observed: .command-link, .command-registry.json, .coverage, .gitignore, .pre-commit-config.yaml, .radon.cfg, AGENTS.md, AGENT_OS_COMMANDS.md, CHANGELOG.md, CLAUDE.md, CLAUDE.md.backup-20251023-081047, CLAUDE.md.backup.20250805-204115, COMMANDS.md, LICENSE, MANDATORY_SLASH_COMMAND_ECOSYSTEM.md, MANIFEST.in, Makefile, README.md, REQUIREMENTS_MIGRATION.md, coverage.json, coverage.xml, mkdocs.yml, poetry.lock, poetry_latest_versions.txt, pyproject.toml, pyproject.toml.backup, pytest.ini, pytest.xml, requirements-consolidated.txt, setup.py, uv.lock, uv.toml, vulture_whitelist.py
- Standard directory counts:
- `src/`: 283 files in working-tree scan
- `tests/`: 349 files in working-tree scan
- `docs/`: 318 files in working-tree scan
- `scripts/`: 19 files in working-tree scan
- `config/`: 6 files in working-tree scan
- `.github/`: 2 files in working-tree scan
- `reports/`: 3 files in working-tree scan
- `data/`: 574 files in working-tree scan
- `modules/`: 7 files in working-tree scan
- `site/`: 316 files in working-tree scan
- `htmlcov/`: 98 files in working-tree scan

### Tracked root files observed

- `AGENT_OS_COMMANDS.md`
- `AGENTS.md`
- `CHANGELOG.md`
- `CLAUDE.md`
- `CLAUDE.md.backup.20250805-204115`
- `CLAUDE.md.backup-20251023-081047`
- `.command-link`
- `.command-registry.json`
- `COMMANDS.md`
- `coverage.json`
- `.gitignore`
- `LICENSE`
- `Makefile`
- `MANDATORY_SLASH_COMMAND_ECOSYSTEM.md`
- `MANIFEST.in`
- `mkdocs.yml`
- `poetry_latest_versions.txt`
- `poetry.lock`
- `.pre-commit-config.yaml`
- `pyproject.toml`
- `pyproject.toml.backup`
- `pytest.ini`
- `.radon.cfg`
- `README.md`
- `requirements-consolidated.txt`
- `REQUIREMENTS_MIGRATION.md`
- `setup.py`
- `uv.lock`
- `uv.toml`
- `vulture_whitelist.py`

### Tracked generated-output candidates observed

- `reports/.gitkeep`
- `reports/daily-strategy/2026-02-18.md`
- `reports/daily-strategy/history/signals.csv`

### Related prior work

- Workspace-hub ecosystem anchors: `workspace-hub#1962` and `workspace-hub#2397`.
- `digitalmodel#596` is the template-quality first repo plan and discipline model: contract first, checker second, bounded moves only after approval.
- This plan does not assume previous repo-specific cleanup issues are complete; implementation must re-check live git state before editing.

### Constraints

- Follow workspace-hub hard gates: Issue → Plan → Adversarial Review → `status:plan-review` → explicit user approval → implementation.
- TDD is mandatory before checker or migration code.
- Preserve evidence and rollback ability for every moved/removed tracked path.
- Do not delete or relocate generated-looking tracked files until classified as unauthorized artifact, durable evidence, or temporary durable exception.
- Do not move package/source/runtime/static entrypoints without import/build/deploy proof specific to this repo.

### Gaps

- No approved local structure contract for this normalization tranche.
- Generated-output and root-clutter classification needs a machine-readable allow/deny/exception inventory before cleanup.
- CI/pre-commit enforcement may be absent or insufficient for new root artifacts.

### Risks / unknowns

- Hidden consumers may reference current paths from docs, CI, packaging, static hosting, notebooks, or external scripts.
- Some generated-looking files may be durable evidence or deploy artifacts; deleting them blindly would lose traceability.
- Root-level clutter can include user/session artifacts; implementation must not reset unrelated dirty files.

## Scope Boundaries

### In scope after approval

1. Add/update repo-local structure standard under `docs/standards/repo-structure.md` or closest existing standards surface.
2. Add machine-readable contract such as `config/repo_structure.yml` listing allowed roots, denied generated roots, and temporary durable exceptions.
3. Add checker under `scripts/maintenance/verify_repo_structure.py` or equivalent repo-appropriate maintenance path.
4. Add TDD tests under `tests/repo_structure/` or equivalent test surface.
5. Wire checker into pre-commit/CI if those surfaces exist.
6. Move only low-risk root utility/docs artifacts that have no source/runtime consumers and are covered by tests/checker evidence.
7. Create follow-up issues for broad package/docs/generated-evidence migrations discovered during implementation.

### Out of scope

- Bulk source package reorganization.
- Broad docs tree migration.
- Deletion of generated-looking tracked files without classification and follow-up linkage.
- Notebook/data/report/static deploy relocation unless explicitly classified and tested.
- Any execution before explicit user approval.

## Artifact Map

| Artifact | Path | Purpose |
|---|---|---|
| Canonical plan | `docs/plans/2026-05-08-issue-49-repo-structure-normalization.md` | Approval gate for this repo |
| Review synthesis | `scripts/review/results/2026-05-08-plan-49-repo-structure-review-synthesis.md` | Adversarial/readiness findings |
| Structure standard | `docs/standards/repo-structure.md` or existing standard path | Human-readable contract |
| Machine contract | `config/repo_structure.yml` | Checker source of truth |
| Checker | `scripts/maintenance/verify_repo_structure.py` | Enforce root/generated/exception rules |
| Tests | `tests/repo_structure/test_repo_structure_contract.py` | TDD for checker and contract |
| Approval marker after approval only | `.planning/plan-approved/49.md` | Execution authorization evidence |

## Pseudocode

```text
load config/repo_structure.yml
collect git-tracked paths and working-tree root entries
for each root entry:
    classify as allowed, denied-generated, temporary-exception, or unknown
    if unknown or denied without exception:
        emit deterministic violation with remediation hint
for each temporary exception:
    require owner/category/review-date/follow-up URL/non-placeholder justification
scan moved-file candidates:
    require no references outside approved update set before moving
return nonzero if violations exist
```

## TDD Test List

- RED: checker fails on an unapproved root file/dir fixture.
- RED: checker fails on tracked generated-output root without exception metadata.
- RED: checker fails on exception metadata with placeholder owner/review-date/follow-up URL.
- GREEN: checker accepts current approved roots and explicitly listed exceptions.
- GREEN: reference scan blocks candidate moves with live consumers.
- GREEN: CI/pre-commit invocation path is covered by a smoke test or workflow grep assertion.

## Acceptance Criteria

1. Plan remains planning-only until explicit user approval.
2. Implementation has TDD coverage before checker/migration code lands.
3. Human-readable and machine-readable structure contracts exist.
4. Generated-output candidates are classified, not blindly deleted.
5. CI/pre-commit prevents newly introduced root/generated drift.
6. Any moved paths have reference-scan proof and rollback notes.
7. Follow-up issues are created for broad migrations rather than silently absorbed.

## Follow-up Issue Candidates

- Package/domain module reorganization if inventory shows large package-layout drift.
- Generated evidence relocation/classification for tracked reports/results/build outputs.
- Docs/navigation restructuring if docs references require broader moves.
- Static deploy artifact policy, if applicable, for generated `dist/`, site, sitemap, or public assets.

## Review Readiness Notes

This plan is intentionally conservative and reusable across the tier-1 repo ecosystem. Reviewers should reject implementation attempts that start moving/deleting files before the contract/checker/test layer is approved and green.

## Approval Gate

Execution is not authorized until the user approves this exact plan and implementation records `.planning/plan-approved/49.md` with the reviewed commit/blob SHA.
