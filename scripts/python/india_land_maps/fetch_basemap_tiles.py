#!/usr/bin/env python3
"""Download and stitch a georeferenced satellite basemap for an AOI.

Pulls ESRI World Imagery XYZ tiles, stitches them into one image per zoom level,
and writes a world file (.pgw) + .prj so the result drops straight into QGIS,
ArcGIS or Google Earth Pro already in the right place on the ground.

Requires Pillow. Run without installing anything permanently:

    uv run --with pillow --no-project \
        scripts/python/india_land_maps/fetch_basemap_tiles.py \
        --aoi config/gis/aoi/kakinada_valasapakala.yaml --zoom 16 17 18

Outputs per zoom level z (JPEG by default; --format png for lossless):
    <name>_esri_z<z>.jpg   stitched mosaic, EPSG:3857 (Web Mercator)
    <name>_esri_z<z>.jgw   world file - georeferencing for the image
    <name>_esri_z<z>.prj   CRS definition (WKT)

Drop the .jpg on a QGIS canvas and it lands in the right place automatically;
the .jgw and .prj must sit beside it with the same stem.

Ground resolution at the equator is 156543.034/2^z m/px; at latitude 17 deg it is
that times cos(17 deg) ~= 0.956. So z=18 is ~0.55 m/px - enough to read compound
walls and plot edges, which is why it is the useful level for land work.

Attribution required by the imagery licence:
    Esri, Maxar, Earthstar Geographics, and the GIS User Community
"""

from __future__ import annotations

import argparse
import math
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_osm_extract import load_aoi  # noqa: E402  (shared AOI parser)

TILE_URL = (
    "https://services.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
USER_AGENT = "assethold-gis/0.1 (+https://github.com/vamseeachanta/assethold)"
TILE_PX = 256
EARTH_CIRCUM = 40075016.68557849  # metres, WGS84 at equator
ORIGIN = EARTH_CIRCUM / 2.0  # 20037508.34 - Web Mercator origin offset


def deg2tile(lat: float, lon: float, z: int) -> tuple[int, int]:
    """Lat/lon -> XYZ tile indices (slippy-map convention)."""
    n = 2**z
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tile2merc(x: int, y: int, z: int) -> tuple[float, float]:
    """Top-left corner of a tile in EPSG:3857 metres."""
    res = EARTH_CIRCUM / (2**z)
    return -ORIGIN + x * res, ORIGIN - y * res


def fetch_tile(args: tuple[int, int, int], retries: int = 3) -> tuple[int, int, bytes | None]:
    z, x, y = args
    url = TILE_URL.format(z=z, x=x, y=y)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return x, y, resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == retries - 1:
                print(f"[tile] MISS z{z}/{x}/{y}: {exc}", file=sys.stderr)
                return x, y, None
            time.sleep(1.5 * (attempt + 1))
    return x, y, None


def build_level(
    bbox: tuple[float, float, float, float],
    z: int,
    out_stem: Path,
    workers: int = 8,
    fmt: str = "jpg",
    quality: int = 88,
) -> None:
    from PIL import Image

    south, west, north, east = bbox
    x0, y0 = deg2tile(north, west, z)  # NW corner -> min x, min y
    x1, y1 = deg2tile(south, east, z)  # SE corner -> max x, max y
    cols, rows = x1 - x0 + 1, y1 - y0 + 1
    total = cols * rows

    res = EARTH_CIRCUM / (2**z) / TILE_PX  # metres per pixel
    ground = res * math.cos(math.radians((north + south) / 2))
    print(
        f"[tile] z{z}: {cols}x{rows} = {total} tiles -> "
        f"{cols * TILE_PX}x{rows * TILE_PX} px (~{ground:.2f} m/px)"
    )

    canvas = Image.new("RGB", (cols * TILE_PX, rows * TILE_PX))
    jobs = [(z, x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]

    done = missing = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for x, y, blob in pool.map(fetch_tile, jobs):
            done += 1
            if blob is None:
                missing += 1
                continue
            try:
                tile = Image.open(BytesIO(blob)).convert("RGB")
            except Exception as exc:  # corrupt/partial tile - leave that cell black
                print(f"[tile] BAD z{z}/{x}/{y}: {exc}", file=sys.stderr)
                missing += 1
                continue
            canvas.paste(tile, ((x - x0) * TILE_PX, (y - y0) * TILE_PX))
            if done % 100 == 0 or done == total:
                print(f"[tile]   {done}/{total}")

    # JPEG by default: these mosaics run to hundreds of MB as PNG, and lossy
    # compression is fine for imagery used as a visual reference layer.
    if fmt == "png":
        img_path, world_ext = out_stem.with_suffix(".png"), ".pgw"
        canvas.save(img_path, optimize=True)
    else:
        img_path, world_ext = out_stem.with_suffix(".jpg"), ".jgw"
        canvas.save(img_path, quality=quality, subsampling=0, optimize=True)

    # World file: pixel size X, rotation, rotation, pixel size Y (negative,
    # because image rows run north->south), then the CENTRE of the top-left pixel.
    ox, oy = tile2merc(x0, y0, z)
    out_stem.with_suffix(world_ext).write_text(
        f"{res}\n0.0\n0.0\n{-res}\n{ox + res / 2}\n{oy - res / 2}\n", encoding="utf-8"
    )
    out_stem.with_suffix(".prj").write_text(
        'PROJCS["WGS 84 / Pseudo-Mercator",GEOGCS["WGS 84",DATUM["WGS_1984",'
        'SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],'
        'UNIT["degree",0.0174532925199433]],PROJECTION["Mercator_1SP"],'
        'PARAMETER["central_meridian",0],PARAMETER["scale_factor",1],'
        'PARAMETER["false_easting",0],PARAMETER["false_northing",0],'
        'UNIT["metre",1],AUTHORITY["EPSG","3857"]]',
        encoding="utf-8",
    )
    size_mb = img_path.stat().st_size / 1e6
    note = f", {missing} tiles missing" if missing else ""
    print(f"[tile] wrote {img_path} ({size_mb:.1f} MB){note}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", type=Path, required=True)
    ap.add_argument("--zoom", type=int, nargs="+", default=[16, 17])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--format", choices=("jpg", "png"), default="jpg")
    ap.add_argument("--quality", type=int, default=88, help="JPEG quality")
    args = ap.parse_args()

    aoi = load_aoi(args.aoi)
    b = aoi["bbox"]
    bbox = (b["min_lat"], b["min_lon"], b["max_lat"], b["max_lon"])
    name = aoi.get("name", "aoi")
    out_dir = args.out or Path(aoi.get("output_dir", "data/gis"))
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[tile] AOI {name} bbox={bbox}")
    for z in args.zoom:
        build_level(
            bbox,
            z,
            out_dir / f"{name}_esri_z{z}",
            workers=args.workers,
            fmt=args.format,
            quality=args.quality,
        )
    print("[tile] attribution: Esri, Maxar, Earthstar Geographics, and the GIS User Community")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
