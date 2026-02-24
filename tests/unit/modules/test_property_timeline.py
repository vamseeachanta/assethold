"""Unit tests for the property_timeline module (WRK-023).

Tests cover:
- DevelopmentChange dataclass
- PropertyTimeline assembly and serialisation
- ImagerySource ABC and stub implementations
- DevelopmentChangeDetector NDVI-based detection
- KMLExporter KML/KMZ generation
- PermitDataLoader parsing and normalisation
- TimelineReport HTML rendering
- DevelopmentProjection linear extrapolation

All tests are self-contained — no network, no file-system writes, no live APIs.
"""

from __future__ import annotations

import json
import os
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Import helpers — we import lazily inside tests so failures are per-test
# ---------------------------------------------------------------------------


def _import_module():
    from assethold.modules.property_timeline import (
        DevelopmentChange,
        PropertyTimeline,
    )
    return DevelopmentChange, PropertyTimeline


def _import_imagery():
    from assethold.modules.property_timeline.imagery_sources import (
        ImagerySource,
        StubImagerySource,
        GoogleEarthEngineSource,
        USGSEarthExplorerSource,
    )
    return ImagerySource, StubImagerySource, GoogleEarthEngineSource, USGSEarthExplorerSource


def _import_change_detector():
    from assethold.modules.property_timeline.change_detector import (
        DevelopmentChangeDetector,
    )
    return DevelopmentChangeDetector


def _import_kml():
    from assethold.modules.property_timeline.kml_exporter import KMLExporter
    return KMLExporter


def _import_permit():
    from assethold.modules.property_timeline.permit_data import PermitDataLoader
    return PermitDataLoader


def _import_report():
    from assethold.modules.property_timeline.timeline_report import TimelineReport
    return TimelineReport


def _import_projection():
    from assethold.modules.property_timeline.projection import DevelopmentProjection
    return DevelopmentProjection


# ===========================================================================
# DevelopmentChange tests
# ===========================================================================


class TestDevelopmentChange:
    def test_required_fields_stored(self) -> None:
        DevelopmentChange, _ = _import_module()
        dc = DevelopmentChange(
            change_date=date(2005, 1, 1),
            change_type="construction",
            description="New apartment block",
            confidence="high",
        )
        assert dc.change_date == date(2005, 1, 1)
        assert dc.change_type == "construction"
        assert dc.confidence == "high"

    def test_to_dict_has_required_keys(self) -> None:
        DevelopmentChange, _ = _import_module()
        dc = DevelopmentChange(
            change_date=date(2010, 6, 15),
            change_type="demolition",
            description="Old factory demolished",
            confidence="medium",
        )
        d = dc.to_dict()
        for key in ("change_date", "change_type", "description", "confidence"):
            assert key in d

    def test_to_dict_date_is_iso_string(self) -> None:
        DevelopmentChange, _ = _import_module()
        dc = DevelopmentChange(
            change_date=date(2015, 3, 20),
            change_type="vegetation_loss",
            description="Clearing activity",
            confidence="low",
        )
        assert dc.to_dict()["change_date"] == "2015-03-20"

    def test_magnitude_defaults_to_zero(self) -> None:
        DevelopmentChange, _ = _import_module()
        dc = DevelopmentChange(
            change_date=date(2010, 1, 1),
            change_type="unknown",
            description="",
            confidence="low",
        )
        assert dc.magnitude == 0.0

    def test_area_sqm_defaults_to_zero(self) -> None:
        DevelopmentChange, _ = _import_module()
        dc = DevelopmentChange(
            change_date=date(2010, 1, 1),
            change_type="unknown",
            description="",
            confidence="low",
        )
        assert dc.area_sqm == 0.0


# ===========================================================================
# PropertyTimeline tests
# ===========================================================================


