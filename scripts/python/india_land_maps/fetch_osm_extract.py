#!/usr/bin/env python3
"""Fetch an OpenStreetMap extract for an AOI and write GeoJSON + KML.

Stdlib only - no geopandas/shapely needed, so it runs anywhere Python 3.9+ does.

Usage:
    python fetch_osm_extract.py --aoi config/gis/aoi/kakinada_valasapakala.yaml
    python fetch_osm_extract.py --bbox 16.982,82.243,17.028,82.300 --out data/gis/foo

Outputs (into the AOI's output_dir):
    <name>_osm_raw.json      Overpass response, kept verbatim for reproducibility
    <name>_osm.geojson       FeatureCollection - open in QGIS, geojson.io, Felt
    <name>_osm.kml           Same features - open in Google Earth Pro

Note on Indian cadastral data: OSM does NOT carry survey-number plot boundaries
for Andhra Pradesh. This extract gives you roads, settlements, landuse and water
- the *context* layer. Plot-level cadastre must come from BhuNaksha/FMB; see
docs/domain/realestate/re_india/india-land-records-sources.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

OVERPASS_DEFAULT = "https://overpass-api.de/api/interpreter"
# The main instance 504s under load fairly often; these mirrors run the same API.
OVERPASS_MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
USER_AGENT = "assethold-gis/0.1 (+https://github.com/vamseeachanta/assethold)"

# Feature selectors pulled for the AOI. Each becomes one Overpass clause.
SELECTORS = [
    ('node["place"]', "place"),
    ('way["boundary"]', "boundary"),
    ('rel["boundary"]', "boundary"),
    ('way["landuse"]', "landuse"),
    ('way["highway"]', "highway"),
    ('way["waterway"]', "waterway"),
    ('way["natural"="water"]', "water"),
    ('way["building"]', "building"),
]

# KML colours are aabbggrr (alpha, blue, green, red) - NOT rrggbb.
KML_STYLES = {
    "place": ("ff0000ff", 2),
    "boundary": ("ff00ffff", 3),
    "landuse": ("ff00aa00", 2),
    "highway": ("ffffffff", 2),
    "waterway": ("ffff9900", 2),
    "water": ("ffff6600", 2),
    "building": ("ffcccccc", 1),
}


def load_aoi(path: Path) -> dict:
    """Parse the small, flat subset of YAML used by the AOI configs.

    Avoids a PyYAML dependency: we only need scalars under `bbox:` and a couple
    of top-level strings, so a targeted line parser is enough and keeps this
    script runnable with a bare interpreter.
    """
    text = path.read_text(encoding="utf-8")
    aoi: dict = {}
    bbox: dict = {}
    in_bbox = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key_match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if not key_match:
            continue
        key, value = key_match.group(1), key_match.group(2).strip()
        if indent == 0:
            in_bbox = key == "bbox"
            if value:
                aoi[key] = value.strip('"')
            continue
        if in_bbox and indent == 2 and value:
            try:
                bbox[key] = float(value)
            except ValueError:
                pass
    if bbox:
        aoi["bbox"] = bbox
    return aoi


def build_query(bbox: tuple[float, float, float, float], timeout: int = 240) -> str:
    south, west, north, east = bbox
    box = f"{south},{west},{north},{east}"
    clauses = "\n  ".join(f"{sel}({box});" for sel, _ in SELECTORS)
    return f"[out:json][timeout:{timeout}];\n(\n  {clauses}\n);\nout geom;"


def run_overpass(query: str, endpoint: str) -> dict:
    """POST the query, falling back across mirrors on 429/504 and transport errors.

    `endpoint` is tried first; the remaining mirrors are tried in order after it.
    """
    endpoints = [endpoint] + [m for m in OVERPASS_MIRRORS if m != endpoint]
    last_exc: Exception | None = None
    for attempt, url in enumerate(endpoints, 1):
        req = urllib.request.Request(
            url,
            data=query.encode("utf-8"),
            headers={"User-Agent": USER_AGENT, "Content-Type": "text/plain"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_exc = exc
            print(f"[osm]   {url} -> {exc}; trying next mirror", file=sys.stderr)
            if attempt < len(endpoints):
                time.sleep(5 * attempt)  # back off before hitting the next mirror
    raise RuntimeError(f"all Overpass endpoints failed; last error: {last_exc}")


def classify(tags: dict) -> str:
    for _, label in SELECTORS:
        if label == "water" and tags.get("natural") == "water":
            return "water"
        if label in tags:
            return label
    return "other"


def to_geojson(elements: list[dict]) -> dict:
    features = []
    for el in elements:
        tags = el.get("tags") or {}
        etype = el.get("type")

        if etype == "node" and "lat" in el:
            geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
        elif etype in ("way", "relation") and el.get("geometry"):
            coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
            if len(coords) < 2:
                continue
            # A way that returns to its start is an area, not a line.
            if coords[0] == coords[-1] and len(coords) >= 4:
                geom = {"type": "Polygon", "coordinates": [coords]}
            else:
                geom = {"type": "LineString", "coordinates": coords}
        else:
            continue

        features.append(
            {
                "type": "Feature",
                "id": f"{etype}/{el.get('id')}",
                "geometry": geom,
                # OSM has its own `layer` tag (bridges/tunnels use layer=1/-1),
                # so ours is namespaced to avoid being clobbered by **tags.
                "properties": {
                    **tags,
                    "osm_type": etype,
                    "osm_id": el.get("id"),
                    "feature_class": classify(tags),
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _kml_coords(coords) -> str:
    return " ".join(f"{lon},{lat},0" for lon, lat in coords)


def to_kml(geojson: dict, doc_name: str) -> str:
    """Group features into one KML Folder per layer so they toggle independently."""
    by_layer: dict[str, list] = {}
    for feat in geojson["features"]:
        by_layer.setdefault(feat["properties"].get("feature_class", "other"), []).append(feat)

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
        f"<name>{escape(doc_name)}</name>",
    ]
    for layer, (colour, width) in KML_STYLES.items():
        out.append(
            f'<Style id="{layer}"><LineStyle><color>{colour}</color>'
            f"<width>{width}</width></LineStyle>"
            f"<PolyStyle><color>4d{colour[2:]}</color></PolyStyle></Style>"
        )

    for layer, feats in sorted(by_layer.items()):
        out.append(f"<Folder><name>{escape(layer)} ({len(feats)})</name>")
        for feat in feats:
            props = feat["properties"]
            name = props.get("name") or props.get("feature_class") or "feature"
            desc = "\n".join(
                f"{k}: {v}"
                for k, v in props.items()
                if k not in ("feature_class", "osm_type", "osm_id")
            )
            geom = feat["geometry"]
            out.append(
                f"<Placemark><name>{escape(str(name))}</name>"
                f"<styleUrl>#{layer}</styleUrl>"
                f"<description>{escape(desc)}</description>"
            )
            if geom["type"] == "Point":
                lon, lat = geom["coordinates"]
                out.append(f"<Point><coordinates>{lon},{lat},0</coordinates></Point>")
            elif geom["type"] == "LineString":
                out.append(
                    "<LineString><tessellate>1</tessellate><coordinates>"
                    f"{_kml_coords(geom['coordinates'])}</coordinates></LineString>"
                )
            else:
                out.append(
                    "<Polygon><outerBoundaryIs><LinearRing><coordinates>"
                    f"{_kml_coords(geom['coordinates'][0])}"
                    "</coordinates></LinearRing></outerBoundaryIs></Polygon>"
                )
            out.append("</Placemark>")
        out.append("</Folder>")

    out.append("</Document></kml>")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", type=Path, help="AOI YAML under config/gis/aoi/")
    ap.add_argument("--bbox", help="south,west,north,east (overrides AOI)")
    ap.add_argument("--out", type=Path, help="output dir (overrides AOI)")
    ap.add_argument("--name", help="output file stem (overrides AOI)")
    ap.add_argument("--endpoint", default=OVERPASS_DEFAULT)
    args = ap.parse_args()

    aoi = load_aoi(args.aoi) if args.aoi else {}

    if args.bbox:
        bbox = tuple(float(x) for x in args.bbox.split(","))
    elif "bbox" in aoi:
        b = aoi["bbox"]
        bbox = (b["min_lat"], b["min_lon"], b["max_lat"], b["max_lon"])
    else:
        ap.error("need --bbox or an --aoi that defines one")

    name = args.name or aoi.get("name", "aoi")
    out_dir = args.out or Path(aoi.get("output_dir", "data/gis") )
    out_dir.mkdir(parents=True, exist_ok=True)

    query = build_query(bbox)
    print(f"[osm] AOI {name} bbox={bbox}")
    print(f"[osm] querying {args.endpoint} ...")
    try:
        data = run_overpass(query, args.endpoint)
    except (urllib.error.URLError, RuntimeError) as exc:
        print(f"[osm] FAILED: {exc}", file=sys.stderr)
        return 1

    elements = data.get("elements", [])
    print(f"[osm] {len(elements)} elements returned")

    raw_path = out_dir / f"{name}_osm_raw.json"
    raw_path.write_text(json.dumps(data), encoding="utf-8")

    geojson = to_geojson(elements)
    gj_path = out_dir / f"{name}_osm.geojson"
    gj_path.write_text(json.dumps(geojson, indent=1), encoding="utf-8")

    kml_path = out_dir / f"{name}_osm.kml"
    kml_path.write_text(to_kml(geojson, name), encoding="utf-8")

    counts: dict[str, int] = {}
    for feat in geojson["features"]:
        layer = feat["properties"].get("feature_class", "other")
        counts[layer] = counts.get(layer, 0) + 1
    print(f"[osm] {len(geojson['features'])} features by layer:")
    for layer, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"        {n:6d}  {layer}")
    for p in (raw_path, gj_path, kml_path):
        print(f"[osm] wrote {p}  ({p.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
