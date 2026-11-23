"""Development projector: forecast future development around a property.

Uses three projection tiers ordered by confidence:
  HIGH   — Approved permits (filed, under review, or under construction)
  MEDIUM — Parcels zoned for development but not yet permitted
  LOW    — Statistical extrapolation of historical building density growth

Each tier produces a ProjectedDevelopment record with a horizon date and
confidence label.  The module is intentionally kept simple (linear
extrapolation) consistent with the Phase 4 scope and review feedback
that "predict future development patterns" was severely underestimated.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

HORIZON_YEARS = (5, 10, 15)


@dataclass
class ProjectedDevelopment:
    """A single development projection for a future horizon.

    Attributes:
        horizon_year: Target year for the projection.
        projection_date: First day of the horizon year.
        projected_building_count: Estimated number of buildings.
        projected_density_bldgs_per_sqkm: Building density per km².
        confidence: "high", "medium", or "low".
        basis: Description of the data driving this projection.
        sources: List of data source labels used.
        metadata: Additional projection parameters.
    """

    horizon_year: int
    projection_date: date
    projected_building_count: int
    projected_density_bldgs_per_sqkm: float
    confidence: str
    basis: str
    sources: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "horizon_year": self.horizon_year,
            "projection_date": self.projection_date.isoformat(),
            "projected_building_count": self.projected_building_count,
            "projected_density_bldgs_per_sqkm": round(
                self.projected_density_bldgs_per_sqkm, 2
            ),
            "confidence": self.confidence,
            "basis": self.basis,
            "sources": self.sources,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Projector
# ---------------------------------------------------------------------------


class DevelopmentProjector:
    """Generate future development projections for a property area of interest.

    Args:
        base_year: Current year used as the projection baseline.
        aoi_area_sqkm: Area of the analysis zone in km² (default 12.6 km²
            for a 2 km buffer radius: π × 2² ≈ 12.57 km²).
        horizon_years: Tuple of future year offsets to project.
    """

    def __init__(
        self,
        base_year: Optional[int] = None,
        aoi_area_sqkm: float = 12.57,
        horizon_years: tuple = HORIZON_YEARS,
    ) -> None:
        import datetime

        self.base_year = base_year or datetime.date.today().year
        self.aoi_area_sqkm = aoi_area_sqkm
        self.horizon_years = horizon_years

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def project_from_history(
        self,
        historical_counts: List[Dict[str, Any]],
        permit_pipeline: Optional[List[Dict[str, Any]]] = None,
        zoning_parcels: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ProjectedDevelopment]:
        """Generate multi-horizon projections from historical building counts.

        Args:
            historical_counts: List of {year, building_count} dicts, sorted
                ascending.  Minimum 2 entries required for extrapolation.
            permit_pipeline: Optional list of approved-but-unbuilt permits,
                each with ``units`` or ``building_count`` key.
            zoning_parcels: Optional list of undeveloped parcels zoned for
                development, each with ``potential_units`` key.

        Returns:
            List of ProjectedDevelopment objects for each horizon year,
            sorted ascending.
        """
        projections: List[ProjectedDevelopment] = []

        base_count = self._latest_building_count(historical_counts)
        annual_growth = self._annual_growth_rate(historical_counts)

        for offset in self.horizon_years:
            horizon_year = self.base_year + offset
            projection_date = date(horizon_year, 1, 1)

            # Tier 1 — HIGH: approved permits
            permitted_delta = self._sum_permitted(permit_pipeline, offset)

            # Tier 2 — MEDIUM: zoning potential (partial realisation)
            zoning_delta = self._sum_zoning(zoning_parcels, offset)

            # Tier 3 — LOW: linear extrapolation of historical growth
            extrapolated_count = self._extrapolate(
                base_count=base_count,
                annual_rate=annual_growth,
                years=offset,
            )

            # Combined estimate (additive, highest-confidence data wins)
            if permitted_delta > 0:
                total = base_count + permitted_delta + zoning_delta
                confidence = CONFIDENCE_HIGH
                basis = (
                    f"Approved permit pipeline (+{permitted_delta} units) "
                    f"plus partial zoning realisation (+{zoning_delta} units)"
                )
                sources = ["permits", "zoning"]
            elif zoning_delta > 0:
                total = base_count + zoning_delta
                confidence = CONFIDENCE_MEDIUM
                basis = (
                    f"Zoning analysis: undeveloped parcels zoned for "
                    f"development (+{zoning_delta} potential units)"
                )
                sources = ["zoning"]
            else:
                total = extrapolated_count
                confidence = CONFIDENCE_LOW
                basis = (
                    f"Linear extrapolation of {annual_growth:.2%}/year "
                    f"historical growth rate over {offset} years"
                )
                sources = ["historical-osm"]

            density = total / max(self.aoi_area_sqkm, 0.01)
            projections.append(
                ProjectedDevelopment(
                    horizon_year=horizon_year,
                    projection_date=projection_date,
                    projected_building_count=max(0, int(round(total))),
                    projected_density_bldgs_per_sqkm=round(density, 2),
                    confidence=confidence,
                    basis=basis,
                    sources=sources,
                    metadata={
                        "base_count": base_count,
                        "annual_growth_rate": round(annual_growth, 4),
                        "extrapolated_count": extrapolated_count,
                        "permitted_delta": permitted_delta,
                        "zoning_delta": zoning_delta,
                    },
                )
            )

        projections.sort(key=lambda p: p.horizon_year)
        return projections

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _latest_building_count(
        self, historical_counts: List[Dict[str, Any]]
    ) -> int:
        """Return the most recent building count from the historical series."""
        if not historical_counts:
            return 0
        sorted_counts = sorted(historical_counts, key=lambda c: c["year"])
        return int(sorted_counts[-1].get("building_count", 0))

    def _annual_growth_rate(
        self, historical_counts: List[Dict[str, Any]]
    ) -> float:
        """Estimate mean annual growth rate via linear regression.

        Falls back to 0.0 if fewer than 2 data points are available.
        """
        if len(historical_counts) < 2:
            return 0.0

        sorted_counts = sorted(historical_counts, key=lambda c: c["year"])
        years = np.array([c["year"] for c in sorted_counts], dtype=float)
        counts = np.array(
            [c["building_count"] for c in sorted_counts], dtype=float
        )

        # Avoid division by zero for constant series
        if counts[0] == 0:
            return 0.0

        # Use relative growth: fit log(count) ~ a + b*year
        with np.errstate(divide="ignore", invalid="ignore"):
            log_counts = np.where(counts > 0, np.log(counts), 0.0)

        try:
            coeffs = np.polyfit(years - years[0], log_counts, 1)
            annual_rate = float(np.exp(coeffs[0]) - 1)
        except (np.linalg.LinAlgError, ValueError):
            annual_rate = 0.0

        # Cap at reasonable bounds to avoid absurd extrapolations
        return max(-0.20, min(0.20, annual_rate))

    def _extrapolate(
        self, base_count: int, annual_rate: float, years: int
    ) -> int:
        """Compound growth extrapolation from base_count."""
        return int(round(base_count * ((1 + annual_rate) ** years)))

    def _sum_permitted(
        self,
        permit_pipeline: Optional[List[Dict[str, Any]]],
        horizon_years: int,
    ) -> int:
        """Sum building units from approved permits expected within horizon."""
        if not permit_pipeline:
            return 0
        total = 0
        for permit in permit_pipeline:
            # Include permit if expected completion is within horizon
            expected_year = permit.get("expected_completion_year")
            if expected_year is None or expected_year <= self.base_year + horizon_years:
                total += int(permit.get("building_count", permit.get("units", 1)))
        return total

    def _sum_zoning(
        self,
        zoning_parcels: Optional[List[Dict[str, Any]]],
        horizon_years: int,
    ) -> int:
        """Estimate partial realisation of zoned-but-undeveloped parcels.

        Assumes a 30 % realisation rate for 5-year horizon, scaling linearly.
        This is a conservative heuristic appropriate for LOW/MEDIUM confidence.
        """
        if not zoning_parcels:
            return 0
        realisation_rate = min(1.0, 0.06 * horizon_years)  # ~30% at 5y, 60% at 10y
        total_potential = sum(
            int(p.get("potential_units", 0)) for p in zoning_parcels
        )
        return int(round(total_potential * realisation_rate))
