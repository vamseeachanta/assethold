# Issue #7 Plan — Portfolio value (cash + stock + dividends + benchmarks)

**Issue:** [vamseeachanta/assethold#7](https://github.com/vamseeachanta/assethold/issues/7)
**Tier:** T3 (module-feature)
**Date:** 2026-05-05

## Context

Issue #7 wants a portfolio-value module that tracks cash + stock holdings together, simulates a fixed monthly cash injection (e.g. $1000/mo), accounts for dividend cash flow back into the cash bucket, and compares to alternatives (FD, SPY benchmark). Three of the seven checkboxes are already marked done in the body; the remaining work is dividend accounting on stock performance, FD comparator, and SPY benchmark. The repo already has `src/assethold/portfolio/positions.py`, `portfolio/allocation.py`, `portfolio/reports.py`, `portfolio/ingest.py` (Fidelity CSV loader), and a fresh `src/assethold/modules/fixed_interest/fd.py` with simple/compound interest + ladder math. SPY benchmark logic is requested by issue #27 — there is overlap.

This issue should be reframed as the **integration tracker**: it stitches dividend reinvestment (per-symbol payout history → cash bucket), monthly-contribution simulation, and SPY/FD comparator views into one report. Standalone modules already exist; what's missing is the assembly + a single CLI entry point. Acceptance criteria below scope to that integration.

## Plan

1. **Dividend cash-flow module** at `src/assethold/portfolio/dividends.py`: ingest dividend events from yfinance (or a cached CSV under `data/dividends/`) per held symbol, project them onto the position-history timeline, and emit a `dividend_cash_flow` series keyed by date.
2. **Monthly-contribution simulator** in `src/assethold/portfolio/value_simulator.py`: take a `PositionsHistory` + a contribution schedule (`amount_usd: 1000, frequency: monthly` from `config/targets.yaml`) and produce a daily cash + stock value series.
3. **Benchmark comparator** in `src/assethold/portfolio/benchmarks.py`: compute SPY and a configurable FD rate trajectory over the same date range using `modules.fixed_interest.fd.compound_interest`. Returns a unified DataFrame: `date, portfolio_value, spy_value, fd_value`.
4. **Wire into reports**: extend `src/assethold/portfolio/reports.py` to accept the comparator series and emit a side-by-side table + matplotlib comparison chart.
5. **CLI entry**: `python -m assethold.portfolio --simulate-monthly 1000 --benchmark spy,fd:0.045 --output data/portfolio/comparison.html`.
6. **Tests**: `tests/portfolio/test_value_simulator.py` and `tests/portfolio/test_benchmarks.py` with synthetic position+dividend fixtures.

Smoke: `uv run pytest tests/portfolio/ -v` and `uv run python -m assethold.portfolio --simulate-monthly 1000 --benchmark spy --dry-run`.

## Acceptance Criteria

- Dividend cash flow correctly maps a $1.40/share VOO ex-date payout onto a 100-share holding as a $140 cash credit on payout-date in the simulated series.
- Monthly contribution at $1000 over 12 months adds exactly $12,000 to cash inflows in the simulator output.
- SPY and FD benchmark series cover the same date range as the portfolio series with no off-by-one errors at the endpoints.
- CLI produces a comparison HTML with portfolio/SPY/FD lines on one chart and a final-value table.
- Unit suite passes; existing portfolio tests still pass (no regressions).

## Open questions

- Should dividend cash-flow be auto-reinvested back into the originating symbol, or accumulate in cash? The issue body says "add this to cash" — defer auto-reinvest to issue #26 which is dividend-focused.
- Does monthly contribution arrive on the first trading day or last calendar day of the month? Default to first trading day; configurable via `targets.yaml`.
