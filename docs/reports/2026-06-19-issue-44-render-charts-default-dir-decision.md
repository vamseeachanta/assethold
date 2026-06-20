# Issue #44 Decision Memo — `--render-charts` default dir (fail-loud vs default-dir)

**Date:** 2026-06-19
**Issue:** [vamseeachanta/assethold#44](https://github.com/vamseeachanta/assethold/issues/44)
**Source:** #39 plan §Open Questions bullet 2; implementation commit `fd0bc33`
**Status:** Decision recorded — memo only, no behavior change applied
**Companion plan:** `docs/plans/2026-05-05-issue-44-render-charts-default-dir.md`

---

## 1. The question

When `--render-charts` is passed to the `WatchlistRunner` CLI without `--charts-dir`, should the
program:

- **Option A (current, fail-loud):** exit with an error telling the user to supply `--charts-dir`, or
- **Option B (default-dir):** silently fall back to a default output directory and write charts there?

This is an ergonomics-vs-safety tradeoff, not a correctness bug (issue priority: low).

## 2. Current behavior (file:line)

Fail-loud (Option A) is enforced at **two** layers today:

| Layer | Site | Behavior |
|---|---|---|
| CLI guard | `src/assethold/signals/watchlist_runner.py:173-178` | `if args.render_charts and args.charts_dir is None:` → prints `--render-charts requires --charts-dir PATH` to stderr and `return 2`. |
| Library invariant | `src/assethold/signals/watchlist_runner.py:43-46` | Constructor: `if render_charts and charts_output_dir is None:` → `raise ValueError("render_charts=True requires charts_output_dir to be set")`. |
| Help text | `src/assethold/signals/watchlist_runner.py:133, 139` | `--render-charts` help: "Requires --charts-dir."; `--charts-dir` help: "(required with --render-charts)." |
| Dir creation | `src/assethold/signals/watchlist_runner.py:78-79` | `run()` does `self._charts_output_dir.mkdir(parents=True, exist_ok=True)` — so the dir is auto-created once a path is known. |

Tests pinning the current contract:

- `tests/unit/signals/test_watchlist_runner.py:334-348` — `test_cli_render_charts_without_dir_exits_2` (CLI exit 2).
- `tests/unit/signals/test_watchlist_runner.py:98-103` — `test_init_raises_if_render_charts_without_dir` (constructor `ValueError`).

This fail-loud stance is a **deliberate house pattern**, not an accident. The sibling `--intraday`
flag in the same Phase-1 work made the same call: see
`docs/reports/2026-04-16-realtime-phase1-design.md` §2 Decision #3 — "**Fail loud** uniformly …
(no silent skip)", citing the user's stated preference.

## 3. The tradeoff

| | Fail-loud (A) | Default-dir (B) |
|---|---|---|
| Scripting friction | Slightly higher — every `--render-charts` invocation must also pass `--charts-dir`. | Lower — one flag does the job. |
| Surprise file writes | None — the program never writes outside a path the user named. | Risk — charts can appear in an unexpected location (`./dashboard-charts/`) the user did not intend, polluting CWD or shadowing a prior run. |
| Misconfig surfacing | Immediate and explicit (exit 2 + message). | Hidden — a typo or forgotten flag still "succeeds", files just land somewhere else. |
| Reversibility | Easy to relax later (A→B is non-breaking: removes an error). | Hard to tighten later (B→A is breaking: scripts relying on the default break). |
| Repo convention | Matches Decision #3 (`--intraday` fails loud) and workspace-hub path-handling guidance (avoid CWD-relative writes). | Diverges from the established sibling-flag pattern. |

The decisive asymmetries:

1. **A→B is non-breaking; B→A is breaking.** Keeping fail-loud preserves the option to add a default
   later for free. Adding a default now forecloses a clean reversal.
2. **`--render-charts` writes files to disk.** Unlike a read-only default, a wrong default-dir
   *produces side effects* in the wrong place — exactly the failure mode Option A exists to prevent.
3. **Consistency.** The codebase already chose fail-loud for the sibling realtime flag in the same
   subsystem; doing the opposite here makes the CLI's contract internally inconsistent.

## 4. Recommendation — keep fail-loud (Option A), with a graceful path to opt-in convenience

**Recommended: stay with Option A (fail-loud) as the default contract.** Do not silently fall back to
`./dashboard-charts/`. Rationale: `--render-charts` is a *data-writing* path, and the project's
stated and demonstrated preference (Decision #3) is to surface misconfiguration early rather than
write to a surprise location. The friction Option B solves is one extra flag on an explicitly
opt-in feature — a low cost — whereas the risk it introduces (files in the wrong place, silently)
matches precisely the class of error fail-loud is meant to catch.

This is consistent with the general principle the issue is probing: **fail loud on explicit
data/output paths; default only for clearly-optional, side-effect-free outputs.** `--render-charts`
is the former.

If friction is later judged too high, prefer an **explicit opt-in** to a silent default:

- A `--charts-dir auto` sentinel (or a dedicated `--charts-dir-default` flag) that *intentionally*
  resolves to `data/dashboards/<YYYY-MM-DD>/`. The user is still naming the behavior; nothing
  happens silently. Date-partitioning under the gitignored `data/` tree avoids both CWD pollution
  and silent overwrite of a prior run.

This supersedes the companion plan
(`docs/plans/2026-05-05-issue-44-render-charts-default-dir.md`), which leaned Option B with a
`--no-default-charts-dir` opt-out. That design inverts the safe default (convenience-by-default,
safety-by-opt-out); this memo recommends the opposite (safety-by-default, convenience-by-opt-in),
which is the non-breaking and reversible direction.

## 5. Concrete changes that implement the recommendation (described, not applied)

The recommended decision is **largely a no-op on behavior** — Option A is already the shipped
contract. The work is to *cement* it and remove the "open question" status:

1. **Tighten the help text** (so the contract is documented as intentional, not provisional):
   - `src/assethold/signals/watchlist_runner.py:133` — leave "Requires --charts-dir." (already
     correct); optionally append "(no default output dir — see issue #44)".
   - `src/assethold/signals/watchlist_runner.py:139` — leave "(required with --render-charts)."
2. **Keep both guards unchanged**: the CLI guard at `:173-178` (`return 2`) and the constructor
   invariant at `:43-46` (`ValueError`). The two-layer defense (CLI message + library invariant) is
   correct and should be retained.
3. **Keep the tests green as the contract pin** — no edits needed:
   - `tests/unit/signals/test_watchlist_runner.py:334-348` (CLI exit 2) stays.
   - `tests/unit/signals/test_watchlist_runner.py:98-103` (constructor `ValueError`) stays.
   - Continue stubbing `dashboard.save_chart` in chart tests (per issue "Not in scope").

If/when the opt-in convenience path (§4) is built later, the *additive* changes would be:

- Accept `--charts-dir auto` (or add `--charts-dir-default`) in `_build_arg_parser()` around
  `src/assethold/signals/watchlist_runner.py:135-140`.
- In `main()` near `:173`, resolve the sentinel to
  `Path("data/dashboards") / date.today().isoformat()` *before* the fail-loud guard, so an explicit
  opt-in bypasses the guard while a bare `--render-charts` still exits 2.
- Add a `test_cli_render_charts_dir_auto_uses_dated_default` test asserting the resolved path; the
  existing exit-2 test is unchanged (bare flag still fails loud).

## 6. Backward-compat / migration

- **No migration needed.** The recommendation keeps the shipped contract (`fd0bc33`), so existing
  scripts and tests are unaffected.
- The recommended direction is the *reversible* one: a future opt-in default (Option B-as-opt-in) is
  purely additive and non-breaking. Had we shipped a silent default now, later tightening would have
  broken any script that relied on it — this memo avoids that trap.
- Action item to close the issue: record this decision (done, this memo) and demote #44 from
  "open design question" to "resolved — fail-loud confirmed".

## 7. References

- Code site: `src/assethold/signals/watchlist_runner.py:43-46, 78-79, 130-140, 173-178`
- Tests: `tests/unit/signals/test_watchlist_runner.py:98-103, 334-348`
- Sibling fail-loud precedent: `docs/reports/2026-04-16-realtime-phase1-design.md` §2 Decision #3
- Companion plan (superseded direction): `docs/plans/2026-05-05-issue-44-render-charts-default-dir.md`
- Implementation commit: `fd0bc33` (#39)
