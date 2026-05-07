# Issue #34 Plan — Assess and integrate real-time stock price feeds across modules

**Issue:** [vamseeachanta/assethold#34](https://github.com/vamseeachanta/assethold/issues/34)
**Tier:** T3 (multi-phase architectural)
**Date:** 2026-05-05

## Context

Issue #34 documents a comprehensive freshness audit across every assethold module showing 4-24h cache TTLs that are wrong for intraday signals (alert engine misses breakouts, allocation drift undetected, covered-call Greeks stale). Body proposes 4 phases: (1) market-hours awareness + reduced intraday TTLs, (2) scheduled intraday monitoring via APScheduler, (3) WebSocket streaming feeds, (4) real-time risk dashboard. Phase 1 is independent and explicitly marked low effort. Phase 1 partially overlaps with #40 (pre-market/after-hours support).

Per #40 body, Phase 1 has already shipped some pieces: NYSE regular-session awareness via `pandas_market_calendars` lives at `src/assethold/utils/market_hours.py`. So Phase 1 here = "wire `is_market_open()` into cache decisions and add the `--intraday` flag", not "implement market hours from scratch".

This plan focuses on **Phase 1 only**. Phases 2-4 should be tracked as separate issues filed once Phase 1 lands and exposes concrete questions about scheduler/streaming choice.

## Plan

1. **Verify and extend `src/assethold/utils/market_hours.py`**:
   - Confirm `is_market_open(ts) -> bool` exists and handles weekends/holidays.
   - Add `effective_cache_ttl(now, base_ttl_hours, intraday_ttl_minutes=15) -> timedelta` returning the shorter intraday TTL when market is open.
2. **Wire reduced TTL into fetchers**:
   - `src/assethold/signals/data_sources.py::StockDataSource` — accept `intraday_ttl_minutes` constructor arg; route through `effective_cache_ttl()`.
   - `src/assethold/analysis/daily_strategy/fetcher.py::MarketDataFetcher` — same.
   - `src/assethold/modules/stocks/cache.py` — extend the cache key to include the TTL bucket so intraday cache entries don't collide with EOD entries.
3. **Skip-when-closed**: extend `StockDataSource.fetch()` to honor a `skip_when_closed: bool = False` flag; when True and market is closed, return cached data without re-fetching even if cache is stale (saves API quota on weekends).
4. **`--intraday` CLI flag** on `src/assethold/analysis/daily_strategy/__main__.py`:
   - When passed, sets `intraday_ttl_minutes=15` on the underlying fetcher and runs the daily-strategy pipeline mid-day.
   - When omitted, behaves exactly as today (no behavior change without flag — preserves backwards compat).
5. **Config block** in `config/daily_strategy.yaml`:
   ```yaml
   intraday:
     enabled: false   # CLI flag overrides
     ttl_minutes: 15
     skip_when_closed: true
   ```
6. **Tests** at `tests/utils/test_market_hours.py` (extend with `effective_cache_ttl` boundary cases) and `tests/signals/test_data_sources_intraday.py` (mock clock at 10:00 ET → intraday TTL applied; at 18:00 ET → base TTL applied).
7. **Phases 2-4 follow-ups**: file 3 new issues citing this issue + scoping each phase before implementation. Do not start implementation in this plan.

Smoke: `uv run pytest tests/utils/test_market_hours.py tests/signals/test_data_sources_intraday.py -v` and `uv run python -m assethold.analysis.daily_strategy --intraday --dry-run`.

## Acceptance Criteria

- `effective_cache_ttl` returns 15 min during market hours, base TTL outside, and base TTL on weekends/holidays.
- `StockDataSource` honors the intraday TTL and emits cache key including TTL bucket so intraday/EOD entries do not collide.
- `--intraday` flag wires through to the fetcher; without flag, no behavior change vs today (regression-tested).
- API calls are skipped on a Saturday fixture when `skip_when_closed=true` and cache is populated.
- 3 follow-up issues filed for Phases 2/3/4 with explicit scope.
- Existing daily-strategy tests still pass.

## Open questions

- Should `--intraday` also trigger a different output path (e.g., `data/reports/<date>-intraday.html`) so morning EOD report isn't overwritten? Default yes — separate path.
- 15 min TTL rationale: matches the shortest cron cadence in #24 monitor. Confirm or adjust per yfinance rate limits in field testing.
