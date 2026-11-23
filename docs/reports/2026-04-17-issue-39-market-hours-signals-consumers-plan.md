# Plan for #39: Extend `market_hours_aware` to signals consumers (alert_engine, trend_detector, dashboard)

> **Status:** plan-review (revised v2.1 after v2 testability findings)
> **Complexity:** T2 (upper)
> **Date:** 2026-04-17
> **Issue:** https://github.com/vamseeachanta/assethold/issues/39
> **Review artifacts (v1):** `docs/reports/reviews/2026-04-17-plan-39-{claude,codex,gemini}.md` — all three MAJOR
> **Review artifacts (v2):** Claude MINOR, Codex MAJOR (retrieval-blocked; plan was local-only). See §Adversarial Review Summary.
> **v2.1 focused fixes:** clock injection for `_date_range()` testability; subprocess-isolated lazy-import test; dropped inconsistent `Watchlist.get_settings()` helper; strengthened governance-comment sequencing.

---

## Resource Intelligence Summary

### Existing repo code (evidence-based findings)

- **Found:** `src/assethold/signals/alert_engine.py:142` — `AlertEngine.build_alerts(ticker, trend_events, insider_flags)` takes **pre-computed** dicts. `run_watchlist(ticker_results)` at line 219 also takes pre-computed dicts. No data-source construction.
- **Found:** `src/assethold/signals/trend_detector.py:18,90,143,196,310` — detectors and `TrendDetector.analyze(df)` take `pd.DataFrame` input. No data-source construction.
- **Found:** `src/assethold/signals/dashboard.py:29,82,132,189` — pure plotting. `save_chart(fig, output_path, fmt="html")` at line 254. No data-source construction.
- **Found:** `src/assethold/signals/data_sources.py:78-84` — `StockDataSource.fetch(self, ticker: str, start_date: str, end_date: str, use_cache: bool = True) -> pd.DataFrame`. **Dates are REQUIRED positional args in `YYYY-MM-DD` format.** Constructor accepts `market_hours_aware`, `intraday_ttl_minutes`, and `cache_ttl_hours`.
- **Found:** `src/assethold/signals/watchlist.py:22-26,50-60` — `Watchlist(config_path=None).load()` uses `yaml.safe_load` (no schema validation); `get_tickers()` returns `list[str]`. `Watchlist` never reads the `settings:` block.
- **Found:** `config/stocks/watchlist.yml:84-88` — existing `settings:` block with `default_monitoring_frequency`, `cache_ttl_hours: 24`, `rate_limit_seconds: 2.0`. New cache-TTL knobs are semantic siblings and MUST live here, not at top level.
- **Found:** `src/assethold/analysis/daily_strategy/__main__.py:94-120` — Phase 1 `--intraday` pre-flight pattern with lazy `from assethold.utils.market_hours import is_market_open, next_open` inside the `if args.intraday:` branch. Reused verbatim.
- **Found:** `src/assethold/utils/market_hours.py` — `_get_calendar()` lazy-imports `pandas_market_calendars`; module-level `import pandas as pd` is eager (pandas is already a project-wide dep, so benign).
- **Gap (orphan-code risk):** `grep -rn "from assethold.signals" --include="*.py" .` outside `signals/` and `tests/` returns **zero** non-test callers of `alert_engine`, `trend_detector`, or `dashboard`. This issue is the first production consumer — without a real CLI entry point the orchestrator becomes dead code.
- **Gap (settings drift):** `watchlist.yml:settings.cache_ttl_hours` is declared but `Watchlist` never reads it. Not in scope for this issue, but flagged as pre-existing tech debt; a follow-up issue should wire `settings.*` into `StockDataSource`.

### Standards
Not applicable — application wiring.

### LLM Wiki pages consulted
Not applicable.

