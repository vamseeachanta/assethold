# Valasapakala GP, Kakinada — map data

Full write-up: `docs/domain/realestate/re_india/kakinada-valasapakala.md`
AOI definition: `config/gis/aoi/kakinada_valasapakala.yaml`

## Tracked in git

| File | What |
|---|---|
| `kakinada_valasapakala_osm.geojson` | 2,218 OSM features (roads, buildings, landuse, water, places) |
| `kakinada_valasapakala_osm.kml` | same, foldered by class, for Google Earth Pro |

OpenStreetMap data © OpenStreetMap contributors, ODbL.

## Not tracked — regenerate locally

The satellite mosaics (`*_esri_z16/17/18.jpg` + `.jgw` + `.prj`) and the raw
Overpass response are gitignored: they are large, fully regenerable, and the
mosaics are derived ESRI imagery that should not be redistributed from a public
repository.

```bash
# from the repo root
python3 scripts/python/india_land_maps/fetch_osm_extract.py \
    --aoi config/gis/aoi/kakinada_valasapakala.yaml

uv run --with pillow --no-project \
    scripts/python/india_land_maps/fetch_basemap_tiles.py \
    --aoi config/gis/aoi/kakinada_valasapakala.yaml --zoom 16 17 18
```

Mosaics are EPSG:3857 with world files — keep each `.jpg`, `.jgw` and `.prj`
together with the same stem and QGIS will place them automatically.

Imagery attribution: *Esri, Maxar, Earthstar Geographics, and the GIS User Community*.

## Reality check

These are **contextual** maps. Neither OSM nor satellite imagery carries
survey-number plot boundaries for Andhra Pradesh. Cadastral records (FMB /
village map) must come from BhuNaksha citizen login, MeeSeva, or the Kakinada
Rural Mandal Surveyor — see `docs/domain/realestate/re_india/india-land-records-sources.md`.
