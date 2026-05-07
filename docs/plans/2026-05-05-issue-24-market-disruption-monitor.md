# Issue #24 Plan — Market disruption monitor (30-min cron during volatile sessions)

**Issue:** [vamseeachanta/assethold#24](https://github.com/vamseeachanta/assethold/issues/24)
**Tier:** T3 (module-feature)
**Date:** 2026-05-05

## Context

Issue #24 specifies a 30-minute lightweight monitor running 9:30 AM-4:00 PM ET Mon-Fri that emits alerts only when disruption thresholds are crossed: VIX > 25, SPY intraday move > ±2%, portfolio drop > 3% from prior close, any held symbol > ±5% intraday. Output: console log + WhatsApp alert (depends on #23) + JSONL audit log under `data/monitor/YYYY-MM-DD.jsonl`. Each run < 10 seconds. Cooldown: max 1 alert per trigger per 2 hours. Depends on #21 Phase 1 (complete) and #23 (optional WhatsApp dispatch).

The disruption-detection logic is the new code; price fetching and WhatsApp dispatch are reused from existing modules. Position cache (per body) is read from `data/cache/positions.json` written by the morning report (#22).

## Plan

1. **Disruption detector** at `src/assethold/monitor/disruption.py`:
   - `DisruptionThresholds` dataclass loaded from `config/targets.yaml::monitor` block.
   - `evaluate(prices, prior_close_portfolio_value, positions) -> list[Trigger]` returning per-trigger objects (`vix_spike`, `spy_swing`, `portfolio_drop`, `symbol_swing`).
2. **State store** at `src/assethold/monitor/state.py`:
   - `MonitorState(file_path)` with `last_alert_at[trigger_type] -> datetime` persisted to `data/monitor/state.json`.
   - `should_alert(trigger, cooldown_hours=2) -> bool` enforcing 2-hour de-dup window.
3. **CLI entry** at `src/assethold/monitor/__main__.py`:
   - Loads position cache from `data/cache/positions.json` (skip + log if missing — morning report owns refresh).
   - Fetches `^VIX`, `SPY`, and per-symbol prices via `StockDataSource` (single batched call).
   - Runs `evaluate()`, applies cooldown, dispatches alerts (console always; WhatsApp if `--enable-whatsapp` and #23 module present), writes one JSONL row per run regardless of alert state.
4. **Config block** in `config/targets.yaml`:
   ```yaml
   monitor:
     vix_threshold: 25
     spy_swing_pct: 2.0
     portfolio_drop_pct: 3.0
     symbol_swing_pct: 5.0
     cooldown_hours: 2
   ```
5. **Cron skeleton** at `scripts/cron/assethold-monitor.cron`: `*/30 8-15 * * 1-5` (CST = 9:30-16:00 ET market hours; convert via systemd timezone).
6. **Tests** at `tests/monitor/test_disruption.py` (each threshold trips/no-trips at boundary), `tests/monitor/test_state.py` (cooldown logic), `tests/monitor/test_cli.py` (integration: synthetic position cache → expected JSONL row).

Smoke: `uv run python -m assethold.monitor --dry-run` (uses cached prices, no external calls, no WhatsApp).

## Acceptance Criteria

- Monitor exits in <10 seconds on a 6-symbol portfolio (timed in test with mocked `StockDataSource`).
- All four thresholds tested at boundary (e.g., VIX=24.99 → no alert, 25.01 → alert).
- Cooldown prevents duplicate alert within 2 hours of the same trigger type; allows after.
- JSONL log contains exactly one row per run (alert-fired or quiet); fields: timestamp, run_id, triggers, portfolio_value, vix.
- Yfinance rate-limit / API failure → log error, write JSONL row with `error: <message>`, exit 0 (cron must not flap).
- Cron runs only during market hours; weekend/holiday execution exits early with skip message.

## Open questions

- VIX delta-vs-prior-close vs absolute VIX > 25: body says absolute. Confirm and stick.
- Should portfolio_drop measure vs prior session close (calendar day) or prior 30-min snapshot? Body says "from prior close" — interpret as session prior close for simplicity.
