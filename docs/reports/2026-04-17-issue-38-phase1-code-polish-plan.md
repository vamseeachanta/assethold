# Plan for #38: Phase 1 code polish — bundled cleanup

> **Status:** draft → plan-review after adversarial pass
> **Complexity:** T2 (bundle of 6 T1-sized mechanical items)
> **Date:** 2026-04-17
> **Issue:** https://github.com/vamseeachanta/assethold/issues/38
> **Review artifacts:** `docs/reports/reviews/2026-04-17-plan-38-{claude,codex}.md`

---

## Resource Intelligence Summary

### Existing repo code (evidence-based findings)

- **Found:** `src/assethold/modules/stocks/cache.py:17` — `TTL_OHLCV_INTRADAY = 15 * 60`. `ohlcv_ttl(market_hours_aware)` helper exists (landed in Phase 1). No regression test locks in the lazy-import invariant that the default path does not touch `assethold.utils.market_hours`.
- **Found:** `tests/unit/test_cache_ohlcv_ttl.py` — 39 lines. `import pytest` and `import assethold.modules.stocks.cache as cache_mod` are declared but unused (flake8/ruff would flag). Existing tests use `from assethold.modules.stocks.cache import ohlcv_ttl, TTL_OHLCV, TTL_OHLCV_INTRADAY`.
- **Found:** `tests/unit/signals/test_data_sources_market_hours.py:7` — `from pathlib import Path` unused (the `tmp_path` fixture already returns `Path`).
- **Found:** `src/assethold/analysis/daily_strategy/fetcher.py:185-195` — docstring on `_fetch_ohlcv` reads *"A 4-day freshness buffer covers weekends and market holidays"* with no mention of the `market_hours_aware=True` branch added in Phase 1. The 3-branch logic is present in the code below the docstring.
- **Found:** `src/assethold/analysis/daily_strategy/__main__.py:185-197` — 13-line `MarketDataFetcher(...)` construction with two nested `int(config.get("scoring", {}).get(...))` lookups and one short-circuit ternary. Readable now; one more knob would tip it into "hard to scan."
- **Found:** `src/assethold/utils/market_hours.py:63-96` — `next_open` and `next_close` share 14 lines of near-identical body: differ only in column name (`market_open` vs `market_close`) and error message.
- **Found:** `tests/integration/test_daily_strategy_intraday.py:48-65` — `test_no_intraday_flag_does_not_check_market_hours` runs the full `daily_strategy` pipeline with `timeout=300` and real yfinance fetches. Narrow assertion (`"next open" not in stderr`). Slow; no pytest marker.
- **Found (proven pattern from #39):** subprocess-isolated lazy-import test lands at `tests/unit/signals/test_watchlist_runner.py::test_default_construction_does_not_import_pandas_market_calendars`. The same pattern applies directly to `cache.ohlcv_ttl()` item 1.

### Documents consulted

- Issue #38 body — six items spelled out verbatim; each sourced from a specific Phase 1 code review (Tasks 2–6).
- `docs/reports/2026-04-17-session-exit-handoff-phase1-complete.md` §"Remaining work" — characterizes #38 as "half-session cleanup. Good warm-up work."
- #39 plan + commits `fd0bc33` / `3f5e81d` — established the subprocess-isolated lazy-import test pattern reused here for item 1.
- `pyproject.toml` — confirms Python `>=3.9`; `pytest-xdist` and `pytest-cov` available; no existing `@pytest.mark.slow` usage in the project (new marker will need registration in `pytest.ini`).

### Gaps identified

- No lazy-import regression test for `cache.ohlcv_ttl()` — item 1 closes this.
- No pytest marker `slow` registered — item 5 adds the registration + decorator.
- Stale docstring on `_fetch_ohlcv` misleads future readers — item 3 corrects.
- `_build_fetcher_kwargs` helper does not exist — item 4 creates.
- `_next_event(ts, column)` helper does not exist — item 6 creates.

Distinct sources: issue body (1) + 5 source files inspected with line-number citations (2) + #39 pattern (3) + pyproject/pytest config (4). Well above ≥3 minimum.

---

## Artifact Map

| Artifact | Path |
|---|---|
| This plan | `docs/reports/2026-04-17-issue-38-phase1-code-polish-plan.md` |
| Item 1 (new regression test) | `tests/unit/test_cache_ohlcv_ttl.py` (edit — append test) |
| Item 2 (unused imports removal) | `tests/unit/test_cache_ohlcv_ttl.py` + `tests/unit/signals/test_data_sources_market_hours.py` |
| Item 3 (docstring) | `src/assethold/analysis/daily_strategy/fetcher.py` |
| Item 4 (`_build_fetcher_kwargs`) | `src/assethold/analysis/daily_strategy/__main__.py` |
| Item 5 (slow marker) | `tests/integration/test_daily_strategy_intraday.py` + `pytest.ini` (register marker) |
| Item 6 (`_next_event` helper) | `src/assethold/utils/market_hours.py` |
| Plan review — Claude | `docs/reports/reviews/2026-04-17-plan-38-claude.md` |
| Plan review — Codex | `docs/reports/reviews/2026-04-17-plan-38-codex.md` |

---

## Deliverable

Six bundled cleanup changes to close Phase 1's deferred code-review backlog, with one new regression test, one docstring correction, two helper extractions, one unused-import sweep, and one slow-test marker registration. No new features; no behavior change in production code.

---

## Pseudocode / item-by-item plan

### Item 1 — Lazy-import regression test for `cache.ohlcv_ttl()`

Use the proven subprocess pattern from #39:

```python
# append to tests/unit/test_cache_ohlcv_ttl.py
def test_ohlcv_ttl_default_does_not_import_market_hours():
    """Default path (market_hours_aware=False) must not pull market_hours."""
    probe = (
        "import sys; "
        "from assethold.modules.stocks.cache import ohlcv_ttl; "
        "assert ohlcv_ttl() == 6 * 3600; "
        "print('assethold.utils.market_hours' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, f"probe stderr: {result.stderr}"
    assert result.stdout.strip() == "False"
```

The issue body proposed `sys.modules["assethold.utils.market_hours"] = None` monkeypatching — rejected here because (a) that pattern was explicitly flagged as unreliable in #39 adversarial review and (b) subprocess isolation is the known-good replacement.

### Item 2 — Remove unused imports

- `tests/unit/test_cache_ohlcv_ttl.py`: delete `import pytest` and `import assethold.modules.stocks.cache as cache_mod`.
- `tests/unit/signals/test_data_sources_market_hours.py`: delete `from pathlib import Path`.

Run `ruff check` on these files as verification step (or manually confirm via flake8/grep).

### Item 3 — Fix stale `_fetch_ohlcv` docstring

In `src/assethold/analysis/daily_strategy/fetcher.py`, append one sentence to the existing docstring:

```
When market_hours_aware=True is set on the fetcher, the buffer switches
to intraday_ttl_minutes during the NYSE regular session.
```

### Item 4 — Extract `_build_fetcher_kwargs(args, config)` helper

Before:

```python
fetcher = MarketDataFetcher(
    price_cache_ttl_hours=0 if args.no_cache else int(
        config.get("scoring", {}).get("price_cache_ttl_hours", 4)
    ),
    info_cache_ttl_hours=0 if args.no_cache else int(
        config.get("scoring", {}).get("info_cache_ttl_hours", 24)
    ),
    history_days=int(config.get("scoring", {}).get("sma_history_days", 252)),
    market_hours_aware=args.intraday,
    intraday_ttl_minutes=int(
        config.get("scoring", {}).get("intraday_ttl_minutes", 15)
    ),
)
```

After:

```python
def _build_fetcher_kwargs(args, config: dict) -> dict:
    scoring = config.get("scoring", {})
    return {
        "price_cache_ttl_hours": 0 if args.no_cache else int(scoring.get("price_cache_ttl_hours", 4)),
        "info_cache_ttl_hours": 0 if args.no_cache else int(scoring.get("info_cache_ttl_hours", 24)),
        "history_days": int(scoring.get("sma_history_days", 252)),
        "market_hours_aware": args.intraday,
        "intraday_ttl_minutes": int(scoring.get("intraday_ttl_minutes", 15)),
    }

# at call site:
fetcher = MarketDataFetcher(**_build_fetcher_kwargs(args, config))
```

### Item 5 — Mark slow integration test

Add to `pytest.ini`:

```ini
[pytest]
markers =
    slow: mark test as slow (skipped with -m "not slow")
    # ... any existing markers preserved
```

Decorate `test_no_intraday_flag_does_not_check_market_hours` with `@pytest.mark.slow`. Quick-mode runs can `pytest -m "not slow"`.

### Item 6 — Extract `_next_event(ts, column)` helper

```python
def _next_event(ts: Optional[datetime], column: str) -> datetime:
    """Return the next `column` ('market_open' or 'market_close') strictly after ts.

    Shared body of next_open and next_close. 14-day forward search; raises
    ValueError if no matching event is found.
    """
    et = _normalize(ts)
    cal = _get_calendar()
    schedule = cal.schedule(
        start_date=et.date(),
        end_date=(et + pd.Timedelta(days=14)).date(),
    )
    for _, row in schedule.iterrows():
        if row[column] > et:
            return row[column].tz_convert("America/New_York").to_pydatetime()
    raise ValueError(f"No NYSE {column} found within 14 days of {ts}")


def next_open(ts: Optional[datetime] = None) -> datetime:
    """Return the next NYSE regular-session opening strictly after ts."""
    return _next_event(ts, "market_open")


def next_close(ts: Optional[datetime] = None) -> datetime:
    """Return the next NYSE regular-session close strictly after ts."""
    return _next_event(ts, "market_close")
```

Existing `tests/unit/test_market_hours.py` tests (14 of them) continue to pass unchanged — the refactor preserves behavior.

---

## Files to Change

| Action | Path | Reason |
|---|---|---|
| Modify | `tests/unit/test_cache_ohlcv_ttl.py` | Item 1 (append subprocess regression test) + Item 2 (remove 2 unused imports) |
| Modify | `tests/unit/signals/test_data_sources_market_hours.py` | Item 2 (remove `from pathlib import Path`) |
| Modify | `src/assethold/analysis/daily_strategy/fetcher.py` | Item 3 (docstring append) |
| Modify | `src/assethold/analysis/daily_strategy/__main__.py` | Item 4 (extract `_build_fetcher_kwargs`) |
| Modify | `tests/integration/test_daily_strategy_intraday.py` | Item 5 (decorator) |
| Modify | `pytest.ini` | Item 5 (register `slow` marker) |
| Modify | `src/assethold/utils/market_hours.py` | Item 6 (extract `_next_event`) |

Total: 7 file edits, 0 new files.

---

## TDD Test List

| Test name | Item | What it verifies | Expected output |
|---|---|---|---|
| `test_ohlcv_ttl_default_does_not_import_market_hours` | 1 | Subprocess probe: default `ohlcv_ttl()` returns `TTL_OHLCV` and `assethold.utils.market_hours` not in `sys.modules` | stdout `"False"`; exit 0 |
| *(no new test — refactor-only for items 2, 3, 4, 6)* | — | Existing test suites continue to pass unchanged | 849+19 = 868 pass |
| `tests/unit/test_market_hours.py` regression | 6 | 14 existing tests of `next_open` / `next_close` pass after `_next_event` extraction | 14/14 |
| `tests/integration/test_daily_strategy_intraday.py::test_no_intraday_flag_does_not_check_market_hours` | 5 | Marked `@pytest.mark.slow`; `pytest -m "not slow"` skips it; default run still includes it | 1 skipped under `-m "not slow"`; 1 run under default |

Items 2, 3, 4, 6 are pure refactors — no new tests needed; existing tests are the regression guard.

---

## Acceptance Criteria

- [ ] `tests/unit/test_cache_ohlcv_ttl.py` gains 1 new subprocess test covering the lazy-import invariant; test passes
- [ ] `ruff check tests/unit/test_cache_ohlcv_ttl.py tests/unit/signals/test_data_sources_market_hours.py` is clean for unused imports
- [ ] `fetcher.py:_fetch_ohlcv` docstring mentions the `market_hours_aware=True` branch
- [ ] `__main__.py` has a named `_build_fetcher_kwargs(args, config)` helper; call site uses `**_build_fetcher_kwargs(...)`
- [ ] `pytest -m "not slow"` skips the slow integration test; default `pytest tests/integration/` still runs it
- [ ] `market_hours.py` has `_next_event` helper; `next_open` and `next_close` delegate to it in 1 line each
- [ ] Full baseline (868 from #39) remains green
- [ ] `python -m assethold.analysis.daily_strategy --help` output unchanged
- [ ] `ruff check src/ tests/` (or equivalent) shows no new warnings introduced
- [ ] Two adversarial review artifacts (Claude + Codex) each return APPROVE or MINOR (no MAJOR) before `status:plan-review` label

---

## Adversarial Review Summary

| Provider | Verdict | Key findings |
|---|---|---|
| Claude | PENDING | (populate after adversarial review) |
| Codex | PENDING | (populate after adversarial review) |

**Overall result:** PENDING — will be set after review wave.

---

## Risks and Open Questions

- **Risk (item 4):** Extracting `_build_fetcher_kwargs` into the CLI module works for one call site; if future code calls `MarketDataFetcher` from another module, the helper becomes private-to-CLI. Alternative: put helper in `fetcher.py` as a classmethod `MarketDataFetcher.build_kwargs(args, config)`. Plan defaults to **keep it module-private in `__main__.py`** because there is exactly one caller today; revisit if a second materializes.
- **Risk (item 5):** Adding `@pytest.mark.slow` changes default CI behavior only if CI uses `-m "not slow"`. The existing CI config (if any) must be inspected. Plan defaults to **only register and decorate**; does not add `-m "not slow"` to any CI step in this issue.
- **Risk (item 6):** Refactor could break the 14 existing `test_market_hours.py` tests if `_next_event` introduces a behavioral difference. Mitigation: run the full `test_market_hours.py` suite before and after; assert byte-for-byte same output (or same `APPROVE`/equality of returned datetimes).
- **Risk (item 1):** Subprocess test adds ~1s runtime per pytest invocation. Acceptable given the proven pattern from #39.
- **Open:** Should items land as one commit or six atomic commits? Plan defaults to **six atomic commits** (one per item) for easy revert + clearer git history. User may redirect at approval.

---

## Complexity: T2 (bundle of 6 T1 items)

**T2** — 7 file edits, 1 new test, ~40 LOC of refactor, 0 new modules. No architectural changes. One focused session (≤2 hours) post-approval. Each sub-item is individually T1.
