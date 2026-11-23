#!/usr/bin/env python3
"""Build a browsable imagery review site from a land-holdings roster.

    uv run --with pyyaml --with pillow --with pypdf --no-project \
        scripts/python/india_land_maps/build_site_review.py \
        --roster  /path/to/sites.yaml \
        --docs-root /path/to/document/tree \
        --out     /path/to/output

The roster is data and lives with the documents it describes - typically in a
private repo. This script is code and lives here, so the imagery maths, the
page layout and the determinism guarantees are versioned and tested in one
place instead of being copy-pasted next to each dataset.

For every site in the roster it:

  * pulls ESRI World Imagery XYZ tiles at three fixed scales and stitches them
    (context ~4 km, site ~1.2 km, close ~400 m), so sites are comparable;
  * marks the anchor and draws an uncertainty ring sized from the declared
    precision - a village-centre guess LOOKS like a village-centre guess and is
    never mistaken for a boundary;
  * lets the reader select a competing candidate anchor, or type a coordinate,
    and moves the marker across all three views client-side;
  * lifts the plan/route-map/photo images out of the deed scans;
  * writes <key>.html plus index.html and manifest.json.

Determinism
-----------
Same roster + same tile cache => byte-identical output, and `--verify` proves
it. Tiles are cached under the output's `_cache/`; a run that cannot fetch a
tile fails rather than silently shipping a mosaic with black holes in it (pass
`--allow-missing-tiles` to override). manifest.json records a SHA-256 for every
generated image, so drift between runs is visible in a diff rather than being
something you have to eyeball.

Imagery attribution: Esri, Maxar, Earthstar Geographics, and the GIS User
Community.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import math
import os
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Reuse the tile/Mercator maths rather than restating it: a sign error here
# puts every mosaic in the wrong place on the ground and the output still
# looks fine. One implementation, one test suite.
from fetch_basemap_tiles import (  # noqa: E402
    EARTH_CIRCUM,
    ORIGIN,
    TILE_PX,
    fetch_tile,
    tile2merc,
)

# (label, zoom, half-width in metres) - three fixed scales for every site.
VIEWS = [
    ("context", 16, 2000),
    ("site", 18, 600),
    ("close", 19, 200),
]

# How far the anchor might be off, in metres, when the roster does not say.
UNCERTAINTY = {"exact": 30, "locality": 400, "village": 1000, "unknown": 3000}

PRECISION_NOTE = {
    "exact": "Pin taken from a map placemark on the property itself.",
    "locality": "Right colony or street area only - the plot is somewhere inside the ring.",
    "village": "Revenue village centre only - the parcel is somewhere in this village's lands.",
    "unknown": "The village could not be geocoded. This is a search box, not a location.",
}

# A blank "map data not available" mosaic is nearly uniform grey; real imagery
# never is. Below this greyscale standard deviation, step down a zoom level.
BLANK_STDDEV = 8.0
MIN_ZOOM = 15

JPEG_QUALITY = 86
PLAN_QUALITY = 84
MAX_PLAN_PX = 1800


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

def merc(lat: float, lon: float) -> tuple[float, float]:
    """Lat/lon -> EPSG:3857 metres."""
    x = ORIGIN * lon / 180.0
    y = ORIGIN * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) / math.pi
    return x, y


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in metres between two (lat, lon) pairs."""
    r = 6371008.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def view_box(lat: float, lon: float, half_m: float) -> tuple[float, float, float, float]:
    """Square box around a point, as (west, south, east, north) in EPSG:3857.

    Web Mercator metres are inflated by 1/cos(lat), so a box that should be
    `half_m` of GROUND metres has to be scaled up before it is applied.
    """
    cx, cy = merc(lat, lon)
    half = half_m / math.cos(math.radians(lat))
    return cx - half, cy - half, cx + half, cy + half


def blankness(img: Image.Image) -> float:
    """Greyscale standard deviation of a downsampled copy."""
    px = list(img.convert("L").resize((64, 64)).getdata())
    mean = sum(px) / len(px)
    return (sum((p - mean) ** 2 for p in px) / len(px)) ** 0.5


# --------------------------------------------------------------------------
# Tiles
# --------------------------------------------------------------------------

