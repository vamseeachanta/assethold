# Commercial Property Valuation Framework - Overview

> **Status:** Planning Phase - Ready for Review
> **Version:** 1.0.0
> **Created:** 2025-10-26

## What Is This?

The **Commercial Property Valuation Framework** is a comprehensive, generic system for evaluating and comparing commercial real estate investments across **all property types**. It transforms the Family Dollar-specific valuation model into a universal framework that can analyze:

- **Retail:** Family Dollar, Dollar General, 7-Eleven, AutoZone, O'Reilly
- **QSR (Quick Service Restaurants):** KFC, McDonald's, Taco Bell, Chipotle, Panera
- **Medical:** Urgent care, dialysis centers, dental offices, physical therapy
- **Financial:** Bank branches, credit unions
- **Office:** Professional services, coworking spaces
- **Industrial:** Warehouse, distribution centers

## Core Capabilities

### 1. Universal Location Scoring (0-100 Scale)

Evaluates any property type using configurable weighted factors:
- **VPD/Traffic** (30%): Vehicles per day with category-specific thresholds
- **Intersection Quality** (25%): Signalized corners, median cuts, access quality
- **Demographics** (20%): Population, income, age (configurable radius: 3/5/10 miles)
- **Visibility** (15%): Monument signs, visibility ratings, street frontage
- **Competition** (10%): Category-specific competitor density analysis
- **Category-Specific** (0-20%): Drive-thru lanes (QSR), hospital proximity (medical), etc.

### 2. Property-to-Property Comparison

**Compare one property against an entire dataset:**
- KFC in Dallas vs. all KFC properties in Texas (or nationally)
- Family Dollar vs. all Dollar stores within 50-mile radius
- Urgent care vs. all medical properties in metro area

**Outputs:**
- Percentile rankings (VPD, demographics, location score, cap rate)
- Similarity scoring to identify true comparables
- Valuation premium/discount vs. comparable average
- Investment thesis: "This KFC ranks top 15% for location quality but priced at 50th percentile - value opportunity"

### 3. Portfolio-Wide Analytics

**Mixed portfolio analysis:**
- Rank 50 properties across different categories (10 Family Dollar, 15 KFC, 8 urgent cares, etc.)
- Normalized quality scoring enables cross-category comparison
- Identify top investment opportunities regardless of property type
- Filter and sort by: location quality, financial metrics, risk scores, state, category

**Outputs:**
- Portfolio ranking dashboard with interactive visualizations
- Capital deployment prioritization
- Risk-adjusted return comparisons
- Export to CSV for further analysis

### 4. Cap Rate Adjustment Methodology

**Market-based baseline cap rates:**
- Database of cap rates by property category and region
- QSR NNN in Texas: 7.5% baseline
- Retail Convenience in Southeast: 8.25% baseline
- Medical Urgent Care in California: 7.75% baseline

**Adjustments based on property quality:**
- **Location Quality:** ±0.50% based on location score (90-100: -0.50%, <60: +0.50%)
- **Tenant Risk:** ±0.50% based on lease strength and credit (strong: -0.25%, weak: +0.50%)
- **Lease Term:** ±0.50% based on years remaining (>10 years: -0.25%, <3 years: +0.50%)

**Result:** Fair market value = NOI / Adjusted Cap Rate

### 5. Risk Scenario Analysis

**Model multiple scenarios with probabilities:**
- **Base Case (70%):** Lease renewed, business as usual
- **Downside (20%):** Lease not renewed, 1-year vacancy, 10% rent reduction
- **Worst Case (10%):** Tenant bankruptcy, 2-year vacancy, 20% rent reduction

**Outputs:**
- Probability-weighted valuation
- Risk-adjusted fair market value
- Monte Carlo simulation for uncertainty quantification
- Sensitivity analysis: how does 10% VPD decline impact valuation?

### 6. Category Definition System

**Extensible property type definitions via YAML templates:**

```yaml
category:
  name: "Quick Service Restaurant - Drive-Thru"
  short_code: "QSR-DT"

  scoring_weights:
    vpd_traffic: 0.30
    intersection_quality: 0.25
    demographics: 0.15
    category_specific: 0.10  # Drive-thru, parking

  vpd_thresholds:
    excellent: 40000
    good: 30000
    average: 20000

  category_specific_factors:
    - drive_thru_lanes: {2: 10pts, 1: 5pts, 0: 0pts}
    - parking_spaces: {30+: 10pts, 20-29: 7pts}

  cap_rate_baseline: 7.5
```

