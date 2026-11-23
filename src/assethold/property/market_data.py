"""
market_data.py — Market data integration for property valuation.

Provides comparable sales and tax assessment data for supported US counties.

Data availability:
  - Tax assessment records: public record for Harris TX, Los Angeles CA, Cook IL
  - Comparable sales: no free API available (Zillow deprecated 2021; MLS not public).
    Stub implementation returns empty list; override _fetch_comparable_sales()
    with a paid API (Bridge Interactive, etc.) when available.

LIMITATION: Automated comparable sales data requires a paid API subscription.
When comps are unavailable, the fallback is the county tax assessment value.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import List, Optional

from assethold.property.property_model import Property


class MarketDataError(Exception):
    """Raised when market data retrieval fails unrecoverably."""


@dataclass
class ComparableSale:
    """A single comparable property sale record."""

    address: str
    lat: float
    lon: float
    sale_price: float
    sale_date: str          # ISO-8601 date string
    building_sqft: int
    distance_m: float       # distance from subject property (metres)

    @property
    def price_per_sqft(self) -> Optional[float]:
        """Sale price per square foot, or None if sqft is zero."""
        if not self.building_sqft:
            return None
        return self.sale_price / self.building_sqft


@dataclass
class MarketDataResult:
    """Aggregated market data for a property valuation."""

    assessed_value: Optional[float]
    comparable_sales: List[ComparableSale]
    median_comp_price: Optional[float]
    median_price_per_sqft: Optional[float]
    data_source: str          # "comparable_sales" | "tax_assessment_fallback"
    county_supported: bool    # True if assessor integration is available


class MarketDataProvider:
    """
    Retrieves market data (assessment values and comparable sales) for
    a given property.

    For supported counties the tax assessment value is fetched from
    public records.  Comparable sales currently require a paid API;
    _fetch_comparable_sales() returns an empty list by default.
    """

    def get_market_data(
        self,
        property_: Property,
        radius_m: float = 1_000.0,
    ) -> MarketDataResult:
        """
        Build a MarketDataResult for the given property.

        Steps:
          1. Fetch tax assessment value (or None for unsupported counties).
          2. Fetch comparable sales within radius_m.
          3. Compute median comp price and price/sqft.
          4. Set data_source label.

        Args:
            property_:  Subject property.
            radius_m:   Search radius for comparable sales (metres).

        Returns:
            MarketDataResult

        Raises:
            MarketDataError: on unrecoverable data-fetch failure.
        """
        try:
            assessed = self._fetch_tax_assessment(property_)
            comps = self._fetch_comparable_sales(property_, radius_m)
        except Exception as exc:
            raise MarketDataError(
                f"Failed to fetch market data for {property_.address!r}: {exc}"
            ) from exc

        county_supported = bool(
            property_.county and property_.state
            and self._is_supported_county(property_.county, property_.state)
        )

        median_price: Optional[float] = None
        median_psf: Optional[float] = None
        source: str

        if comps:
            prices = [c.sale_price for c in comps]
            median_price = statistics.median(prices)

            psf_values = [
                c.price_per_sqft
                for c in comps
                if c.price_per_sqft is not None
            ]
            if psf_values:
                median_psf = statistics.median(psf_values)

            source = "comparable_sales"
        else:
            source = "tax_assessment_fallback"

        return MarketDataResult(
            assessed_value=assessed,
            comparable_sales=comps,
            median_comp_price=median_price,
            median_price_per_sqft=median_psf,
            data_source=source,
            county_supported=county_supported,
        )

    # ------------------------------------------------------------------
    # Data-fetch stubs (override / patch for live data)
    # ------------------------------------------------------------------

    def _fetch_tax_assessment(
        self, property_: Property
    ) -> Optional[float]:
        """
        Return the assessed value from county public records.

        Default stub: returns property.assessed_value if already populated,
        else None.  Override to scrape supported county web portals.

        Supported county portals (initial set):
          - Harris County TX:    https://hcad.org/
          - Los Angeles County:  https://assessor.lacounty.gov/
          - Cook County IL:      https://www.cookcountyassessor.com/
        """
        return property_.assessed_value

    def _fetch_comparable_sales(
        self,
        property_: Property,
        radius_m: float,
    ) -> List[ComparableSale]:
        """
        Return recent comparable sales within radius_m of the property.

        Default stub: returns empty list.

        NOTE: Automated comp data requires a paid API subscription.
        Zillow Zestimate API was deprecated in 2021. MLS data is not
        publicly available. Bridge Interactive and similar providers offer
        comp data via paid API — integrate by overriding this method.
        """
        return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_supported_county(self, county: str, state: str) -> bool:
        """Return True for counties with supported assessor integrations."""
        supported = {
            ("harris", "TX"),
            ("los angeles", "CA"),
            ("cook", "IL"),
        }
        return (county.lower(), state.upper()) in supported