class TileStore:
    """Disk-backed tile cache. Same cache + same roster => same pixels."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, z: int, x: int, y: int) -> Path:
        return self.root / str(z) / str(x) / f"{y}.jpg"

    def get(self, job: tuple[int, int, int]) -> tuple[int, int, bytes | None]:
        z, x, y = job
        cached = self.path(z, x, y)
        if cached.exists():
            return x, y, cached.read_bytes()
        _, _, blob = fetch_tile(job)
        if blob is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(blob)
        return x, y, blob


def build_view(
    store: TileStore,
    lat: float,
    lon: float,
    z: int,
    half_m: float,
    dst: Path,
    workers: int = 8,
) -> dict:
    """Stitch a square mosaic centred on lat/lon; return its geometry."""
    west, south, east, north = view_box(lat, lon, half_m)

    res_tile = EARTH_CIRCUM / (2**z)  # metres per tile edge
    x0 = int((west + ORIGIN) / res_tile)
    x1 = int((east + ORIGIN) / res_tile)
    y0 = int((ORIGIN - north) / res_tile)
    y1 = int((ORIGIN - south) / res_tile)

    canvas = Image.new("RGB", ((x1 - x0 + 1) * TILE_PX, (y1 - y0 + 1) * TILE_PX))
    jobs = [(z, x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]
    missing = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for x, y, blob in pool.map(store.get, jobs):
            if blob is None:
                missing += 1
                continue
            try:
                canvas.paste(
                    Image.open(io.BytesIO(blob)).convert("RGB"),
                    ((x - x0) * TILE_PX, (y - y0) * TILE_PX),
                )
            except Exception as exc:  # corrupt tile - treat as missing
                print(f"  [tile] BAD z{z}/{x}/{y}: {exc}", file=sys.stderr)
                missing += 1

    ox, oy = tile2merc(x0, y0, z)
    res_px = res_tile / TILE_PX

    # Crop to the requested box so every view is exactly square and its
    # geographic extent is known to the pixel.
    left = max(0, int((west - ox) / res_px))
    top = max(0, int((oy - north) / res_px))
    right = min(canvas.width, int((east - ox) / res_px))
    bottom = min(canvas.height, int((oy - south) / res_px))
    canvas = canvas.crop((left, top, right, bottom))

    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst, quality=JPEG_QUALITY, subsampling=0, optimize=True)

    # Exact mercator extent of the saved image - the page needs this to place
    # an arbitrary coordinate the reader types in.
    box = {
        "west": ox + left * res_px,
        "north": oy - top * res_px,
        "east": ox + right * res_px,
        "south": oy - bottom * res_px,
    }
    ground_res = res_px * math.cos(math.radians(lat))
    return {
        "file": dst.name,
        "zoom": z,
        "stddev": round(blankness(canvas), 1),
        "width": canvas.width,
        "height": canvas.height,
        "ground_m_per_px": round(ground_res, 3),
        "span_m": round(canvas.width * ground_res),
        "missing_tiles": missing,
        "merc_box": {k: round(v, 3) for k, v in box.items()},
        "sha256": sha256(dst),
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Plan / photo images
# --------------------------------------------------------------------------

def _finish(img: Image.Image, dst: Path, crop) -> bool:
    """Optionally crop (fractions of width/height: l, t, r, b), then save."""
    if crop:
        w, h = img.size
        left, top, right, bottom = crop
        img = img.crop((int(left * w), int(top * h), int(right * w), int(bottom * h)))
    img.thumbnail((MAX_PLAN_PX, MAX_PLAN_PX))
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, quality=PLAN_QUALITY, optimize=True)
    return True


def extract_pdf_page(pdf: Path, page: int, dst: Path, crop=None) -> bool:
    """Pull the largest embedded image out of one page of a scanned PDF."""
    from pypdf import PdfReader

    try:
        images = list(PdfReader(str(pdf)).pages[page - 1].images)
    except Exception as exc:
        print(f"  [plan] {pdf.name} p{page}: {exc}", file=sys.stderr)
        return False
    if not images:
        print(f"  [plan] {pdf.name} p{page}: no embedded image", file=sys.stderr)
        return False
    best = max(images, key=lambda im: len(im.data))
    try:
        img = Image.open(io.BytesIO(best.data)).convert("RGB")
    except Exception as exc:
        print(f"  [plan] {pdf.name} p{page}: {exc}", file=sys.stderr)
        return False
    return _finish(img, dst, crop)


def copy_image(src: Path, dst: Path, crop=None) -> bool:
    try:
        img = Image.open(src).convert("RGB")
    except Exception as exc:
        print(f"  [plan] {src.name}: {exc}", file=sys.stderr)
        return False
    return _finish(img, dst, crop)


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

CSS = """
:root {
  --bg: #fbfaf8; --panel: #ffffff; --ink: #1b1a18; --muted: #6b6660;
  --line: #e3ded6; --accent: #b4581f; --accent-soft: #f4e6da; --field: #fff;
  --exact: #1c7c4a; --locality: #b07d18; --village: #a2571c; --unknown: #a32d2d;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #16150f; --panel: #1f1e17; --ink: #ece7dd; --muted: #9b948a;
          --line: #34322a; --accent: #e59155; --accent-soft: #33261c; --field: #14130e;
          --exact: #57c98a; --locality: #e2b356; --village: #e0965a; --unknown: #ef7f7f; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.6 ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif; }
.wrap { max-width: 1120px; margin: 0 auto; padding: 32px 20px 80px; }
a { color: var(--accent); }
h1 { font-size: 1.9rem; line-height: 1.2; margin: 0 0 4px; letter-spacing: -0.01em; }
h2 { font-size: 1.05rem; text-transform: uppercase; letter-spacing: 0.08em;
     color: var(--muted); margin: 44px 0 14px; font-weight: 600; }
.sub { color: var(--muted); margin: 0 0 22px; }
.nav { display: flex; gap: 14px; align-items: center; margin-bottom: 26px;
       font-size: 0.9rem; flex-wrap: wrap; }
.card { background: var(--panel); border: 1px solid var(--line);
        border-radius: 12px; padding: 18px 20px; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
         gap: 14px 26px; }
.facts div { min-width: 0; }
.k { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.07em;
     color: var(--muted); }
.v { font-variant-numeric: tabular-nums; word-wrap: break-word; }
.pill { display: inline-block; padding: 2px 9px; border-radius: 999px;
        font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em;
        text-transform: uppercase; border: 1px solid currentColor; }
.p-exact { color: var(--exact); } .p-locality { color: var(--locality); }
.p-village { color: var(--village); } .p-unknown { color: var(--unknown); }
.views { display: grid; gap: 18px; grid-template-columns: 1fr; }
@media (min-width: 780px) { .views { grid-template-columns: repeat(3, 1fr); } }
figure { margin: 0; }
.shot { position: relative; overflow: hidden; border-radius: 10px;
        border: 1px solid var(--line); background: #000; aspect-ratio: 1; }
.shot img { width: 100%; height: 100%; object-fit: cover; display: block; }
.mark { position: absolute; transform: translate(-50%, -50%); pointer-events: none; }
.ring { border: 1.5px dashed rgba(255,255,255,.85); border-radius: 50%;
        box-shadow: 0 0 0 1px rgba(0,0,0,.45) inset, 0 0 0 1px rgba(0,0,0,.35); }
.dot { width: 13px; height: 13px; border-radius: 50%; background: #ff5f2e;
       border: 2px solid #fff; box-shadow: 0 0 5px rgba(0,0,0,.8); }
.probe { width: 15px; height: 15px; border-radius: 50%; background: #2ea8ff;
         border: 2px solid #fff; box-shadow: 0 0 6px rgba(0,0,0,.9); display: none; }
.offscreen { position: absolute; left: 50%; bottom: 8px; transform: translateX(-50%);
             background: rgba(0,0,0,.72); color: #fff; font-size: 0.72rem;
             padding: 3px 9px; border-radius: 999px; display: none;
             white-space: nowrap; }
figcaption { font-size: 0.82rem; color: var(--muted); margin-top: 7px; }
figcaption b { color: var(--ink); font-weight: 600; }
.picker { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end;
          margin-top: 16px; }
.picker label { display: block; }
.picker .k { margin-bottom: 4px; }
select, input[type=text] { font: inherit; font-size: 0.92rem; color: var(--ink);
  background: var(--field); border: 1px solid var(--line); border-radius: 8px;
  padding: 8px 10px; max-width: 100%; }
select { min-width: 260px; }
input[type=text] { min-width: 230px; }
button { font: inherit; font-size: 0.92rem; cursor: pointer; color: var(--ink);
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  padding: 8px 14px; }
button:hover { border-color: var(--accent); color: var(--accent); }
.readout { font-size: 0.85rem; color: var(--muted); margin-top: 10px;
           min-height: 1.6em; }
.readout b { color: var(--ink); }
.readout .bad { color: var(--unknown); }
ul.hand { padding-left: 18px; margin: 0; }
ul.hand li { margin-bottom: 7px; }
.warn { border-left: 3px solid var(--unknown); background: var(--accent-soft);
        padding: 12px 16px; border-radius: 0 8px 8px 0; margin: 14px 0 0; }
.plans { display: grid; gap: 20px; grid-template-columns: 1fr; }
@media (min-width: 720px) { .plans { grid-template-columns: 1fr 1fr; } }
.plans img { width: 100%; border-radius: 10px; border: 1px solid var(--line);
             background: #fff; display: block; }
table { border-collapse: collapse; width: 100%; font-size: 0.92rem; }
th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--line);
         vertical-align: top; }
th { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.07em;
     color: var(--muted); font-weight: 600; }
tr:last-child td { border-bottom: none; }
.tablewrap { overflow-x: auto; }
.docs a { display: block; padding: 7px 0; border-bottom: 1px solid var(--line); }
.docs a:last-child { border-bottom: none; }
.docs small { color: var(--muted); }
footer { margin-top: 60px; padding-top: 18px; border-top: 1px solid var(--line);
         color: var(--muted); font-size: 0.8rem; }
"""

# Client-side anchor probe. Everything it needs is baked into the page: each
# view carries its exact Web Mercator extent, so an arbitrary coordinate can be
# placed without a network call, a tile server or a mapping library.
JS = """
(function () {
  var R = 20037508.342789244;
  function merc(lat, lon) {
    return [R * lon / 180,
            R * Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)) / Math.PI];
  }
  function haversine(a, b) {
    var r = 6371008.8, p1 = a[0] * Math.PI / 180, p2 = b[0] * Math.PI / 180;
    var dp = p2 - p1, dl = (b[1] - a[1]) * Math.PI / 180;
    var h = Math.sin(dp / 2) * Math.sin(dp / 2) +
            Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
    return 2 * r * Math.asin(Math.sqrt(h));
  }
  function bearing(a, b) {
    var p1 = a[0] * Math.PI / 180, p2 = b[0] * Math.PI / 180;
    var dl = (b[1] - a[1]) * Math.PI / 180;
    var y = Math.sin(dl) * Math.cos(p2);
    var x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
    var d = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
    return ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW',
            'W','WNW','NW','NNW'][Math.round(d / 22.5) % 16];
  }
  // Accepts "16.9886, 82.2488" or 16 deg 59' 25.7" N, 82 deg 15' 37.7" E.
  function parseCoord(raw) {
    var s = raw.trim();
    if (!s) return null;
    var dec = s.match(/^\\s*(-?\\d+(?:\\.\\d+)?)\\s*[, ]\\s*(-?\\d+(?:\\.\\d+)?)\\s*$/);
    if (dec) return [parseFloat(dec[1]), parseFloat(dec[2])];
    var dms = /(\\d+(?:\\.\\d+)?)[^\\d]+(\\d+(?:\\.\\d+)?)[^\\d]+(\\d+(?:\\.\\d+)?)[^A-Za-z]*([NSEW])/gi;
    var m, vals = [];
    while ((m = dms.exec(s)) !== null) {
      var v = parseFloat(m[1]) + parseFloat(m[2]) / 60 + parseFloat(m[3]) / 3600;
      var h = m[4].toUpperCase();
      if (h === 'S' || h === 'W') v = -v;
      vals.push([h, v]);
    }
    if (vals.length === 2) {
      var lat = vals.find(function (p) { return p[0] === 'N' || p[0] === 'S'; });
      var lon = vals.find(function (p) { return p[0] === 'E' || p[0] === 'W'; });
      if (lat && lon) return [lat[1], lon[1]];
    }
    return null;
  }
  function place(lat, lon) {
    var p = merc(lat, lon);
    document.querySelectorAll('.shot').forEach(function (shot) {
      var box = JSON.parse(shot.dataset.box);
      var dot = shot.querySelector('.probe');
      var tag = shot.querySelector('.offscreen');
      var fx = (p[0] - box.west) / (box.east - box.west);
      var fy = (box.north - p[1]) / (box.north - box.south);
      if (fx >= 0 && fx <= 1 && fy >= 0 && fy <= 1) {
        dot.style.left = (fx * 100) + '%';
        dot.style.top = (fy * 100) + '%';
        dot.style.display = 'block';
        tag.style.display = 'none';
      } else {
        dot.style.display = 'none';
        tag.textContent = 'outside this view';
        tag.style.display = 'block';
      }
    });
  }
  function clear() {
    document.querySelectorAll('.probe,.offscreen').forEach(function (el) {
      el.style.display = 'none';
    });
  }
  document.addEventListener('DOMContentLoaded', function () {
    var sel = document.getElementById('candidate');
    var box = document.getElementById('coord');
    var out = document.getElementById('readout');
    var anchor = JSON.parse(document.body.dataset.anchor);
    function show(lat, lon, label) {
      place(lat, lon);
      var d = haversine(anchor, [lat, lon]);
      var where = d < 1 ? 'the anchor itself'
        : (d < 1000 ? Math.round(d) + ' m ' : (d / 1000).toFixed(2) + ' km ') +
          bearing(anchor, [lat, lon]) + ' of the anchor';
      out.innerHTML = '<b>' + label + '</b> &middot; ' + lat.toFixed(6) + ', ' +
        lon.toFixed(6) + ' &middot; ' + where +
        ' &middot; <a target="_blank" rel="noopener" href="https://www.openstreetmap.org/?mlat=' +
        lat + '&mlon=' + lon + '#map=18/' + lat + '/' + lon + '">open in OSM</a>';
    }
    if (sel) {
      sel.addEventListener('change', function () {
        if (!sel.value) { clear(); out.textContent = ''; return; }
        var c = JSON.parse(sel.value);
        box.value = '';
        show(c.lat, c.lon, c.label);
      });
    }
    if (box) {
      var go = function () {
        var c = parseCoord(box.value);
        if (!c) {
          clear();
          out.innerHTML = box.value.trim()
            ? '<span class="bad">Not a coordinate.</span> Enter "16.9886, 82.2488" ' +
              'or 16&deg;59\\'25.7"N 82&deg;15\\'37.7"E. Place names cannot be ' +
              'resolved here - this page makes no network calls.'
            : '';
          return;
        }
        if (sel) sel.value = '';
        show(c[0], c[1], 'entered');
      };
      box.addEventListener('change', go);
      box.addEventListener('keydown', function (e) { if (e.key === 'Enter') go(); });
    }
    var reset = document.getElementById('reset');
    if (reset) {
      reset.addEventListener('click', function () {
        if (sel) sel.value = '';
        if (box) box.value = '';
        clear();
        out.textContent = '';
      });
    }
  });
})();
"""


def esc(text) -> str:
    return html.escape(str(text if text is not None else ""))


def shot_html(view: dict, rel: str, ring_pct: float) -> str:
    box = json.dumps(view["merc_box"], sort_keys=True)
    ring = ""
    if ring_pct > 6:
        ring = (
            f'<div class="mark ring" style="left:50%;top:50%;'
            f'width:{ring_pct:.1f}%;height:{ring_pct:.1f}%"></div>'
        )
    return (
        f"<div class=\"shot\" data-box='{esc(box)}'>"
        f'<img src="{rel}" alt="satellite view" loading="lazy">'
        f'{ring}<div class="mark dot" style="left:50%;top:50%"></div>'
        f'<div class="mark probe"></div><div class="offscreen"></div></div>'
    )


def picker_html(site: dict) -> str:
    """Anchor selector: the roster's candidates plus free coordinate entry."""
    a = site["anchor"]
    options = [{"label": "Anchor (as published on this page)",
                "lat": a["lat"], "lon": a["lon"]}]
    for c in site.get("candidates", []):
        options.append({"label": c["label"], "lat": c["lat"], "lon": c["lon"]})

    opts = '<option value="">-- none --</option>' + "".join(
        f"<option value='{esc(json.dumps(o, sort_keys=True))}'>{esc(o['label'])}</option>"
        for o in options
    )
    return f"""
  <div class="card" style="margin-top:18px">
    <div class="k">Try a different position</div>
    <div class="picker">
      <label><span class="k">Candidate</span>
        <select id="candidate">{opts}</select></label>
      <label><span class="k">Or a coordinate</span>
        <input type="text" id="coord" placeholder="16.9886, 82.2488"
               autocomplete="off" spellcheck="false"></label>
      <button type="button" id="reset">Clear</button>
    </div>
    <div class="readout" id="readout"></div>
  </div>"""


