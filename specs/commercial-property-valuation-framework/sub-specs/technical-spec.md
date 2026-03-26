# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/commercial-property-valuation-framework/spec.md

> Created: 2025-10-26
> Version: 1.0.0

## Technical Requirements

### Universal Location Scoring Engine

**Core Scoring Architecture:**

The framework uses a **weighted scoring system (0-100 scale)** with configurable category-specific weights:

```python
Total_Location_Score = Σ(Factor_Score[i] * Weight[i]) for all factors

Where weights must sum to 100%
```

**Universal Scoring Factors (All Property Types):**

1. **Traffic/VPD Score (Default 30% weight)**
   - Configurable VPD thresholds by category
   - Example Retail thresholds:
     - VPD >= 40,000: 30 points
     - VPD 30,000-39,999: 24 points
     - VPD 20,000-29,999: 18 points
     - VPD 10,000-19,999: 12 points
     - VPD < 10,000: 6 points

2. **Intersection/Access Quality (Default 25% weight)**
   - Signalized corner with median cut: 25 points
   - Signalized corner: 20 points
   - Unsignalized corner: 15 points
   - Mid-block with left turn lane: 10 points
   - Mid-block standard: 5 points

3. **Demographics Score (Default 20% weight)**
   - Configurable radius (3-mile, 5-mile, 10-mile)
   - Population density scoring
   - Income/wealth scoring
   - Age demographics (category-dependent)
   - Education levels (office/medical)

4. **Visibility & Signage (Default 15% weight)**
   - Monument sign + excellent visibility: 15 points
   - Good visibility, standard signage: 10 points
   - Limited visibility or poor signage: 5 points

5. **Competition Analysis (Default 10% weight)**
   - Category-specific competition definition
   - Distance-weighted competition scoring
   - Market saturation assessment

**Category-Specific Factors (Additional 0-20% weight allocation):**

- **QSR:** Drive-thru lanes (1 lane: 5 pts, 2 lanes: 10 pts), parking spaces (>20: 10 pts)
- **Medical:** Hospital proximity (0-1 mile: 15 pts, 1-3 miles: 10 pts), insurance acceptance (Medicare: 5 pts)
- **Office:** Nearby employment centers (within 1 mile: 15 pts), public transit access (yes: 10 pts)
- **Retail:** Anchor tenant proximity (within 500 ft: 15 pts), foot traffic (high: 10 pts)

### Category Definition System

**YAML Category Template Structure:**

```yaml
category:
  name: "Quick Service Restaurant"
  short_code: "QSR"

  scoring_weights:
    vpd_traffic: 0.30
    intersection_quality: 0.25
    demographics: 0.15
    visibility: 0.10
    competition: 0.10
    category_specific: 0.10

  vpd_thresholds:
    excellent: 40000
    good: 30000
    average: 20000
    fair: 10000

  demographic_radius: 3  # miles
  demographic_factors:
    - population_total
    - median_household_income
    - population_age_25_44  # target demographic

  category_specific_factors:
    - name: "drive_thru_lanes"
      scoring:
        2: 10
        1: 5
        0: 0
    - name: "parking_spaces"
      scoring:
        "30+": 10
        "20-29": 7
        "10-19": 4
        "<10": 0

  competition_definition:
    - category: "QSR"
      radius_miles: 1.0
      max_competitors_excellent: 2
      max_competitors_good: 4

  cap_rate_range:
    min: 6.5
    max: 8.5
    baseline: 7.5

  lease_type: "NNN"

  risk_factors:
    - "Franchise failure rate"
    - "Brand strength deterioration"
    - "Changing consumer preferences"
```

**Pre-Configured Categories:**

