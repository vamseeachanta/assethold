# Land imagery review — generator

> **First compiled**: 2026-08-04
> **Tool**: [`scripts/python/india_land_maps/build_site_review.py`](../../../../scripts/python/india_land_maps/build_site_review.py)
> **Tests**: [`tests/test_site_review.py`](../../../../tests/test_site_review.py) — 54 unit tests, no network
>
> This page explains *why the tool is shaped this way*. How to run it against a
> particular set of holdings belongs with that roster, not here.

Takes a roster of land holdings and produces a browsable site: satellite
imagery at three fixed scales per holding, the plan and route-map images lifted
out of the deed scans, and one page per site.

## The split: code here, roster elsewhere

This repository is **public**. Land rosters are not — a roster carries survey
numbers, registration document numbers, extents, and the names of adjoining
owners. So:

| | Lives in | Why |
|---|---|---|
| Generator, tests, this doc | `assethold` (public) | Versioned, tested, reusable |
| `sites.yaml` roster | The private repo holding the deeds | Personally identifying |
| Generated HTML + imagery | Beside the roster | Derived from private data |

The generator takes `--roster`, `--docs-root` and `--out`, so it has no
knowledge of any particular dataset. Nothing about a specific holding is
hardcoded, and nothing should be added.

## Anchor precision is the product

Most of these parcels **cannot be pointed at**. The deed gives a village and a
survey number; the survey number cannot be resolved to a polygon without an FMB
from the mandal surveyor. A map pin that does not say how confident it is will
be read as a boundary, and that is the failure this tool exists to prevent.

Every anchor declares a precision, which drives a dashed uncertainty ring drawn
to scale on all three views:

| Precision | Ring | Means |
|---|---|---|
| `exact` | 30 m | A map placemark on the property itself |
| `locality` | 400 m | Right colony or street; plot is somewhere inside |
| `village` | 1000 m | Revenue village centre only |
| `unknown` | 3000 m | Could not be geocoded. A search box, not a location |

A roster may override the radius with `uncertainty_m` when the real bound is
known — e.g. a site known to front a specific 1.06 km road gets 700 m, not the
generic 400 m.

`validate()` **rejects an unrecognised precision** rather than defaulting.
Defaulting would silently understate how badly a plot is located, which is the
one error mode that matters here.

Satellite imagery is never a boundary. The footer of every page says so.

## Determinism

The point of moving this out of a scratch script: same roster + same tile cache
must produce the same bytes, and that must be *checkable*.

- **`manifest.json`** records a SHA-256 for every generated image and page.
- **`--verify`** rebuilds into a temporary directory and diffs against the
  recorded manifest, naming the sites that drifted, and exits non-zero. It
  writes nothing to the published output.
- **Tile cache** (`<out>/_cache`, gitignore it) is shared by build and verify,
  so `--verify` tests the generator rather than the network.
- **A missing tile fails the run** (exit 3) instead of shipping a mosaic with
  black holes in it. `--allow-missing-tiles` overrides when you need it.

Two traps found by `--verify` itself, both worth knowing:

1. **Relative document links must resolve against the published output
   directory, not `out`.** Under `--verify`, `out` is a scratch directory;
   resolving there changed every page's hash and reported false drift.
2. **Nothing may embed a timestamp, a run id, or a path that varies.** The
   manifest is the contract; anything ambient in the output breaks it.

## Imagery

Tiles come from ESRI World Imagery. The Web Mercator and tile-indexing maths is
**imported from `fetch_basemap_tiles`, not restated** — a sign error or a
half-pixel offset silently puts a mosaic in the wrong place on the ground while
the output still looks fine. One implementation, one test suite.

Three fixed scales per site, so sites are comparable side by side:

| View | Zoom | Span | Ground resolution |
|---|---|---|---|
| Context | 16 | ~4 km | ~2.3 m/px |
| Site | 18 | ~1.2 km | ~0.57 m/px |
| Close | 19 | ~400 m | ~0.29 m/px |

