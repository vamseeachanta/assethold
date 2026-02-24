"""
test_appliance_model.py — Unit tests for the Appliance dataclass and enumerations.

TDD Red phase: all tests written before implementation.
"""

import pytest
from datetime import date, timedelta

from assethold.modules.appliances.appliance_model import (
    Appliance,
    ApplianceCategory,
    ApplianceCondition,
    MaintenanceRecord,
    RepairRecord,
)


# ---------------------------------------------------------------------------
# ApplianceCategory
# ---------------------------------------------------------------------------

class TestApplianceCategory:

    def test_category_values_exist(self):
        assert ApplianceCategory.HVAC.value == "hvac"
        assert ApplianceCategory.REFRIGERATOR.value == "refrigerator"
        assert ApplianceCategory.WASHER.value == "washer"
        assert ApplianceCategory.DRYER.value == "dryer"
        assert ApplianceCategory.DISHWASHER.value == "dishwasher"
        assert ApplianceCategory.WATER_HEATER.value == "water_heater"
        assert ApplianceCategory.OVEN.value == "oven"
        assert ApplianceCategory.MICROWAVE.value == "microwave"
        assert ApplianceCategory.OTHER.value == "other"


# ---------------------------------------------------------------------------
# ApplianceCondition
# ---------------------------------------------------------------------------

class TestApplianceCondition:

    def test_condition_values_exist(self):
        assert ApplianceCondition.EXCELLENT.value == "excellent"
        assert ApplianceCondition.GOOD.value == "good"
        assert ApplianceCondition.FAIR.value == "fair"
        assert ApplianceCondition.POOR.value == "poor"
        assert ApplianceCondition.FAILED.value == "failed"


# ---------------------------------------------------------------------------
# MaintenanceRecord
# ---------------------------------------------------------------------------

class TestMaintenanceRecord:

    def test_maintenance_record_creation_minimal(self):
        rec = MaintenanceRecord(
            service_date=date(2024, 3, 15),
            description="Annual filter replacement",
            cost=75.00,
        )
        assert rec.service_date == date(2024, 3, 15)
        assert rec.description == "Annual filter replacement"
        assert rec.cost == 75.00
        assert rec.technician is None
        assert rec.notes is None

    def test_maintenance_record_creation_full(self):
        rec = MaintenanceRecord(
            service_date=date(2024, 3, 15),
            description="Full inspection",
            cost=150.00,
            technician="ABC HVAC Services",
            notes="Filter replaced, refrigerant topped off",
        )
        assert rec.technician == "ABC HVAC Services"
        assert rec.notes == "Filter replaced, refrigerant topped off"

    def test_maintenance_record_rejects_negative_cost(self):
        with pytest.raises(ValueError, match="cost"):
            MaintenanceRecord(
                service_date=date(2024, 1, 1),
                description="Service",
                cost=-10.0,
            )


# ---------------------------------------------------------------------------
# RepairRecord
# ---------------------------------------------------------------------------

class TestRepairRecord:

    def test_repair_record_creation_minimal(self):
        rec = RepairRecord(
            repair_date=date(2023, 8, 20),
            description="Compressor replacement",
            cost=850.00,
            failure_cause="Compressor burnout",
        )
        assert rec.repair_date == date(2023, 8, 20)
        assert rec.cost == 850.00
        assert rec.failure_cause == "Compressor burnout"
        assert rec.technician is None
        assert rec.warranty_covered is False

    def test_repair_record_warranty_covered(self):
        rec = RepairRecord(
            repair_date=date(2023, 8, 20),
            description="Compressor replacement",
            cost=0.0,
            failure_cause="Manufacturing defect",
            warranty_covered=True,
        )
        assert rec.warranty_covered is True

    def test_repair_record_rejects_negative_cost(self):
        with pytest.raises(ValueError, match="cost"):
            RepairRecord(
                repair_date=date(2023, 1, 1),
                description="Repair",
                cost=-5.0,
                failure_cause="Unknown",
            )


