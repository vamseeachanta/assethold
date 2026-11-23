# Issue #21 Plan — Portfolio Dashboard: Automated Allocation Tracking & Daily Review

**Issue:** [vamseeachanta/assethold#21](https://github.com/vamseeachanta/assethold/issues/21)
**Tier:** T3 (module-feature, multi-phase)
**Date:** 2026-05-05

## Context

Issue #21 specifies a 5-phase dashboard: ingest Fidelity CSVs → compute net positions/cost basis → allocation monitor (vs targets in `config/targets.yaml`) → DCA cadence tracker → performance benchmarking → daily report generator. Phase 1 is annotated "complete" in dependent issues #22/#23/#24/#25/#26/#27 — the existing `src/assethold/portfolio/{ingest,positions,allocation,reports}.py` files corroborate that. Phases 2–5 still need work, with concrete sub-bullets in the body. `config/targets.yaml` already exists and matches the target_allocation block in the issue.

This is the umbrella for the dashboard family. Plans for #22–#28 cite #21 as a dependency. Treat each remaining phase as one shippable increment.

## Plan

1. **Phase 2 — Allocation monitor** (`src/assethold/portfolio/allocation.py` extension):
   - Add `compute_allocation(positions, prices, targets) -> AllocationReport` returning per-symbol current%, target%, drift%, trim/accumulate flag (>±5pp threshold per `targets.yaml`).
   - Add `new_money_split(amount_usd, split_config) -> dict[str, float]` returning per-symbol share counts to deploy.
   - Tests in `tests/portfolio/test_allocation.py`.
2. **Phase 3 — DCA tracker** at `src/assethold/portfolio/dca.py`:
   - `buying_cadence(transaction_history, dca_config) -> CadenceReport` with last-buy date, days-since-last, days-until-due-per-symbol.
   - `lot_size_drift(transactions, target_lot_usd) -> Series` flagging recent buys far from `$4500` target.
3. **Phase 4 — Performance** at `src/assethold/portfolio/performance.py`:
   - `time_weighted_return(positions, prices, cash_flows) -> pd.Series` (daily TWR vs static-hold).
   - Realized G/L by year + tax-lot aging stub (full implementation in #25).
4. **Phase 5 — Report generator** at `src/assethold/portfolio/daily_report.py`:
   - Aggregates Phase 2/3/4 outputs into a single `DailyReport` dataclass.
   - Renders to terminal (rich-text), markdown, and HTML (Jinja2 template at `src/assethold/portfolio/templates/daily.html.j2`).
   - CLI: `python -m assethold.portfolio.daily_report --output html|md|terminal`.
5. **Integration tests** at `tests/integration/test_daily_report_e2e.py`: synthetic transaction history → CSV → report. Verify each phase wires into the next.

Smoke per phase:
- `uv run pytest tests/portfolio/test_allocation.py -v`
- `uv run pytest tests/portfolio/test_dca.py -v`
- `uv run pytest tests/portfolio/test_performance.py -v`
- `uv run python -m assethold.portfolio.daily_report --dry-run`

## Acceptance Criteria

- Phase 2 outputs trim/accumulate flags matching the trim_rules.threshold_pct=5.0 boundary (a position at +4.9pp does NOT trigger; at +5.1pp does).
- New-money splitter for $1000 input with VOO=0.55 / BRKB=0.45 returns proportional share counts based on current prices.
- Phase 3 cadence tracker emits "overdue" when last VOO buy was >6 days ago (per `dca_cadence.VOO.interval_days`).
- Phase 4 TWR for a buy-and-hold-only portfolio matches a hand-computed expected value within 0.01%.
- Phase 5 daily report renders all three formats (terminal, md, html) and contains: positions table, allocation deltas, trim/accumulate signals, DCA status, dividend summary placeholder.
- E2E integration test passes end-to-end on a synthetic 100-transaction fixture.

## Open questions

- Market-price source for Phase 2: yfinance live or cached EOD? Default to cached EOD via existing `signals.data_sources.StockDataSource`; an `--intraday` flag uses live (mirrors #34 Phase 1 pattern).
- Realized G/L lot-selection method: FIFO, LIFO, or specific-lot? Default FIFO; specific-lot deferred to #25.
