# Issue #8 Plan — Literature / Running Board

**Issue:** [vamseeachanta/assethold#8](https://github.com/vamseeachanta/assethold/issues/8)
**Tier:** T1 (single-site doc)
**Date:** 2026-05-05

## Context

Issue #8 is a running notepad that captures three external references (PyQuant News LinkedIn page, two TradingView replication articles, and the `python-tradingview-ta` library). The first checkbox is already marked done. The remaining items are an exploratory note about TradingView lowcode/nocode replication — not an implementation request. There is no acceptance criteria, no module to touch, no falsifiable outcome.

**Recommendation:** close as too broad / parking-lot. The actionable subset is "evaluate `python-tradingview-ta` as a complement to yfinance" — that should become its own narrow follow-up issue if the user wants to pursue it. The literature list itself belongs in `docs/finanace_data.md` or a new `docs/external-references.md` file as a one-shot doc edit, not an open issue.

## Plan

If user opts to keep the issue open instead of closing:

1. **Migrate the link list** into `docs/external-references.md` (new file) with a one-line annotation per link describing what it offers (lowcode charting / TA library / replication tutorial). Group by category: TradingView, PyQuant News, other.
2. **Append a one-paragraph evaluation note** for each TradingView link: is the technique practical for this repo (which already uses yfinance + matplotlib + Plotly)? What would it cost to adopt?
3. **Close issue #8** once the doc lands; file a fresh narrow issue *only* if the evaluation surfaces a concrete adoption decision (e.g. "adopt `python-tradingview-ta` for sentiment overlay on daily strategy charts").
4. **No source code changes.** This is a documentation-only edit.

Smoke: `mkdocs build --strict` (verifies the new doc renders without dead links / nav errors).

## Acceptance Criteria

- `docs/external-references.md` exists with all three URLs from the issue body, each annotated with a one-line use-case description.
- `mkdocs build --strict` completes without warnings about the new file.
- Either issue #8 is closed (preferred), or a narrow follow-up issue is filed citing a specific adoption decision derived from the evaluation note.
- No changes to `src/assethold/` source modules.

## Recommendation

**Close as too broad** once doc lands. Running-board issues attract scope creep without delivering executor value; convert to docs and let new ideas land as fresh issues.
