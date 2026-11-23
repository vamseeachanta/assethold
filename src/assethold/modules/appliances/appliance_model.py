"""
appliance_model.py — Core Appliance dataclass and supporting enumerations.

Represents a household or commercial appliance with manufacturer info,
install date, maintenance/repair history, reliability rating, and lifecycle data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ApplianceCategory(Enum):
    """High-level appliance classification."""

    HVAC = "hvac"
    REFRIGERATOR = "refrigerator"
    WASHER = "washer"
    DRYER = "dryer"
    DISHWASHER = "dishwasher"
    WATER_HEATER = "water_heater"
    OVEN = "oven"
    MICROWAVE = "microwave"
    OTHER = "other"


class ApplianceCondition(Enum):
    """Observed condition of an appliance."""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Sub-records
# ---------------------------------------------------------------------------

@dataclass
class MaintenanceRecord:
    """A single preventive maintenance event for an appliance."""

    service_date: date
    description: str
    cost: float
    technician: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if self.cost < 0:
            raise ValueError(f"cost must be non-negative, got {self.cost}")


@dataclass
class RepairRecord:
    """A single corrective repair event for an appliance."""

    repair_date: date
    description: str
    cost: float
    failure_cause: str
    technician: Optional[str] = None
    warranty_covered: bool = False

    def __post_init__(self) -> None:
        if self.cost < 0:
            raise ValueError(f"cost must be non-negative, got {self.cost}")


# ---------------------------------------------------------------------------
# Appliance
# ---------------------------------------------------------------------------

@dataclass
class Appliance:
    """
    A household or commercial appliance record.

    Required fields: appliance_id, manufacturer, model, category,
    install_date, purchase_cost, expected_lifespan_years.
    """

    appliance_id: str
    manufacturer: str
    model: str
    category: ApplianceCategory
    install_date: date
    purchase_cost: float
    expected_lifespan_years: int

    # Optional descriptive fields
    serial_number: Optional[str] = None
    warranty_expiry: Optional[date] = None
    condition: ApplianceCondition = ApplianceCondition.GOOD
    reliability_rating: Optional[float] = None  # 0.0–5.0 scale
    notes: Optional[str] = None

    # History (populated via add_* methods)
    maintenance_records: List[MaintenanceRecord] = field(default_factory=list)
    repair_records: List[RepairRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._validate()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        if not self.manufacturer or not self.manufacturer.strip():
            raise ValueError("manufacturer must be a non-empty string")
        if not self.model or not self.model.strip():
            raise ValueError("model must be a non-empty string")
        if self.purchase_cost < 0:
            raise ValueError(
                f"purchase_cost must be non-negative, got {self.purchase_cost}"
            )
        if self.expected_lifespan_years <= 0:
            raise ValueError(
                f"expected_lifespan_years must be positive, got {self.expected_lifespan_years}"
            )
        if self.reliability_rating is not None:
            if not (0.0 <= self.reliability_rating <= 5.0):
                raise ValueError(
                    f"reliability_rating must be in [0.0, 5.0], got {self.reliability_rating}"
                )

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def age_years(self) -> float:
        """Return current age of the appliance in fractional years."""
        delta = date.today() - self.install_date
        return max(0.0, delta.days / 365.25)

    def remaining_life_years(self) -> float:
        """Return estimated remaining useful life in fractional years."""
        remaining = self.expected_lifespan_years - self.age_years()
        return max(0.0, remaining)

    def pct_life_used(self) -> float:
        """Return percentage of expected lifespan consumed (0–100)."""
        pct = (self.age_years() / self.expected_lifespan_years) * 100.0
        return min(100.0, max(0.0, pct))

    def is_under_warranty(self) -> bool:
        """Return True if the appliance is currently under warranty."""
        if self.warranty_expiry is None:
            return False
        return date.today() <= self.warranty_expiry

    # ------------------------------------------------------------------
    # History management
    # ------------------------------------------------------------------

    def add_maintenance_record(self, record: MaintenanceRecord) -> None:
        """Append a maintenance record to the appliance history."""
        self.maintenance_records.append(record)

    def add_repair_record(self, record: RepairRecord) -> None:
        """Append a repair record to the appliance history."""
        self.repair_records.append(record)

    def total_maintenance_cost(self) -> float:
        """Return the sum of all maintenance costs."""
        return sum(r.cost for r in self.maintenance_records)

    def total_repair_cost(self) -> float:
        """Return the sum of all repair costs."""
        return sum(r.cost for r in self.repair_records)

    def __repr__(self) -> str:
        return (
            f"Appliance(id={self.appliance_id!r}, "
            f"manufacturer={self.manufacturer!r}, "
            f"model={self.model!r}, "
            f"category={self.category.value})"
        )
