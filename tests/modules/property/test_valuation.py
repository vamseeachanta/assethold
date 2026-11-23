"""
Tests for valuation.py — Weighted spatial factor valuation model.
TDD: red → green → refactor

NOTE: Output is an estimated range, NOT a certified appraisal.
"""
import pytest
from unittest.mock import patch, MagicMock

from assethold.property.valuation import (
    ValuationEngine,
    ValuationResult,
    ValuationError,
)
from assethold.property.property_model import Property, PropertyType
from assethold.property.spatial_factors import (
    SpatialFactors,
    FloodZone,
    TrafficLevel,
)
from assethold.property.market_data import (
    ComparableSale,
    MarketDataResult,
)


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
def good_spatial_factors():
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
def market_data_with_comps():
    comps = [
        ComparableSale("A", 29.761, -95.370, 300000.0, "2025-01-01", 1950, 200.0),
        ComparableSale("B", 29.762, -95.369, 330000.0, "2025-02-01", 2050, 350.0),
        ComparableSale("C", 29.763, -95.368, 315000.0, "2025-03-01", 2000, 480.0),
    ]
    return MarketDataResult(
        assessed_value=320000.0,
        comparable_sales=comps,
        median_comp_price=315000.0,
        median_price_per_sqft=157.5,
        data_source="comparable_sales",
        county_supported=True,
    )


@pytest.fixture()
def market_data_no_comps():
    return MarketDataResult(
        assessed_value=320000.0,
        comparable_sales=[],
        median_comp_price=None,
        median_price_per_sqft=None,
        data_source="tax_assessment_fallback",
        county_supported=True,
    )


class TestValuationResult:
    """Tests for ValuationResult structure."""

    def test_valuation_result_has_required_fields(self):
        result = ValuationResult(
            estimated_value_low=280000.0,
            estimated_value_high=350000.0,
            estimated_value_mid=315000.0,
            base_value=315000.0,
            spatial_adjustment_pct=0.0,
            confidence="medium",
            data_source="comparable_sales",
            factor_scores={},
            disclaimer=(
                "This is an estimated range for screening purposes only. "
                "Not a certified appraisal."
            ),
        )
        assert result.estimated_value_low == pytest.approx(280000.0)
        assert result.estimated_value_high == pytest.approx(350000.0)
        assert result.estimated_value_mid == pytest.approx(315000.0)
        assert "not a certified appraisal" in result.disclaimer.lower()

    def test_estimated_range_low_le_mid_le_high(self):
        result = ValuationResult(
            estimated_value_low=280000.0,
            estimated_value_high=350000.0,
            estimated_value_mid=315000.0,
            base_value=315000.0,
            spatial_adjustment_pct=0.0,
            confidence="medium",
            data_source="comparable_sales",
            factor_scores={},
            disclaimer="Estimated range only.",
        )
        assert result.estimated_value_low <= result.estimated_value_mid
        assert result.estimated_value_mid <= result.estimated_value_high