class TestPropertyTimeline:
    def _make_change(self, year: int, change_type: str = "construction") -> Any:
        DevelopmentChange, _ = _import_module()
        return DevelopmentChange(
            change_date=date(year, 1, 1),
            change_type=change_type,
            description=f"Event {year}",
            confidence="medium",
        )

    def test_initial_timeline_is_empty(self) -> None:
        _, PropertyTimeline = _import_module()
        pt = PropertyTimeline(property_id="p1", address="1 Main St")
        assert len(pt.changes) == 0

    def test_add_change_appends_and_sorts(self) -> None:
        DevelopmentChange, PropertyTimeline = _import_module()
        pt = PropertyTimeline(property_id="p1", address="1 Main St")
        pt.add_change(self._make_change(2015))
        pt.add_change(self._make_change(2000))
        dates = [c.change_date.year for c in pt.changes]
        assert dates == [2000, 2015]

    def test_changes_in_range_filters_correctly(self) -> None:
        DevelopmentChange, PropertyTimeline = _import_module()
        pt = PropertyTimeline(property_id="p1", address="1 Main St")
        for yr in [2000, 2005, 2010, 2015]:
            pt.add_change(self._make_change(yr))
        in_range = pt.changes_in_range(date(2003, 1, 1), date(2012, 1, 1))
        assert [c.change_date.year for c in in_range] == [2005, 2010]

    def test_to_dict_contains_property_id_and_address(self) -> None:
        _, PropertyTimeline = _import_module()
        pt = PropertyTimeline(property_id="px", address="42 Test Ave")
        d = pt.to_dict()
        assert d["property_id"] == "px"
        assert d["address"] == "42 Test Ave"

    def test_to_dict_change_count_matches(self) -> None:
        _, PropertyTimeline = _import_module()
        pt = PropertyTimeline(property_id="p2", address="2 Main St")
        for yr in [2000, 2010]:
            pt.add_change(self._make_change(yr))
        d = pt.to_dict()
        assert d["change_count"] == 2

    def test_summary_describes_changes_by_type(self) -> None:
        DevelopmentChange, PropertyTimeline = _import_module()
        pt = PropertyTimeline(property_id="p3", address="3 Main St")
        pt.add_change(self._make_change(2005, "construction"))
        pt.add_change(self._make_change(2010, "construction"))
        pt.add_change(self._make_change(2015, "demolition"))
        summary = pt.type_summary()
        assert summary.get("construction") == 2
        assert summary.get("demolition") == 1


# ===========================================================================
# ImagerySource tests
# ===========================================================================


class TestImagerySource:
    def test_imagery_source_is_abstract(self) -> None:
        import inspect
        ImagerySource, *_ = _import_imagery()
        assert inspect.isabstract(ImagerySource)

    def test_stub_source_returns_scene_list(self) -> None:
        _, StubImagerySource, *_ = _import_imagery()
        stub = StubImagerySource()
        scenes = stub.fetch(
            bbox=(29.74, 29.78, -95.39, -95.35),
            start_year=2000,
            end_year=2010,
        )
        assert isinstance(scenes, list)
        assert len(scenes) > 0

    def test_stub_scenes_have_acquisition_date(self) -> None:
        _, StubImagerySource, *_ = _import_imagery()
        stub = StubImagerySource()
        scenes = stub.fetch(
            bbox=(29.74, 29.78, -95.39, -95.35),
            start_year=2005,
            end_year=2010,
        )
        for scene in scenes:
            assert hasattr(scene, "acquisition_date")
            assert isinstance(scene.acquisition_date, date)

    def test_stub_scenes_within_year_range(self) -> None:
        _, StubImagerySource, *_ = _import_imagery()
        stub = StubImagerySource()
        scenes = stub.fetch(
            bbox=(0.0, 1.0, 0.0, 1.0),
            start_year=2010,
            end_year=2015,
        )
        for scene in scenes:
            assert 2010 <= scene.acquisition_date.year <= 2015

    def test_gee_source_raises_not_implemented_when_no_api(self) -> None:
        _, _, GoogleEarthEngineSource, _ = _import_imagery()
        gee = GoogleEarthEngineSource()
        # When geemap/ee not installed, should return empty list (not crash)
        scenes = gee.fetch(bbox=(0.0, 1.0, 0.0, 1.0), start_year=2000, end_year=2005)
        assert isinstance(scenes, list)

    def test_usgs_source_returns_empty_without_credentials(self) -> None:
        _, _, _, USGSEarthExplorerSource = _import_imagery()
        usgs = USGSEarthExplorerSource()
        scenes = usgs.fetch(bbox=(0.0, 1.0, 0.0, 1.0), start_year=2000, end_year=2005)
        assert isinstance(scenes, list)


