# Valasapakala GP, Kakinada — map dossier

> **Compiled**: 2026-08-03
> **Portal access reflects**: 2026-08-03 probe — see
> [`portal-status-log.md`](./portal-status-log.md)
> **Imagery captured**: 2026-08-03 (ESRI World Imagery; Esri's own capture date
> for these tiles is not exposed by the tile API — treat the scene as "recent,
> undated" and re-pull before relying on it to show current construction)
>
> Sections below marked *blocked* were blocked **from a US network on that date**.
> Re-run the probe before assuming they still are.

**AOI**: `config/gis/aoi/kakinada_valasapakala.yaml`
**Data**: `data/gis/kakinada_valasapakala/`

---

## Administrative identity

| Field | Value |
|---|---|
| State | Andhra Pradesh (LGD code 28) |
| District | **Kakinada** (carved out of East Godavari, Apr 2022) |
| District (pre-2022) | East Godavari |
| Mandal | Kakinada Rural |
| Gram Panchayat | Valasapakala |
| Revenue villages under GP | includes **Vakalapudi** |
| PIN | 533005 |
| Anchor point | 16.9963762 N, 82.2563312 E (OSM node `12496017004`) |

Valasapakala sits on the **north-east urban fringe of Kakinada city**, between
the built-up city and the coast. Vakalapudi (lighthouse at 17.0145 N, 82.2827 E)
lies ~3 km NE of the Valasapakala settlement centre — the two anchor opposite
ends of the panchayat.

There is a naming trap here: *Valasapakala* also appears as a **locality name
inside Kakinada city** (Ramanayapeta area) in some directories, and third-party
sites variously file the panchayat under "Kakinada" or "Kakinada Rural" mandal.
Confirm which one a document means before acting on it.

### Boundary caveat

**No authoritative Valasapakala GP boundary polygon is available in any openly
accessible dataset.** OSM has the place only as a single node — no boundary way,
no relation. The AOI bbox below is a working envelope chosen to contain the
settlement, Vakalapudi and the coastal strip. It is **not a legal boundary** and
must not be presented as one.

```
bbox:  16.982 N – 17.028 N,  82.243 E – 82.300 E   (~5.1 km N-S × 6.1 km E-W)
```

---

## What is in `data/gis/kakinada_valasapakala/`

### Satellite basemaps (ESRI World Imagery, EPSG:3857)

| File | Dimensions | Resolution | Size |
|---|---|---|---|
| `..._esri_z16.jpg` | 3072 × 2560 | ~2.28 m/px | 1.6 MB |
| `..._esri_z17.jpg` | 5632 × 4864 | ~1.14 m/px | 5.2 MB |
| `..._esri_z18.jpg` | 11008 × 9216 | ~0.57 m/px | 16.8 MB |

Each has a matching `.jgw` (world file) and `.prj` (CRS). **Keep the three files
together with the same stem** — drop the `.jpg` on a QGIS canvas and it lands in
the correct ground position automatically.

Georeferencing was verified two ways: reference points (Valasapakala node,
Vakalapudi lighthouse, both AOI corners) reproject to the expected pixel
positions, and a visual crop at the anchor point shows the expected dense
plot-and-compound settlement fabric.

At z18 you can make out individual compound walls, roof outlines and road
frontages — enough to sanity-check a sketch against the ground, spot new
construction, and see where a layout has been cut.

Attribution required: *Esri, Maxar, Earthstar Geographics, and the GIS User Community*.

### Vector context (OpenStreetMap)

| File | Contents |
|---|---|
| `..._osm.geojson` | 2,218 features — open in QGIS, geojson.io, Felt |
| `..._osm.kml` | same features, foldered by class — Google Earth Pro |
| `..._osm_raw.json` | verbatim Overpass response, kept for reproducibility |

Feature breakdown: 1,624 highway · 538 building · 29 place · 18 landuse ·
5 water · 4 waterway.

**No cadastral parcels.** OSM does not carry survey-number boundaries for AP.
This is the context layer — roads, built-up footprint, water — not a plot map.

---

## Regenerating

```bash
# vector context (stdlib only)
python3 scripts/python/india_land_maps/fetch_osm_extract.py \
    --aoi config/gis/aoi/kakinada_valasapakala.yaml

# satellite mosaics (Pillow via uv, nothing installed permanently)
uv run --with pillow --no-project \
    scripts/python/india_land_maps/fetch_basemap_tiles.py \
    --aoi config/gis/aoi/kakinada_valasapakala.yaml --zoom 16 17 18
```

Both scripts are AOI-driven — point them at a different YAML in
`config/gis/aoi/` to cover another village with no code changes.

---

## What is still missing, and how to get it

Everything below was **blocked from a US network on 2026-08-03**. Re-check with
`python3 scripts/python/india_land_maps/probe_portals.py` before acting — see
[`india-land-records-sources.md`](./india-land-records-sources.md) for why each
one behaves the way it does.

### 1. Plot-level cadastre (FMB / village map) — the thing that actually matters

BhuNaksha AP is login-gated; its whole REST layer refuses anonymous access.
Routes, in order of practicality:

- **MeeSeva centre or Village Secretariat**, Kakinada Rural — request FMB /
  village map by survey number. Produces a stamped copy, which is what any
  transaction or dispute will require.
- **BhuNaksha citizen login** — needs an Indian mobile number for OTP.
- **Mandal Surveyor / MRO, Kakinada Rural** — office of record for FMB sheets
  and post-survey sub-division sketches.
- **Licensed surveyor** — for on-ground demarcation. Necessary if boundaries are
  contested or the plot was sub-divided after the last survey.

To make any of these efficient, have the **survey numbers** in hand first —
without them the offices cannot pull anything.

### 2. Kakinada master plan / zonal development plan

KAUDA (`kauda.ap.gov.in`) is the authority covering Valasapakala. The host is
**geo-blocked** — TCP times out from the US — and has **no Wayback snapshots**,
so there is no archival fallback. Needs an Indian connection:

- `https://kauda.ap.gov.in/documents/MasterPlans/KakinadaMasterPlan.pdf`
- `https://kauda.ap.gov.in/documents/downloads/KAKINADA_ZDp_2040-compressed.pdf`

This matters commercially: the zoning designation (residential / commercial /
industrial / green / coastal-regulation) drives value and buildability on the
Kakinada fringe far more than raw location does.

### 3. Approved-layout status

DTCP's published layout links are broken (both 404 as of 2026-08-03) and APDPMS'
public list endpoints are port-blocked externally. For a specific plot, the
reliable check is to ask the **KAUDA planning wing** directly whether the survey
number falls in an approved layout, and to get the LP (layout permit) number.

Unapproved-layout exposure is a real risk on the Kakinada fringe — an
LRS/BPS-pending plot carries regularisation cost and transfer friction.

### 4. Coastal Regulation Zone

Vakalapudi is coastal. CRZ classification constrains construction near the
shoreline and is a separate approval track (`apczma.ap.gov.in`). Anything in the
eastern part of this AOI should be CRZ-checked before it is treated as
developable.