### Documents consulted
- `docs/reports/2026-04-16-realtime-feeds-assessment.md` §2 — ranks `alert_engine`, `trend_detector`, `dashboard` as top realtime-value consumers; §4 Phase 2 defers the APScheduler daemon (explicitly out of scope for this issue).
- `docs/reports/2026-04-16-realtime-phase1-design.md` §2 decision table — naive-ts-as-UTC, fail-loud outside market hours, lazy-import when flag off, default `False`. All carried forward.
- `docs/reports/2026-04-17-session-exit-handoff-phase1-complete.md` — handoff decisions, `tz_convert` discipline, 3-branch `_fetch_ohlcv` pattern.
- GitHub issue #39 body — frames scope as "plumb kwargs through each module's public API." **Adversarial review confirmed this framing is inaccurate**: none of the three modules own data-source construction. Plan redirects to a thin orchestrator. The issue body must be updated to reflect this redirect as part of approval — see §Acceptance Criteria.
- GitHub issue #38 — Phase 1 polish backlog item 1 (lazy-import regression test for `cache.ohlcv_ttl`). This plan applies analogous lazy-import discipline and closes the gap for the CLI entry point.

### Gaps identified (what must be built from scratch)
1. A thin `WatchlistRunner` orchestrator in `src/assethold/signals/watchlist_runner.py` that owns the `StockDataSource` instance, computes the fetch date range, drives the per-ticker pipeline, and exposes a CLI entry.
2. A `lookback_days` decision (see §Decisions below) — this is load-bearing for `StockDataSource.fetch(..., start_date, end_date, ...)` and was missed in v1.
3. Two new keys under `config/stocks/watchlist.yml:settings:` — `market_hours_aware: false`, `intraday_ttl_minutes: 15`, `lookback_days: 90`.
4. Unit + integration tests exercising the real `StockDataSource` wiring, date-range computation, CLI `--intraday` / `--no-intraday` override, and `--render-charts` guard rails.

Distinct sources: issue body (1) + signals source inspection w/ exact line numbers (2) + `data_sources.py` fetch signature verified (3) + Phase 1 plan+design docs (4) + assessment §2/§4 (5) + Phase 1 handoff decisions (6) + existing `Watchlist`/`settings:` block (7) + `daily_strategy/__main__.py` CLI pattern (8). Well above the ≥3 minimum.

---

## Design Decisions Resolved (MUST honor during implementation)