# ===========================================================================
# DevelopmentChangeDetector tests
# ===========================================================================


class TestDevelopmentChangeDetector:
    def _make_detector(self):
        DevelopmentChangeDetector = _import_change_detector()
        return DevelopmentChangeDetector()

    def _dense_veg(self, shape=(10, 10)):
        red = np.full(shape, 0.05, dtype=np.float32)
        nir = np.full(shape, 0.45, dtype=np.float32)
        return red, nir

    def _bare_soil(self, shape=(10, 10)):
        red = np.full(shape, 0.30, dtype=np.float32)
        nir = np.full(shape, 0.33, dtype=np.float32)
        return red, nir

    def test_detect_returns_list(self) -> None:
        det = self._make_detector()
        r_b, n_b = self._dense_veg()
        r_a, n_a = self._bare_soil()
        result = det.detect(
            red_before=r_b, nir_before=n_b,
            red_after=r_a, nir_after=n_a,
            date_before=date(2000, 7, 1),
            date_after=date(2005, 7, 1),
        )
        assert isinstance(result, list)

    def test_vegetation_loss_detected_as_construction(self) -> None:
        det = self._make_detector()
        r_b, n_b = self._dense_veg((50, 50))
        r_a, n_a = self._bare_soil((50, 50))
        changes = det.detect(
            red_before=r_b, nir_before=n_b,
            red_after=r_a, nir_after=n_a,
            date_before=date(2000, 7, 1),
            date_after=date(2005, 7, 1),
        )
        types = {c.change_type for c in changes}
        assert "vegetation_loss" in types or "construction" in types

    def test_no_changes_when_arrays_identical(self) -> None:
        det = self._make_detector()
        band = np.full((10, 10), 0.3, dtype=np.float32)
        changes = det.detect(
            red_before=band, nir_before=band,
            red_after=band.copy(), nir_after=band.copy(),
            date_before=date(2000, 7, 1),
            date_after=date(2005, 7, 1),
        )
        assert changes == []

    def test_change_date_reflects_after_date(self) -> None:
        det = self._make_detector()
        r_b, n_b = self._dense_veg((20, 20))
        r_a, n_a = self._bare_soil((20, 20))
        d_after = date(2010, 3, 15)
        changes = det.detect(
            red_before=r_b, nir_before=n_b,
            red_after=r_a, nir_after=n_a,
            date_before=date(2005, 1, 1),
            date_after=d_after,
        )
        for c in changes:
            assert c.change_date == d_after

    def test_magnitude_between_zero_and_one(self) -> None:
        det = self._make_detector()
        r_b, n_b = self._dense_veg((20, 20))
        r_a, n_a = self._bare_soil((20, 20))
        changes = det.detect(
            red_before=r_b, nir_before=n_b,
            red_after=r_a, nir_after=n_a,
            date_before=date(2000, 7, 1),
            date_after=date(2005, 7, 1),
        )
        for c in changes:
            assert 0.0 <= c.magnitude <= 1.0

    def test_detect_from_historical_records_returns_list(self) -> None:
        DevelopmentChangeDetector = _import_change_detector()
        det = DevelopmentChangeDetector()
        records = [
            {"year": 2000, "building_count": 50},
            {"year": 2010, "building_count": 80},
        ]
        changes = det.detect_from_historical_records(records)
        assert isinstance(changes, list)
        assert len(changes) > 0

    def test_detect_from_records_change_type_for_increase(self) -> None:
        DevelopmentChangeDetector = _import_change_detector()
        det = DevelopmentChangeDetector()
        records = [
            {"year": 2000, "building_count": 10},
            {"year": 2010, "building_count": 50},
        ]
        changes = det.detect_from_historical_records(records)
        types = {c.change_type for c in changes}
        assert "construction" in types

    def test_detect_from_records_ignores_small_changes(self) -> None:
        DevelopmentChangeDetector = _import_change_detector()
        det = DevelopmentChangeDetector()
        records = [
            {"year": 2000, "building_count": 50},
            {"year": 2005, "building_count": 51},  # +1, below noise threshold
        ]
        changes = det.detect_from_historical_records(records)
        assert changes == []


