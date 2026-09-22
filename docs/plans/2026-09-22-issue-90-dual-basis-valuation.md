# Plan for #90: Dual-basis property valuation — rental basis, location/traffic basis, and the value gap

> **Status:** REJECTED at adversarial review 2026-09-22 — revision required, NOT approved for implementation
> **Complexity:** T3 (cross-module: `property/` + `modules/net_lease/`, introduces a data contract and a calibration corpus)
> **Date:** 2026-09-22
> **Issue:** https://github.com/vamseeachanta/assethold/issues/90
> **Client:** N/A
> **Lane:** lane:claude
> **Review artifacts:** [`reviews/2026-09-22-plan-90-adversarial-review.md`](reviews/2026-09-22-plan-90-adversarial-review.md) — r1 REJECT (12 MAJOR), r2 REJECT (16 MAJOR)
> **⚠ Do not implement from this document.** Five defects were verified first-hand: the core identity returns a non-zero gap on an at-market asset; the rent benchmark calls the repo's only asset under-rented when it is over-rented at 14.4% occupancy cost; two NOI bases differ by $240,745 of value; the traffic score is sign-inverted for retail; and the asserted CI legal scan does not exist in this repo.

---

## Resource Intelligence Summary

### Existing repo code

- **Found:** `src/assethold/modules/net_lease/analysis.py` — `cap_rate_sensitivity(noi, low, high, step)`
  returns implied value across a cap-rate *range*; `compare_nnn_vs_modified_gross()` compares expense
  burden between structures; `lease_expiration_timeline()` builds rent-at-risk by year.
  **Gap:** nothing *selects* a cap rate for a given asset. The sensitivity table is an input to
  judgement, not an output of a model.
- **Found:** `src/assethold/modules/net_lease/net_lease_model.py` (293 LOC) — `NNLeaseProperty` with
  `NNLeaseTenant` (credit_profile, guaranty, lease_type), `NNLeaseFinancials` (rent_psf_annual, noi),
  `NNLeaseRenewalOption`, `NNLeaseDemographics`, YAML round-trip via `to_yaml`/`from_yaml`.
  **The model already carries `aadt_primary_road`, `aadt_secondary_road`, `aadt_highway` and
  demographics at 1/3/5-mile radii.** The inputs for location-basis rent are already in the schema and
  unused by any valuation path.
- **Found:** `src/assethold/property/spatial_factors.py` — AADT → `TrafficLevel` enum
  (LOW <5k / MODERATE 5–25k / HIGH 25–60k / VERY_HIGH >60k) → `traffic_score` at weight 0.20 in a
  composite. **Gap:** the composite feeds only `valuation.py`'s ±15% adjustment on a comp-anchored
  base. There is no traffic → achievable-rent path.
- **Found:** `src/assethold/property/valuation.py` — screening model:
  `adjusted_mid = base_value × (1 + spatial_adjustment_pct/100)`, band ±5/10/20% by confidence.
  **Gap:** base value is a comp median or tax assessment. Rent is never an input. This is a
  *sales-comparison* approach with a GIS overlay; the income approach is absent from `property/`.
- **Found:** `src/assethold/modules/multifamily/multifamily_analysis.py:189` —
  `sale_proceeds = NOI[-1] / project['exit']['Cap_Rate'] * 100`. The only income-approach arithmetic in
  the repo, hard-coded to a config-supplied exit cap, multifamily-only, not reusable.
- **Found:** `data/cre/net_lease/nola-pharmacy-retail-nn-2025.yaml` — the abstraction precedent for this
  repo. Carries `# Data abstracted per data-room confidentiality obligations`, `entity name abstracted`,
  `tenant_type: national_pharmacy_chain` rather than a brand. **This is the pattern all calibration data
  must follow**, because the repo is public.
- **Gap (build from scratch):** confidence labelling, cap-rate selection, rent benchmarking against a
  comp set, parking/occupancy feasibility gates, traffic→rent mapping, value-gap synthesis, and the
  reference-table corpus.

### Related issues