| # | Question | Decision | Rationale |
|---|---|---|---|
| 1 | How does the orchestrator compute `start_date`/`end_date` for `StockDataSource.fetch`? | `lookback_days: int = 90` knob in `settings:` of `watchlist.yml`. `end_date = date.today()`, `start_date = end_date - timedelta(days=lookback_days)`. Formatted `%Y-%m-%d`. `--lookback-days INT` CLI override. | 90d is a sane default for MA-50/RSI-14/volume-spike calculations; matches typical timeframe used in `trend_detector`. Uses `date.today()` (wall-clock), independent of `--intraday` pre-flight semantics. |
| 2 | `--intraday` / `--no-intraday` / config interaction. | `argparse.BooleanOptionalAction` for `--intraday` / `--no-intraday`. **Precedence:** CLI flag (if provided, either direction) > config.settings.market_hours_aware > `False`. If neither CLI nor config specifies, default `False`. | Phase 1 contract was "default False, opt-in via CLI." This extends symmetrically: user can force off explicitly, closing the gap identified by Claude reviewer. |
| 3 | Issue-body scope redirect from "edit 3 modules" to "new orchestrator". | Accept the redirect; file a governance comment on #39 noting the scope change and acceptance-criteria update. **User approval of this plan = approval of the redirect.** | None of the three listed modules own data-source construction (see Resource Intel). A literal interpretation would produce no-op kwarg arguments on pure computation/plotting functions. Orchestrator is the minimum-viable change that honors the freshness intent. |
| 4 | `insider_flags=[]` hardcoded. | Orchestrator accepts optional `insider_flags_provider: Callable[[str], list[dict]] | None = None`. When `None`, the runner calls `build_alerts(ticker, trend_events, insider_flags=[])` **and logs a WARNING once per run** (not per ticker) that insider flags are disabled. | Silent empty alerts would mislead operators. Logging makes the deferral visible; provider slot allows future wiring without signature churn. |
| 5 | `WatchlistRunner` constructs `StockDataSource` — `__init__` or `run()`? | **`__init__`.** `StockDataSource.__init__` does not import `pandas_market_calendars` (verified in `signals/data_sources.py`); lazy-import discipline lives inside `_is_cache_valid`. Eager construction avoids null-check sprawl in `run()`. | v1 plan's lazy-source design was defensive against a concern that doesn't exist. |
| 6 | `render_charts=True` but `charts_output_dir=None`. | **Invalid combination — `__init__` raises `ValueError`.** CLI parser enforces same. When rendering, directory is `mkdir -p`-ed. | v1 plan had a silent `TypeError` at runtime. Explicit fail-loud at construction is the Phase 1 discipline. |
| 7 | Where do new YAML knobs live? | **Under `settings:`.** `market_hours_aware: false`, `intraday_ttl_minutes: 15`, `lookback_days: 90`. | Consistent with existing shape. Claude + Gemini reviewers agreed. `main()` reads via direct `config.get("settings", {})` (no new helper on `Watchlist`; keeps surface area minimal — see v2.1 fix dropping the `get_settings()` helper). |
| 8 | Lazy-import test shape (v2.1). | **Use subprocess isolation.** Test spawns a fresh Python subprocess that (a) imports `assethold.signals.watchlist_runner`, (b) prints `"pandas_market_calendars" in sys.modules` to stdout. Test asserts output is `"False"`. This avoids the shared-process `sys.modules` contamination risk Codex v2 flagged. Pattern: `subprocess.run([sys.executable, "-c", probe_script], capture_output=True)`. | v1 test was a no-op. v2 sys.modules check was unreliable in shared pytest process (pandas-market-calendars is already a project dep). Subprocess gives a clean import context. |
| 10 | `_date_range()` testability (v2.1 fix). | Inject a clock: `WatchlistRunner(..., now: Callable[[], date] = date.today)`. `_date_range()` calls `self._now()`. Tests pass a lambda returning fixed date, e.g. `now=lambda: date(2026, 4, 17)`. | Monkeypatching `date.today` fails because `datetime.date` is C-implemented and its methods are immutable. Dependency injection is the clean solution; matches Phase 1's explicit-semantics preference. |
| 9 | Claude reviewer MINOR: `settings.cache_ttl_hours` orphaned. | **Out of scope** for this issue. Filed as follow-up (see §Risks). This issue only adds knobs; it does not fix the pre-existing orphan. | Scope discipline; fixing `cache_ttl_hours` wiring is an independent concern. |

---

## Artifact Map

| Artifact | Path |
|---|---|
| This plan | `docs/reports/2026-04-17-issue-39-market-hours-signals-consumers-plan.md` |
| New orchestrator | `src/assethold/signals/watchlist_runner.py` |
| Orchestrator tests | `tests/unit/signals/test_watchlist_runner.py` |
| Integration test | `tests/integration/test_watchlist_runner_intraday.py` |
| Config edit | `config/stocks/watchlist.yml` (under `settings:`) |
| Module export | `src/assethold/signals/__init__.py` |
| `Watchlist.get_settings()` helper | `src/assethold/signals/watchlist.py` (add ~10-line method) |
| Plan review v1 — Claude | `docs/reports/reviews/2026-04-17-plan-39-claude.md` |
| Plan review v1 — Codex | `docs/reports/reviews/2026-04-17-plan-39-codex.md` |
| Plan review v1 — Gemini | `docs/reports/reviews/2026-04-17-plan-39-gemini.md` |
| Plan review v2 — Claude | `docs/reports/reviews/2026-04-17-plan-39-claude-v2.md` |
| Plan review v2 — Codex | `docs/reports/reviews/2026-04-17-plan-39-codex-v2.md` |

---

## Deliverable

A `WatchlistRunner` class + `main()` CLI entry in `src/assethold/signals/watchlist_runner.py` that (a) loads `config/stocks/watchlist.yml`, (b) eagerly constructs a single `StockDataSource(market_hours_aware=..., intraday_ttl_minutes=..., cache_ttl_hours=...)` in `__init__`, (c) computes a `lookback_days`-based date range, (d) fetches OHLCV per ticker using the real `fetch(ticker, start_date, end_date)` signature, (e) runs `TrendDetector.analyze(df)` and `AlertEngine.build_alerts(ticker, trend_events, insider_flags)` per ticker, (f) optionally renders dashboards to a required output directory, and (g) exposes `--intraday` / `--no-intraday` / `--lookback-days` / `--render-charts --charts-dir` CLI flags mirroring Phase 1 fail-loud pre-flight semantics.

