"""
test_vendor_lookup.py — Unit tests for geographic vendor density lookup.

TDD Red phase: tests written before implementation.
All external HTTP calls are mocked at the boundary.
"""

import pytest
from unittest.mock import patch, MagicMock

from assethold.modules.appliances.vendor_lookup import (
    VendorRecord,
    VendorLookup,
)


# ---------------------------------------------------------------------------
# VendorRecord
# ---------------------------------------------------------------------------

class TestVendorRecord:

    def test_vendor_record_creation(self):
        vendor = VendorRecord(
            name="City Appliance Repair",
            address="123 Main St, Houston, TX 77001",
            lat=29.7604,
            lon=-95.3698,
            categories=["refrigerator", "washer", "dryer"],
            phone="713-555-0100",
            rating=4.5,
        )
        assert vendor.name == "City Appliance Repair"
        assert vendor.lat == 29.7604
        assert "refrigerator" in vendor.categories
        assert vendor.rating == 4.5

    def test_vendor_record_optional_fields_default_to_none(self):
        vendor = VendorRecord(
            name="Quick Fix",
            address="456 Oak Ave",
            lat=29.76,
            lon=-95.37,
            categories=["hvac"],
        )
        assert vendor.phone is None
        assert vendor.rating is None


# ---------------------------------------------------------------------------
# VendorLookup — distance filtering
# ---------------------------------------------------------------------------

class TestVendorLookupDistanceFiltering:

    def _build_lookup(self):
        return VendorLookup()

    def test_haversine_distance_same_point_is_zero(self):
        lookup = self._build_lookup()
        dist = lookup.haversine_distance_km(29.76, -95.37, 29.76, -95.37)
        assert dist == pytest.approx(0.0, abs=1e-6)

    def test_haversine_distance_known_pair(self):
        # Houston (29.7604 N, 95.3698 W) to Dallas (32.7767 N, 96.7970 W)
        # Approximate straight-line ~362 km
        lookup = self._build_lookup()
        dist = lookup.haversine_distance_km(29.7604, -95.3698, 32.7767, -96.7970)
        assert 340.0 <= dist <= 390.0

    def test_filter_vendors_by_radius_returns_only_nearby(self):
        lookup = self._build_lookup()
        vendors = [
            VendorRecord(
                name="Near Vendor",
                address="1 Close St",
                lat=29.77,
                lon=-95.38,
                categories=["hvac"],
            ),
            VendorRecord(
                name="Far Vendor",
                address="1 Far Ave",
                lat=32.77,
                lon=-96.80,
                categories=["hvac"],
            ),
        ]
        nearby = lookup.filter_vendors_by_radius(
            vendors=vendors,
            center_lat=29.7604,
            center_lon=-95.3698,
            radius_km=50.0,
        )
        names = [v.name for v in nearby]
        assert "Near Vendor" in names
        assert "Far Vendor" not in names

    def test_filter_vendors_by_radius_empty_list_returns_empty(self):
        lookup = self._build_lookup()
        result = lookup.filter_vendors_by_radius([], 0.0, 0.0, 100.0)
        assert result == []

    def test_count_vendors_in_area_matches_filter_length(self):
        lookup = self._build_lookup()
        vendors = [
            VendorRecord(
                name=f"Vendor {i}",
                address=f"{i} St",
                lat=29.76 + i * 0.001,
                lon=-95.37,
                categories=["hvac"],
            )
            for i in range(5)
        ]
        count = lookup.count_vendors_in_area(
            vendors=vendors,
            center_lat=29.76,
            center_lon=-95.37,
            radius_km=100.0,
        )
        assert count == 5


# ---------------------------------------------------------------------------
# VendorLookup — mock-based search tests
# ---------------------------------------------------------------------------

class TestVendorLookupSearch:

    def test_search_vendors_returns_list_of_vendor_records(self):
        """search_vendors wraps an external API; verify it returns VendorRecords."""
        lookup = VendorLookup()
        mock_raw = [
            {
                "name": "Houston HVAC Pro",
                "address": "100 Energy Corridor, Houston, TX",
                "lat": 29.76,
                "lon": -95.37,
                "categories": ["hvac"],
                "phone": "713-555-1234",
                "rating": 4.3,
            }
        ]
        with patch.object(lookup, "_fetch_vendor_data", return_value=mock_raw):
            results = lookup.search_vendors(
                location="Houston, TX",
                category="hvac",
                radius_km=40.0,
            )
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], VendorRecord)
        assert results[0].name == "Houston HVAC Pro"

    def test_search_vendors_empty_fetch_returns_empty_list(self):
        lookup = VendorLookup()
        with patch.object(lookup, "_fetch_vendor_data", return_value=[]):
            results = lookup.search_vendors(
                location="Nowhere, TX",
                category="refrigerator",
                radius_km=50.0,
            )
        assert results == []

    def test_geocode_location_returns_lat_lon_tuple(self):
        lookup = VendorLookup()
        with patch.object(
            lookup, "_geocode_address", return_value=(29.7604, -95.3698)
        ):
            lat, lon = lookup.geocode_location("Houston, TX")
        assert lat == pytest.approx(29.7604)
        assert lon == pytest.approx(-95.3698)

    def test_vendor_count_by_location_returns_int(self):
        lookup = VendorLookup()
        mock_vendors = [
            VendorRecord(
                name=f"Vendor {i}",
                address=f"{i} St",
                lat=29.76,
                lon=-95.37,
                categories=["hvac"],
            )
            for i in range(3)
        ]
        with patch.object(lookup, "search_vendors", return_value=mock_vendors):
            count = lookup.vendor_count_by_location(
                location="Houston, TX",
                category="hvac",
                radius_km=40.0,
            )
        assert count == 3

    def test_vendor_count_by_location_returns_zero_on_empty(self):
        lookup = VendorLookup()
        with patch.object(lookup, "search_vendors", return_value=[]):
            count = lookup.vendor_count_by_location(
                location="Remote Place, TX",
                category="hvac",
                radius_km=40.0,
            )
        assert count == 0
