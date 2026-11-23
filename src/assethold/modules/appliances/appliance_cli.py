"""
appliance_cli.py — CLI and config-driven interface for the appliance lifecycle module.

Exposes:
  - ApplianceCLI: query appliance status and vendor counts
  - build_sample_inventory(): factory that returns a pre-populated demo inventory

Usage (from project root):
    python -m assethold.modules.appliances.appliance_cli --help
    python -m assethold.modules.appliances.appliance_cli status
    python -m assethold.modules.appliances.appliance_cli vendors --location "Houston, TX" \
        --category hvac --radius 40
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any, Dict, List, Optional

from assethold.modules.appliances.appliance_inventory import ApplianceInventory
from assethold.modules.appliances.appliance_model import (
    Appliance,
    ApplianceCategory,
    MaintenanceRecord,
    RepairRecord,
)
from assethold.modules.appliances.lifecycle_calculator import LifecycleCostCalculator
from assethold.modules.appliances.vendor_lookup import VendorLookup


# ---------------------------------------------------------------------------
# Sample inventory factory
# ---------------------------------------------------------------------------

def build_sample_inventory() -> ApplianceInventory:
    """Return a pre-populated demo ApplianceInventory for development/testing."""
    inv = ApplianceInventory()

    hvac = Appliance(
        appliance_id="DEMO-HVAC-01",
        manufacturer="Carrier",
        model="24ACC636A003",
        category=ApplianceCategory.HVAC,
        install_date=date(2018, 6, 1),
        purchase_cost=4200.00,
        expected_lifespan_years=15,
        reliability_rating=4.1,
        notes="Central air unit, 3-ton",
    )
    hvac.add_maintenance_record(
        MaintenanceRecord(
            service_date=date(2021, 5, 15),
            description="Annual inspection and filter replacement",
            cost=120.0,
            technician="CoolAir Services",
        )
    )
    hvac.add_maintenance_record(
        MaintenanceRecord(
            service_date=date(2023, 5, 10),
            description="Refrigerant top-off and coil cleaning",
            cost=180.0,
            technician="CoolAir Services",
        )
    )
    inv.add(hvac)

    fridge = Appliance(
        appliance_id="DEMO-FRIDGE-01",
        manufacturer="Whirlpool",
        model="WRF535SWHZ",
        category=ApplianceCategory.REFRIGERATOR,
        install_date=date(2020, 3, 12),
        purchase_cost=1350.00,
        expected_lifespan_years=14,
        reliability_rating=4.3,
    )
    inv.add(fridge)

    washer = Appliance(
        appliance_id="DEMO-WASH-01",
        manufacturer="LG",
        model="WM4000HWA",
        category=ApplianceCategory.WASHER,
        install_date=date(2021, 8, 20),
        purchase_cost=950.00,
        expected_lifespan_years=11,
        reliability_rating=4.5,
    )
    washer.add_repair_record(
        RepairRecord(
            repair_date=date(2023, 11, 5),
            description="Door latch replacement",
            cost=95.0,
            failure_cause="Worn latch mechanism",
        )
    )
    inv.add(washer)

    water_heater = Appliance(
        appliance_id="DEMO-WH-01",
        manufacturer="Rheem",
        model="PROG40-38N RH62",
        category=ApplianceCategory.WATER_HEATER,
        install_date=date(2015, 11, 3),
        purchase_cost=650.00,
        expected_lifespan_years=12,
        reliability_rating=3.8,
        notes="40-gal natural gas unit",
    )
    inv.add(water_heater)

    return inv


# ---------------------------------------------------------------------------
# ApplianceCLI
# ---------------------------------------------------------------------------

class ApplianceCLI:
    """
    High-level interface for querying appliance lifecycle status and vendor data.

    Wraps ApplianceInventory + LifecycleCostCalculator + VendorLookup.
    """

    def __init__(self, inventory: Optional[ApplianceInventory] = None) -> None:
        self._inventory = inventory or build_sample_inventory()

    # ------------------------------------------------------------------
    # Status report
    # ------------------------------------------------------------------

    def status_report(self) -> Dict[str, Any]:
        """
        Return a full lifecycle status report for every appliance in the inventory.
        """
        entries: List[Dict[str, Any]] = []
        for appl in self._inventory.list_all():
            calc = LifecycleCostCalculator(appl)
            entries.append(calc.lifecycle_summary())
        return {"appliances": entries}

    # ------------------------------------------------------------------
    # Vendor count
    # ------------------------------------------------------------------

    def vendor_count(
        self,
        location: str,
        category: str,
        radius_km: float = 40.0,
    ) -> int:
        """
        Return the number of preferred service vendors within radius_km of location.
        """
        lookup = VendorLookup()
        return lookup.vendor_count_by_location(
            location=location,
            category=category,
            radius_km=radius_km,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="appliance-cli",
        description="Appliance lifecycle analytics CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status sub-command
    status_parser = subparsers.add_parser(
        "status", help="Print lifecycle status for all appliances"
    )
    status_parser.add_argument(
        "--inventory",
        metavar="PATH",
        help="Path to a JSON inventory file (default: built-in demo)",
    )
    status_parser.add_argument(
        "--output",
        metavar="PATH",
        help="Write JSON output to this file instead of stdout",
    )

    # vendors sub-command
    vendor_parser = subparsers.add_parser(
        "vendors",
        help="Count preferred vendor service companies in a geographic area",
    )
    vendor_parser.add_argument(
        "--location",
        required=True,
        metavar="LOCATION",
        help='Location string, e.g. "Houston, TX" or "77001"',
    )
    vendor_parser.add_argument(
        "--category",
        required=True,
        metavar="CATEGORY",
        help="Appliance category (hvac, refrigerator, washer, …)",
    )
    vendor_parser.add_argument(
        "--radius",
        type=float,
        default=40.0,
        metavar="KM",
        help="Search radius in kilometres (default: 40)",
    )

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv)

    if args.command == "status":
        if args.inventory:
            inventory = ApplianceInventory.load_json(args.inventory)
        else:
            inventory = build_sample_inventory()
        cli = ApplianceCLI(inventory=inventory)
        report = cli.status_report()
        output_json = json.dumps(report, indent=2, ensure_ascii=False)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(output_json)
            print(f"Report written to {args.output}")
        else:
            print(output_json)

    elif args.command == "vendors":
        cli = ApplianceCLI()
        count = cli.vendor_count(
            location=args.location,
            category=args.category,
            radius_km=args.radius,
        )
        print(
            f"Vendors found for '{args.category}' within {args.radius} km "
            f"of '{args.location}': {count}"
        )


if __name__ == "__main__":
    main()
