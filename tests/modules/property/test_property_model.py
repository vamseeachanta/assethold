"""
Tests for property_model.py — Property dataclass and validation.
TDD: red → green → refactor
"""
import pytest
from dataclasses import FrozenInstanceError

from assethold.property.property_model import Property, PropertyType, ZoningClass


class TestPropertyCreation:
    """Tests for Property dataclass instantiation."""

    def test_property_created_with_required_fields(self):
        prop = Property(
            address="123 Main St, Houston, TX 77001",
            lat=29.7604,
            lon=-95.3698,
        )
        assert prop.address == "123 Main St, Houston, TX 77001"
        assert prop.lat == pytest.approx(29.7604)
        assert prop.lon == pytest.approx(-95.3698)

    def test_property_defaults_are_none_or_expected(self):
        prop = Property(
            address="456 Oak Ave, Chicago, IL 60601",
            lat=41.8827,
            lon=-87.6233,
        )
        assert prop.parcel_id is None
        assert prop.zoning is None
        assert prop.lot_size_sqft is None
        assert prop.building_sqft is None
        assert prop.property_type == PropertyType.RESIDENTIAL
        assert prop.year_built is None
        assert prop.assessed_value is None
        assert prop.county is None
        assert prop.state is None

    def test_property_full_fields(self):
        prop = Property(
            address="789 Elm St, Los Angeles, CA 90001",
            lat=34.0522,
            lon=-118.2437,
            parcel_id="2345-678-901",
            zoning=ZoningClass.RESIDENTIAL_SINGLE,
            lot_size_sqft=6000,
            building_sqft=1800,
            property_type=PropertyType.RESIDENTIAL,
            year_built=1990,
            assessed_value=450000.0,
            county="Los Angeles",
            state="CA",
        )
        assert prop.parcel_id == "2345-678-901"
        assert prop.zoning == ZoningClass.RESIDENTIAL_SINGLE
        assert prop.lot_size_sqft == 6000
        assert prop.building_sqft == 1800
        assert prop.year_built == 1990
        assert prop.assessed_value == pytest.approx(450000.0)
        assert prop.county == "Los Angeles"
        assert prop.state == "CA"

    def test_property_repr_contains_address(self):
        prop = Property(
            address="1 Test Rd, Dallas, TX 75201",
            lat=32.7767,
            lon=-96.7970,
        )
        assert "1 Test Rd" in repr(prop)


class TestPropertyValidation:
    """Tests for coordinate and field validation on Property."""

    def test_invalid_lat_too_high_raises(self):
        with pytest.raises(ValueError, match="lat"):
            Property(address="Bad Lat", lat=95.0, lon=0.0)

    def test_invalid_lat_too_low_raises(self):
        with pytest.raises(ValueError, match="lat"):
            Property(address="Bad Lat", lat=-95.0, lon=0.0)

    def test_invalid_lon_too_high_raises(self):
        with pytest.raises(ValueError, match="lon"):
            Property(address="Bad Lon", lat=0.0, lon=185.0)

    def test_invalid_lon_too_low_raises(self):
        with pytest.raises(ValueError, match="lon"):
            Property(address="Bad Lon", lat=0.0, lon=-185.0)

    def test_empty_address_raises(self):
        with pytest.raises(ValueError, match="address"):
            Property(address="", lat=29.76, lon=-95.37)

    def test_negative_building_sqft_raises(self):
        with pytest.raises(ValueError, match="building_sqft"):
            Property(
                address="100 Test St",
                lat=29.76,
                lon=-95.37,
                building_sqft=-500,
            )

    def test_negative_assessed_value_raises(self):
        with pytest.raises(ValueError, match="assessed_value"):
            Property(
                address="100 Test St",
                lat=29.76,
                lon=-95.37,
                assessed_value=-1.0,
            )


class TestPropertyTypeEnum:
    def test_residential_enum_value(self):
        assert PropertyType.RESIDENTIAL.value == "residential"

    def test_commercial_enum_value(self):
        assert PropertyType.COMMERCIAL.value == "commercial"

    def test_industrial_enum_value(self):
        assert PropertyType.INDUSTRIAL.value == "industrial"

    def test_land_enum_value(self):
        assert PropertyType.LAND.value == "land"


class TestZoningClassEnum:
    def test_residential_single_enum_value(self):
        assert ZoningClass.RESIDENTIAL_SINGLE.value == "R1"

    def test_residential_multi_enum_value(self):
        assert ZoningClass.RESIDENTIAL_MULTI.value == "R2"

    def test_commercial_enum_value(self):
        assert ZoningClass.COMMERCIAL.value == "C"

    def test_industrial_enum_value(self):
        assert ZoningClass.INDUSTRIAL.value == "I"

    def test_mixed_use_enum_value(self):
        assert ZoningClass.MIXED_USE.value == "MU"