def site_page(site: dict, views: list[dict], plans: list[dict], prev, nxt) -> str:
    a = site["anchor"]
    prec = a.get("precision", "unknown")
    unc = a.get("uncertainty_m", UNCERTAINTY[prec])

    view_html = []
    for v in views:
        ring_pct = 100 * (2 * unc) / max(v["span_m"], 1)
        label = {"context": "Context", "site": "Site", "close": "Close"}[v["name"]]
        fallback = ""
        if v["zoom"] != v.get("requested_zoom", v["zoom"]):
            fallback = (
                f'<br>Esri has no imagery here at z{v["requested_zoom"]} - '
                f"z{v['zoom']} is the sharpest available."
            )
        view_html.append(
            "<figure>"
            + shot_html(v, f"assets/{site['key']}/{v['file']}", ring_pct)
            + f"<figcaption><b>{label}</b> &middot; z{v['zoom']} &middot; "
            f"{v['span_m']} m across &middot; {v['ground_m_per_px']} m/px{fallback}"
            "</figcaption></figure>"
        )

    facts = [
        ("Owner group", site.get("owner")),
        ("Revenue village", site.get("village")),
        ("Mandal", site.get("mandal")),
        ("District / State", f"{site.get('district')}, {site.get('state')}"),
        ("PIN", site.get("pincode")),
        ("Extent", site.get("extent")),
        ("Survey no.", site.get("survey")),
        ("Document(s)", site.get("deeds")),
        ("Status", site.get("status")),
        ("Anchor", f"{a['lat']:.6f}, {a['lon']:.6f}"),
    ]
    facts_html = "".join(
        f'<div><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div></div>'
        for k, v in facts
        if v
    )

    handles = "".join(f"<li>{esc(h)}</li>" for h in site.get("ground_handles", []))
    handles_html = (
        f'<h2>How to recognise it on the ground</h2><ul class="hand">{handles}</ul>'
        if handles else ""
    )

    plans_html = ""
    if plans:
        cards = "".join(
            f'<figure><img src="assets/{site["key"]}/{p["file"]}" '
            f'alt="{esc(p["caption"])}" loading="lazy">'
            f'<figcaption>{esc(p["caption"])}</figcaption></figure>'
            for p in plans
        )
        plans_html = (
            f'<h2>Plans, records and site photographs</h2>'
            f'<div class="plans">{cards}</div>'
        )

    docs_html = ""
    if site.get("docs"):
        rows = "".join(
            f'<a href="{esc(d["href"])}">{esc(d["label"])}<br>'
            f'<small>{esc(d["path"])}</small></a>'
            for d in site["docs"]
        )
        docs_html = f'<h2>Source documents</h2><div class="card docs">{rows}</div>'

    steps_html = ""
    if site.get("next_steps"):
        items = "".join(f"<li>{esc(s)}</li>" for s in site["next_steps"])
        steps_html = f'<h2>To pin this down</h2><ul class="hand">{items}</ul>'

    warn = ""
    if prec != "exact":
        warn = (
            f'<div class="warn"><b>The marker is not the plot.</b> '
            f'{esc(PRECISION_NOTE[prec])} The dashed ring is {unc} m in radius. '
            f'{esc(a.get("source", ""))}</div>'
        )

    nav = []
    if prev:
        nav.append(f'<a href="{prev[0]}.html">&larr; {esc(prev[1])}</a>')
    nav.append('<a href="index.html">All sites</a>')
    if nxt:
        nav.append(f'<a href="{nxt[0]}.html">{esc(nxt[1])} &rarr;</a>')

    anchor_json = json.dumps([a["lat"], a["lon"]])
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(site['title'])} - land review</title>
<style>{CSS}</style>
<script>{JS}</script>
<body data-anchor='{esc(anchor_json)}'>
<div class="wrap">
  <div class="nav">{' &middot; '.join(nav)}</div>
  <h1>{esc(site['title'])}</h1>
  <p class="sub">{esc(site.get('village'))}, {esc(site.get('mandal'))} mandal,
     {esc(site.get('district'))}, {esc(site.get('state'))}
     &nbsp; <span class="pill p-{prec}">{prec} anchor</span></p>

  <div class="card"><div class="facts">{facts_html}</div></div>

  <h2>Satellite imagery</h2>
  <div class="views">{''.join(view_html)}</div>
  {warn}
  {picker_html(site)}

  {handles_html}
  {plans_html}
  {steps_html}
  {docs_html}

  <footer>Imagery &copy; Esri, Maxar, Earthstar Geographics and the GIS User
  Community. Satellite imagery is never a boundary - only a surveyed FMB from
  the mandal surveyor is. Deed scans in this tree also contain identity
  documents; those pages are excluded from this review deliberately.</footer>