---

## Pseudocode

```python
# src/assethold/signals/watchlist_runner.py

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from assethold.signals.data_sources import StockDataSource
from assethold.signals.alert_engine import AlertEngine, AlertEvent
from assethold.signals.trend_detector import TrendDetector
from assethold.signals.watchlist import Watchlist
from assethold.signals import dashboard

logger = logging.getLogger(__name__)

# Note: NO top-level import of assethold.utils.market_hours — that stays lazy inside main().


class WatchlistRunner:
    def __init__(
        self,
        watchlist: Watchlist,
        market_hours_aware: bool = False,
        intraday_ttl_minutes: int = 15,
        lookback_days: int = 90,
        cache_ttl_hours: int = 24,
        insider_flags_provider: Callable[[str], list[dict]] | None = None,
        render_charts: bool = False,
        charts_output_dir: Path | None = None,
        now: Callable[[], date] = date.today,  # v2.1: injected clock for testability
    ):
        if render_charts and charts_output_dir is None:
            raise ValueError("render_charts=True requires charts_output_dir")

        self._watchlist = watchlist
        self._lookback_days = lookback_days
        self._render_charts = render_charts
        self._charts_output_dir = charts_output_dir
        self._insider_flags_provider = insider_flags_provider
        self._now = now  # v2.1: stored for _date_range()

        # Eager construction — StockDataSource.__init__ does not touch pandas_market_calendars.
        self._source = StockDataSource(
            market_hours_aware=market_hours_aware,
            intraday_ttl_minutes=intraday_ttl_minutes,
            cache_ttl_hours=cache_ttl_hours,
        )
        self._detector = TrendDetector()
        self._engine = AlertEngine()

        if insider_flags_provider is None:
            logger.warning(
                "WatchlistRunner: insider_flags_provider not set; "
                "CRITICAL-severity unusual_insider_activity alerts will not fire."
            )

    def _date_range(self) -> tuple[str, str]:
        end = self._now()  # v2.1: injectable clock
        start = end - timedelta(days=self._lookback_days)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    def run(self) -> dict[str, list[AlertEvent]]:
        start_date, end_date = self._date_range()
        if self._render_charts:
            self._charts_output_dir.mkdir(parents=True, exist_ok=True)

        results: dict[str, list[AlertEvent]] = {}
        for ticker in self._watchlist.get_tickers():
            df = self._source.fetch(ticker, start_date, end_date)  # real 3-arg signature
            if df is None or df.empty:
                results[ticker] = []
                continue

            trend_events = self._detector.analyze(df)
            insider_flags = (
                self._insider_flags_provider(ticker)
                if self._insider_flags_provider is not None
                else []
            )
            alerts = self._engine.build_alerts(ticker, trend_events, insider_flags)
            results[ticker] = alerts

            if self._render_charts:
                fig = dashboard.build_price_chart(df, ticker)
                dashboard.save_chart(fig, self._charts_output_dir / f"{ticker}.html")

        return results


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="watchlist_runner")
    p.add_argument(
        "--intraday",
        action=argparse.BooleanOptionalAction,
        default=None,  # None = not specified → fall back to config
        help="Enable market-hours-aware intraday freshness. --no-intraday forces off.",
    )
    p.add_argument("--lookback-days", type=int, default=None)
    p.add_argument("--render-charts", action="store_true")
    p.add_argument("--charts-dir", type=str, default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    watchlist = Watchlist()
    config = watchlist.load()
    settings = config.get("settings", {})

    # Precedence: CLI (explicit True/False) > config > False
    if args.intraday is not None:
        market_hours_aware = args.intraday
    else:
        market_hours_aware = bool(settings.get("market_hours_aware", False))

    if market_hours_aware:
        # Lazy import — identical discipline to Phase 1 (commit 00a8bbe).
        from assethold.utils.market_hours import is_market_open, next_open
        if not is_market_open():
            print(
                f"--intraday requires NYSE regular session open. "
                f"Next open: {next_open()}",
                file=sys.stderr,
            )
            print(
                "Note: --intraday is a wall-clock pre-flight; unrelated to "
                "--lookback-days which controls the historical date range.",
                file=sys.stderr,
            )
            return 1

    if args.render_charts and args.charts_dir is None:
        print("--render-charts requires --charts-dir PATH", file=sys.stderr)
        return 2

    runner = WatchlistRunner(
        watchlist=watchlist,
        market_hours_aware=market_hours_aware,
        intraday_ttl_minutes=int(settings.get("intraday_ttl_minutes", 15)),
        lookback_days=(
            args.lookback_days
            if args.lookback_days is not None
            else int(settings.get("lookback_days", 90))
        ),
        cache_ttl_hours=int(settings.get("cache_ttl_hours", 24)),
        render_charts=args.render_charts,
        charts_output_dir=Path(args.charts_dir) if args.charts_dir else None,
    )
    results = runner.run()
    _print_summary(results)
    return 0


def _print_summary(results: dict[str, list[AlertEvent]]) -> None:
    for ticker, alerts in sorted(results.items()):
        print(f"{ticker}: {len(alerts)} alert(s)")


if __name__ == "__main__":
    sys.exit(main())
```

