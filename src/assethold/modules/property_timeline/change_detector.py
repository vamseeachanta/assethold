"""Development change detector for the property_timeline module.

DevelopmentChangeDetector wraps the lower-level NDVI primitives from
assethold.modules.gis.change_detector and converts their output into
DevelopmentChange objects used by the property_timeline pipeline.

Two detection modes:
1. detect()                 — array-based NDVI differencing (satellite bands)
2. detect_from_historical_records() — building-count comparison (OSM records)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List

import numpy as np

from assethold.modules.property_timeline.models import DevelopmentChange

logger = logging.getLogger(__name__)

# Minimum building-count delta to generate a change event (noise filter)
_MIN_BUILDING_DELTA = 3


class DevelopmentChangeDetector:
    """Detect development changes between two satellite imagery scenes or
    between consecutive historical building-count records.

    Args:
        loss_threshold: NDVI change below this value counts as vegetation
            loss / construction activity.  Default -0.15.
        gain_threshold: NDVI change above this value counts as vegetation
            gain.  Default 0.15.
        pixel_area_sqm: Ground area per pixel in m² (default 900 m² = 30 m
            Landsat resolution).
    """

    def __init__(
        self,
        loss_threshold: float = -0.15,
        gain_threshold: float = 0.15,
        pixel_area_sqm: float = 900.0,
    ) -> None:
        self.loss_threshold = loss_threshold
        self.gain_threshold = gain_threshold
        self.pixel_area_sqm = pixel_area_sqm

    # ------------------------------------------------------------------
    # Array-based detection (satellite imagery)
    # ------------------------------------------------------------------

    def detect(
        self,
        red_before: np.ndarray,
        nir_before: np.ndarray,
        red_after: np.ndarray,
        nir_after: np.ndarray,
        date_before: date,
        date_after: date,
    ) -> List[DevelopmentChange]:
        """Detect changes between two satellite scenes using NDVI differencing.

        Args:
            red_before / nir_before: Red + NIR band arrays for the earlier scene.
            red_after  / nir_after:  Red + NIR band arrays for the later scene.
            date_before: Acquisition date of the earlier scene.
            date_after:  Acquisition date of the later scene.

        Returns:
            List of DevelopmentChange objects.  Empty if no significant change.
        """
        ndvi_b = self._compute_ndvi(red_before, nir_before)
        ndvi_a = self._compute_ndvi(red_after, nir_after)
        diff = (ndvi_a - ndvi_b).astype(np.float32)

        changes: List[DevelopmentChange] = []

        # Vegetation loss → construction indicator
        loss_mask = diff <= self.loss_threshold
        loss_pixels = int(np.sum(loss_mask))
        if loss_pixels > 0:
            total_pixels = diff.size
            magnitude = min(1.0, loss_pixels / max(total_pixels, 1))
            area = loss_pixels * self.pixel_area_sqm
            changes.append(
                DevelopmentChange(
                    change_date=date_after,
                    change_type="vegetation_loss",
                    description=(
                        f"Vegetation loss over {area / 10_000:.2f} ha "
                        f"(mean NDVI Δ: {float(np.mean(diff[loss_mask])):.3f}). "
                        f"Likely construction activity."
                    ),
                    confidence=self._confidence(magnitude),
                    magnitude=round(magnitude, 4),
                    area_sqm=round(area, 1),
                    source="satellite-ndvi",
                )
            )

        # Vegetation gain → recovery or landscaping
        gain_mask = diff >= self.gain_threshold
        gain_pixels = int(np.sum(gain_mask))
        if gain_pixels > 0:
            total_pixels = diff.size
            magnitude = min(1.0, gain_pixels / max(total_pixels, 1))
            area = gain_pixels * self.pixel_area_sqm
            changes.append(
                DevelopmentChange(
                    change_date=date_after,
                    change_type="vegetation_gain",
                    description=(
                        f"Vegetation gain over {area / 10_000:.2f} ha. "
                        f"Landscaping or natural regrowth."
                    ),
                    confidence=self._confidence(magnitude),
                    magnitude=round(magnitude, 4),
                    area_sqm=round(area, 1),
                    source="satellite-ndvi",
                )
            )

        return changes

    # ------------------------------------------------------------------
    # Record-based detection (historical building counts)
    # ------------------------------------------------------------------

    def detect_from_historical_records(
        self,
        records: List[Dict[str, Any]],
    ) -> List[DevelopmentChange]:
        """Detect changes from year-over-year building-count records.

        Each record must contain ``year`` (int) and ``building_count`` (int).
        Consecutive pairs with a delta >= _MIN_BUILDING_DELTA produce a
        DevelopmentChange event.

        Args:
            records: List of {year, building_count} dicts in any order.

        Returns:
            List of DevelopmentChange objects, one per significant transition.
        """
        if len(records) < 2:
            return []

        sorted_records = sorted(records, key=lambda r: r["year"])
        changes: List[DevelopmentChange] = []

        for i in range(1, len(sorted_records)):
            prev = sorted_records[i - 1]
            curr = sorted_records[i]
            delta = curr["building_count"] - prev["building_count"]

            if abs(delta) < _MIN_BUILDING_DELTA:
                continue

            direction = "construction" if delta > 0 else "demolition"
            magnitude = min(1.0, abs(delta) / max(curr["building_count"], 1))
            changes.append(
                DevelopmentChange(
                    change_date=date(curr["year"], 1, 1),
                    change_type=direction,
                    description=(
                        f"Building count changed by {delta:+d} "
                        f"({prev['year']}→{curr['year']}): "
                        f"{prev['building_count']} → {curr['building_count']} buildings."
                    ),
                    confidence="medium",
                    magnitude=round(magnitude, 4),
                    source="osm-building-counts",
                    metadata={
                        "prev_year": prev["year"],
                        "curr_year": curr["year"],
                        "delta": delta,
                    },
                )
            )

        return changes

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_ndvi(
        red: np.ndarray, nir: np.ndarray
    ) -> np.ndarray:
        """Compute NDVI from red and NIR band arrays."""
        red_f = red.astype(np.float32)
        nir_f = nir.astype(np.float32)
        denom = nir_f + red_f
        with np.errstate(invalid="ignore", divide="ignore"):
            ndvi = np.where(denom != 0, (nir_f - red_f) / denom, 0.0)
        return ndvi.astype(np.float32)

    @staticmethod
    def _confidence(magnitude: float) -> str:
        """Map a change magnitude (0–1) to a confidence label."""
        if magnitude >= 0.10:
            return "high"
        if magnitude >= 0.03:
            return "medium"
        return "low"