</div>
</body>
"""


def index_page(entries: list[dict]) -> str:
    rows = "".join(
        f'<tr><td><a href="{e["key"]}.html">{esc(e["title"])}</a></td>'
        f'<td>{esc(e["owner"])}</td>'
        f'<td>{esc(e["village"])}<br><small>{esc(e["mandal"])}, '
        f'{esc(e["district"])}</small></td>'
        f'<td>{esc(e["extent"])}</td>'
        f'<td>{esc(e["survey"])}</td>'
        f'<td><span class="pill p-{e["precision"]}">{e["precision"]}</span></td></tr>'
        for e in entries
    )
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["precision"]] = counts.get(e["precision"], 0) + 1
    tally = " &middot; ".join(f"{v} {k}" for k, v in sorted(counts.items()))

    notes = "".join(
        f'<div><div class="k"><span class="pill p-{p}">{p}</span></div>'
        f'<div class="v">{esc(PRECISION_NOTE[p])}</div></div>'
        for p in ("exact", "locality", "village", "unknown")
    )

    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Land holdings - imagery review</title>
<style>{CSS}</style>
<div class="wrap">
  <h1>Land holdings</h1>
  <p class="sub">{len(entries)} sites, each with satellite imagery at three
     scales plus whatever plan, record or photograph exists on paper.
     Anchor quality: {tally}. Every site page lets you drop a competing
     candidate position, or a coordinate you type, onto the same imagery.</p>

  <div class="tablewrap card">
  <table>
    <tr><th>Site</th><th>Owner</th><th>Village</th><th>Extent</th>
        <th>Survey</th><th>Anchor</th></tr>
    {rows}
  </table>
  </div>

  <h2>How to read the anchor column</h2>
  <div class="card"><div class="facts">{notes}</div></div>

  <footer>Generated by india_land_maps/build_site_review.py from the roster.
  Imagery &copy; Esri, Maxar, Earthstar Geographics and the GIS User
  Community.</footer>
</div>
"""


