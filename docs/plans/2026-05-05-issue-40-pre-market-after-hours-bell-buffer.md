# Issue #40 Plan — Phase 1.5: pre-market/after-hours support + configurable bell buffer

**Issue:** [vamseeachanta/assethold#40](https://github.com/vamseeachanta/assethold/issues/40)
**Tier:** T1 (single-site extension)
**Date:** 2026-05-05

## Context

Issue #40 is the explicit Phase 1.5 follow-up to #35 (NYSE regular-session awareness, already shipped at `src/assethold/utils/market_hours.py`). Two extensions:
1. **Pre-market / after-hours support** — wire `pandas_market_calendars`'s `pre`/`post` columns through `is_market_open()`. Body estimates ~10-15 LOC.
2. **Configurable bell buffer** — a `bell_buffer_minutes` knob extending the effective regular-session window by N minutes on each side, addressing the edge case where a 9:32 ET cache built at 9:25 (pre-bell) is technically stale by 7 minutes but functionally fresh.

Body marks low priority — defer until real demand surfaces. Body raises two open questions: do free-tier feeds (yfinance, Alpaca IEX) deliver useful pre/post data, and should `--intraday` become tri-state (`--extended-hours`).

This is a clean, well-scoped extension. Implementation is small enough that it can land before demand surfaces if the user prefers.

## Plan

1. **Extend `src/assethold/utils/market_hours.py`**:
   - Add `include_extended: bool = False` kwarg to `is_market_open(ts, include_extended=False)`. When True, check `pre_open <= ts < post_close` against the calendar schedule's `pre`/`post` columns.
   - Mirror in `next_open(ts, include_extended=False)` and `next_close(ts, include_extended=False)`.
   - Add `bell_buffer_minutes: int = 0` to all three. When non-zero, extend the effective regular-session window by N minutes on each side (regular session only; extended-hours window already has wide buffers).
2. **Wire `effective_cache_ttl()`** (added by #34 plan) to honor the same `include_extended` flag — extended-hours fetches use intraday TTL, regular-session-only fetches use base TTL during pre/post.
3. **CLI flag handling** in `src/assethold/analysis/daily_strategy/__main__.py`:
   - Add `--extended-hours` flag, mutually exclusive with `--no-intraday`.
   - When set, daily-strategy treats pre-market and after-hours as cacheable intraday windows.
4. **Config block** in `config/daily_strategy.yaml`:
   ```yaml
   intraday:
     extended_hours: false
     bell_buffer_minutes: 0
   ```
5. **Tests** at `tests/utils/test_market_hours.py` (extend):
   - 4 cases for pre-market: at 7:00 ET strict mode → False, extended mode → True; same for after-hours.
   - 2 cases for bell buffer: at 9:25 ET with `bell_buffer_minutes=10` → True; without buffer → False.
   - Holiday boundary: 2026-07-03 (early close) extended-hours window respects the calendar's truncated `post` column.

Smoke: `uv run pytest tests/utils/test_market_hours.py -v` and `uv run python -c "from datetime import datetime; from zoneinfo import ZoneInfo; from assethold.utils.market_hours import is_market_open; print(is_market_open(datetime(2026,5,5,7,0,tzinfo=ZoneInfo('America/New_York')), include_extended=True))"`.

## Acceptance Criteria

- `is_market_open(ts, include_extended=True)` returns True for 7:00 ET on a trading day; returns False without the flag.
- `bell_buffer_minutes=10` makes a 9:25 ET timestamp evaluate as open in regular-session mode.
- Holiday early-close (e.g., 2026-07-03 NYSE early close at 13:00 ET) → after-hours window starts at 13:00 ET, not 16:00 ET.
- `--extended-hours` CLI flag changes fetch behavior; `--dry-run` confirms intent without making API calls.
- Existing market-hours tests still pass.
- Open question on free-tier pre/post data quality is documented as a TODO comment in the module, not gated.

## Open questions

- yfinance pre/post quote quality — body raises this as open. Defer to field testing; surface a warning when extended-hours mode is active and the fetched data has obvious gaps.
- `--intraday` vs `--extended-hours` flag semantics: this plan treats them as additive (both can be set; `--extended-hours` extends `--intraday`'s window). Body's tri-state proposal is explicitly considered and rejected for v1 in favor of additive flags.
