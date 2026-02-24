"""
spatial_factors.py — GIS-based spatial attribute extraction.

Extracts location-quality scores for a property from public data sources:
  - Flood zone (FEMA NFHL)
  - Traffic volume (AADT from state DOT data)
  - School quality (NCES / GreatSchools scale proxy)
  - Proximity to transit, parks, and commercial centers (OpenStreetMap)

Each factor is normalised to a [0, 1] score where 1 = most desirable.
The composite_score is a weighted average of individual factor scores.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from assethold.property.property_model import Property


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class FloodZone(Enum):
    """FEMA flood zone designations (simplified)."""

    ZONE_AE = "AE"       # High risk — special flood hazard area
    ZONE_A = "A"         # High risk — no base flood elevation determined
    ZONE_VE = "VE"       # High risk coastal — wave action
    ZONE_X500 = "X500"   # Moderate risk (0.2% annual chance)
    ZONE_X = "X"         # Minimal / moderate risk
    ZONE_D = "D"         # Undetermined risk
    UNKNOWN = "UNKNOWN"


class TrafficLevel(Enum):
    """Qualitative traffic level derived from AADT."""

    LOW = "low"            # < 5 000 AADT
    MODERATE = "moderate"  # 5 000 – 25 000 AADT
    HIGH = "high"          # 25 000 – 60 000 AADT
    VERY_HIGH = "very_high"  # > 60 000 AADT


# ---------------------------------------------------------------------------
# Score thresholds
# ---------------------------------------------------------------------------

_FLOOD_ZONE_SCORES: dict = {
    FloodZone.ZONE_AE: 0.15,
    FloodZone.ZONE_A: 0.15,
    FloodZone.ZONE_VE: 0.10,
    FloodZone.ZONE_X500: 0.55,
    FloodZone.ZONE_X: 0.95,
    FloodZone.ZONE_D: 0.50,
    FloodZone.UNKNOWN: 0.50,
}

_TRAFFIC_THRESHOLDS = [
    (5_000, TrafficLevel.LOW),
    (25_000, TrafficLevel.MODERATE),
    (60_000, TrafficLevel.HIGH),
]

# Composite score weights
_WEIGHTS = {
    "flood_zone": 0.25,
    "traffic": 0.20,
    "school": 0.25,
    "transit": 0.10,
    "park": 0.10,
    "commercial": 0.10,
}


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class SpatialFactors:
    """
    Collection of spatially-derived property quality scores.

    All *_score fields are normalised to [0, 1] (higher = more desirable).
    composite_score is a weighted average of the individual factor scores.
    """

    flood_zone: FloodZone
    flood_zone_score: float

    traffic_aadt: int
    traffic_level: TrafficLevel
    traffic_score: float

    school_rating: float       # 0–10 scale proxy
    school_score: float

    transit_distance_m: float
    transit_score: float

    park_distance_m: float
    park_score: float

    commercial_distance_m: float
    commercial_score: float

    composite_score: float


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class SpatialFactorExtractor:
    """
    Extracts and scores spatial factors for a given property.

    External data is fetched lazily; each `_get_*` method can be patched
    in tests or overridden in subclasses to supply real API responses.
    """

    # Default search radii
    _TRANSIT_MAX_M: float = 1_600.0   # ~1 mile
    _PARK_MAX_M: float = 2_000.0
    _COMMERCIAL_MAX_M: float = 2_000.0

    def extract(self, property_: Property) -> SpatialFactors:
        """
        Compute all spatial factors for the given property.

        Returns:
            SpatialFactors with individual scores and composite_score.
        """
        flood_zone, flood_score = self._get_flood_zone(property_)
        traffic_aadt, traffic_level, traffic_score = self._get_traffic_volume(property_)
        school_rating, school_score = self._get_school_rating(property_)
        transit_m, transit_score = self._get_transit_distance(property_)
        park_m, park_score = self._get_park_distance(property_)
        commercial_m, commercial_score = self._get_commercial_distance(property_)

        composite = self._compute_composite({
            "flood_zone": flood_score,
            "traffic": traffic_score,
            "school": school_score,
            "transit": transit_score,
            "park": park_score,
            "commercial": commercial_score,
        })

        return SpatialFactors(
            flood_zone=flood_zone,
            flood_zone_score=flood_score,
            traffic_aadt=traffic_aadt,
            traffic_level=traffic_level,
            traffic_score=traffic_score,
            school_rating=school_rating,
            school_score=school_score,
            transit_distance_m=transit_m,
            transit_score=transit_score,
            park_distance_m=park_m,
            park_score=park_score,
            commercial_distance_m=commercial_m,
            commercial_score=commercial_score,
            composite_score=composite,
        )

    # ------------------------------------------------------------------
    # Data-fetch stubs (override / patch for live data)
    # ------------------------------------------------------------------

    def _get_flood_zone(
        self, property_: Property
    ) -> Tuple[FloodZone, float]:
        """
        Return (FloodZone, score) for the property location.

        Default stub returns UNKNOWN with neutral score.
        Override or patch to call FEMA NFHL API:
          https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer
        """
        return self._score_flood_zone(FloodZone.UNKNOWN)

    def _get_traffic_volume(
        self, property_: Property
    ) -> Tuple[int, TrafficLevel, float]:
        """
        Return (aadt, TrafficLevel, score) for the nearest road.

        Default stub returns 0 (unknown / no data).
        Override or patch to query state DOT traffic count APIs.
        """
        return self._score_traffic(0)

    def _get_school_rating(
        self, property_: Property
    ) -> Tuple[float, float]:
        """
        Return (rating_0_to_10, score) for the nearest school.

        Default stub returns mid-range 5.0.
        Override or patch to query NCES boundary + rating data.
        """
        rating = 5.0
        score = rating / 10.0
        return rating, score

    def _get_transit_distance(
        self, property_: Property
    ) -> Tuple[float, float]:
        """
        Return (distance_m, score) to the nearest transit stop.

        Default stub returns max distance (no transit found).
        Override or patch to call OpenStreetMap Overpass API.
        """
        dist = self._TRANSIT_MAX_M
        score = self._distance_to_score(dist, self._TRANSIT_MAX_M)
        return dist, score

    def _get_park_distance(
        self, property_: Property
    ) -> Tuple[float, float]:
        """Return (distance_m, score) to the nearest park."""
        dist = self._PARK_MAX_M
        score = self._distance_to_score(dist, self._PARK_MAX_M)
        return dist, score

    def _get_commercial_distance(
        self, property_: Property
    ) -> Tuple[float, float]:
        """Return (distance_m, score) to the nearest commercial centre."""
        dist = self._COMMERCIAL_MAX_M
        score = self._distance_to_score(dist, self._COMMERCIAL_MAX_M)
        return dist, score

    # ------------------------------------------------------------------
    # Scoring primitives (tested directly)
    # ------------------------------------------------------------------

    def _score_flood_zone(
        self, zone: FloodZone
    ) -> Tuple[FloodZone, float]:
        """Map a FloodZone enum to (zone, score)."""
        score = _FLOOD_ZONE_SCORES.get(zone, 0.50)
        return zone, score

    def _score_traffic(
        self, aadt: int
    ) -> Tuple[int, TrafficLevel, float]:
        """
        Convert Annual Average Daily Traffic to (aadt, TrafficLevel, score).

        Score is 1.0 for zero traffic, decreasing logarithmically to ~0
        at very high volumes (100 000+ AADT).
        """
        level = TrafficLevel.VERY_HIGH
        for threshold, lvl in _TRAFFIC_THRESHOLDS:
            if aadt < threshold:
                level = lvl
                break

        # Logarithmic normalisation: score = 1 - log10(1 + aadt) / log10(1 + 100_000)
        max_aadt = 100_000.0
        if aadt <= 0:
            score = 1.0
        elif aadt >= max_aadt:
            score = 0.0
        else:
            score = 1.0 - math.log10(1 + aadt) / math.log10(1 + max_aadt)

        score = max(0.0, min(1.0, score))
        return aadt, level, score

    def _distance_to_score(
        self, distance_m: float, max_distance_m: float
    ) -> float:
        """
        Convert a proximity distance to a [0, 1] desirability score.

        Score = 1.0 at distance 0, linearly decreasing to 0.0 at max_distance_m.
        Distances beyond max are clamped to 0.0.
        """
        if max_distance_m <= 0:
            return 0.0
        score = 1.0 - (distance_m / max_distance_m)
        return max(0.0, min(1.0, score))

    def _compute_composite(self, scores: dict) -> float:
        """Weighted average of individual factor scores."""
        total_weight = sum(_WEIGHTS[k] for k in scores if k in _WEIGHTS)
        if total_weight == 0:
            return 0.5
        weighted_sum = sum(
            scores[k] * _WEIGHTS[k]
            for k in scores
            if k in _WEIGHTS
        )
        return max(0.0, min(1.0, weighted_sum / total_weight))
