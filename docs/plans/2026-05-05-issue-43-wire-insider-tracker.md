# Issue #43 Plan — Wire insider_tracker into WatchlistRunner.insider_flags_provider

**Issue:** [vamseeachanta/assethold#43](https://github.com/vamseeachanta/assethold/issues/43)
**Tier:** T2 (focused integration)
**Date:** 2026-05-05

## Context

Issue #43 closes a deferred wire-up from #39: `WatchlistRunner.insider_flags_provider` is a `Callable[[str], list[dict]] | None` slot landed in commit `fd0bc33`. When `None` (current default), the runner logs a one-shot WARNING at `__init__` and `AlertEngine.build_alerts` is called with `insider_flags=[]` — meaning CRITICAL-severity `unusual_insider_activity` alerts never fire. The slot exists specifically so this wire-up can land as its own change. Body declares `assethold.signals.insider_tracker` as the existing module to wire in.

Body lists 5 concrete steps + acceptance criteria including the existing test `test_run_uses_insider_provider_when_set`. Out of scope: extending the insider tracker itself (SEC scraping, new signals); scheduler wiring (Phase 2 of #34).

## Plan

1. **Inspect `src/assethold/signals/insider_tracker.py`**:
   - Locate `InsiderTracker.flag_unusual_activity` (per body, signature was verified in #39 review).
   - Decide whether the signature matches `Callable[[str], list[dict]]` directly or needs a thin adapter.
2. **Wire the default provider**:
   - In `src/assethold/signals/watchlist_runner.py::main()`, instantiate `InsiderTracker` and pass `tracker.flag_unusual_activity` (or an adapter lambda) as `insider_flags_provider` when config `settings.insider_tracking: true` is set.
   - Add CLI flag `--insider-tracking` / `--no-insider-tracking` mirroring the `--intraday` precedence contract from #39 (CLI flag overrides config; config defaults from `settings:` block).
3. **Config block** in `config/stocks/watchlist.yml`:
   ```yaml
   settings:
     insider_tracking: true   # CLI flag overrides
   ```
4. **Tests** at `tests/unit/signals/test_watchlist_runner.py` (extend):
   - With `--insider-tracking` and a mocked `InsiderTracker.flag_unusual_activity` returning a qualifying transaction, `runner.run()` for a 2-ticker watchlist produces at least one `unusual_insider_activity` alert.
   - With `--no-insider-tracking`, the tracker is not constructed and the WARNING is suppressed.
   - The `WARNING` log at `__init__` no longer fires when a provider is set.
5. **Integration smoke** at `tests/integration/test_watchlist_insider_e2e.py`: real `InsiderTracker` against a fixture SEC Form 4 response (mocked HTTP); end-to-end alert emission.

Smoke: `uv run pytest tests/unit/signals/test_watchlist_runner.py tests/integration/test_watchlist_insider_e2e.py -v` and `uv run python -m assethold.signals.watchlist_runner --insider-tracking --dry-run`.

## Acceptance Criteria

- With `--insider-tracking` (or `settings.insider_tracking: true`), `runner.run()` for a 2-ticker watchlist with qualifying SEC Form 4 fixture data produces at least one `unusual_insider_activity` alert.
- With `--no-insider-tracking`, `InsiderTracker` is not constructed; WARNING log present (as it was before #43).
- With `--insider-tracking` set, the `WARNING` log at `__init__` is suppressed.
- Existing `test_run_uses_insider_provider_when_set` (from #39) still passes — the injection mechanism remains unchanged.
- Integration smoke passes against a fixture HTTP response.
- No regression in the 868+ existing unit suite.

## Open questions

- Adapter shape: if `InsiderTracker.flag_unusual_activity(ticker, *, lookback_days=30)` has extra optional kwargs, the adapter can use `partial(tracker.flag_unusual_activity, lookback_days=30)`. Confirm during inspection.
- Should `--insider-tracking` default to True or False? Body says "config opts in" → default False, explicit opt-in (preserves existing behavior for users who haven't updated config).
