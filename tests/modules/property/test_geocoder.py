"""
Tests for geocoder.py — Address geocoding and county assessor data.
TDD: red → green → refactor
"""
import pytest
from unittest.mock import patch, MagicMock

from assethold.property.geocoder import (
    Geocoder,
    GeocoderResult,
    GeocodeError,
)


class TestGeocoderResult:
    """Tests for GeocoderResult dataclass."""

    def test_geocoder_result_stores_fields(self):
        result = GeocoderResult(
            lat=29.7604,
            lon=-95.3698,
            display_name="123 Main St, Houston, TX 77001, USA",
            county="Harris",
            state="TX",
            country="US",
            raw={},
        )
        assert result.lat == pytest.approx(29.7604)
        assert result.lon == pytest.approx(-95.3698)
        assert result.county == "Harris"
        assert result.state == "TX"

    def test_geocoder_result_country_defaults_us(self):
        result = GeocoderResult(
            lat=34.0522,
            lon=-118.2437,
            display_name="456 Oak Ave, Los Angeles, CA 90001, USA",
            county="Los Angeles",
            state="CA",
            country="US",
            raw={},
        )
        assert result.country == "US"


class TestGeocoderInit:
    """Tests for Geocoder instantiation."""

    def test_geocoder_default_provider(self):
        gc = Geocoder()
        assert gc.provider == "nominatim"

    def test_geocoder_custom_user_agent(self):
        gc = Geocoder(user_agent="test-agent/1.0")
        assert gc.user_agent == "test-agent/1.0"

    def test_geocoder_timeout_default(self):
        gc = Geocoder()
        assert gc.timeout == 10


class TestGeocoderGeocode:
    """Tests for Geocoder.geocode() method."""

    def test_geocode_returns_geocoder_result_on_success(self):
        gc = Geocoder()
        mock_response = {
            "lat": "29.7604",
            "lon": "-95.3698",
            "display_name": "123 Main St, Houston, Harris County, TX, 77001, USA",
            "address": {
                "county": "Harris County",
                "state": "Texas",
                "country_code": "us",
            },
        }

        with patch.object(gc, "_call_nominatim", return_value=mock_response):
            result = gc.geocode("123 Main St, Houston, TX 77001")

        assert isinstance(result, GeocoderResult)
        assert result.lat == pytest.approx(29.7604)
        assert result.lon == pytest.approx(-95.3698)
        assert result.state == "TX"

    def test_geocode_raises_geocode_error_on_no_results(self):
        gc = Geocoder()
        with patch.object(gc, "_call_nominatim", return_value=None):
            with pytest.raises(GeocodeError, match="No results"):
                gc.geocode("99999 Nonexistent Blvd, Nowhere, XX 00000")

    def test_geocode_raises_on_empty_address(self):
        gc = Geocoder()
        with pytest.raises(ValueError, match="address"):
            gc.geocode("")

    def test_geocode_strips_county_suffix(self):
        gc = Geocoder()
        mock_response = {
            "lat": "29.7604",
            "lon": "-95.3698",
            "display_name": "...",
            "address": {
                "county": "Harris County",
                "state": "Texas",
                "country_code": "us",
            },
        }
        with patch.object(gc, "_call_nominatim", return_value=mock_response):
            result = gc.geocode("123 Main St, Houston, TX 77001")

        assert result.county == "Harris"

    def test_geocode_normalizes_state_abbreviation(self):
        gc = Geocoder()
        mock_response = {
            "lat": "41.8827",
            "lon": "-87.6233",
            "display_name": "...",
            "address": {
                "county": "Cook County",
                "state": "Illinois",
                "country_code": "us",
            },
        }
        with patch.object(gc, "_call_nominatim", return_value=mock_response):
            result = gc.geocode("100 N State St, Chicago, IL 60601")

        assert result.state == "IL"

    def test_geocode_raises_geocode_error_on_network_failure(self):
        gc = Geocoder()
        with patch.object(gc, "_call_nominatim", side_effect=Exception("timeout")):
            with pytest.raises(GeocodeError):
                gc.geocode("123 Main St, Houston, TX 77001")


class TestGeocoderSupportedCounties:
    """Tests for supported county resolution."""

    def test_harris_county_is_supported(self):
        gc = Geocoder()
        assert gc.is_supported_county("Harris", "TX") is True

    def test_los_angeles_county_is_supported(self):
        gc = Geocoder()
        assert gc.is_supported_county("Los Angeles", "CA") is True

    def test_cook_county_is_supported(self):
        gc = Geocoder()
        assert gc.is_supported_county("Cook", "IL") is True

    def test_unknown_county_is_not_supported(self):
        gc = Geocoder()
        assert gc.is_supported_county("Podunk", "ZZ") is False
