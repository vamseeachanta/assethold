# ABOUTME: Cap-rate sensitivity, lease expiration timeline, and NNN vs modified-gross
# ABOUTME: comparison utilities for single-tenant net lease properties.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


# ---------------------------------------------------------------------------
# Cap Rate Sensitivity
# ---------------------------------------------------------------------------


@dataclass
class CapRateScenario:
    """One row in a cap-rate sensitivity table."""

    cap_rate_pct: float
    implied_value: float


def cap_rate_sensitivity(
    noi: float,
    low: float = 5.0,
    high: float = 9.0,
    step: float = 0.5,
) -> List[CapRateScenario]:
    """Compute implied property value at a range of cap rates.

    Args:
        noi: Annual net operating income.
        low: Starting cap rate in percent (inclusive).
        high: Ending cap rate in percent (inclusive).
        step: Increment between cap rates in percent.

    Returns:
        Sorted list of CapRateScenario from lowest cap rate to highest.

    Raises:
        ValueError: If noi is negative, low >= high, or step <= 0.
    """
    if noi < 0:
        raise ValueError(f"noi must be non-negative, got {noi}")
    if low >= high:
        raise ValueError(f"low ({low}) must be less than high ({high})")
    if step <= 0:
        raise ValueError(f"step must be positive, got {step}")

    results: List[CapRateScenario] = []
    rate = low
    # Use a tolerance to avoid floating-point drift skipping the last step.
    while rate <= high + 1e-9:
        cap_decimal = round(rate, 4) / 100.0
        implied = noi / cap_decimal if cap_decimal > 0 else 0.0
        results.append(
            CapRateScenario(cap_rate_pct=round(rate, 4), implied_value=round(implied, 2))
        )
        rate += step
    return results


# ---------------------------------------------------------------------------
# Lease Expiration Timeline
# ---------------------------------------------------------------------------


@dataclass
class LeaseInput:
    """Minimal lease descriptor for timeline analysis."""

    tenant_name: str
    start_date: date
    term_years: int
    annual_rent: float


@dataclass
class ExpirationEvent:
    """A single lease expiration on the timeline."""

    tenant_name: str
    expiration_date: date
    annual_rent: float


@dataclass
class YearlyRentAtRisk:
    """Total rent expiring in a given calendar year."""

    year: int
    rent_expiring: float
    tenants_expiring: List[str]


@dataclass
class LeaseExpirationTimeline:
    """Full timeline result with per-event and per-year rollups."""

    events: List[ExpirationEvent]
    yearly_summary: List[YearlyRentAtRisk]
    total_annual_rent: float


def lease_expiration_timeline(leases: List[LeaseInput]) -> LeaseExpirationTimeline:
    """Build an expiration timeline from a list of leases.

    Each lease expires on the anniversary of its start date after
    ``term_years`` years.  The yearly summary aggregates rent at risk
    per calendar year.

    Args:
        leases: List of lease descriptors.

    Returns:
        LeaseExpirationTimeline with sorted events and yearly rollup.
    """
    events: List[ExpirationEvent] = []
    total_rent = 0.0

    for lease in leases:
        exp_date = date(
            lease.start_date.year + lease.term_years,
            lease.start_date.month,
            lease.start_date.day,
        )
        events.append(
            ExpirationEvent(
                tenant_name=lease.tenant_name,
                expiration_date=exp_date,
                annual_rent=lease.annual_rent,
            )
        )
        total_rent += lease.annual_rent

    events.sort(key=lambda e: e.expiration_date)

    # Aggregate by year.
    year_map: dict[int, YearlyRentAtRisk] = {}
    for ev in events:
        yr = ev.expiration_date.year
        if yr not in year_map:
            year_map[yr] = YearlyRentAtRisk(year=yr, rent_expiring=0.0, tenants_expiring=[])
        year_map[yr].rent_expiring += ev.annual_rent
        year_map[yr].tenants_expiring.append(ev.tenant_name)

    yearly = sorted(year_map.values(), key=lambda y: y.year)

    return LeaseExpirationTimeline(
        events=events,
        yearly_summary=yearly,
        total_annual_rent=total_rent,
    )


# ---------------------------------------------------------------------------
# NNN vs Modified Gross Comparison
# ---------------------------------------------------------------------------


@dataclass
class ExpenseEstimates:
    """Estimated annual operating expenses passed through or absorbed."""

    cam: float = 0.0
    insurance: float = 0.0
    taxes: float = 0.0

    @property
    def total(self) -> float:
        return self.cam + self.insurance + self.taxes


@dataclass
class LeaseStructureResult:
    """Side-by-side comparison of one lease structure."""

    structure: str  # "NNN" or "Modified Gross"
    base_rent: float
    tenant_expense_share: float
    landlord_expense_share: float
    net_effective_rent_to_landlord: float
    gross_occupancy_cost_to_tenant: float


@dataclass
class NNNvsModifiedGrossComparison:
    """Comparison result for both structures."""

    nnn: LeaseStructureResult
    modified_gross: LeaseStructureResult
    landlord_advantage_nnn: float  # positive = NNN is better for landlord


def compare_nnn_vs_modified_gross(
    base_rent: float,
    expenses: ExpenseEstimates,
    modified_gross_landlord_share_pct: float = 50.0,
) -> NNNvsModifiedGrossComparison:
    """Compare net effective rent under NNN vs modified gross.

    Under **NNN**, the tenant pays all operating expenses on top of base
    rent, so the landlord keeps the full base rent.

    Under **modified gross**, the landlord absorbs a share of operating
    expenses (default 50%).  The base rent is the same, but net
    effective rent to the landlord is reduced by the absorbed expenses.

    Args:
        base_rent: Annual base rent.
        expenses: Estimated annual CAM, insurance, and property taxes.
        modified_gross_landlord_share_pct: Percentage of expenses
            absorbed by the landlord under modified gross (0-100).

    Returns:
        NNNvsModifiedGrossComparison with both structures and delta.

    Raises:
        ValueError: If base_rent is negative or share_pct out of range.
    """
    if base_rent < 0:
        raise ValueError(f"base_rent must be non-negative, got {base_rent}")
    if not (0 <= modified_gross_landlord_share_pct <= 100):
        raise ValueError(
            f"modified_gross_landlord_share_pct must be 0-100, got {modified_gross_landlord_share_pct}"
        )

    total_exp = expenses.total
    ll_share_frac = modified_gross_landlord_share_pct / 100.0

    # NNN: tenant pays all expenses.
    nnn = LeaseStructureResult(
        structure="NNN",
        base_rent=base_rent,
        tenant_expense_share=total_exp,
        landlord_expense_share=0.0,
        net_effective_rent_to_landlord=base_rent,
        gross_occupancy_cost_to_tenant=base_rent + total_exp,
    )

    # Modified Gross: landlord absorbs a share of expenses.
    ll_expense = round(total_exp * ll_share_frac, 2)
    tenant_expense = round(total_exp - ll_expense, 2)

    mg = LeaseStructureResult(
        structure="Modified Gross",
        base_rent=base_rent,
        tenant_expense_share=tenant_expense,
        landlord_expense_share=ll_expense,
        net_effective_rent_to_landlord=round(base_rent - ll_expense, 2),
        gross_occupancy_cost_to_tenant=round(base_rent + tenant_expense, 2),
    )

    return NNNvsModifiedGrossComparison(
        nnn=nnn,
        modified_gross=mg,
        landlord_advantage_nnn=round(nnn.net_effective_rent_to_landlord - mg.net_effective_rent_to_landlord, 2),
    )
