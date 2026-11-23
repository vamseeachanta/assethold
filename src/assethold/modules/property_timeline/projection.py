"""Development projection for the property_timeline module.

DevelopmentProjection provides a simple linear/log-linear extrapolation
of historical building density growth rates to produce 5/10/15-year
horizon estimates.  Three confidence tiers are supported:

  LOW    — statistical extrapolation of historical growth
  MEDIUM — zoning potential (if zoning_parcels supplied)
  HIGH   — approved permit pipeline (if permit_pipeline supplied)

The model is intentionally conservative and matches the scope described
in the WRK-023 plan Phase 4 review feedback: sophisticated ML models are
deferred to May 2026 when improved multimodal agents are available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Default horizon offsets in years
_DEFAULT_HORIZONS: Tuple[int, ...] = (5, 10, 15)

# Annual growth rate cap (±20 %/year)
_MAX_ANNUAL_RATE = 0.20

# Zoning realisation rate: 6 %/year (≈ 30 % over 5 years)
_ZONING_REALISATION_RATE_PER_YEAR = 0.06


@dataclass
class DevelopmentProjection:
    """A single future development estimate for one horizon year.

    Attributes:
        horizon_year: Target calendar year of the projection.
        projected_building_count: Estimated number of buildings.
        confidence: "high", "medium", or "low".
        basis: Human-readable explanation of the projection method.
        projected_density_bldgs_per_sqkm: Building density estimate.
        sources: Data source labels used.
        metadata: Additional projection parameters.
    """

    horizon_year: int
    projected_building_count: int
    confidence: str
    basis: str
    projected_density_bldgs_per_sqkm: float = 0.0
    sources: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "horizon_year": self.horizon_year,
            "projected_building_count": self.projected_building_count,
            "projected_density_bldgs_per_sqkm": round(
                self.projected_density_bldgs_per_sqkm, 2
            ),
            "confidence": self.confidence,
            "basis": self.basis,
            "sources": self.sources,
            "metadata": self.metadata,
        }

    # ------------------------------------------------------------------
    # Class-method factory
    # ------------------------------------------------------------------

    @classmethod
    def from_history(
        cls,
        historical_counts: List[Dict[str, Any]],
        base_year: int,
        horizon_years: Tuple[int, ...] = _DEFAULT_HORIZONS,
        aoi_area_sqkm: float = 12.57,
        permit_pipeline: Optional[List[Dict[str, Any]]] = None,
        zoning_parcels: Optional[List[Dict[str, Any]]] = None,
    ) -> List["DevelopmentProjection"]:
        """Generate multi-horizon projections from historical building counts.

        Args:
            historical_counts: List of {year, building_count} dicts.
                Minimum 2 entries required for extrapolation.
            base_year: Reference year for computing horizon years.
            horizon_years: Tuple of year offsets from base_year to project.
            aoi_area_sqkm: Area of the analysis zone in km².
            permit_pipeline: Optional list of approved-but-unbuilt permits,
                each with ``building_count`` or ``units`` and optionally
                ``expected_completion_year``.
            zoning_parcels: Optional list of undeveloped parcels zoned for
                development, each with ``potential_units``.

        Returns:
            List of DevelopmentProjection sorted ascending by horizon_year.
        """
        base_count = _latest_building_count(historical_counts)
        annual_rate = _annual_growth_rate(historical_counts)

        projections: List[DevelopmentProjection] = []

        for offset in horizon_years:
            target_year = base_year + offset

            permitted_delta = _sum_permitted(permit_pipeline, base_year, target_year)
            zoning_delta = _sum_zoning(zoning_parcels, offset)
            extrapolated = int(round(base_count * ((1 + annual_rate) ** offset)))

            if permitted_delta > 0:
                total = base_count + permitted_delta + zoning_delta
                confidence = "high"
                basis = (
                    f"Approved permit pipeline (+{permitted_delta} units) "
                    f"plus partial zoning realisation (+{zoning_delta} units)"
                )
                sources = ["permits", "zoning"]
            elif zoning_delta > 0:
                total = base_count + zoning_delta
                confidence = "medium"
                basis = (
                    f"Zoning analysis: undeveloped parcels zoned for "
                    f"development (+{zoning_delta} potential units)"
                )
                sources = ["zoning"]
            else:
                total = extrapolated
                confidence = "low"
                basis = (
                    f"Linear extrapolation of {annual_rate:.2%}/year "
                    f"historical growth rate over {offset} years"
                )
                sources = ["historical-osm"]

            density = max(0.0, total) / max(aoi_area_sqkm, 0.01)
            projections.append(
                cls(
                    horizon_year=target_year,
                    projected_building_count=max(0, int(round(total))),
                    projected_density_bldgs_per_sqkm=round(density, 2),
                    confidence=confidence,
                    basis=basis,
                    sources=sources,
                    metadata={
                        "base_count": base_count,
                        "annual_growth_rate": round(annual_rate, 4),
                        "extrapolated_count": extrapolated,
                        "permitted_delta": permitted_delta,
                        "zoning_delta": zoning_delta,
                    },
                )
            )

        projections.sort(key=lambda p: p.horizon_year)
        return projections


# ---------------------------------------------------------------------------
# Private helper functions
# ---------------------------------------------------------------------------


def _latest_building_count(counts: List[Dict[str, Any]]) -> int:
    """Return the most recent building count from the time series."""
    if not counts:
        return 0
    return int(sorted(counts, key=lambda c: c["year"])[-1].get("building_count", 0))


def _annual_growth_rate(counts: List[Dict[str, Any]]) -> float:
    """Estimate mean annual growth rate via log-linear regression.

    Falls back to 0.0 for fewer than 2 data points or a constant series.
    Rate is capped at ±_MAX_ANNUAL_RATE to prevent absurd extrapolations.
    """
    if len(counts) < 2:
        return 0.0

    sorted_counts = sorted(counts, key=lambda c: c["year"])
    years = np.array([c["year"] for c in sorted_counts], dtype=float)
    bldg = np.array([c["building_count"] for c in sorted_counts], dtype=float)

    if bldg[0] == 0:
        return 0.0

    with np.errstate(divide="ignore", invalid="ignore"):
        log_bldg = np.where(bldg > 0, np.log(bldg), 0.0)

    try:
        coeffs = np.polyfit(years - years[0], log_bldg, 1)
        rate = float(np.exp(coeffs[0]) - 1)
    except (np.linalg.LinAlgError, ValueError):
        return 0.0

    return max(-_MAX_ANNUAL_RATE, min(_MAX_ANNUAL_RATE, rate))


def _sum_permitted(
    pipeline: Optional[List[Dict[str, Any]]],
    base_year: int,
    target_year: int,
) -> int:
    """Sum building units from permits expected to complete by target_year."""
    if not pipeline:
        return 0
    total = 0
    for permit in pipeline:
        expected = permit.get("expected_completion_year", target_year)
        if expected <= target_year:
            total += int(
                permit.get("building_count", permit.get("units", 1))
            )
    return total


def _sum_zoning(
    parcels: Optional[List[Dict[str, Any]]],
    horizon_years: int,
) -> int:
    """Estimate partial realisation of zoned-but-undeveloped parcels.

    Uses a 6 %/year realisation rate, capped at 100 %.
    """
    if not parcels:
        return 0
    rate = min(1.0, _ZONING_REALISATION_RATE_PER_YEAR * horizon_years)
    total_potential = sum(int(p.get("potential_units", 0)) for p in parcels)
    return int(round(total_potential * rate))
