# Plan for #38: Phase 1 code polish — bundled cleanup

> **Status:** plan-review (v2 after Claude+Codex MAJOR findings)
> **Complexity:** T2 (bundle of 6 T1-sized mechanical items)
> **Date:** 2026-04-17
> **Issue:** https://github.com/vamseeachanta/assethold/issues/38
> **Review artifacts (v1):** `docs/reports/reviews/2026-04-17-plan-38-{claude,codex}.md` — both MAJOR
> **Review artifacts (v2 — this revision):** `docs/reports/reviews/2026-04-17-plan-38-{claude,codex}-v2.md`
> **v2 fixes:** (1) dropped erroneous `pytest.ini` marker registration — already exists at `pytest.ini:13` AND `tests/conftest.py:275`; (2) Item 1 now replaces the 2 unused imports (Item 2) with `import subprocess`, `import sys` so the probe is syntactically valid; (3) Item 6 passes a `label` arg to preserve original `ValueError` text; (4) sibling slow test in watchlist_runner_intraday.py also marked.

---

## Resource Intelligence Summary

### Existing repo code (evidence-based findings)

- **Found:** `src/assethold/modules/stocks/cache.py:17` — `TTL_OHLCV_INTRADAY = 15 * 60`. `ohlcv_ttl(market_hours_aware)` helper exists (landed in Phase 1). No regression test locks in the lazy-import invariant that the default path does not touch `assethold.utils.market_hours`.
- **Found:** `tests/unit/test_cache_ohlcv_ttl.py` — 39 lines. `import pytest` and `import assethold.modules.stocks.cache as cache_mod` are declared but unused (flake8/ruff would flag). Existing tests use `from assethold.modules.stocks.cache import ohlcv_ttl, TTL_OHLCV, TTL_OHLCV_INTRADAY`.
- **Found:** `tests/unit/signals/test_data_sources_market_hours.py:7` — `from pathlib import Path` unused (the `tmp_path` fixture already returns `Path`).
- **Found:** `src/assethold/analysis/daily_strategy/fetcher.py:185-195` — docstring on `_fetch_ohlcv` reads *"A 4-day freshness buffer covers weekends and market holidays"* with no mention of the `market_hours_aware=True` branch added in Phase 1. The 3-branch logic is present in the code below the docstring.
- **Found:** `src/assethold/analysis/daily_strategy/__main__.py:185-197` — 13-line `MarketDataFetcher(...)` construction with two nested `int(config.get("scoring", {}).get(...))` lookups and one short-circuit ternary. Readable now; one more knob would tip it into "hard to scan."
- **Found:** `src/assethold/utils/market_hours.py:63-96` — `next_open` and `next_close` share 14 lines of near-identical body: differ only in column name (`market_open` vs `market_close`) and error message.
- **Found:** `tests/integration/test_daily_strategy_intraday.py:48-65` — `test_no_intraday_flag_does_not_check_market_hours` runs the full `daily_strategy` pipeline with `timeout=300` and real yfinance fetches. Narrow assertion (`"next open" not in stderr`). Slow; no `@pytest.mark.slow` decorator applied (though the marker itself IS registered — see next bullet).
- **Found (sibling, v2 added):** `tests/integration/test_watchlist_runner_intraday.py:51` — `test_no_intraday_flag_does_not_check_market_hours` added in #39 with the same `timeout=300` real-subprocess pattern. Also lacks the `@pytest.mark.slow` decorator. Item 5 (v2) marks BOTH tests.
- **Found (v2 correction):** `pytest.ini:13` **already registers** `slow: marks tests as slow (deselect with '-m "not slow"')`. `tests/conftest.py:275` re-registers via `pytest_configure`'s `config.addinivalue_line`. `tests/conftest.py:294` also auto-applies `pytest.mark.slow` to any test under an `e2e/` path. Item 5 (v1) said "marker needs registration" — that was false. Item 5 (v2) only adds the decorator.
- **Found (v2):** `pyproject.toml:139-172` defines `[tool.pytest.ini_options]` with its OWN marker list (including `slow`) plus `--cov-fail-under=80` and `--strict-config`. Currently shadowed by `pytest.ini`. **This drift is out-of-scope for #38**, but flagged as a follow-up risk in §Risks (removing `pytest.ini` later would abruptly enable `--strict-config` and break CI).
- **Found (v2, CI verification):** `.github/workflows/python-tests.yml` runs `pytest` with no `-m` filter on lines 102, 110, 126, 235, 275, 285. Adding `@pytest.mark.slow` has **zero effect on CI wall-clock** until a follow-up PR adds `-m "not slow"` to the relevant jobs. Plan (v2) acknowledges this explicitly — Item 5's value is symbolic/documentary until the CI follow-up lands.
- **Found (proven pattern from #39):** subprocess-isolated lazy-import test lands at `tests/unit/signals/test_watchlist_runner.py::test_default_construction_does_not_import_pandas_market_calendars`. The same pattern applies directly to `cache.ohlcv_ttl()` item 1. `tests/unit/test_cache_ohlcv_ttl.py` currently has **no** `import subprocess` or `import sys` — Item 1 (v2) now adds them as part of the import swap with Item 2.

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

### Item 1 — Lazy-import regression test for `cache.ohlcv_ttl()` (v2)

Use the proven subprocess pattern from #39. **Important (v2 fix):** the target file `tests/unit/test_cache_ohlcv_ttl.py` does not currently import `subprocess` or `sys`. Item 1 adds them as part of the Item 2 import swap (see merged step below).

```python
# tests/unit/test_cache_ohlcv_ttl.py
# Item 2 removes: import pytest, import assethold.modules.stocks.cache as cache_mod
# Item 1 adds:    import subprocess, import sys
# (Net change: same line count; unused imports replaced with used ones.)

def test_ohlcv_ttl_default_does_not_import_market_hours():
    """Default path (market_hours_aware=False) must not pull market_hours."""
    probe = (
        "import sys; "
        "from assethold.modules.stocks.cache import ohlcv_ttl, TTL_OHLCV; "
        "assert ohlcv_ttl() == TTL_OHLCV; "
        "print('assethold.utils.market_hours' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, f"probe stderr: {result.stderr}"
    assert result.stdout.strip() == "False"
```

v2 changes vs v1:
- Probe imports `TTL_OHLCV` and asserts equality to the symbol instead of the magic `6 * 3600` — decouples the lazy-import invariant test from the TTL's numeric value (Claude MINOR).
- Pseudocode now names `import subprocess` and `import sys` explicitly so the test file is syntactically valid (Claude + Codex MAJOR).

The issue body proposed `sys.modules["assethold.utils.market_hours"] = None` monkeypatching — rejected because (a) that pattern was flagged unreliable in #39 adversarial review and (b) subprocess isolation is the known-good replacement.

### Item 2 — Remove unused imports (v2)

- `tests/unit/test_cache_ohlcv_ttl.py`: **replace** `import pytest` and `import assethold.modules.stocks.cache as cache_mod` **with** `import subprocess` and `import sys` (both needed by Item 1). Verified via grep — `pytest.` and `cache_mod.` have zero references; `monkeypatch` fixture is injected by pytest without requiring `import pytest`.
- `tests/unit/signals/test_data_sources_market_hours.py`: delete `from pathlib import Path`. Verified no `Path(` calls exist in the file.

Verification: `.venv/bin/python -m ruff check tests/unit/test_cache_ohlcv_ttl.py tests/unit/signals/test_data_sources_market_hours.py` must show no F401 (unused-import) warnings. (v2: single verification tool, not "ruff or flake8 or grep" ambiguity.)

### Item 3 — Fix stale `_fetch_ohlcv` docstring (v2)

In `src/assethold/analysis/daily_strategy/fetcher.py:185-195`, replace the single-branch docstring with a three-branch description matching the actual logic (lines 207-221): intraday TTL when aware+open, legacy 4-day when aware+closed, legacy 4-day when not aware.

```
Freshness semantics depend on the fetcher's market_hours_aware flag:

- When market_hours_aware=True and the NYSE regular session is open,
  the cache is considered fresh within intraday_ttl_minutes (mtime-based).
- When market_hours_aware=True and the session is closed, the legacy
  4-day calendar buffer applies (weekend/holiday coverage).
- When market_hours_aware=False (default), the legacy 4-day buffer
  always applies.
```

v2 vs v1: expanded from 1 sentence to 3 lines so the docstring matches all three branches (Codex MINOR).

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
import argparse  # add to existing imports if not already present

def _build_fetcher_kwargs(args: argparse.Namespace, config: dict) -> dict:
    """Construct MarketDataFetcher kwargs from CLI args + daily_strategy config.

    Module-private helper; not intended for cross-module reuse.
    """
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

v2 vs v1: `args: argparse.Namespace` explicit typing (mypy strict-mode compliance); docstring explicitly states module-private scope (Codex MINOR).

### Item 5 — Mark slow integration tests (v2 — marker already registered)

**v2 correction:** `pytest.ini:13` ALREADY registers the `slow` marker; `tests/conftest.py:275` re-registers it programmatically; `tests/conftest.py:294` auto-applies it to any test under `e2e/`. No `pytest.ini` edit is needed.

Item 5 therefore reduces to: apply `@pytest.mark.slow` to **both** identical slow tests.

```python
# tests/integration/test_daily_strategy_intraday.py
@pytest.mark.slow  # v2: marker already registered; decorator only
def test_no_intraday_flag_does_not_check_market_hours():
    ...

# tests/integration/test_watchlist_runner_intraday.py  (added in #39)
@pytest.mark.slow  # v2: same rationale; sibling test had identical runtime profile
def test_no_intraday_flag_does_not_check_market_hours():
    ...
```

**CI impact (v2 honest framing):** `.github/workflows/python-tests.yml` currently runs pytest without `-m` filtering on every job. Adding the decorator has **zero wall-clock effect on CI today**. The decorator's purpose is to enable a future follow-up issue (file as "#XX: gate slow tests in CI with -m 'not slow'") where CI jobs add `-m "not slow"` to fast-path stages. Local developers can already filter via `pytest -m "not slow"` the moment this lands.

v2 vs v1: dropped erroneous `pytest.ini` edit; added sibling slow test from #39; honest framing of CI-impact-zero until follow-up lands.

### Item 6 — Extract `_next_event(ts, column, label)` helper (v2 — preserves error text)

**v2 correction:** v1's `f"No NYSE {column} found..."` would have changed the public `ValueError` text from `"No NYSE market open found..."` to `"No NYSE market_open found..."` (underscore). Both Claude and Codex flagged this as contradicting the "no behavior change" claim. Fix: pass a human `label` arg separately.

```python
def _next_event(
    ts: Optional[datetime],
    column: str,
    label: str,
) -> datetime:
    """Return the next `column` ('market_open' or 'market_close') strictly after ts.

    Shared body of next_open and next_close. 14-day forward search; raises
    ValueError (with the human-readable `label`) if no matching event is found.
    """
    if column not in ("market_open", "market_close"):
        raise ValueError(f"Invalid column {column!r}; expected 'market_open' or 'market_close'")
    et = _normalize(ts)
    cal = _get_calendar()
    schedule = cal.schedule(
        start_date=et.date(),
        end_date=(et + pd.Timedelta(days=14)).date(),
    )
    for _, row in schedule.iterrows():
        if row[column] > et:
            return row[column].tz_convert("America/New_York").to_pydatetime()
    raise ValueError(f"No NYSE {label} found within 14 days of {ts}")


def next_open(ts: Optional[datetime] = None) -> datetime:
    """Return the next NYSE regular-session opening strictly after ts."""
    return _next_event(ts, "market_open", "market open")


def next_close(ts: Optional[datetime] = None) -> datetime:
    """Return the next NYSE regular-session close strictly after ts."""
    return _next_event(ts, "market_close", "market close")
```

v2 changes:
- Added `label: str` parameter — preserves the original error text `"No NYSE market open found..."` / `"No NYSE market close found..."` byte-identical (Claude + Codex MAJOR).
- Added column validation — raises `ValueError` (not raw `KeyError`) if a bad column is passed (Codex MINOR).

Existing `tests/unit/test_market_hours.py` tests (14 of them) continue to pass unchanged — error text preserved, behavior preserved.

---

## Files to Change

| Action | Path | Reason |
|---|---|---|
| Modify | `tests/unit/test_cache_ohlcv_ttl.py` | Item 1 (append subprocess regression test) + Item 2 (remove 2 unused imports) |
| Modify | `tests/unit/signals/test_data_sources_market_hours.py` | Item 2 (remove `from pathlib import Path`) |
| Modify | `src/assethold/analysis/daily_strategy/fetcher.py` | Item 3 (docstring append) |
| Modify | `src/assethold/analysis/daily_strategy/__main__.py` | Item 4 (extract `_build_fetcher_kwargs`) |
| Modify | `tests/integration/test_daily_strategy_intraday.py` | Item 5 (apply `@pytest.mark.slow` decorator; marker already registered in pytest.ini:13) |
| Modify | `tests/integration/test_watchlist_runner_intraday.py` | Item 5 (apply `@pytest.mark.slow` to sibling test from #39) |
| ~~`pytest.ini`~~ | ~~`pytest.ini`~~ | **Dropped in v2** — marker is already registered at line 13 |
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
- [ ] `pytest -m "not slow"` skips BOTH `test_no_intraday_flag_does_not_check_market_hours` tests (daily_strategy + watchlist_runner sibling); default `pytest tests/integration/` still runs them
- [ ] `market_hours.py` has `_next_event(ts, column, label)` helper with column-validation; `next_open` and `next_close` delegate in 1 line each; existing `ValueError` text preserved byte-identical
- [ ] All pre-change tests pass with no new failures (no fixed count claim — baseline drifts between plan and implementation)
- [ ] `python -m assethold.analysis.daily_strategy --help` output unchanged
- [ ] `.venv/bin/python -m ruff check tests/unit/test_cache_ohlcv_ttl.py tests/unit/signals/test_data_sources_market_hours.py` shows zero F401 warnings
- [ ] Two adversarial review artifacts v2 (Claude + Codex) each return APPROVE or MINOR before implementation begins

---

## Adversarial Review Summary

### v1 (2026-04-17 afternoon)

| Provider | Verdict | Key findings |
|---|---|---|
| Claude (code-reviewer subagent) | **MAJOR** | (1) `slow` marker already registered in `pytest.ini:13` + `conftest.py:275` — Item 5's registration action is no-op/corrupting; (2) Item 1 subprocess pseudocode would NameError — no `import subprocess`/`sys` in target file; (3) Item 6 changes ValueError text from "No NYSE market open" to "No NYSE market_open". Plus MINORs on pyproject.toml drift, sibling slow test unmarked, CI filter framing, Item 4 type annotation, Item 1 magic number, Item 3 docstring incomplete. |
| Codex (gpt-5.4) | **MAJOR** | Converged on same 3 MAJORs + drift-risk MINOR. Independently verified pytest.ini already has marker. Additional MINOR on Item 2 tooling ambiguity (ruff vs flake8). |

**Overall v1 result:** FAIL — revise required.

### v2 fixes applied in this revision

1. **MAJOR 1 fix:** Dropped the erroneous `pytest.ini` edit. Item 5 reduces to applying `@pytest.mark.slow` to the two sibling slow tests.
2. **MAJOR 2 fix:** Item 1 pseudocode integrated with Item 2 import swap (remove `pytest`+`cache_mod`, add `subprocess`+`sys`). Probe also asserts `ohlcv_ttl() == TTL_OHLCV` instead of magic number.
3. **MAJOR 3 fix:** Item 6 `_next_event` signature gains `label: str` — preserves original `ValueError` text byte-identical. Column validation added so invalid column raises `ValueError` not `KeyError`.
4. **MINOR fixes:** Item 3 docstring now covers all 3 branches; Item 4 adds `args: argparse.Namespace` typing + module-private docstring note; Item 5 includes sibling slow test in watchlist_runner_intraday.py; Item 5 explicitly acknowledges CI-impact-zero until follow-up adds `-m "not slow"`; baseline claim replaced with "no new failures"; Item 2 tooling fixed on `ruff` alone; pyproject.toml drift flagged as follow-up risk.

### v2 (this revision)

| Provider | Verdict | Key findings |
|---|---|---|
| Claude | PENDING | re-review pending |
| Codex | PENDING | re-review pending |

**Overall v2 result:** PENDING — re-review wave in flight.

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