class TestValuationEngine:
    """Tests for ValuationEngine."""

    def test_engine_instantiates(self):
        engine = ValuationEngine()
        assert engine is not None

    def test_estimate_returns_valuation_result(
        self, sample_property, good_spatial_factors, market_data_with_comps
    ):
        engine = ValuationEngine()
        result = engine.estimate(
            property_=sample_property,
            spatial_factors=good_spatial_factors,
            market_data=market_data_with_comps,
        )
        assert isinstance(result, ValuationResult)

    def test_estimate_uses_median_comp_as_base_when_comps_present(
        self, sample_property, good_spatial_factors, market_data_with_comps
    ):
        engine = ValuationEngine()
        result = engine.estimate(
            property_=sample_property,
            spatial_factors=good_spatial_factors,
            market_data=market_data_with_comps,
        )
        # Base value should be anchored near median comp price
        assert result.data_source == "comparable_sales"
        assert result.base_value == pytest.approx(315000.0)

    def test_estimate_falls_back_to_assessed_value_when_no_comps(
        self, sample_property, good_spatial_factors, market_data_no_comps
    ):
        engine = ValuationEngine()
        result = engine.estimate(
            property_=sample_property,
            spatial_factors=good_spatial_factors,
            market_data=market_data_no_comps,
        )
        assert result.data_source == "tax_assessment_fallback"
        assert result.base_value == pytest.approx(320000.0)

    def test_perfect_spatial_factors_positive_adjustment(
        self, sample_property, market_data_with_comps
    ):
        perfect_sf = SpatialFactors(
            flood_zone=FloodZone.ZONE_X,
            flood_zone_score=1.0,
            traffic_aadt=0,
            traffic_level=TrafficLevel.LOW,
            traffic_score=1.0,
            school_rating=10.0,
            school_score=1.0,
            transit_distance_m=0.0,
            transit_score=1.0,
            park_distance_m=0.0,
            park_score=1.0,
            commercial_distance_m=0.0,
            commercial_score=1.0,
            composite_score=1.0,
        )
        engine = ValuationEngine()
        result = engine.estimate(
            property_=sample_property,
            spatial_factors=perfect_sf,
            market_data=market_data_with_comps,
        )
        assert result.spatial_adjustment_pct >= 0.0

    def test_poor_spatial_factors_negative_adjustment(
        self, sample_property, market_data_with_comps
    ):
        poor_sf = SpatialFactors(
            flood_zone=FloodZone.ZONE_AE,
            flood_zone_score=0.1,
            traffic_aadt=90000,
            traffic_level=TrafficLevel.VERY_HIGH,
            traffic_score=0.1,
            school_rating=2.0,
            school_score=0.2,
            transit_distance_m=3000.0,
            transit_score=0.1,
            park_distance_m=4000.0,
            park_score=0.1,
            commercial_distance_m=5000.0,
            commercial_score=0.1,
            composite_score=0.12,
        )
        engine = ValuationEngine()
        result = engine.estimate(
            property_=sample_property,
            spatial_factors=poor_sf,
            market_data=market_data_with_comps,
        )
        assert result.spatial_adjustment_pct <= 0.0

    def test_range_width_reflects_confidence(
        self, sample_property, good_spatial_factors, market_data_with_comps
    ):
        engine = ValuationEngine()
        result = engine.estimate(
            property_=sample_property,
            spatial_factors=good_spatial_factors,
            market_data=market_data_with_comps,
        )
        range_width_pct = (
            (result.estimated_value_high - result.estimated_value_low)
            / result.estimated_value_mid
        )
        # Expect a range band of roughly 10-30% for medium confidence
        assert 0.05 <= range_width_pct <= 0.50

    def test_factor_scores_present_in_result(
        self, sample_property, good_spatial_factors, market_data_with_comps
    ):
        engine = ValuationEngine()
        result = engine.estimate(
            property_=sample_property,
            spatial_factors=good_spatial_factors,
            market_data=market_data_with_comps,
        )
        assert "flood_zone" in result.factor_scores
        assert "traffic" in result.factor_scores
        assert "school" in result.factor_scores

    def test_disclaimer_present_in_result(
        self, sample_property, good_spatial_factors, market_data_with_comps
    ):
        engine = ValuationEngine()
        result = engine.estimate(
            property_=sample_property,
            spatial_factors=good_spatial_factors,
            market_data=market_data_with_comps,
        )
        assert result.disclaimer
        assert len(result.disclaimer) > 20

    def test_valuation_raises_on_missing_base_value(
        self, sample_property, good_spatial_factors
    ):
        no_value_market = MarketDataResult(
            assessed_value=None,
            comparable_sales=[],
            median_comp_price=None,
            median_price_per_sqft=None,
            data_source="tax_assessment_fallback",
            county_supported=False,
        )
        engine = ValuationEngine()
        with pytest.raises(ValuationError, match="base value"):
            engine.estimate(
                property_=sample_property,
                spatial_factors=good_spatial_factors,
                market_data=no_value_market,
            )
