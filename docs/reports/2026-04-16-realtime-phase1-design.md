# Realtime Phase 1 — Market-Hours Awareness + Intraday TTL (Design)

**Date:** 2026-04-16
**Issue:** [#35](https://github.com/vamseeachanta/assethold/issues/35) (spun off from [#34](https://github.com/vamseeachanta/assethold/issues/34))
**Parent assessment:** `docs/reports/2026-04-16-realtime-feeds-assessment.md` §4 Phase 1
**Status:** Approved design — ready for implementation plan
**Brainstorming session:** 2026-04-16 (continuation of `assethold-followups` handoff)

---

## 1. Context

Today every consumer of price data inherits a 4–24 hour staleness window because cache TTLs are static (`TTL_OHLCV = 6 * 3600`) and the daily-strategy CLI has no concept of market hours. Phase 1 of the realtime-feeds initiative delivers ~6× freshness improvement during market hours by introducing a tiered TTL that drops to 15 minutes when the NYSE regular session is open. No provider commitment, no async/streaming, no scheduler — bounded executable scope, ~1–2 focused sessions.

The umbrella tracker (#34) stays open for Phases 2–4, which are blocked on open questions in the assessment doc §7.

---

## 2. Decisions resolved during brainstorming

These are the design choices the implementation MUST honor. Each is a deliberate selection from named alternatives; do not silently revisit during implementation.

| # | Question | Decision | Rationale |
|---|---|---|---|
| 1 | What does "market open" mean? | NYSE **regular session only** — 9:30am–16:00 ET, weekdays, NYSE-holiday-aware, half-day-aware (early close at 13:00 ET on known days) | Matches assessment §4; simplest semantics; matches what `yfinance` and Alpaca IEX free actually serve reliably |
| 2 | Scope of fetcher edits | Both `signals/data_sources.py` **and** `daily_strategy/fetcher.py` | Issue body lists only the former, but the daily-strategy CLI consumes `MarketDataFetcher`. Without wiring fetcher.py, `--intraday` does not affect the CLI's freshness. Issue-body gap acknowledged here. |
| 3 | `--intraday` outside market hours | **Fail loud** uniformly — weekend, NYSE holiday, before-bell, after-close, half-day-after-13:00 ET. Error must include `next_open` time | Handoff captures user preference: "fail loud (no silent skip)"; consistent UX across all closed states |
| 4 | `is_market_open(ts)` timezone contract | Accept aware OR naive `datetime`. Naive `ts` is interpreted as **UTC** (matches `datetime.utcnow()` semantics). `ts=None` defaults to `datetime.now(timezone.utc)`. Internal conversion to ET is hidden from the caller. | Doesn't break existing naive `datetime.now()` callers in the codebase; explicit and documented |
| 5 | Are `next_open` / `next_close` consumed in Phase 1? | **Yes** — used in the `--intraday` error message and available for log decoration | Listed in issue body; <10 LOC each as wrappers around `pandas_market_calendars` |
| 6 | Where does `intraday_ttl_minutes` live? | `config/daily_strategy.yaml` under `scoring:` alongside the existing `price_cache_ttl_hours` | Single source of truth; matches established config pattern |
| 7 | `market_hours_aware` default | **`False`** in both fetcher constructors | Backwards compat; the `--intraday` flag explicitly flips it on |
| 8 | Cache-layer routing strategy | Add a thin `cache.ohlcv_ttl(market_hours_aware: bool)` helper. `fetch_with_fallback` is unchanged — callers compute the effective TTL and pass it in. | Preserves the cache module's current purity ("disk caching layer" — no business policy); easier to test in isolation |
| 9 | Test scope | Unit tests for `market_hours.py`, `cache.ohlcv_ttl()`, `data_sources` constructor; one CLI integration test for `--intraday` on a known-closed time. **No live-network tests.** | Bounded; `pandas_market_calendars` is deterministic so monkeypatching is rarely needed |
| 10 | `pandas_market_calendars` import failure | Hard fail when `market_hours_aware=True` was explicitly requested. When the flag is `False` (default), the dep is never touched. | Explicit flag means explicit dep; respects YAGNI for the default path |

---

## 3. Architecture

One new module + light edits to four existing files + one config file + `pyproject.toml`. No new packages or sub-packages introduced.

```
src/assethold/
├── utils/
│   └── market_hours.py                        [NEW]
│       ├─ is_market_open(ts: datetime|None=None) -> bool
│       ├─ next_open(ts: datetime|None=None)  -> datetime  (TZ-aware, ET)
│       ├─ next_close(ts: datetime|None=None) -> datetime  (TZ-aware, ET)
│       └─ wraps pandas_market_calendars.get_calendar("XNYS")
│
├── modules/stocks/cache.py                    [EDIT]
│   ├─ + TTL_OHLCV_INTRADAY = 15 * 60
│   └─ + ohlcv_ttl(market_hours_aware: bool = False) -> int
│
├── signals/data_sources.py                    [EDIT]
│   └─ StockDataSource.__init__:
│       + market_hours_aware: bool = False
│       + intraday_ttl_minutes: int = 15
│       _is_cache_valid(): TTL chosen per-call via market_hours.is_market_open()
│
└── analysis/daily_strategy/
    ├── fetcher.py                             [EDIT — not in original issue body]
    │   └─ MarketDataFetcher.__init__:
    │       + market_hours_aware: bool = False
    │       + intraday_ttl_minutes: int = 15
    │
    └── __main__.py                            [EDIT]
        └─ + --intraday flag
            Pre-flight: if --intraday and not is_market_open():
                        print error w/ next_open(), return 1
            Else: pass market_hours_aware=True to MarketDataFetcher

config/daily_strategy.yaml                     [EDIT]
    └─ scoring.intraday_ttl_minutes: 15

pyproject.toml                                 [EDIT]
    └─ + pandas_market_calendars  (MIT, well-maintained)
```

### Component contracts

**`utils/market_hours.py`** — pure module, no I/O beyond what `pandas_market_calendars` does internally (it ships with embedded holiday calendars, no network calls).

```python
def is_market_open(ts: datetime | None = None) -> bool:
    """Return True iff NYSE regular session is open at `ts`.

    Regular session = 9:30am–16:00 ET, weekdays, excluding NYSE holidays.
    Half-day closes are honored via the calendar's per-day schedule
    (e.g. Black Friday and Christmas Eve typically close at 13:00 ET).

    Parameters
    ----------
    ts : datetime, optional
        Timestamp to check. May be timezone-aware (any zone) or naive.
        If naive, interpreted as UTC. If None, uses datetime.now(timezone.utc).

    Returns
    -------
    bool
    """
```

`next_open` / `next_close` mirror the same `ts` contract and return TZ-aware ET datetimes.

**`modules/stocks/cache.py`** — adds:

```python
TTL_OHLCV_INTRADAY = 15 * 60  # 15 min, used during NYSE regular session

def ohlcv_ttl(market_hours_aware: bool = False) -> int:
    """Return the OHLCV cache TTL in seconds.

    When market_hours_aware is True AND market_hours.is_market_open() is True,
    returns TTL_OHLCV_INTRADAY (15 min). Otherwise returns TTL_OHLCV (6 h).

    The static TTL_OHLCV path does NOT import market_hours, so the
    pandas_market_calendars dep is only required when the caller opts in.
    """
```

**`signals/data_sources.py`** — `StockDataSource.__init__` gains two kwargs with backwards-compatible defaults. `_is_cache_valid` recomputes the effective TTL on each call (live evaluation, not init-time snapshot) so a cache that was valid pre-9:30am becomes invalid at 9:31am once the intraday window kicks in.

**`daily_strategy/fetcher.py`** — `MarketDataFetcher.__init__` mirrors the same two kwargs. The class already accepts `price_cache_ttl_hours` and `info_cache_ttl_hours`; the new kwargs are additive. **Discovery during plan-writing:** `_fetch_ohlcv` (lines 175–223) does NOT route through `StockDataSource`'s TTL cache — it has its own 4-day-buffer check (`if last_date >= today - timedelta(days=4): return existing`) and calls `self._source.fetch(use_cache=False)`. This buffer must also honor intraday mode: when `market_hours_aware=True` and `is_market_open()` is True, the freshness check switches to `(now - mtime) < intraday_ttl_minutes`. Otherwise the legacy 4-day buffer applies. Without this change, `--intraday` is cosmetic for the daily-strategy CLI's OHLCV path. ~10 additional LOC.

**`daily_strategy/__main__.py`** — the `--intraday` flag is opt-in. Without it, current behavior is preserved exactly (no TZ awareness, no `pandas_market_calendars` import).

---

## 4. Data flow

### Happy path: `--intraday` on Tuesday 2026-04-21 at 10:00am ET

```
1. CLI: argparse sees --intraday → args.intraday = True
2. CLI pre-flight: market_hours.is_market_open() → True
                   → no fail-loud, proceed
3. CLI constructs: MarketDataFetcher(market_hours_aware=True,
                                     intraday_ttl_minutes=15,
                                     price_cache_ttl_hours=4)
4. For each ticker, fetcher computes effective TTL:
       cache.ohlcv_ttl(market_hours_aware=True) → 900 sec (intraday)
5. fetch_with_fallback(key, ttl=900, primary_fn, fallback_fn) → DataFrame
6. Report renders as usual
```

### Fail-loud path: `--intraday` on Sunday 2026-04-19 at 15:00 ET

```
1. CLI: args.intraday = True
2. CLI pre-flight: market_hours.is_market_open() → False
3. CLI: next_open_ts = market_hours.next_open()   → 2026-04-20 09:30 ET
4. CLI: print to stderr:
       "ERROR: market is closed. Next open: 2026-04-20 09:30 ET"
5. CLI: return 1  (no fetch attempted, no cache touched)
```

### Default path (unchanged from today): no `--intraday` flag

```
1. CLI: args.intraday = False
2. CLI constructs: MarketDataFetcher(market_hours_aware=False, ...)
3. cache.ohlcv_ttl(False) → TTL_OHLCV (6 h) — the legacy constant
4. market_hours module is never imported; pandas_market_calendars not loaded
```

---

## 5. Error handling

| Condition | Behavior |
|---|---|
| `--intraday` outside regular session | `print("ERROR: market is closed. Next open: <ts ET>", file=sys.stderr); return 1` |
| `pandas_market_calendars` import fails AND `market_hours_aware=True` was explicitly requested | Raise `ImportError` with installation hint at first call to `is_market_open()` |
| `pandas_market_calendars` import fails AND `market_hours_aware=False` (default) | Module is never imported. No error. |
| `is_market_open(ts)` called with `ts` outside the calendar's known range (e.g., 2050-01-01) | Raise `ValueError`. Do NOT silently return False. |
| `next_open(ts)` called when `ts` is exactly at the bell (9:30:00.000 ET) | Returns the *next* open after `ts`. Boundary case test required. |
| `--intraday` combined with `--no-cache` | Both flags honored. `--no-cache` wins (TTL=0); the `--intraday` pre-flight still runs (fails loud if market closed). |
| `--intraday` combined with `--date <past-date>` | The `--date` override is used for *report date*, not for cache freshness. Pre-flight still uses real wall-clock time. Document this in CLI help. |

---

## 6. Testing

Per the handoff gotcha, all tests run via `.venv/bin/python -m pytest tests/` (10s feedback) — not `uv run pytest` (5–15 min).

| Test file | Coverage |
|---|---|
| `tests/unit/test_market_hours.py` | • Tuesday 10:00am ET → True<br>• Tuesday 8:00am ET (pre-market) → False<br>• Tuesday 17:00 ET (after-hours) → False<br>• Saturday 12:00pm ET → False<br>• Sunday 12:00pm ET → False<br>• Monday 25 May 2026 (Memorial Day, full closure) at 10:00am ET → False<br>• Friday 27 Nov 2026 (Black Friday, early close) at 12:00pm ET → True<br>• Friday 27 Nov 2026 at 14:00 ET → False (early close honored)<br>• Naive ts treated as UTC<br>• Aware ts in PST converted correctly to ET<br>• `next_open` / `next_close` return TZ-aware ET datetimes<br>• `next_open` at the bell (boundary) returns the *next* open<br>• Out-of-range `ts` raises `ValueError` |
| `tests/unit/test_cache_ohlcv_ttl.py` | • `ohlcv_ttl(False) == TTL_OHLCV` (always)<br>• `ohlcv_ttl(True)` returns `TTL_OHLCV_INTRADAY` when `is_market_open` monkeypatched True<br>• `ohlcv_ttl(True)` returns `TTL_OHLCV` when `is_market_open` monkeypatched False |
| `tests/unit/signals/test_data_sources_market_hours.py` | • Constructor accepts `market_hours_aware` and `intraday_ttl_minutes` kwargs with documented defaults<br>• `_is_cache_valid()` uses 15-min window when aware+open, 24h otherwise (monkeypatch `is_market_open`)<br>• Default-constructed instance behaves identically to today (no behavior change) |
| `tests/integration/test_daily_strategy_intraday.py` | • `python -m assethold.analysis.daily_strategy --intraday --date 2026-04-19` (Sunday) → exit 1, stderr contains "next open"<br>• Without `--intraday`, same Sunday invocation runs to completion (legacy behavior preserved) |

**No live-network tests.** **No mocked-behavior tests** (per repo CLAUDE.md). Where monkeypatching is used, it's confined to swapping the deterministic `is_market_open` return value, not faking provider responses.

**Suite size impact:** ~25–35 new tests. Suite goes from 819 → ~845–855.

---

## 7. Out of scope (deferred to follow-up issues)

- **Pre-market / after-hours support** — Phase 1.5 if user demand emerges. `pandas_market_calendars` exposes `pre`/`post` columns; trivial to add later.
- **Streaming WebSocket** — Phase 3 of #34.
- **Scheduler daemon (`assethold watch`)** — Phase 2 of #34.
- **Wiring `market_hours_aware` into other consumers** — `signals/alert_engine.py`, `signals/trend_detector.py`, `signals/dashboard.py`. These are separate code paths and should land as their own follow-ups once Phase 1 proves the pattern.
- **Configurable bell buffer** (e.g., open 15 min before bell to catch opening auction) — file as Phase 1.5 if needed.
- **Cache invalidation across DST transitions** — `pandas_market_calendars` handles ET DST internally; no special handling required at our layer.

---

## 8. Implementation notes for the planner

When the writing-plans skill picks this up, the natural task decomposition is:

1. **Add dependency** — `pandas_market_calendars` to `pyproject.toml`; verify `uv sync` resolves cleanly. Test: import succeeds in `.venv`.
2. **Create `utils/market_hours.py`** with the three functions + docstrings. **TDD:** write `tests/unit/test_market_hours.py` first (red), then implement (green).
3. **Extend `cache.py`** with `TTL_OHLCV_INTRADAY` and `ohlcv_ttl()`. **TDD:** write `tests/unit/test_cache_ohlcv_ttl.py` first.
4. **Extend `signals/data_sources.py`** constructor + `_is_cache_valid`. **TDD:** write the data-sources test first.
5. **Extend `daily_strategy/fetcher.py`** constructor (mirror of step 4) AND `_fetch_ohlcv` freshness check (the 4-day-buffer block at lines 191–198 must consult `market_hours.is_market_open()` and switch to mtime-vs-intraday-TTL when aware+open). Tests for the existing `MarketDataFetcher` should not regress; add focused new tests for both the constructor kwargs and the buffer-switching behavior.
6. **Extend `daily_strategy/__main__.py`** — `--intraday` flag, pre-flight, threading to fetcher. Update CLI help docstring.
7. **Update `config/daily_strategy.yaml`** — add `intraday_ttl_minutes: 15`. Add a YAML comment cross-referencing the spec.
8. **Add the integration test** for the `--intraday`-on-Sunday fail-loud behavior.

Each step is its own commit. Prefer running the focused test file after each step (`.venv/bin/python -m pytest tests/unit/test_market_hours.py -v`) for fast feedback; full suite at the end.

---

## 9. Acceptance criteria (from issue + brainstorming)

The implementation is done when:

- [ ] `is_market_open()` returns correct state for: NYSE regular hours, US holidays from `pandas_market_calendars`'s embedded calendar, weekends, half-days
- [ ] `cache.ohlcv_ttl(True)` drops to 900 seconds during regular session, stays at 21600 outside
- [ ] `python -m assethold.analysis.daily_strategy --intraday` succeeds on a weekday at 10am ET
- [ ] Same command fails loud on a Sunday at 3am with a `next open` message in stderr
- [ ] Default invocation (no `--intraday`) is byte-identical to today's behavior — no `pandas_market_calendars` import, no behavior change
- [ ] Test suite is green (`.venv/bin/python -m pytest tests/` exits 0). Suite size grew by ~25–35 tests.
- [ ] No new `# TODO` markers introduced
- [ ] All four file edits + the new module + the new tests + the YAML update + the `pyproject.toml` update land as separate atomic commits with descriptive messages

---

## 10. References

- Issue: https://github.com/vamseeachanta/assethold/issues/35
- Umbrella tracker: https://github.com/vamseeachanta/assethold/issues/34
- Assessment doc: `docs/reports/2026-04-16-realtime-feeds-assessment.md`
- Handoff doc: `docs/reports/2026-04-16-session-exit-handoff-assethold-followups.md`
- `pandas_market_calendars` docs: https://pandas-market-calendars.readthedocs.io/
