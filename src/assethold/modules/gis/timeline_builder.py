"""Timeline builder: assemble historical development milestones for a property.

Combines change detection events, permit data, and OSM building footprint
counts into a chronologically ordered development timeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from assethold.modules.gis.change_detector import ChangeEvent, ChangeType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DevelopmentMilestone:
    """A single dated event in a property's development timeline.

    Attributes:
        event_date: Date (or approximate date) of the milestone.
        title: Short title, e.g. "New retail centre opened".
        description: Detailed narrative description.
        source: Data source, e.g. "satellite-ndvi", "permit", "osm".
        change_type: Optional ChangeType classification.
        confidence: "high", "medium", or "low".
        metadata: Arbitrary additional data for report generation.
    """

    event_date: date
    title: str
    description: str
    source: str
    change_type: Optional[ChangeType] = None
    confidence: str = "medium"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_date": self.event_date.isoformat(),
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "change_type": self.change_type.value if self.change_type else None,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class DevelopmentTimeline:
    """Ordered collection of development milestones for a property.

    Attributes:
        property_id: Unique property slug.
        address: Human-readable address.
        milestones: Chronologically sorted list of milestones.
        start_date: Earliest date covered by the timeline.
        end_date: Latest date covered by the timeline.
    """

    property_id: str
    address: str
    milestones: List[DevelopmentMilestone] = field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    def add_milestone(self, milestone: DevelopmentMilestone) -> None:
        """Append a milestone and keep the list sorted by date."""
        self.milestones.append(milestone)
        self.milestones.sort(key=lambda m: m.event_date)

    def milestones_in_range(self, start: date, end: date) -> List[DevelopmentMilestone]:
        """Return milestones whose dates fall within [start, end]."""
        return [m for m in self.milestones if start <= m.event_date <= end]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "property_id": self.property_id,
            "address": self.address,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "milestone_count": len(self.milestones),
            "milestones": [m.to_dict() for m in self.milestones],
        }


# ---------------------------------------------------------------------------
# Timeline builder
# ---------------------------------------------------------------------------


class TimelineBuilder:
    """Assemble a DevelopmentTimeline from multiple data sources.

    Args:
        property_id: Unique slug for the property being analysed.
        address: Human-readable address string.
    """

    def __init__(self, property_id: str, address: str) -> None:
        self.property_id = property_id
        self.address = address
        self._timeline = DevelopmentTimeline(
            property_id=property_id,
            address=address,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_change_events(self, events: List[ChangeEvent]) -> None:
        """Ingest a list of ChangeEvent objects as timeline milestones.

        Args:
            events: Output from ChangeDetector.detect_from_arrays() or
                    ChangeDetector.detect_from_rasters().
        """
        for event in events:
            title = self._title_for_change(event)
            milestone = DevelopmentMilestone(
                event_date=event.to_date,
                title=title,
                description=event.description,
                source="satellite-ndvi",
                change_type=event.change_type,
                confidence=event.confidence,
                metadata={
                    "magnitude": event.magnitude,
                    "area_sqm": event.area_sqm,
                    "from_date": event.from_date.isoformat(),
                },
            )
            self._timeline.add_milestone(milestone)
        logger.debug(
            "Added %d change events to timeline for '%s'",
            len(events),
            self.property_id,
        )

    def add_permit_data(self, permits: List[Dict[str, Any]]) -> None:
        """Ingest permit records as timeline milestones.

        Each permit dict is expected to have at minimum:
          - ``issue_date``: ISO-format date string or date object
          - ``description``: Permit description
          - ``permit_type``: e.g. "new_construction", "demolition", "renovation"

        Args:
            permits: List of permit record dicts from local open data sources.
        """
        for permit in permits:
            raw_date = permit.get("issue_date")
            if raw_date is None:
                continue
            if isinstance(raw_date, str):
                event_date = date.fromisoformat(raw_date)
            else:
                event_date = raw_date

            permit_type = permit.get("permit_type", "unknown")
            milestone = DevelopmentMilestone(
                event_date=event_date,
                title=f"Permit filed: {permit_type.replace('_', ' ').title()}",
                description=permit.get("description", ""),
                source="permit",
                change_type=self._change_type_for_permit(permit_type),
                confidence="high",
                metadata=permit,
            )
            self._timeline.add_milestone(milestone)
        logger.debug(
            "Added %d permit records to timeline for '%s'",
            len(permits),
            self.property_id,
        )

    def add_osm_building_counts(
        self,
        counts: List[Dict[str, Any]],
    ) -> None:
        """Ingest historical OSM building footprint counts as milestones.

        Each dict is expected to have:
          - ``year``: Integer year
          - ``building_count``: Integer count of building footprints

        Converts significant year-over-year changes into milestone events.

        Args:
            counts: List of {year, building_count} dicts in chronological order.
        """
        if len(counts) < 2:
            return

        sorted_counts = sorted(counts, key=lambda c: c["year"])
        for i in range(1, len(sorted_counts)):
            prev = sorted_counts[i - 1]
            curr = sorted_counts[i]
            delta = curr["building_count"] - prev["building_count"]
            if abs(delta) < 3:  # ignore noise
                continue

            direction = "increased" if delta > 0 else "decreased"
            event_date = date(curr["year"], 1, 1)
            milestone = DevelopmentMilestone(
                event_date=event_date,
                title=(
                    f"Building count {direction} by {abs(delta)} "
                    f"({prev['year']}→{curr['year']})"
                ),
                description=(
                    f"OSM building footprints {direction} from "
                    f"{prev['building_count']} to {curr['building_count']} "
                    f"between {prev['year']} and {curr['year']}."
                ),
                source="osm-ohsome",
                change_type=(
                    ChangeType.CONSTRUCTION if delta > 0 else ChangeType.DEMOLITION
                ),
                confidence="medium",
                metadata={
                    "prev_year": prev["year"],
                    "prev_count": prev["building_count"],
                    "curr_year": curr["year"],
                    "curr_count": curr["building_count"],
                    "delta": delta,
                },
            )
            self._timeline.add_milestone(milestone)

    def build(self) -> DevelopmentTimeline:
        """Return the assembled DevelopmentTimeline.

        Sets start_date and end_date from the milestone range.
        """
        if self._timeline.milestones:
            self._timeline.start_date = self._timeline.milestones[0].event_date
            self._timeline.end_date = self._timeline.milestones[-1].event_date
        return self._timeline

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _title_for_change(event: ChangeEvent) -> str:
        """Derive a short human-readable title from a ChangeEvent."""
        type_labels = {
            ChangeType.VEGETATION_LOSS: "Development activity detected",
            ChangeType.VEGETATION_GAIN: "Vegetation/landscaping increase",
            ChangeType.CONSTRUCTION: "New construction",
            ChangeType.DEMOLITION: "Demolition",
            ChangeType.ROAD_EXPANSION: "Road expansion",
            ChangeType.UNKNOWN: "Change detected",
        }
        return type_labels.get(event.change_type, "Change detected")

    @staticmethod
    def _change_type_for_permit(permit_type: str) -> Optional[ChangeType]:
        """Map a permit type string to a ChangeType enum value."""
        mapping = {
            "new_construction": ChangeType.CONSTRUCTION,
            "demolition": ChangeType.DEMOLITION,
            "road": ChangeType.ROAD_EXPANSION,
        }
        return mapping.get(permit_type.lower())