**Pre-built category templates:**
1. Retail - Convenience Stores
2. Retail - Automotive Parts
3. QSR - Drive-Thru
4. QSR - No Drive-Thru
5. Medical - Urgent Care
6. Medical - Dialysis Centers
7. Medical - Dental Offices
8. Financial - Bank Branches
9. Office - Professional Services
10. Industrial - Warehouse/Distribution

**Create custom categories:** Dialysis centers, pet stores, fitness centers, car washes, etc.

### 7. Interactive Reporting & Visualization

**Professional HTML reports with Plotly charts:**
- Location score breakdown (radar/bar chart showing each factor)
- Cap rate sensitivity analysis (how valuation changes with cap rate ±1%)
- Comparable properties scatter plot (VPD vs price, color by location score)
- Percentile ranking dashboard (how subject property ranks vs dataset)
- Portfolio comparison table (sortable, filterable)

**Export formats:**
- Standalone HTML (shareable with investors)
- CSV data exports for Excel analysis
- JSON for programmatic access

## Architecture

### Modular Python Framework

```
modules/valuation/
├── core/
│   ├── scoring_engine.py          # Universal location scoring
│   ├── cap_rate_adjuster.py       # Cap rate adjustment logic
│   ├── valuation_calculator.py    # Fair market value calculations
│   └── scenario_analyzer.py       # Risk modeling
├── categories/
│   ├── category_loader.py         # Load YAML templates
│   ├── retail-convenience.yaml    # Family Dollar, Dollar General
│   ├── qsr-drive-thru.yaml        # KFC, McDonald's
│   └── medical-urgent-care.yaml   # Urgent care centers
├── database/
│   ├── property_database.py       # Property CRUD operations
│   ├── query_engine.py            # Comparison queries
│   └── benchmarking.py            # Percentile calculations
└── reporting/
    ├── report_generator.py        # HTML report creation
    └── visualizations.py          # Plotly chart generation
```

### Database Schema (CSV → SQLite → PostgreSQL)

**Phase 1 (MVP):** CSV files for simple deployment
**Phase 2:** SQLite for efficient querying
**Phase 3:** PostgreSQL for team collaboration

**Core tables:**
- `properties` - Core property and financial data
- `categories` - Property type definitions and scoring parameters
- `location_data` - VPD, demographics, visibility, competition
- `lease_terms` - Lease agreements, renewal options, guarantees
- `scores` - Calculated location scores and percentile rankings
- `valuations` - Cap rate adjustments and fair market values
- `scenarios` - Risk scenarios for scenario analysis
- `comparables` - Property-to-property similarity mappings

## Use Cases

### Use Case 1: Evaluate Single Property

**Input:** YAML configuration with property details
```yaml
property:
  tenant_name: "KFC"
  address: "123 Main St, Dallas, TX"
  category: "QSR - Drive-Thru"
  annual_rent: 80000
  asking_price: 1000000

location:
  vpd: 35000
  intersection_type: "Signalized Corner"
  drive_thru_lanes: 1
  parking_spaces: 25
```

**Output:**
- Location score: 78/100
- Adjusted cap rate: 7.6%
- Fair market value: $1,052,632
- Recommendation: "Buy - Asking price within fair value range"
- HTML report with interactive charts

### Use Case 2: Compare Property Against Dataset

**Scenario:** Evaluating a KFC in Dallas

**Query:** Compare against all KFC properties in Texas

**Output:**
- **VPD Percentile:** 65th (this property has higher VPD than 65% of TX KFCs)
- **Location Score Percentile:** 72nd (top 28% for location quality)
- **Cap Rate Percentile:** 45th (asking cap rate is mid-range)
- **Investment Thesis:** "Above-average location quality at average pricing - modest value opportunity"

**10 Most Similar Properties:** Ranked by similarity score with VPD, demographics, lease terms

### Use Case 3: Portfolio Ranking

**Scenario:** 50 properties across mixed categories

