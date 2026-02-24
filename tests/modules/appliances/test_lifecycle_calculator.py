"""
test_lifecycle_calculator.py — Unit tests for the lifecycle cost calculator.

TDD Red phase: tests written before implementation.
"""

import pytest
from datetime import date

from assethold.modules.appliances.appliance_model import (
    Appliance,
    ApplianceCategory,
    MaintenanceRecord,
    RepairRecord,
)
from assethold.modules.appliances.lifecycle_calculator import LifecycleCostCalculator


class TestLifecycleCostCalculatorBasic:

    def _make_hvac(self):
        appl = Appliance(
            appliance_id="APP-HVAC-01",
            manufacturer="Trane",
            model="XR15",
            category=ApplianceCategory.HVAC,
            install_date=date(2018, 6, 1),
            purchase_cost=4500.00,
            expected_lifespan_years=15,
        )
        return appl

    def test_total_cost_of_ownership_equals_purchase_plus_running_costs(self):
        appl = self._make_hvac()
        appl.add_maintenance_record(
            MaintenanceRecord(service_date=date(2020, 1, 1), description="A", cost=100.0)
        )
        appl.add_repair_record(
            RepairRecord(
                repair_date=date(2021, 1, 1),
                description="B",
                cost=500.0,
                failure_cause="Leak",
            )
        )
        calc = LifecycleCostCalculator(appl)
        tco = calc.total_cost_of_ownership()
        expected = 4500.0 + 100.0 + 500.0
        assert tco == pytest.approx(expected)

    def test_tco_no_history_equals_purchase_cost(self):
        appl = self._make_hvac()
        calc = LifecycleCostCalculator(appl)
        assert calc.total_cost_of_ownership() == pytest.approx(4500.0)

    def test_average_annual_cost_divides_tco_by_age(self):
        appl = Appliance(
            appliance_id="APP-HVAC-02",
            manufacturer="Trane",
            model="XR15",
            category=ApplianceCategory.HVAC,
            install_date=date(2019, 1, 1),
            purchase_cost=4000.00,
            expected_lifespan_years=15,
        )
        calc = LifecycleCostCalculator(appl)
        age = appl.age_years()
        expected = 4000.0 / age if age > 0 else 0.0
        assert calc.average_annual_cost() == pytest.approx(expected, rel=0.01)

    def test_average_annual_cost_brand_new_returns_zero(self):
        appl = Appliance(
            appliance_id="APP-NEW",
            manufacturer="LG",
            model="LFXS26973S",
            category=ApplianceCategory.REFRIGERATOR,
            install_date=date.today(),
            purchase_cost=1500.0,
            expected_lifespan_years=12,
        )
        calc = LifecycleCostCalculator(appl)
        assert calc.average_annual_cost() == pytest.approx(0.0, abs=0.01)

    def test_projected_replacement_cost_uses_inflation(self):
        appl = self._make_hvac()
        calc = LifecycleCostCalculator(appl)
        # With positive inflation, projected cost > purchase cost
        projected = calc.projected_replacement_cost(annual_inflation_rate=0.03)
        assert projected > appl.purchase_cost

    def test_projected_replacement_cost_zero_inflation_equals_purchase(self):
        appl = self._make_hvac()
        calc = LifecycleCostCalculator(appl)
        projected = calc.projected_replacement_cost(annual_inflation_rate=0.0)
        remaining = appl.remaining_life_years()
        # cost * (1+0)^remaining == purchase_cost
        assert projected == pytest.approx(appl.purchase_cost)

    def test_cost_per_year_remaining_uses_tco_and_remaining_life(self):
        appl = self._make_hvac()
        calc = LifecycleCostCalculator(appl)
        remaining = appl.remaining_life_years()
        if remaining > 0:
            expected = calc.total_cost_of_ownership() / remaining
            assert calc.cost_per_year_remaining() == pytest.approx(expected, rel=0.01)

    def test_cost_per_year_remaining_zero_when_no_life_left(self):
        appl = Appliance(
            appliance_id="APP-OLD",
            manufacturer="Carrier",
            model="Old",
            category=ApplianceCategory.HVAC,
            install_date=date(1990, 1, 1),
            purchase_cost=2000.0,
            expected_lifespan_years=15,
        )
        calc = LifecycleCostCalculator(appl)
        assert calc.cost_per_year_remaining() == pytest.approx(0.0)


class TestLifecycleSummary:

    def test_lifecycle_summary_returns_dict_with_required_keys(self):
        appl = Appliance(
            appliance_id="APP-SUM-01",
            manufacturer="Samsung",
            model="RF23M8570SR",
            category=ApplianceCategory.REFRIGERATOR,
            install_date=date(2020, 4, 15),
            purchase_cost=1800.00,
            expected_lifespan_years=12,
        )
        calc = LifecycleCostCalculator(appl)
        summary = calc.lifecycle_summary()
        required_keys = {
            "appliance_id",
            "manufacturer",
            "model",
            "category",
            "age_years",
            "remaining_life_years",
            "pct_life_used",
            "purchase_cost",
            "total_maintenance_cost",
            "total_repair_cost",
            "total_cost_of_ownership",
            "average_annual_cost",
            "condition",
        }
        assert required_keys.issubset(summary.keys())

    def test_lifecycle_summary_values_are_consistent(self):
        appl = Appliance(
            appliance_id="APP-SUM-02",
            manufacturer="Bosch",
            model="SHPM88Z75N",
            category=ApplianceCategory.DISHWASHER,
            install_date=date(2021, 1, 1),
            purchase_cost=900.00,
            expected_lifespan_years=10,
        )
        calc = LifecycleCostCalculator(appl)
        summary = calc.lifecycle_summary()
        assert summary["purchase_cost"] == pytest.approx(900.0)
        assert summary["total_maintenance_cost"] == pytest.approx(0.0)
        assert summary["total_cost_of_ownership"] == pytest.approx(900.0)
        assert 0.0 <= summary["pct_life_used"] <= 100.0
