"""Tests for the net_lease module — NNLeaseProperty model."""

from __future__ import annotations

import pytest

from assethold.modules.net_lease.net_lease_model import (
    NNLeaseProperty,
    NNLeaseTenant,
    NNLeaseFinancials,
    NNLeaseRenewalOption,
    LeaseType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_tenant() -> NNLeaseTenant:
    return NNLeaseTenant(
        tenant_type="national_pharmacy_chain",
        guaranty="corporate",
        credit_profile="investment_grade_parent",
        lease_type=LeaseType.NN,
        tenant_since_year=2000,
        sales_reporting=True,
    )


@pytest.fixture()
def sample_financials() -> NNLeaseFinancials:
    return NNLeaseFinancials(
        fixed_rent_annual=284_000.0,
        fixed_rent_monthly=23_667.0,
        noi=284_000.0,
        rent_psf_annual=19.03,
        percentage_rent_merch_rate=0.020,
        percentage_rent_food_rate=0.005,
        percentage_rent_rx_rate=0.005,
        total_rent_cap_annual=552_000.0,
    )


@pytest.fixture()
def sample_property(
    sample_tenant: NNLeaseTenant,
    sample_financials: NNLeaseFinancials,
) -> NNLeaseProperty:
    return NNLeaseProperty(
        asset_id="nola-pharmacy-nn-001",
        address="11297 Lake Forest Blvd, New Orleans, LA 70128",
        lat=30.0218,
        lon=-89.8570,
        state="LA",
        city="New Orleans",
        msa="New Orleans-Metairie",
        parcel_id="39W016593",
        year_built=2000,
        building_sqft=14_920,
        land_acres=1.9,
        land_sqft=82_677,
        zoning="C1",
        ownership="fee_simple",
        corner_location=True,
        drive_thru=True,
        parking_spaces=76,
        parking_ratio_per_1000sf=5.09,
        lease_start="2000-09-30",
        lease_end="2030-09-29",
        renewal_options=[
            NNLeaseRenewalOption(count=6, years_each=5)
        ],
        tenant=sample_tenant,
        financials=sample_financials,
    )


# ---------------------------------------------------------------------------
# LeaseType tests
# ---------------------------------------------------------------------------


def test_lease_type_nn_value() -> None:
    assert LeaseType.NN.value == "NN"


def test_lease_type_nnn_value() -> None:
    assert LeaseType.NNN.value == "NNN"


# ---------------------------------------------------------------------------
# NNLeaseTenant tests
# ---------------------------------------------------------------------------


def test_tenant_created_successfully(sample_tenant: NNLeaseTenant) -> None:
    assert sample_tenant.tenant_type == "national_pharmacy_chain"
    assert sample_tenant.guaranty == "corporate"
    assert sample_tenant.lease_type == LeaseType.NN


def test_tenant_invalid_lease_type_raises() -> None:
    with pytest.raises(ValueError, match="lease_type"):
        NNLeaseTenant(
            tenant_type="retail",
            guaranty="corporate",
            credit_profile="ig",
            lease_type="INVALID",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# NNLeaseFinancials tests
# ---------------------------------------------------------------------------


def test_financials_noi_set(sample_financials: NNLeaseFinancials) -> None:
    assert sample_financials.noi == 284_000.0


def test_financials_rent_cap_above_noi(sample_financials: NNLeaseFinancials) -> None:
    assert sample_financials.total_rent_cap_annual > sample_financials.fixed_rent_annual


def test_financials_negative_noi_raises() -> None:
    with pytest.raises(ValueError, match="noi"):
        NNLeaseFinancials(
            fixed_rent_annual=284_000.0,
            fixed_rent_monthly=23_667.0,
            noi=-1.0,
            rent_psf_annual=19.03,
        )


def test_financials_negative_rate_raises() -> None:
    with pytest.raises(ValueError, match="percentage_rent"):
        NNLeaseFinancials(
            fixed_rent_annual=284_000.0,
            fixed_rent_monthly=23_667.0,
            noi=284_000.0,
            rent_psf_annual=19.03,
            percentage_rent_merch_rate=-0.01,
        )


# ---------------------------------------------------------------------------
# NNLeaseRenewalOption tests
# ---------------------------------------------------------------------------


def test_renewal_option_total_years() -> None:
    opt = NNLeaseRenewalOption(count=6, years_each=5)
    assert opt.total_option_years == 30


def test_renewal_option_zero_count() -> None:
    opt = NNLeaseRenewalOption(count=0, years_each=5)
    assert opt.total_option_years == 0


# ---------------------------------------------------------------------------
# NNLeaseProperty tests
# ---------------------------------------------------------------------------


def test_property_created(sample_property: NNLeaseProperty) -> None:
    assert sample_property.asset_id == "nola-pharmacy-nn-001"
    assert sample_property.building_sqft == 14_920


def test_property_lease_remaining_years(sample_property: NNLeaseProperty) -> None:
    # From 2025 perspective: lease ends 2030-09-29 → ~5 years
    remaining = sample_property.lease_remaining_years(as_of_year=2025)
    assert 4 <= remaining <= 6


def test_property_max_option_term_years(sample_property: NNLeaseProperty) -> None:
    assert sample_property.max_option_term_years == 30


def test_property_invalid_lat_raises() -> None:
    with pytest.raises(ValueError, match="lat"):
        NNLeaseProperty(
            asset_id="x",
            address="123 Main St",
            lat=999.0,
            lon=-90.0,
        )


def test_property_invalid_building_sqft_raises() -> None:
    with pytest.raises(ValueError, match="building_sqft"):
        NNLeaseProperty(
            asset_id="x",
            address="123 Main St",
            lat=30.0,
            lon=-90.0,
            building_sqft=-1,
        )


def test_property_repr_contains_address(sample_property: NNLeaseProperty) -> None:
    r = repr(sample_property)
    assert "Lake Forest" in r


def test_property_from_yaml_roundtrip(
    sample_property: NNLeaseProperty, tmp_path
) -> None:
    yaml_file = tmp_path / "test_prop.yaml"
    sample_property.to_yaml(yaml_file)
    loaded = NNLeaseProperty.from_yaml(yaml_file)
    assert loaded.asset_id == sample_property.asset_id
    assert loaded.financials is not None
    assert loaded.financials.noi == pytest.approx(284_000.0)
