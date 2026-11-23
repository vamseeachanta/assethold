"""Imagery fetcher: download historical satellite imagery for a property AOI.

Supports two backends:
- Google Earth Engine via ``geemap`` (preferred; free, cloud-processed)
- USGS EarthExplorer via ``landsatxplore`` (fallback; requires local download)

Both backends are optional at import time.  The module degrades gracefully to
stub behaviour when neither is installed.

NOTE: Full implementation deferred to May 2026 per WRK-023 disposition.
      This module provides the interface contract and stub implementations.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ImageryScene:
    """Metadata for a single satellite imagery scene.

    Attributes:
        scene_id: Unique identifier from the imagery provider.
        source: Provider name, e.g. "landsat-c2", "sentinel-2".
        acquisition_date: Date image was captured.
        cloud_cover_pct: Cloud cover percentage (0–100).
        resolution_m: Ground sampling distance in metres.
        bands: List of available spectral bands.
        local_path: Local file path if downloaded; None if cloud-only.
        bbox: (min_lat, max_lat, min_lon, max_lon) scene footprint.
    """

    scene_id: str
    source: str
    acquisition_date: date
    cloud_cover_pct: float
    resolution_m: float
    bands: List[str] = field(default_factory=list)
    local_path: Optional[str] = None
    bbox: Tuple[float, float, float, float] = field(
        default_factory=lambda: (0.0, 0.0, 0.0, 0.0)
    )

    @property
    def year(self) -> int:
        return self.acquisition_date.year

    def is_usable(self, max_cloud_pct: float = 20.0) -> bool:
        """Return True if cloud cover is below the threshold."""
        return self.cloud_cover_pct <= max_cloud_pct


# ---------------------------------------------------------------------------
# Imagery fetcher
# ---------------------------------------------------------------------------


class ImageryFetcher:
    """Download and cache historical satellite imagery scenes for an AOI.

    The fetcher queries a configurable list of sources at 5-year intervals
    and applies cloud-cover filtering.  Images are saved to
    ``data/gis/{property_id}/imagery/``.

    Args:
        output_dir: Root directory for cached imagery.
        max_cloud_pct: Maximum acceptable cloud cover (default 20 %).
        year_step: Interval in years between imagery samples (default 5).
    """

    SUPPORTED_SOURCES = ("landsat-c2", "sentinel-2", "stub")

    def __init__(
        self,
        output_dir: str = "data/gis",
        max_cloud_pct: float = 20.0,
        year_step: int = 5,
    ) -> None:
        self.output_dir = output_dir
        self.max_cloud_pct = max_cloud_pct
        self.year_step = year_step

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_timeline(
        self,
        property_id: str,
        bbox: Tuple[float, float, float, float],
        start_year: int = 1990,
        end_year: Optional[int] = None,
        sources: Optional[List[str]] = None,
    ) -> List[ImageryScene]:
        """Fetch imagery scenes for a property AOI across a date range.

        Returns a chronologically sorted list of usable scenes (one per
        sample year per source where cloud cover is acceptable).

        Args:
            property_id: Slug used for local cache directory naming.
            bbox: (min_lat, max_lat, min_lon, max_lon) area of interest.
            start_year: First year to sample.
            end_year: Last year to sample (defaults to current year).
            sources: List of sources to query; defaults to all supported.
        """
        import datetime

        if end_year is None:
            end_year = datetime.date.today().year
        if sources is None:
            sources = list(self.SUPPORTED_SOURCES)

        sample_years = list(range(start_year, end_year + 1, self.year_step))
        # Always include the end year for current state
        if end_year not in sample_years:
            sample_years.append(end_year)

        scenes: List[ImageryScene] = []
        for year in sorted(sample_years):
            for source in sources:
                scene = self._fetch_scene(
                    property_id=property_id,
                    bbox=bbox,
                    year=year,
                    source=source,
                )
                if scene is not None and scene.is_usable(self.max_cloud_pct):
                    scenes.append(scene)

        scenes.sort(key=lambda s: s.acquisition_date)
        logger.info(
            "Fetched %d usable scenes for property '%s' (%d–%d)",
            len(scenes),
            property_id,
            start_year,
            end_year,
        )
        return scenes

    def build_property_dir(self, property_id: str) -> str:
        """Return (and create) the local cache directory for a property."""
        path = os.path.join(self.output_dir, property_id, "imagery")
        os.makedirs(path, exist_ok=True)
        return path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_scene(
        self,
        property_id: str,
        bbox: Tuple[float, float, float, float],
        year: int,
        source: str,
    ) -> Optional[ImageryScene]:
        """Dispatch to the appropriate backend for a single scene."""
        if source == "landsat-c2":
            return self._fetch_landsat(property_id, bbox, year)
        if source == "sentinel-2":
            return self._fetch_sentinel(property_id, bbox, year)
        if source == "stub":
            return self._fetch_stub(property_id, bbox, year)
        logger.warning("Unknown imagery source: %s", source)
        return None

    def _fetch_landsat(
        self,
        property_id: str,
        bbox: Tuple[float, float, float, float],
        year: int,
    ) -> Optional[ImageryScene]:
        """Fetch Landsat Collection 2 scene via landsatxplore (stub)."""
        logger.debug(
            "Landsat fetch not yet implemented (deferred to May 2026). "
            "property=%s year=%d",
            property_id,
            year,
        )
        # TODO: implement via landsatxplore when full build resumes
        return None

    def _fetch_sentinel(
        self,
        property_id: str,
        bbox: Tuple[float, float, float, float],
        year: int,
    ) -> Optional[ImageryScene]:
        """Fetch Sentinel-2 scene via sentinelsat (stub)."""
        logger.debug(
            "Sentinel-2 fetch not yet implemented (deferred to May 2026). "
            "property=%s year=%d",
            property_id,
            year,
        )
        # TODO: implement via sentinelsat when full build resumes
        return None

    def _fetch_stub(
        self,
        property_id: str,
        bbox: Tuple[float, float, float, float],
        year: int,
    ) -> ImageryScene:
        """Return a synthetic stub scene for testing without API access."""
        return ImageryScene(
            scene_id=f"stub-{property_id}-{year}",
            source="stub",
            acquisition_date=date(year, 7, 1),
            cloud_cover_pct=5.0,
            resolution_m=30.0,
            bands=["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"],
            local_path=None,
            bbox=bbox,
        )

    # ------------------------------------------------------------------
    # GEE / geemap integration (Phase 2 — deferred)
    # ------------------------------------------------------------------

    def generate_timelapse_gif(
        self,
        property_id: str,
        bbox: Tuple[float, float, float, float],
        start_year: int = 2000,
        end_year: Optional[int] = None,
        output_path: Optional[str] = None,
    ) -> Optional[str]:
        """Generate animated GIF timelapse via geemap/Google Earth Engine.

        Requires: ``pip install geemap`` and authenticated GEE account.
        Returns the output GIF path, or None if geemap is unavailable.

        Args:
            property_id: Used for output file naming.
            bbox: (min_lat, max_lat, min_lon, max_lon) AOI.
            start_year: First year for the timelapse.
            end_year: Last year (default: current year).
            output_path: Override output file path.
        """
        import datetime

        if end_year is None:
            end_year = datetime.date.today().year

        try:
            import geemap  # type: ignore[import]
            import ee  # type: ignore[import]
        except ImportError:
            logger.warning(
                "geemap/earthengine-api not installed. "
                "Install with: pip install geemap"
            )
            return None

        if output_path is None:
            output_path = os.path.join(
                self.build_property_dir(property_id),
                f"{property_id}_timelapse_{start_year}_{end_year}.gif",
            )

        min_lat, max_lat, min_lon, max_lon = bbox
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2

        try:
            roi = ee.Geometry.Point([center_lon, center_lat]).buffer(2000)
            m = geemap.Map()
            m.add_landsat_ts_gif(
                roi=roi,
                start_year=start_year,
                end_year=end_year,
                bands=["Red", "Green", "Blue"],
                frames_per_second=3,
                out_gif=output_path,
            )
            logger.info("Timelapse GIF saved to: %s", output_path)
            return output_path
        except Exception as exc:
            logger.error("GEE timelapse generation failed: %s", exc)
            return None