**Esri coverage is not uniform.** Rural Telangana and Korukonda have no z19;
the server returns a flat "map data not available" tile. The builder detects
this by greyscale standard deviation (below 8 on a 64×64 downsample), steps
down a zoom level, and discloses the substitution in the view's caption rather
than shipping a grey square.

The half-width is in **ground** metres, so `view_box()` divides by `cos(lat)`
to get Web Mercator metres. Dropping that correction makes every view ~5% too
small at Andhra latitudes — small enough to look right, large enough to matter.
It is tested directly.

## The position picker

Each page carries a **Try a different position** control: a dropdown of
candidate anchors from the roster, plus free coordinate entry. Selecting one
drops a probe on all three views with distance and bearing from the published
anchor.

This exists because the hard cases are **disputes between sources** — a
gazetteer centroid against a deed's route map, a folder name against its own
survey certificate. Listing the losing candidates alongside the chosen one, and
letting a reader put each on the imagery, is more honest than silently picking
one. Rejected candidates stay in the roster labelled as rejected.

It works with **no network calls at all** — each view's exact Web Mercator
extent is baked into the page, so a coordinate is placed by interpolation. That
means it works offline and over `file://`, and it cannot leak which parcels are
being looked at to a tile server. The cost is that place names cannot be
resolved; the page says so plainly instead of failing quietly.

Accepted input: decimal (`16.9886, 82.2488`) and the DMS form the deeds
themselves use (`16°59'25.7"N 82°15'37.7"E`). A point outside a given view is
labelled "outside this view" rather than clamped to the edge, which would put a
marker somewhere the point is not.

## Identity documents

Indian deed scans routinely include Aadhaar cards, PAN cards, passport
photographs and fingerprints — often on pages adjacent to the plan you want.
The generator only ever renders pages a roster **names explicitly**; it never
sweeps a PDF. Anyone adding a `plans:` entry must look at the page first. This
is a convention the tool cannot enforce, so it is stated on every generated
page and in every roster template.

## Roster shape

```yaml
sites:
  - key: short_slug                 # unique; becomes <key>.html
    title: Human readable
    owner: OWNER                    # free-text grouping
    village: ...
    mandal: ...
    district: ...
    state: ...
    pincode: "533005"
    extent: ...
    survey: ...
    deeds: ...
    status: ...
    anchor:
      lat: 16.9886
      lon: 82.2488
      precision: locality           # exact | locality | village | unknown
      uncertainty_m: 700            # optional override
      source: "where this came from, and what it is not"
    candidates:                     # optional competing positions
      - {label: "...", lat: 0.0, lon: 0.0, source: "..."}
    ground_handles:                 # how to recognise it on the ground
      - "..."
    plans:                          # images to show
      - {src: relative/path.pdf, page: 7, crop: [0.0, 0.0, 1.0, 0.55],
         caption: "..."}
    docs:                           # links to sources
      - {path: relative/path.pdf, label: "..."}
    next_steps:                     # optional, for unresolved sites
      - "..."
```

`src` and `path` are relative to `--docs-root`. `page` applies to PDFs only and
extracts the largest embedded image on that page — deed scans have no text
layer. `crop` is fractions of width/height as `[left, top, right, bottom]`;
`validate()` rejects inverted or out-of-range boxes.

## Known limits

- **No text layer in deed scans.** Pages are extracted as images; there is no
  OCR step, and Telugu handwriting would defeat one anyway. Reading the route
  maps is manual work, and it is where the real location information is.
- **`page.images` takes the largest embedded image**, which is right for a
  single-image scan and wrong for a composited page. Check the output.
- **Coverage and vintage of Esri imagery are not controlled.** A layout
  approved in 2021 may not appear on imagery captured earlier.
- **The picker cannot geocode.** By design — see above.

## Related

- [`india-land-records-sources.md`](./india-land-records-sources.md) — which
  official portals actually answer, and from where
- [`kakinada-valasapakala.md`](./kakinada-valasapakala.md) — the AOI-driven
  fetchers this tool sits beside
