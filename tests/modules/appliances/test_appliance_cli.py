"""
test_appliance_cli.py — Unit tests for the appliance CLI entry point.

TDD Red phase: tests written before implementation.
"""

import json
import pytest
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

from assethold.modules.appliances.appliance_model import (
    Appliance,
    ApplianceCategory,
)
from assethold.modules.appliances.appliance_inventory import ApplianceInventory
from assethold.modules.appliances.appliance_cli import (
    ApplianceCLI,
    build_sample_inventory,
)


# ---------------------------------------------------------------------------
# build_sample_inventory helper
# ---------------------------------------------------------------------------

class TestBuildSampleInventory:

    def test_build_sample_inventory_returns_non_empty_inventory(self):
        inv = build_sample_inventory()
        assert isinstance(inv, ApplianceInventory)
        assert inv.count() > 0

    def test_build_sample_inventory_appliances_have_valid_fields(self):
        inv = build_sample_inventory()
        for appl in inv.list_all():
            assert appl.appliance_id
            assert appl.manufacturer
            assert appl.purchase_cost > 0


# ---------------------------------------------------------------------------
# ApplianceCLI.status_report
# ---------------------------------------------------------------------------

class TestApplianceCLIStatusReport:

    def _build_cli(self):
        inv = ApplianceInventory()
        inv.add(
            Appliance(
                appliance_id="APP-CLI-01",
                manufacturer="LG",
                model="LRE3061ST",
                category=ApplianceCategory.OVEN,
                install_date=date(2019, 1, 1),
                purchase_cost=800.0,
                expected_lifespan_years=15,
            )
        )
        return ApplianceCLI(inventory=inv)

    def test_status_report_returns_dict(self):
        cli = self._build_cli()
        report = cli.status_report()
        assert isinstance(report, dict)

    def test_status_report_contains_appliances_key(self):
        cli = self._build_cli()
        report = cli.status_report()
        assert "appliances" in report

    def test_status_report_each_entry_has_required_fields(self):
        cli = self._build_cli()
        report = cli.status_report()
        for entry in report["appliances"]:
            assert "appliance_id" in entry
            assert "age_years" in entry
            assert "pct_life_used" in entry
            assert "total_cost_of_ownership" in entry


# ---------------------------------------------------------------------------
# ApplianceCLI.vendor_count
# ---------------------------------------------------------------------------

class TestApplianceCLIVendorCount:

    def test_vendor_count_returns_integer(self):
        inv = build_sample_inventory()
        cli = ApplianceCLI(inventory=inv)
        mock_lookup = MagicMock()
        mock_lookup.vendor_count_by_location.return_value = 7
        with patch(
            "assethold.modules.appliances.appliance_cli.VendorLookup",
            return_value=mock_lookup,
        ):
            count = cli.vendor_count(
                location="Houston, TX",
                category="hvac",
                radius_km=40.0,
            )
        assert count == 7

    def test_vendor_count_passes_correct_args_to_lookup(self):
        inv = build_sample_inventory()
        cli = ApplianceCLI(inventory=inv)
        mock_lookup = MagicMock()
        mock_lookup.vendor_count_by_location.return_value = 3
        with patch(
            "assethold.modules.appliances.appliance_cli.VendorLookup",
            return_value=mock_lookup,
        ):
            cli.vendor_count(
                location="Austin, TX",
                category="refrigerator",
                radius_km=25.0,
            )
        mock_lookup.vendor_count_by_location.assert_called_once_with(
            location="Austin, TX",
            category="refrigerator",
            radius_km=25.0,
        )
