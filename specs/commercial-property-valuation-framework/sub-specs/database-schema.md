# Database Schema

This is the database schema implementation for the spec detailed in @.agent-os/specs/commercial-property-valuation-framework/spec.md

> Created: 2025-10-26
> Version: 1.0.0

## Overview

The Commercial Property Valuation Framework requires a structured database to store evaluated properties, enable cross-property comparisons, calculate percentile rankings, and support portfolio analytics. This schema is designed for initial CSV/JSON implementation with migration path to SQLite/PostgreSQL.

## Database Design Principles

1. **Flexibility:** Support diverse property types with category-specific attributes
2. **Queryability:** Enable efficient comparison and benchmarking queries
3. **Versioning:** Track property evaluations over time
4. **Normalization:** Avoid data duplication while maintaining query performance
5. **Extensibility:** Easy addition of new property categories and attributes

## Core Tables

### 1. Properties Table

**Purpose:** Store core property information and financial data

**Schema:**

```python
properties = {
    "property_id": str,              # UUID primary key
    "category_id": str,              # Foreign key to categories table
    "tenant_name": str,              # e.g., "Family Dollar", "KFC"
    "property_name": str,            # Optional friendly name

    # Location
    "address": str,
    "city": str,
    "state": str,
    "zip_code": str,
    "county": str,
    "latitude": float,
    "longitude": float,

    # Building Details
    "building_sf": int,              # Square footage
    "lot_sf": int,                   # Lot size
    "year_built": int,
    "building_condition": str,       # Excellent, Good, Fair, Poor

    # Financial
    "annual_rent": float,
    "noi": float,                    # Net Operating Income
    "asking_price": float,
    "price_per_sf": float,
    "purchase_price": float,         # If acquired
    "purchase_date": date,

    # Metadata
    "evaluation_date": datetime,
    "analyst": str,
    "data_sources": str,             # Comma-separated list
    "notes": str,                    # Free-form notes
    "status": str,                   # Active, Under Review, Archived

    # Timestamps
    "created_at": datetime,
    "updated_at": datetime
}
```

**CSV Format:**
```csv
property_id,category_id,tenant_name,address,city,state,zip_code,latitude,longitude,building_sf,annual_rent,noi,asking_price,evaluation_date
uuid-123,retail-conv,Family Dollar,"123 Main St",Dallas,TX,75001,32.7767,-96.7970,9000,120000,115000,1400000,2025-10-26
```

### 2. Categories Table

**Purpose:** Define property category configurations and scoring parameters

**Schema:**

```python
categories = {
    "category_id": str,              # Primary key (e.g., "retail-conv", "qsr-dt")
    "name": str,                     # "Retail - Convenience Store"
    "short_code": str,               # "Retail-Conv"
    "description": str,

    # Scoring Weights (must sum to 1.0)
    "weight_vpd": float,
    "weight_intersection": float,
    "weight_demographics": float,
    "weight_visibility": float,
    "weight_competition": float,
    "weight_category_specific": float,

    # VPD Thresholds
    "vpd_excellent": int,
    "vpd_good": int,
    "vpd_average": int,
    "vpd_fair": int,

    # Demographics Settings
    "demographic_radius_miles": int,

    # Cap Rate Ranges
    "cap_rate_min": float,
    "cap_rate_max": float,
    "cap_rate_baseline": float,

    # Lease Settings
    "typical_lease_type": str,       # NNN, NN, MG, Ground

    # Configuration File Path
    "config_file": str,              # Path to YAML template

    "created_at": datetime,
    "updated_at": datetime
}
```

**CSV Format:**
```csv
category_id,name,short_code,weight_vpd,weight_intersection,weight_demographics,cap_rate_baseline
retail-conv,Retail - Convenience Store,Retail-Conv,0.30,0.25,0.20,0.080
qsr-dt,QSR - Drive-Thru,QSR-DT,0.30,0.25,0.15,0.075
```

### 3. Location_Data Table

**Purpose:** Store location-specific metrics (VPD, demographics, visibility)

**Schema:**

