"""
Tests for market_data.py — Comparable sales and tax assessment data.
TDD: red → green → refactor
"""
import pytest
from unittest.mock import patch, MagicMock

from assethold.property.market_data import (
    MarketDataProvider,
    ComparableSale,
    MarketDataResult,
    MarketDataError,
)
from assethold.property.property_model import Property, PropertyType


@pytest.fixture()
def sample_property():
    return Property(
        address="123 Main St, Houston, TX 77001",
        lat=29.7604,
        lon=-95.3698,
        county="Harris",
        state="TX",
        building_sqft=2000,
        property_type=PropertyType.RESIDENTIAL,
        assessed_value=320000.0,
    )


class TestComparableSale:
    """Tests for ComparableSale dataclass."""

    def test_comparable_sale_stores_all_fields(self):
        comp = ComparableSale(
            address="456 Oak Ave, Houston, TX 77002",
            lat=29.762,
            lon=-95.371,
            sale_price=310000.0,
            sale_date="2025-06-15",
            building_sqft=1900,
            distance_m=450.0,
        )
        assert comp.sale_price == pytest.approx(310000.0)
        assert comp.building_sqft == 1900
        assert comp.distance_m == pytest.approx(450.0)

    def test_price_per_sqft_computed(self):
        comp = ComparableSale(
            address="789 Elm St",
            lat=29.760,
            lon=-95.368,
            sale_price=300000.0,
            sale_date="2025-01-10",
            building_sqft=2000,
            distance_m=300.0,
        )
        assert comp.price_per_sqft == pytest.approx(150.0)

    def test_price_per_sqft_zero_sqft_returns_none(self):
        comp = ComparableSale(
            address="789 Elm St",
            lat=29.760,
            lon=-95.368,
            sale_price=300000.0,
            sale_date="2025-01-10",
            building_sqft=0,
            distance_m=300.0,
        )
        assert comp.price_per_sqft is None


class TestMarketDataResult:
    """Tests for MarketDataResult container."""

    def test_market_data_result_fields(self):
        comps = [
            ComparableSale("A", 29.76, -95.37, 310000.0, "2025-01-01", 1900, 400.0),
            ComparableSale("B", 29.761, -95.369, 330000.0, "2025-03-01", 2100, 600.0),
        ]
        result = MarketDataResult(
            assessed_value=320000.0,
            comparable_sales=comps,
            median_comp_price=320000.0,
            median_price_per_sqft=160.0,
            data_source="tax_assessment_fallback",
            county_supported=True,
        )
        assert result.assessed_value == pytest.approx(320000.0)
        assert len(result.comparable_sales) == 2
        assert result.data_source == "tax_assessment_fallback"

    def test_market_data_result_no_comps(self):
        result = MarketDataResult(
            assessed_value=250000.0,
            comparable_sales=[],
            median_comp_price=None,
            median_price_per_sqft=None,
            data_source="tax_assessment_fallback",
            county_supported=False,
        )
        assert result.comparable_sales == []
        assert result.median_comp_price is None


class TestMarketDataProvider:
    """Tests for MarketDataProvider."""

    def test_provider_instantiates(self):
        provider = MarketDataProvider()
        assert provider is not None

    def test_get_market_data_returns_result(self, sample_property):
        provider = MarketDataProvider()
        with patch.object(
            provider, "_fetch_tax_assessment", return_value=320000.0
        ):
            result = provider.get_market_data(sample_property, radius_m=1000.0)

        assert isinstance(result, MarketDataResult)

    def test_fallback_uses_assessed_value_when_no_comps(self, sample_property):
        provider = MarketDataProvider()
        with patch.object(
            provider, "_fetch_tax_assessment", return_value=320000.0
        ), patch.object(
            provider, "_fetch_comparable_sales", return_value=[]
        ):
            result = provider.get_market_data(sample_property, radius_m=1000.0)

        assert result.assessed_value == pytest.approx(320000.0)
        assert result.data_source == "tax_assessment_fallback"

    def test_with_comps_source_label_correct(self, sample_property):
        provider = MarketDataProvider()
        comps = [
            ComparableSale("X", 29.760, -95.368, 315000.0, "2025-01-01", 1950, 200.0),
            ComparableSale("Y", 29.761, -95.371, 325000.0, "2025-02-01", 2050, 350.0),
        ]
        with patch.object(
            provider, "_fetch_tax_assessment", return_value=320000.0
        ), patch.object(
            provider, "_fetch_comparable_sales", return_value=comps
        ):
            result = provider.get_market_data(sample_property, radius_m=1000.0)

        assert result.data_source == "comparable_sales"
        assert len(result.comparable_sales) == 2

    def test_median_comp_price_computed_correctly(self, sample_property):
        provider = MarketDataProvider()
        comps = [
            ComparableSale("A", 29.760, -95.368, 300000.0, "2025-01-01", 2000, 100.0),
            ComparableSale("B", 29.761, -95.369, 350000.0, "2025-02-01", 2000, 200.0),
            ComparableSale("C", 29.762, -95.370, 320000.0, "2025-03-01", 2000, 300.0),
        ]
        with patch.object(
            provider, "_fetch_tax_assessment", return_value=310000.0
        ), patch.object(
            provider, "_fetch_comparable_sales", return_value=comps
        ):
            result = provider.get_market_data(sample_property, radius_m=1000.0)

        assert result.median_comp_price == pytest.approx(320000.0)

    def test_median_price_per_sqft_computed(self, sample_property):
        provider = MarketDataProvider()
        comps = [
            ComparableSale("A", 29.760, -95.368, 300000.0, "2025-01-01", 2000, 100.0),
            ComparableSale("B", 29.761, -95.369, 320000.0, "2025-02-01", 2000, 200.0),
        ]
        with patch.object(
            provider, "_fetch_tax_assessment", return_value=310000.0
        ), patch.object(
            provider, "_fetch_comparable_sales", return_value=comps
        ):
            result = provider.get_market_data(sample_property, radius_m=1000.0)

        assert result.median_price_per_sqft == pytest.approx(155.0)

    def test_raises_market_data_error_on_failure(self, sample_property):
        provider = MarketDataProvider()
        with patch.object(
            provider, "_fetch_tax_assessment", side_effect=Exception("network")
        ):
            with pytest.raises(MarketDataError):
                provider.get_market_data(sample_property, radius_m=1000.0)
