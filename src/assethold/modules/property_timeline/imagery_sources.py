"""Imagery source abstractions for historical satellite scene retrieval.

Provides:
- ImagerySource: abstract base class defining the fetch() contract
- StubImagerySource: deterministic test stub (no API key needed)
- GoogleEarthEngineSource: GEE stub (requires geemap + authenticated account)
- USGSEarthExplorerSource: USGS EarthExplorer stub (requires credentials)

The Landsat/GEE implementations are deferred to May 2026 per WRK-023
disposition. Stubs provide the interface contract for testing and
allow the rest of the pipeline to run without live API access.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scene dataclass
# ---------------------------------------------------------------------------


@dataclass
class ImageryScene:
    """Metadata for one historical satellite scene.

    Attributes:
        scene_id: Provider-assigned unique ID.
        source: Source label, e.g. "stub", "landsat-c2", "sentinel-2".
        acquisition_date: Date the scene was captured.
        cloud_cover_pct: Cloud cover 0–100 %.
        resolution_m: Ground sample distance in metres.
        bands: Available spectral band names.
        bbox: (min_lat, max_lat, min_lon, max_lon) of the scene footprint.
        local_path: Local file path if downloaded; None for cloud-only scenes.
    """

    scene_id: str
    source: str
    acquisition_date: date
    cloud_cover_pct: float = 0.0
    resolution_m: float = 30.0
    bands: List[str] = field(default_factory=list)
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    local_path: Optional[str] = None

    def is_usable(self, max_cloud_pct: float = 20.0) -> bool:
        """Return True if cloud cover is within the acceptable threshold."""
        return self.cloud_cover_pct <= max_cloud_pct


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class ImagerySource(ABC):
    """Abstract base class for satellite imagery providers.

    Concrete implementations must override ``fetch()``.
    """

    @abstractmethod
    def fetch(
        self,
        bbox: Tuple[float, float, float, float],
        start_year: int,
        end_year: int,
        year_step: int = 5,
    ) -> List[ImageryScene]:
        """Fetch imagery scenes for the given bounding box and year range.

        Args:
            bbox: (min_lat, max_lat, min_lon, max_lon) area of interest.
            start_year: First year to sample.
            end_year: Last year to sample (inclusive).
            year_step: Sampling interval in years.

        Returns:
            Chronologically sorted list of ImageryScene objects.
        """


# ---------------------------------------------------------------------------
# Stub source (used for testing + offline demos)
# ---------------------------------------------------------------------------


class StubImagerySource(ImagerySource):
    """Deterministic stub that returns synthetic scenes — no API required.

    Generates one scene per sample year with zero cloud cover and
    standardised Landsat band names.  Useful for unit tests and
    offline pipeline validation.
    """

    def fetch(
        self,
        bbox: Tuple[float, float, float, float],
        start_year: int,
        end_year: int,
        year_step: int = 5,
    ) -> List[ImageryScene]:
        years = list(range(start_year, end_year + 1, year_step))
        if end_year not in years:
            years.append(end_year)

        scenes = []
        for year in sorted(set(years)):
            scenes.append(
                ImageryScene(
                    scene_id=f"stub-{year}-001",
                    source="stub",
                    acquisition_date=date(year, 7, 1),
                    cloud_cover_pct=5.0,
                    resolution_m=30.0,
                    bands=["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"],
                    bbox=bbox,
                )
            )
        return scenes


# ---------------------------------------------------------------------------
# Google Earth Engine source (stub — deferred May 2026)
# ---------------------------------------------------------------------------


class GoogleEarthEngineSource(ImagerySource):
    """Google Earth Engine imagery source via geemap/earthengine-api.

    Full implementation deferred to May 2026 (WRK-023 disposition).
    Returns an empty list when geemap or ee are not installed.

    To use: ``pip install geemap`` and authenticate with ``earthengine authenticate``.
    """

    def fetch(
        self,
        bbox: Tuple[float, float, float, float],
        start_year: int,
        end_year: int,
        year_step: int = 5,
    ) -> List[ImageryScene]:
        try:
            import geemap  # type: ignore[import]  # noqa: F401
            import ee  # type: ignore[import]  # noqa: F401
        except ImportError:
            logger.warning(
                "geemap/earthengine-api not installed — GEE source unavailable. "
                "Install with: pip install geemap"
            )
            return []

        # TODO: implement full GEE Landsat time-series when resumed May 2026
        logger.warning(
            "GoogleEarthEngineSource.fetch() is a stub — full implementation "
            "deferred to May 2026 (WRK-023)."
        )
        return []


# ---------------------------------------------------------------------------
# USGS EarthExplorer source (stub — deferred May 2026)
# ---------------------------------------------------------------------------


class USGSEarthExplorerSource(ImagerySource):
    """USGS EarthExplorer Landsat Collection 2 source via landsatxplore.

    Full implementation deferred to May 2026 (WRK-023 disposition).
    Returns an empty list when credentials are not configured or the
    landsatxplore library is not installed.

    To use: set USGS_USERNAME and USGS_PASSWORD environment variables and
    install ``pip install landsatxplore``.
    """

    def fetch(
        self,
        bbox: Tuple[float, float, float, float],
        start_year: int,
        end_year: int,
        year_step: int = 5,
    ) -> List[ImageryScene]:
        try:
            import landsatxplore  # type: ignore[import]  # noqa: F401
        except ImportError:
            logger.warning(
                "landsatxplore not installed — USGS source unavailable. "
                "Install with: pip install landsatxplore"
            )
            return []

        # TODO: implement full USGS EarthExplorer download when resumed May 2026
        logger.warning(
            "USGSEarthExplorerSource.fetch() is a stub — full implementation "
            "deferred to May 2026 (WRK-023)."
        )
        return []
