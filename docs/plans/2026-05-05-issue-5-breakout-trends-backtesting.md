# Issue #5 Plan — Breakout / Trends / Backtesting

**Issue:** [vamseeachanta/assethold#5](https://github.com/vamseeachanta/assethold/issues/5)
**Tier:** T3 (module-feature)
**Date:** 2026-05-05

## Context

Issue #5 sketches a 10-criterion breakout screener (price vs 50/150/200-day MAs, distance from 52-week low/high, MA stack ordering, MA uptrend duration) and proposes a per-symbol traffic-light state machine (green = all pass, orange = 1 fail, red = 2+ fail) plotted only on trend changes. The body is a brainstorming list; it does not specify the data source, lookback window, the change-detection rule, or how the "track what failed at each change" persistence layer should look. The repo already has `src/assethold/signals/trend_detector.py` and `src/assethold/signals/indicators.py` which provide MA infrastructure plus an existing alert engine — the new work is the criterion-aggregator + traffic-light emitter, not raw indicators.

Body language ("guess work", "Visually identified") indicates this is exploratory rather than executor-ready. Recommend tightening scope to **the 10 criteria + a deterministic traffic-light evaluator** in this iteration; defer the ML-driven "most important criteria" half to a follow-up issue once the deterministic version has produced enough labelled cases to train against. If the user prefers to keep this as a brainstorming bucket, this issue should close as too broad and a focused follow-up filed.

## Plan

1. **Codify the 10 criteria** in `src/assethold/signals/breakout_criteria.py` as pure functions taking an OHLCV DataFrame and returning `BreakoutCheck(name: str, passed: bool, value: float, threshold: float)`. Reuse `signals.indicators` for SMA computation; do not reimplement.
2. **Build the aggregator** `evaluate_breakout(symbol, ohlcv) -> BreakoutSnapshot` that returns the failed-criterion list and the traffic-light color per the body's spec. Persist snapshots to `data/breakout/<symbol>.jsonl` so the "track what failed at each change" requirement is satisfied via append-only history.
3. **Add change-detection emitter** `breakout_changes(snapshots) -> list[ChangeEvent]` that yields events only when color changes vs the previous snapshot — supports the body's "Only upon trend change, plot" rule.
4. **CLI entry**: `python -m assethold.signals.breakout_criteria --watchlist config/stocks/watchlist.yml --output data/breakout/`. Wire into existing `WatchlistRunner` cadence (does not need new scheduler — runs in the same nightly job).
5. **Tests**: `tests/unit/signals/test_breakout_criteria.py` with synthetic OHLCV fixtures covering all-pass, 1-fail (each criterion), 2-fail combinations, and the change-event boundary cases.

Smoke: `uv run pytest tests/unit/signals/test_breakout_criteria.py -v` and `uv run python -m assethold.signals.breakout_criteria --watchlist config/stocks/watchlist.yml --dry-run`.

## Acceptance Criteria

- 10 criterion functions pass synthetic-fixture tests for both pass and fail boundary values.
- `evaluate_breakout()` emits the correct color (green/orange/red) for hand-constructed snapshots covering 0/1/2/3 failures.
- `breakout_changes()` emits zero events on identical consecutive snapshots and exactly one event on a color flip.
- JSONL history under `data/breakout/<symbol>.jsonl` survives a process restart (append-only, no truncation).
- ML-driven criterion weighting is explicitly out of scope; tracked separately in a follow-up issue once labelled history is available.

## Open questions

- Lookback window for "200-day uptrend for 1mo" — is "uptrend" defined as monotone non-decreasing across 21 trading days, or a positive linear-regression slope? Defer to current trend_detector convention if it already encodes one.