| Issue | Finding |
|---|---|
| [#78](https://github.com/vamseeachanta/assethold/issues/78) | Parent epic — "underwrite real assets end to end … net-lease & property due diligence". #90 sits under it. |
| [#32](https://github.com/vamseeachanta/assethold/issues/32) | `status:plan-approved`. Lists "NNN vs modified gross comparison" and "cap rate sensitivity" as *needed* for net_lease. **Both are implemented.** Issue records net_lease at 316 LOC; actual is 602. **The issue body is stale** — discovery-first fired here. #90 begins where #32's net_lease scope ends. Recommend commenting on #32 to record that its net_lease criteria are met. |
| [#54](https://github.com/vamseeachanta/assethold/issues/54) | GIS timelapse at "appraisal-style 2/5/10-mile radii". **Conflict to resolve:** the existing `NNLeaseDemographics` uses **1/3/5**-mile radii. Phase 2 must pick one convention or explicitly carry both; silently mixing them would corrupt trade-area comparisons. |
| [#74](https://github.com/vamseeachanta/assethold/issues/74) | `status:needs-plan` — asset-financial database. The reference tables in #90 should not pre-empt its schema; keep them file-local YAML under `data/cre/reference/`. |

### Standards

Not applicable — no engineering standard governs CRE valuation method here. The nearest governing
convention is the appraisal distinction between the **income approach**, the **sales-comparison
approach** and the **cost approach**; this plan implements the first and benchmarks against the second.
Output is explicitly a screening estimate, not a certified appraisal — `valuation.py`'s existing
`_DISCLAIMER` text is the precedent and must be carried onto every new output.

### Repo conventions consulted

- `docs/HTML_REPORTING_STANDARDS.md` — governs the Phase 3 report. **Note:** it mandates *interactive*
  plots and names Plotly / Bokeh / Altair / D3, explicitly disallowing static matplotlib or seaborn
  exports. Phase 3 must either use one of those libraries or establish that a self-contained
  hand-rolled interactive SVG satisfies the intent; this is a conflict to settle in Phase 3, not to
  discover during it.
- `src/assethold/property/valuation_report.py` — existing report structure and the disclaimer pattern.
- `pyproject.toml` / `pytest.ini` — test layout and coverage gate.

---

## Design

### The identity

```
income_value    = NOI / cap_rate(lease_structure, credit_tier, term_remaining)
location_value  = achievable_rent(traffic, demographics, use) x leasable_sf / market_cap
                  - retenanting_drag(downtime_months, ti_psf, commission)
value_gap       = location_value - income_value
```

`value_gap > 0` identifies a property worth more than the rent it pays. Ranking a portfolio by gap,
normalised by income value, is the screen.

### Phase 1 — rental basis

**`src/assethold/property/confidence.py`**

```python
class Confidence(Enum):
    ACTUAL         = "actual"          # an executed instrument states it
    CONTRACTUAL    = "contractual"     # a future amount fixed by an executed instrument
    DOCUMENTED     = "documented"      # an external source states it, with a citation
    DERIVED        = "derived"         # arithmetic from retrieved figures - NOT a reported number
    NOT_DOCUMENTED = "not_documented"  # searched for, not found. Never inferred
```

`Valued[T]` wraps a figure with its `Confidence` and a `source` string. **Rule enforced in code: an
exact amount, once supplied at `ACTUAL` or `CONTRACTUAL`, is never recomputed from a rounded per-unit
figure.** This is a concrete defect that occurred in practice — a contractual $121,700 rendered as
$121,722 because annual rent was back-computed from a rounded $/sq ft. The wrapper makes the override
explicit and a test asserts it.

**`src/assethold/modules/net_lease/cap_rate_model.py`**

`select_cap_rate(lease_structure, credit_tier, term_remaining_years, asset_class) -> Valued[float]`

Base cap by credit tier, adjusted by a structure spread and a term adjustment. The structure spread is
the load-bearing new idea: **lease structure moves cap rates independently of credit.**

**`src/assethold/modules/net_lease/rent_benchmark.py`**

`benchmark_rent(contract_psf, comps: list[Comp], prototype_filter) -> RentBenchmark`

Returns over/under-rented percentage against the comp median, the comp set actually used, and its N.
**Refuses to report a percentage when N is below a floor** (proposed: 3) — returns
`NOT_DOCUMENTED` rather than a number computed from one comp.

**`data/cre/reference/`** — versioned YAML, every row carrying `source`, `as_of`, and `n`:
- `cap_spread_by_structure.yaml`
- `credit_tier_base_cap.yaml`

### Phase 2 — location basis

**`src/assethold/property/use_feasibility.py`**

Two gates, both of which have bitten in practice:

1. **Parking.** `spaces_required = ceil(ratio_per_1000sf x building_sf / 1000)` against spaces
   available. Ratios are jurisdiction-specific; ship a default table plus a per-jurisdiction override
   file. A use failing this gate is rejected with the gate named.
2. **Occupancy classification.** A change of use can trigger a fire-protection retrofit. The governing
   distinction in the model codes is whether the new use renders occupants *incapable of
   self-preservation* (an ambulatory care facility) rather than merely being "medical". Encode the
   trigger as a per-use boolean with the code citation, not as a guess.

`feasible_uses(building, site, jurisdiction) -> list[UseVerdict]` — each verdict names the binding gate
and the retrofit cost category where triggered.

**`src/assethold/property/location_rent.py`**

`achievable_rent(aadt_band, demographics, use) -> Valued[RentBand]` — reuses the existing
`TrafficLevel` enum rather than inventing a second banding.

### Phase 3 — the screen

**`src/assethold/property/value_gap.py`** — synthesis with `retenanting_drag`. Portfolio ranking, and a
self-contained HTML report per `docs/HTML_REPORTING_STANDARDS.md`.

---

## The calibration problem — stated plainly

**The evidence supporting the structure spread is low-N**: a small number of listings from a single
brokerage within a single year, for one tenant brand. It is enough to establish that the spread exists
and its direction. **It is not enough to support a national model.**

Mitigations, all mandatory:

1. Every reference row carries `n:`, `as_of:` and `source:`. A table with `n: 6` says so in-band.
2. `select_cap_rate` returns `Confidence.DERIVED` — never `DOCUMENTED` — while `n` is below a stated
   threshold, and the returned object carries the `n` that produced it.
3. The screen ranks by gap **and** displays the confidence of both legs. A large gap resting on a
   `DERIVED` cap rate is a research lead, not a conclusion, and the report must not let those look
   alike.
4. Growing the corpus is a separate, ongoing task. This plan does not gate on it.

**Design consequence:** the modules must be useful at low N. `rent_benchmark` refusing to report below
N=3 is the pattern — correct refusal beats a confident wrong number.

---

## Test plan (TDD — tests precede implementation)

| Module | Tests that must exist first |
|---|---|
| `confidence` | Round-trip; **an `ACTUAL` figure survives a per-unit recomputation attempt unchanged** (the $121,700 / $121,722 regression) |
| `cap_rate_model` | Monotonicity: absolute-NNN cap <= NN cap <= NN+ cap at equal credit and term; shorter term never yields a tighter cap; confidence degrades to `DERIVED` at low N; unknown structure raises rather than defaulting |
| `rent_benchmark` | N below floor returns `NOT_DOCUMENTED`, not 0%; empty comp set raises; over- and under-rented signs are correct |
| `use_feasibility` | A use needing more spaces than available is rejected **with the gate named**; the occupancy trigger fires on the incapable-of-self-preservation flag and not on "medical" generally |
| `location_rent` | Band ordering follows AADT band ordering; unknown use raises |
| `value_gap` | Gap sign; drag reduces location value; a `NOT_DOCUMENTED` leg propagates to the result rather than being treated as zero |

Coverage gate >= 80% on new modules, per #31 and #32 precedent.

---

## Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | **False precision.** A cap rate to two decimals from n=6 implies rigour that is not there | Confidence labels in the return type, `n` surfaced in every output, `DERIVED` while low-N |
| 2 | **Public repo leakage.** Calibration derived from private holdings could identify them | Follow the `nola-pharmacy` abstraction precedent: type not brand, no parcel IDs, no addresses for privately-held assets. **Correction, verified 2026-09-22: `scripts/legal/legal-sanity-scan.sh` does NOT exist in this repo and there is no `.legal-deny-list.yaml` here — the scan lives only in `workspace-hub`. CI here is `ci.yml`, `docs.yml`, `pages.yml`, `python-tests.yml` with no legal gate.** So this mitigation is currently unavailable and must be built, not assumed. Phase 1 must either port the scan and a deny-list into this repo's CI, or the corpus must be restricted to sources already public (broker marketing, public record) with no privately-held asset represented at all. **Decide this before the first reference row is written.** |
| 3 | **Radius convention conflict** — #54 uses 2/5/10 miles, `NNLeaseDemographics` uses 1/3/5 | Resolve before Phase 2 writes any trade-area code. Carry both explicitly or migrate one; never mix |
| 4 | Jurisdiction-specific parking ratios generalise badly across US municipalities | Ship a default table plus per-jurisdiction override; `feasible_uses` requires a jurisdiction argument and refuses a silent national default |
| 5 | Scope sprawl into #74's asset-financial database | Keep reference data as file-local YAML; no DB schema in this issue |
| 6 | Alternative-use value becomes fantasy without a real tenant | The feasibility gates are the constraint; a use with no gate verdict cannot contribute to location value |

---

## Out of scope

- Paid comparable-sales APIs (`market_data.py` limitation stands)
- A certified appraisal path — output remains a screening estimate with the existing disclaimer
- The asset-financial database (#74)
- Automated AADT retrieval from state DOT endpoints — Phase 2 consumes AADT already present on the model

---

## Phasing and review

| Phase | Deliverable | Reviewable alone? |
|---|---|---|
| 1 | Rental basis: confidence, cap-rate selection, rent benchmark, reference tables | Yes — answers "is this asset over- or under-rented, and what is it worth on its income" |
| 2 | Location basis: feasibility gates, traffic→rent | Yes |
| 3 | Value-gap synthesis, portfolio screen, HTML report | Depends on 1 and 2 |

**Recommend approving Phase 1 only**, then re-reviewing before Phase 2. Phase 1 is independently
useful, and the calibration limitation is best understood with a working Phase 1 in hand.

---

## Gate status

Draft. **T3 requires independent adversarial review before `status:plan-review`.** Self-review does not
satisfy this gate — on this repo's own record, self-review returns MINOR where independent review
returns MAJOR. Review dispatch is the next action, then user approval.

**This plan must not be self-labelled `status:plan-approved`.**
