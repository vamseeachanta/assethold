# Adversarial review record — plan #90 dual-basis valuation

**Date:** 2026-09-22 · **Plan:** `../2026-09-22-issue-90-dual-basis-valuation.md` · **Issue:** [#90](https://github.com/vamseeachanta/assethold/issues/90)

Two independent reviewers, fresh context, both instructed to refute and to default to non-APPROVE.

| Reviewer | Focus | Verdict |
|---|---|---|
| r1 | Method, code claims, statistical validity, sequencing | **REJECT** — 12 MAJOR, 11 MINOR |
| r2 | CRE decision hazard, disclosure, liability | **REJECT** — 16 MAJOR, 8 MINOR |

**Consolidated verdict: REJECT. The plan is not safe to build as written.**

Self-review would not have found these. Both reviewers were independent, and the repo's own record
(self-review returns MINOR where independent returns MAJOR) held again.

---

## Findings verified first-hand before acceptance

Reviewer claims were not taken on trust. These were re-derived from the repo's own data:

### V1 — The core identity is wrong (r1 M1). CONFIRMED.

With contract rent equal to achievable rent and drag zero, a correct gap must be exactly zero.
It is not. The two legs carry different denominators by construction:

| Case | cap_asset | market_cap | income | location | gap | plan reads it as |
|---|---|---|---|---|---|---|
| Strong credit, absolute NNN | 7.50% | 8.50% | $1,774,933 | $1,566,118 | **−$208,816** | "over-rented, a liability" |
| Weak credit, NN | 9.00% | 8.50% | $1,479,111 | $1,566,118 | **+$87,007** | "under-rented, buy" |
| Equal caps (control) | 8.50% | 8.50% | $1,566,118 | $1,566,118 | $0 | at market |

**The rents are identical in every row.** The screen ranks by credit quality inverted, not by rent
recoverability. `gap = NOI × (1/market_cap − 1/cap_asset)` is a cap-rate delta wearing a rent-delta's
name.

### V2 — The rent benchmark would have called the repo's only asset under-rented. It is over-rented. (r2 M5). CONFIRMED.

From `data/cre/net_lease/nola-pharmacy-retail-nn-2025.yaml`, using data already committed:

| Period | Merchandise + food sales | Occupancy cost (rent ÷ sales) | Sales per sq ft |
|---|---|---|---|
| FY2022 | $2,175,098 | **13.1%** | $146 |
| FY2024 | $1,970,063 | **14.4%** | $132 |

Merchandise sales fell **12.4%** between the two periods. A psf benchmark sees $19.03/sq ft — low in
absolute retail terms — and reports under-rented. The occupancy-cost ratio says the rent is high
relative to what the location produces, which is why percentage rent has never breached its
breakpoint ($0 paid in both years). `sales_reporting: true` is in the schema and the plan never uses it.

**This is a false positive in exactly the direction the issue exists to find.**

### V3 — Two NOI bases, 8.0% apart, and the plan specifies neither (r1 M2 / r2 M6). CONFIRMED.

| Basis | Value | Source |
|---|---|---|
| Offering NOI | $284,000.00 | `financials.noi`, "per offering materials" (= gross rent) |
| Owner NOI | $262,934.78 | `owner_pnl` rental income $285,486.79 − opex $22,552.01 |

**$240,745 of valuation swing at an 8.75% cap on a single asset.** Worse, the two interact with the
structure spread: the NN premium over absolute NNN largely *is* the landlord's roof/structure/parking
burden. Use owner NOI (already net of it) **and** widen the cap, and the same expense is charged twice.

### V4 — The traffic score is sign-inverted for retail (r1 M4 / r2 M8). CONFIRMED.

`spatial_factors._score_traffic` = `1 − log10(1+aadt)/log10(1+100000)`:

| AADT | score |
|---|---|
| 0 | 1.000 |
| 1,000 | 0.400 |
| 13,500 | 0.174 |
| 60,000 | 0.044 |

It is a residential noise model. The whole thesis of #90 is that more traffic supports more retail
rent. The plan proposed reusing the enum "rather than inventing a second banding" — inheriting the
inverted companion score with it. The stated test ("band ordering follows AADT band ordering") passes
under either sign convention and catches nothing.

### V5 — Three inconsistent representations of one contractual rent, already committed. CONFIRMED.

`fixed_rent_annual: 284,000.00` · `rent_psf_annual × sqft: 283,927.60` · `fixed_rent_monthly × 12:
284,004.00` — spread $76.40, with no validator in `NNLeaseFinancials.__post_init__`. This is the
plan's own motivating defect class, live in committed data. It is a better regression fixture than a
synthetic one.

---

## The finding that does not wait for the plan

**`data/cre/net_lease/nola-pharmacy-retail-nn-2025.yaml` is on `origin/main` in a public repository**
and carries, under a header reading `# Data abstracted per data-room confidentiality obligations`:

- exact street address, `lat`/`lon` to four decimals, `parcel_id`
- two years of the tenant's **category-level gross sales**, obtained under the lease's sales-reporting clause
- the owner's P&L including `debt_service_interest`

It reached `origin` via `9c207c1 chore(sync): auto-sync 2026-08-02` — an unattended sync, not a review
gate. Abstracting the tenant to `national_pharmacy_chain` is cosmetic once the parcel is named, and
r2 notes the remaining quasi-identifiers (14,920 sq ft, NN, double drive-thru, hard corner,
`lease_start 2000-09-30`, six 5-year options, 1.9 acres, 76 spaces) resolve to one parcel with routine
assessor work.

**This is an owner decision requiring counsel, not an agent action.** No file was modified and no
history was rewritten. Note that removal from a public repo is best-effort — forks, clones and the
GitHub events archive persist.

Related: the plan asserted "legal sanity scan in CI" as the mitigation. **Verified absent** —
no `scripts/legal/`, no `.legal-deny-list.yaml`, and no legal gate in any of the four workflows.

---

## Structural findings accepted without independent re-derivation

- **Leased fee vs fee simple (r2 M4).** `NNLeaseRenewalOption` holds `count` and `years_each` and **no
  option rent field**. With six 5-year options running to ~2060, a tenant holding flat or capped option
  rent owns the reversion, and every dollar of modelled "gap" accrues to the tenant. The plan reinvents
  an established appraisal distinction and loses its treatment. **This alone invalidates the thesis for
  any asset with unpriced options.**
- **Land residual inverted (r1 M11).** A teardown asset has near-zero achievable rent in the existing
  shell; the framework returns a large negative gap and calls it over-rented — the opposite of correct,
  and most confidently on the assets #90 most wants to find.
- **Circular import (r1 M7).** `property/__init__` eagerly re-exports; `property/value_gap` →
  `modules/net_lease/cap_rate_model` → `property/confidence` closes a cycle. A Phase 1 placement
  decision that detonates in Phase 3.
- **Asking prices are not transactions (r1 M3).** The calibration set is broker asks, which are
  systematically tighter than closes and biased *differently by structure*. Confidence labels
  communicate variance, not bias.
- **Feasibility gates check the wrong things (r2 M12).** Zoning permitted-use, the lease's own
  `exclusivity: true` 500-ft covenant, recorded deed restrictions, ROFR, Phase I ESA, ADA
  path-of-travel, flood and stormwater are all unmodelled. The exclusive-use covenant is *in the file*
  and the module built to find constraints does not read it.
- **Standards section is wrong (r2 M14).** USPAP governs appraisal practice in the US, and the
  Interagency Guidelines define "evaluation" as a bounded non-appraisal product. "No standard
  applicable" is what enables downstream misuse. No new return type carries a disclaimer field and the
  test plan has no disclaimer test.
- **Gap is structurally biased positive (r2 M10).** A contracted cash flow is compared undiscounted to
  a speculative one 18–36 months out; `market_cap` is one undefined rate for both legs; drag omits
  carry (taxes, insurance, reassessment); no vacancy factor; and cap uncertainty at n≈6 spans 13.3%,
  so any gap under ~20% of income value is inside model noise.

---

## Required before re-review

1. **Phase 0** — disclosure triage with counsel; publication rule with a k-anonymity floor; a working
   legal scan in *this* repo's CI with a test proving it fails on the current file.
2. Decompose the identity: `rent_gap` as the primary screen at a single cap; `cap_gap` separate and
   separately labelled. Test: equal rents, zero drag → `rent_gap == 0` exactly.
3. Occupancy-cost-ratio gate in **Phase 1**, hard-blocking a positive gap above a sector threshold.
4. Single declared NOI basis, with offering-vs-owner reconciliation and a matched cap table.
5. Option-rent fields on `NNLeaseRenewalOption`; `value_gap` refuses without them; output renamed to
   name the leased-fee/fee-simple spread.
6. Asset-class-conditional traffic score with a sign-asserting numeric test.
7. Gate ledger — IMPLEMENTED / NOT_IMPLEMENTED, where NOT_IMPLEMENTED forces `NOT_DOCUMENTED`.
8. Disclaimer / method / intended-use / intended-user on every value-bearing type, with tests.
9. Governance clause: research lead only; no tenant-facing action on a modelled gap.

## What survived

The discovery-first work (it caught #32's stale LOC count and the absent legal scan), the five-level
`Confidence` taxonomy, the ACTUAL-never-recomputed rule, and `rent_benchmark` refusing below N=3.
The structure is sound; the content is not yet safe to build.
