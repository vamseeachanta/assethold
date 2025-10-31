# Tests Specification

This is the tests coverage details for the spec detailed in @.agent-os/specs/commercial-property-valuation-framework/spec.md

> Created: 2025-10-26
> Version: 1.0.0

## Test Coverage Strategy

The commercial property valuation framework requires comprehensive testing across multiple dimensions:

1. **Unit Tests:** Individual calculation functions and scoring algorithms
2. **Integration Tests:** End-to-end property evaluation workflows
3. **Data Validation Tests:** Input data quality and constraint enforcement
4. **Comparison Tests:** Benchmarking and percentile calculation accuracy
5. **Regression Tests:** Ensure consistent valuations across code changes
6. **Performance Tests:** Query and calculation speed requirements

## Unit Tests

### Scoring Engine Tests

**Test: `test_universal_location_score_calculation()`**
- **Purpose:** Verify weighted scoring formula produces correct results
- **Test Cases:**
  - All factors at maximum (100 points expected)
  - All factors at minimum (0 points expected)
  - Mixed factors with known weights
  - Edge case: weights sum to 100%
  - Edge case: scores clamped to 0-100 range

**Test: `test_vpd_score_calculation()`**
- **Purpose:** Validate VPD threshold scoring
- **Test Cases:**
  - VPD = 50,000 → 30 points (excellent)
  - VPD = 35,000 → 24 points (good)
  - VPD = 25,000 → 18 points (average)
  - VPD = 15,000 → 12 points (fair)
  - VPD = 5,000 → 6 points (poor)
  - Edge case: VPD = 0
  - Edge case: VPD = 200,000 (extreme high)

**Test: `test_intersection_quality_scoring()`**
- **Purpose:** Verify intersection type scoring
- **Test Cases:**
  - "Signalized Corner with Median Cut" → 25 points
  - "Signalized Corner" → 20 points
  - "Unsignalized Corner" → 15 points
  - "Mid-block with Left Turn Lane" → 10 points
  - "Mid-block Standard" → 5 points
  - Invalid intersection type → error

**Test: `test_demographics_score_calculation()`**
- **Purpose:** Validate demographic scoring (population + income)
- **Test Cases:**
  - High population (>100K), high income (>$80K) → 20 points
  - Medium population (50-100K), medium income ($60-80K) → 14 points
  - Low population (<50K), low income (<$60K) → 8 points
  - Edge case: Zero population
  - Edge case: Negative income (invalid)

**Test: `test_category_specific_factor_scoring()`**
- **Purpose:** Verify category-specific factor calculations
- **Test Cases (QSR):**
  - 2 drive-thru lanes → 10 points
  - 1 drive-thru lane → 5 points
  - 0 drive-thru lanes → 0 points
  - 30+ parking spaces → 10 points
- **Test Cases (Medical):**
  - Hospital within 1 mile → 15 points
  - Hospital 1-3 miles → 10 points
  - Hospital >3 miles → 5 points

### Cap Rate Adjustment Tests

**Test: `test_location_quality_cap_rate_adjustment()`**
- **Purpose:** Verify location score influences cap rate correctly
- **Test Cases:**
  - Location score 95 → -0.50% adjustment (premium)
  - Location score 85 → -0.25% adjustment
  - Location score 75 → 0.00% adjustment (market)
  - Location score 65 → +0.25% adjustment
  - Location score 55 → +0.50% adjustment (higher risk)

**Test: `test_tenant_risk_cap_rate_adjustment()`**
- **Purpose:** Validate tenant credit and lease strength impact on cap rate
- **Test Cases:**
  - Lease strength 95, Tenant credit 95 → -0.25%
  - Lease strength 85, Tenant credit 85 → 0.00%
  - Lease strength 75, Tenant credit 70 → +0.25%
  - Lease strength 60, Tenant credit 65 → +0.50%

**Test: `test_lease_term_cap_rate_adjustment()`**
- **Purpose:** Verify remaining lease term adjustments
- **Test Cases:**
  - 12 years remaining → -0.25%
  - 7 years remaining → 0.00%
  - 4 years remaining → +0.25%
  - 2 years remaining → +0.50%
  - Edge case: 0 years remaining

