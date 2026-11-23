"""
lifecycle_calculator.py — Lifecycle cost calculations for an Appliance.

Provides total cost of ownership, average annual cost, projected replacement
cost (with inflation), and per-year-remaining cost breakdowns.
"""

from __future__ import annotations

from typing import Any, Dict

from assethold.modules.appliances.appliance_model import Appliance


class LifecycleCostCalculator:
    """
    Compute lifecycle cost metrics for a single Appliance.

    All monetary values are in the same currency as purchase_cost.
    """

    def __init__(self, appliance: Appliance) -> None:
        self._appliance = appliance

    # ------------------------------------------------------------------
    # Core calculations
    # ------------------------------------------------------------------

    def total_cost_of_ownership(self) -> float:
        """
        Total cost of ownership = purchase cost + all maintenance + all repair costs.
        """
        appl = self._appliance
        return (
            appl.purchase_cost
            + appl.total_maintenance_cost()
            + appl.total_repair_cost()
        )

    def average_annual_cost(self) -> float:
        """
        Average annual cost = TCO / age in years.

        Returns 0.0 for brand-new appliances (age < 1 day).
        """
        age = self._appliance.age_years()
        if age < (1.0 / 365.25):
            return 0.0
        return self.total_cost_of_ownership() / age

    def projected_replacement_cost(self, annual_inflation_rate: float = 0.03) -> float:
        """
        Estimate the replacement cost when the appliance reaches end of life.

        Uses compound inflation over the remaining useful life:
            projected = purchase_cost * (1 + rate) ^ remaining_years
        """
        remaining = self._appliance.remaining_life_years()
        return self._appliance.purchase_cost * ((1.0 + annual_inflation_rate) ** remaining)

    def cost_per_year_remaining(self) -> float:
        """
        Spread the total cost of ownership over remaining useful life.

        Returns 0.0 when no useful life remains.
        """
        remaining = self._appliance.remaining_life_years()
        if remaining <= 0.0:
            return 0.0
        return self.total_cost_of_ownership() / remaining

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def lifecycle_summary(self) -> Dict[str, Any]:
        """
        Return a dict summarising all lifecycle metrics for the appliance.
        """
        appl = self._appliance
        return {
            "appliance_id": appl.appliance_id,
            "manufacturer": appl.manufacturer,
            "model": appl.model,
            "category": appl.category.value,
            "condition": appl.condition.value,
            "age_years": round(appl.age_years(), 2),
            "remaining_life_years": round(appl.remaining_life_years(), 2),
            "pct_life_used": round(appl.pct_life_used(), 1),
            "purchase_cost": appl.purchase_cost,
            "total_maintenance_cost": round(appl.total_maintenance_cost(), 2),
            "total_repair_cost": round(appl.total_repair_cost(), 2),
            "total_cost_of_ownership": round(self.total_cost_of_ownership(), 2),
            "average_annual_cost": round(self.average_annual_cost(), 2),
            "projected_replacement_cost": round(
                self.projected_replacement_cost(), 2
            ),
            "cost_per_year_remaining": round(self.cost_per_year_remaining(), 2),
        }
