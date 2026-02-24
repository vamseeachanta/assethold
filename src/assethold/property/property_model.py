"""
property_model.py — Core Property dataclass and supporting enumerations.

Represents a US real-property record with geographic coordinates,
physical attributes, and assessment data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PropertyType(Enum):
    """High-level property use classification."""

    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    LAND = "land"


class ZoningClass(Enum):
    """Common US zoning classifications (simplified)."""

    RESIDENTIAL_SINGLE = "R1"
    RESIDENTIAL_MULTI = "R2"
    COMMERCIAL = "C"
    INDUSTRIAL = "I"
    MIXED_USE = "MU"
    UNKNOWN = "UNKNOWN"


@dataclass
class Property:
    """
    A US real-property record.

    Required fields: address, lat, lon.
    All other fields are optional and populated from assessor / GIS data.
    """

    address: str
    lat: float
    lon: float

    # Assessor / parcel fields
    parcel_id: Optional[str] = None
    zoning: Optional[ZoningClass] = None
    lot_size_sqft: Optional[int] = None
    building_sqft: Optional[int] = None
    property_type: PropertyType = PropertyType.RESIDENTIAL
    year_built: Optional[int] = None
    assessed_value: Optional[float] = None

    # Geographic context
    county: Optional[str] = None
    state: Optional[str] = None

    def __post_init__(self) -> None:
        self._validate()

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        if not self.address or not self.address.strip():
            raise ValueError("address must be a non-empty string")

        if not (-90.0 <= self.lat <= 90.0):
            raise ValueError(
                f"lat {self.lat} is out of range [-90, 90]"
            )

        if not (-180.0 <= self.lon <= 180.0):
            raise ValueError(
                f"lon {self.lon} is out of range [-180, 180]"
            )

        if self.building_sqft is not None and self.building_sqft < 0:
            raise ValueError(
                f"building_sqft must be non-negative, got {self.building_sqft}"
            )

        if self.assessed_value is not None and self.assessed_value < 0:
            raise ValueError(
                f"assessed_value must be non-negative, got {self.assessed_value}"
            )

    def __repr__(self) -> str:
        return (
            f"Property(address={self.address!r}, "
            f"lat={self.lat:.4f}, lon={self.lon:.4f}, "
            f"type={self.property_type.value})"
        )