**Test: `test_combined_cap_rate_adjustment()`**
- **Purpose:** Verify all adjustments combine correctly
- **Test Cases:**
  - Base 7.5% + location(-0.25%) + tenant(0.0%) + term(-0.25%) = 7.0%
  - Base 8.0% + location(+0.50%) + tenant(+0.50%) + term(+0.25%) = 9.25%
  - Edge case: Adjusted cap rate < 4% (sanity check warning)
  - Edge case: Adjusted cap rate > 15% (sanity check warning)

### Valuation Calculator Tests

**Test: `test_fair_market_value_calculation()`**
- **Purpose:** Verify FMV = NOI / Cap Rate
- **Test Cases:**
  - NOI = $100,000, Cap Rate = 8.0% → FMV = $1,250,000
  - NOI = $150,000, Cap Rate = 7.5% → FMV = $2,000,000
  - NOI = $80,000, Cap Rate = 9.0% → FMV = $888,889
  - Edge case: NOI = 0 (warning)
  - Edge case: Cap Rate = 0 (error)

**Test: `test_valuation_range_calculation()`**
- **Purpose:** Verify low/base/high valuation range
- **Test Cases:**
  - Base cap rate 8.0%:
    - Low FMV (8.25% cap) = $1,212,121
    - Base FMV (8.0% cap) = $1,250,000
    - High FMV (7.75% cap) = $1,290,323
  - Confidence interval calculation

**Test: `test_investment_recommendation_logic()`**
- **Purpose:** Validate recommendation based on asking price vs FMV
- **Test Cases:**
  - Asking $1,150,000 < Low FMV $1,200,000 → "Strong Buy"
  - Asking $1,225,000 between Low and Base → "Buy"
  - Asking $1,275,000 between Base and High → "Fair - Negotiate"
  - Asking $1,350,000 > High FMV → "Pass"

### Category Loader Tests

**Test: `test_load_category_yaml_template()`**
- **Purpose:** Verify YAML category templates load correctly
- **Test Cases:**
  - Load retail-convenience.yaml → all fields populated
  - Load qsr-drive-thru.yaml → category-specific factors present
  - Invalid YAML syntax → error with helpful message
  - Missing required fields → validation error

**Test: `test_category_weights_validation()`**
- **Purpose:** Ensure category weights sum to 100%
- **Test Cases:**
  - Valid weights summing to 1.0 → pass
  - Weights summing to 0.98 → error
  - Weights summing to 1.05 → error
  - Negative weight → error

**Test: `test_category_threshold_validation()`**
- **Purpose:** Validate category threshold values are logical
- **Test Cases:**
  - VPD thresholds in descending order → pass
  - VPD thresholds out of order → error
  - Negative thresholds → error
  - Cap rate min < max → pass
  - Cap rate min > max → error

## Integration Tests

### End-to-End Property Evaluation

**Test: `test_evaluate_family_dollar_property()`**
- **Purpose:** Complete evaluation of Family Dollar property
- **Input:** YAML configuration with all property details
- **Expected Output:**
  - Location score between 0-100
  - Adjusted cap rate within reasonable range
  - Fair market value calculated
  - Investment recommendation generated
  - HTML report created with visualizations

**Test: `test_evaluate_kfc_property()`**
- **Purpose:** Complete evaluation of KFC property with QSR category
- **Input:** YAML configuration with QSR-specific factors
- **Expected Output:**
  - QSR category template loaded
  - Drive-thru lanes factored into score
  - Parking spaces scored correctly
  - Valuation report generated

**Test: `test_evaluate_multiple_property_types()`**
- **Purpose:** Process mixed portfolio (retail, QSR, medical)
- **Input:** 10 properties across 3 categories
- **Expected Output:**
  - All 10 properties evaluated successfully
  - Category-specific scoring applied correctly
  - Normalized scores enable cross-category comparison
  - Portfolio summary report generated

### Property Comparison Workflows

**Test: `test_find_comparable_properties()`**
- **Purpose:** Identify similar properties for benchmarking
- **Input:** Subject KFC property in Dallas
- **Expected Output:**
  - 10 comparable KFC properties returned
  - All within ±20% VPD range
  - All same category (QSR)
  - Ranked by similarity score
  - Similarity breakdown provided

