"""Unit tests for the GIS ChangeDetector and NDVI helpers.

Uses synthetic numpy arrays to verify NDVI computation, differencing,
classification, and ChangeEvent generation without any file I/O or
external API calls.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from assethold.modules.gis.change_detector import (
    ChangeDetector,
    ChangeEvent,
    ChangeType,
    classify_ndvi_change,
    compute_ndvi,
    ndvi_difference,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def detector() -> ChangeDetector:
    """ChangeDetector with default thresholds and 30 m Landsat pixel size."""
    return ChangeDetector(
        loss_threshold=-0.15,
        gain_threshold=0.15,
        pixel_area_sqm=900.0,
    )


@pytest.fixture
def dense_vegetation_bands() -> tuple:
    """Dense vegetation: high NIR, low Red → NDVI ≈ 0.8."""
    shape = (10, 10)
    red = np.full(shape, 0.05, dtype=np.float32)
    nir = np.full(shape, 0.45, dtype=np.float32)
    return red, nir


@pytest.fixture
def bare_soil_bands() -> tuple:
    """Bare soil / construction: low NIR, high Red → NDVI ≈ 0.05."""
    shape = (10, 10)
    red = np.full(shape, 0.30, dtype=np.float32)
    nir = np.full(shape, 0.33, dtype=np.float32)
    return red, nir


# ---------------------------------------------------------------------------
# compute_ndvi tests
# ---------------------------------------------------------------------------


class TestComputeNdvi:
    def test_ndvi_dense_vegetation_is_high(
        self, dense_vegetation_bands: tuple
    ) -> None:
        red, nir = dense_vegetation_bands
        ndvi = compute_ndvi(red, nir)
        assert float(np.mean(ndvi)) > 0.7

    def test_ndvi_bare_soil_is_near_zero(self, bare_soil_bands: tuple) -> None:
        red, nir = bare_soil_bands
        ndvi = compute_ndvi(red, nir)
        assert abs(float(np.mean(ndvi))) < 0.10

    def test_ndvi_values_in_valid_range(self) -> None:
        rng = np.random.RandomState(42)
        red = rng.rand(20, 20).astype(np.float32)
        nir = rng.rand(20, 20).astype(np.float32)
        ndvi = compute_ndvi(red, nir)
        assert float(np.min(ndvi)) >= -1.0
        assert float(np.max(ndvi)) <= 1.0

    def test_ndvi_zero_denominator_gives_zero(self) -> None:
        red = np.zeros((5, 5), dtype=np.float32)
        nir = np.zeros((5, 5), dtype=np.float32)
        ndvi = compute_ndvi(red, nir)
        assert np.all(ndvi == 0.0)

    def test_ndvi_output_shape_matches_input(self) -> None:
        red = np.ones((8, 12), dtype=np.float32) * 0.2
        nir = np.ones((8, 12), dtype=np.float32) * 0.4
        ndvi = compute_ndvi(red, nir)
        assert ndvi.shape == (8, 12)

    def test_ndvi_is_float32(self) -> None:
        red = np.full((5, 5), 0.2, dtype=np.float32)
        nir = np.full((5, 5), 0.4, dtype=np.float32)
        ndvi = compute_ndvi(red, nir)
        assert ndvi.dtype == np.float32


# ---------------------------------------------------------------------------
# ndvi_difference tests
# ---------------------------------------------------------------------------


class TestNdviDifference:
    def test_difference_positive_when_vegetation_grows(self) -> None:
        before = np.full((5, 5), 0.2, dtype=np.float32)
        after = np.full((5, 5), 0.6, dtype=np.float32)
        diff = ndvi_difference(before, after)
        assert float(np.mean(diff)) > 0.0

    def test_difference_negative_when_vegetation_lost(self) -> None:
        before = np.full((5, 5), 0.7, dtype=np.float32)
        after = np.full((5, 5), 0.1, dtype=np.float32)
        diff = ndvi_difference(before, after)
        assert float(np.mean(diff)) < 0.0

    def test_difference_zero_when_no_change(self) -> None:
        ndvi = np.full((5, 5), 0.5, dtype=np.float32)
        diff = ndvi_difference(ndvi, ndvi.copy())
        assert np.allclose(diff, 0.0)


# ---------------------------------------------------------------------------
# classify_ndvi_change tests
# ---------------------------------------------------------------------------


class TestClassifyNdviChange:
    def test_loss_pixels_classified_as_one(self) -> None:
        diff = np.array([[-0.20, -0.30], [0.0, 0.10]], dtype=np.float32)
        classified = classify_ndvi_change(diff, loss_threshold=-0.15)
        assert classified[0, 0] == 1  # -0.20 < -0.15 → loss
        assert classified[0, 1] == 1  # -0.30 < -0.15 → loss

    def test_gain_pixels_classified_as_two(self) -> None:
        diff = np.array([[0.25, 0.0], [0.0, -0.10]], dtype=np.float32)
        classified = classify_ndvi_change(diff, gain_threshold=0.15)
        assert classified[0, 0] == 2  # 0.25 > 0.15 → gain

    def test_no_change_pixels_classified_as_zero(self) -> None:
        diff = np.array([[0.05, -0.05], [0.10, -0.10]], dtype=np.float32)
        classified = classify_ndvi_change(diff)
        assert np.all(classified == 0)

    def test_output_dtype_is_int8(self) -> None:
        diff = np.zeros((4, 4), dtype=np.float32)
        classified = classify_ndvi_change(diff)
        assert classified.dtype == np.int8


# ---------------------------------------------------------------------------
# ChangeDetector.detect_from_arrays tests
# ---------------------------------------------------------------------------


class TestChangeDetectorDetectFromArrays:
    def test_vegetation_loss_event_detected(
        self,
        detector: ChangeDetector,
        dense_vegetation_bands: tuple,
        bare_soil_bands: tuple,
    ) -> None:
        red_before, nir_before = dense_vegetation_bands
        red_after, nir_after = bare_soil_bands
        events = detector.detect_from_arrays(
            red_before=red_before,
            nir_before=nir_before,
            red_after=red_after,
            nir_after=nir_after,
            date_before=date(2000, 7, 1),
            date_after=date(2005, 7, 1),
        )
        types = [e.change_type for e in events]
        assert ChangeType.VEGETATION_LOSS in types

    def test_vegetation_gain_event_detected(
        self,
        detector: ChangeDetector,
        bare_soil_bands: tuple,
        dense_vegetation_bands: tuple,
    ) -> None:
        red_before, nir_before = bare_soil_bands
        red_after, nir_after = dense_vegetation_bands
        events = detector.detect_from_arrays(
            red_before=red_before,
            nir_before=nir_before,
            red_after=red_after,
            nir_after=nir_after,
            date_before=date(2000, 7, 1),
            date_after=date(2005, 7, 1),
        )
        types = [e.change_type for e in events]
        assert ChangeType.VEGETATION_GAIN in types

    def test_no_events_when_bands_identical(
        self, detector: ChangeDetector
    ) -> None:
        band = np.full((10, 10), 0.3, dtype=np.float32)
        events = detector.detect_from_arrays(
            red_before=band,
            nir_before=band,
            red_after=band.copy(),
            nir_after=band.copy(),
            date_before=date(2000, 7, 1),
            date_after=date(2005, 7, 1),
        )
        assert events == []

    def test_change_event_dates_are_set_correctly(
        self,
        detector: ChangeDetector,
        dense_vegetation_bands: tuple,
        bare_soil_bands: tuple,
    ) -> None:
        red_before, nir_before = dense_vegetation_bands
        red_after, nir_after = bare_soil_bands
        date_before = date(1995, 6, 15)
        date_after = date(2000, 8, 20)

        events = detector.detect_from_arrays(
            red_before=red_before,
            nir_before=nir_before,
            red_after=red_after,
            nir_after=nir_after,
            date_before=date_before,
            date_after=date_after,
        )
        for event in events:
            assert event.from_date == date_before
            assert event.to_date == date_after

    def test_change_event_area_is_positive(
        self,
        detector: ChangeDetector,
        dense_vegetation_bands: tuple,
        bare_soil_bands: tuple,
    ) -> None:
        red_before, nir_before = dense_vegetation_bands
        red_after, nir_after = bare_soil_bands
        events = detector.detect_from_arrays(
            red_before=red_before,
            nir_before=nir_before,
            red_after=red_after,
            nir_after=nir_after,
            date_before=date(2000, 7, 1),
            date_after=date(2005, 7, 1),
        )
        loss_events = [e for e in events if e.change_type == ChangeType.VEGETATION_LOSS]
        assert all(e.area_sqm > 0 for e in loss_events)

    def test_change_event_magnitude_in_range(
        self,
        detector: ChangeDetector,
        dense_vegetation_bands: tuple,
        bare_soil_bands: tuple,
    ) -> None:
        red_before, nir_before = dense_vegetation_bands
        red_after, nir_after = bare_soil_bands
        events = detector.detect_from_arrays(
            red_before=red_before,
            nir_before=nir_before,
            red_after=red_after,
            nir_after=nir_after,
            date_before=date(2000, 7, 1),
            date_after=date(2005, 7, 1),
        )
        for event in events:
            assert 0.0 <= event.magnitude <= 1.0

    def test_confidence_high_for_large_change(
        self, detector: ChangeDetector
    ) -> None:
        """A full-AOI vegetation → bare conversion should yield high confidence."""
        before_red = np.full((100, 100), 0.05, dtype=np.float32)
        before_nir = np.full((100, 100), 0.45, dtype=np.float32)
        after_red = np.full((100, 100), 0.30, dtype=np.float32)
        after_nir = np.full((100, 100), 0.33, dtype=np.float32)
        events = detector.detect_from_arrays(
            red_before=before_red,
            nir_before=before_nir,
            red_after=after_red,
            nir_after=after_nir,
            date_before=date(2000, 7, 1),
            date_after=date(2005, 7, 1),
        )
        loss_events = [e for e in events if e.change_type == ChangeType.VEGETATION_LOSS]
        assert any(e.confidence == "high" for e in loss_events)

    def test_year_range_property(self) -> None:
        event = ChangeEvent(
            change_type=ChangeType.CONSTRUCTION,
            from_date=date(2000, 1, 1),
            to_date=date(2005, 1, 1),
            magnitude=0.5,
        )
        assert event.year_range == "2000–2005"

    def test_raster_read_returns_empty_without_rasterio(
        self, detector: ChangeDetector, tmp_path
    ) -> None:
        """detect_from_rasters returns empty list when rasterio not installed."""
        import sys
        from unittest.mock import patch

        with patch.dict(sys.modules, {"rasterio": None}):
            result = detector.detect_from_rasters(
                path_before=str(tmp_path / "before.tif"),
                path_after=str(tmp_path / "after.tif"),
                date_before=date(2000, 1, 1),
                date_after=date(2005, 1, 1),
            )
        assert result == []
