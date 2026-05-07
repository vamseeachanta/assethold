# Issue #23 Plan — WhatsApp trade signals at market open and close

**Issue:** [vamseeachanta/assethold#23](https://github.com/vamseeachanta/assethold/issues/23)
**Tier:** T3 (module-feature, external-integration)
**Date:** 2026-05-05

## Context

Issue #23 specifies two scheduled WhatsApp messages per trading day: 8:35 AM CST (5 min after open) and 2:45 PM CST (75 min before close). Each message contains top buy signal, top trim signal, DCA status. Body is concrete on times, format, and rationale. Integration options: Twilio WhatsApp API or Meta Cloud API (WhatsApp Business). Phone + API key in env vars, holiday-aware, retry on API failure.

Depends on #21 Phase 1 (positions/allocation) — already complete — and #21 Phase 2 (allocation monitor) which is scoped in the #21 plan.

## Plan

1. **WhatsApp client** at `src/assethold/notifications/whatsapp.py`: `send_message(phone_number, body)` wrapping Twilio's `whatsapp:` endpoint. Credentials from env (`ASSETHOLD_TWILIO_SID`, `ASSETHOLD_TWILIO_TOKEN`, `ASSETHOLD_TWILIO_FROM`, `ASSETHOLD_WHATSAPP_TO`). Add `twilio` to `pyproject.toml`.
2. **Signal aggregator** at `src/assethold/notifications/signal_message.py`: `build_signal_message(positions, allocation_report, dca_report) -> str` returning the formatted message body (matches body example exactly: emoji prefix, BUY/TRIM/DCA lines, portfolio total + gain).
3. **Schedule entry** at `src/assethold/notifications/__main__.py`: parses `--window {open,close}` (8:35 = open, 14:45 = close), pulls fresh prices via existing `StockDataSource`, runs allocation + DCA modules, builds message, dispatches.
4. **Config block** in `config/targets.yaml`:
   ```yaml
   notifications:
     whatsapp:
       enabled: true
       times:
         open: "08:35"   # CST
         close: "14:45"  # CST
       provider: twilio
   ```
5. **Holiday + weekend gate**: reuse `assethold.utils.market_hours.is_trading_day()` — exit 0 with a log line on non-trading days.
6. **Retry logic**: on Twilio failure (5xx or rate limit), retry up to 3 times with 30s backoff; log final failure but exit 0 (cron should not flap).
7. **Cron skeleton** at `scripts/cron/assethold-whatsapp.cron`: two entries, one per window.
8. **Tests** at `tests/notifications/test_signal_message.py` (asserts message format), `tests/notifications/test_whatsapp.py` (mocks Twilio client, verifies retry behavior).

Smoke: `uv run python -m assethold.notifications --window open --dry-run` (prints message to stdout, does not call Twilio).

## Acceptance Criteria

- Message body matches the example in issue body: contains top BUY, top TRIM, DCA status, portfolio total, gain%.
- Twilio calls happen only when `ASSETHOLD_TWILIO_*` env vars are set; missing creds → exit 2 with clear stderr.
- Holiday gate skips dispatch on a NYSE holiday (asserted via test fixture).
- Retry on simulated 503 succeeds on the second attempt; logs both attempts.
- No credentials appear in config files, logs, or commit history (verified via grep in CI).
- Dry-run produces formatted message on stdout without making any external API call.

## Open questions

- Twilio vs Meta Cloud API: Twilio is simpler (single env-var bundle) but charges per message; Meta is free but requires Business verification. Default to Twilio for v1; document migration path in module docstring.
- Should "top buy / top trim" be ranked by drift magnitude, signal strength, or recency? Default to drift magnitude (largest %-points away from target wins) for determinism.
