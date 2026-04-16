# StockHoldAnalysis

Stock analysis, logic and guidance for long-term holding of a stock market asset trading on US stock exchanges i.e. Nasdaq etc.

Helps manage a stock as a stand-alone portfolio

# Summary


# Usage

See test file for example ticker, [test file](https://github.com/samdansk2/assethold/blob/master/src/assethold/tests/test_stock_visualization_for_ticker_text_area.py)

Analysis output is: 
https://github.com/samdansk2/assethold/blob/master/docs/2022-11-26_RIG_Analysis.png


See a [test file](https://github.com/samdansk2/assethold/blob/master/src/assethold/tests/test_all_analysis_xom.py) to see how to perform analysis




## Technical Details

Mapping Dashboard UI to the financial analysis

| Analysis     | Code class | Code object   | Current Status | Description | 
|----------|------------|---------------|----------------|-----------|
| Insider <br> Insider Cost and Volumes | fc.fanalysis | insider_df_buy <br> insider_df_sell | done | - [x] ok?
| Insider <br> Relation | fc.fanalysis | insider_analysis_by_relation_df | done | - [x] ok?
| Insider <br> Timeline | fc.fanalysis | insider_analysis_by_timeline_df | done | - [x] ok?
| Insider <br> Relative Buy | fc.fanalysis | insider_df_buy | done | - [x] ok?
| Insider <br> Relative Sell | fc.fanalysis | insider_df_sell | done | - [x] ok?
| Institution <br> Institution | fc.fanalysis | df_institutional_holders | done | - [x] ok?
| Price <br> Price | fc.fanalysis | ta | done | - [x] ok?
| Technical <br> Volume | fc.fanalysis | ta | done | - [x] ok?
| Technical <br> cfm | fc.fanalysis | ta | done | - [x] ok?
| Technical <br> eom | fc.fanalysis | ta | done | - [x] ok?
| Technical <br> wt_price | fc.fanalysis | ta | done | - [x] ok?
| Technical <br> volatility | fc.fanalysis | ta | done | - [x] ok?
| Technical <br> volatility_hi_low | fc.fanalysis | ta | done | - [x] ok?
| Technical <br> ulcer | fc.fanalysis | ta | done | - [x] ok?
| Technical <br> strength | fc.fanalysis | ta | done | - [x] ok?
| Option <br> Call | fc.fanalysis | df_call_analysis | done | - [x] ok?
| Option <br> Put | fc.fanalysis | TBA | done | - [x] ok?

## Daily Portfolio Strategy

Produces a daily Build/Hold/Trim recommendation for each position in your Fidelity portfolio.

### Prerequisites

```bash
# Install dependencies via uv (recommended)
uv sync
```

### Quick start

```bash
# Run from the assethold repo root — writes Markdown + HTML to reports/daily-strategy/
uv run python -m assethold.analysis.daily_strategy

# Print terminal summary only (no files written)
uv run python -m assethold.analysis.daily_strategy --no-write

# Compare arbitrary tickers alongside portfolio positions
uv run python -m assethold.analysis.daily_strategy --compare AAPL,MSFT,NVDA

# Use a custom config file
uv run python -m assethold.analysis.daily_strategy --config /path/to/daily_strategy.yaml
```

Reports are written in two formats:
- `reports/daily-strategy/YYYY-MM-DD.html` — **primary**: interactive Plotly charts, sectioned layout
- `reports/daily-strategy/YYYY-MM-DD.md` — archival Markdown for git diffing

### How to read the report

| Signal | Score | Meaning |
|--------|-------|---------|
| STRONG BUILD ▲▲ | > 0.50 | High conviction buy opportunity |
| BUILD ▲ | 0.20 – 0.50 | Moderate buying opportunity |
| HOLD — | ±0.20 | No clear action needed |
| TRIM ▼ | -0.50 – -0.20 | Consider reducing position |
| STRONG TRIM ▼▼ | < -0.50 | Strong case to reduce |

### Signals used (weighted composite)

| Sub-signal | Weight | Logic |
|-----------|--------|-------|
| RSI momentum | 25% | RSI < 30 → bullish; RSI > 70 → bearish |
| 52-week position | 20% | Near 52w low → bullish; near high → bearish |
| Price vs SMA-50 | 20% | Below SMA-50 → bullish |
| Price vs SMA-200 | 15% | Below SMA-200 → bullish |
| Insider trend (90d) | 10% | Open-market buys → bullish; sells → bearish |
| Portfolio weight | 10% | Drift from target triggers build/trim |

### Position modes (configured in `config/daily_strategy.yaml`)

- **managed** — full signal range (e.g. BRKB, VOO with 25% target weight)
- **trim_only** — score clamped to ≤ 0; build signals suppressed (e.g. XOM, RIG)

### Data sources

- **Portfolio holdings**: reconstructed from Fidelity transaction CSVs (net shares per position)
- **Market data**: yfinance (price, RSI-14, SMA-50/200, 52-week range, P/E, P/B)
- **Insider activity**: yfinance SEC Form 4 filings (open-market buys/sells, 90-day window)
- All data is cached locally (OHLCV: 4h TTL; fundamentals/insider: 24h TTL)

### Scheduling (cron example)

```cron
# Run daily at 6:30 PM ET (after US market close)
30 18 * * 1-5 cd /path/to/assethold && uv run python -m assethold.analysis.daily_strategy
```

---

## Debt

Library TODO list to keep track of ideas.

**TODO**

- Add summary for all key analysis to help make faster decisions.
- Add insider ranking for relative comparison between tickers
- Troubleshoot SEC data import. Advise users to put appropriate headers to avoid lock-out by SEC websites
- Add Logic Flowchart

## References

https://www.lynalden.com/covered-calls/

Getting into and out of stocks:
https://www.marketwatch.com/story/plan-now-when-to-get-back-into-stocks-11657920632
