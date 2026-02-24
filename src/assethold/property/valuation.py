"""
valuation.py — Spatial factor screening valuation model.

Produces an ESTIMATED RANGE for a US property based on:
  1. A base value (median comparable sale price or tax assessment).
  2. A spatial adjustment percentage derived from GIS factor scores.
  3. A confidence band applied symmetrically around the adjusted mid-point.

IMPORTANT DISCLAIMER:
  Output is an estimated screening range, NOT a certified real-estate appraisal.
  Do not use this output as the sole basis for purchase, financing, or legal
  decisions. Always consult a licensed appraiser for formal valuations.

Methodology:
  spatial_adjustment_pct = (composite_score - 0.5) * MAX_ADJUSTMENT_PCT * 2
  adjusted_mid           = base_value * (1 + spatial_adjustment_pct / 100)
  range_half_width       = adjusted_mid * confidence_band_pct
  low                    = adjusted_mid - range_half_width
  high                   = adjusted_mid + range_half_width
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from assethold.property.property_model import Property
from assethold.property.spatial_factors import SpatialFactors
from assethold.property.market_data import MarketDataResult


# Maximum spatial adjustment (±%) applied when composite_score = 0 or 1
_MAX_ADJUSTMENT_PCT: float = 15.0

# Confidence band half-width by confidence level
_CONFIDENCE_BANDS: Dict[str, float] = {
    "high": 0.05,    # ±5 %
    "medium": 0.10,  # ±10 %
    "low": 0.20,     # ±20 %
}

_DISCLAIMER = (
    "This is an estimated range produced by a spatial factor screening model "
    "for informational purposes only. It is NOT a certified real-estate "
    "appraisal and should not be used as the sole basis for any purchase, "
    "financing, insurance, or legal decision. Consult a licensed appraiser "
    "for a formal valuation."
)


class ValuationError(Exception):
    """Raised when a valuation cannot be computed."""


@dataclass
class ValuationResult:
    """
    Estimated value range for a property.

    All monetary values are in USD.
    """

    estimated_value_low: float
    estimated_value_high: float
    estimated_value_mid: float

    base_value: float              # anchor before spatial adjustment
    spatial_adjustment_pct: float  # positive = premium, negative = discount

    confidence: str                # "high" | "medium" | "low"
    data_source: str               # from MarketDataResult.data_source

    factor_scores: Dict[str, float]  # individual spatial scores
    disclaimer: str


class ValuationEngine:
    """
    Computes a screening-level value range for a property.

    Args:
        max_adjustment_pct:  Maximum spatial adjustment percentage (default 15 %).
    """

    def __init__(self, max_adjustment_pct: float = _MAX_ADJUSTMENT_PCT) -> None:
        self._max_adj = max_adjustment_pct

    def estimate(
        self,
        property_: Property,
        spatial_factors: SpatialFactors,
        market_data: MarketDataResult,
    ) -> ValuationResult:
        """
        Produce a ValuationResult for the given property.

        Args:
            property_:       Subject property.
            spatial_factors: Output from SpatialFactorExtractor.
            market_data:     Output from MarketDataProvider.

        Returns:
            ValuationResult with estimated range and factor breakdown.

        Raises:
            ValuationError: if no base value is available.
        """
        base_value = self._select_base_value(market_data)

        spatial_adj_pct = self._compute_spatial_adjustment(
            spatial_factors.composite_score
        )

        adjusted_mid = base_value * (1.0 + spatial_adj_pct / 100.0)

        confidence = self._determine_confidence(market_data)
        band = _CONFIDENCE_BANDS[confidence]

        low = adjusted_mid * (1.0 - band)
        high = adjusted_mid * (1.0 + band)

        factor_scores = {
            "flood_zone": spatial_factors.flood_zone_score,
            "traffic": spatial_factors.traffic_score,
            "school": spatial_factors.school_score,
            "transit": spatial_factors.transit_score,
            "park": spatial_factors.park_score,
            "commercial": spatial_factors.commercial_score,
        }

        return ValuationResult(
            estimated_value_low=round(low, 2),
            estimated_value_high=round(high, 2),
            estimated_value_mid=round(adjusted_mid, 2),
            base_value=base_value,
            spatial_adjustment_pct=round(spatial_adj_pct, 3),
            confidence=confidence,
            data_source=market_data.data_source,
            factor_scores=factor_scores,
            disclaimer=_DISCLAIMER,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _select_base_value(self, market_data: MarketDataResult) -> float:
        """
        Choose the base value anchor.

        Priority: median comparable sale price → assessed value.
        Raises ValuationError if neither is available.
        """
        if market_data.median_comp_price is not None:
            return market_data.median_comp_price
        if market_data.assessed_value is not None:
            return market_data.assessed_value
        raise ValuationError(
            "Cannot compute valuation: no base value available "
            "(median comp price and assessed value are both None)"
        )

    def _compute_spatial_adjustment(self, composite_score: float) -> float:
        """
        Map composite_score [0, 1] to an adjustment percentage [-max, +max].

        composite_score = 0.5 → 0 % adjustment (neutral)
        composite_score = 1.0 → +max_adjustment_pct
        composite_score = 0.0 → -max_adjustment_pct
        """
        return (composite_score - 0.5) * self._max_adj * 2.0

    def _determine_confidence(self, market_data: MarketDataResult) -> str:
        """
        Assign a confidence level based on data quality.

        High:   3+ comparable sales in a supported county.
        Medium: 1-2 comps, or assessed value in a supported county.
        Low:    no comps and unsupported county (assessment only fallback).
        """
        n_comps = len(market_data.comparable_sales)
        if n_comps >= 3 and market_data.county_supported:
            return "high"
        if n_comps >= 1 or market_data.county_supported:
            return "medium"
        return "low"
