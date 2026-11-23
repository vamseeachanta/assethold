# ABOUTME: Unit tests for the appliances module — model, inventory, and lifecycle calculator.
# ABOUTME: Covers dataclass validation, CRUD operations, cost calculations, and JSON round-trips.

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from assethold.modules.appliances.appliance_model import (
    Appliance,
    ApplianceCategory,
    ApplianceCondition,
    MaintenanceRecord,
    RepairRecord,
)
from assethold.modules.appliances.appliance_inventory import ApplianceInventory
from assethold.modules.appliances.lifecycle_calculator import LifecycleCostCalculator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_appliance(**overrides) -> Appliance:
    """Return a valid Appliance with sensible defaults, accepting overrides."""
    defaults = dict(
        appliance_id="A001",
        manufacturer="Whirlpool",
        model="WRS325SDHZ",
        category=ApplianceCategory.REFRIGERATOR,
        install_date=date(2020, 1, 1),
        purchase_cost=1200.0,
        expected_lifespan_years=15,
    )
    defaults.update(overrides)
    return Appliance(**defaults)


# ---------------------------------------------------------------------------
# Appliance model tests
# ---------------------------------------------------------------------------

class TestApplianceModel:
    """Tests for the Appliance dataclass and its validation."""

    def test_create_appliance_with_defaults(self):
        appl = _make_appliance()
        assert appl.appliance_id == "A001"
        assert appl.manufacturer == "Whirlpool"
        assert appl.condition == ApplianceCondition.GOOD
        assert appl.maintenance_records == []
        assert appl.repair_records == []

    def test_negative_purchase_cost_raises(self):
        with pytest.raises(ValueError, match="purchase_cost must be non-negative"):
            _make_appliance(purchase_cost=-100.0)

    def test_zero_expected_lifespan_raises(self):
        with pytest.raises(ValueError, match="expected_lifespan_years must be positive"):
            _make_appliance(expected_lifespan_years=0)

    def test_empty_manufacturer_raises(self):
        with pytest.raises(ValueError, match="manufacturer must be a non-empty string"):
            _make_appliance(manufacturer="  ")

    def test_empty_model_raises(self):
        with pytest.raises(ValueError, match="model must be a non-empty string"):
            _make_appliance(model="")

    def test_reliability_rating_out_of_range_raises(self):
        with pytest.raises(ValueError, match="reliability_rating must be in"):
            _make_appliance(reliability_rating=5.5)

    def test_reliability_rating_in_range_accepted(self):
        appl = _make_appliance(reliability_rating=4.2)
        assert appl.reliability_rating == pytest.approx(4.2)

    def test_age_years_positive_for_past_install(self):
        appl = _make_appliance(install_date=date.today() - timedelta(days=730))
        assert appl.age_years() == pytest.approx(2.0, abs=0.05)

    def test_remaining_life_years_decreases_with_age(self):
        appl = _make_appliance(
            install_date=date.today() - timedelta(days=int(5 * 365.25)),
            expected_lifespan_years=15,
        )
        assert appl.remaining_life_years() == pytest.approx(10.0, abs=0.1)

    def test_remaining_life_years_never_negative(self):
        appl = _make_appliance(
            install_date=date.today() - timedelta(days=int(20 * 365.25)),
            expected_lifespan_years=10,
        )
        assert appl.remaining_life_years() == 0.0

    def test_pct_life_used_clamped_to_100(self):
        appl = _make_appliance(
            install_date=date.today() - timedelta(days=int(20 * 365.25)),
            expected_lifespan_years=10,
        )
        assert appl.pct_life_used() == 100.0

    def test_is_under_warranty_true(self):
        appl = _make_appliance(warranty_expiry=date.today() + timedelta(days=365))
        assert appl.is_under_warranty() is True

    def test_is_under_warranty_false_when_expired(self):
        appl = _make_appliance(warranty_expiry=date.today() - timedelta(days=1))
        assert appl.is_under_warranty() is False

    def test_is_under_warranty_false_when_none(self):
        appl = _make_appliance(warranty_expiry=None)
        assert appl.is_under_warranty() is False


# ---------------------------------------------------------------------------
# Record sub-types
# ---------------------------------------------------------------------------

