# 2026-09-22 — Exit: #90 dual-basis valuation, plan REJECTED at adversarial review

## State on exit

| Item | State |
|---|---|
| Issue [#90](https://github.com/vamseeachanta/assethold/issues/90) | **OPEN**, `status:needs-plan`. Created this session |
| Plan `docs/plans/2026-09-22-issue-90-dual-basis-valuation.md` | **REJECTED** — do not implement from it |
| Review record `docs/plans/reviews/2026-09-22-plan-90-adversarial-review.md` | Written |
| Code | **None written.** No module, no test, no data file. The gate held |

T3 plan, two independent adversarial reviewers, fresh context, both instructed to refute.
**r1 REJECT (12 MAJOR) · r2 REJECT (16 MAJOR).** Self-review would not have found these; the repo's
own pattern (self-review MINOR, independent MAJOR) held again.

---

## ⚠ Blocker that does not belong to #90

`data/cre/net_lease/nola-pharmacy-retail-nn-2025.yaml` is **on `origin/main` in this public repo** and
carries, under a header reading `# Data abstracted per data-room confidentiality obligations`:

- exact street address, `lat`/`lon` to four decimals, `parcel_id`
- **two years of the tenant's category-level gross sales**, obtained under the lease's sales-reporting
  clause
- the owner's P&L including `debt_service_interest`

Reached origin via `9c207c1 chore(sync): auto-sync 2026-08-02` — an unattended sync, not a review gate.
Abstracting the tenant to `national_pharmacy_chain` is cosmetic once the parcel is named; the residual
quasi-identifiers (14,920 sq ft, NN, double drive-thru, hard corner, `lease_start 2000-09-30`, six
5-year options, 1.9 acres, 76 spaces) resolve to one parcel with routine assessor work.

**No file was modified and no history was rewritten — owner decision, with counsel.** Removal from a
public repo is best-effort; forks, clones and the GitHub events archive persist.

Related, verified: the plan asserted "legal sanity scan in CI" as the mitigation for this risk class.
**It does not exist here** — no `scripts/legal/`, no `.legal-deny-list.yaml`, no legal gate in any of
`ci.yml`, `docs.yml`, `pages.yml`, `python-tests.yml`.

---

## Findings verified first-hand (not taken on the reviewers' word)

1. **The core identity does not compute what the plan claims.** With contract rent equal to achievable
   rent and zero drag, a correct gap must be zero. It is not — the legs carry different denominators.
   Strong credit at market rent → **−$208,816**, read as "over-rented"; weak credit → **+$87,007**,
   read as "buy". Identical rents. The screen ranks by credit quality inverted.
2. **The rent benchmark inverts on the repo's only asset.** Occupancy cost **14.4%** of sales (FY2024),
   up from 13.1%, merchandise sales **−12.4%**. A psf benchmark sees $19.03/sq ft and says
   under-rented; the asset is over-rented. `sales_reporting: true` is in the schema and the plan never
   used it. **A false positive in exactly the direction #90 exists to find.**
3. **Two NOI bases, 8.0% apart** — $284,000 offering vs $262,934.78 owner-derived = **$240,745** of
   valuation swing at 8.75%. The plan specified neither. The NN cap premium largely *is* the landlord's
   expense burden, so pairing owner NOI with a widened cap double-counts it.
4. **`spatial_factors._score_traffic` is sign-inverted for retail** — 13,500 AADT → 0.174, 60,000 →
   0.044. A residential noise model. The plan proposed reusing it.
5. **Three inconsistent representations of one contractual rent** already committed
   ($284,000.00 / $283,927.60 / $284,004.00, spread $76.40), with no validator in
   `NNLeaseFinancials.__post_init__`.

## Structural findings accepted without re-derivation

- **Leased fee vs fee simple.** `NNLeaseRenewalOption` has no option-rent field. With six 5-year
  options to ~2060, flat or capped option rent means the tenant owns the reversion and the modelled
  gap accrues to them. **Invalidates the thesis for any asset with unpriced options.**
- Land-residual case inverted (teardown reads as over-rented). Circular import at
  `property/__init__` if `value_gap` lands in `property/`. Calibration is broker **asks**, not closes,
  with a structure-dependent bias that confidence labels cannot correct. Feasibility gates omit zoning
  use-table, the lease's own 500-ft exclusive covenant, deed restrictions, ROFR, Phase I, ADA and
  flood. Standards section wrong — USPAP and the appraisal/evaluation distinction apply. Gap is
  structurally biased positive with no minimum-detectable threshold against a 13.3% cap spread at n≈6.

Full detail with fixes: `docs/plans/reviews/2026-09-22-plan-90-adversarial-review.md`.

---

## Discovery findings worth keeping regardless of #90

- **Issue [#32](https://github.com/vamseeachanta/assethold/issues/32) is stale.** It is
  `status:plan-approved` and lists "NNN vs modified gross comparison" and "cap rate sensitivity" as
  work still needed for `net_lease`. **Both are implemented.** It records the module at 316 LOC;
  actual is 602 (50 + 259 + 293). Anyone picking up #32 today would rebuild working code.
  **Caveat before closing it:** `grep -rln "cap_rate_sensitivity\|compare_nnn_vs_modified_gross" tests/`
  returns nothing — both functions have zero direct test coverage against #32's own 80% criterion.
  **Not commented on #32 this session** — left for the owner.
- `modules/net_lease/net_lease_model.py` already carries `aadt_primary_road`, `aadt_secondary_road`,
  `aadt_highway` and 1/3/5-mile demographics. **The location inputs exist and no valuation path
  consumes them.**
- The income approach is genuinely absent from `property/` — verified, one false grep hit ("illinois").
- Radius convention conflict: [#54](https://github.com/vamseeachanta/assethold/issues/54) specifies
  2/5/10 miles; `NNLeaseDemographics` hard-codes 1/3/5. Unresolved.
- `docs/HTML_REPORTING_STANDARDS.md` mandates *interactive* plots and names Plotly / Bokeh / Altair /
  D3, disallowing static matplotlib. Any future report work must reconcile with it.

---

## Next actions, in order

1. **Disclosure triage** on the nola YAML with counsel. Blocks any new calibration data.
2. Decide: revise the plan against the nine remediation items, or narrow scope to something smaller.
3. If revising, the shape that survives review is **rent-gap at a single cap rate**, gated by
   occupancy cost, with option rent priced and the reversion date honest — not the dual-basis
   subtraction as drafted.
4. Phase 0 before any Phase 1: publication rule with a k-anonymity floor, and a working legal scan in
   this repo's CI with a test proving it fails on the current file.

## External actions this session

One: **issue #90 created on GitHub** (public), and a `status:needs-plan` label applied to it. No code
committed to any branch, no PR, no comment on any existing issue, no history rewritten, no file
deleted. Browser use was read-only against public pages.
