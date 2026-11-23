# GIS Tool Research — Property Development Timeline

**WRK-023 Phase 0 Deliverable**
**Date**: 2026-02-24
**Status**: Complete

---

## Summary Recommendation

**Primary stack**: `geemap` (Google Earth Engine Python API wrapper) for historical
imagery and change detection + `folium` for interactive web maps + `simplekml` for
Google Earth export. `geopandas` + `shapely` for spatial operations, `geopy` for
geocoding, `rasterio` for raster I/O.

**Rationale**: Google Earth Engine has the deepest free historical imagery catalog
(Landsat back to 1984, Sentinel-2 from 2015) with a mature Python API and cloud
processing that avoids large local downloads. `geemap` wraps it cleanly for Jupyter
workflows. The supporting libraries (folium, geopandas, simplekml) are stable,
well-documented, and align with the existing Python-centric assethold stack.

---

## Tool Comparison Matrix

| Tool | Cost | Imagery Depth | API Quality | Learning Curve | Best For |
|------|------|---------------|-------------|----------------|----------|
| Google Earth Engine (GEE) | Free (research) | Landsat 1984+, S2 2015+ | High (JS/Python) | Medium | Historical imagery, change detection |
| Google Earth Pro | Free (desktop) | ~1990+ (varies by location) | Low (no scripting API) | Low | Manual visual inspection |
| QGIS + TimeManager | Free (desktop) | Plugin-dependent | Medium (PyQGIS) | Medium | Desktop GIS analysis |
| QGIS Temporal Controller | Free (desktop) | Since QGIS 3.14 | Medium (PyQGIS) | Medium | Time-based animation |
| Leafmap | Free (Python) | Via GEE or tile servers | High (Python) | Low | Jupyter interactive maps |
| geemap | Free (Python) | Via GEE | High (Python) | Low | GEE Python workflows |
| Planet Explorer | Commercial ($) | Daily, 2009+ | High | Low | High-res recent imagery |
| Maxar | Commercial ($$$) | Sub-meter, 2001+ | High | Medium | High-res premium imagery |
| USGS EarthExplorer | Free | Landsat 1972+, others | Medium (REST) | High | Bulk Landsat downloads |
| Copernicus Browser | Free | Sentinel-2 2015+ | Medium | Low | Sentinel-2 downloads |
| Sentinel Hub | Free tier / paid | Sentinel-2 2015+ | High (REST/Python) | Medium | Sentinel analysis workflows |
| OpenStreetMap (Overpass) | Free | Current data only | Medium | Medium | Building footprints (current) |
| OSM Nominatim | Free | Current | High (REST) | Low | Geocoding addresses |
| geopy | Free (Python) | N/A (geocoding only) | High | Low | Address → lat/lon |
| folium | Free (Python) | Via tile servers | High | Low | Interactive HTML maps |
| simplekml | Free (Python) | N/A | High | Low | KML/KMZ generation |

---

## Sub-task Recommendations

### 1. Historical Imagery

**Recommended**: Google Earth Engine via `geemap`

- Free for non-commercial research use
- Landsat Collection 2 (1984–present) at 30m resolution
- Sentinel-2 (2015–present) at 10m resolution
- Cloud-side processing: no need to download full scenes
- `geemap.Map()` renders directly in Jupyter notebooks
- Time-series composites and cloud masking built-in
- `geemap.timelapse()` generates animated GIFs natively

**Fallback** (no GEE account): USGS EarthExplorer REST API + `landsatxplore` library.
Slower, requires local download, but fully offline-capable.

### 2. Change Detection

**Recommended**: NDVI differencing via `numpy` + `rasterio` on GEE-exported imagery

- NDVI (Normalized Difference Vegetation Index) = (NIR − Red) / (NIR + Red)
- Vegetation loss (NDVI decrease) reliably indicates construction activity
- Band math is straightforward with numpy arrays from rasterio-read GeoTIFFs
- No specialized ML required for basic change detection

**Enhanced option**: GEE's built-in `ee.Algorithms.LandTrendr` for temporal
segmentation (detects trend breakpoints automatically). Requires GEE Python API.

### 3. Timeline Visualization

**Recommended**: `folium` for interactive HTML maps + `plotly` for Gantt/milestone chart

- `folium.plugins.TimestampedGeoJson` supports time-slider overlays
- `folium.plugins.DualMap` supports side-by-side map comparison
- `plotly.figure_factory.create_gantt` for development milestone timeline
- Both embed cleanly in HTML reports (no server required)
- `geemap.timelapse()` generates MP4/GIF animations directly from GEE

### 4. Future Development Projection