# --------------------------------------------------------------------------

def validate(roster: dict) -> list[str]:
    """Structural problems that would produce a wrong or misleading page."""
    problems = []
    seen = set()
    for i, site in enumerate(roster.get("sites", [])):
        where = site.get("key") or f"site[{i}]"
        for field in ("key", "title", "anchor"):
            if not site.get(field):
                problems.append(f"{where}: missing {field}")
        if site.get("key") in seen:
            problems.append(f"{where}: duplicate key")
        seen.add(site.get("key"))
        a = site.get("anchor") or {}
        if not isinstance(a.get("lat"), (int, float)) or not isinstance(
            a.get("lon"), (int, float)
        ):
            problems.append(f"{where}: anchor needs numeric lat and lon")
            continue
        if not -90 <= a["lat"] <= 90 or not -180 <= a["lon"] <= 180:
            problems.append(f"{where}: anchor out of range")
        prec = a.get("precision", "unknown")
        if prec not in UNCERTAINTY:
            problems.append(f"{where}: unknown precision {prec!r}")
        for c in site.get("candidates", []):
            if not all(k in c for k in ("label", "lat", "lon")):
                problems.append(f"{where}: candidate needs label, lat and lon")
        for p in site.get("plans", []):
            crop = p.get("crop")
            if crop and (len(crop) != 4 or not (0 <= crop[0] < crop[2] <= 1)
                         or not (0 <= crop[1] < crop[3] <= 1)):
                problems.append(f"{where}: bad crop {crop}")
    return problems