```python
location_data = {
    "location_id": str,              # UUID primary key
    "property_id": str,              # Foreign key to properties

    # Traffic
    "vpd": int,                      # Vehicles per day
    "vpd_source": str,               # "DOT", "Manual Count", "Estimate"
    "vpd_date": date,                # When VPD measured
    "peak_hour_traffic": str,        # "7-9am, 4-7pm"

    # Intersection
    "intersection_type": str,        # "Signalized Corner", "Mid-block", etc.
    "has_median_cut": bool,
    "has_left_turn_lane": bool,
    "traffic_signal": bool,

    # Access
    "ingress_egress_quality": str,  # "Easy", "Moderate", "Difficult"
    "parking_spaces": int,
    "parking_type": str,             # "Surface", "Structured", "Street"

    # Visibility
    "visibility_rating": str,        # "Excellent", "Good", "Fair", "Poor"
    "has_monument_sign": bool,
    "sign_quality": str,
    "street_frontage_ft": int,

    # Demographics (3-mile radius default)
    "population_3mi": int,
    "median_income_3mi": float,
    "median_age_3mi": float,
    "households_3mi": int,

    # Additional radius if needed
    "population_5mi": int,
    "median_income_5mi": float,

    "created_at": datetime,
    "updated_at": datetime
}
```

### 4. Lease_Terms Table

**Purpose:** Store lease agreement details

**Schema:**

```python
lease_terms = {
    "lease_id": str,                 # UUID primary key
    "property_id": str,              # Foreign key to properties

    "lease_type": str,               # NNN, NN, Modified Gross, Ground
    "lease_start_date": date,
    "lease_end_date": date,
    "years_remaining": float,

    # Renewal Options
    "renewal_options": int,          # Number of renewal options
    "renewal_option_years": int,     # Years per option (e.g., 5)
    "renewal_rent_increase": str,    # "10% every 5 years", "CPI"

    # Rent Escalations
    "base_rent": float,
    "escalation_type": str,          # "Fixed %", "CPI", "None"
    "escalation_pct": float,
    "escalation_frequency": str,     # "Annual", "Every 5 years"

    # Guarantees
    "guarantee_type": str,           # "Corporate", "Store-level", "None"
    "guarantor_name": str,
    "guarantor_credit_rating": str,

    # Tenant Responsibilities (for NN/NNN)
    "tenant_pays_taxes": bool,
    "tenant_pays_insurance": bool,
    "tenant_pays_maintenance": bool,

    "created_at": datetime,
    "updated_at": datetime
}
```

### 5. Competition Table

**Purpose:** Track competitive properties near subject property

**Schema:**

```python
competition = {
    "competition_id": str,           # UUID primary key
    "property_id": str,              # Foreign key (subject property)

    "competitor_name": str,          # "Dollar General", "Walgreens"
    "competitor_type": str,          # Same category or related
    "distance_miles": float,
    "competitive_threat": str,       # "High", "Medium", "Low"

    # Location
    "competitor_address": str,
    "competitor_latitude": float,
    "competitor_longitude": float,

    # Quality Assessment
    "competitor_building_sf": int,
    "competitor_parking": int,
    "competitor_visibility": str,

    "created_at": datetime,
    "updated_at": datetime
}
```

### 6. Category_Specific_Data Table

**Purpose:** Store category-specific attributes (flexible schema)

**Schema:**

```python
category_specific_data = {
    "data_id": str,                  # UUID primary key
    "property_id": str,              # Foreign key to properties
    "category_id": str,              # Foreign key to categories

    # JSON blob for flexibility
    "attributes": json,              # Category-specific attributes

    # Example for QSR:
    # {
    #   "drive_thru_lanes": 2,
    #   "seating_capacity": 40,
    #   "outdoor_seating": true,
    #   "delivery_pickup": true
    # }

    # Example for Medical:
    # {
    #   "exam_rooms": 8,
    #   "hospital_distance_miles": 1.5,
    #   "accepts_medicare": true,
    #   "accepts_medicaid": true
    # }

    "created_at": datetime,
    "updated_at": datetime
}
```

### 7. Scores Table

**Purpose:** Store calculated scores for each property

**Schema:**

