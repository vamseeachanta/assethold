# WRK-189-ext: HTML Report, UV Environment, Sectioned Data, Stock Comparison Design

## Context

The daily strategy tool works end-to-end (live run confirmed, 170 tests passing). Three enhancements are needed:

1. **UV environment** — system Python was used for the live run; the project already has `pyproject.toml` + `uv.lock` + `.venv` (Python 3.11). Switch canonical invocation to `uv run`.
2. **Sectioned HTML report** — current Markdown output mixes technical, insider, and fundamental signals. User wants them in separate sections with a summary at the top. Existing `PlotlyReportGenerator` at `assethold/src/assethold/modules/reporting/templates/plotly_report_template.py` establishes the styling convention to adopt (purple gradient header `#667eea → #764ba2`, stat cards, Plotly.js, vanilla CSS grid, no Bootstrap).
3. **Stock comparison** — design and partially implement so arbitrary tickers (not just owned positions) can be analysed and compared side-by-side.

User said "pick the best" — decision: **HTML becomes the primary output** (self-contained, interactive Plotly), Markdown is retained for git-diffable archival.

---

## Critical Files

| File | Role | Action |
|------|------|--------|
| `src/assethold/analysis/daily_strategy/html_report.py` | **NEW** — HTML report generator | Create |
| `src/assethold/analysis/daily_strategy/fetcher.py` | MarketSnapshot dataclass | Extend with 5 new fundamentals fields |
| `src/assethold/analysis/daily_strategy/__main__.py` | CLI entry | Add `--compare`, generate HTML, document `uv run` |
| `src/assethold/analysis/daily_strategy/loader.py` | Position / FidelityLoader | Add `ComparisonLoader` for watchlist tickers |
| `src/assethold/analysis/daily_strategy/__init__.py` | Package exports | Add new exports |
| `pyproject.toml` | Dependencies | Update `yfinance` version to `>=1.2.0` |
| `config/daily_strategy.yaml` | Config | Add `watchlist:` section for comparison tickers |
| `README.md` | Docs | Update with `uv sync && uv run` instructions |
| `tests/unit/analysis/daily_strategy/test_html_report.py` | **NEW** | Tests for HTML generator |
| `src/assethold/modules/reporting/templates/plotly_report_template.py` | Reference | Read-only — adopt its CSS/color conventions |

---

## Phase 1 — UV Environment

**Problem**: `pyproject.toml` pins `yfinance==0.2.57` but 1.2.0 is what works. `.venv` exists.

**Changes:**
1. Update `pyproject.toml`: change `yfinance==0.2.57` → `yfinance>=1.2.0`
2. Run `uv sync` to update `.venv` and `uv.lock`
3. README: replace `python -m assethold.analysis.daily_strategy` with:
   ```bash
   uv sync
   uv run python -m assethold.analysis.daily_strategy
   ```
4. All test invocations: `uv run python -m pytest ...`

**Verification**: `uv run python -c "import yfinance; print(yfinance.__version__)"` prints `1.2.x`.

---

## Phase 2 — Extend MarketSnapshot with Richer Fundamentals

Add 5 fields to `MarketSnapshot` dataclass in `fetcher.py`:

```python
forward_pe: Optional[float]      # forwardPE from yfinance info
dividend_yield: Optional[float]  # dividendYield (annualised %)
market_cap: Optional[float]      # marketCap in USD
beta: Optional[float]            # beta (market sensitivity)
analyst_rating: Optional[str]    # recommendationKey e.g. "buy", "hold"
```

Extract in `_fetch_info` using `_safe_float` / direct string read. No changes to signal engine (fundamentals section is display-only; P/E scoring remains deferred to v2).

---

## Phase 3 — HTML Report (Primary Output)

New file: `src/assethold/analysis/daily_strategy/html_report.py`

### Class: `DailyStrategyHtmlReport`

Self-contained HTML: all CSS inline, Plotly.js from CDN, no external dependencies.

**Report structure (top to bottom):**

