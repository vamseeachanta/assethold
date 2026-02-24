"""Geocoder: address-to-coordinate conversion and property boundary lookup.

Converts a property address to (lat, lon) using the Nominatim geocoder (OSM)
and computes a bounding box suitable for satellite imagery queries.

External dependency: geopy (pure Python, no C libs required).
Falls back to a stub when geopy is not installed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PropertyLocation:
    """Geocoded property location with derived spatial metadata.

    Attributes:
        address: Original input address string.
        latitude: WGS-84 latitude (decimal degrees).
        longitude: WGS-84 longitude (decimal degrees).
        display_name: Full resolved address from geocoder.
        bounding_box: (min_lat, max_lat, min_lon, max_lon) tuple.
        buffer_km: Radius in km used to compute the bounding box.
    """

    address: str
    latitude: float
    longitude: float
    display_name: str = ""
    bounding_box: Tuple[float, float, float, float] = field(
        default_factory=lambda: (0.0, 0.0, 0.0, 0.0)
    )
    buffer_km: float = 2.0

    @property
    def centroid(self) -> Tuple[float, float]:
        """Return (lat, lon) tuple."""
        return (self.latitude, self.longitude)

    @property
    def bbox_dict(self) -> dict:
        """Bounding box as labeled dict for use with imagery APIs."""
        min_lat, max_lat, min_lon, max_lon = self.bounding_box
        return {
            "min_lat": min_lat,
            "max_lat": max_lat,
            "min_lon": min_lon,
            "max_lon": max_lon,
        }


# ---------------------------------------------------------------------------
# Geocoder
# ---------------------------------------------------------------------------


class Geocoder:
    """Geocode property addresses and compute spatial extents for AOI queries.

    Uses OSM Nominatim by default (free, no API key).  Nominatim has a
    1-request/second rate limit; the caller is responsible for throttling when
    processing batches.

    Args:
        user_agent: Identifier string sent to Nominatim (required by ToS).
        buffer_km: Buffer radius in km around the property centroid.
        timeout: HTTP request timeout in seconds.
    """

    # Degrees-per-km approximation (good to ~1% for latitudes <60°)
    _KM_PER_DEG_LAT = 110.574
    _KM_PER_DEG_LON_AT_EQUATOR = 111.320

    def __init__(
        self,
        user_agent: str = "assethold-gis/0.1",
        buffer_km: float = 2.0,
        timeout: int = 10,
    ) -> None:
        self.user_agent = user_agent
        self.buffer_km = buffer_km
        self.timeout = timeout
        self._geolocator: Optional[object] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def geocode(self, address: str) -> Optional[PropertyLocation]:
        """Geocode an address string to a PropertyLocation.

        Returns None if the address cannot be resolved.

        Args:
            address: Full property address, e.g. "123 Main St, Houston, TX 77002".
        """
        try:
            geolocator = self._get_geolocator()
            location = geolocator.geocode(address, timeout=self.timeout)
        except ImportError:
            logger.warning(
                "geopy not installed; returning stub location. "
                "Install with: pip install geopy"
            )
            return self._stub_location(address)
        except Exception as exc:
            logger.error("Geocoding failed for '%s': %s", address, exc)
            return None

        if location is None:
            logger.warning("No geocoding result for address: %s", address)
            return None

        bbox = self._compute_bounding_box(
            lat=location.latitude,
            lon=location.longitude,
            buffer_km=self.buffer_km,
        )

        return PropertyLocation(
            address=address,
            latitude=location.latitude,
            longitude=location.longitude,
            display_name=location.address,
            bounding_box=bbox,
            buffer_km=self.buffer_km,
        )

    def compute_bounding_box(
        self,
        lat: float,
        lon: float,
        buffer_km: Optional[float] = None,
    ) -> Tuple[float, float, float, float]:
        """Compute a rectangular bounding box around (lat, lon).

        Args:
            lat: Centre latitude in decimal degrees.
            lon: Centre longitude in decimal degrees.
            buffer_km: Override the instance default buffer radius.

        Returns:
            (min_lat, max_lat, min_lon, max_lon) tuple.
        """
        km = buffer_km if buffer_km is not None else self.buffer_km
        return self._compute_bounding_box(lat, lon, km)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_geolocator(self) -> object:
        """Lazy-load the Nominatim geolocator."""
        if self._geolocator is None:
            from geopy.geocoders import Nominatim  # type: ignore[import]

            self._geolocator = Nominatim(
                user_agent=self.user_agent,
                timeout=self.timeout,
            )
        return self._geolocator

    def _compute_bounding_box(
        self,
        lat: float,
        lon: float,
        buffer_km: float,
    ) -> Tuple[float, float, float, float]:
        """Rectangular bounding box using simple degree-per-km conversion."""
        import math

        delta_lat = buffer_km / self._KM_PER_DEG_LAT
        # Longitude degrees per km vary with latitude
        delta_lon = buffer_km / (
            self._KM_PER_DEG_LON_AT_EQUATOR * math.cos(math.radians(lat))
        )
        return (
            lat - delta_lat,
            lat + delta_lat,
            lon - delta_lon,
            lon + delta_lon,
        )

    def _stub_location(self, address: str) -> PropertyLocation:
        """Return a zero-coordinate stub when geopy is unavailable."""
        bbox = self._compute_bounding_box(0.0, 0.0, self.buffer_km)
        return PropertyLocation(
            address=address,
            latitude=0.0,
            longitude=0.0,
            display_name="[stub — geopy not installed]",
            bounding_box=bbox,
            buffer_km=self.buffer_km,
        )