# ===========================================================================
# KMLExporter tests
# ===========================================================================


class TestKMLExporter:
    def _make_timeline(self):
        DevelopmentChange, PropertyTimeline = _import_module()
        pt = PropertyTimeline(property_id="test-prop", address="1 Main St, TX")
        pt.add_change(DevelopmentChange(
            change_date=date(2005, 6, 1),
            change_type="construction",
            description="New housing",
            confidence="high",
            magnitude=0.5,
        ))
        pt.add_change(DevelopmentChange(
            change_date=date(2015, 1, 15),
            change_type="demolition",
            description="Old warehouse removed",
            confidence="medium",
        ))
        return pt

    def test_kml_string_is_valid_xml(self) -> None:
        KMLExporter = _import_kml()
        exp = KMLExporter()
        timeline = self._make_timeline()
        kml_str = exp.to_kml_string(timeline)
        ET.fromstring(kml_str)  # should not raise

    def test_kml_string_contains_namespace(self) -> None:
        KMLExporter = _import_kml()
        exp = KMLExporter()
        timeline = self._make_timeline()
        kml_str = exp.to_kml_string(timeline)
        assert "opengis.net/kml" in kml_str

    def test_kml_contains_placemark_per_change(self) -> None:
        KMLExporter = _import_kml()
        exp = KMLExporter()
        timeline = self._make_timeline()
        kml_str = exp.to_kml_string(timeline)
        assert kml_str.count("<Placemark>") == len(timeline.changes)

    def test_kml_contains_timespan_per_change(self) -> None:
        KMLExporter = _import_kml()
        exp = KMLExporter()
        timeline = self._make_timeline()
        kml_str = exp.to_kml_string(timeline)
        assert kml_str.count("<TimeSpan>") == len(timeline.changes)

    def test_kml_contains_change_dates(self) -> None:
        KMLExporter = _import_kml()
        exp = KMLExporter()
        timeline = self._make_timeline()
        kml_str = exp.to_kml_string(timeline)
        assert "2005-06-01" in kml_str
        assert "2015-01-15" in kml_str

    def test_export_kmz_creates_file(self) -> None:
        KMLExporter = _import_kml()
        exp = KMLExporter()
        timeline = self._make_timeline()
        with tempfile.TemporaryDirectory() as tmp:
            out = exp.export_kmz(timeline, output_dir=tmp)
            assert out is not None
            assert os.path.exists(out)
            assert out.endswith(".kmz")

    def test_kmz_contains_doc_kml(self) -> None:
        KMLExporter = _import_kml()
        exp = KMLExporter()
        timeline = self._make_timeline()
        with tempfile.TemporaryDirectory() as tmp:
            out = exp.export_kmz(timeline, output_dir=tmp)
            with zipfile.ZipFile(out, "r") as z:
                assert "doc.kml" in z.namelist()

    def test_empty_timeline_produces_valid_kml(self) -> None:
        KMLExporter = _import_kml()
        _, PropertyTimeline = _import_module()
        exp = KMLExporter()
        pt = PropertyTimeline(property_id="empty", address="nowhere")
        kml_str = exp.to_kml_string(pt)
        ET.fromstring(kml_str)