```
┌─────────────────────────────────────────────────┐
│  HEADER  (purple gradient, date, portfolio $)   │
├─────────────────────────────────────────────────┤
│  1. EXECUTIVE SUMMARY                           │
│     Stat cards: Total Value | # Positions |     │
│     # BUILDs | # TRIMs | Biggest Change         │
│     Signal changes table (↑/↓ vs yesterday)    │
│     Action priority table (sorted by signal)   │
├─────────────────────────────────────────────────┤
│  2. TECHNICAL INDICATORS                        │
│     Table: RSI | SMA-50 Δ% | SMA-200 Δ% |      │
│            52w% | Trend badge                   │
│     Plotly bar: RSI by ticker (oversold band)   │
│     Plotly bar: % from SMA-50 by ticker         │
├─────────────────────────────────────────────────┤
│  3. INSIDER SENTIMENT                           │
│     Table: Trend | Buys | Sells | Net | Last    │
│     Trend badge coloring:                       │
│       BULLISH=green, BEARISH=red,               │
│       MIXED=amber, NEUTRAL/N/A=gray             │
├─────────────────────────────────────────────────┤
│  4. FUNDAMENTALS                                │
│     Table: P/E | Fwd P/E | P/B | Beta |        │
│            Div Yield | Analyst Rating           │
│     N/A shown where data unavailable            │
├─────────────────────────────────────────────────┤
│  5. PORTFOLIO BREAKDOWN (per-account)           │
│     Collapsible account sections                │
│     Plotly pie: weight distribution             │
├─────────────────────────────────────────────────┤
│  6. SIGNAL DETAILS (per-ticker deep-dive)       │
│     Cards: score gauge | price | rationale      │
│     Ordered: STRONG BUILD → STRONG TRIM         │
├─────────────────────────────────────────────────┤
│  FOOTER — methodology, data source disclaimer   │
└─────────────────────────────────────────────────┘
```

**Styling** (adopt from `plotly_report_template.py`):
- Header: `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
- Background: `#f5f7fa`
- Cards: white, `border-radius: 10px`, subtle shadow
- Stat card grid: `repeat(auto-fit, minmax(180px, 1fr))`
- Signal badge colors: green (BUILD), blue (HOLD), orange (TRIM), red (STRONG TRIM)
- Plotly template: `plotly_white`

**Output path**: `reports/daily-strategy/YYYY-MM-DD.html`

**`generate(signals, report_date, changes) -> str`** — returns full HTML string.
**`write(signals, report_date, changes) -> Path`** — renders and saves.

---

## Phase 4 — Stock Comparison Design + CLI

### Comparison Mode Design

Enables `--compare AAPL,MSFT,NVDA` to analyse and rank arbitrary tickers without owning them.

**`ComparisonLoader`** (new class in `loader.py`):
```python
def load_tickers(self, tickers: list[str]) -> list[Position]:
    # Returns synthetic Position objects:
    #   shares=0, tradeable=True, avg_cost_basis=None
    #   account="Watchlist", account_number=""
    # These are scored by SignalEngine with weight signal disabled
    # (portfolio_value=0 → weight sub-signal skipped automatically)
```

**Signal engine**: no changes needed — weight signal already skips when `portfolio_value=0`.

**HTML report comparison mode**:
- Replaces "Portfolio Breakdown" section with "Comparison Matrix"
- Shows all comparison tickers in a ranked table (score, signal, all sub-signals)
- Plotly radar/spider chart: one line per ticker across all sub-signal dimensions
- No per-account sections (no accounts for watchlist tickers)

**CLI flag**:
```bash
uv run python -m assethold.analysis.daily_strategy --compare AAPL,MSFT,NVDA
# OR mix portfolio + comparison:
uv run python -m assethold.analysis.daily_strategy --compare AAPL,MSFT
```

**Config** (`config/daily_strategy.yaml`):
```yaml
watchlist:
  - AAPL
  - MSFT
  - NVDA
```
Loaded automatically when `--compare` flag is absent but `watchlist:` is non-empty, so each daily run also benchmarks portfolio holdings against watchlist peers.

---

## Phase 5 — Tests

New: `tests/unit/analysis/daily_strategy/test_html_report.py`
- `test_generate_returns_html_string` — output starts with `<!DOCTYPE`
- `test_html_contains_all_sections` — checks for section headings
- `test_changes_section_present_when_provided`
- `test_changes_section_absent_when_none`
- `test_write_creates_html_file`
- `test_summary_shows_portfolio_value`
- `test_technical_section_shows_rsi`
- `test_insider_section_shows_trend`
- `test_fundamentals_section_shows_pe`

Update `test_fetcher.py` for new MarketSnapshot fields (forward_pe, dividend_yield, etc.).

Target: **185+ tests passing**.

---

## Verification

```bash
# 1. UV environment
uv sync
uv run python -c "import yfinance; print(yfinance.__version__)"

# 2. Full test suite
uv run python -m pytest tests/unit/analysis/daily_strategy/ -v --noconftest

# 3. Live run — generates both .md and .html
uv run python -m assethold.analysis.daily_strategy

# 4. Comparison run
uv run python -m assethold.analysis.daily_strategy --compare AAPL,MSFT

# 5. Verify HTML output
ls -la reports/daily-strategy/*.html
```

---

## Implementation Order

1. Phase 1: UV sync + pyproject.toml fix (5 min)
2. Phase 2: Extend MarketSnapshot (15 min)
3. Phase 3: `html_report.py` + tests (45 min) ← largest piece
4. Phase 4: `ComparisonLoader` + CLI `--compare` flag + config (20 min)
5. Phase 5: Wire `__main__.py` to generate HTML, update README