Invariants (carry from Phase 1):
- Lazy import of `pandas_market_calendars` (via `assethold.utils.market_hours`) happens ONLY in the `if market_hours_aware:` branch of `main()`.
- Default construction (`market_hours_aware=False`) pays zero `pandas_market_calendars` import cost.
- `--intraday` fail-loud error message explicitly disambiguates wall-clock vs. `--lookback-days` (Phase 1 learning — commit `35ea4b2`).

---

## Files to Change

| Action | Path | Reason |
|---|---|---|
| Create | `src/assethold/signals/watchlist_runner.py` | `WatchlistRunner` class + CLI `main()` + arg parser |
| Modify | `src/assethold/signals/__init__.py` | export `WatchlistRunner` |
| (dropped in v2.1) | ~~`src/assethold/signals/watchlist.py`~~ | ~~`get_settings()` helper~~ — dropped; `main()` reads `config.get("settings", {})` directly after `Watchlist().load()` |
| Modify | `config/stocks/watchlist.yml` | under `settings:`, add `market_hours_aware: false`, `intraday_ttl_minutes: 15`, `lookback_days: 90` with inline docs |
| Create | `tests/unit/signals/test_watchlist_runner.py` | TDD tests (see table) |
| Create | `tests/integration/test_watchlist_runner_intraday.py` | subprocess test mirroring `test_daily_strategy_intraday.py` |

---

## TDD Test List

