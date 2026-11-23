# Issue #25 Plan — Tax lot aging report (long-term capital gains optimizer)

**Issue:** [vamseeachanta/assethold#25](https://github.com/vamseeachanta/assethold/issues/25)
**Tier:** T2 (bug-fix-sized feature)
**Date:** 2026-05-05

## Context

Issue #25 wants per-tax-lot aging tracking so the trim signal (#21 Phase 2) only suggests selling lots that are already long-term (>365 days). It also wants alerts when a lot is "almost long-term" (within 30/60/90 days of crossing). Realized G/L by year is part of the deliverable. Depends on #21 Phase 1 (transaction history with per-buy dates) — already in `src/assethold/portfolio/positions.py`.

This is a focused, testable add-on. Lot data is already in the transaction history; the work is computing aging + integrating into the trim recommender.

## Plan

1. **Tax lot dataclass + builder** at `src/assethold/portfolio/tax_lots.py`:
   - `TaxLot(symbol, purchase_date, shares, cost_basis, current_value)`.
   - `build_lots(transaction_history) -> dict[symbol, list[TaxLot]]` — splits any sells using FIFO against open lots.
   - `aging_days(lot, as_of_date) -> int` and `is_long_term(lot, as_of_date) -> bool` (>=365 days).
2. **Almost-long-term detector**: `lots_approaching_long_term(lots, as_of_date, windows=(30, 60, 90)) -> dict[int, list[TaxLot]]` returning lots crossing the threshold within each window.
3. **Tax-aware trim integration**: extend `src/assethold/portfolio/allocation.py::compute_allocation` to accept an optional `tax_aware: bool` flag. When true, trim recommendations cite only long-term lots; if no long-term lots exist for an over-target symbol, downgrade trim signal to "wait for long-term" with the days-until-crossing.
4. **Realized G/L report**: `realized_gain_loss(transaction_history, year) -> RealizedGLReport` summing per-lot proceeds-minus-cost for all sells in `year`, partitioned into ST vs LT buckets.
5. **Daily-report integration**: add "Tax Lot Alerts" section to `src/assethold/portfolio/daily_report.py` showing lots within 30 days of long-term and the savings (cost-basis × ST-vs-LT rate delta, configurable rate).
6. **Tests** at `tests/portfolio/test_tax_lots.py`: lot construction with multiple buys + a partial sell (FIFO), boundary at 364 vs 365 days, almost-long-term windows, realized G/L year-partition.

Smoke: `uv run pytest tests/portfolio/test_tax_lots.py -v` and `uv run python -m assethold.portfolio.daily_report --tax-aware --dry-run`.

## Acceptance Criteria

- A buy on 2025-01-01 evaluated as-of 2026-01-01 reports `is_long_term=True`; same lot evaluated 2025-12-31 reports `False` and `aging_days=364`.
- FIFO sell of 50 shares against two 100-share buys correctly closes the older lot first; remaining lots reflect 50 + 100 shares with the newer purchase date.
- Tax-aware trim downgrades the signal for an over-target symbol with only short-term lots; surfaces "long-term in N days" message.
- Realized G/L for a fixture with 3 sells (1 ST, 2 LT) correctly partitions amounts.
- Tax-Lot-Alerts section in daily report contains a row per lot crossing long-term within the next 90 days.

## Open questions

- Default ST-vs-LT rate delta for the savings estimate? Use a config knob (`tax.short_term_rate`, `tax.long_term_rate`) defaulting to 0.32 / 0.15 — explicitly note these are the user's responsibility to keep current.
- Should specific-lot identification (vs FIFO) be user-selectable for the realized G/L computation? Defer to follow-up; FIFO only in v1.
