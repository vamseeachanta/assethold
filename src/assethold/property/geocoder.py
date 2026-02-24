"""
geocoder.py — Address geocoding via Nominatim/OpenStreetMap.

Converts a US street address to (lat, lon) coordinates and infers
county/state context. No API key required.

Data source: OpenStreetMap Nominatim (https://nominatim.openstreetmap.org)
Usage policy: max 1 req/sec, must set a descriptive User-Agent.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import urllib.request
import urllib.parse
import json

# ---------------------------------------------------------------------------
# US state name → abbreviation map (used to normalise Nominatim responses)
# ---------------------------------------------------------------------------
_STATE_ABBREV: Dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
    "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY", "district of columbia": "DC",
}

# Supported counties: (county_lower, state_abbrev) → True
_SUPPORTED_COUNTIES: Dict[tuple, bool] = {
    ("harris", "TX"): True,
    ("los angeles", "CA"): True,
    ("cook", "IL"): True,
}


class GeocodeError(Exception):
    """Raised when geocoding fails or returns no results."""


@dataclass
class GeocoderResult:
    """Result from a successful geocode call."""

    lat: float
    lon: float
    display_name: str
    county: str
    state: str
    country: str
    raw: Dict[str, Any]


class Geocoder:
    """
    Geocodes US addresses using the Nominatim OpenStreetMap service.

    Args:
        user_agent: Identifies your application to Nominatim (required by
                    their usage policy; must be descriptive).
        timeout:    HTTP request timeout in seconds.
        provider:   Geocoding backend. Currently only "nominatim" is supported.
    """

    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    _MIN_REQUEST_INTERVAL = 1.1  # seconds (Nominatim: max 1 req/s)

    def __init__(
        self,
        user_agent: str = "assethold-property-valuation/1.0",
        timeout: int = 10,
        provider: str = "nominatim",
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.provider = provider
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def geocode(self, address: str) -> GeocoderResult:
        """
        Geocode a US address string.

        Args:
            address: Full US address (e.g. "123 Main St, Houston, TX 77001").

        Returns:
            GeocoderResult with lat/lon and county/state.

        Raises:
            ValueError:    if address is empty.
            GeocodeError:  if no result found or network/parsing error.
        """
        if not address or not address.strip():
            raise ValueError("address must be a non-empty string")

        try:
            raw = self._call_nominatim(address)
        except Exception as exc:
            raise GeocodeError(
                f"Geocoding failed for address {address!r}: {exc}"
            ) from exc

        if raw is None:
            raise GeocodeError(
                f"No results found for address {address!r}"
            )

        return self._parse_result(raw)

    def is_supported_county(self, county: str, state: str) -> bool:
        """Return True if the county has a supported assessor integration."""
        key = (county.lower(), state.upper())
        return _SUPPORTED_COUNTIES.get(key, False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_nominatim(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Call the Nominatim REST API and return the first result dict,
        or None if no results.

        Respects Nominatim's 1 req/sec rate limit.
        """
        self._throttle()

        params = urllib.parse.urlencode({
            "q": address,
            "format": "json",
            "addressdetails": "1",
            "limit": "1",
            "countrycodes": "us",
        })
        url = f"{self.NOMINATIM_URL}?{params}"

        req = urllib.request.Request(
            url, headers={"User-Agent": self.user_agent}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())

        self._last_request_time = time.monotonic()

        if not data:
            return None
        return data[0]

    def _throttle(self) -> None:
        """Sleep if needed to respect Nominatim rate limit."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._MIN_REQUEST_INTERVAL:
            time.sleep(self._MIN_REQUEST_INTERVAL - elapsed)

    def _parse_result(self, raw: Dict[str, Any]) -> GeocoderResult:
        """Parse a Nominatim result dict into a GeocoderResult."""
        address_data = raw.get("address", {})

        county_raw = (
            address_data.get("county")
            or address_data.get("borough")
            or ""
        )
        county = _strip_county_suffix(county_raw)

        state_raw = address_data.get("state", "")
        state = _normalise_state(state_raw)

        country_code = address_data.get("country_code", "us").upper()

        return GeocoderResult(
            lat=float(raw["lat"]),
            lon=float(raw["lon"]),
            display_name=raw.get("display_name", ""),
            county=county,
            state=state,
            country=country_code,
            raw=raw,
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _strip_county_suffix(county_name: str) -> str:
    """Remove ' County' suffix from Nominatim county strings."""
    suffixes = (" County", " Parish", " Borough", " Census Area")
    for suffix in suffixes:
        if county_name.endswith(suffix):
            return county_name[: -len(suffix)]
    return county_name


def _normalise_state(state_name: str) -> str:
    """Convert a full US state name to its two-letter abbreviation."""
    key = state_name.strip().lower()
    return _STATE_ABBREV.get(key, state_name.upper()[:2])
