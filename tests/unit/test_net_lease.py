# ABOUTME: Unit tests for the net lease financial model — tenants, financials, and property records.
# ABOUTME: Covers dataclass validation, computed properties, YAML round-trips, and edge cases.

import tempfile
from pathlib import Path

import pytest
import yaml

from assethold.modules.net_lease.net_lease_model import (
    LeaseType,
    NNLeaseTenant,
    NNLeaseFinancials,
    NNLeaseRenewalOption,
    NNLeaseSalesHistory,
    NNLeaseOwnerPnL,
    NNLeaseDemographics,
    NNLeaseProperty,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_property(**overrides) -> NNLeaseProperty:
    """Return a valid NNLeaseProperty with sensible defaults."""
    defaults = dict(
        asset_id="NNL-001",
        address="100 Main St, Anytown, TX 75001",
        lat=32.78,
        lon=-96.80,
        state="TX",
        building_sqft=14000,
        year_built=2005,
        lease_start="2020-01-01",
        lease_end="2040-12-31",
    )
    defaults.update(overrides)
    return NNLeaseProperty(**defaults)


def _make_financials(**overrides) -> NNLeaseFinancials:
    defaults = dict(
        fixed_rent_annual=120000.0,
        fixed_rent_monthly=10000.0,
        noi=115000.0,
        rent_psf_annual=8.57,
    )
    defaults.update(overrides)
    return NNLeaseFinancials(**defaults)


# ---------------------------------------------------------------------------
# LeaseType enum
# ---------------------------------------------------------------------------

class TestLeaseType:
    """Tests for the LeaseType enumeration."""

    def test_nn_value(self):
        assert LeaseType.NN.value == "NN"

    def test_nnn_value(self):
        assert LeaseType.NNN.value == "NNN"

    def test_gross_value(self):
        assert LeaseType.GROSS.value == "Gross"


# ---------------------------------------------------------------------------
# NNLeaseTenant
# ---------------------------------------------------------------------------

class TestNNLeaseTenant:
    """Tests for NNLeaseTenant dataclass."""

    def test_create_valid_tenant(self):
        tenant = NNLeaseTenant(
            tenant_type="pharmacy",
            guaranty="corporate",
            credit_profile="investment_grade_parent",
            lease_type=LeaseType.NN,
        )
        assert tenant.tenant_type == "pharmacy"
        assert tenant.lease_type == LeaseType.NN
        assert tenant.rofr is False

    def test_invalid_lease_type_raises(self):
        with pytest.raises(ValueError, match="lease_type must be a LeaseType enum"):
            NNLeaseTenant(
                tenant_type="retail",
                guaranty="personal",
                credit_profile="speculative",
                lease_type="NN",  # string instead of enum
            )

    def test_optional_fields_default_to_none_or_false(self):
        tenant = NNLeaseTenant(
            tenant_type="grocery",
            guaranty="corporate",
            credit_profile="bbb",
        )
        assert tenant.tenant_since_year is None
        assert tenant.sales_reporting is False
        assert tenant.exclusivity is False


# ---------------------------------------------------------------------------
# NNLeaseFinancials
# ---------------------------------------------------------------------------

class TestNNLeaseFinancials:
    """Tests for NNLeaseFinancials dataclass."""

    def test_create_valid_financials(self):
        fin = _make_financials()
        assert fin.fixed_rent_annual == pytest.approx(120000.0)
        assert fin.percentage_rent_merch_rate == pytest.approx(0.0)

    def test_negative_noi_raises(self):
        with pytest.raises(ValueError, match="noi must be non-negative"):
            _make_financials(noi=-5000.0)

    def test_negative_percentage_rent_rate_raises(self):
        with pytest.raises(ValueError, match="percentage_rent rate"):
            _make_financials(percentage_rent_merch_rate=-0.01)

    def test_valid_percentage_rent_rates(self):
        fin = _make_financials(
            percentage_rent_merch_rate=0.02,
            percentage_rent_food_rate=0.03,
            percentage_rent_rx_rate=0.01,
        )
        assert fin.percentage_rent_merch_rate == pytest.approx(0.02)


# ---------------------------------------------------------------------------
# NNLeaseRenewalOption
# ---------------------------------------------------------------------------

class TestNNLeaseRenewalOption:
    """Tests for NNLeaseRenewalOption computed properties."""

    def test_total_option_years(self):
        opt = NNLeaseRenewalOption(count=4, years_each=5)
        assert opt.total_option_years == 20

    def test_total_option_years_single(self):
        opt = NNLeaseRenewalOption(count=1, years_each=10)
        assert opt.total_option_years == 10

    def test_total_option_years_zero(self):
        opt = NNLeaseRenewalOption(count=0, years_each=5)
        assert opt.total_option_years == 0


# ---------------------------------------------------------------------------
# NNLeaseSalesHistory
# ---------------------------------------------------------------------------

class TestNNLeaseSalesHistory:
    """Tests for sales history computed properties."""

    def test_total_gross_sales(self):
        sales = NNLeaseSalesHistory(
            period_label="FY2024",
            merchandise_sales=500000.0,
            food_sales=200000.0,
            rx_sales=300000.0,
            fixed_rent=120000.0,
            percentage_rent_calculated=5000.0,
            percentage_rent_paid=5000.0,
        )
        assert sales.total_gross_sales == pytest.approx(1000000.0)


# ---------------------------------------------------------------------------
# NNLeaseOwnerPnL
# ---------------------------------------------------------------------------

class TestNNLeaseOwnerPnL:
    """Tests for owner P&L computed properties."""

    def test_total_opex(self):
        pnl = NNLeaseOwnerPnL(
            period_label="CY2024",
            rental_income=120000.0,
            expense_insurance=3000.0,
            expense_property_mgmt=2000.0,
            expense_repairs=1500.0,
            expense_legal=500.0,
            expense_bank_charges=100.0,
            expense_office=200.0,
        )
        assert pnl.total_opex == pytest.approx(7300.0)

    def test_noi_before_debt(self):
        pnl = NNLeaseOwnerPnL(
            period_label="CY2024",
            rental_income=120000.0,
            expense_insurance=5000.0,
        )
        assert pnl.noi_before_debt == pytest.approx(115000.0)

    def test_net_income_with_debt_service(self):
        pnl = NNLeaseOwnerPnL(
            period_label="CY2024",
            rental_income=120000.0,
            expense_insurance=5000.0,
            debt_service_interest=30000.0,
        )
        assert pnl.net_income == pytest.approx(85000.0)

    def test_net_income_zero_expenses(self):
        pnl = NNLeaseOwnerPnL(period_label="CY2024", rental_income=100000.0)
        assert pnl.total_opex == pytest.approx(0.0)
        assert pnl.noi_before_debt == pytest.approx(100000.0)
        assert pnl.net_income == pytest.approx(100000.0)


# ---------------------------------------------------------------------------
# NNLeaseProperty
# ---------------------------------------------------------------------------

class TestNNLeaseProperty:
    """Tests for the NNLeaseProperty dataclass."""

    def test_create_minimal_property(self):
        prop = NNLeaseProperty(asset_id="P1", address="123 Test St")
        assert prop.asset_id == "P1"
        assert prop.lat == 0.0
        assert prop.ownership == "fee_simple"

    def test_invalid_lat_raises(self):
        with pytest.raises(ValueError, match="lat .* out of range"):
            _make_property(lat=91.0)

    def test_invalid_lon_raises(self):
        with pytest.raises(ValueError, match="lon .* out of range"):
            _make_property(lon=-181.0)

    def test_negative_building_sqft_raises(self):
        with pytest.raises(ValueError, match="building_sqft must be non-negative"):
            _make_property(building_sqft=-100)

    def test_lease_remaining_years(self):
        prop = _make_property(lease_end="2040-12-31")
        assert prop.lease_remaining_years(as_of_year=2026) == 14

    def test_lease_remaining_years_past_expiry(self):
        prop = _make_property(lease_end="2020-06-30")
        assert prop.lease_remaining_years(as_of_year=2026) == 0

    def test_lease_remaining_years_no_end(self):
        prop = _make_property(lease_end=None)
        assert prop.lease_remaining_years(as_of_year=2026) == 0

    def test_max_option_term_years(self):
        prop = _make_property(
            renewal_options=[
                NNLeaseRenewalOption(count=4, years_each=5),
                NNLeaseRenewalOption(count=2, years_each=3),
            ]
        )
        assert prop.max_option_term_years == 26

    def test_max_option_term_years_no_options(self):
        prop = _make_property()
        assert prop.max_option_term_years == 0

    def test_yaml_round_trip(self, tmp_path):
        tenant = NNLeaseTenant(
            tenant_type="pharmacy",
            guaranty="corporate",
            credit_profile="investment_grade",
            lease_type=LeaseType.NNN,
            tenant_since_year=2010,
        )
        financials = _make_financials()
        demographics = NNLeaseDemographics(pop_1mi=25000, avg_hhi_1mi=75000.0)
        sales = NNLeaseSalesHistory(
            period_label="FY2024",
            merchandise_sales=500000.0,
            food_sales=200000.0,
            rx_sales=300000.0,
            fixed_rent=120000.0,
            percentage_rent_calculated=5000.0,
            percentage_rent_paid=5000.0,
        )
        owner_pnl = NNLeaseOwnerPnL(
            period_label="CY2024",
            rental_income=120000.0,
            expense_insurance=3000.0,
        )
        renewal = NNLeaseRenewalOption(count=4, years_each=5)

        prop = _make_property(
            tenant=tenant,
            financials=financials,
            demographics=demographics,
            sales_history=[sales],
            owner_pnl=[owner_pnl],
            renewal_options=[renewal],
        )

        yaml_path = tmp_path / "lease.yaml"
        prop.to_yaml(yaml_path)
        loaded = NNLeaseProperty.from_yaml(yaml_path)

        assert loaded.asset_id == "NNL-001"
        assert loaded.tenant.tenant_type == "pharmacy"
        assert loaded.tenant.lease_type == LeaseType.NNN
        assert loaded.financials.fixed_rent_annual == pytest.approx(120000.0)
        assert loaded.demographics.pop_1mi == 25000
        assert len(loaded.sales_history) == 1
        assert loaded.sales_history[0].total_gross_sales == pytest.approx(1000000.0)
        assert len(loaded.owner_pnl) == 1
        assert loaded.max_option_term_years == 20

    def test_repr_contains_id_and_address(self):
        prop = _make_property()
        r = repr(prop)
        assert "NNL-001" in r
        assert "100 Main St" in r