class TestRecords:
    """Tests for MaintenanceRecord and RepairRecord."""

    def test_maintenance_record_valid(self):
        rec = MaintenanceRecord(
            service_date=date(2023, 6, 15),
            description="Filter change",
            cost=75.0,
        )
        assert rec.cost == 75.0

    def test_maintenance_record_negative_cost_raises(self):
        with pytest.raises(ValueError, match="cost must be non-negative"):
            MaintenanceRecord(
                service_date=date(2023, 6, 15),
                description="Filter change",
                cost=-10.0,
            )

    def test_repair_record_valid(self):
        rec = RepairRecord(
            repair_date=date(2024, 1, 10),
            description="Compressor replacement",
            cost=450.0,
            failure_cause="wear",
        )
        assert rec.warranty_covered is False

    def test_repair_record_negative_cost_raises(self):
        with pytest.raises(ValueError, match="cost must be non-negative"):
            RepairRecord(
                repair_date=date(2024, 1, 10),
                description="Compressor",
                cost=-5.0,
                failure_cause="wear",
            )


# ---------------------------------------------------------------------------
# History management on Appliance
# ---------------------------------------------------------------------------

class TestApplianceHistory:
    """Tests for add_*_record and total cost methods."""

    def test_add_maintenance_and_total_cost(self):
        appl = _make_appliance()
        appl.add_maintenance_record(
            MaintenanceRecord(date(2021, 3, 1), "Filter", 50.0)
        )
        appl.add_maintenance_record(
            MaintenanceRecord(date(2022, 3, 1), "Filter", 60.0)
        )
        assert appl.total_maintenance_cost() == pytest.approx(110.0)

    def test_add_repair_and_total_cost(self):
        appl = _make_appliance()
        appl.add_repair_record(
            RepairRecord(date(2022, 7, 1), "Valve", 200.0, "corrosion")
        )
        assert appl.total_repair_cost() == pytest.approx(200.0)

    def test_total_costs_zero_with_no_records(self):
        appl = _make_appliance()
        assert appl.total_maintenance_cost() == 0.0
        assert appl.total_repair_cost() == 0.0


# ---------------------------------------------------------------------------
# Inventory tests
# ---------------------------------------------------------------------------

class TestApplianceInventory:
    """Tests for the in-memory inventory CRUD and serialization."""

    def test_add_and_get(self):
        inv = ApplianceInventory()
        appl = _make_appliance()
        inv.add(appl)
        assert inv.get("A001") is appl
        assert inv.count() == 1

    def test_add_duplicate_raises(self):
        inv = ApplianceInventory()
        inv.add(_make_appliance())
        with pytest.raises(ValueError, match="already exists"):
            inv.add(_make_appliance())

    def test_remove_existing(self):
        inv = ApplianceInventory()
        inv.add(_make_appliance())
        inv.remove("A001")
        assert inv.count() == 0

    def test_remove_nonexistent_raises(self):
        inv = ApplianceInventory()
        with pytest.raises(KeyError, match="No appliance"):
            inv.remove("NONEXIST")

    def test_get_nonexistent_returns_none(self):
        inv = ApplianceInventory()
        assert inv.get("NOPE") is None

    def test_list_all(self):
        inv = ApplianceInventory()
        inv.add(_make_appliance(appliance_id="A1"))
        inv.add(_make_appliance(appliance_id="A2"))
        assert len(inv.list_all()) == 2

    def test_filter_by_category(self):
        inv = ApplianceInventory()
        inv.add(_make_appliance(appliance_id="R1", category=ApplianceCategory.REFRIGERATOR))
        inv.add(_make_appliance(appliance_id="W1", category=ApplianceCategory.WASHER))
        result = inv.filter_by_category(ApplianceCategory.REFRIGERATOR)
        assert len(result) == 1
        assert result[0].appliance_id == "R1"

    def test_json_round_trip(self, tmp_path):
        inv = ApplianceInventory()
        appl = _make_appliance(
            warranty_expiry=date(2025, 12, 31),
            reliability_rating=4.0,
        )
        appl.add_maintenance_record(
            MaintenanceRecord(date(2021, 6, 1), "Filter change", 50.0, "Tech A")
        )
        appl.add_repair_record(
            RepairRecord(date(2022, 1, 15), "Fan motor", 300.0, "bearing failure")
        )
        inv.add(appl)

        json_path = str(tmp_path / "inv.json")
        inv.save_json(json_path)
        loaded = ApplianceInventory.load_json(json_path)

        assert loaded.count() == 1
        loaded_appl = loaded.get("A001")
        assert loaded_appl.manufacturer == "Whirlpool"
        assert loaded_appl.warranty_expiry == date(2025, 12, 31)
        assert len(loaded_appl.maintenance_records) == 1
        assert len(loaded_appl.repair_records) == 1
        assert loaded_appl.total_maintenance_cost() == pytest.approx(50.0)
        assert loaded_appl.total_repair_cost() == pytest.approx(300.0)

    def test_to_dict_from_dict_round_trip(self):
        inv = ApplianceInventory()
        inv.add(_make_appliance(appliance_id="X1"))
        inv.add(_make_appliance(appliance_id="X2", category=ApplianceCategory.HVAC))
        data = inv.to_dict()
        restored = ApplianceInventory.from_dict(data)
        assert restored.count() == 2
        assert restored.get("X2").category == ApplianceCategory.HVAC


