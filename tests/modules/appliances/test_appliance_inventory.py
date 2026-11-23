"""
test_appliance_inventory.py — Unit tests for the ApplianceInventory storage layer.

TDD Red phase: tests written before implementation.
"""

import json
import pytest
import tempfile
from datetime import date
from pathlib import Path

from assethold.modules.appliances.appliance_model import (
    Appliance,
    ApplianceCategory,
    ApplianceCondition,
    MaintenanceRecord,
    RepairRecord,
)
from assethold.modules.appliances.appliance_inventory import ApplianceInventory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_appliance(appliance_id: str = "APP-001", category=ApplianceCategory.HVAC):
    return Appliance(
        appliance_id=appliance_id,
        manufacturer="Carrier",
        model="24ACC636A003",
        category=category,
        install_date=date(2018, 6, 1),
        purchase_cost=3200.00,
        expected_lifespan_years=15,
    )


# ---------------------------------------------------------------------------
# In-memory CRUD
# ---------------------------------------------------------------------------

class TestApplianceInventoryCRUD:

    def test_add_and_get_appliance(self):
        inv = ApplianceInventory()
        appl = _make_appliance("APP-001")
        inv.add(appl)
        result = inv.get("APP-001")
        assert result is appl

    def test_get_missing_returns_none(self):
        inv = ApplianceInventory()
        assert inv.get("NONEXISTENT") is None

    def test_add_duplicate_raises_error(self):
        inv = ApplianceInventory()
        appl = _make_appliance("APP-001")
        inv.add(appl)
        with pytest.raises(ValueError, match="APP-001"):
            inv.add(appl)

    def test_remove_existing_appliance(self):
        inv = ApplianceInventory()
        appl = _make_appliance("APP-001")
        inv.add(appl)
        inv.remove("APP-001")
        assert inv.get("APP-001") is None

    def test_remove_missing_raises_error(self):
        inv = ApplianceInventory()
        with pytest.raises(KeyError):
            inv.remove("NONEXISTENT")

    def test_count_returns_number_of_appliances(self):
        inv = ApplianceInventory()
        assert inv.count() == 0
        inv.add(_make_appliance("APP-001"))
        inv.add(_make_appliance("APP-002", ApplianceCategory.REFRIGERATOR))
        assert inv.count() == 2

    def test_list_all_returns_all_appliances(self):
        inv = ApplianceInventory()
        appl1 = _make_appliance("APP-001")
        appl2 = _make_appliance("APP-002", ApplianceCategory.WASHER)
        inv.add(appl1)
        inv.add(appl2)
        all_appliances = inv.list_all()
        assert len(all_appliances) == 2

    def test_filter_by_category_returns_matching_only(self):
        inv = ApplianceInventory()
        inv.add(_make_appliance("APP-001", ApplianceCategory.HVAC))
        inv.add(_make_appliance("APP-002", ApplianceCategory.HVAC))
        inv.add(_make_appliance("APP-003", ApplianceCategory.REFRIGERATOR))
        hvac = inv.filter_by_category(ApplianceCategory.HVAC)
        assert len(hvac) == 2
        assert all(a.category == ApplianceCategory.HVAC for a in hvac)

    def test_filter_by_category_empty_when_none_match(self):
        inv = ApplianceInventory()
        inv.add(_make_appliance("APP-001", ApplianceCategory.HVAC))
        result = inv.filter_by_category(ApplianceCategory.DRYER)
        assert result == []


# ---------------------------------------------------------------------------
# Serialization round-trip (JSON)
# ---------------------------------------------------------------------------

class TestApplianceInventorySerialization:

    def test_to_dict_round_trip_preserves_appliance_fields(self):
        inv = ApplianceInventory()
        appl = _make_appliance("APP-SERIAL-01")
        appl.add_maintenance_record(
            MaintenanceRecord(
                service_date=date(2022, 3, 1),
                description="Filter change",
                cost=80.0,
            )
        )
        inv.add(appl)
        data = inv.to_dict()
        assert "appliances" in data
        assert len(data["appliances"]) == 1
        entry = data["appliances"][0]
        assert entry["appliance_id"] == "APP-SERIAL-01"
        assert entry["manufacturer"] == "Carrier"
        assert len(entry["maintenance_records"]) == 1

    def test_from_dict_round_trip_restores_appliance(self):
        inv = ApplianceInventory()
        appl = _make_appliance("APP-SERIAL-02")
        inv.add(appl)
        data = inv.to_dict()
        inv2 = ApplianceInventory.from_dict(data)
        restored = inv2.get("APP-SERIAL-02")
        assert restored is not None
        assert restored.manufacturer == "Carrier"
        assert restored.purchase_cost == pytest.approx(3200.0)
        assert restored.category == ApplianceCategory.HVAC

    def test_save_and_load_json_round_trip(self, tmp_path):
        inv = ApplianceInventory()
        appl = _make_appliance("APP-IO-01")
        inv.add(appl)
        json_path = tmp_path / "inventory.json"
        inv.save_json(str(json_path))
        assert json_path.exists()
        inv2 = ApplianceInventory.load_json(str(json_path))
        restored = inv2.get("APP-IO-01")
        assert restored is not None
        assert restored.model == "24ACC636A003"

    def test_save_json_creates_valid_json(self, tmp_path):
        inv = ApplianceInventory()
        inv.add(_make_appliance("APP-IO-02"))
        json_path = tmp_path / "out.json"
        inv.save_json(str(json_path))
        with open(json_path) as f:
            data = json.load(f)
        assert "appliances" in data