**Output:** Ranked table showing:
1. Urgent Care, Austin TX - Quality Score: 92, Location: 95, Cap Rate: 7.8%, Recommendation: Strong Buy
2. Family Dollar, Houston TX - Quality Score: 88, Location: 87, Cap Rate: 8.1%, Recommendation: Buy
3. KFC, Dallas TX - Quality Score: 85, Location: 78, Cap Rate: 7.6%, Recommendation: Buy
...
50. Dollar General, Rural TX - Quality Score: 45, Location: 42, Cap Rate: 10.2%, Recommendation: Pass

**Filter by:** Category, State, Quality Score >80, Cap Rate <8%

### Use Case 4: Risk Scenario Analysis

**Scenario:** Family Dollar with lease expiring in 3 years

**Risk Scenarios:**
1. **Base (60%):** Lease renewed at current terms
2. **Moderate (30%):** 6-month vacancy, new tenant at 10% lower rent
3. **Severe (10%):** 18-month vacancy, 20% lower rent, $30K releasing costs

**Output:**
- Base FMV: $1,400,000
- Risk-Adjusted FMV: $1,285,000 (9% haircut for risk)
- Recommendation: "Buy if price <$1,250,000 to compensate for renewal risk"

### Use Case 5: Create Custom Property Category

**Scenario:** Evaluating dialysis centers (not a pre-built category)

**Steps:**
1. Create `medical-dialysis.yaml` category template
2. Define custom factors:
   - Hospital proximity (critical for referrals)
   - Population over 65 (target demographic)
   - Medicare Advantage penetration
   - Competition: existing dialysis centers within 5 miles
3. Set category-specific weights and cap rate baseline
4. Save template for reuse

**Result:** Can now evaluate all dialysis centers using consistent methodology

## Extensibility Patterns

### Adding a New Property Type

1. **Create category YAML template** (`categories/your-category.yaml`)
2. **Define scoring weights** appropriate for that property type
3. **Specify category-specific factors** (e.g., drive-thru lanes for QSR)
4. **Set cap rate baseline** based on market research
5. **Test with sample properties** to validate scoring
6. **Share template** with team for consistent evaluations

### Integrating External Data Sources

**Future enhancements:**
- LoopNet API for automated comparable property data
- CoStar integration for market cap rates
- DOT traffic data APIs for VPD
- Census Bureau API for demographics

**Current approach:** Manual data entry via YAML ensures data quality and understanding

## Performance Requirements

- **Single property evaluation:** <2 seconds
- **Portfolio comparison (50 properties):** <10 seconds
- **Benchmarking query (1 vs 100 comparables):** <1 second
- **HTML report generation:** <5 seconds

## Integration with AssetHold

This framework integrates into the existing AssetHold codebase:

**Location:** `modules/real_estate/valuation/`

**Dependencies:** Already in use
- NumPy (calculations)
- Plotly (visualizations)
- PyYAML (configuration)
- pandas (data operations)

**Configuration:** Extends existing YAML pattern

**Reports:** Integrates with existing HTML report generation

## Next Steps

### Immediate (This Revision)
1. Review spec for completeness
2. Clarify any ambiguous requirements
3. Refine category definitions
4. Validate scoring methodology

### Phase 1 Implementation
1. Build core scoring engine
2. Implement cap rate adjustments
3. Create CSV database structure
4. Develop valuation calculator
5. Generate basic HTML reports

### Phase 2 Enhancement
1. Add benchmarking/comparison engine
2. Implement percentile rankings
3. Build portfolio analytics
4. Create interactive dashboards

### Phase 3 Advanced Features
1. Risk scenario modeling
2. Monte Carlo simulation
3. SQLite database migration
4. Category template marketplace

## Related Specifications

- **Family Dollar Valuation Model:** @.agent-os/specs/family-dollar-valuation-model/spec.md
  - Reference implementation showing framework in action
  - Convenience store category template
  - Dollar store competition analysis

**Future property-specific specs:**
- KFC Valuation Model (QSR drive-thru)
- Urgent Care Valuation Model (Medical)
- Bank Branch Valuation Model (Financial)

## Questions for Next Revision

1. **Data sources:** Manual entry only, or plan for API integration?
2. **Geographic scope:** National database or regional focus?
3. **Comparison sets:** How many comparable properties constitute valid dataset?
4. **Category priorities:** Which property types to implement first?
5. **Risk modeling:** How sophisticated should scenario analysis be?
6. **Machine learning:** Future enhancement for predictive modeling?

---

**This framework transforms property-specific valuation into a systematic, repeatable, data-driven process applicable to any commercial property type.**
