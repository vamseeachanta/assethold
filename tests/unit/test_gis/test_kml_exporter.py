"""Unit tests for the KMLExporter module.

Tests KML string generation (no simplekml dep), TimeSpan element presence,
placemark structure, and export behaviour.
"""

from __future__ import annotations

import zipfile
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from assethold.modules.gis.change_detector import ChangeType
from assethold.modules.gis.kml_exporter import KMLExporter, _COLOUR_MILESTONE_HIGH
from assethold.modules.gis.timeline_builder import DevelopmentMilestone, DevelopmentTimeline

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def exporter(tmp_path) -> KMLExporter:
    return KMLExporter(output_dir=str(tmp_path))


@pytest.fixture
def sample_timeline() -> DevelopmentTimeline:
    tl = DevelopmentTimeline(
        property_id="prop-001",
        address="1 Main St, Houston, TX",
        start_date=date(2000, 1, 1),
        end_date=date(2020, 1, 1),
    )
    tl.milestones = [
        DevelopmentMilestone(
            event_date=date(2005, 6, 1),
            title="Construction wave",
            description="New residential subdivision built.",
            source="satellite-ndvi",
            change_type=ChangeType.CONSTRUCTION,
            confidence="high",
            metadata={"centroid": (29.76, -95.37)},
        ),
        DevelopmentMilestone(
            event_date=date(2015, 3, 15),
            title="Retail development",
            description="Strip mall constructed.",
            source="permit",
            change_type=ChangeType.CONSTRUCTION,
            confidence="medium",
            metadata={"centroid": (29.77, -95.38)},
        ),
    ]
    return tl


# ---------------------------------------------------------------------------
# KML string generation tests (no simplekml dep)
# ---------------------------------------------------------------------------


class TestKmlStringGeneration:
    def test_export_milestones_kml_string_is_valid_xml(
        self, exporter: KMLExporter, sample_timeline: DevelopmentTimeline
    ) -> None:
        import xml.etree.ElementTree as ET

        kml_str = exporter.export_milestones_kml_string(sample_timeline.milestones)
        # Should not raise ParseError
        ET.fromstring(kml_str)

    def test_kml_string_contains_kml_namespace(
        self, exporter: KMLExporter, sample_timeline: DevelopmentTimeline
    ) -> None:
        kml_str = exporter.export_milestones_kml_string(sample_timeline.milestones)
        assert "http://www.opengis.net/kml/2.2" in kml_str

    def test_kml_string_contains_placemark_for_each_milestone(
        self, exporter: KMLExporter, sample_timeline: DevelopmentTimeline
    ) -> None:
        kml_str = exporter.export_milestones_kml_string(sample_timeline.milestones)
        assert kml_str.count("<Placemark>") == len(sample_timeline.milestones)

    def test_kml_string_contains_timespan_elements(
        self, exporter: KMLExporter, sample_timeline: DevelopmentTimeline
    ) -> None:
        kml_str = exporter.export_milestones_kml_string(sample_timeline.milestones)
        assert kml_str.count("<TimeSpan>") == len(sample_timeline.milestones)

    def test_kml_string_contains_begin_dates(
        self, exporter: KMLExporter, sample_timeline: DevelopmentTimeline
    ) -> None:
        kml_str = exporter.export_milestones_kml_string(sample_timeline.milestones)
        assert "2005-06-01" in kml_str
        assert "2015-03-15" in kml_str

    def test_kml_string_contains_milestone_titles(
        self, exporter: KMLExporter, sample_timeline: DevelopmentTimeline
    ) -> None:
        kml_str = exporter.export_milestones_kml_string(sample_timeline.milestones)
        assert "Construction wave" in kml_str
        assert "Retail development" in kml_str

    def test_kml_string_contains_coordinate_elements(
        self, exporter: KMLExporter, sample_timeline: DevelopmentTimeline
    ) -> None:
        kml_str = exporter.export_milestones_kml_string(sample_timeline.milestones)
        assert "<coordinates>" in kml_str

    def test_kml_empty_milestones_produces_valid_document(
        self, exporter: KMLExporter
    ) -> None:
        import xml.etree.ElementTree as ET

        kml_str = exporter.export_milestones_kml_string([])
        ET.fromstring(kml_str)  # should not raise


# ---------------------------------------------------------------------------
# Colour mapping tests
# ---------------------------------------------------------------------------


class TestColourForConfidence:
    def test_high_confidence_maps_to_red(self, exporter: KMLExporter) -> None:
        colour = exporter._colour_for_confidence("high")
        assert colour == _COLOUR_MILESTONE_HIGH

    def test_unknown_confidence_maps_to_medium_colour(
        self, exporter: KMLExporter
    ) -> None:
        colour = exporter._colour_for_confidence("unknown_value")
        assert colour is not None
        assert len(colour) == 8  # AABBGGRR format

    def test_all_confidence_levels_return_eight_char_string(
        self, exporter: KMLExporter
    ) -> None:
        for level in ("high", "medium", "low"):
            colour = exporter._colour_for_confidence(level)
            assert len(colour) == 8


# ---------------------------------------------------------------------------
# Milestone placemark XML tests
# ---------------------------------------------------------------------------


class TestMilestonePlacemarkXml:
    def test_placemark_xml_contains_name(self) -> None:
        m = DevelopmentMilestone(
            event_date=date(2010, 5, 1),
            title="Test Title",
            description="Test description.",
            source="test",
            metadata={"centroid": (29.76, -95.37)},
        )
        xml_str = KMLExporter._milestone_placemark_xml(m)
        assert "Test Title" in xml_str

    def test_placemark_xml_contains_begin_date(self) -> None:
        m = DevelopmentMilestone(
            event_date=date(2010, 5, 1),
            title="T",
            description="D",
            source="s",
            metadata={"centroid": (0.0, 0.0)},
        )
        xml_str = KMLExporter._milestone_placemark_xml(m)
        assert "2010-05-01" in xml_str

    def test_placemark_xml_uses_lon_lat_order_in_coordinates(self) -> None:
        """KML coordinates are lon,lat,elevation."""
        m = DevelopmentMilestone(
            event_date=date(2010, 5, 1),
            title="T",
            description="D",
            source="s",
            metadata={"centroid": (29.76, -95.37)},
        )
        xml_str = KMLExporter._milestone_placemark_xml(m)
        # Coordinates should be lon,lat → -95.37,29.76,0
        assert "-95.37,29.76,0" in xml_str


# ---------------------------------------------------------------------------
# Export to KMZ (mocked simplekml)
# ---------------------------------------------------------------------------


class TestKmlExportKmz:
    def test_export_returns_none_when_simplekml_missing(
        self, exporter: KMLExporter, sample_timeline: DevelopmentTimeline
    ) -> None:
        import sys

        with patch.dict(sys.modules, {"simplekml": None}):
            result = exporter.export(sample_timeline)
        assert result is None

    def test_export_calls_simplekml_kml_constructor(
        self, exporter: KMLExporter, sample_timeline: DevelopmentTimeline
    ) -> None:
        mock_kml_instance = MagicMock()
        mock_kml_instance.kml.return_value = (
            '<?xml version="1.0"?><kml></kml>'
        )
        mock_kml_cls = MagicMock(return_value=mock_kml_instance)
        mock_simplekml = MagicMock()
        mock_simplekml.Kml = mock_kml_cls

        with patch.dict("sys.modules", {"simplekml": mock_simplekml}):
            result = exporter.export(sample_timeline)

        mock_kml_cls.assert_called_once()
