"""Unit tests for parcel measurement from deed calls and survey drawings.

The traverse maths is the part worth guarding hardest. A sign error in a
quadrant bearing, or a curve correction added where it should be subtracted,
still produces a plausible-looking acreage — it just is not the parcel. So the
tests here pin the closure and the area against figures a surveyor independently
stated on a sealed drawing, not against this module's own output.

No fixture files: the PNG reader is exercised against rasters this test encodes
itself, so there is nothing to keep in sync.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

import pytest

from assethold.property.survey_measure import (
    GrayImage,
    RasterFrame,
    acres,
    circular_segment_area,
    closure_error,
    fit_line_robust,
    inset_polygon,
    parse_bearing,
    polygon_area,
    read_png_gray,
    segment_intersection,
    to_baseline_frame,
    traverse,
    widest_dark_run,
)


# ---------------------------------------------------------------------------
# Bearings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("N 61-43-40 E", 61.727778),
        ("S 28-16-20 E", 151.727778),
        ("S 72-11-54 W", 252.198333),
        ("N 00-15-58 E", 0.266111),
        ("N 30-59-49 E", 30.996944),
        # Formatting the module has to tolerate, same angle each time.
        ("N45E", 45.0),
        ("n 45 00 00 e", 45.0),
        ("N45°00'00\"E", 45.0),
    ],
)
def test_parse_bearing_quadrants(text, expected):
    assert parse_bearing(text) == pytest.approx(expected, abs=1e-4)


def test_parse_bearing_covers_all_four_quadrants():
    """A 45 degree call must land in the right quadrant, not merely 45 off north."""
    assert parse_bearing("N 45 E") == pytest.approx(45.0)
    assert parse_bearing("S 45 E") == pytest.approx(135.0)
    assert parse_bearing("S 45 W") == pytest.approx(225.0)
    assert parse_bearing("N 45 W") == pytest.approx(315.0)


@pytest.mark.parametrize("bad", ["", "E 10 N", "N 91-00-00 E", "N 61-43-40", "north"])
def test_parse_bearing_rejects_nonsense(bad):
    with pytest.raises(ValueError):
        parse_bearing(bad)


# ---------------------------------------------------------------------------
# Traverse closure and area, against a sealed ALTA survey
# ---------------------------------------------------------------------------

# Field note for a 1.5628-acre tract out of Unrestricted Reserve "E", Clayton
# Section Two, Harris County, Texas (recorded plat Vol. 247 Pg. 70 H.C.M.R.).
# The west line is a right-of-way curve, walked here on its chord.
ALTA_CALLS = [
    ("N 61-43-40 E", 135.92),
    ("S 28-16-20 E", 326.36),
    ("S 72-11-54 W", 303.40),
    ("N 01-22-43 E", 223.28),  # chord of a 5750.00 ft radius curve, arc 223.29
    ("N 00-15-58 E", 77.85),
    ("N 30-59-49 E", 17.19),  # cut-back corner, back to the point of beginning
]
ALTA_CURVE_RADIUS = 5750.00
ALTA_CURVE_ARC = 223.29
ALTA_STATED_SF = 68076.0
ALTA_STATED_ACRES = 1.5628


def test_alta_traverse_closes():
    """A correctly transcribed metes-and-bounds description returns to its start."""
    assert closure_error(traverse(ALTA_CALLS)) < 0.01


def test_alta_area_matches_surveyor_within_one_square_foot():
    """The curve bulges into the tract, so its segment comes off the chord area."""
    points = traverse(ALTA_CALLS)
    chord_area = polygon_area(points)
    segment = circular_segment_area(ALTA_CURVE_RADIUS, ALTA_CURVE_ARC)
    assert chord_area - segment == pytest.approx(ALTA_STATED_SF, abs=1.0)
    assert acres(chord_area - segment) == pytest.approx(ALTA_STATED_ACRES, abs=1e-4)


def test_curve_correction_is_not_negligible_but_is_small():
    """Guards the sign: adding rather than subtracting misses by twice the segment."""
    segment = circular_segment_area(ALTA_CURVE_RADIUS, ALTA_CURVE_ARC)
    assert 100.0 < segment < 250.0
    wrong_sign = polygon_area(traverse(ALTA_CALLS)) + segment
    assert abs(wrong_sign - ALTA_STATED_SF) > 300.0


def test_transcription_error_is_caught_by_closure():
    """Two digits transposed in one distance breaks closure, which is the point."""
    corrupted = list(ALTA_CALLS)
    corrupted[1] = ("S 28-16-20 E", 362.36)  # 326.36 mistyped
    assert closure_error(traverse(corrupted)) > 30.0


def test_polygon_area_ignores_a_repeated_closing_vertex():
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert polygon_area(square) == pytest.approx(100.0)
    assert polygon_area(square + [(0.0, 0.0)]) == pytest.approx(100.0)


def test_polygon_area_is_orientation_independent():
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert polygon_area(square) == pytest.approx(polygon_area(square[::-1]))


def test_acres_conversion():
    assert acres(43560.0) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Baseline frame
# ---------------------------------------------------------------------------


def test_to_baseline_frame_puts_the_baseline_on_the_u_axis():
    points = traverse(ALTA_CALLS)
    pob, ne, se = points[0], points[1], points[2]
    uv = to_baseline_frame([pob, ne, se], origin=ne, along=se, interior=pob)
    ne_uv, se_uv = uv[1], uv[2]
    assert ne_uv == pytest.approx((0.0, 0.0), abs=1e-6)
    assert se_uv[0] == pytest.approx(326.36, abs=1e-6)
    assert se_uv[1] == pytest.approx(0.0, abs=1e-6)
    # The interior point must land on the positive v side, whichever way the
    # baseline happens to run.
    assert uv[0][1] > 0


def test_baseline_frame_preserves_area():
    """A rotation and translation must not change the acreage."""
    points = traverse(ALTA_CALLS)[:-1]
    uv = to_baseline_frame(points, origin=points[1], along=points[2], interior=points[0])
    assert polygon_area(uv) == pytest.approx(polygon_area(points), rel=1e-9)


# ---------------------------------------------------------------------------
# Raster registration
# ---------------------------------------------------------------------------


def _frame(origin=(100.0, 100.0), end=(100.0, 600.0), baseline=250.0, interior=(0.0, 350.0)):
    return RasterFrame(
        origin_px=origin, end_px=end, baseline_ft=baseline, interior_px=interior
    )


def test_raster_frame_scale_and_roundtrip():
    frame = _frame()
    assert frame.scale_px_per_ft == pytest.approx(2.0)
    for u, v in [(0.0, 0.0), (250.0, 0.0), (125.0, 40.0), (10.0, -5.0)]:
        x, y = frame.to_px(u, v)
        assert frame.to_uv(x, y) == pytest.approx((u, v), abs=1e-9)


def test_raster_frame_v_axis_points_at_the_interior():
    """The perpendicular is flipped to face the parcel, not away from it."""
    frame = _frame(interior=(0.0, 350.0))
    x, y = frame.to_px(125.0, 50.0)
    assert x < 100.0  # interior lies to the left of a baseline running down-screen
    flipped = _frame(interior=(500.0, 350.0))
    x2, _ = flipped.to_px(125.0, 50.0)
    assert x2 > 100.0


def test_raster_frame_bearing_check_accepts_a_good_registration():
    """A baseline drawn due south reads as a S00E bearing with north up."""
    frame = _frame()
    assert frame.bearing_deg() == pytest.approx(180.0)
    assert frame.check_bearing("S 00-00-00 E") == pytest.approx(0.0, abs=1e-9)


def test_raster_frame_bearing_check_rejects_a_bad_registration():
    """Mis-picked corners are the failure mode this guard exists for."""
    frame = _frame(end=(160.0, 600.0))  # corner off by 60 px, ~7 degrees
    with pytest.raises(ValueError, match="differs from recorded"):
        frame.check_bearing("S 00-00-00 E")
    assert frame.residuals["S 00-00-00 E"] > 5.0


def test_raster_frame_rejects_a_degenerate_baseline():
    with pytest.raises(ValueError):
        RasterFrame((0.0, 0.0), (0.0, 0.0), 100.0, (1.0, 1.0))
    with pytest.raises(ValueError):
        RasterFrame((0.0, 0.0), (0.0, 10.0), 0.0, (1.0, 1.0))


# ---------------------------------------------------------------------------
# PNG reading and line finding
# ---------------------------------------------------------------------------


def _write_png(path: Path, width: int, height: int, pixels, filter_type: int = 0) -> None:
    """Encode an 8-bit greyscale PNG, optionally exercising a row filter."""
    rows = []
    prev = bytearray(width)
    for y in range(height):
        line = bytearray(pixels[y * width : (y + 1) * width])
        if filter_type == 0:
            encoded = bytes(line)
        elif filter_type == 1:
            encoded = bytes(
                [(line[i] - (line[i - 1] if i else 0)) & 0xFF for i in range(width)]
            )
        elif filter_type == 2:
            encoded = bytes([(line[i] - prev[i]) & 0xFF for i in range(width)])
        else:
            raise ValueError(filter_type)
        rows.append(bytes([filter_type]) + encoded)
        prev = line
    raw = b"".join(rows)

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


@pytest.mark.parametrize("filter_type", [0, 1, 2])
def test_read_png_gray_roundtrip_across_filters(tmp_path, filter_type):
    width, height = 9, 5
    pixels = bytearray((x * 20 + y * 3) % 256 for y in range(height) for x in range(width))
    path = tmp_path / f"f{filter_type}.png"
    _write_png(path, width, height, pixels, filter_type)
    img = read_png_gray(path)
    assert (img.width, img.height) == (width, height)
    assert img.data == pixels


def test_read_png_gray_rejects_a_non_png(tmp_path):
    path = tmp_path / "not.png"
    path.write_bytes(b"just some bytes")
    with pytest.raises(ValueError, match="not a PNG"):
        read_png_gray(path)


def test_gray_image_sampling_outside_the_raster_reads_as_background():
    img = GrayImage(2, 2, bytearray([0, 0, 0, 0]))
    assert img.at(0, 0) == 0
    assert img.at(-1, 0) == 255
    assert img.at(0, 99) == 255


def test_widest_dark_run_prefers_the_heavy_line():
    """Boundary line work is plotted heavier than dimension leaders beside it."""
    width, height = 40, 1
    row = bytearray([255] * width)
    for x in range(5, 7):  # thin leader, 2 px
        row[x] = 0
    for x in range(20, 27):  # boundary, 7 px
        row[x] = 0
    img = GrayImage(width, height, row)
    centre, thickness = widest_dark_run(img, fixed=0, lo=0, hi=width)
    assert thickness == 7
    assert centre == pytest.approx(23.0)


def test_widest_dark_run_returns_none_when_nothing_qualifies():
    img = GrayImage(10, 1, bytearray([255] * 10))
    assert widest_dark_run(img, fixed=0, lo=0, hi=10) is None


def test_fit_line_robust_recovers_a_line_despite_outliers():
    clean = [(t, 3.0 * t + 7.0) for t in range(60)]
    noise = [(5.0, 900.0), (17.0, -400.0), (44.0, 1200.0)]  # stray text in the window
    m, c, kept = fit_line_robust(clean + noise)
    assert m == pytest.approx(3.0, abs=1e-6)
    assert c == pytest.approx(7.0, abs=1e-6)
    assert kept == len(clean)


def test_fit_line_robust_needs_two_points():
    with pytest.raises(ValueError):
        fit_line_robust([(0.0, 0.0)])


def test_scan_profile_reports_wall_stations_in_feet():
    """A wall drawn across the sheet must be found at its true station."""
    width = height = 200
    pixels = bytearray([255] * (width * height))
    for y in range(height):  # a vertical dark line at x = 150 px
        for x in (149, 150, 151):
            pixels[y * width + x] = 0
    img = GrayImage(width, height, pixels)
    # Baseline runs left to right along the top: 100 px == 50 ft, so 2 px/ft.
    frame = RasterFrame(
        origin_px=(50.0, 10.0), end_px=(150.0, 10.0), baseline_ft=50.0,
        interior_px=(100.0, 100.0),
    )
    hits = frame.scan_profile(img, fixed=20.0, axis="u", lo=0.0, hi=60.0)
    assert len(hits) == 1
    start, end = hits[0]
    assert (start + end) / 2 == pytest.approx(50.0, abs=0.5)  # (150-50)/2 px per ft


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def test_segment_intersection_and_parallel_case():
    hit = segment_intersection((0.0, 0.0), (10.0, 0.0), (5.0, -5.0), (5.0, 5.0))
    assert hit == pytest.approx((5.0, 0.0))
    assert segment_intersection((0.0, 0.0), (10.0, 0.0), (0.0, 1.0), (10.0, 1.0)) is None


def test_inset_polygon_shrinks_a_square_by_the_setback():
    square = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    inner = inset_polygon(square, 10.0)
    assert polygon_area(inner) == pytest.approx(80.0 * 80.0, abs=1e-6)


def test_inset_polygon_is_orientation_independent():
    square = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    assert polygon_area(inset_polygon(square, 10.0)) == pytest.approx(
        polygon_area(inset_polygon(square[::-1], 10.0)), rel=1e-9
    )


def test_inset_polygon_needs_a_polygon():
    with pytest.raises(ValueError):
        inset_polygon([(0.0, 0.0), (1.0, 1.0)], 1.0)