```python
scores = {
    "score_id": str,                 # UUID primary key
    "property_id": str,              # Foreign key to properties
    "evaluation_date": datetime,     # When scores calculated

    # Location Scores (0-100)
    "vpd_score": float,
    "intersection_score": float,
    "demographics_score": float,
    "visibility_score": float,
    "competition_score": float,
    "category_specific_score": float,
    "total_location_score": float,   # Weighted sum

    # Financial Scores (0-100)
    "lease_strength_score": float,
    "tenant_credit_score": float,

    # Overall Quality Score (0-100)
    "overall_quality_score": float,  # Composite of all factors

    # Percentile Rankings (vs comparable properties)
    "location_percentile": float,
    "cap_rate_percentile": float,
    "quality_percentile": float,

    "created_at": datetime,
    "updated_at": datetime
}
```

### 8. Valuations Table

**Purpose:** Store valuation results and cap rate adjustments

**Schema:**

```python
valuations = {
    "valuation_id": str,             # UUID primary key
    "property_id": str,              # Foreign key to properties
    "evaluation_date": datetime,

    # Cap Rate Components
    "base_cap_rate": float,
    "location_adjustment": float,    # ±0.50%
    "tenant_risk_adjustment": float,
    "lease_term_adjustment": float,
    "market_adjustment": float,
    "adjusted_cap_rate": float,      # Final cap rate

    # Valuation Results
    "fair_market_value": float,      # Base valuation
    "valuation_low": float,          # Conservative
    "valuation_high": float,         # Optimistic
    "confidence_interval_pct": float,

    # Comparison to Asking Price
    "asking_price": float,
    "premium_discount_pct": float,   # How much over/under FMV
    "recommendation": str,           # "Strong Buy", "Buy", "Fair", "Pass"
    "recommendation_rationale": str,

    # Risk-Adjusted Valuation
    "risk_adjusted_value": float,    # After scenario analysis
    "expected_return_pct": float,

    "created_at": datetime,
    "updated_at": datetime
}
```

### 9. Scenarios Table

**Purpose:** Store risk scenarios for scenario analysis

**Schema:**

```python
scenarios = {
    "scenario_id": str,              # UUID primary key
    "property_id": str,              # Foreign key to properties
    "scenario_name": str,            # "Base Case", "Lease Not Renewed"
    "probability": float,            # 0.0 to 1.0

    # Scenario Adjustments
    "rent_reduction_pct": float,
    "vacancy_months": int,
    "releasing_costs": float,
    "cap_rate_adjustment": float,
    "additional_capex": float,

    # Scenario Results
    "scenario_value": float,
    "scenario_return_pct": float,

    "created_at": datetime,
    "updated_at": datetime
}
```

### 10. Comparables Table

**Purpose:** Link properties that are comparable for benchmarking

**Schema:**

```python
comparables = {
    "comparable_id": str,            # UUID primary key
    "subject_property_id": str,      # Foreign key (subject)
    "comparable_property_id": str,   # Foreign key (comparable)

    "similarity_score": float,       # 0-100, how similar
    "similarity_factors": json,      # Breakdown of similarity
    # {
    #   "vpd_similarity": 85,
    #   "demographics_similarity": 90,
    #   "lease_term_similarity": 75
    # }

    "comparison_date": datetime,
    "created_at": datetime,
    "updated_at": datetime
}
```

## Relationships

```
Properties (1) ─── (1) Location_Data
           (1) ─── (1) Lease_Terms
           (1) ─── (1) Category_Specific_Data
           (1) ─── (1) Scores
           (1) ─── (1) Valuations
           (1) ─── (M) Competition
           (1) ─── (M) Scenarios
           (M) ─── (1) Categories

Properties (M) ─── (M) Comparables (self-referencing)
```

## Database Implementation Phases

### Phase 1: CSV/JSON (MVP)

**Storage Structure:**
```
data/
└── valuation/
    ├── properties.csv
    ├── categories.csv
    ├── location_data.csv
    ├── lease_terms.csv
    ├── competition.csv
    ├── scores.csv
    ├── valuations.csv
    ├── scenarios.csv
    └── category_specific/
        ├── property_uuid_123.json
        └── property_uuid_456.json
```

**Pros:**
- Simple to implement
- Human-readable
- Easy backup/version control
- No database setup required

**Cons:**
- Slower queries on large datasets
- No referential integrity enforcement
- Manual relationship management

### Phase 2: SQLite (Local Database)

