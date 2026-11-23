"""
Tests for spatial_factors.py — GIS-based spatial attribute extraction.
TDD: red → green → refactor
"""
import pytest
from unittest.mock import patch, MagicMock

from assethold.property.spatial_factors import (
    SpatialFactorExtractor,
    SpatialFactors,
    FloodZone,
    TrafficLevel,
)
from assethold.property.property_model import Property


@pytest.fixture()
def sample_property():
    return Property(
        address="123 Main St, Houston, TX 77001",
        lat=29.7604,
        lon=-95.3698,
        county="Harris",
        state="TX",
    )


class TestSpatialFactors:
    """Tests for SpatialFactors result container."""

    def test_spatial_factors_stores_all_fields(self):
        sf = SpatialFactors(
            flood_zone=FloodZone.ZONE_X,
            flood_zone_score=0.9,
            traffic_aadt=15000,
            traffic_level=TrafficLevel.MODERATE,
            traffic_score=0.6,
            school_rating=7.0,
            school_score=0.7,
            transit_distance_m=400.0,
            transit_score=0.8,
            park_distance_m=800.0,
            park_score=0.75,
            commercial_distance_m=300.0,
            commercial_score=0.85,
            composite_score=0.76,
        )
        assert sf.flood_zone == FloodZone.ZONE_X
        assert sf.flood_zone_score == pytest.approx(0.9)
        assert sf.traffic_aadt == 15000
        assert sf.composite_score == pytest.approx(0.76)

    def test_spatial_factors_scores_bounded_0_to_1(self):
        sf = SpatialFactors(
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
        for score_attr in [
            "flood_zone_score", "traffic_score", "school_score",
            "transit_score", "park_score", "commercial_score",
            "composite_score",
        ]:
            val = getattr(sf, score_attr)
            assert 0.0 <= val <= 1.0, f"{score_attr} out of range: {val}"


class TestFloodZoneEnum:
    def test_zone_ae_high_risk(self):
        assert FloodZone.ZONE_AE.value == "AE"

    def test_zone_x_minimal_risk(self):
        assert FloodZone.ZONE_X.value == "X"

    def test_zone_unknown(self):
        assert FloodZone.UNKNOWN.value == "UNKNOWN"


class TestTrafficLevelEnum:
    def test_low_value(self):
        assert TrafficLevel.LOW.value == "low"

    def test_moderate_value(self):
        assert TrafficLevel.MODERATE.value == "moderate"

    def test_high_value(self):
        assert TrafficLevel.HIGH.value == "high"

    def test_very_high_value(self):
        assert TrafficLevel.VERY_HIGH.value == "very_high"


class TestSpatialFactorExtractor:
    """Tests for SpatialFactorExtractor orchestrator."""

    def test_extractor_instantiates(self):
        extractor = SpatialFactorExtractor()
        assert extractor is not None

    def test_extract_returns_spatial_factors(self, sample_property):
        extractor = SpatialFactorExtractor()
        with (
            patch.object(extractor, "_get_flood_zone",
                         return_value=(FloodZone.ZONE_X, 0.9)),
            patch.object(extractor, "_get_traffic_volume",
                         return_value=(12000, TrafficLevel.MODERATE, 0.65)),
            patch.object(extractor, "_get_school_rating",
                         return_value=(7.5, 0.75)),
            patch.object(extractor, "_get_transit_distance",
                         return_value=(500.0, 0.75)),
            patch.object(extractor, "_get_park_distance",
                         return_value=(600.0, 0.8)),
            patch.object(extractor, "_get_commercial_distance",
                         return_value=(250.0, 0.88)),
        ):
            result = extractor.extract(sample_property)

        assert isinstance(result, SpatialFactors)
        assert result.flood_zone == FloodZone.ZONE_X
        assert result.traffic_aadt == 12000

    def test_composite_score_is_weighted_average(self, sample_property):
        extractor = SpatialFactorExtractor()
        with (
            patch.object(extractor, "_get_flood_zone",
                         return_value=(FloodZone.ZONE_X, 1.0)),
            patch.object(extractor, "_get_traffic_volume",
                         return_value=(0, TrafficLevel.LOW, 1.0)),
            patch.object(extractor, "_get_school_rating",
                         return_value=(10.0, 1.0)),
            patch.object(extractor, "_get_transit_distance",
                         return_value=(0.0, 1.0)),
            patch.object(extractor, "_get_park_distance",
                         return_value=(0.0, 1.0)),
            patch.object(extractor, "_get_commercial_distance",
                         return_value=(0.0, 1.0)),
        ):
            result = extractor.extract(sample_property)

        assert result.composite_score == pytest.approx(1.0)


class TestFloodZoneScoring:
    """Tests for internal flood zone scoring logic."""

    def test_zone_ae_low_score(self):
        extractor = SpatialFactorExtractor()
        _, score = extractor._score_flood_zone(FloodZone.ZONE_AE)
        assert score < 0.4

    def test_zone_x_high_score(self):
        extractor = SpatialFactorExtractor()
        _, score = extractor._score_flood_zone(FloodZone.ZONE_X)
        assert score > 0.8

    def test_zone_unknown_mid_score(self):
        extractor = SpatialFactorExtractor()
        _, score = extractor._score_flood_zone(FloodZone.UNKNOWN)
        assert 0.3 <= score <= 0.7


class TestTrafficScoring:
    """Tests for AADT traffic score normalization."""

    def test_zero_aadt_score_high(self):
        extractor = SpatialFactorExtractor()
        _, level, score = extractor._score_traffic(0)
        assert score >= 0.9

    def test_high_aadt_score_low(self):
        extractor = SpatialFactorExtractor()
        _, level, score = extractor._score_traffic(100000)
        assert score <= 0.3

    def test_moderate_aadt_returns_moderate_level(self):
        extractor = SpatialFactorExtractor()
        _, level, score = extractor._score_traffic(15000)
        assert level == TrafficLevel.MODERATE

    def test_score_is_normalized_0_to_1(self):
        extractor = SpatialFactorExtractor()
        for aadt in [0, 5000, 20000, 75000, 200000]:
            _, _, score = extractor._score_traffic(aadt)
            assert 0.0 <= score <= 1.0, f"score out of range for aadt={aadt}"


class TestProximityScoring:
    """Tests for distance-to-score conversion."""

    def test_zero_distance_score_is_1(self):
        extractor = SpatialFactorExtractor()
        score = extractor._distance_to_score(0.0, max_distance_m=2000.0)
        assert score == pytest.approx(1.0)

    def test_max_distance_score_is_0(self):
        extractor = SpatialFactorExtractor()
        score = extractor._distance_to_score(2000.0, max_distance_m=2000.0)
        assert score == pytest.approx(0.0)

    def test_half_distance_score_near_half(self):
        extractor = SpatialFactorExtractor()
        score = extractor._distance_to_score(1000.0, max_distance_m=2000.0)
        assert 0.4 <= score <= 0.6

    def test_beyond_max_distance_clamps_to_0(self):
        extractor = SpatialFactorExtractor()
        score = extractor._distance_to_score(5000.0, max_distance_m=2000.0)
        assert score == pytest.approx(0.0)
