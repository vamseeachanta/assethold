"""Unit tests for the GIS Geocoder module.

Tests address geocoding, bounding box computation, and graceful fallback
when geopy is unavailable.  All tests use mocked geopy responses — no
network calls are made.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

from assethold.modules.gis.geocoder import Geocoder, PropertyLocation

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def geocoder() -> Geocoder:
    """Geocoder with default 2 km buffer."""
    return Geocoder(user_agent="assethold-gis-test/0.1", buffer_km=2.0, timeout=5)


@pytest.fixture
def mock_nominatim_location() -> MagicMock:
    """Fake geopy location object simulating Houston TX downtown."""
    loc = MagicMock()
    loc.latitude = 29.7604
    loc.longitude = -95.3698
    loc.address = "1 Main Street, Houston, TX 77002, United States"
    return loc


# ---------------------------------------------------------------------------
# PropertyLocation tests
# ---------------------------------------------------------------------------


class TestPropertyLocation:
    def test_centroid_returns_lat_lon_tuple(self) -> None:
        loc = PropertyLocation(
            address="123 Test St",
            latitude=29.76,
            longitude=-95.37,
            bounding_box=(29.74, 29.78, -95.39, -95.35),
        )
        assert loc.centroid == (29.76, -95.37)

    def test_bbox_dict_has_expected_keys(self) -> None:
        loc = PropertyLocation(
            address="123 Test St",
            latitude=29.76,
            longitude=-95.37,
            bounding_box=(29.74, 29.78, -95.39, -95.35),
        )
        bbox = loc.bbox_dict
        assert set(bbox.keys()) == {"min_lat", "max_lat", "min_lon", "max_lon"}
        assert bbox["min_lat"] == 29.74
        assert bbox["max_lat"] == 29.78
        assert bbox["min_lon"] == -95.39
        assert bbox["max_lon"] == -95.35

    def test_buffer_km_default_is_two(self) -> None:
        loc = PropertyLocation(address="test", latitude=0.0, longitude=0.0)
        assert loc.buffer_km == 2.0


# ---------------------------------------------------------------------------
# Geocoder.compute_bounding_box tests
# ---------------------------------------------------------------------------


class TestGeocoderBoundingBox:
    def test_bounding_box_has_four_elements(self, geocoder: Geocoder) -> None:
        bbox = geocoder.compute_bounding_box(lat=29.76, lon=-95.37)
        assert len(bbox) == 4

    def test_bounding_box_lat_range_correct(self, geocoder: Geocoder) -> None:
        lat, lon = 29.76, -95.37
        min_lat, max_lat, min_lon, max_lon = geocoder.compute_bounding_box(lat, lon)
        assert min_lat < lat < max_lat

    def test_bounding_box_lon_range_correct(self, geocoder: Geocoder) -> None:
        lat, lon = 29.76, -95.37
        min_lat, max_lat, min_lon, max_lon = geocoder.compute_bounding_box(lat, lon)
        assert min_lon < lon < max_lon

    def test_bounding_box_buffer_scales_proportionally(
        self, geocoder: Geocoder
    ) -> None:
        lat, lon = 29.76, -95.37
        bbox_2km = geocoder.compute_bounding_box(lat, lon, buffer_km=2.0)
        bbox_4km = geocoder.compute_bounding_box(lat, lon, buffer_km=4.0)
        lat_span_2km = bbox_2km[1] - bbox_2km[0]
        lat_span_4km = bbox_4km[1] - bbox_4km[0]
        assert pytest.approx(lat_span_4km / lat_span_2km, rel=0.02) == 2.0

    def test_bounding_box_is_symmetric_around_centre(self, geocoder: Geocoder) -> None:
        lat, lon = 29.76, -95.37
        min_lat, max_lat, min_lon, max_lon = geocoder.compute_bounding_box(lat, lon)
        lat_centre = (min_lat + max_lat) / 2
        assert pytest.approx(lat_centre, abs=1e-6) == lat

    def test_equator_box_is_approximately_correct_size(self) -> None:
        gc = Geocoder(buffer_km=1.0)
        min_lat, max_lat, min_lon, max_lon = gc.compute_bounding_box(0.0, 0.0)
        # 1 km / 110.574 km/deg ≈ 0.00905 degrees latitude
        expected_half_lat = 1.0 / 110.574
        assert pytest.approx(max_lat - min_lat, rel=0.01) == 2 * expected_half_lat

    def test_zero_buffer_gives_zero_extent_box(self) -> None:
        gc = Geocoder(buffer_km=0.0)
        min_lat, max_lat, min_lon, max_lon = gc.compute_bounding_box(29.76, -95.37, 0.0)
        assert min_lat == max_lat
        assert min_lon == max_lon


# ---------------------------------------------------------------------------
# Geocoder.geocode tests (mocked network)
# ---------------------------------------------------------------------------


class TestGeocoderGeocode:
    def test_geocode_returns_property_location_on_success(
        self,
        geocoder: Geocoder,
        mock_nominatim_location: MagicMock,
    ) -> None:
        with patch.object(geocoder, "_get_geolocator") as mock_get_geo:
            mock_geo = MagicMock()
            mock_geo.geocode.return_value = mock_nominatim_location
            mock_get_geo.return_value = mock_geo

            result = geocoder.geocode("1 Main Street, Houston, TX")

        assert result is not None
        assert isinstance(result, PropertyLocation)
        assert result.latitude == pytest.approx(29.7604, abs=1e-4)
        assert result.longitude == pytest.approx(-95.3698, abs=1e-4)

    def test_geocode_sets_display_name(
        self,
        geocoder: Geocoder,
        mock_nominatim_location: MagicMock,
    ) -> None:
        with patch.object(geocoder, "_get_geolocator") as mock_get_geo:
            mock_geo = MagicMock()
            mock_geo.geocode.return_value = mock_nominatim_location
            mock_get_geo.return_value = mock_geo

            result = geocoder.geocode("1 Main Street, Houston, TX")

        assert result is not None
        assert "Houston" in result.display_name

    def test_geocode_returns_none_when_address_not_found(
        self, geocoder: Geocoder
    ) -> None:
        with patch.object(geocoder, "_get_geolocator") as mock_get_geo:
            mock_geo = MagicMock()
            mock_geo.geocode.return_value = None
            mock_get_geo.return_value = mock_geo

            result = geocoder.geocode("zzz nonexistent address xyz")

        assert result is None

    def test_geocode_returns_none_on_network_exception(
        self, geocoder: Geocoder
    ) -> None:
        with patch.object(geocoder, "_get_geolocator") as mock_get_geo:
            mock_geo = MagicMock()
            mock_geo.geocode.side_effect = Exception("Connection refused")
            mock_get_geo.return_value = mock_geo

            result = geocoder.geocode("Some Address")

        assert result is None

    def test_geocode_returns_stub_when_geopy_not_installed(
        self, geocoder: Geocoder
    ) -> None:
        with patch.object(geocoder, "_get_geolocator") as mock_get_geo:
            mock_get_geo.side_effect = ImportError("geopy not installed")

            result = geocoder.geocode("1 Main Street, Houston, TX")

        assert result is not None
        assert "stub" in result.display_name.lower()
        assert result.latitude == 0.0
        assert result.longitude == 0.0

    def test_geocode_computes_bounding_box_around_result(
        self,
        geocoder: Geocoder,
        mock_nominatim_location: MagicMock,
    ) -> None:
        with patch.object(geocoder, "_get_geolocator") as mock_get_geo:
            mock_geo = MagicMock()
            mock_geo.geocode.return_value = mock_nominatim_location
            mock_get_geo.return_value = mock_geo

            result = geocoder.geocode("1 Main Street, Houston, TX")

        assert result is not None
        min_lat, max_lat, min_lon, max_lon = result.bounding_box
        assert min_lat < result.latitude < max_lat
        assert min_lon < result.longitude < max_lon
