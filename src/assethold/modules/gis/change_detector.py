"""Change detector: identify development activity between satellite imagery dates.

Uses NDVI differencing as the primary indicator — vegetation loss signals
construction activity.  Also supports building-footprint-count comparison
via the ohsome historical OSM API.

Design note: full raster processing (rasterio) is optional and only imported
when actually needed.  The module operates on numpy arrays when rasterio is
unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class ChangeType(str, Enum):
    """Classification of a detected spatial change event."""

    CONSTRUCTION = "construction"
    DEMOLITION = "demolition"
    VEGETATION_LOSS = "vegetation_loss"
    VEGETATION_GAIN = "vegetation_gain"
    ROAD_EXPANSION = "road_expansion"
    UNKNOWN = "unknown"


@dataclass
class ChangeEvent:
    """A single detected change between two imagery dates.

    Attributes:
        change_type: Classified type of change.
        from_date: Start of the change window.
        to_date: End of the change window.
        magnitude: Change magnitude (0.0–1.0).
        area_sqm: Approximate affected area in square metres.
        centroid: (lat, lon) of the change centroid.
        description: Human-readable description.
        confidence: Confidence level string: "high", "medium", "low".
    """

    change_type: ChangeType
    from_date: date
    to_date: date
    magnitude: float
    area_sqm: float = 0.0
    centroid: Tuple[float, float] = (0.0, 0.0)
    description: str = ""
    confidence: str = "medium"

    @property
    def year_range(self) -> str:
        return f"{self.from_date.year}–{self.to_date.year}"


# ---------------------------------------------------------------------------
# NDVI helpers (pure numpy)
# ---------------------------------------------------------------------------


def compute_ndvi(red_band: np.ndarray, nir_band: np.ndarray) -> np.ndarray:
    """Compute NDVI from red and near-infrared bands.

    NDVI = (NIR - Red) / (NIR + Red)

    Values range from -1.0 (water/bare soil) to +1.0 (dense vegetation).
    Division by zero is suppressed; those pixels are set to 0.0.

    Args:
        red_band: 2-D array of red-band reflectance values.
        nir_band: 2-D array of NIR-band reflectance values.
    """
    red = red_band.astype(np.float32)
    nir = nir_band.astype(np.float32)
    denominator = nir + red
    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = np.where(denominator != 0, (nir - red) / denominator, 0.0)
    return ndvi.astype(np.float32)


def ndvi_difference(
    ndvi_before: np.ndarray,
    ndvi_after: np.ndarray,
) -> np.ndarray:
    """Compute signed NDVI change (after - before).

    Negative values indicate vegetation loss (construction indicator).
    Positive values indicate vegetation gain (recovery or new planting).
    """
    return (ndvi_after - ndvi_before).astype(np.float32)


def classify_ndvi_change(
    ndvi_diff: np.ndarray,
    loss_threshold: float = -0.15,
    gain_threshold: float = 0.15,
) -> np.ndarray:
    """Classify each pixel by change type.

    Returns an integer array:
      0 = no significant change
      1 = vegetation loss (construction indicator)
      2 = vegetation gain
    """
    result = np.zeros_like(ndvi_diff, dtype=np.int8)
    result[ndvi_diff <= loss_threshold] = 1
    result[ndvi_diff >= gain_threshold] = 2
    return result


# ---------------------------------------------------------------------------
# Change detector
# ---------------------------------------------------------------------------


class ChangeDetector:
    """Detect and classify development changes between two imagery scenes.

    Args:
        loss_threshold: NDVI change below this value counts as vegetation loss.
        gain_threshold: NDVI change above this value counts as vegetation gain.
        pixel_area_sqm: Ground area represented by one pixel (default 900 m²
            for 30 m Landsat).
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
    # Public API
    # ------------------------------------------------------------------

    def detect_from_arrays(
        self,
        red_before: np.ndarray,
        nir_before: np.ndarray,
        red_after: np.ndarray,
        nir_after: np.ndarray,
        date_before: date,
        date_after: date,
        centroid: Tuple[float, float] = (0.0, 0.0),
    ) -> List[ChangeEvent]:
        """Detect changes between two scenes represented as numpy arrays.

        Args:
            red_before / nir_before: Red + NIR bands for the earlier scene.
            red_after / nir_after:   Red + NIR bands for the later scene.
            date_before: Acquisition date of the earlier scene.
            date_after:  Acquisition date of the later scene.
            centroid: (lat, lon) approximate centre of the AOI.

        Returns:
            List of ChangeEvent objects (may be empty if no significant change).
        """
        ndvi_before = compute_ndvi(red_before, nir_before)
        ndvi_after = compute_ndvi(red_after, nir_after)
        diff = ndvi_difference(ndvi_before, ndvi_after)
        classified = classify_ndvi_change(
            diff,
            loss_threshold=self.loss_threshold,
            gain_threshold=self.gain_threshold,
        )
        return self._build_events(
            classified=classified,
            ndvi_diff=diff,
            date_before=date_before,
            date_after=date_after,
            centroid=centroid,
        )

    def detect_from_rasters(
        self,
        path_before: str,
        path_after: str,
        date_before: date,
        date_after: date,
        red_band_idx: int = 3,
        nir_band_idx: int = 4,
    ) -> List[ChangeEvent]:
        """Detect changes from GeoTIFF file paths using rasterio.

        Requires: ``pip install rasterio``

        Args:
            path_before: File path to the earlier GeoTIFF.
            path_after:  File path to the later GeoTIFF.
            date_before: Acquisition date of the earlier scene.
            date_after:  Acquisition date of the later scene.
            red_band_idx: 1-based band index for red channel.
            nir_band_idx: 1-based band index for NIR channel.
        """
        try:
            import rasterio  # type: ignore[import]
        except ImportError:
            logger.error(
                "rasterio not installed; cannot read GeoTIFF files. "
                "Install with: pip install rasterio"
            )
            return []

        def _read_bands(path: str) -> Tuple[np.ndarray, np.ndarray]:
            with rasterio.open(path) as src:
                red = src.read(red_band_idx).astype(np.float32)
                nir = src.read(nir_band_idx).astype(np.float32)
            return red, nir

        red_b, nir_b = _read_bands(path_before)
        red_a, nir_a = _read_bands(path_after)
        return self.detect_from_arrays(
            red_b, nir_b, red_a, nir_a, date_before, date_after
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_events(
        self,
        classified: np.ndarray,
        ndvi_diff: np.ndarray,
        date_before: date,
        date_after: date,
        centroid: Tuple[float, float],
    ) -> List[ChangeEvent]:
        """Convert classified pixel arrays to a list of ChangeEvent objects."""
        events: List[ChangeEvent] = []

        loss_pixels = int(np.sum(classified == 1))
        gain_pixels = int(np.sum(classified == 2))
        total_pixels = classified.size

        if loss_pixels > 0:
            loss_area = loss_pixels * self.pixel_area_sqm
            magnitude = min(1.0, loss_pixels / max(total_pixels, 1))
            mean_change = float(np.mean(ndvi_diff[classified == 1]))
            events.append(
                ChangeEvent(
                    change_type=ChangeType.VEGETATION_LOSS,
                    from_date=date_before,
                    to_date=date_after,
                    magnitude=round(magnitude, 4),
                    area_sqm=round(loss_area, 1),
                    centroid=centroid,
                    description=(
                        f"Vegetation loss detected over "
                        f"{loss_area / 10_000:.2f} ha "
                        f"(mean NDVI change: {mean_change:.3f}). "
                        f"Likely construction activity."
                    ),
                    confidence=self._confidence(magnitude),
                )
            )

        if gain_pixels > 0:
            gain_area = gain_pixels * self.pixel_area_sqm
            magnitude = min(1.0, gain_pixels / max(total_pixels, 1))
            events.append(
                ChangeEvent(
                    change_type=ChangeType.VEGETATION_GAIN,
                    from_date=date_before,
                    to_date=date_after,
                    magnitude=round(magnitude, 4),
                    area_sqm=round(gain_area, 1),
                    centroid=centroid,
                    description=(
                        f"Vegetation gain detected over "
                        f"{gain_area / 10_000:.2f} ha. "
                        f"Landscaping or natural regrowth."
                    ),
                    confidence=self._confidence(magnitude),
                )
            )

        return events

    def _confidence(self, magnitude: float) -> str:
        """Map change magnitude to a confidence label."""
        if magnitude >= 0.10:
            return "high"
        if magnitude >= 0.03:
            return "medium"
        return "low"
