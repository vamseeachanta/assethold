# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/family-dollar-valuation-model/spec.md

> Created: 2025-10-11
> Version: 1.0.0

## Technical Requirements

### Location Scoring Algorithm

**Multi-Factor Weighted Scoring System (0-100 scale):**

1. **Traffic/VPD Score (30% weight)**
   - VPD >= 40,000: 30 points
   - VPD 30,000-39,999: 24 points
   - VPD 20,000-29,999: 18 points
   - VPD 10,000-19,999: 12 points
   - VPD < 10,000: 6 points

2. **Intersection Quality (25% weight)**
   - Signalized corner with median cut: 25 points
   - Signalized corner: 20 points
   - Unsignalized corner: 15 points
   - Mid-block with left turn lane: 10 points
   - Mid-block standard: 5 points

3. **Demographics Score (20% weight)**
   - Population (3-mile): >100K = 10 pts, 50-100K = 7 pts, <50K = 4 pts
   - Income (3-mile avg): >$80K = 10 pts, $60-80K = 7 pts, <$60K = 4 pts

4. **Visibility & Access (15% weight)**
   - Monument sign + excellent visibility: 15 points
   - Good visibility, standard signage: 10 points
   - Limited visibility or poor signage: 5 points

5. **Competition Density (10% weight)**
   - No dollar stores within 1 mile: 10 points
   - 1 competitor within 1 mile: 7 points
   - 2+ competitors within 1 mile: 3 points

### VPD Analysis Framework

**Data Collection Requirements:**
- Primary intersection VPD count
- Secondary street VPD (if applicable)
- Peak hour traffic patterns
- Directional flow analysis

**VPD Thresholds:**
- **Excellent:** 40,000+ VPD (high-traffic urban arterial)
- **Good:** 30,000-39,999 VPD (strong suburban arterial)
- **Average:** 20,000-29,999 VPD (moderate traffic)
- **Fair:** 10,000-19,999 VPD (low-traffic location)
- **Poor:** <10,000 VPD (marginal location)

**Traffic Pattern Evaluation:**
- Morning rush (7-9am) patterns
- Evening rush (4-7pm) patterns
- Weekend traffic assessment
- Ingress/egress quality rating (easy/moderate/difficult)

### Tenant Creditworthiness Assessment

**Family Dollar Risk Factors (Post-PE Sale):**

1. **Corporate Financial Health**
   - PE sale price: $1B (down from $9B acquisition in 2015)
   - Market share erosion (90%+ overlap with Walmart customers)
   - Store closure risk assessment
   - Credit rating: Monitor for downgrade

2. **Lease Strength Scoring (0-100)**
   - Years remaining: >10yrs = 30pts, 5-10yrs = 20pts, <5yrs = 10pts
   - Renewal options: 4+ options = 25pts, 2-3 options = 15pts, 0-1 = 5pts
   - Rent increases: 10%+ = 20pts, 5-10% = 15pts, <5% = 10pts
   - Guarantee: Corporate guarantee = 25pts, Store-level = 10pts

3. **Renewal Probability**
   - Recent renewal exercised: +High probability
   - Strong sales location (high VPD, good demographics): +Moderate probability
   - Marginal location or poor performance: -Low probability

### Cap Rate Adjustment Methodology

**Base Cap Rate:** Market comparable NNN convenience store cap rate (typically 7.0-8.5%)

**Adjustment Factors:**

1. **Location Quality Adjustment**
   - Location score 90-100: -0.50% (premium location)
   - Location score 80-89: -0.25%
   - Location score 70-79: 0.00% (market rate)
   - Location score 60-69: +0.25%
   - Location score <60: +0.50% (higher risk)

2. **Tenant Risk Adjustment**
   - Lease strength 90-100: -0.25%
   - Lease strength 80-89: 0.00%
   - Lease strength 70-79: +0.25%
   - Lease strength <70: +0.50%
   - Recent PE sale concern: +0.25% additional

3. **Lease Term Adjustment**
   - >10 years remaining: -0.25%
   - 5-10 years: 0.00%
   - 3-5 years: +0.25%
   - <3 years: +0.50%

**Adjusted Cap Rate Formula:**
```
Adjusted Cap Rate = Base Cap Rate + Location Adjustment + Tenant Risk Adjustment + Lease Term Adjustment
```

### Valuation Calculator

**Fair Market Value Calculation:**
```python
Fair_Market_Value = NOI / Adjusted_Cap_Rate

Where:
- NOI = Annual_Rent (for NN/NNN leases, assumes minimal landlord expenses)
- Adjusted_Cap_Rate = calculated using methodology above
```

**Valuation Range:**
```python
Low_Value = NOI / (Adjusted_Cap_Rate + 0.25%)
Base_Value = NOI / Adjusted_Cap_Rate
High_Value = NOI / (Adjusted_Cap_Rate - 0.25%)
```

**Investment Recommendation Logic:**
```python
if Asking_Price < Low_Value:
    recommendation = "Strong Buy - Below fair value range"
elif Asking_Price <= Base_Value:
    recommendation = "Buy - Within fair value range"
elif Asking_Price <= High_Value:
    recommendation = "Fair - At upper range, negotiate lower"
else:
    recommendation = "Pass - Overpriced, significant downside risk"
```

## Approach Options

### Option A: Python-Only Calculator (Selected)

**Pros:**
- Consistent with existing tech stack (Python/NumPy)
- Easy integration with Plotly visualizations
- Can generate HTML reports
- Reusable for other convenience store evaluations

**Cons:**
- Requires Python environment
- Less accessible for quick calculations

**Rationale:** Aligns with existing investment analysis infrastructure and enables automated report generation

### Option B: Excel-Based Model

**Pros:**
- More accessible to non-technical users
- Familiar interface
- Easy to share and modify

**Cons:**
- Limited visualization capabilities
- Harder to maintain consistency
- No automated report generation
- Doesn't integrate with existing Python tools

**Rationale:** Rejected due to tech stack inconsistency

## External Dependencies

**None required** - all calculations use standard Python libraries:
- **NumPy:** Numerical calculations (already in use)
- **Plotly:** Visualizations (already in use)
- **PyYAML:** Configuration files (already in use)

## File Structure

```
modules/
└── real_estate/
    └── convenience_store/
        ├── valuation_model.py        # Core valuation engine
        ├── location_scorer.py        # Location scoring logic
        ├── cap_rate_adjuster.py      # Cap rate adjustment calculator
        ├── report_generator.py       # HTML report generator
        └── config/
            ├── market_cap_rates.yaml # Market cap rate database
            └── scoring_weights.yaml  # Configurable scoring weights
```

## Integration Points

1. **Property Data Input:** Manual entry via YAML configuration file
2. **Output Storage:** `re_cre/conv_store/{property_name}/analysis/valuation_report.html`
3. **Comparable Properties:** Reference data from other Family Dollar evaluations in repository
4. **Market Data:** Manual input of market cap rates by region

## Performance Requirements

- Calculation time: <1 second for single property
- Report generation: <5 seconds including visualizations
- Support for batch analysis: 10+ properties in single run

## Data Validation

- VPD: Must be positive integer
- Demographics: Population and income must be positive
- Cap rates: Must be between 4% and 15% (sanity check)
- Lease terms: Years remaining must be positive
- Location scores: Auto-clamped to 0-100 range
