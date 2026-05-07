# Issue #26 Plan — Dividend reinvestment and ex-date calendar

**Issue:** [vamseeachanta/assethold#26](https://github.com/vamseeachanta/assethold/issues/26)
**Tier:** T2 (focused feature)
**Date:** 2026-05-05

## Context

Issue #26 wants ex-dividend date tracking for held symbols, expected dividend income calculation, an alert when an upcoming ex-date is within the next DCA window ("buy before ex-date to capture dividend"), dividend growth rate YoY, and monthly/quarterly/annual income projection. Depends on #21 Phase 1 (complete) and #21 Phase 4 (dividend income tracker, scoped in #21 plan). Uses yfinance dividend calendar — no new external API.

This complements but does not duplicate #17 (forecasted yield via DDM). #17 projects the *price* of dividend streams via growth models; #26 projects the *cash flow timeline* using observed ex-dates.

## Plan

1. **Ex-date fetcher** at `src/assethold/dividends/ex_date_calendar.py`:
   - `fetch_ex_dates(symbols, lookahead_days=180) -> dict[symbol, list[ExDateEvent]]` using `yfinance.Ticker(s).dividends` (historical) + `yfinance.Ticker(s).calendar` (next ex-date if available). Cache under `data/cache/dividends/<symbol>.json` with 24h TTL.
   - `ExDateEvent(symbol, ex_date, amount_per_share, source: 'historical'|'calendar')`.
2. **Income projector** at `src/assethold/dividends/projection.py`:
   - `project_income(positions, ex_dates, horizon='monthly|quarterly|annual') -> DataFrame` summing `shares × amount_per_share` grouped by horizon bucket.
   - `growth_rate_yoy(historical_dividends) -> dict[symbol, float]` computing trailing-12-month vs prior-12-month divs.
3. **DCA-window alert** at `src/assethold/dividends/dca_alert.py`:
   - `dca_capture_alert(symbol, dca_cadence, ex_dates) -> Optional[Alert]` returning an alert when the next DCA-due date is after the next ex-date (i.e., "buy before X to capture div").
4. **Daily-report integration**: add "Dividend Calendar" section to `src/assethold/portfolio/daily_report.py` with: next 30 days of ex-dates for held symbols, projected next-quarter income, capture-window alerts.
5. **Tests** at `tests/dividends/test_projection.py` (income math), `tests/dividends/test_dca_alert.py` (alert fires when ex-date < next-DCA-due), `tests/dividends/test_ex_date_calendar.py` (fetcher with mocked yfinance).

Smoke: `uv run pytest tests/dividends/ -v` and `uv run python -c "from assethold.dividends.ex_date_calendar import fetch_ex_dates; print(fetch_ex_dates(['VOO', 'XOM']))"`.

## Acceptance Criteria

- `fetch_ex_dates(['VOO'])` returns at least 4 historical ex-dates from the trailing year (VOO is quarterly).
- Income projector for 100 VOO shares × $1.40 quarterly div = $140 in the next quarter bucket; $560 annual.
- DCA-capture alert fires when next ex-date is 3 days out and next DCA-due is 8 days out (capture window: buy-now beats waiting).
- DCA-capture alert does NOT fire when next DCA-due is before next ex-date.
- Cache is honored on a second invocation within 24h (mocked clock test).
- Daily report section renders without crashing for a symbol with no scheduled ex-date in the calendar window.

## Open questions

- Should we model the actual reinvestment (auto-buy at ex-date+1)? Body says "track" + "alert", not auto-buy. Stick with alert-only for v1; full DRIP simulation is a follow-up.
- yfinance `.calendar` is unreliable for some symbols — should we cross-check against Alpha Vantage as a backup? Defer; surface "calendar unavailable" gracefully and rely on historical-cadence inference.