def build(args) -> int:
    roster = yaml.safe_load(args.roster.read_text(encoding="utf-8"))
    problems = validate(roster)
    if problems:
        for p in problems:
            print(f"[roster] {p}", file=sys.stderr)
        return 2

    sites = roster["sites"]
    out = args.out
    assets = out / "assets"
    store = TileStore(args.cache)
    index_entries, manifest = [], {}

    for i, site in enumerate(sites):
        key = site["key"]
        a = site["anchor"]
        print(f"[{key}] {site['title']}")
        site_dir = assets / key
        if site_dir.exists():
            shutil.rmtree(site_dir)

        views = []
        for name, zoom, half_m in VIEWS:
            # Esri lacks high-zoom coverage in places; a missing level comes
            # back as a flat "map data not available" tile. Step down rather
            # than shipping a grey square.
            z = zoom
            while True:
                info = build_view(store, a["lat"], a["lon"], z, half_m,
                                  site_dir / f"{name}.jpg", args.workers)
                if info["stddev"] >= BLANK_STDDEV or z <= MIN_ZOOM:
                    break
                print(f"  [view] {name}: blank at z{z} (stddev {info['stddev']}),"
                      f" stepping down to z{z - 1}")
                z -= 1
            if info["missing_tiles"] and not args.allow_missing_tiles:
                print(f"[{key}] {name}: {info['missing_tiles']} tiles could not be "
                      "fetched. Output would not be reproducible; re-run when the "
                      "network is healthy, or pass --allow-missing-tiles.",
                      file=sys.stderr)
                return 3
            info["name"] = name
            info["requested_zoom"] = zoom
            views.append(info)
            note = f", {info['missing_tiles']} tiles missing" if info["missing_tiles"] else ""
            if z != zoom:
                note += f" (requested z{zoom})"
            print(f"  [view] {name}: z{z}, {info['span_m']} m, "
                  f"{info['ground_m_per_px']} m/px{note}")

        plans = []
        for n, plan in enumerate(site.get("plans", []), 1):
            src = args.docs_root / plan["src"]
            if not src.exists():
                print(f"  [plan] MISSING {plan['src']}", file=sys.stderr)
                continue
            dst = site_dir / f"plan{n:02d}.jpg"
            crop = plan.get("crop")
            ok = (
                extract_pdf_page(src, plan["page"], dst, crop)
                if src.suffix.lower() == ".pdf"
                else copy_image(src, dst, crop)
            )
            if ok:
                plans.append({"file": dst.name, "caption": plan["caption"],
                              "sha256": sha256(dst)})
        print(f"  [plan] {len(plans)} image(s)")

        # Document links are relative to the page, so the review directory can
        # sit anywhere relative to the document tree. Resolve against the
        # PUBLISHED location, not `out` - under --verify `out` is a scratch
        # directory, and the pages must still hash the same.
        for d in site.get("docs", []):
            d["href"] = os.path.relpath(
                args.docs_root / d["path"], args.reference
            ).replace(os.sep, "/")

        prev = (sites[i - 1]["key"], sites[i - 1]["title"]) if i else None
        nxt = (sites[i + 1]["key"], sites[i + 1]["title"]) if i + 1 < len(sites) else None
        page = out / f"{key}.html"
        page.write_text(site_page(site, views, plans, prev, nxt), encoding="utf-8")

        index_entries.append({
            "key": key, "title": site["title"], "owner": site.get("owner", ""),
            "village": site.get("village", ""), "mandal": site.get("mandal", ""),
            "district": site.get("district", ""), "extent": site.get("extent", ""),
            "survey": site.get("survey", ""),
            "precision": a.get("precision", "unknown"),
        })
        manifest[key] = {
            "anchor": a,
            "candidates": site.get("candidates", []),
            "views": views,
            "plans": plans,
            "page_sha256": sha256(page),
        }

    index = out / "index.html"
    index.write_text(index_page(index_entries), encoding="utf-8")
    manifest["_index"] = {"page_sha256": sha256(index), "sites": len(sites)}

    new = json.dumps(manifest, indent=2, sort_keys=True)

    if args.verify:
        reference = args.reference / "manifest.json"
        if not reference.exists():
            print(f"[verify] no manifest.json at {reference}", file=sys.stderr)
            return 4
        old = reference.read_text(encoding="utf-8")
        if old == new:
            print(f"[verify] {len(sites)} sites rebuild byte-identical")
            return 0
        print("[verify] output DIFFERS from the recorded manifest:", file=sys.stderr)
        for key in sorted(set(json.loads(old)) | set(manifest)):
            a, b = json.loads(old).get(key), manifest.get(key)
            if a != b:
                print(f"[verify]   {key}", file=sys.stderr)
        return 4

    (out / "manifest.json").write_text(new, encoding="utf-8")
    print(f"\nWrote {len(sites)} site pages + index.html to {out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roster", type=Path, required=True,
                    help="sites.yaml describing the holdings")
    ap.add_argument("--docs-root", type=Path,
                    help="base directory that `plans` and `docs` paths are "
                         "relative to (default: the roster's parent's parent)")
    ap.add_argument("--out", type=Path,
                    help="output directory (default: the roster's directory)")
    ap.add_argument("--cache", type=Path, help="tile cache (default: <out>/_cache)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--allow-missing-tiles", action="store_true",
                    help="ship a mosaic with holes instead of failing")
    ap.add_argument("--verify", action="store_true",
                    help="rebuild and compare against the recorded manifest.json; "
                         "exit non-zero on any drift. Writes nothing new.")
    args = ap.parse_args(argv)

    args.roster = args.roster.resolve()
    args.out = (args.out or args.roster.parent).resolve()
    args.docs_root = (args.docs_root or args.roster.parent.parent).resolve()
    args.reference = args.out
    # The tile cache lives with the real output, so --verify reuses the same
    # tiles and is testing the generator, not the network.
    args.cache = (args.cache or args.out / "_cache").resolve()

    if args.verify:
        # Never write over the artefact being checked.
        with tempfile.TemporaryDirectory(prefix="site-review-verify-") as tmp:
            args.out = Path(tmp)
            return build(args)

    args.out.mkdir(parents=True, exist_ok=True)
    return build(args)


if __name__ == "__main__":
    raise SystemExit(main())