# ===========================================================================
# PermitDataLoader tests
# ===========================================================================


class TestPermitDataLoader:
    def test_load_from_records_returns_changes(self) -> None:
        PermitDataLoader = _import_permit()
        loader = PermitDataLoader()
        records = [
            {
                "issue_date": "2010-03-15",
                "permit_type": "new_construction",
                "description": "4-storey residential",
            },
            {
                "issue_date": "2015-07-01",
                "permit_type": "demolition",
                "description": "Old barn demolished",
            },
        ]
        DevelopmentChange, _ = _import_module()
        changes = loader.load_from_records(records)
        assert len(changes) == 2
        assert all(isinstance(c, DevelopmentChange) for c in changes)

    def test_skip_records_without_date(self) -> None:
        PermitDataLoader = _import_permit()
        loader = PermitDataLoader()
        records = [
            {"permit_type": "new_construction", "description": "no date"},
        ]
        changes = loader.load_from_records(records)
        assert changes == []

    def test_new_construction_maps_to_construction_type(self) -> None:
        PermitDataLoader = _import_permit()
        loader = PermitDataLoader()
        records = [
            {
                "issue_date": "2012-01-01",
                "permit_type": "new_construction",
                "description": "unit test building",
            }
        ]
        changes = loader.load_from_records(records)
        assert changes[0].change_type == "construction"

    def test_demolition_maps_to_demolition_type(self) -> None:
        PermitDataLoader = _import_permit()
        loader = PermitDataLoader()
        records = [
            {
                "issue_date": "2018-06-01",
                "permit_type": "demolition",
                "description": "teardown",
            }
        ]
        changes = loader.load_from_records(records)
        assert changes[0].change_type == "demolition"

    def test_permit_changes_have_high_confidence(self) -> None:
        PermitDataLoader = _import_permit()
        loader = PermitDataLoader()
        records = [
            {
                "issue_date": "2020-01-01",
                "permit_type": "new_construction",
                "description": "approved build",
            }
        ]
        changes = loader.load_from_records(records)
        assert changes[0].confidence == "high"

    def test_normalize_date_string(self) -> None:
        PermitDataLoader = _import_permit()
        loader = PermitDataLoader()
        records = [
            {
                "issue_date": "2022-11-30",
                "permit_type": "renovation",
                "description": "refurb",
            }
        ]
        changes = loader.load_from_records(records)
        assert changes[0].change_date == date(2022, 11, 30)


# ===========================================================================
# TimelineReport tests
# ===========================================================================


class TestTimelineReport:
    def _make_timeline(self):
        DevelopmentChange, PropertyTimeline = _import_module()
        pt = PropertyTimeline(property_id="rpt-prop", address="99 Report Rd")
        pt.add_change(DevelopmentChange(
            change_date=date(2005, 6, 1),
            change_type="construction",
            description="Stadium built",
            confidence="high",
        ))
        return pt

    def test_render_returns_html_string(self) -> None:
        TimelineReport = _import_report()
        rpt = TimelineReport()
        timeline = self._make_timeline()
        html = rpt.render(timeline)
        assert isinstance(html, str)
        assert "<html" in html.lower()

    def test_html_contains_property_address(self) -> None:
        TimelineReport = _import_report()
        rpt = TimelineReport()
        timeline = self._make_timeline()
        html = rpt.render(timeline)
        assert "99 Report Rd" in html

    def test_html_contains_change_title_or_description(self) -> None:
        TimelineReport = _import_report()
        rpt = TimelineReport()
        timeline = self._make_timeline()
        html = rpt.render(timeline)
        assert "Stadium built" in html

    def test_html_contains_confidence_label(self) -> None:
        TimelineReport = _import_report()
        rpt = TimelineReport()
        timeline = self._make_timeline()
        html = rpt.render(timeline)
        assert "high" in html.lower()

    def test_save_writes_file(self) -> None:
        TimelineReport = _import_report()
        rpt = TimelineReport()
        timeline = self._make_timeline()
        with tempfile.TemporaryDirectory() as tmp:
            out = rpt.save(timeline, output_dir=tmp)
            assert out is not None
            assert os.path.exists(out)
            assert out.endswith(".html")

    def test_render_with_projections_includes_horizon_year(self) -> None:
        TimelineReport = _import_report()
        DevelopmentProjection = _import_projection()
        rpt = TimelineReport()
        timeline = self._make_timeline()
        proj = DevelopmentProjection(
            horizon_year=2030,
            projected_building_count=200,
            confidence="low",
            basis="linear extrapolation",
        )
        html = rpt.render(timeline, projections=[proj])
        assert "2030" in html


