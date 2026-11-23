# Real-Time Stock Price Feeds — Assessment

**Date:** 2026-04-16
**Issue:** #34
**Status:** Assessment (no implementation)
**Scope:** Identify providers, quantify phase effort, surface design decisions needed before Phase 1 starts.

---

## 1. Current State (grounded in repo, not assumption)

| Setting | Value | Location |
|---|---|---|
| `price_cache_ttl_hours` | 4h | `config/daily_strategy.yaml:65` |
| OHLCV TTL constant | 6h (`TTL_OHLCV`) | `src/assethold/modules/stocks/cache.py:16` |
| Options TTL | 4h | `cache.py:19` |
| Insider TTL | 7d | `cache.py:18` |
| Institutions TTL | 30d | `cache.py:20` |
| `monitoring_frequency` | `daily` / `hourly` fields exist — **no scheduler enforces them** | `config/stocks/watchlist.yml:10,18,…` |
| Fetch mode | 100% synchronous polling (`yfinance.Ticker.history`, finnhub REST) | `signals/data_sources.py`, `modules/stocks/providers/finnhub_provider.py` |
| Async/await | Not used anywhere in the price-data path | repo-wide grep |
| Market-hours gating | None — fetches run at any time | `signals/data_sources.py:fetch` |

**Net:** every price consumer inherits a 4–24h staleness window, and the watchlist has declared-but-unenforced frequency fields. The issue body's freshness audit is accurate.

## 2. Per-Consumer Freshness Needs (ranked by value of sub-hour data)

| Consumer | Where | Sub-hour data matters because… | Realistic target |
|---|---|---|---|
| `alert_engine` | `signals/alert_engine.py` | Missed intraday breakouts = missed trades | 5–15 min during market hours |
| `trend_detector` | `signals/trend_detector.py` | Volume spikes, S/R breaks are intraday-defined | 5–15 min |
| `daily_strategy/signals` | `analysis/daily_strategy/signals.py` | RSI/SMA on 4h-stale close = compounded lag | 15–30 min (the "daily" framing already implies a grace period) |
| `portfolio/allocation` | `portfolio/sector_tracker.py` | Weight drift detection; intraday not critical | 30–60 min |
| `options/covered_call` | `options/covered_call.py` | Greeks on stale underlying → wrong recommendations | Near-realtime when user is evaluating a trade, batch otherwise |
| `risk_metrics` | `risk_metrics.py` | VaR/Sharpe are historical metrics — intraday adds noise > signal | EOD is fine |
| `dashboard` | `signals/dashboard.py` | User-facing — freshness = UX | 15 min |
| `insider_tracker` | `signals/insider_tracker.py` | SEC filings lag by days inherently | 7d is correct |

**Takeaway:** **not every module wants realtime.** Only `alert_engine`, `trend_detector`, and `covered_call` (when active) have strong business cases for sub-15-minute data. The rest work fine with 15–60 min TTL. This argues for a tiered approach, not a wholesale streaming migration.

## 3. Provider Comparison

Pricing and features below reflect public provider documentation at time of writing; verify against each provider's current plan page before committing.

| Provider | Real-time delivery | Free tier | Paid entry | Python SDK | Notes |
|---|---|---|---|---|---|
| **Alpaca Markets** | WebSocket stream (IEX) + REST | Yes — IEX feed, paper trading, 200 req/min | ~$9/mo individual → SIP feed | `alpaca-py` | **Best free-tier WS**. IEX-only on free (partial book) but sufficient for quote/trade streams. Brokerage account required (free) but no trading needed. |
| **Finnhub** | WebSocket stream | REST only on free (60 req/min); limited symbols | ~$50/mo adds WebSocket + fundamentals | `finnhub-python` (already installed) | Already integrated as fallback. Cheapest "upgrade in place". Non-US coverage is a plus. |
| **Polygon.io** | WebSocket + REST | Delayed data + 5 req/min | ~$29/mo Stocks Starter → real-time | `polygon-api-client` | Best historical depth. Real-time tier is ~$99/mo — price-sensitive for individual use. |
| **Yahoo Finance (yfinance)** | None | Free, unofficial scraping | N/A | `yfinance` (already installed) | 15-min delayed in practice; no WebSocket. Subject to TOS enforcement shifts — cannot build production realtime on this. |
| **Interactive Brokers** | TWS API streaming | Free with funded brokerage account | Included | `ib_insync`, `ibapi` | Requires running TWS/Gateway desktop app. Great data if you already trade with IBKR. High operational overhead for non-customers. |
| **Tradier** | WebSocket | Delayed on sandbox | ~$10/mo brokerage adds real-time | `tradier-python` | Niche — worth considering if options-chain streaming becomes a priority. |
| **IEX Cloud** | — | **Shut down 2024** | N/A | N/A | Formerly popular in assethold's peer repos; no longer an option. |

