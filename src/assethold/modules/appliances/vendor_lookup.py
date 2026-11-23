"""
vendor_lookup.py — Geographic vendor density analysis for appliance service companies.

Provides Haversine distance filtering, geocoding abstraction, and vendor search
so callers can determine how many preferred appliance service vendors operate
within a given geographic area.

External API calls are isolated behind _fetch_vendor_data and _geocode_address
so they can be mocked cleanly in tests without network access.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class VendorRecord:
    """A single appliance service vendor."""

    name: str
    address: str
    lat: float
    lon: float
    categories: List[str] = field(default_factory=list)
    phone: Optional[str] = None
    rating: Optional[float] = None


# ---------------------------------------------------------------------------
# VendorLookup
# ---------------------------------------------------------------------------

class VendorLookup:
    """
    Provides geographic vendor density queries for appliance service companies.

    External data retrieval is isolated in _fetch_vendor_data and
    _geocode_address — override or mock those methods to swap data sources.
    """

    # Radius of the Earth in kilometres (WGS-84 mean)
    _EARTH_RADIUS_KM = 6371.0

    # ------------------------------------------------------------------
    # Distance maths
    # ------------------------------------------------------------------

    def haversine_distance_km(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """
        Return the great-circle distance in kilometres between two WGS-84 points.
        """
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lam = math.radians(lon2 - lon1)

        a = (
            math.sin(d_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return self._EARTH_RADIUS_KM * c

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def filter_vendors_by_radius(
        self,
        vendors: List[VendorRecord],
        center_lat: float,
        center_lon: float,
        radius_km: float,
    ) -> List[VendorRecord]:
        """Return the subset of vendors within radius_km of the centre point."""
        result = []
        for vendor in vendors:
            dist = self.haversine_distance_km(
                center_lat, center_lon, vendor.lat, vendor.lon
            )
            if dist <= radius_km:
                result.append(vendor)
        return result

    def count_vendors_in_area(
        self,
        vendors: List[VendorRecord],
        center_lat: float,
        center_lon: float,
        radius_km: float,
    ) -> int:
        """Return the count of vendors within radius_km of the centre point."""
        return len(
            self.filter_vendors_by_radius(vendors, center_lat, center_lon, radius_km)
        )

    # ------------------------------------------------------------------
    # Geocoding boundary
    # ------------------------------------------------------------------

    def _geocode_address(self, address: str) -> Tuple[float, float]:
        """
        Convert an address string to (lat, lon).

        Override or mock this method to inject a real geocoding provider
        (e.g. Nominatim, Google Maps Geocoding API, or similar).
        Returns (0.0, 0.0) as a safe default — callers should verify.
        """
        return (0.0, 0.0)

    def geocode_location(self, location: str) -> Tuple[float, float]:
        """Public geocoding entry point.  Delegates to _geocode_address."""
        return self._geocode_address(location)

    # ------------------------------------------------------------------
    # External data boundary
    # ------------------------------------------------------------------

    def _fetch_vendor_data(
        self,
        location: str,
        category: str,
        radius_km: float,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve raw vendor data from an external source.

        Override or mock this method to connect to a real data source such as
        a web search API, Yelp Fusion, or a local cache.  Returns an empty
        list by default so the module is safe to use without credentials.

        Expected dict keys per vendor:
            name, address, lat, lon, categories, phone (opt), rating (opt)
        """
        return []

    # ------------------------------------------------------------------
    # High-level query API
    # ------------------------------------------------------------------

    def search_vendors(
        self,
        location: str,
        category: str,
        radius_km: float = 40.0,
    ) -> List[VendorRecord]:
        """
        Search for appliance service vendors near location for the given category.

        Converts raw dicts from _fetch_vendor_data into VendorRecord objects.
        """
        raw = self._fetch_vendor_data(location, category, radius_km)
        vendors = []
        for item in raw:
            vendors.append(
                VendorRecord(
                    name=item.get("name", ""),
                    address=item.get("address", ""),
                    lat=float(item.get("lat", 0.0)),
                    lon=float(item.get("lon", 0.0)),
                    categories=list(item.get("categories", [])),
                    phone=item.get("phone"),
                    rating=item.get("rating"),
                )
            )
        return vendors

    def vendor_count_by_location(
        self,
        location: str,
        category: str,
        radius_km: float = 40.0,
    ) -> int:
        """
        Return the number of service vendors for the given appliance category
        operating within radius_km of location.
        """
        vendors = self.search_vendors(location, category, radius_km)
        return len(vendors)
