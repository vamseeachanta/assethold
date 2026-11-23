# Portfolio Returns Analyzer

A small, **deterministic, offline** tool that turns a YAML description of your
investment account(s) into a single self-contained interactive `dashboard.html`
— assessing returns honestly (XIRR + TWR), against a **dollar-matched index
benchmark**, with cash-drag, drawdown, and money-flow views.

All data in this repo is **hypothetical** (see `config.example.yaml`). Bring your
own numbers in a private copy; nothing personal lives here.

## Quick start

```bash
pip install pyyaml                 # the only dependency
python analyze.py config.example.yaml
# -> writes dashboard.html ; open it in any browser (works offline, file://)
```

Use your own data: copy `config.example.yaml` to `config.yaml`, edit it, run
`python analyze.py config.yaml`.

## What you get
- **You vs. the index** — your value vs. the *same dated deposits* put into the
  benchmark (the fair comparison for irregular contributions), + working-capital
  step and deposit/withdrawal markers.
- **Money-flow waterfall** — start → +deposits → −withdrawals → +gains → end.
- **Returns by year** — TWR (how the picks did) vs. XIRR (what your dollars earned).
- **New money vs. appreciation**, **cash on sidelines**, **drawdown**.
- Account toggle (each account + combined). Self-contained ECharts (vendored).

## Determinism — reproduce byte-for-byte

This tool is built so **any machine or AI provider reproduces the exact same
output**. The guarantees:

- **No network at run time** — benchmark prices are read from the frozen
  `benchmark_prices.json` (public month-end data). Refresh it only via the
  optional `fetch_prices.py` (the one place that touches the network).
- **No system clock, no randomness** — the "generated" label is the config's
  `as_of`; iteration order is sorted; rounding is fixed; timestamps are UTC-pinned
  (no timezone drift); ECharts is a pinned vendored file.

Verify your run matches the reference example:

```bash
python analyze.py config.example.yaml
sha256sum dashboard.html
# compare against expected_output.sha256 (must match exactly)
```

Requirements: Python 3.8+, PyYAML. (Float math, `json` output, and `round()` are
stable across these; the vendored `echarts.min.js` is byte-pinned.)

## Files
| File | Role |
|---|---|
| `analyze.py` | engine — config + frozen prices → dashboard (deterministic) |
| `config.example.yaml` | hypothetical input; copy & edit for your own portfolio |
| `benchmark_prices.json` | **frozen** month-end benchmark prices (offline, public data) |
| `template.html`, `app.js` | dashboard shell + render layer |
| `echarts.min.js` | vendored chart library (pinned, inlined for offline use) |
| `fetch_prices.py` | optional — regenerate `benchmark_prices.json` from Yahoo (network) |
| `expected_output.sha256` | golden hash of the example `dashboard.html` |

## Input config (Mode A — values + flows)

```yaml
portfolio: { owner: "Jane Investor", as_of: "2025-12-31" }
benchmark: { primary: VOO, cash_rate_apy: 0.045 }
accounts:
  - id: brokerage
    type: taxable
    year_end: { 2019-12-31: 0, 2020-12-31: 32000, ... }   # market value per year end
    cash:     { 2020-12-31: 3000, ... }                   # uninvested cash (optional, for cash-drag)
    external_flows:                                        # deposits (+) / withdrawals (-), exact dates
      - { date: 2020-01-15, amount: 15000 }
```

The engine **derives** each year's investment gain = `end − start − net_flow`, so
you only supply values, cash, and dated flows.

> Mode B (auto-parse raw broker transaction/statement exports, plus a per-stock
> drilldown) is the planned extension — see issue #67.