**Test: `test_calculate_percentile_rankings()`**
- **Purpose:** Calculate property position within dataset
- **Input:** Subject property + 100 comparable properties
- **Expected Output:**
  - VPD percentile calculated (e.g., 75th percentile)
  - Location score percentile calculated
  - Cap rate percentile calculated
  - All percentiles between 0-100

**Test: `test_portfolio_comparison_dashboard()`**
- **Purpose:** Compare multiple properties with ranking
- **Input:** 50 properties across mixed categories
- **Expected Output:**
  - All properties ranked by normalized quality score
  - Filtering by category works correctly
  - Sorting by multiple metrics works
  - Top 10 opportunities identified
  - Export to CSV successful

### Risk Scenario Analysis

**Test: `test_single_scenario_analysis()`**
- **Purpose:** Apply one risk scenario to property
- **Input:** Base property + "Lease Not Renewed" scenario
- **Expected Output:**
  - Vacancy costs applied correctly
  - Re-leasing costs deducted
  - Rent reduction applied to NOI
  - Scenario value < base value
  - Impact on recommendation assessed

**Test: `test_multi_scenario_probability_weighted_valuation()`**
- **Purpose:** Combine multiple scenarios with probabilities
- **Input:** 3 scenarios (Base 70%, Non-renewal 20%, Bankruptcy 10%)
- **Expected Output:**
  - Probability-weighted value calculated
  - Expected value between worst and best scenarios
  - Risk-adjusted recommendation provided
  - Sensitivity analysis chart generated

## Data Validation Tests

### Input Data Validation

**Test: `test_property_input_validation()`**
- **Purpose:** Reject invalid property data
- **Test Cases:**
  - Negative VPD → error
  - VPD > 200,000 → warning (sanity check)
  - Negative annual rent → error
  - Missing required fields → error with field name
  - Invalid state code → error
  - Invalid ZIP code format → error

**Test: `test_lease_terms_validation()`**
- **Purpose:** Validate lease term data
- **Test Cases:**
  - Negative years remaining → error
  - Years remaining > 30 → warning
  - Renewal options < 0 → error
  - Invalid lease type → error
  - Missing guarantee type for NNN → warning

**Test: `test_demographics_validation()`**
- **Purpose:** Ensure demographic data is reasonable
- **Test Cases:**
  - Negative population → error
  - Population > 10 million (3-mile radius) → warning
  - Negative median income → error
  - Median income > $500,000 → warning (sanity check)

### Database Integrity Tests

**Test: `test_no_duplicate_property_ids()`**
- **Purpose:** Ensure property_id uniqueness
- **Test Cases:**
  - Insert property with existing ID → error
  - Insert 100 properties → all unique IDs

**Test: `test_foreign_key_constraints()`**
- **Purpose:** Verify referential integrity
- **Test Cases:**
  - Property references non-existent category → error
  - Delete category with existing properties → error
  - Location data references non-existent property → error

**Test: `test_required_fields_populated()`**
- **Purpose:** Ensure all required fields have values
- **Test Cases:**
  - Property with missing address → error
  - Valuation with missing cap rate → error
  - Score with missing location score → error

## Comparison Tests

### Percentile Calculation Tests

**Test: `test_percentile_calculation_accuracy()`**
- **Purpose:** Verify percentile math is correct
- **Test Cases:**
  - Dataset of 100 properties, subject ranks 75th → 75.0 percentile
  - Dataset of 100 properties, subject ranks 1st → 99.0 percentile (top)
  - Dataset of 100 properties, subject ranks 100th → 0.0 percentile (bottom)
  - Small dataset (10 properties) → percentiles still accurate

**Test: `test_comparable_similarity_scoring()`**
- **Purpose:** Validate similarity score calculation
- **Test Cases:**
  - Identical properties → 100 similarity score
  - VPD differs by 50% → lower VPD similarity
  - Demographics match perfectly → 100 demographics similarity
  - All factors differ significantly → low overall similarity