### Recommendation

For this repo's scale (single-user, daily-strategy-driven, occasional intraday monitoring):

- **First choice: Alpaca free tier** — IEX-feed WebSocket is free, the `alpaca-py` SDK is current, brokerage signup is free and doesn't require funding. Gets us streaming quotes without any paid commitment, and opens the door to paper-trading the signals later.
- **Second choice: Finnhub paid (~$50/mo)** — lowest-friction upgrade since the code already has a `finnhub_provider.py` fallback. Adds WebSocket + better fundamentals. Justified if Alpaca's IEX-only coverage turns out to miss needed tickers.
- **Avoid on the first pass:** Polygon ($$$ for real-time), IBKR (ops overhead), Tradier (narrow fit).

## 4. Phase Effort — Quantified

The issue body lists four phases. Here is the effort breakdown I'd expect, with the concrete design decisions each phase forces.

### Phase 1 — Market-hours awareness + shorter intraday TTLs

**Effort:** 1–2 focused sessions.
**Files touched:** ~4 new, ~3 modified.

- New: `src/assethold/utils/market_hours.py` with `is_market_open(ts)`, `next_open(ts)`, `next_close(ts)`. Use `pandas_market_calendars` (already well-maintained, MIT-licensed) rather than hand-rolling NYSE holidays.
- Modify: `signals/data_sources.py` to accept a `market_hours_aware: bool` constructor flag. When true, TTL drops to `intraday_ttl_minutes` during market hours, uses `cache_ttl_hours` otherwise.
- Modify: `modules/stocks/cache.py` to add `TTL_OHLCV_INTRADAY = 15 * 60` constant and route through `market_hours.is_market_open()`.
- Modify: `analysis/daily_strategy/__main__.py` to add `--intraday` CLI flag that overrides cache TTLs and skips if market is closed.

