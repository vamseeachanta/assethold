"""Unit tests for the DevelopmentProjector module.

Tests growth rate estimation, multi-horizon projection, confidence tier
assignment, and edge cases (no data, constant series, etc.).
"""

from __future__ import annotations

from datetime import date

import pytest

from assethold.modules.gis.projector import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    DevelopmentProjector,
    ProjectedDevelopment,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def projector() -> DevelopmentProjector:
    return DevelopmentProjector(
        base_year=2024,
        aoi_area_sqkm=12.57,
        horizon_years=(5, 10, 15),
    )


@pytest.fixture
def steady_growth_counts() -> list:
    """20 % per-year growth: 100, 120, 144, ..."""
    counts = []
    count = 100
    for year in range(2000, 2024, 2):
        counts.append({"year": year, "building_count": count})
        count = int(count * 1.044)  # ~4.4 % biennial ≈ 2.2 %/yr
    return counts


@pytest.fixture
def flat_counts() -> list:
    """Constant series — zero growth."""
    return [{"year": y, "building_count": 100} for y in range(2000, 2024, 2)]


@pytest.fixture
def permit_pipeline() -> list:
    return [
        {
            "building_count": 12,
            "expected_completion_year": 2028,
        },
        {
            "units": 8,
            "expected_completion_year": 2032,
        },
    ]


@pytest.fixture
def zoning_parcels() -> list:
    return [
        {"potential_units": 30},
        {"potential_units": 20},
    ]


# ---------------------------------------------------------------------------
# ProjectedDevelopment tests
# ---------------------------------------------------------------------------


class TestProjectedDevelopment:
    def test_to_dict_contains_required_fields(self) -> None:
        p = ProjectedDevelopment(
            horizon_year=2029,
            projection_date=date(2029, 1, 1),
            projected_building_count=150,
            projected_density_bldgs_per_sqkm=12.0,
            confidence=CONFIDENCE_LOW,
            basis="test",
        )
        d = p.to_dict()
        required = {
            "horizon_year",
            "projection_date",
            "projected_building_count",
            "projected_density_bldgs_per_sqkm",
            "confidence",
            "basis",
        }
        assert required <= set(d.keys())

    def test_to_dict_rounds_density(self) -> None:
        p = ProjectedDevelopment(
            horizon_year=2029,
            projection_date=date(2029, 1, 1),
            projected_building_count=100,
            projected_density_bldgs_per_sqkm=7.123456789,
            confidence=CONFIDENCE_LOW,
            basis="test",
        )
        d = p.to_dict()
        assert d["projected_density_bldgs_per_sqkm"] == round(7.123456789, 2)


# ---------------------------------------------------------------------------
# DevelopmentProjector tests
# ---------------------------------------------------------------------------


class TestDevelopmentProjector:
    def test_project_returns_one_projection_per_horizon(
        self, projector: DevelopmentProjector, flat_counts: list
    ) -> None:
        projections = projector.project_from_history(flat_counts)
        assert len(projections) == 3

    def test_projections_sorted_ascending_by_horizon(
        self, projector: DevelopmentProjector, flat_counts: list
    ) -> None:
        projections = projector.project_from_history(flat_counts)
        years = [p.horizon_year for p in projections]
        assert years == sorted(years)

    def test_projection_horizon_years_match_config(
        self, projector: DevelopmentProjector, flat_counts: list
    ) -> None:
        projections = projector.project_from_history(flat_counts)
        assert projections[0].horizon_year == 2029
        assert projections[1].horizon_year == 2034
        assert projections[2].horizon_year == 2039

    def test_flat_growth_keeps_count_stable(
        self, projector: DevelopmentProjector, flat_counts: list
    ) -> None:
        projections = projector.project_from_history(flat_counts)
        for p in projections:
            # Flat series → near 100 buildings for all horizons
            assert abs(p.projected_building_count - 100) <= 10

    def test_positive_growth_increases_count_with_horizon(
        self, projector: DevelopmentProjector, steady_growth_counts: list
    ) -> None:
        projections = projector.project_from_history(steady_growth_counts)
        counts = [p.projected_building_count for p in projections]
        assert counts[0] < counts[1] < counts[2]

    def test_confidence_low_without_permits_or_zoning(
        self, projector: DevelopmentProjector, flat_counts: list
    ) -> None:
        projections = projector.project_from_history(flat_counts)
        for p in projections:
            assert p.confidence == CONFIDENCE_LOW

    def test_confidence_high_with_permit_pipeline(
        self,
        projector: DevelopmentProjector,
        flat_counts: list,
        permit_pipeline: list,
    ) -> None:
        projections = projector.project_from_history(flat_counts, permit_pipeline)
        # Permits cover ≤2029 and ≤2032 horizons
        five_year = next(p for p in projections if p.horizon_year == 2029)
        assert five_year.confidence == CONFIDENCE_HIGH

    def test_confidence_medium_with_zoning_no_permits(
        self,
        projector: DevelopmentProjector,
        flat_counts: list,
        zoning_parcels: list,
    ) -> None:
        projections = projector.project_from_history(flat_counts, None, zoning_parcels)
        for p in projections:
            assert p.confidence == CONFIDENCE_MEDIUM

    def test_permitted_units_added_to_base_count(
        self,
        projector: DevelopmentProjector,
        flat_counts: list,
        permit_pipeline: list,
    ) -> None:
        projections = projector.project_from_history(flat_counts, permit_pipeline)
        five_year = next(p for p in projections if p.horizon_year == 2029)
        # Base 100 + 12 permitted within 5yr horizon
        assert five_year.projected_building_count >= 112

    def test_density_equals_count_divided_by_area(
        self, projector: DevelopmentProjector, flat_counts: list
    ) -> None:
        projections = projector.project_from_history(flat_counts)
        for p in projections:
            expected_density = p.projected_building_count / projector.aoi_area_sqkm
            assert abs(p.projected_density_bldgs_per_sqkm - expected_density) < 0.01

    def test_empty_history_returns_zero_count(
        self, projector: DevelopmentProjector
    ) -> None:
        projections = projector.project_from_history([])
        for p in projections:
            assert p.projected_building_count == 0

    def test_single_history_entry_returns_stable_projection(
        self, projector: DevelopmentProjector
    ) -> None:
        counts = [{"year": 2020, "building_count": 80}]
        projections = projector.project_from_history(counts)
        for p in projections:
            assert p.projected_building_count == 80

    def test_growth_rate_capped_at_twenty_percent(
        self, projector: DevelopmentProjector
    ) -> None:
        """Even unrealistic 100 %/yr growth should be capped at 20 %."""
        counts = [
            {"year": 2010, "building_count": 1},
            {"year": 2020, "building_count": 10000},
        ]
        projections = projector.project_from_history(counts)
        # With 20 % cap over 5 years from base 10000: 10000 * 1.2^5 ≈ 24883
        five_year = projections[0]
        max_at_cap = int(10000 * (1.20 ** 5))
        assert five_year.projected_building_count <= max_at_cap + 1

    def test_projection_date_is_first_of_horizon_year(
        self, projector: DevelopmentProjector, flat_counts: list
    ) -> None:
        projections = projector.project_from_history(flat_counts)
        for p in projections:
            assert p.projection_date == date(p.horizon_year, 1, 1)