| Test name | What it verifies | Input | Output |
|---|---|---|---|
| `test_init_constructs_real_stock_data_source` | `WatchlistRunner(watchlist, market_hours_aware=True, intraday_ttl_minutes=15, cache_ttl_hours=24)` creates a real `StockDataSource` with those attrs set | constructor args | `runner._source.market_hours_aware is True` and `runner._source.intraday_ttl == timedelta(minutes=15)` (real-instance check, no spy) |
| `test_init_raises_if_render_charts_without_dir` | `render_charts=True, charts_output_dir=None` fails at construction | constructor args | `ValueError` raised |
| `test_init_warns_when_insider_provider_missing` | Default construction (no provider) logs WARNING once | caplog fixture | Exactly 1 WARNING record containing "insider_flags_provider not set" |
| `test_date_range_uses_today_minus_lookback_days` | `_date_range()` returns `(today-lookback, today)` in `%Y-%m-%d` using injected clock (v2.1: clock injection, not monkeypatching) | `lookback_days=90`, `now=lambda: date(2026, 4, 17)` | `("2026-01-17", "2026-04-17")` |
| `test_run_per_ticker_pipeline_with_real_signatures` | For 2-ticker watchlist, `StockDataSource.fetch(ticker, start, end)` called once per ticker with correct dates; results threaded to `TrendDetector.analyze` and `AlertEngine.build_alerts` | stub `fetch` returns synthetic uptrend df | `runner.run()` returns `{"AAPL": [...], "MSFT": [...]}` both non-empty; `fetch.mock_calls` has 2 calls with dates matching lookback window |
| `test_run_skips_empty_dataframe` | Empty df → `results[ticker] = []`; detector/engine not invoked for that ticker | stub `fetch` returns empty df for one ticker | Assertions on no-call and empty list |
| `test_run_skips_none_dataframe` | `None` from `fetch` handled identically to empty | stub `fetch` returns `None` | No exception, empty list |
| `test_run_uses_insider_provider_when_set` | `insider_flags_provider(ticker)` is called per ticker and result flows to `build_alerts` | stub provider returns fixed list | `build_alerts` called with that list |
| `test_run_creates_charts_dir_and_saves_html` | `render_charts=True` with valid dir: `charts_output_dir/<TICKER>.html` exists after `run()` | `tmp_path`, 1 ticker | File exists at `tmp_path / "AAPL.html"` |
| `test_default_construction_does_not_import_pandas_market_calendars` | **Real invariant via subprocess isolation (v2.1):** spawns `subprocess.run([sys.executable, "-c", probe_script])` where probe_script imports `assethold.signals.watchlist_runner`, constructs a `WatchlistRunner` with `market_hours_aware=False`, then prints `"pandas_market_calendars" in sys.modules`. Avoids shared-pytest-process contamination that Codex v2 flagged. | subprocess probe | stdout `"False"`; exit 0 |
| `test_cli_intraday_fail_loud_outside_market_hours` | `main(["--intraday"])` at a monkey-patched known-closed timestamp returns 1 with `next open:` in stderr | monkeypatch `assethold.utils.market_hours.is_market_open` to `False` | Exit 1; stderr contains both "next open" and the clarifying wall-clock line |
| `test_cli_no_intraday_overrides_config_true` | With `config.settings.market_hours_aware = true`, `main(["--no-intraday"])` constructs `StockDataSource(market_hours_aware=False)` | config with flag on, CLI `--no-intraday` | `StockDataSource.__init__` called with `market_hours_aware=False` |
| `test_cli_no_flag_falls_back_to_config` | Without any `--intraday` flag, `main([])` reads `settings.market_hours_aware` from YAML | config with flag true | `StockDataSource.__init__` called with `market_hours_aware=True` |
| `test_cli_render_charts_without_dir_exits_2` | `main(["--render-charts"])` without `--charts-dir` returns exit 2 | argv | Exit 2; stderr contains "--charts-dir" |
| `test_cli_lookback_days_override` | `main(["--lookback-days", "30"])` overrides config default | argv | `StockDataSource.fetch` called with dates 30 days apart |

Integration test: `tests/integration/test_watchlist_runner_intraday.py::test_intraday_flag_fail_loud_outside_market_hours` — subprocess invocation mirroring Phase 1's `test_daily_strategy_intraday.py`.

---

## Acceptance Criteria

- [ ] **Scope-redirect acknowledgement:** issue #39 body has a comment (posted as part of the plan-review comment) explicitly stating that the "plumb kwargs into alert_engine/trend_detector/dashboard" framing is replaced by a `WatchlistRunner` orchestrator, and this plan's approval by the user is the approval of that redirect.
- [ ] All new unit tests pass: `.venv/bin/python -m pytest tests/unit/signals/test_watchlist_runner.py -v`
- [ ] Existing signals tests remain green: `.venv/bin/python -m pytest tests/unit/signals/ -v`
- [ ] Full baseline (849 from Phase 1) remains green: `.venv/bin/python -m pytest tests/unit/ -v`
- [ ] Integration test passes: `.venv/bin/python -m pytest tests/integration/test_watchlist_runner_intraday.py -v`
- [ ] `python -m assethold.signals.watchlist_runner --help` prints usage including `--intraday`, `--no-intraday`, `--lookback-days`, `--render-charts`, `--charts-dir`.
- [ ] `test_default_construction_does_not_import_pandas_market_calendars` passes — verifies lazy-import invariant via `sys.modules` inspection (subprocess-based if needed).
- [ ] Three adversarial reviews at plan-review time: `docs/reports/reviews/2026-04-17-plan-39-{claude,codex,gemini}-v2.md` each return APPROVE or MINOR (no MAJOR). Gemini is optional if capacity-exhausted (document fallback).
- [ ] Scope-redirect governance comment posted on issue #39 before `status:plan-review` label applied.