# ---------------------------------------------------------------------------
# Lifecycle calculator tests
# ---------------------------------------------------------------------------

class TestLifecycleCostCalculator:
    """Tests for lifecycle cost calculations."""

    def test_total_cost_of_ownership_no_records(self):
        appl = _make_appliance(purchase_cost=1000.0)
        calc = LifecycleCostCalculator(appl)
        assert calc.total_cost_of_ownership() == pytest.approx(1000.0)

    def test_total_cost_of_ownership_with_records(self):
        appl = _make_appliance(purchase_cost=1000.0)
        appl.add_maintenance_record(MaintenanceRecord(date(2021, 1, 1), "tune-up", 100.0))
        appl.add_repair_record(RepairRecord(date(2022, 1, 1), "fix", 250.0, "wear"))
        calc = LifecycleCostCalculator(appl)
        assert calc.total_cost_of_ownership() == pytest.approx(1350.0)

    def test_average_annual_cost_brand_new(self):
        appl = _make_appliance(install_date=date.today(), purchase_cost=1000.0)
        calc = LifecycleCostCalculator(appl)
        assert calc.average_annual_cost() == pytest.approx(0.0)

    def test_average_annual_cost_after_years(self):
        appl = _make_appliance(
            install_date=date.today() - timedelta(days=int(5 * 365.25)),
            purchase_cost=1500.0,
        )
        calc = LifecycleCostCalculator(appl)
        # TCO = 1500, age ~ 5 years => ~300/year
        assert calc.average_annual_cost() == pytest.approx(300.0, rel=0.05)

    def test_projected_replacement_cost_no_remaining_life(self):
        appl = _make_appliance(
            install_date=date.today() - timedelta(days=int(20 * 365.25)),
            expected_lifespan_years=10,
            purchase_cost=1000.0,
        )
        calc = LifecycleCostCalculator(appl)
        # remaining = 0 => (1 + 0.03)^0 = 1 => same as purchase cost
        assert calc.projected_replacement_cost() == pytest.approx(1000.0)

    def test_projected_replacement_cost_with_inflation(self):
        appl = _make_appliance(
            install_date=date.today(),
            expected_lifespan_years=10,
            purchase_cost=1000.0,
        )
        calc = LifecycleCostCalculator(appl)
        # ~10 years remaining, 3% inflation => 1000 * 1.03^10 ~ 1343.92
        expected = 1000.0 * (1.03 ** 10)
        assert calc.projected_replacement_cost(0.03) == pytest.approx(expected, rel=0.05)

    def test_cost_per_year_remaining_zero_when_expired(self):
        appl = _make_appliance(
            install_date=date.today() - timedelta(days=int(20 * 365.25)),
            expected_lifespan_years=10,
        )
        calc = LifecycleCostCalculator(appl)
        assert calc.cost_per_year_remaining() == pytest.approx(0.0)

    def test_lifecycle_summary_returns_expected_keys(self):
        appl = _make_appliance(
            install_date=date.today() - timedelta(days=int(3 * 365.25)),
        )
        calc = LifecycleCostCalculator(appl)
        summary = calc.lifecycle_summary()
        expected_keys = {
            "appliance_id", "manufacturer", "model", "category", "condition",
            "age_years", "remaining_life_years", "pct_life_used",
            "purchase_cost", "total_maintenance_cost", "total_repair_cost",
            "total_cost_of_ownership", "average_annual_cost",
            "projected_replacement_cost", "cost_per_year_remaining",
        }
        assert set(summary.keys()) == expected_keys