# ---------------------------------------------------------------------------
# Appliance — construction and validation
# ---------------------------------------------------------------------------

class TestApplianceConstruction:

    def _make_appliance(self, **overrides):
        defaults = dict(
            appliance_id="APP-001",
            manufacturer="Carrier",
            model="24ACC636A003",
            category=ApplianceCategory.HVAC,
            install_date=date(2018, 6, 1),
            purchase_cost=3200.00,
            expected_lifespan_years=15,
        )
        defaults.update(overrides)
        return Appliance(**defaults)

    def test_appliance_creation_minimal(self):
        appl = self._make_appliance()
        assert appl.appliance_id == "APP-001"
        assert appl.manufacturer == "Carrier"
        assert appl.model == "24ACC636A003"
        assert appl.category == ApplianceCategory.HVAC
        assert appl.install_date == date(2018, 6, 1)
        assert appl.purchase_cost == 3200.00
        assert appl.expected_lifespan_years == 15
        assert appl.condition == ApplianceCondition.GOOD
        assert appl.reliability_rating is None
        assert appl.warranty_expiry is None
        assert appl.serial_number is None
        assert appl.maintenance_records == []
        assert appl.repair_records == []
        assert appl.notes is None

    def test_appliance_rejects_blank_manufacturer(self):
        with pytest.raises(ValueError, match="manufacturer"):
            self._make_appliance(manufacturer="")

    def test_appliance_rejects_blank_model(self):
        with pytest.raises(ValueError, match="model"):
            self._make_appliance(model="  ")

    def test_appliance_rejects_negative_purchase_cost(self):
        with pytest.raises(ValueError, match="purchase_cost"):
            self._make_appliance(purchase_cost=-100.0)

    def test_appliance_rejects_zero_lifespan(self):
        with pytest.raises(ValueError, match="expected_lifespan_years"):
            self._make_appliance(expected_lifespan_years=0)

    def test_appliance_rejects_invalid_reliability_rating(self):
        with pytest.raises(ValueError, match="reliability_rating"):
            self._make_appliance(reliability_rating=6.0)

    def test_appliance_rejects_negative_reliability_rating(self):
        with pytest.raises(ValueError, match="reliability_rating"):
            self._make_appliance(reliability_rating=-0.1)

    def test_appliance_accepts_zero_reliability_rating(self):
        appl = self._make_appliance(reliability_rating=0.0)
        assert appl.reliability_rating == 0.0

    def test_appliance_accepts_max_reliability_rating(self):
        appl = self._make_appliance(reliability_rating=5.0)
        assert appl.reliability_rating == 5.0

    def test_appliance_repr_contains_key_fields(self):
        appl = self._make_appliance()
        r = repr(appl)
        assert "APP-001" in r
        assert "Carrier" in r


# ---------------------------------------------------------------------------
# Appliance — age and lifecycle helpers
# ---------------------------------------------------------------------------

