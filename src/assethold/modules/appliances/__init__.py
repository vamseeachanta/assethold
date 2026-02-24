"""
Appliance lifecycle analytics module for assethold.

Provides data models, lifecycle cost calculations, geographic vendor lookup,
and an inventory storage layer for tracking household and commercial appliances.
"""

from assethold.modules.appliances.appliance_model import (
    Appliance,
    ApplianceCategory,
    ApplianceCondition,
    MaintenanceRecord,
    RepairRecord,
)
from assethold.modules.appliances.appliance_inventory import ApplianceInventory
from assethold.modules.appliances.lifecycle_calculator import LifecycleCostCalculator
from assethold.modules.appliances.vendor_lookup import VendorLookup, VendorRecord
from assethold.modules.appliances.appliance_cli import ApplianceCLI

__all__ = [
    "Appliance",
    "ApplianceCategory",
    "ApplianceCondition",
    "MaintenanceRecord",
    "RepairRecord",
    "ApplianceInventory",
    "LifecycleCostCalculator",
    "VendorLookup",
    "VendorRecord",
    "ApplianceCLI",
]
