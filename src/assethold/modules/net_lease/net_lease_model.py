"""net_lease_model.py — Dataclasses for single-tenant net lease (NN/NNN) properties."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml


class LeaseType(Enum):
    NN = "NN"
    NNN = "NNN"
    N = "N"
    GROSS = "Gross"


@dataclass
class NNLeaseTenant:
    """Abstracted tenant profile — no client-identifying data."""

    tenant_type: str
    guaranty: str  # e.g. "corporate", "personal"
    credit_profile: str  # e.g. "investment_grade_parent"
    lease_type: LeaseType = LeaseType.NN
    tenant_since_year: Optional[int] = None
    sales_reporting: bool = False
    exclusivity: bool = False
    rofr: bool = False  # right of first refusal

    def __post_init__(self) -> None:
        if not isinstance(self.lease_type, LeaseType):
            raise ValueError(
                f"lease_type must be a LeaseType enum, got {self.lease_type!r}"
            )


@dataclass
class NNLeaseFinancials:
    """Rent and income figures for a net lease property."""

    fixed_rent_annual: float
    fixed_rent_monthly: float
    noi: float  # net operating income (per offering / stated)
    rent_psf_annual: float
    rent_psf_monthly: Optional[float] = None
    percentage_rent_merch_rate: float = 0.0
    percentage_rent_food_rate: float = 0.0
    percentage_rent_rx_rate: float = 0.0
    total_rent_cap_annual: Optional[float] = None

    def __post_init__(self) -> None:
        if self.noi < 0:
            raise ValueError(f"noi must be non-negative, got {self.noi}")
        for attr in (
            "percentage_rent_merch_rate",
            "percentage_rent_food_rate",
            "percentage_rent_rx_rate",
        ):
            val = getattr(self, attr)
            if val < 0:
                raise ValueError(f"percentage_rent rate {attr}={val} must be >= 0")


@dataclass
class NNLeaseRenewalOption:
    """Renewal option block (count × years_each)."""

    count: int
    years_each: int

    @property
    def total_option_years(self) -> int:
        return self.count * self.years_each


@dataclass
class NNLeaseSalesHistory:
    """Annual gross-sales statement from tenant (abstracted — no tenant ID)."""

    period_label: str  # e.g. "FY2022", "CY2025"
    merchandise_sales: float
    food_sales: float
    rx_sales: float
    fixed_rent: float
    percentage_rent_calculated: float
    percentage_rent_paid: float  # amount above fixed rent actually remitted

    @property
    def total_gross_sales(self) -> float:
        return self.merchandise_sales + self.food_sales + self.rx_sales


@dataclass
class NNLeaseOwnerPnL:
    """Simplified owner P&L (entity name abstracted)."""

    period_label: str
    rental_income: float
    expense_insurance: float = 0.0
    expense_property_mgmt: float = 0.0
    expense_repairs: float = 0.0
    expense_legal: float = 0.0
    expense_bank_charges: float = 0.0
    expense_office: float = 0.0
    debt_service_interest: float = 0.0

    @property
    def total_opex(self) -> float:
        return (
            self.expense_insurance
            + self.expense_property_mgmt
            + self.expense_repairs
            + self.expense_legal
            + self.expense_bank_charges
            + self.expense_office
        )

    @property
    def noi_before_debt(self) -> float:
        return self.rental_income - self.total_opex

    @property
    def net_income(self) -> float:
        return self.noi_before_debt - self.debt_service_interest


@dataclass
class NNLeaseDemographics:
    """Trade area demographics at standard radii."""

    pop_1mi: Optional[int] = None
    pop_3mi: Optional[int] = None
    pop_5mi: Optional[int] = None
    avg_hhi_1mi: Optional[float] = None
    avg_hhi_3mi: Optional[float] = None
    avg_hhi_5mi: Optional[float] = None
    employees_1mi: Optional[int] = None
    employees_3mi: Optional[int] = None
    employees_5mi: Optional[int] = None
    demo_year: Optional[int] = None


@dataclass
class NNLeaseProperty:
    """
    Single-tenant net lease property record.

    Designed to hold due-diligence data from offering materials and
    data rooms without embedding proprietary source attribution.
    """

    # Identity
    asset_id: str
    address: str

    # Geography
    lat: float = 0.0
    lon: float = 0.0
    state: Optional[str] = None
    city: Optional[str] = None
    msa: Optional[str] = None
    parcel_id: Optional[str] = None

    # Physical
    year_built: Optional[int] = None
    building_sqft: Optional[int] = None
    land_acres: Optional[float] = None
    land_sqft: Optional[int] = None
    zoning: Optional[str] = None
    ownership: str = "fee_simple"
    corner_location: bool = False
    drive_thru: bool = False
    parking_spaces: Optional[int] = None
    parking_ratio_per_1000sf: Optional[float] = None

    # Traffic
    aadt_primary_road: Optional[int] = None
    aadt_secondary_road: Optional[int] = None
    aadt_highway: Optional[int] = None
    annual_foot_traffic: Optional[int] = None
    foot_traffic_national_pct: Optional[int] = None
    foot_traffic_state_pct: Optional[int] = None

    # Lease terms
    lease_start: Optional[str] = None  # ISO date string
    lease_end: Optional[str] = None
    renewal_options: list[NNLeaseRenewalOption] = field(default_factory=list)

    # Related objects
    tenant: Optional[NNLeaseTenant] = None
    financials: Optional[NNLeaseFinancials] = None
    demographics: Optional[NNLeaseDemographics] = None
    sales_history: list[NNLeaseSalesHistory] = field(default_factory=list)
    owner_pnl: list[NNLeaseOwnerPnL] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if self.lat and not (-90.0 <= self.lat <= 90.0):
            raise ValueError(f"lat {self.lat} out of range [-90, 90]")
        if self.lon and not (-180.0 <= self.lon <= 180.0):
            raise ValueError(f"lon {self.lon} out of range [-180, 180]")
        if self.building_sqft is not None and self.building_sqft < 0:
            raise ValueError(f"building_sqft must be non-negative, got {self.building_sqft}")

    def lease_remaining_years(self, as_of_year: int) -> int:
        """Approximate whole years remaining on base lease term."""
        if not self.lease_end:
            return 0
        end_year = int(self.lease_end[:4])
        return max(0, end_year - as_of_year)

    @property
    def max_option_term_years(self) -> int:
        return sum(opt.total_option_years for opt in self.renewal_options)

    def __repr__(self) -> str:
        return (
            f"NNLeaseProperty(id={self.asset_id!r}, address={self.address!r}, "
            f"sqft={self.building_sqft}, lease_end={self.lease_end!r})"
        )

    # ------------------------------------------------------------------
    # YAML serialisation helpers
    # ------------------------------------------------------------------

    def to_yaml(self, path: Path) -> None:
        """Serialise to YAML for persistence."""
        data = _to_dict(self)
        with open(path, "w") as fh:
            yaml.dump(data, fh, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, path: Path) -> NNLeaseProperty:
        """Load an NNLeaseProperty from a YAML file."""
        with open(path) as fh:
            data = yaml.safe_load(fh)
        return _from_dict(data)


# ---------------------------------------------------------------------------
# Private (de)serialisation helpers
# ---------------------------------------------------------------------------


def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclass/enum instances to plain dicts."""
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    return obj


