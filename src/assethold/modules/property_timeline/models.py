"""Core domain models for the property_timeline module.

DevelopmentChange — a single detected or recorded development event.
PropertyTimeline  — ordered collection of changes for one property.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional


@dataclass
class DevelopmentChange:
    """A single development event detected or recorded for a property.

    Attributes:
        change_date: Date of the event (or midpoint of detection window).
        change_type: Category string, e.g. "construction", "demolition",
            "vegetation_loss", "vegetation_gain", "road_expansion", "unknown".
        description: Human-readable narrative for the event.
        confidence: "high", "medium", or "low".
        magnitude: Change intensity (0.0–1.0).  Defaults to 0.0.
        area_sqm: Approximate affected area in square metres.
        source: Data source label, e.g. "satellite-ndvi", "permit", "osm".
        metadata: Arbitrary extra data (centroid, permit_id, etc.).
    """

    change_date: date
    change_type: str
    description: str
    confidence: str
    magnitude: float = 0.0
    area_sqm: float = 0.0
    source: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_date": self.change_date.isoformat(),
            "change_type": self.change_type,
            "description": self.description,
            "confidence": self.confidence,
            "magnitude": self.magnitude,
            "area_sqm": self.area_sqm,
            "source": self.source,
            "metadata": self.metadata,
        }


class PropertyTimeline:
    """Ordered collection of development changes for a single property.

    Args:
        property_id: Unique slug for the property (used for file naming).
        address: Human-readable address string.
    """

    def __init__(self, property_id: str, address: str) -> None:
        self.property_id = property_id
        self.address = address
        self._changes: List[DevelopmentChange] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def changes(self) -> List[DevelopmentChange]:
        """Chronologically sorted list of development changes."""
        return self._changes

    def add_change(self, change: DevelopmentChange) -> None:
        """Append a change and re-sort by date."""
        self._changes.append(change)
        self._changes.sort(key=lambda c: c.change_date)

    def changes_in_range(
        self, start: date, end: date
    ) -> List[DevelopmentChange]:
        """Return changes whose date falls within [start, end]."""
        return [c for c in self._changes if start <= c.change_date <= end]

    def type_summary(self) -> Dict[str, int]:
        """Return a dict mapping change_type -> count."""
        result: Dict[str, int] = {}
        for c in self._changes:
            result[c.change_type] = result.get(c.change_type, 0) + 1
        return result

    def to_dict(self) -> Dict[str, Any]:
        start = self._changes[0].change_date if self._changes else None
        end = self._changes[-1].change_date if self._changes else None
        return {
            "property_id": self.property_id,
            "address": self.address,
            "change_count": len(self._changes),
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat() if end else None,
            "changes": [c.to_dict() for c in self._changes],
        }
