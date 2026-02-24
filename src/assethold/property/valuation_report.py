"""
valuation_report.py — Markdown report generator for property valuation.

Produces a human-readable Markdown report containing:
  - Property details
  - Spatial factor scores with explanations
  - Comparable sales summary
  - Estimated value range with disclaimer
  - Data sources and methodology notes
"""

from __future__ import annotations

from typing import List

from assethold.property.property_model import Property
from assethold.property.spatial_factors import SpatialFactors
from assethold.property.market_data import ComparableSale, MarketDataResult
from assethold.property.valuation import ValuationResult


_FACTOR_LABELS = {
    "flood_zone": "Flood Zone",
    "traffic": "Traffic Volume",
    "school": "School Quality",
    "transit": "Transit Access",
    "park": "Park Proximity",
    "commercial": "Commercial Proximity",
}

_DATA_SOURCE_NOTES = {
    "comparable_sales": (
        "Comparable sales data sourced from county records or third-party provider."
    ),
    "tax_assessment_fallback": (
        "No comparable sales data available. Base value derived from county "
        "tax assessment record. Automated comparable sales require a paid API "
        "subscription (Zillow Zestimate API deprecated 2021; MLS data not public)."
    ),
}


class ValuationReport:
    """
    Generates a Markdown report for a completed property valuation.

    Args:
        property_:       Subject property.
        spatial_factors: Extracted spatial scores.
        market_data:     Market data result.
        valuation:       Valuation engine output.
    """

    def __init__(
        self,
        property_: Property,
        spatial_factors: SpatialFactors,
        market_data: MarketDataResult,
        valuation: ValuationResult,
    ) -> None:
        self._property = property_
        self._spatial = spatial_factors
        self._market = market_data
        self._valuation = valuation

    def to_markdown(self) -> str:
        """Render the report as a Markdown string."""
        sections: List[str] = [
            self._header(),
            self._property_section(),
            self._estimated_range_section(),
            self._spatial_factors_section(),
            self._comparable_sales_section(),
            self._data_sources_section(),
            self._disclaimer_section(),
        ]
        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _header(self) -> str:
        return (
            "# Property Valuation Screening Report\n\n"
            f"**Address:** {self._property.address}"
        )

    def _property_section(self) -> str:
        p = self._property
        lines = ["## Property Details", ""]
        lines.append(f"- **Address:** {p.address}")
        lines.append(f"- **Coordinates:** {p.lat:.5f}, {p.lon:.5f}")
        if p.county:
            lines.append(f"- **County:** {p.county}, {p.state}")
        if p.property_type:
            lines.append(f"- **Property Type:** {p.property_type.value.title()}")
        if p.building_sqft:
            lines.append(f"- **Building Size:** {p.building_sqft:,} sq ft")
        if p.lot_size_sqft:
            lines.append(f"- **Lot Size:** {p.lot_size_sqft:,} sq ft")
        if p.year_built:
            lines.append(f"- **Year Built:** {p.year_built}")
        if p.assessed_value:
            lines.append(
                f"- **Assessed Value:** ${p.assessed_value:,.0f}"
            )
        return "\n".join(lines)

    def _estimated_range_section(self) -> str:
        v = self._valuation
        lines = [
            "## Estimated Value Range",
            "",
            f"| | Amount |",
            f"|---|---|",
            f"| **Low** | ${v.estimated_value_low:,.0f} |",
            f"| **Mid** | ${v.estimated_value_mid:,.0f} |",
            f"| **High** | ${v.estimated_value_high:,.0f} |",
            "",
            f"- **Base Value:** ${v.base_value:,.0f}",
            f"- **Spatial Adjustment:** {v.spatial_adjustment_pct:+.1f}%",
            f"- **Confidence:** {v.confidence.title()}",
        ]
        return "\n".join(lines)

    def _spatial_factors_section(self) -> str:
        s = self._spatial
        lines = [
            "## Spatial Factors",
            "",
            f"**Composite Score:** {s.composite_score:.2f} / 1.00",
            "",
            "| Factor | Value | Score |",
            "|---|---|---|",
        ]

        rows = [
            (
                "Flood Zone",
                s.flood_zone.value,
                f"{s.flood_zone_score:.2f}",
            ),
            (
                "Traffic (AADT)",
                f"{s.traffic_aadt:,} ({s.traffic_level.value})",
                f"{s.traffic_score:.2f}",
            ),
            (
                "School Rating",
                f"{s.school_rating:.1f} / 10",
                f"{s.school_score:.2f}",
            ),
            (
                "Transit Distance",
                f"{s.transit_distance_m:,.0f} m",
                f"{s.transit_score:.2f}",
            ),
            (
                "Park Distance",
                f"{s.park_distance_m:,.0f} m",
                f"{s.park_score:.2f}",
            ),
            (
                "Commercial Distance",
                f"{s.commercial_distance_m:,.0f} m",
                f"{s.commercial_score:.2f}",
            ),
        ]

        for name, value, score in rows:
            lines.append(f"| {name} | {value} | {score} |")

        return "\n".join(lines)

    def _comparable_sales_section(self) -> str:
        comps = self._market.comparable_sales
        lines = ["## Comparable Sales", ""]

        if not comps:
            lines.append(
                "_No comparable sales available. "
                "See Data Sources section for limitations._"
            )
            return "\n".join(lines)

        if self._market.median_comp_price is not None:
            lines.append(
                f"**Median Sale Price:** ${self._market.median_comp_price:,.0f}"
            )
        if self._market.median_price_per_sqft is not None:
            lines.append(
                f"**Median Price / sq ft:** "
                f"${self._market.median_price_per_sqft:,.2f}"
            )
        lines.append("")
        lines.append("| Address | Sale Price | Sq Ft | $/Sq Ft | Distance |")
        lines.append("|---|---|---|---|---|")

        for comp in comps:
            psf = (
                f"${comp.price_per_sqft:,.2f}"
                if comp.price_per_sqft is not None
                else "N/A"
            )
            lines.append(
                f"| {comp.address} "
                f"| ${comp.sale_price:,.0f} "
                f"| {comp.building_sqft:,} "
                f"| {psf} "
                f"| {comp.distance_m:,.0f} m |"
            )

        return "\n".join(lines)

    def _data_sources_section(self) -> str:
        note = _DATA_SOURCE_NOTES.get(
            self._valuation.data_source,
            self._valuation.data_source,
        )
        lines = [
            "## Data Sources",
            "",
            f"**Valuation Data Source:** {self._valuation.data_source}",
            "",
            note,
            "",
            "**Spatial Data Sources:**",
            "- Geocoding: OpenStreetMap Nominatim (https://nominatim.openstreetmap.org)",
            "- Flood zone: FEMA National Flood Hazard Layer (NFHL) public API",
            "- Traffic: State DOT Annual Average Daily Traffic (AADT) data",
            "- School ratings: NCES school boundary data",
            "- Proximity factors: OpenStreetMap Overpass API",
        ]
        return "\n".join(lines)

    def _disclaimer_section(self) -> str:
        return (
            "## Disclaimer\n\n"
            f"> {self._valuation.disclaimer}"
        )