**Test: `test_comparison_set_filtering()`**
- **Purpose:** Ensure comparison queries filter correctly
- **Test Cases:**
  - State filter → only TX properties returned
  - Category filter → only QSR properties returned
  - VPD range filter → only properties within range
  - Combined filters → all conditions met

## Regression Tests

### Calculation Consistency Tests

**Test: `test_valuation_consistency_across_runs()`**
- **Purpose:** Ensure same inputs produce same outputs
- **Test Cases:**
  - Run evaluation 10 times → identical results every time
  - Load from different YAML format → same calculation results
  - Different code paths (optimized vs debug) → same valuations

**Test: `test_backwards_compatibility()`**
- **Purpose:** Ensure previous evaluations still work
- **Test Cases:**
  - Load property evaluated in v1.0 → still calculates correctly in v2.0
  - Category templates from v1.0 → still compatible
  - Database from v1.0 → migrates cleanly to v2.0

**Test: `test_edge_case_handling()`**
- **Purpose:** Verify graceful handling of edge cases
- **Test Cases:**
  - Property with all zeros → doesn't crash, produces warnings
  - Extreme cap rate (15%) → warning issued, calculation proceeds
  - Missing optional fields → defaults applied correctly

## Performance Tests

### Query Performance Tests

**Test: `test_comparable_query_performance()`**
- **Purpose:** Ensure queries complete within time limits
- **Test Cases:**
  - Query 100 properties → <1 second
  - Query 1,000 properties → <2 seconds
  - Complex filter query → <500ms

**Test: `test_portfolio_analysis_performance()`**
- **Purpose:** Validate performance with large portfolios
- **Test Cases:**
  - Analyze 50 properties → <10 seconds
  - Analyze 100 properties → <20 seconds
  - Generate 50 HTML reports → <5 minutes

**Test: `test_percentile_calculation_performance()`**
- **Purpose:** Ensure ranking calculations are fast
- **Test Cases:**
  - Calculate percentiles for 1 property vs 100 → <1 second
  - Calculate percentiles for 1 property vs 1,000 → <2 seconds
  - Batch percentile calculation (50 properties) → <5 seconds

### Report Generation Performance

**Test: `test_html_report_generation_speed()`**
- **Purpose:** Verify report creation meets requirements
- **Test Cases:**
  - Single property report with 5 charts → <5 seconds
  - Portfolio comparison report (20 properties) → <10 seconds
  - Benchmarking report with 50 comparables → <8 seconds

## Test Data Fixtures

### Sample Property Data (YAML)

**Fixture: `test_family_dollar_excellent.yaml`**
```yaml
property:
  tenant_name: "Family Dollar"
  address: "123 Main St"
  city: "Dallas"
  state: "TX"
  building_sf: 9000
  annual_rent: 120000
  asking_price: 1400000

location:
  vpd: 45000  # Excellent
  intersection_type: "Signalized Corner with Median Cut"
  visibility_rating: "Excellent"
  population_3mi: 120000
  median_income_3mi: 85000

lease:
  years_remaining: 12
  renewal_options: 4
  guarantee_type: "Corporate"
```

**Fixture: `test_kfc_average.yaml`**
```yaml
category: "QSR - Drive-Thru"
property:
  tenant_name: "KFC"
  address: "456 Oak Ave"
  city: "Houston"
  state: "TX"
  building_sf: 2500
  annual_rent: 80000
  asking_price: 1000000

location:
  vpd: 25000  # Average
  intersection_type: "Unsignalized Corner"

category_specific:
  drive_thru_lanes: 1
  parking_spaces: 25
```

## Mocking Requirements

**NO MOCKS ALLOWED** - This framework uses real data and real calculations. All tests must use actual CSV data files or in-memory datasets with realistic values.

**Data Sources:**
- Real property data from evaluated properties
- Synthetic datasets based on realistic distributions
- Historical valuations from actual transactions

## Test Execution Strategy

### Continuous Integration

```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/performance/

# Generate coverage report
pytest --cov=modules/valuation --cov-report=html
```

### Coverage Requirements

- **Unit tests:** 95%+ code coverage
- **Integration tests:** All major workflows covered
- **Edge cases:** All error conditions tested
- **Performance:** All performance requirements validated
