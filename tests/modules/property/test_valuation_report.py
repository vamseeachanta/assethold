"""
Tests for valuation_report.py — Text/Markdown report generation.
TDD: red → green → refactor
"""
import pytest

from assethold.property.property_model import Property, PropertyType
from assethold.property.spatial_factors import (
    SpatialFactors,
    FloodZone,
    TrafficLevel,
)
from assethold.property.market_data import ComparableSale, MarketDataResult
from assethold.property.valuation import ValuationResult
from assethold.property.valuation_report import ValuationReport


@pytest.fixture()
def sample_property():
    return Property(
        address="123 Main St, Houston, TX 77001",
        lat=29.7604,
        lon=-95.3698,
        county="Harris",
        state="TX",
        building_sqft=2000,
        property_type=PropertyType.RESIDENTIAL,
        assessed_value=320000.0,
    )


@pytest.fixture()
def sample_spatial_factors():
    return SpatialFactors(
        flood_zone=FloodZone.ZONE_X,
        flood_zone_score=0.9,
        traffic_aadt=10000,
        traffic_level=TrafficLevel.MODERATE,
        traffic_score=0.7,
        school_rating=8.0,
        school_score=0.8,
        transit_distance_m=400.0,
        transit_score=0.8,
        park_distance_m=500.0,
        park_score=0.8,
        commercial_distance_m=300.0,
        commercial_score=0.85,
        composite_score=0.81,
    )


@pytest.fixture()
def sample_market_data():
    comps = [
        ComparableSale("456 Oak Ave", 29.762, -95.371,
                       310000.0, "2025-01-15", 1950, 350.0),
    ]
    return MarketDataResult(
        assessed_value=320000.0,
        comparable_sales=comps,
        median_comp_price=310000.0,
        median_price_per_sqft=158.97,
        data_source="comparable_sales",
        county_supported=True,
    )


@pytest.fixture()
def sample_valuation_result():
    return ValuationResult(
        estimated_value_low=285000.0,
        estimated_value_high=345000.0,
        estimated_value_mid=315000.0,
        base_value=310000.0,
        spatial_adjustment_pct=1.6,
        confidence="medium",
        data_source="comparable_sales",
        factor_scores={
            "flood_zone": 0.9,
            "traffic": 0.7,
            "school": 0.8,
            "transit": 0.8,
            "park": 0.8,
            "commercial": 0.85,
        },
        disclaimer=(
            "This is an estimated range for screening purposes only. "
            "Not a certified appraisal."
        ),
    )


class TestValuationReport:
    """Tests for ValuationReport Markdown/text output."""

    def test_report_instantiates(
        self,
        sample_property,
        sample_spatial_factors,
        sample_market_data,
        sample_valuation_result,
    ):
        report = ValuationReport(
            property_=sample_property,
            spatial_factors=sample_spatial_factors,
            market_data=sample_market_data,
            valuation=sample_valuation_result,
        )
        assert report is not None

    def test_to_markdown_returns_string(
        self,
        sample_property,
        sample_spatial_factors,
        sample_market_data,
        sample_valuation_result,
    ):
        report = ValuationReport(
            property_=sample_property,
            spatial_factors=sample_spatial_factors,
            market_data=sample_market_data,
            valuation=sample_valuation_result,
        )
        md = report.to_markdown()
        assert isinstance(md, str)
        assert len(md) > 100

    def test_markdown_contains_address(
        self,
        sample_property,
        sample_spatial_factors,
        sample_market_data,
        sample_valuation_result,
    ):
        report = ValuationReport(
            property_=sample_property,
            spatial_factors=sample_spatial_factors,
            market_data=sample_market_data,
            valuation=sample_valuation_result,
        )
        md = report.to_markdown()
        assert "123 Main St" in md

    def test_markdown_contains_estimated_range(
        self,
        sample_property,
        sample_spatial_factors,
        sample_market_data,
        sample_valuation_result,
    ):
        report = ValuationReport(
            property_=sample_property,
            spatial_factors=sample_spatial_factors,
            market_data=sample_market_data,
            valuation=sample_valuation_result,
        )
        md = report.to_markdown()
        assert "285,000" in md or "285000" in md
        assert "345,000" in md or "345000" in md

    def test_markdown_contains_flood_zone(
        self,
        sample_property,
        sample_spatial_factors,
        sample_market_data,
        sample_valuation_result,
    ):
        report = ValuationReport(
            property_=sample_property,
            spatial_factors=sample_spatial_factors,
            market_data=sample_market_data,
            valuation=sample_valuation_result,
        )
        md = report.to_markdown()
        assert "X" in md  # FloodZone.ZONE_X

    def test_markdown_contains_disclaimer(
        self,
        sample_property,
        sample_spatial_factors,
        sample_market_data,
        sample_valuation_result,
    ):
        report = ValuationReport(
            property_=sample_property,
            spatial_factors=sample_spatial_factors,
            market_data=sample_market_data,
            valuation=sample_valuation_result,
        )
        md = report.to_markdown()
        assert "not a certified appraisal" in md.lower()

    def test_markdown_contains_comparable_sales(
        self,
        sample_property,
        sample_spatial_factors,
        sample_market_data,
        sample_valuation_result,
    ):
        report = ValuationReport(
            property_=sample_property,
            spatial_factors=sample_spatial_factors,
            market_data=sample_market_data,
            valuation=sample_valuation_result,
        )
        md = report.to_markdown()
        assert "456 Oak Ave" in md

    def test_markdown_contains_data_sources_section(
        self,
        sample_property,
        sample_spatial_factors,
        sample_market_data,
        sample_valuation_result,
    ):
        report = ValuationReport(
            property_=sample_property,
            spatial_factors=sample_spatial_factors,
            market_data=sample_market_data,
            valuation=sample_valuation_result,
        )
        md = report.to_markdown()
        assert "Data Source" in md or "data source" in md.lower()