def _from_dict(data: dict) -> NNLeaseProperty:
    """Reconstruct NNLeaseProperty from a plain dict (loaded from YAML)."""
    tenant_raw = data.pop("tenant", None)
    fin_raw = data.pop("financials", None)
    demo_raw = data.pop("demographics", None)
    sales_raw = data.pop("sales_history", []) or []
    pnl_raw = data.pop("owner_pnl", []) or []
    opts_raw = data.pop("renewal_options", []) or []

    tenant = None
    if tenant_raw:
        lt = tenant_raw.pop("lease_type", "NN")
        tenant = NNLeaseTenant(
            lease_type=LeaseType(lt),
            **tenant_raw,
        )

    financials = NNLeaseFinancials(**fin_raw) if fin_raw else None
    demographics = NNLeaseDemographics(**demo_raw) if demo_raw else None
    sales_history = [NNLeaseSalesHistory(**s) for s in sales_raw]
    owner_pnl = [NNLeaseOwnerPnL(**p) for p in pnl_raw]
    renewal_options = [NNLeaseRenewalOption(**o) for o in opts_raw]

    return NNLeaseProperty(
        tenant=tenant,
        financials=financials,
        demographics=demographics,
        sales_history=sales_history,
        owner_pnl=owner_pnl,
        renewal_options=renewal_options,
        **data,
    )
