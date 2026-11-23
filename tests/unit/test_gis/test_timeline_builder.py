"""Unit tests for the TimelineBuilder module.

Verifies chronological ordering, milestone ingestion from change events,
permit records, and OSM building counts.
"""

from __future__ import annotations

from datetime import date

import pytest

from assethold.modules.gis.change_detector import ChangeEvent, ChangeType
from assethold.modules.gis.timeline_builder import (
    DevelopmentMilestone,
    DevelopmentTimeline,
    TimelineBuilder,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def builder() -> TimelineBuilder:
    return TimelineBuilder(property_id="test-property-001", address="123 Main St")


@pytest.fixture
def vegetation_loss_event() -> ChangeEvent:
    return ChangeEvent(
        change_type=ChangeType.VEGETATION_LOSS,
        from_date=date(2000, 7, 1),
        to_date=date(2005, 7, 1),
        magnitude=0.45,
        area_sqm=27000.0,
        centroid=(29.76, -95.37),
        description="Vegetation loss detected over 2.70 ha.",
        confidence="high",
    )


@pytest.fixture
def vegetation_gain_event() -> ChangeEvent:
    return ChangeEvent(
        change_type=ChangeType.VEGETATION_GAIN,
        from_date=date(2005, 7, 1),
        to_date=date(2010, 7, 1),
        magnitude=0.12,
        area_sqm=10800.0,
        centroid=(29.76, -95.37),
        description="Vegetation gain.",
        confidence="medium",
    )


@pytest.fixture
def permit_records() -> list:
    return [
        {
            "issue_date": "2003-04-15",
            "permit_type": "new_construction",
            "description": "Commercial retail development, 3 buildings",
        },
        {
            "issue_date": "2008-11-01",
            "permit_type": "renovation",
            "description": "Facade renovation",
        },
        {
            "issue_date": "2012-06-20",
            "permit_type": "demolition",
            "description": "Old warehouse demolished",
        },
    ]


@pytest.fixture
def osm_building_counts() -> list:
    return [
        {"year": 2010, "building_count": 20},
        {"year": 2012, "building_count": 35},
        {"year": 2014, "building_count": 42},
        {"year": 2016, "building_count": 42},  # no change — should not produce event
        {"year": 2018, "building_count": 55},
    ]


# ---------------------------------------------------------------------------
# DevelopmentMilestone tests
# ---------------------------------------------------------------------------


class TestDevelopmentMilestone:
    def test_to_dict_contains_required_keys(self) -> None:
        m = DevelopmentMilestone(
            event_date=date(2005, 1, 1),
            title="Test event",
            description="A test",
            source="test",
        )
        d = m.to_dict()
        assert "event_date" in d
        assert "title" in d
        assert "description" in d
        assert "source" in d
        assert "confidence" in d

    def test_to_dict_change_type_is_string_or_none(self) -> None:
        m = DevelopmentMilestone(
            event_date=date(2005, 1, 1),
            title="Event",
            description="Desc",
            source="test",
            change_type=ChangeType.CONSTRUCTION,
        )
        assert isinstance(m.to_dict()["change_type"], str)

    def test_to_dict_no_change_type_is_none(self) -> None:
        m = DevelopmentMilestone(
            event_date=date(2005, 1, 1),
            title="Event",
            description="Desc",
            source="test",
        )
        assert m.to_dict()["change_type"] is None


# ---------------------------------------------------------------------------
# DevelopmentTimeline tests
# ---------------------------------------------------------------------------


class TestDevelopmentTimeline:
    def test_add_milestone_keeps_chronological_order(self) -> None:
        tl = DevelopmentTimeline(property_id="p1", address="1 Main St")
        tl.add_milestone(
            DevelopmentMilestone(
                event_date=date(2010, 1, 1), title="Later", description="", source="x"
            )
        )
        tl.add_milestone(
            DevelopmentMilestone(
                event_date=date(2000, 1, 1), title="Earlier", description="", source="x"
            )
        )
        assert tl.milestones[0].event_date == date(2000, 1, 1)
        assert tl.milestones[1].event_date == date(2010, 1, 1)

    def test_milestones_in_range_filters_correctly(self) -> None:
        tl = DevelopmentTimeline(property_id="p1", address="1 Main St")
        for year in [2000, 2005, 2010, 2015]:
            tl.add_milestone(
                DevelopmentMilestone(
                    event_date=date(year, 1, 1),
                    title=f"Event {year}",
                    description="",
                    source="test",
                )
            )
        in_range = tl.milestones_in_range(date(2005, 1, 1), date(2012, 1, 1))
        years_in_range = [m.event_date.year for m in in_range]
        assert years_in_range == [2005, 2010]

    def test_to_dict_milestone_count_matches(self) -> None:
        tl = DevelopmentTimeline(property_id="p1", address="1 Main St")
        for year in [2000, 2005]:
            tl.add_milestone(
                DevelopmentMilestone(
                    event_date=date(year, 1, 1), title="E", description="", source="x"
                )
            )
        d = tl.to_dict()
        assert d["milestone_count"] == 2
        assert len(d["milestones"]) == 2


# ---------------------------------------------------------------------------
# TimelineBuilder tests
# ---------------------------------------------------------------------------


class TestTimelineBuilder:
    def test_add_change_events_creates_milestones(
        self,
        builder: TimelineBuilder,
        vegetation_loss_event: ChangeEvent,
    ) -> None:
        builder.add_change_events([vegetation_loss_event])
        tl = builder.build()
        assert len(tl.milestones) == 1

    def test_add_change_events_sets_source_satellite(
        self,
        builder: TimelineBuilder,
        vegetation_loss_event: ChangeEvent,
    ) -> None:
        builder.add_change_events([vegetation_loss_event])
        tl = builder.build()
        assert tl.milestones[0].source == "satellite-ndvi"

    def test_add_change_events_preserves_change_type(
        self,
        builder: TimelineBuilder,
        vegetation_loss_event: ChangeEvent,
    ) -> None:
        builder.add_change_events([vegetation_loss_event])
        tl = builder.build()
        assert tl.milestones[0].change_type == ChangeType.VEGETATION_LOSS

    def test_add_permit_data_creates_milestones(
        self,
        builder: TimelineBuilder,
        permit_records: list,
    ) -> None:
        builder.add_permit_data(permit_records)
        tl = builder.build()
        assert len(tl.milestones) == 3

    def test_add_permit_data_sets_source_permit(
        self,
        builder: TimelineBuilder,
        permit_records: list,
    ) -> None:
        builder.add_permit_data(permit_records)
        tl = builder.build()
        assert all(m.source == "permit" for m in tl.milestones)

    def test_add_permit_data_skips_records_without_date(
        self, builder: TimelineBuilder
    ) -> None:
        permits = [
            {"permit_type": "new_construction", "description": "No date"},
        ]
        builder.add_permit_data(permits)
        tl = builder.build()
        assert len(tl.milestones) == 0

    def test_add_permit_data_new_construction_type(
        self, builder: TimelineBuilder
    ) -> None:
        permits = [
            {
                "issue_date": "2010-01-01",
                "permit_type": "new_construction",
                "description": "Building A",
            }
        ]
        builder.add_permit_data(permits)
        tl = builder.build()
        assert tl.milestones[0].change_type == ChangeType.CONSTRUCTION

    def test_add_osm_building_counts_generates_events(
        self,
        builder: TimelineBuilder,
        osm_building_counts: list,
    ) -> None:
        builder.add_osm_building_counts(osm_building_counts)
        tl = builder.build()
        # Should generate events for significant year-over-year changes
        # 2010→2012: +15 (event), 2012→2014: +7 (event),
        # 2014→2016: 0 (no event), 2016→2018: +13 (event)
        assert len(tl.milestones) == 3

    def test_add_osm_building_counts_no_events_for_single_entry(
        self, builder: TimelineBuilder
    ) -> None:
        builder.add_osm_building_counts([{"year": 2020, "building_count": 50}])
        tl = builder.build()
        assert len(tl.milestones) == 0

    def test_build_sets_start_and_end_dates(
        self,
        builder: TimelineBuilder,
        vegetation_loss_event: ChangeEvent,
        vegetation_gain_event: ChangeEvent,
    ) -> None:
        builder.add_change_events([vegetation_loss_event, vegetation_gain_event])
        tl = builder.build()
        assert tl.start_date == date(2005, 7, 1)  # to_date of first event
        assert tl.end_date == date(2010, 7, 1)    # to_date of second event

    def test_build_milestones_sorted_across_all_sources(
        self,
        builder: TimelineBuilder,
        vegetation_loss_event: ChangeEvent,
        permit_records: list,
        osm_building_counts: list,
    ) -> None:
        builder.add_change_events([vegetation_loss_event])
        builder.add_permit_data(permit_records)
        builder.add_osm_building_counts(osm_building_counts)
        tl = builder.build()
        dates = [m.event_date for m in tl.milestones]
        assert dates == sorted(dates)

    def test_build_returns_development_timeline_instance(
        self, builder: TimelineBuilder
    ) -> None:
        tl = builder.build()
        assert isinstance(tl, DevelopmentTimeline)
        assert tl.property_id == "test-property-001"
        assert tl.address == "123 Main St"
