# Tests Specification

This is the tests coverage details for the spec detailed in @.agent-os/specs/family-dollar-valuation-model/spec.md

> Created: 2025-10-11
> Version: 1.0.0

## Test Coverage

### Unit Tests

**location_scorer.py**
- Test VPD scoring at each threshold boundary (9,999, 10,000, 19,999, 20,000, etc.)
- Test intersection quality scoring for all 5 types
- Test demographics scoring with edge cases (0 population, negative income)
- Test visibility scoring for all 3 levels
- Test competition density scoring for 0, 1, 2+ competitors
- Test overall location score calculation with known inputs
- Test location score bounds (verify 0-100 clamping)
- Test weighted scoring accuracy (verify 30% + 25% + 20% + 15% + 10% = 100%)

**cap_rate_adjuster.py**
- Test base cap rate with no adjustments
- Test location quality adjustments at each score range (90-100, 80-89, etc.)
- Test tenant risk adjustments at each lease strength level
- Test lease term adjustments for all year ranges
- Test PE sale risk premium (+0.25%)
- Test cap rate bounds (verify 4-15% sanity check)
- Test combined adjustments (all factors together)
- Test adjustment calculation order independence

**valuation_model.py**
- Test NOI to value conversion at various cap rates
- Test valuation range calculation (low, base, high)
- Test investment recommendation logic at each price threshold
- Test division by zero handling (cap rate = 0)
- Test negative NOI handling
- Test extreme cap rate handling (very high/low)
- Test fair market value accuracy (compare to manual calculation)

**report_generator.py**
- Test HTML structure generation
- Test Plotly chart embedding
- Test location score breakdown visualization
- Test cap rate sensitivity analysis chart
- Test comparable properties table rendering
- Test report file output creation
- Test CSS styling application

### Integration Tests

**Complete Valuation Workflow**
- Test end-to-end valuation for Westpark Family Dollar property
  - Input: 15645 Westpark Dr property data
  - Expected: Location score ~85, adjusted cap rate ~7.75%, value ~$1.57M
- Test multi-property batch processing
  - Input: 3 different Family Dollar properties
  - Expected: 3 separate HTML reports generated
- Test configuration file loading (YAML)
  - Input: market_cap_rates.yaml and scoring_weights.yaml
  - Expected: Correct values loaded into models

**Data Flow Tests**
- Test property data → location scorer → location score
- Test location score + lease data → cap rate adjuster → adjusted cap rate
- Test NOI + adjusted cap rate → valuation model → fair market value
- Test all outputs → report generator → HTML file

**Error Handling Tests**
- Test missing required property fields
- Test invalid VPD (negative, non-numeric)
- Test invalid demographics (negative population/income)
- Test missing configuration files
- Test corrupted YAML files

### Feature Tests

**Location Scoring End-to-End**
- **Scenario 1: Premium Location**
  - VPD: 45,000
  - Signalized corner intersection
  - Population: 150K, Income: $90K
  - Excellent visibility with monument sign
  - No competition within 1 mile
  - Expected: Location score 95-100

- **Scenario 2: Average Location**
  - VPD: 25,000
  - Unsignalized corner
  - Population: 80K, Income: $65K
  - Good visibility, standard signage
  - 1 competitor within 1 mile
  - Expected: Location score 60-70

- **Scenario 3: Poor Location**
  - VPD: 8,000
  - Mid-block standard
  - Population: 40K, Income: $50K
  - Limited visibility
  - 2+ competitors within 1 mile
  - Expected: Location score 30-40

**Valuation Accuracy Tests**
- **Westpark Property Validation:**
  - NOI: $121,700
  - Expected location score: 80-90
  - Expected adjusted cap rate: 7.5-8.0%
  - Expected value range: $1.52M - $1.62M
  - Verify against asking price: $1,550,000

- **Sensitivity Analysis:**
  - Test +/- 10% VPD impact on value
  - Test +/- 10% NOI impact on value
  - Test +/- 0.5% cap rate impact on value
  - Verify sensitivity chart accuracy

**Investment Recommendation Logic**
- Test "Strong Buy" recommendation when price < low value
- Test "Buy" recommendation when price in fair range
- Test "Fair" recommendation when price at upper range
- Test "Pass" recommendation when price > high value
- Test recommendation reasoning text generation

### Mocking Requirements

**Market Data:**
- Mock market cap rates by region (Houston: 7.5-8.0% baseline)
- Mock comparable sales data for relative valuation
- Mock regional VPD averages for context

**External Data (Future):**
- Mock traffic count APIs (when automated VPD collection added)
- Mock demographic data sources (census API)
- Mock Family Dollar store performance data

### Test Data Files

Create test fixtures:
```
tests/
└── fixtures/
    ├── westpark_property.yaml          # Real Westpark data
    ├── premium_location.yaml           # Ideal property
    ├── average_location.yaml           # Median property
    ├── poor_location.yaml              # Below-average property
    ├── market_cap_rates_test.yaml      # Test market data
    └── expected_outputs/
        ├── westpark_valuation.json     # Expected calculation results
        ├── premium_valuation.json
        ├── average_valuation.json
        └── poor_valuation.json
```

## Test Execution

**Unit Tests:** Run with pytest
```bash
pytest tests/unit/ -v
```

**Integration Tests:** Run with pytest
```bash
pytest tests/integration/ -v
```

**Feature Tests:** Run complete scenarios
```bash
pytest tests/features/ -v --html=test_report.html
```

**Coverage Requirements:**
- Minimum 90% code coverage
- 100% coverage for calculation functions
- All edge cases must have explicit tests
