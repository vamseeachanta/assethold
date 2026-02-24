"""
Property valuation analysis module.

Provides GIS-based spatial factor extraction and screening-level
value range estimation for US properties.

NOTE: Output is an estimated range for screening purposes only.
It is NOT a certified appraisal.

Supported counties (initial version):
  - Harris County, TX
  - Los Angeles County, CA
  - Cook County, IL
"""

from assethold.property.property_model import Property, PropertyType, ZoningClass
from assethold.property.geocoder import Geocoder, GeocoderResult, GeocodeError
from assethold.property.spatial_factors import (
    SpatialFactorExtractor,
    SpatialFactors,
    FloodZone,
    TrafficLevel,
)
from assethold.property.market_data import (
    MarketDataProvider,
    ComparableSale,
    MarketDataResult,
    MarketDataError,
)
from assethold.property.valuation import ValuationEngine, ValuationResult, ValuationError
from assethold.property.valuation_report import ValuationReport

__all__ = [
    "Property",
    "PropertyType",
    "ZoningClass",
    "Geocoder",
    "GeocoderResult",
    "GeocodeError",
    "SpatialFactorExtractor",
    "SpatialFactors",
    "FloodZone",
    "TrafficLevel",
    "MarketDataProvider",
    "ComparableSale",
    "MarketDataResult",
    "MarketDataError",
    "ValuationEngine",
    "ValuationResult",
    "ValuationError",
    "ValuationReport",
]
