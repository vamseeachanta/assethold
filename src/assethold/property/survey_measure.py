"""
survey_measure.py — measure a parcel from its deed calls and its survey drawing.

Two independent things happen here, and the value is in doing both:

  1. ``traverse`` walks the metes-and-bounds calls from a deed or ALTA field
     note and closes the figure.  The closure error and the recomputed area are
     a check on the surveyor's stated acreage that costs nothing and
     occasionally catches a transcription error in the legal description.

  2. ``RasterFrame`` registers a scanned/plotted survey sheet to that closed
     traverse, so anything visible on the drawing — a building, a pavement
     edge, a detention basin — can be measured in feet instead of guessed at.

The registration is the part worth guarding hardest.  Two boundary corners fix
scale and rotation; if either is off, every downstream area is wrong while the
overlay still *looks* plausible.  Always check ``RasterFrame.residuals`` (the
fitted bearings against the recorded ones) before trusting a measurement.

Pure standard library: no Pillow, no numpy.  Survey sheets arrive as PDFs that
``pdftoppm`` renders to PNG, and the small PNG reader here handles those
directly so the module runs on a bare interpreter.
"""

from __future__ import annotations

import math
import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

Point = Tuple[float, float]

# ---------------------------------------------------------------------------
# Bearings and traverses
# ---------------------------------------------------------------------------

_BEARING_RE = re.compile(
    r"""^\s*
    (?P<ns>[NS])\s*
    (?P<deg>\d{1,3})\s*(?:[-°d]\s*)?
    (?:(?P<min>\d{1,2})\s*(?:['m′-]\s*)?)?
    (?:(?P<sec>\d{1,2}(?:\.\d+)?)\s*(?:["s″]\s*)?)?
    (?P<ew>[EW])\s*$""",
    re.VERBOSE | re.IGNORECASE,
)


def parse_bearing(text: str) -> float:
    """Convert a quadrant bearing to an azimuth in degrees clockwise from north.

    Accepts the forms surveyors actually write: ``N 61-43-40 E``,
    ``S28°16'20"E``, ``N 0 15 58 E``.

    >>> round(parse_bearing("N 61-43-40 E"), 4)
    61.7278
    >>> round(parse_bearing('S 28°16\\'20" E'), 4)
    151.7278
    """
    m = _BEARING_RE.match(text)
    if not m:
        raise ValueError(f"unparseable bearing: {text!r}")
    angle = (
        int(m.group("deg"))
        + int(m.group("min") or 0) / 60.0
        + float(m.group("sec") or 0.0) / 3600.0
    )
    if angle > 90.0:
        raise ValueError(f"quadrant bearing exceeds 90 degrees: {text!r}")
    ns, ew = m.group("ns").upper(), m.group("ew").upper()
    if ns == "N":
        return angle if ew == "E" else (360.0 - angle) % 360.0
    return 180.0 - angle if ew == "E" else 180.0 + angle


def traverse(calls: Sequence[Tuple[str, float]], start: Point = (0.0, 0.0)) -> List[Point]:
    """Walk ``(bearing, distance)`` calls, returning vertices in (east, north) feet.

    The returned list has ``len(calls) + 1`` points: the starting point, then
    one per call.  For a closed figure the last should coincide with the first;
    see :func:`closure_error`.
    """
    pts = [start]
    for bearing, dist in calls:
        az = math.radians(parse_bearing(bearing))
        x, y = pts[-1]
        pts.append((x + dist * math.sin(az), y + dist * math.cos(az)))
    return pts


def closure_error(points: Sequence[Point]) -> float:
    """Distance in feet between the first and last vertex of a walked traverse."""
    return math.hypot(points[-1][0] - points[0][0], points[-1][1] - points[0][1])


def polygon_area(points: Sequence[Point]) -> float:
    """Absolute shoelace area of a polygon, in square feet.

    A repeated closing vertex is ignored, so the output of :func:`traverse` can
    be passed in directly.
    """
    pts = list(points)
    if len(pts) > 2 and math.isclose(pts[0][0], pts[-1][0], abs_tol=1e-6) and math.isclose(
        pts[0][1], pts[-1][1], abs_tol=1e-6
    ):
        pts = pts[:-1]
    if len(pts) < 3:
        return 0.0
    total = 0.0
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def circular_segment_area(radius: float, arc_length: float) -> float:
    """Area between a chord and its arc — the correction a curved call needs.

    A traverse walked on chords approximates a boundary curve by a straight
    line.  Add this when the arc bulges away from the parcel, subtract it when
    the arc bulges into it (the usual case for a right-of-way curving into the
    land).
    """
    delta = arc_length / radius
    return 0.5 * radius * radius * (delta - math.sin(delta))


