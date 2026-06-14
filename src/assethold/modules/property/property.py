from __future__ import annotations

from assethold.modules.workflow_io import (
    record_outputs,
    section,
    write_json,
    write_text,
)
from assethold.property.market_data import ComparableSale, MarketDataResult
from assethold.property.property_model import Property, PropertyType, ZoningClass
from assethold.property.spatial_factors import FloodZone, SpatialFactors, TrafficLevel
from assethold.property.valuation import ValuationEngine
from assethold.property.valuation_report import ValuationReport


class PropertyWorkflow:
    """Run a deterministic property valuation screening report from cfg."""

    def router(self, cfg: dict) -> dict:
        settings = section(cfg, "property")
        outputs = settings["outputs"]

        property_ = self._property(settings["subject"])
        spatial = self._spatial_factors(settings["spatial_factors"])
        market = self._market_data(settings["market_data"])
        valuation = ValuationEngine().estimate(property_, spatial, market)
        markdown = ValuationReport(
            property_=property_,
            spatial_factors=spatial,
            market_data=market,
            valuation=valuation,
        ).to_markdown()

        report_file = write_text(outputs["report_md"], markdown)
        summary_file = write_json(outputs["summary_json"], valuation)
        return record_outputs(cfg, "property", [report_file, summary_file])

    def _property(self, data: dict) -> Property:
        zoning = data.get("zoning")
        return Property(
            address=str(data["address"]),
            lat=float(data["lat"]),
            lon=float(data["lon"]),
            parcel_id=data.get("parcel_id"),
            zoning=ZoningClass(zoning) if zoning else None,
            lot_size_sqft=data.get("lot_size_sqft"),
            building_sqft=data.get("building_sqft"),
            property_type=PropertyType(data.get("property_type", "residential")),
            year_built=data.get("year_built"),
            assessed_value=data.get("assessed_value"),
            county=data.get("county"),
            state=data.get("state"),
        )

    def _spatial_factors(self, data: dict) -> SpatialFactors:
        return SpatialFactors(
            flood_zone=FloodZone(data["flood_zone"]),
            flood_zone_score=float(data["flood_zone_score"]),
            traffic_aadt=int(data["traffic_aadt"]),
            traffic_level=TrafficLevel(data["traffic_level"]),
            traffic_score=float(data["traffic_score"]),
            school_rating=float(data["school_rating"]),
            school_score=float(data["school_score"]),
            transit_distance_m=float(data["transit_distance_m"]),
            transit_score=float(data["transit_score"]),
            park_distance_m=float(data["park_distance_m"]),
            park_score=float(data["park_score"]),
            commercial_distance_m=float(data["commercial_distance_m"]),
            commercial_score=float(data["commercial_score"]),
            composite_score=float(data["composite_score"]),
        )

    def _market_data(self, data: dict) -> MarketDataResult:
        comps = [
            ComparableSale(
                address=str(comp["address"]),
                lat=float(comp["lat"]),
                lon=float(comp["lon"]),
                sale_price=float(comp["sale_price"]),
                sale_date=str(comp["sale_date"]),
                building_sqft=int(comp["building_sqft"]),
                distance_m=float(comp["distance_m"]),
            )
            for comp in data.get("comparable_sales", [])
        ]
        return MarketDataResult(
            assessed_value=data.get("assessed_value"),
            comparable_sales=comps,
            median_comp_price=data.get("median_comp_price"),
            median_price_per_sqft=data.get("median_price_per_sqft"),
            data_source=str(data["data_source"]),
            county_supported=bool(data["county_supported"]),
        )