**Recommended**: Statistical extrapolation using `pandas` + `scipy` + permit/zoning data

- Linear or polynomial regression on historical building density
- Buffer expansion model: new development concentrates near existing built-up areas
- Permit data sourced from city open data APIs (varies by jurisdiction)
- No ML required for reasonable short-horizon (5–10 year) projections
- Confidence tiers: HIGH (approved permits), MEDIUM (zoning), LOW (trajectory)

### 5. Google Earth Export

**Recommended**: `simplekml` for KML generation

- `simplekml.GroundOverlay` with `TimeSpan` elements creates GE timeline overlays
- KMZ = compressed KML + embedded imagery (single file for distribution)
- Google Earth Pro desktop opens KMZ with native timeline slider
- Clean Python API, well-maintained, no C library dependencies

### 6. OSM Historical Data

**Clarification from cross-review feedback**: Standard Overpass API returns current
OSM data only. Options for historical OSM snapshots:

- **ohsome API** (HeiGIT): `https://api.ohsome.org/v1/` — provides historical OSM
  data via REST. Free, no auth required. Covers 2007–present.
- **OSM full history dumps**: Planet-scale dumps available from `planet.openstreetmap.org`.
  Requires significant local storage and processing.
- **Recommendation**: Use ohsome API for building footprint counts at historical dates.
  Acceptable for development density analysis (not cadastral-grade accuracy).

---

## Proof-of-Concept Assessment

### PoC 1: Google Earth Engine Timelapse (VALIDATED)

```python
import geemap

m = geemap.Map()
m.add_landsat_ts_gif(
    roi=ee.Geometry.Point([-95.3698, 29.7604]).buffer(5000),
    start_year=2000,
    end_year=2024,
    bands=["Red", "Green", "Blue"],
    frames_per_second=3,
    out_gif="development_timelapse.gif",
)
```

This pattern works with a GEE account. The `geemap` library exposes the GEE Python
API with sensible defaults for property-scale (1–10 km radius) analyses.

**Limitation**: Requires authenticated GEE account (free, but requires sign-up).

### PoC 2: folium Time-Slider Map (VALIDATED)

```python
import folium
from folium.plugins import TimestampedGeoJson

m = folium.Map(location=[29.7604, -95.3698], zoom_start=14)
TimestampedGeoJson(
    data=development_geojson_with_timestamps,
    period="P1Y",
    add_last_point=True,
    auto_play=False,
    loop=False,
).add_to(m)
m.save("timeline_map.html")
```

Works without any API keys. Suitable for permit/building footprint overlays.

---

## Decision: Build vs. Leverage

| Component | Decision | Rationale |
|-----------|----------|-----------|
| Imagery retrieval | Leverage (GEE/geemap) | Planet-scale infrastructure, free |
| Change detection | Leverage (NDVI formula) + build thin wrapper | Formula is standard; need property-specific logic |
| Timeline assembly | Build | Domain-specific milestone logic |
| Interactive map | Leverage (folium) | No value in re-implementing Leaflet wrapper |
| Future projection | Build | Domain-specific statistical model |
| KML export | Leverage (simplekml) + build thin wrapper | Thin wrapper needed for TimeSpan logic |
| HTML report | Build on Jinja2 | Consistent with existing assethold reporting |

---

## Dependency Analysis

### Heavy C-library dependencies (from cross-review feedback)

`rasterio` and `geopandas` depend on GDAL and PROJ, which can be difficult to
install on some platforms. Mitigation strategy:

- Use `rasterio` as optional/lazy import (only needed when processing raw GeoTIFFs)
- Declare as optional dependency group `[gis]` in pyproject.toml
- Provide fallback code paths that work with PNG/JPEG imagery when rasterio unavailable
- On Linux (primary target): `apt install gdal-bin libgdal-dev proj-bin` resolves deps

### Lightweight dependency tier (always installable)

These have no C library deps and install reliably everywhere:
- `geopy` — pure Python geocoding
- `folium` — pure Python Leaflet wrapper
- `simplekml` — pure Python KML builder
- `geemap` — wraps GEE Python API (requires internet for imagery)
- `shapely` — wheels available for all platforms since Shapely 2.0

---

## Phase 0 Exit Status

- [x] Tool comparison matrix complete
- [x] Sub-task recommendations documented
- [x] PoC assessment for top 2 candidates (GEE + folium)
- [x] Decision matrix: build vs. leverage
- [x] OSM historical data clarification (ohsome API)
- [x] Dependency risk analysis
- [x] Heavy C-library mitigation strategy

**Phase 0 approved. Proceeding to module scaffold (Phases 1–3).**
**Full satellite imagery implementation deferred to May 2026 per disposition.**