---

## Adversarial Review Summary

### v1 (2026-04-17 morning)

| Provider | Verdict | Key findings |
|---|---|---|
| Claude (code-reviewer subagent) | **MAJOR** | (1) `fetch(ticker)` unimplementable — dates required; (2) lazy-import test monkeypatches module the orchestrator never imports; (3) scope-redirect not surfaced into acceptance criteria or issue body; (4) no `--no-intraday` override path. Plus MINORs on YAML placement, insider silent suppression, render-charts None path, ghost helpers, bad verification method, lazy-construct vs eager. |
| Codex (gpt-5.4) | **MAJOR** | Same fetch-signature defect; dashboard/trend_detector are not data consumers at all. Retrieval-insufficient on the plan file itself (local-only, not pushed). |
| Gemini (gemini-3.1-pro-preview, 429-retried) | **MAJOR** | Same fetch-signature defect; YAML placement under `settings:`; render-charts `None` TypeError. |

**Overall v1 result:** FAIL — revise required.

### Revisions made in v2 (this revision)

- **MAJOR 1 fix:** Added Decision #1 (`lookback_days` knob) + `_date_range()` method + `test_date_range_uses_today_minus_lookback_days` + `test_cli_lookback_days_override`. Pseudocode now uses real 3-arg `fetch(ticker, start_date, end_date)` signature.
- **MAJOR 2 fix:** Removed v1's monkeypatched lazy-import test. Replaced with `test_default_construction_does_not_import_pandas_market_calendars` that inspects `sys.modules` for the real invariant.
- **MAJOR 3 fix:** Added scope-redirect acknowledgement to Acceptance Criteria as a first-class checkbox; added Decision #3 making the redirect explicit; added Risk about governance comment on issue body.
- **MAJOR 4 fix:** Added Decision #2 using `argparse.BooleanOptionalAction` with explicit CLI > config > False precedence. Tests `test_cli_no_intraday_overrides_config_true` and `test_cli_no_flag_falls_back_to_config` encode the contract.
- **MINOR fixes:** YAML knobs moved under `settings:` (Decision #7); `insider_flags_provider` callable slot + one-shot WARNING log (Decision #4); `render_charts=True` without dir raises `ValueError` at construction + CLI exits 2 (Decision #6, test `test_init_raises_if_render_charts_without_dir` + `test_cli_render_charts_without_dir_exits_2`); `_print_summary` defined inline (no ghost); `load_watchlist_config` removed — uses real `Watchlist().load()`; eager `StockDataSource` construction in `__init__` (Decision #5); spy-based wiring test replaced with real-instance attribute check.

### v2 (2026-04-17, post-MAJOR revision)

| Provider | Verdict | Key findings |
|---|---|---|
| Claude (code-reviewer subagent) | **MINOR** | All 4 v1 MAJORs confirmed FIXED (read `data_sources.py`, `pyproject.toml` Python 3.9+, `market_hours.py` lazy pattern, revised pseudocode). MINOR: (1) `Watchlist.get_settings()` helper promised but bypassed by `main()`; (2) `date.today()` monkeypatching fails for C-level types; (3) `sys.modules` test needs subprocess isolation; (4) governance-comment wording ambiguous. Approval-ready after fixes. |
| Codex (gpt-5.4) | **MAJOR** | Retrieval-blocked: plan was local-only, not pushed; Codex could not fetch from GitHub so verification relied on source baseline only. Substantive findings converge with Claude on `sys.modules` subprocess-isolation, `date.today()` testability, and that scope-redirect governance must hit the **issue body/comment**, not only the plan. |
| Gemini | **UNAVAILABLE** | 429 capacity-exhausted on re-review dispatch; v1 review returned MAJOR converging with Claude on signature defect (now fixed in v2). Per skill rule ("do not stall indefinitely when a provider is unavailable"), proceeding with Claude + Codex evidence. |

**Overall v2 result:** Revise → v2.1 (address convergent testability + governance MINORs + commit/push for retrievability).

### v2.1 (2026-04-17, this revision — minimal targeted fixes)

Applied in v2.1:
1. **Clock injection for `_date_range()`**: `now: Callable[[], date] = date.today` injectable; test uses `now=lambda: date(2026, 4, 17)`.
2. **Subprocess-isolated lazy-import test**: spawns fresh Python subprocess for `sys.modules` probe (clean import context).
3. **Dropped `Watchlist.get_settings()` helper**: `main()` uses direct `config.get("settings", {})`; no new public API on `Watchlist`.
4. **Governance sequencing strengthened**: governance comment MUST be posted on issue #39 BEFORE `status:plan-review` label is applied; plan-review comment links to both committed plan file AND governance comment.
5. **Plan committed and pushed** so future Codex/Gemini reviews can fetch via GitHub (addresses Codex v2 retrieval failure).

**Overall v2.1 result:** PENDING re-review. If Claude re-verification returns APPROVE/MINOR with the specific fixes checked, plan is approval-ready. Codex retrieval blocker is resolved by the push.

---

## Risks and Open Questions

- **Risk (governance):** The issue body tells implementers to edit three specific modules. This plan redirects to a new orchestrator module. If the user does NOT approve the redirect, the plan collapses — there is no code-only path that satisfies the literal issue body because the three modules don't own data-source construction. Mitigation: governance comment on #39 at `status:plan-review` time stating the redirect explicitly.
- **Risk (orphan-code):** Without the CLI entry, `WatchlistRunner` has no production caller. Mitigation: `main()` + `__main__` entry + integration test all delivered in the same commit.
- **Risk (pre-existing orphan config):** `config/stocks/watchlist.yml:settings.cache_ttl_hours` is declared but never read. This plan adds three MORE keys under the same `settings:` block. The `get_settings()` helper this plan adds to `Watchlist` finally gives `settings:` a reader — but only the runner reads it, not existing fetchers. **Follow-up:** file a separate issue to wire `settings.cache_ttl_hours` into `StockDataSource(cache_ttl_hours=...)` everywhere; this issue acknowledges the gap but does not fix it.
- **Risk (Gemini provider instability):** Gemini returned 429 on v1 and produced only a partial review. If v2 re-review also hits 429, the plan proceeds with Claude + Codex agreeing — documented explicitly. (Per skill: "do not stall indefinitely; record the provider failure explicitly and continue with available review evidence while keeping the issue in a non-approved state until blocking findings are resolved.")
- **Open:** Is `lookback_days=90` the right default, or should it match an existing constant (e.g., daily-strategy uses a different lookback)? Check `daily_strategy/fetcher.py` at implementation time; if there's a shared constant, reuse it.
- **Open:** Should `--render-charts` imply `--charts-dir` to a sane default (e.g. `./dashboard-charts/`) rather than failing? Plan defaults to **require explicit dir** for fail-loud discipline; user can redirect at approval.
- **Open:** `insider_flags_provider` is a callable slot; should the plan include a minimal placeholder implementation reading from existing insider-tracker artifacts, or leave the slot empty? Plan defaults to **leave empty + log warning**; follow-up issue to wire insider-tracker.

---

## Complexity: T2 (upper)

**T2 (upper)** — ~220 LOC orchestrator + CLI, ~15 unit tests, 1 integration test, ~10 LOC `Watchlist.get_settings()` helper, 3-line YAML edit, `__init__.py` export edit. All carries from Phase 1 design patterns; no novel framework choices. One focused implementation session after approval; estimated 4–6 hours including TDD discipline and the integration test subprocess harness.

---

## Implementation Sequencing (for reference, not binding)

1. Write failing tests for `WatchlistRunner.__init__` (real `StockDataSource` attr checks, ValueError on bad combo, insider warning).
2. Implement `__init__` to pass those tests.
3. Write failing test for `_date_range()`. Implement.
4. Write failing tests for `run()` per-ticker pipeline with stubbed `fetch`. Implement.
5. Write failing tests for CLI precedence (intraday / no-intraday / config / lookback / render-charts). Implement `main()` and `_build_arg_parser()`.
6. Write failing integration test (subprocess). Verify.
7. Add `Watchlist.get_settings()` with its own tests.
8. Edit `config/stocks/watchlist.yml` (add three keys under `settings:`).
9. Edit `src/assethold/signals/__init__.py` (export).
10. Run full suite. Close with commit + PR referencing #39.