def acres(square_feet: float) -> float:
    """Square feet to acres."""
    return square_feet / 43560.0


# ---------------------------------------------------------------------------
# Minimal PNG reader (pdftoppm output; avoids a Pillow dependency)
# ---------------------------------------------------------------------------


@dataclass
class GrayImage:
    """An 8-bit greyscale raster.  ``data`` is row-major, length ``width*height``."""

    width: int
    height: int
    data: bytearray

    def at(self, x: int, y: int, default: int = 255) -> int:
        """Sample a pixel, returning ``default`` outside the image."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.data[y * self.width + x]
        return default


def read_png_gray(path: str | Path) -> GrayImage:
    """Read a non-interlaced 8-bit PNG and return its first channel as greyscale.

    Survey sheets render as black line work on white, so the red channel of an
    RGB render is as good as a luminance conversion and is cheaper.
    """
    raw = Path(path).read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    pos, idat = 8, bytearray()
    width = height = depth = color = None
    while pos < len(raw):
        (length,) = struct.unpack(">I", raw[pos : pos + 4])
        kind = raw[pos + 4 : pos + 8]
        body = raw[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(
                ">IIBBBBB", body
            )
            if interlace:
                raise ValueError("interlaced PNG is not supported")
            if depth != 8:
                raise ValueError(f"only 8-bit PNG is supported, got {depth}-bit")
            if color == 3:
                raise ValueError("palletted PNG is not supported")
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    if width is None:
        raise ValueError("PNG has no IHDR")

    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color]
    stride = width * channels
    unpacked = zlib.decompress(bytes(idat))
    out = bytearray(width * height)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        ftype = unpacked[pos]
        pos += 1
        line = bytearray(unpacked[pos : pos + stride])
        pos += stride
        if ftype == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif ftype != 0:
            raise ValueError(f"bad PNG filter type {ftype} on row {y}")
        for x in range(width):
            out[y * width + x] = line[x * channels]
        prev = line
    return GrayImage(width, height, out)


# ---------------------------------------------------------------------------
# Finding the boundary line work
# ---------------------------------------------------------------------------


def _dark_runs(values: Sequence[int], threshold: int) -> List[Tuple[int, int]]:
    runs: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for i, v in enumerate(values):
        if v < threshold:
            if start is None:
                start = i
        elif start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(values) - 1))
    return runs


def widest_dark_run(
    image: GrayImage,
    fixed: int,
    lo: int,
    hi: int,
    *,
    along: str = "x",
    threshold: int = 110,
    min_width: int = 3,
) -> Optional[Tuple[float, int]]:
    """Centre and width of the heaviest dark run on one scan line.

    Boundary lines are plotted heavier than dimension and text line work, so
    the widest run inside a narrow search window is almost always the boundary.
    Returns ``None`` when nothing meets ``min_width``.
    """
    if along == "x":
        values = [image.at(v, fixed) for v in range(lo, hi)]
    else:
        values = [image.at(fixed, v) for v in range(lo, hi)]
    runs = [r for r in _dark_runs(values, threshold) if r[1] - r[0] + 1 >= min_width]
    if not runs:
        return None
    a, b = max(runs, key=lambda r: r[1] - r[0])
    return lo + (a + b) / 2.0, b - a + 1


def fit_line_robust(
    samples: Sequence[Tuple[float, float]], iterations: int = 6
) -> Tuple[float, float, int]:
    """Least-squares fit of ``u = m*t + c`` with iterative outlier rejection.

    Returns ``(m, c, n_kept)``.  Rejection is by median absolute residual, which
    survives the stray text and dimension leaders that inevitably fall inside a
    search window.
    """
    kept = list(samples)
    if len(kept) < 2:
        raise ValueError("need at least two samples to fit a line")
    m = c = 0.0
    for _ in range(iterations):
        n = len(kept)
        st = sum(t for t, _ in kept)
        su = sum(u for _, u in kept)
        stt = sum(t * t for t, _ in kept)
        stu = sum(t * u for t, u in kept)
        det = n * stt - st * st
        if abs(det) < 1e-12:
            break
        m = (n * stu - st * su) / det
        c = (su * stt - st * stu) / det
        residuals = [abs(u - (m * t + c)) for t, u in kept]
        scale = sorted(residuals)[len(residuals) // 2] or 1e-9
        survivors = [
            s for s, r in zip(kept, residuals) if r <= max(3.0 * scale, 1.5)
        ]
        if len(survivors) == len(kept) or len(survivors) < 8:
            break
        kept = survivors
    return m, c, len(kept)


def intersect(
    x_of_y: Tuple[float, float], y_of_x: Tuple[float, float]
) -> Point:
    """Intersect a line given as ``x = m*y + c`` with one given as ``y = m*x + c``."""
    m1, c1 = x_of_y
    m2, c2 = y_of_x
    denom = 1.0 - m2 * m1
    if abs(denom) < 1e-12:
        raise ValueError("lines are parallel")
    y = (m2 * c1 + c2) / denom
    return m1 * y + c1, y


# ---------------------------------------------------------------------------
# Registering a drawing to the ground
# ---------------------------------------------------------------------------


@dataclass
class RasterFrame:
    """Maps pixels on a survey render to feet along a chosen baseline.

    The baseline is one boundary line of known length — pick the longest you can
    identify at both ends.  ``u`` runs along it from ``origin_px``; ``v`` runs
    perpendicular, positive toward ``interior_px``.  Because parcel improvements
    are almost always laid out square to a property line, measuring in (u, v)
    turns building and pavement edges into constant-``u`` or constant-``v``
    lines, which is what makes them findable by scanning.
    """

    origin_px: Point
    end_px: Point
    baseline_ft: float
    interior_px: Point
    residuals: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        dx = self.end_px[0] - self.origin_px[0]
        dy = self.end_px[1] - self.origin_px[1]
        length_px = math.hypot(dx, dy)
        if length_px <= 0 or self.baseline_ft <= 0:
            raise ValueError("baseline must have non-zero pixel and ground length")
        self.scale_px_per_ft = length_px / self.baseline_ft
        self._u = (dx / length_px, dy / length_px)
        perp = (-self._u[1], self._u[0])
        toward = (
            self.interior_px[0] - self.origin_px[0],
            self.interior_px[1] - self.origin_px[1],
        )
        if perp[0] * toward[0] + perp[1] * toward[1] < 0:
            perp = (-perp[0], -perp[1])
        self._v = perp

    def to_px(self, u: float, v: float) -> Point:
        """(u, v) in feet to pixel coordinates."""
        s = self.scale_px_per_ft
        return (
            self.origin_px[0] + (u * self._u[0] + v * self._v[0]) * s,
            self.origin_px[1] + (u * self._u[1] + v * self._v[1]) * s,
        )

    def to_uv(self, x: float, y: float) -> Point:
        """Pixel coordinates to (u, v) in feet."""
        a = x - self.origin_px[0]
        b = y - self.origin_px[1]
        s = self.scale_px_per_ft
        return (
            (a * self._u[0] + b * self._u[1]) / s,
            (a * self._v[0] + b * self._v[1]) / s,
        )

    def bearing_deg(self) -> float:
        """Azimuth of the baseline, assuming north is up in the raster."""
        return math.degrees(math.atan2(self._u[0], -self._u[1])) % 360.0

    def check_bearing(self, recorded: str, tolerance_deg: float = 0.5) -> float:
        """Compare the fitted baseline against its recorded bearing.

        Returns the absolute difference in degrees and records it in
        ``residuals``.  A drawing that is registered correctly agrees to a
        fraction of a degree; anything approaching a degree means the corner
        pixels are wrong and every measurement taken from the frame is suspect.
        """
        want = parse_bearing(recorded)
        got = self.bearing_deg()
        diff = abs((got - want + 180.0) % 360.0 - 180.0)
        self.residuals[recorded] = diff
        if diff > tolerance_deg:
            raise ValueError(
                f"baseline bearing {got:.3f} deg differs from recorded "
                f"{want:.3f} deg by {diff:.3f} deg (tolerance {tolerance_deg})"
            )
        return diff

    def scan_profile(
        self,
        image: GrayImage,
        fixed: float,
        axis: str,
        lo: float,
        hi: float,
        *,
        step: float = 0.2,
        threshold: int = 110,
        min_length: float = 0.25,
    ) -> List[Tuple[float, float]]:
        """Walk a line in (u, v) feet and report the dark intervals crossed.

        ``axis="u"`` holds ``v = fixed`` and sweeps ``u``; ``axis="v"`` does the
        reverse.  Intervals are in feet, so a wall shows up directly as its
        station along the baseline.
        """
        found: List[Tuple[float, float]] = []
        start: Optional[float] = None
        last = lo
        steps = int((hi - lo) / step)
        for i in range(steps + 1):
            t = lo + i * step
            u, v = (t, fixed) if axis == "u" else (fixed, t)
            x, y = self.to_px(u, v)
            if image.at(int(round(x)), int(round(y))) < threshold:
                if start is None:
                    start = t
                last = t
            elif start is not None:
                if last - start >= min_length:
                    found.append((start, last))
                start = None
        if start is not None and last - start >= min_length:
            found.append((start, last))
        return found


def to_baseline_frame(
    points: Iterable[Point], origin: Point, along: Point, interior: Point
) -> List[Point]:
    """Re-express ground coordinates in the same (u, v) frame as a RasterFrame.

    ``origin`` and ``along`` are the two ends of the baseline in (east, north)
    feet; ``interior`` is any point on the parcel side of it.  This puts the
    closed traverse and the measurements taken off the drawing into one
    coordinate system so they can be combined.
    """
    dx, dy = along[0] - origin[0], along[1] - origin[1]
    length = math.hypot(dx, dy)
    if length <= 0:
        raise ValueError("baseline endpoints coincide")
    u_hat = (dx / length, dy / length)
    v_hat = (-u_hat[1], u_hat[0])
    toward = (interior[0] - origin[0], interior[1] - origin[1])
    if v_hat[0] * toward[0] + v_hat[1] * toward[1] < 0:
        v_hat = (-v_hat[0], -v_hat[1])
    out = []
    for px, py in points:
        a, b = px - origin[0], py - origin[1]
        out.append((a * u_hat[0] + b * u_hat[1], a * v_hat[0] + b * v_hat[1]))
    return out


def segment_intersection(
    p1: Point, p2: Point, p3: Point, p4: Point
) -> Optional[Point]:
    """Intersection of the infinite lines through ``p1p2`` and ``p3p4``."""
    d1 = (p2[0] - p1[0], p2[1] - p1[1])
    d2 = (p4[0] - p3[0], p4[1] - p3[1])
    denom = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(denom) < 1e-12:
        return None
    t = ((p3[0] - p1[0]) * d2[1] - (p3[1] - p1[1]) * d2[0]) / denom
    return p1[0] + t * d1[0], p1[1] + t * d1[1]


def inset_polygon(points: Sequence[Point], distance: float) -> List[Point]:
    """Offset a polygon inward by ``distance`` feet — a uniform building setback.

    Edges are offset and re-intersected.  This is the simple construction, so it
    is only trustworthy for convex-ish parcels and modest setbacks; a deep inset
    on a sharp wedge will self-intersect and needs a real straight-skeleton.
    """
    pts = list(points)
    n = len(pts)
    if n < 3:
        raise ValueError("need at least three vertices")
    signed = sum(
        (pts[(i + 1) % n][0] - pts[i][0]) * (pts[(i + 1) % n][1] + pts[i][1])
        for i in range(n)
    )
    if signed <= 0:
        pts = pts[::-1]

    def offset(a: Point, b: Point) -> Tuple[Point, Point]:
        vx, vy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(vx, vy)
        nx, ny = vy / length * distance, -vx / length * distance
        return (a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny)

    out: List[Point] = []
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        a1, b1 = offset(p0, p1)
        a2, b2 = offset(p1, p2)
        hit = segment_intersection(a1, b1, a2, b2)
        out.append(hit if hit is not None else b1)
    return out
