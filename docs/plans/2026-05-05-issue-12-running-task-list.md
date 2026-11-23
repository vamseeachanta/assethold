# Issue #12 Plan — Running Task List

**Issue:** [vamseeachanta/assethold#12](https://github.com/vamseeachanta/assethold/issues/12)
**Tier:** T1 (close-as-too-broad)
**Date:** 2026-05-05

## Context

Issue #12 is a five-item running task list. Two items are marked done ("open virtual portfolio in Yahoo/Google", "utilize existing libraries"). The remaining three items — "Buy favorite stock?", "Get all the data possible and document it in a PUML", "Analysis. PUML" — are not actionable: they have no acceptance criteria, no module references, and the question mark on "Buy favorite stock" indicates this is a personal note rather than a code task.

**Recommendation:** close as too broad. This duplicates the running-checklist anti-pattern flagged in #8 and #11. None of the remaining bullets correspond to a falsifiable engineering deliverable.

## Plan

1. **Salvage any durable intent into focused issues**:
   - "Get all the data possible and document it in PUML" → if data-source documentation is genuinely wanted, this is partially covered by issue #33 (architecture documentation, data format specs). Cross-reference and close.
   - "Analysis. PUML" → ambiguous; if there's a real ask for a UML / sequence diagram of the analysis pipeline, file a fresh narrow issue with the specific module to diagram.
   - "Buy favorite stock" → personal note, not a code task; remove.

2. **Close issue #12** with a comment summarizing where each remaining intent landed (in #33, in a new issue, or removed as personal note).

3. **No source code or documentation changes** required by this plan.

Smoke: none — close-only.

## Acceptance Criteria

- Issue #12 is closed with a comment cross-referencing #33 (which absorbs the PUML/data-doc intent) and noting any new follow-up issues filed.
- No work products land in `src/assethold/` or `docs/` from this issue.
- The running-checklist anti-pattern is documented as something to avoid in future issue creation (one-line note in `CONTRIBUTING.md` if such a file exists; otherwise skip).

## Recommendation

**Close as too broad.** Three out of three remaining items lack acceptance criteria. The durable subset (data-source PUML) is already tracked in #33.