class TestApplianceLifecycle:

    def _make_appliance(self, install_date=None):
        return Appliance(
            appliance_id="APP-002",
            manufacturer="Whirlpool",
            model="WRF535SWHZ",
            category=ApplianceCategory.REFRIGERATOR,
            install_date=install_date or date(2015, 1, 1),
            purchase_cost=1200.00,
            expected_lifespan_years=12,
        )

    def test_age_years_returns_non_negative_float(self):
        appl = self._make_appliance(install_date=date(2020, 1, 1))
        assert appl.age_years() >= 0.0

    def test_age_years_brand_new_is_zero(self):
        today = date.today()
        appl = self._make_appliance(install_date=today)
        assert appl.age_years() == pytest.approx(0.0, abs=0.1)

    def test_remaining_life_years_decreases_with_age(self):
        old = self._make_appliance(install_date=date(2010, 1, 1))
        new = self._make_appliance(install_date=date(2023, 1, 1))
        assert old.remaining_life_years() < new.remaining_life_years()

    def test_remaining_life_years_not_negative(self):
        very_old = self._make_appliance(install_date=date(1990, 1, 1))
        assert very_old.remaining_life_years() >= 0.0

    def test_pct_life_used_returns_0_to_100(self):
        appl = self._make_appliance()
        pct = appl.pct_life_used()
        assert 0.0 <= pct <= 100.0

    def test_pct_life_used_brand_new_near_zero(self):
        today = date.today()
        appl = self._make_appliance(install_date=today)
        assert appl.pct_life_used() == pytest.approx(0.0, abs=1.0)

    def test_pct_life_used_past_lifespan_is_100(self):
        very_old = self._make_appliance(install_date=date(1990, 1, 1))
        assert very_old.pct_life_used() == 100.0

    def test_is_under_warranty_true_when_before_expiry(self):
        appl = self._make_appliance()
        appl.warranty_expiry = date.today() + timedelta(days=30)
        assert appl.is_under_warranty() is True

    def test_is_under_warranty_false_when_after_expiry(self):
        appl = self._make_appliance()
        appl.warranty_expiry = date.today() - timedelta(days=1)
        assert appl.is_under_warranty() is False

    def test_is_under_warranty_false_when_no_warranty(self):
        appl = self._make_appliance()
        assert appl.is_under_warranty() is False


# ---------------------------------------------------------------------------
# Appliance — maintenance and repair history
# ---------------------------------------------------------------------------

class TestApplianceHistory:

    def _make_appliance(self):
        return Appliance(
            appliance_id="APP-003",
            manufacturer="GE",
            model="GTD65EBSJWS",
            category=ApplianceCategory.DRYER,
            install_date=date(2019, 5, 10),
            purchase_cost=700.00,
            expected_lifespan_years=13,
        )

    def test_add_maintenance_record_stores_correctly(self):
        appl = self._make_appliance()
        rec = MaintenanceRecord(
            service_date=date(2022, 6, 1),
            description="Lint trap deep clean",
            cost=60.00,
        )
        appl.add_maintenance_record(rec)
        assert len(appl.maintenance_records) == 1
        assert appl.maintenance_records[0] is rec

    def test_add_multiple_maintenance_records(self):
        appl = self._make_appliance()
        for i in range(3):
            appl.add_maintenance_record(
                MaintenanceRecord(
                    service_date=date(2022, i + 1, 1),
                    description=f"Service {i}",
                    cost=50.0,
                )
            )
        assert len(appl.maintenance_records) == 3

    def test_add_repair_record_stores_correctly(self):
        appl = self._make_appliance()
        rec = RepairRecord(
            repair_date=date(2021, 9, 15),
            description="Drum bearing replaced",
            cost=320.00,
            failure_cause="Worn bearing",
        )
        appl.add_repair_record(rec)
        assert len(appl.repair_records) == 1

    def test_total_maintenance_cost_sums_correctly(self):
        appl = self._make_appliance()
        appl.add_maintenance_record(
            MaintenanceRecord(service_date=date(2021, 1, 1), description="A", cost=50.0)
        )
        appl.add_maintenance_record(
            MaintenanceRecord(service_date=date(2022, 1, 1), description="B", cost=80.0)
        )
        assert appl.total_maintenance_cost() == pytest.approx(130.0)

    def test_total_repair_cost_sums_correctly(self):
        appl = self._make_appliance()
        appl.add_repair_record(
            RepairRecord(
                repair_date=date(2021, 1, 1),
                description="A",
                cost=200.0,
                failure_cause="X",
            )
        )
        appl.add_repair_record(
            RepairRecord(
                repair_date=date(2022, 1, 1),
                description="B",
                cost=150.0,
                failure_cause="Y",
            )
        )
        assert appl.total_repair_cost() == pytest.approx(350.0)

    def test_total_maintenance_cost_empty_is_zero(self):
        appl = self._make_appliance()
        assert appl.total_maintenance_cost() == 0.0

    def test_total_repair_cost_empty_is_zero(self):
        appl = self._make_appliance()
        assert appl.total_repair_cost() == 0.0
