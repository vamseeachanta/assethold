"""
appliance_inventory.py — In-memory appliance inventory with JSON persistence.

Provides CRUD operations, category filtering, and round-trip JSON
serialization so appliance records can be saved to and loaded from disk.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional

from assethold.modules.appliances.appliance_model import (
    Appliance,
    ApplianceCategory,
    ApplianceCondition,
    MaintenanceRecord,
    RepairRecord,
)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _date_to_str(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d is not None else None


def _str_to_date(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s is not None else None


def _maintenance_to_dict(rec: MaintenanceRecord) -> Dict[str, Any]:
    return {
        "service_date": _date_to_str(rec.service_date),
        "description": rec.description,
        "cost": rec.cost,
        "technician": rec.technician,
        "notes": rec.notes,
    }


def _dict_to_maintenance(d: Dict[str, Any]) -> MaintenanceRecord:
    return MaintenanceRecord(
        service_date=date.fromisoformat(d["service_date"]),
        description=d["description"],
        cost=float(d["cost"]),
        technician=d.get("technician"),
        notes=d.get("notes"),
    )


def _repair_to_dict(rec: RepairRecord) -> Dict[str, Any]:
    return {
        "repair_date": _date_to_str(rec.repair_date),
        "description": rec.description,
        "cost": rec.cost,
        "failure_cause": rec.failure_cause,
        "technician": rec.technician,
        "warranty_covered": rec.warranty_covered,
    }


def _dict_to_repair(d: Dict[str, Any]) -> RepairRecord:
    return RepairRecord(
        repair_date=date.fromisoformat(d["repair_date"]),
        description=d["description"],
        cost=float(d["cost"]),
        failure_cause=d["failure_cause"],
        technician=d.get("technician"),
        warranty_covered=bool(d.get("warranty_covered", False)),
    )


def _appliance_to_dict(appl: Appliance) -> Dict[str, Any]:
    return {
        "appliance_id": appl.appliance_id,
        "manufacturer": appl.manufacturer,
        "model": appl.model,
        "category": appl.category.value,
        "install_date": _date_to_str(appl.install_date),
        "purchase_cost": appl.purchase_cost,
        "expected_lifespan_years": appl.expected_lifespan_years,
        "serial_number": appl.serial_number,
        "warranty_expiry": _date_to_str(appl.warranty_expiry),
        "condition": appl.condition.value,
        "reliability_rating": appl.reliability_rating,
        "notes": appl.notes,
        "maintenance_records": [
            _maintenance_to_dict(r) for r in appl.maintenance_records
        ],
        "repair_records": [_repair_to_dict(r) for r in appl.repair_records],
    }


def _dict_to_appliance(d: Dict[str, Any]) -> Appliance:
    appl = Appliance(
        appliance_id=d["appliance_id"],
        manufacturer=d["manufacturer"],
        model=d["model"],
        category=ApplianceCategory(d["category"]),
        install_date=date.fromisoformat(d["install_date"]),
        purchase_cost=float(d["purchase_cost"]),
        expected_lifespan_years=int(d["expected_lifespan_years"]),
        serial_number=d.get("serial_number"),
        warranty_expiry=_str_to_date(d.get("warranty_expiry")),
        condition=ApplianceCondition(d.get("condition", "good")),
        reliability_rating=d.get("reliability_rating"),
        notes=d.get("notes"),
    )
    for m in d.get("maintenance_records", []):
        appl.add_maintenance_record(_dict_to_maintenance(m))
    for r in d.get("repair_records", []):
        appl.add_repair_record(_dict_to_repair(r))
    return appl


# ---------------------------------------------------------------------------
# ApplianceInventory
# ---------------------------------------------------------------------------

class ApplianceInventory:
    """
    In-memory repository of Appliance records with JSON persistence.

    Acts as the single source of truth for the appliance inventory.
    Business logic stays out of this class — see LifecycleCostCalculator.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Appliance] = {}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, appliance: Appliance) -> None:
        """Add an appliance to the inventory.  Raises ValueError on duplicate ID."""
        if appliance.appliance_id in self._store:
            raise ValueError(
                f"Appliance with ID '{appliance.appliance_id}' already exists"
            )
        self._store[appliance.appliance_id] = appliance

    def get(self, appliance_id: str) -> Optional[Appliance]:
        """Return the appliance with the given ID, or None if not found."""
        return self._store.get(appliance_id)

    def remove(self, appliance_id: str) -> None:
        """Remove an appliance by ID.  Raises KeyError if not found."""
        if appliance_id not in self._store:
            raise KeyError(f"No appliance with ID '{appliance_id}'")
        del self._store[appliance_id]

    def count(self) -> int:
        """Return the number of appliances in the inventory."""
        return len(self._store)

    def list_all(self) -> List[Appliance]:
        """Return a list of all appliances."""
        return list(self._store.values())

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def filter_by_category(self, category: ApplianceCategory) -> List[Appliance]:
        """Return appliances matching the given category."""
        return [a for a in self._store.values() if a.category == category]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the inventory to a plain dict (JSON-safe)."""
        return {
            "appliances": [_appliance_to_dict(a) for a in self._store.values()]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApplianceInventory":
        """Deserialise an inventory from a dict produced by to_dict()."""
        inv = cls()
        for item in data.get("appliances", []):
            inv.add(_dict_to_appliance(item))
        return inv

    def save_json(self, path: str) -> None:
        """Write the inventory to a JSON file at path."""
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)

    @classmethod
    def load_json(cls, path: str) -> "ApplianceInventory":
        """Load an inventory from a JSON file at path."""
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(data)