1. **Retail - Convenience Stores** (Family Dollar, Dollar General, 7-Eleven)
2. **Retail - Automotive** (AutoZone, O'Reilly, NAPA)
3. **QSR - Drive-Thru** (KFC, McDonald's, Taco Bell)
4. **QSR - No Drive-Thru** (Chipotle, Panera)
5. **Medical - Urgent Care**
6. **Medical - Dialysis Centers**
7. **Medical - Dental Offices**
8. **Financial - Bank Branches**
9. **Office - Professional Services**
10. **Industrial - Warehouse/Distribution**

### Property Comparison Database Schema

**Data Model:**

```python
Property = {
    "property_id": str,  # UUID
    "category": str,     # References category template
    "location": {
        "address": str,
        "city": str,
        "state": str,
        "zip": str,
        "lat": float,
        "lon": float
    },
    "financial": {
        "annual_rent": float,
        "noi": float,
        "asking_price": float,
        "price_per_sf": float,
        "building_sf": int
    },
    "lease": {
        "type": str,  # NNN, NN, MG, Ground
        "years_remaining": float,
        "renewal_options": int,
        "rent_increases": str,  # "10% every 5 years"
        "guarantee_type": str   # Corporate, Store-level, None
    },
    "location_data": {
        "vpd": int,
        "intersection_type": str,
        "visibility_rating": str,
        "demographics": {
            "population_3mi": int,
            "median_income_3mi": float,
            "age_distribution": dict
        }
    },
    "category_specific": dict,  # Flexible for category factors
    "scores": {
        "location_score": float,
        "lease_strength_score": float,
        "tenant_credit_score": float,
        "overall_quality_score": float
    },
    "valuation": {
        "base_cap_rate": float,
        "adjusted_cap_rate": float,
        "fair_market_value": float,
        "valuation_range": {
            "low": float,
            "base": float,
            "high": float
        }
    },
    "metadata": {
        "evaluation_date": datetime,
        "analyst": str,
        "data_sources": list
    }
}
```

**Database Storage Options:**

- **Phase 1 (MVP):** CSV files with JSON for nested structures
- **Phase 2:** SQLite local database
- **Phase 3:** PostgreSQL for multi-user access

**Query Requirements:**

```python
# Find comparable properties
find_comparables(
    category="QSR",
    state="TX",
    vpd_range=(30000, 50000),
    limit=10
)

# Calculate percentile rankings
calculate_percentile(
    property_id="abc-123",
    metric="location_score",
    comparison_set="category_state"  # or "category_national"
)

# Portfolio analytics
portfolio_summary(
    property_ids=["abc-123", "def-456", ...],
    sort_by="overall_quality_score",
    filters={"state": "TX", "category": "QSR"}
)
```

### Cap Rate Adjustment Methodology

**Base Cap Rate Determination:**

```python
Base_Cap_Rate = lookup_market_cap_rate(
    category=property.category,
    region=property.location.state,
    lease_type=property.lease.type
)
```

**Market Cap Rate Database (YAML):**

```yaml
market_cap_rates:
  QSR:
    NNN:
      national_average: 7.5
      by_region:
        northeast: 7.25
        southeast: 7.75
        midwest: 7.50
        southwest: 7.60
        west: 7.00
  Retail_Convenience:
    NNN:
      national_average: 8.0
      by_region:
        northeast: 7.75
        southeast: 8.25
```

**Adjustment Calculation:**

```python
# Location Quality Adjustment
def location_adjustment(location_score):
    if location_score >= 90: return -0.50
    elif location_score >= 80: return -0.25
    elif location_score >= 70: return 0.00
    elif location_score >= 60: return +0.25
    else: return +0.50

# Tenant Risk Adjustment
def tenant_risk_adjustment(lease_strength_score, tenant_credit_score):
    combined_score = (lease_strength_score + tenant_credit_score) / 2

    if combined_score >= 90: return -0.25
    elif combined_score >= 80: return 0.00
    elif combined_score >= 70: return +0.25
    else: return +0.50

# Lease Term Adjustment
def lease_term_adjustment(years_remaining):
    if years_remaining > 10: return -0.25
    elif years_remaining >= 5: return 0.00
    elif years_remaining >= 3: return +0.25
    else: return +0.50

# Final Adjusted Cap Rate
Adjusted_Cap_Rate = (
    Base_Cap_Rate +
    location_adjustment(scores.location_score) +
    tenant_risk_adjustment(scores.lease_strength_score, scores.tenant_credit_score) +
    lease_term_adjustment(lease.years_remaining)
)
```

### Valuation Calculator

**Fair Market Value Calculation:**

```python
def calculate_valuation(property):
    noi = property.financial.noi
    adjusted_cap = property.valuation.adjusted_cap_rate

    # Base valuation
    base_value = noi / adjusted_cap

    # Valuation range (±0.25% cap rate)
    low_value = noi / (adjusted_cap + 0.0025)
    high_value = noi / (adjusted_cap - 0.0025)

    return {
        "base": base_value,
        "low": low_value,
        "high": high_value,
        "confidence_interval_pct": ((high_value - low_value) / base_value) * 100
    }
```

**Investment Recommendation Logic:**

```python
def generate_recommendation(asking_price, valuation):
    discount_pct = ((valuation["base"] - asking_price) / valuation["base"]) * 100

    if asking_price < valuation["low"]:
        return {
            "recommendation": "Strong Buy",
            "rationale": f"Priced {discount_pct:.1f}% below fair value range",
            "confidence": "High"
        }
    elif asking_price <= valuation["base"]:
        return {
            "recommendation": "Buy",
            "rationale": f"Within fair value range, {discount_pct:.1f}% discount to base",
            "confidence": "Medium-High"
        }
    elif asking_price <= valuation["high"]:
        return {
            "recommendation": "Fair - Negotiate",
            "rationale": f"At upper range, seek {discount_pct:.1f}% reduction",
            "confidence": "Medium"
        }
    else:
        return {
            "recommendation": "Pass",
            "rationale": f"Overpriced by {abs(discount_pct):.1f}%, significant downside risk",
            "confidence": "High"
        }
```

### Benchmarking Analysis Engine

**Percentile Ranking Calculation:**

```python
def calculate_percentile(property_id, metric, comparison_set):
    # Load comparison properties
    comparables = load_comparison_set(
        category=property.category,
        scope=comparison_set  # "state", "region", "national"
    )

    # Extract metric values
    values = [p[metric] for p in comparables]
    subject_value = property[metric]

    # Calculate percentile
    percentile = (sum(v < subject_value for v in values) / len(values)) * 100

    return {
        "percentile": percentile,
        "subject_value": subject_value,
        "dataset_mean": mean(values),
        "dataset_median": median(values),
        "dataset_std": std(values),
        "comparison_count": len(values)
    }
```

**Comparable Property Identification:**

```python
def find_comparables(subject_property, criteria, max_results=10):
    candidates = query_database(
        category=subject_property.category,
        state=criteria.get("state_match", True) and subject_property.location.state
    )

    # Score similarity
    for candidate in candidates:
        similarity_score = 0

        # VPD similarity (±20%)
        vpd_diff = abs(candidate.vpd - subject_property.vpd) / subject_property.vpd
        if vpd_diff < 0.20:
            similarity_score += 30

        # Demographics similarity
        income_diff = abs(candidate.demographics.median_income - subject_property.demographics.median_income) / subject_property.demographics.median_income
        if income_diff < 0.15:
            similarity_score += 20

        # Lease term similarity
        term_diff = abs(candidate.lease.years_remaining - subject_property.lease.years_remaining)
        if term_diff < 2:
            similarity_score += 20

        # Location score similarity
        location_diff = abs(candidate.scores.location_score - subject_property.scores.location_score)
        if location_diff < 10:
            similarity_score += 30

        candidate.similarity_score = similarity_score

    # Return top matches
    return sorted(candidates, key=lambda c: c.similarity_score, reverse=True)[:max_results]
```

### Risk Modeling & Scenario Analysis

**Scenario Definition:**

```python
Scenario = {
    "name": str,
    "probability": float,  # 0.0 to 1.0
    "adjustments": {
        "rent_reduction_pct": float,
        "vacancy_months": int,
        "releasing_costs": float,
        "cap_rate_adjustment": float
    }
}
```

**Probability-Weighted Valuation:**

```python
def calculate_risk_adjusted_value(base_valuation, scenarios):
    weighted_value = base_valuation * scenarios[0].probability  # Base scenario

    for scenario in scenarios[1:]:
        # Apply scenario adjustments
        adjusted_noi = base_noi * (1 - scenario.adjustments.rent_reduction_pct)
        adjusted_noi -= (scenario.adjustments.vacancy_months / 12) * base_noi
        adjusted_noi -= scenario.adjustments.releasing_costs

        adjusted_cap = base_cap_rate + scenario.adjustments.cap_rate_adjustment
        scenario_value = adjusted_noi / adjusted_cap

        weighted_value += scenario_value * scenario.probability

    return weighted_value
```

**Example Scenario Analysis:**

```python
scenarios = [
    {
        "name": "Base Case - Lease Renewed",
        "probability": 0.70,
        "adjustments": {
            "rent_reduction_pct": 0.00,
            "vacancy_months": 0,
            "releasing_costs": 0,
            "cap_rate_adjustment": 0.00
        }
    },
    {
        "name": "Lease Not Renewed - 1 Year Vacancy",
        "probability": 0.20,
        "adjustments": {
            "rent_reduction_pct": 0.10,  # New tenant at 10% lower rent
            "vacancy_months": 12,
            "releasing_costs": 25000,
            "cap_rate_adjustment": 0.50  # Increased risk
        }
    },
    {
        "name": "Tenant Bankruptcy - 2 Year Vacancy",
        "probability": 0.10,
        "adjustments": {
            "rent_reduction_pct": 0.20,
            "vacancy_months": 24,
            "releasing_costs": 50000,
            "cap_rate_adjustment": 1.00
        }
    }
]
```

## Approach Options

### Option A: Modular Python Framework (Selected)

**Architecture:**
```
modules/
└── valuation/
    ├── core/
    │   ├── scoring_engine.py      # Universal scoring calculator
    │   ├── cap_rate_adjuster.py   # Cap rate adjustment logic
    │   ├── valuation_calculator.py # Fair market value calculations
    │   └── scenario_analyzer.py   # Risk modeling
    ├── categories/
    │   ├── category_loader.py     # Load YAML category definitions
    │   ├── retail.yaml            # Retail category template
    │   ├── qsr.yaml               # QSR category template
    │   └── medical.yaml           # Medical category template
    ├── database/
    │   ├── property_database.py   # Property CRUD operations
    │   ├── query_engine.py        # Comparison queries
    │   └── benchmarking.py        # Percentile calculations
    └── reporting/
        ├── report_generator.py    # HTML report creation
        └── visualizations.py      # Plotly chart generation
```

**Pros:**
- Consistent with existing AssetHold tech stack (Python/Poetry)
- Easy integration with existing real estate module
- Plotly visualization support
- YAML configuration aligns with existing patterns
- Reusable across all property types
- Extensible for future categories

**Cons:**
- Requires Python environment
- Initial setup more complex than spreadsheet

**Rationale:** Aligns perfectly with AssetHold's existing architecture, enables automated report generation, and provides foundation for advanced analytics

### Option B: Excel-Based Template System

**Pros:**
- Immediately accessible to all users
- Familiar interface
- Easy manual adjustments
- No technical setup required

**Cons:**
- Limited visualization capabilities
- Difficult to maintain consistency across multiple properties
- No automated benchmarking against database
- Cannot scale to portfolio-level analytics
- Doesn't integrate with existing Python codebase

**Rationale:** Rejected due to scalability limitations and tech stack inconsistency

### Option C: Web Application (Future Phase)

**Pros:**
- Most user-friendly interface
- Cloud-based collaboration
- Real-time updates
- Mobile access

**Cons:**
- Significant development effort
- Infrastructure costs
- Beyond current scope

**Rationale:** Consider for Phase 2 after core framework proven

## External Dependencies

**Required:**
- **NumPy:** Numerical calculations (already in use)
- **Plotly:** Interactive visualizations (already in use)
- **PyYAML:** Category configuration files (already in use)
- **pandas:** DataFrame operations for database queries (already in use)

**Optional:**
- **scikit-learn:** For future machine learning features (percentile calculations, outlier detection)
- **geopy:** For distance calculations between properties
- **pytest:** Testing framework (already in use)

## Integration Points

1. **Existing Real Estate Module:** Integrate into `modules/real_estate/` as new `valuation/` submodule
2. **Configuration System:** Leverage existing YAML configuration patterns
3. **Report Generation:** Extend existing HTML report generation capabilities
4. **Data Storage:** Initially use CSV/JSON, migrate to SQLite in Phase 2
5. **Category Templates:** Store in `modules/valuation/categories/` directory

## Performance Requirements

- **Single property evaluation:** <2 seconds
- **Portfolio comparison (50 properties):** <10 seconds
- **Benchmarking query (1 property vs 100 comparables):** <1 second
- **Report generation with 5 Plotly charts:** <5 seconds
- **Database queries:** <500ms for typical queries

## Data Validation

**Property Input Validation:**
- VPD: Positive integer, range 0-200,000 (sanity check)
- Demographics: Population and income must be positive
- Cap rates: Between 4% and 15% (extreme values flagged)
- Lease terms: Years remaining must be positive, <30 years
- Location scores: Auto-clamped to 0-100 range
- Financial: Annual rent and NOI must be positive

**Category Template Validation:**
- Weights must sum to 100%
- All threshold values must be positive
- Cap rate ranges must be valid (min < max)
- Required fields present for category type

**Database Integrity:**
- No duplicate property_ids
- All required fields populated
- Foreign key constraints (category must exist)
- Date ranges logical (evaluation_date not in future)
