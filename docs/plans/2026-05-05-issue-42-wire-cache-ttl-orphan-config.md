# Issue #42 Plan — Wire settings.cache_ttl_hours through StockDataSource consumers (orphan config)

**Issue:** [vamseeachanta/assethold#42](https://github.com/vamseeachanta/assethold/issues/42)
**Tier:** T1 (single-site config wiring)
**Date:** 2026-05-05

## Context

Issue #42 is a focused remediation for an orphan config value: `config/stocks/watchlist.yml::settings.cache_ttl_hours` (= 24) is declared but never consumed by any fetcher. Body confirms the precedent already landed in #39 (`src/assethold/signals/watchlist_runner.py` reads it; commit `3f5e81d`). The remaining gap is `src/assethold/analysis/daily_strategy/fetcher.py:80` — `MarketDataFetcher.__init__` constructs a `StockDataSource` but reads from `daily_strategy.yaml`, not `watchlist.yml`'s `settings:` block.

Body explicitly limits scope: do not change semantic meaning of `cache_ttl_hours`, do not migrate `daily_strategy.yaml`'s separate `price_cache_ttl_hours` knob (that's a separate dedup concern). The decision is per-consumer: either wire watchlist's settings block, or document why the consumer uses its own config.

## Plan

1. **Audit all `StockDataSource` constructions**:
   - `git grep -n "StockDataSource(" src/` to enumerate every site.
   - Known sites: `src/assethold/signals/watchlist_runner.py` (already wired per #39), `src/assethold/analysis/daily_strategy/fetcher.py:80`.
2. **Decide per-consumer**:
   - **Daily-strategy fetcher**: it reads `daily_strategy.yaml` and has its own `price_cache_ttl_hours`. Decision: keep its own config; do not also read `watchlist.yml`. Document this in the constructor docstring with a one-line "uses daily_strategy.yaml::price_cache_ttl_hours; see watchlist.yml::settings.cache_ttl_hours for watchlist consumers" note.
   - **Future Phase-2 (#34) consumers**: ensure new code reads `cache_ttl_hours` from the appropriate config (watchlist for watchlist-driven runs, daily_strategy for daily-strategy runs).
3. **Docstring update on `Watchlist`** (`src/assethold/signals/watchlist.py`): note that `settings:` block is consumed by callers (was orphan before #39).
4. **Regression test** at `tests/unit/signals/test_watchlist_runner.py` (extend, not rewrite):
   - Set `settings.cache_ttl_hours: 7` in test YAML; instantiate `WatchlistRunner`; assert `runner._source.cache_ttl == 7 * 3600` (or whatever unit the existing field uses).
5. **No changes to `daily_strategy.yaml` schema** — this is the deliberate scope limit per body.

Smoke: `uv run pytest tests/unit/signals/test_watchlist_runner.py -v` and `uv run python -c "from assethold.signals.watchlist import Watchlist; w = Watchlist.load('config/stocks/watchlist.yml'); print(w.settings.cache_ttl_hours)"`.

## Acceptance Criteria

- Audit comment landed in code identifying every `StockDataSource` construction site and its config source.
- `MarketDataFetcher.__init__` docstring notes the deliberate decision to use its own config; no behavior change.
- `Watchlist` docstring documents that `settings:` is consumer-facing, not orphan.
- New regression test confirms modifying `settings.cache_ttl_hours` in a test YAML is reflected in `runner._source.cache_ttl`.
- No regression in existing 868-test unit suite.

## Open questions

- Should `daily_strategy.yaml::price_cache_ttl_hours` and `watchlist.yml::settings.cache_ttl_hours` be deduplicated to a single root-level config? Body explicitly defers this to a separate concern. Defer.
- Should the audit comment be a docstring or a code comment in a `# CONFIG-AUDIT:` block? Default: docstring on the consumer, plus one `# fmt: off` audit table in `docs/data-formats/daily-strategy-yaml.md` (per #33 plan).
