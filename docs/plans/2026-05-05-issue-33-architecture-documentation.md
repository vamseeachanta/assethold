# Issue #33 Plan — Architecture documentation (module diagram, MkDocs build, data format specs)

**Issue:** [vamseeachanta/assethold#33](https://github.com/vamseeachanta/assethold/issues/33)
**Tier:** T2 (documentation)
**Date:** 2026-05-05

## Context

Issue #33 lists four documentation gaps: (1) no architecture overview / module dependency diagram, (2) MkDocs configured (`pyproject.toml` + `mkdocs.yml` exist) but never built in CI, (3) no data format specs for Fidelity CSV / yfinance cache / `daily_strategy.yaml`, (4) sub-modules under `appliances/`, `gis/`, `property_timeline/`, `analysis/daily_strategy/` lack READMEs. Body declares dependency on #30 (module consolidation).

Repo state confirms `mkdocs.yml` exists at root, `docs/` already has `architecture.md` (6.8 KB), `index.md`, `HTML_REPORTING_STANDARDS.md`, plus a `modules/` subfolder. So the "no architecture overview" claim is partially stale — there *is* an `architecture.md`. Plan verifies and extends rather than starting from scratch.

## Plan

1. **Audit and extend `docs/architecture.md`**:
   - Confirm the existing 6.8 KB document covers the system.
   - Add Mermaid diagram showing top-level dependency: `data sources → ingest → positions → allocation → reports`, with sibling modules (`signals/`, `factor_models/` from #18, `projection/` from #28, `dividends/` from #26).
   - Add data-flow narrative: CSV → ingest → analysis → report.
   - Add config hierarchy section: `config/*.yaml` → CLI args → defaults precedence.
2. **MkDocs build verification**:
   - Run `uv run mkdocs build --strict` locally; fix any warnings.
   - Add `docs-build` job to `.github/workflows/docs.yml` (file already exists — verify) to run `mkdocs build --strict` on every PR. Do not deploy yet.
   - Verify `mkdocstrings` plugin auto-generates API pages for at least `assethold.portfolio`, `assethold.signals`, `assethold.dividend_forecast`.
3. **Data format specs** at `docs/data-formats/`:
   - `fidelity-csv.md` — column schema, both 2020-2021 and 2022+ format versions, action-type vocabulary, money-market ticker handling. Cite `src/assethold/portfolio/ingest.py` and `config/daily_strategy.yaml::loader.columns` as ground truth.
   - `yfinance-cache.md` — directory layout under `data/cache/`, TTLs, file naming convention. Cite `src/assethold/modules/stocks/cache.py`.
   - `daily-strategy-yaml.md` — schema for `config/daily_strategy.yaml` with field-by-field meaning.
4. **Sub-module READMEs**:
   - `src/assethold/modules/appliances/README.md`
   - `src/assethold/modules/gis/README.md`
   - `src/assethold/modules/property_timeline/README.md`
   - `src/assethold/analysis/daily_strategy/README.md`
   - Each: 1-paragraph purpose, public entry points, input/output contracts, example CLI invocation.
5. **Update `mkdocs.yml`** nav block to include all new doc pages.

Smoke: `uv run mkdocs build --strict` and `find docs -name '*.md' | xargs grep -l 'TODO' | wc -l` (should remain 0 for new docs).

## Acceptance Criteria

- `mkdocs build --strict` completes with zero warnings.
- `docs/architecture.md` contains a Mermaid diagram with at least 8 module nodes and arrow edges.
- `docs/data-formats/` directory contains the three named markdown files; each cites the source-of-truth Python module path.
- 4 named sub-modules each have a README with the required sections.
- `.github/workflows/docs.yml` runs `mkdocs build --strict` as a blocking check on PRs.
- `mkdocs.yml` nav references all new pages.

## Open questions

- Should we deploy MkDocs to GitHub Pages now, or just gate the build? Body says "don't deploy yet, just verify it builds" — defer deploy.
- Cite `mkdocstrings` auto-generated API pages explicitly in nav, or rely on plugin defaults? Plugin defaults are fine for v1.