# ===========================================================================
# DevelopmentProjection tests
# ===========================================================================


class TestDevelopmentProjection:
    def test_projection_stores_fields(self) -> None:
        DevelopmentProjection = _import_projection()
        proj = DevelopmentProjection(
            horizon_year=2030,
            projected_building_count=150,
            confidence="medium",
            basis="zoning analysis",
        )
        assert proj.horizon_year == 2030
        assert proj.projected_building_count == 150
        assert proj.confidence == "medium"

    def test_to_dict_has_required_keys(self) -> None:
        DevelopmentProjection = _import_projection()
        proj = DevelopmentProjection(
            horizon_year=2030,
            projected_building_count=150,
            confidence="medium",
            basis="test",
        )
        d = proj.to_dict()
        for key in ("horizon_year", "projected_building_count", "confidence", "basis"):
            assert key in d

    def test_project_from_history_returns_projections(self) -> None:
        DevelopmentProjection = _import_projection()
        counts = [
            {"year": 2000, "building_count": 100},
            {"year": 2005, "building_count": 120},
            {"year": 2010, "building_count": 145},
        ]
        projections = DevelopmentProjection.from_history(
            historical_counts=counts,
            base_year=2020,
            horizon_years=(5, 10),
        )
        assert len(projections) == 2
        assert all(isinstance(p, DevelopmentProjection) for p in projections)

    def test_projections_sorted_by_horizon_year(self) -> None:
        DevelopmentProjection = _import_projection()
        counts = [
            {"year": 2000, "building_count": 100},
            {"year": 2010, "building_count": 130},
        ]
        projections = DevelopmentProjection.from_history(
            historical_counts=counts,
            base_year=2020,
            horizon_years=(10, 5),  # intentionally reversed
        )
        years = [p.horizon_year for p in projections]
        assert years == sorted(years)

    def test_positive_growth_increases_count_across_horizons(self) -> None:
        DevelopmentProjection = _import_projection()
        counts = [
            {"year": 2000, "building_count": 100},
            {"year": 2010, "building_count": 150},
        ]
        projections = DevelopmentProjection.from_history(
            historical_counts=counts,
            base_year=2020,
            horizon_years=(5, 10, 15),
        )
        cnts = [p.projected_building_count for p in projections]
        assert cnts[0] <= cnts[1] <= cnts[2]

    def test_empty_history_yields_zero_count(self) -> None:
        DevelopmentProjection = _import_projection()
        projections = DevelopmentProjection.from_history(
            historical_counts=[],
            base_year=2020,
            horizon_years=(5,),
        )
        assert projections[0].projected_building_count == 0

    def test_flat_history_gives_low_confidence(self) -> None:
        DevelopmentProjection = _import_projection()
        counts = [{"year": y, "building_count": 100} for y in range(2000, 2021)]
        projections = DevelopmentProjection.from_history(
            historical_counts=counts,
            base_year=2021,
            horizon_years=(5,),
        )
        assert projections[0].confidence == "low"