**Migration Path:**
1. Create SQLite database schema
2. Import CSV data using pandas
3. Add indexes on key fields
4. Implement foreign key constraints

**SQL Schema Example:**

```sql
CREATE TABLE properties (
    property_id TEXT PRIMARY KEY,
    category_id TEXT NOT NULL,
    tenant_name TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    annual_rent REAL,
    asking_price REAL,
    evaluation_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

CREATE INDEX idx_properties_category ON properties(category_id);
CREATE INDEX idx_properties_state ON properties(state);
CREATE INDEX idx_properties_tenant ON properties(tenant_name);
```

### Phase 3: PostgreSQL (Multi-User)

**For future team collaboration:**
- Concurrent access
- Advanced query optimization
- Replication and backup
- User permissions

## Query Examples

### Find Comparable Properties

```python
def find_comparables(subject_property_id, max_results=10):
    """
    Find similar properties for benchmarking
    """
    subject = get_property(subject_property_id)

    query = f"""
    SELECT p.*, s.total_location_score, v.adjusted_cap_rate
    FROM properties p
    JOIN scores s ON p.property_id = s.property_id
    JOIN valuations v ON p.property_id = v.property_id
    JOIN location_data l ON p.property_id = l.property_id
    WHERE p.category_id = '{subject.category_id}'
      AND p.state = '{subject.state}'
      AND l.vpd BETWEEN {subject.vpd * 0.8} AND {subject.vpd * 1.2}
      AND p.property_id != '{subject_property_id}'
    ORDER BY ABS(s.total_location_score - {subject.location_score})
    LIMIT {max_results}
    """

    return execute_query(query)
```

### Calculate Percentile Rankings

```python
def calculate_percentile(property_id, metric, scope="state"):
    """
    Calculate percentile ranking for a property
    """
    property = get_property(property_id)

    if scope == "state":
        filter_clause = f"AND p.state = '{property.state}'"
    elif scope == "national":
        filter_clause = ""

    query = f"""
    WITH ranked AS (
        SELECT
            p.property_id,
            s.{metric},
            PERCENT_RANK() OVER (ORDER BY s.{metric}) as percentile
        FROM properties p
        JOIN scores s ON p.property_id = s.property_id
        WHERE p.category_id = '{property.category_id}'
        {filter_clause}
    )
    SELECT percentile * 100 as percentile_rank
    FROM ranked
    WHERE property_id = '{property_id}'
    """

    return execute_query(query)
```

### Portfolio Summary

```python
def portfolio_summary(property_ids, sort_by="overall_quality_score"):
    """
    Generate summary of multiple properties
    """
    ids_list = "','".join(property_ids)

    query = f"""
    SELECT
        p.property_id,
        p.tenant_name,
        p.address,
        p.city,
        p.state,
        s.total_location_score,
        s.overall_quality_score,
        v.adjusted_cap_rate,
        v.fair_market_value,
        v.recommendation
    FROM properties p
    JOIN scores s ON p.property_id = s.property_id
    JOIN valuations v ON p.property_id = v.property_id
    WHERE p.property_id IN ('{ids_list}')
    ORDER BY s.{sort_by} DESC
    """

    return execute_query(query)
```

## Data Migration Strategy

### CSV to SQLite Migration Script

```python
import pandas as pd
import sqlite3

def migrate_csv_to_sqlite(csv_dir, sqlite_path):
    conn = sqlite3.connect(sqlite_path)

    # Migrate each table
    tables = [
        'properties', 'categories', 'location_data',
        'lease_terms', 'competition', 'scores',
        'valuations', 'scenarios'
    ]

    for table in tables:
        csv_file = f"{csv_dir}/{table}.csv"
        df = pd.read_csv(csv_file)
        df.to_sql(table, conn, if_exists='replace', index=False)

    conn.close()
```

## Backup and Version Control

**Backup Strategy:**
- Daily CSV exports from database
- Git version control for category templates (YAML)
- Weekly full database backups
- Property evaluations tracked over time (immutable records)

**Version Control Fields:**
- `created_at`: Original creation timestamp
- `updated_at`: Last modification timestamp
- `evaluation_date`: When property was evaluated
- Historical records preserved (soft deletes with `status` field)