**Decisions needed:**
- Intraday TTL — 5, 10, or 15 min? (Recommend **15 min** to keep provider quota low on free tiers.)
- Add `pandas_market_calendars` dependency, or hand-roll a small NYSE calendar? (Recommend **dependency** — holidays drift yearly.)
- Should `--intraday` fail loud or silently skip when market is closed? (Recommend **loud** — matches user's preference for explicit behavior over shortcuts.)

### Phase 2 — Scheduled intraday monitoring

**Effort:** 3–5 sessions.
**Major new component:** a scheduler daemon.

- Options: **APScheduler** (lightweight, in-process, good for single-user), **cron** (ops-minimal but loses state), **systemd timer** (Linux-native). Recommend **APScheduler** — it can live inside a long-running `assethold watch` command, integrates cleanly with the existing synchronous fetchers, and doesn't require root.
- Wire `watchlist.monitoring_frequency: hourly` → APScheduler job that calls `alert_engine.run(watchlist)` every N minutes during market hours.
- Alert dispatch: **blocked on #23 (WhatsApp) and #24 (market disruption monitor)**. Until one of those lands, alerts accumulate in `data/alerts/YYYY-MM-DD.jsonl`. That's usable but passive.

**Decisions needed:**
- Daemon lifecycle — systemd unit, `screen`/`tmux`, or `nohup` background? (Recommend **systemd user unit** on Linux; document a tmux fallback.)
- Alert persistence format — JSONL (grep-friendly), SQLite (queryable), or both? (Recommend **JSONL first**; promote to SQLite only if alert volume justifies.)
- Dispatch channel priority — email (easiest), WhatsApp (#23 scope), Discord/Slack (ops-minimal webhook)? (Recommend **email + webhook** as the v1 dispatch surface so this phase isn't hard-blocked on #23.)

### Phase 3 — Streaming price feeds (WebSocket)

**Effort:** 5–8 sessions. Biggest conceptual lift in the codebase — introduces **async** for the first time.

**New architecture component:** a streaming consumer that subscribes to the provider WebSocket, buffers ticks, and re-invokes signal detectors on a throttle.

```
WebSocket tick ─→ RingBuffer(ticker, 1000 ticks)
                      │
                      └─→ on_tick_batch (every 5s or N ticks):
                             ├─ update indicators (RSI, SMA, etc.)
                             ├─ run trend_detector on sliding window
                             └─ publish AlertEvent to dispatch bus
```

- Dependency: `alpaca-py[asyncio]` or `finnhub-python` (both support asyncio WebSockets).
- **New module boundary:** `signals/streaming/` with `consumer.py`, `buffer.py`, `dispatcher.py`. Keeps async scope contained; the rest of the repo stays synchronous.
- Indicator recomputation: most current indicators (`calculate_sma`, `calculate_rsi` in `signals/indicators.py`) are pure-function-on-DataFrame, so they work fine on a rolling window. No refactor needed for them.
- Trend detectors (`detect_volume_spike`, `detect_ma_crossover`) also work on a window — they just need a "last-evaluated" marker so events aren't re-emitted each tick.

**Decisions needed:**
- Async scope — keep it confined to `signals/streaming/` and bridge via a sync queue, or go async end-to-end? (Recommend **confined** — a repo-wide async migration is a massive undertaking for modest gain.)
- Event bus — in-process queue, Redis pub/sub, or disk-backed (e.g. `sqlite-queue`)? (Recommend **in-process queue** for single-user; defer Redis until/unless a second consumer emerges.)
- Rate limiting — respect provider WebSocket message quotas. Alpaca IEX free tier is generous; Finnhub basic has limits. Need per-provider throttle config.
- Failure mode — if the WebSocket drops, fall back to REST polling at intraday TTL, or halt? (Recommend **fall back** — graceful degradation.)

### Phase 4 — Real-time risk dashboard

**Effort:** 4–6 sessions.
**Depends on Phase 3.**

- Plotly Dash already present in dependencies (`dash-3.0.4` in test plugins). Live-update via `dcc.Interval` polling the in-process event bus.
- Rolling VaR/CVaR on tick buffer — existing `risk_metrics.py` functions are vectorized, so the only new code is the "evaluate on window" glue.
- Circuit-breaker detection is a trend_detector extension (another variant on `detect_volume_spike`).

**Decisions needed:**
- Deployment — local-only `uv run dash`, behind reverse proxy, or container? (Depends on who views it — probably local-only.)
- Persistence — should the dashboard remember state across restarts, or is ephemeral OK? (Recommend **ephemeral** unless there's a specific need.)

## 5. Gaps in the Issue Body That Need Closing

1. **"Streaming data source"** — which provider? The issue doesn't commit. See §3 recommendation.
2. **"No async/await patterns"** — confirmed repo-wide. The architectural choice in Phase 3 (confined async vs end-to-end) is the single biggest open decision.
3. **"No message bus"** — agree, but in-process is likely sufficient.
4. **"No scheduler"** — APScheduler recommended above.
5. **"No market hours awareness"** — `pandas_market_calendars` handles this in <10 lines; see Phase 1.
6. **"No rate limit intelligence"** — punt to the provider SDK layer (Alpaca/Finnhub SDKs handle this internally).

## 6. Recommended Immediate Next Steps

1. **Start Phase 1 — standalone** (no external dependencies, no provider commitment). Gives 6× freshness improvement during market hours for one session of effort.
2. **Spike Alpaca free-tier WebSocket** — 2-hour timebox. Verify IEX feed covers the current watchlist tickers (assethold holds mostly US-listed equities). If yes, Phase 3 has a concrete, zero-cost data source.
3. **Defer Phases 2–4** until Phase 1 is landed and the Alpaca spike either succeeds or pushes us to Finnhub-paid.
4. **Open sub-issues** for each phase to keep #34 as the umbrella tracker.

## 7. Open Questions for the User

| Q | Why it matters |
|---|---|
| Is this single-user home use, or is a small team watching alerts? | Determines whether in-process queue is enough (§ Phase 3 decisions). |
| Is $50/mo for a data feed acceptable if Alpaca IEX isn't sufficient? | Caps provider choice. |
| Do you want realtime in `options/covered_call`, or is batch-on-demand OK? | Whether options-chain streaming goes into Phase 3 scope. |
| Target a Linux-only daemon or keep cross-platform? | APScheduler + systemd unit vs. platform-agnostic tmux wrapper. |

## 8. Non-Goals for This Assessment

- No code written; no new dependencies added.
- No new issues opened — recommend user opens sub-issues per phase when ready.
- No provider account signups triggered.
