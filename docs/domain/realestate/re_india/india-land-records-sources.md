# India land records & mapping — source register (Andhra Pradesh focus)

**Status of every portal below was probed directly on 2026-08-03** from a US
network. Reachability is stated as observed, not as advertised. Several AP
government hosts are firewalled to Indian IP ranges — that is called out
explicitly because it changes *who* has to do the fetching, not *whether* the
data exists.

---

## The core distinction

Indian land mapping splits into two tiers that are constantly conflated:

| Tier | What it is | Legal weight | Openly downloadable? |
|---|---|---|---|
| **Cadastral** | Survey-number plot boundaries, FMB (Field Measurement Book) sketches, village maps | Authoritative for boundaries | **No** — login-gated |
| **Contextual** | Satellite imagery, roads, settlement footprint, zoning/master plans | Reference only | **Yes** — see below |

Anything you can download without authentication is **tier 2**. It shows you
where things are and what the ground looks like. It does **not** establish a
plot boundary, and no amount of satellite resolution substitutes for an FMB or a
licensed surveyor's demarcation.

---

## Tier 1 — cadastral (survey-number level)

### BhuNaksha AP — `bhunaksha.ap.gov.in`

The authoritative AP cadastral viewer. **Login-gated as of 2026-08-03.**

Observed behaviour:
- `https://bhunaksha.ap.gov.in/` → 302 → `/bhunakshalpm/` → `/bhunakshalpm/28/index.jsp`
  (28 = LGD state code for Andhra Pradesh)
- The landing page offers only **Citizen Login** and **Officer Login**.
- Every REST endpoint (`/rest/MapInfo/getDistrictCodes`, `getMapContent`,
  `getPlotInfo`, `/rest/Urban/getDashboardIndex`, …) returns a generic error
  page without a session. There is no anonymous district/mandal/village
  dropdown flow any more.

Older guides — and the large cluster of SEO sites (`meebhoomiap.com`,
`meebhoomi.net.in`, `bhulekhindia.in`, and similar) that still describe an open
"select District → Mandal → Village" flow — are **out of date**. Those sites are
not government properties; do not rely on them.

To actually obtain a plot map you need one of:
1. **Citizen login** on BhuNaksha (Indian mobile number for OTP).
2. **MeeSeva / Village Secretariat counter** — request the FMB / village map for
   the survey number. This is the normal route and produces a stamped copy,
   which is what matters for any transaction.
3. **Mandal Surveyor / MRO office** for Kakinada Rural mandal — the office of
   record for FMB sheets and for sub-division sketches.
4. **Licensed surveyor** for an on-ground demarcation. Required if boundaries
   are disputed or the plot has been sub-divided since the last survey.

### MeeBhoomi — `meebhoomi.ap.gov.in`

Adangal / 1-B / ROR records. **Fully login-gated as of 2026-08-03.**

Every path tested (`/VillageMap.aspx`, `/Home/VillageMap`, `/Adangal/Adangal`,
`/VillageMap/VillageMap`) returns the identical 82,585-byte login page — the app
serves a catch-all redirect, so a `200 OK` here does **not** mean the page
exists. Same access routes as BhuNaksha above.

### Not live

- `bhubharati.ap.gov.in` / `bhubharathi.ap.gov.in` — **do not resolve** (no DNS
  record). "Bhu Bharati" is the Telangana-adjacent branding; it is not a live AP
  hostname. Do not cite it.
- `webland.ap.gov.in` and `ccla.ap.gov.in` respond (200) but are departmental
  landing pages, not public map services.

---

## Tier 2 — contextual (openly downloadable)

### ESRI World Imagery — recommended, automated here

XYZ tiles at `services.arcgisonline.com/.../World_Imagery/MapServer/tile/{z}/{y}/{x}`.
No key, no login. At z=18 the ground resolution is ~0.57 m/px at this latitude —
enough to read compound walls, roof outlines and the *visible* plot fabric.

Automated by `scripts/python/india_land_maps/fetch_basemap_tiles.py`, which
stitches a mosaic and writes a world file so it is georeferenced.

**Attribution is required**: *Esri, Maxar, Earthstar Geographics, and the GIS
User Community*. Caching for personal/internal reference is fine; republishing
the stitched mosaic is a different question — keep these out of public repos.

### OpenStreetMap (Overpass API)

Free, no key. Gives roads, buildings, landuse, water, place names.

**Important limitation**: OSM carries **no survey-number parcels** for Andhra
Pradesh, and for Valasapakala specifically there is no boundary polygon at all —
only a single `place=neighbourhood` node (OSM node `12496017004`). Do not expect
a panchayat boundary from OSM here.

Automated by `scripts/python/india_land_maps/fetch_osm_extract.py`.

### Bhuvan / SISDP — `bhuvanpanchayat.nrsc.gov.in`

ISRO's "Space-based Information Support for Decentralised Planning", v4.0 —
explicitly panchayat-level geospatial products (thematic layers, land use / land
cover, infrastructure). Reachable (200). Bulk download generally requires a free
NRSC account. This is the best *official* source for panchayat-scale thematic
mapping, and worth an account if this work continues.

`bhuvan.nrsc.gov.in` (main portal) also reachable.

---

## Zoning & layout approvals

### KAUDA — `kauda.ap.gov.in` — **geo-blocked**

Kakinada Urban Development Authority. This is the correct authority for the
Kakinada master plan and for approved layouts in the Kakinada urban fringe,
**including Valasapakala**.

- DNS resolves (`164.100.192.133`) but TCP connections **time out** from a US
  network, on both 80 and 443. Not a bad path — the host is unreachable.
- **No Wayback Machine snapshots exist** (`archive.org/wayback/available`
  returns an empty `archived_snapshots` object, and a CDX query for PDFs under
  `kauda.ap.gov.in` returns nothing). There is no archival fallback.

Two documents are known to exist and are worth retrieving from an Indian
connection:
- `https://kauda.ap.gov.in/documents/MasterPlans/KakinadaMasterPlan.pdf`
- `https://kauda.ap.gov.in/documents/downloads/KAKINADA_ZDp_2040-compressed.pdf`
  (Zonal Development Plan 2040)

**Action required**: someone on an Indian network (or an Indian VPN egress)
must fetch these. They cannot be obtained from here.

### DTCP AP — `dtcp.ap.gov.in` — reachable, but its layout links are broken

Directorate of Town & Country Planning. Homepage loads (200). However the two
links that matter both **404 as of 2026-08-03**:
- `http://dtcp.ap.gov.in/webdtcp/approvedlayouts.html` → 404
- `https://dtcp.ap.gov.in/downloads/Unauthorised Layout Details.pdf` → 404

These are stale links on a live homepage — a common failure mode on these sites.
Do not assume a link works because it is published.

Related systems:
- **APDPMS** — `apdpms.ap.gov.in` — now a "CivitPermit" SPA; building-permit
  workflow, login-gated. The public list endpoints referenced from the DTCP
  homepage (`portal.apdpms.ap.gov.in:8085/BPAMSClient/Common/OpList.aspx`) are
  **port-blocked** externally (connection fails on :8085).
- **UCIMS** — `ucimsapdtcp.ap.gov.in/ucims/home.aspx` — reachable (200).
  Unauthorized Constructions Identification & Monitoring System. Carries an
  "Unauthorized Layout App" and LRS material. Departmental login for the data
  itself, but the public pages are useful for the regulatory picture.

---

## Practical guidance

1. **Verify the district name twice.** Kakinada district was carved out of East
   Godavari in April 2022. Pre-2022 deeds, and most third-party sites, still say
   *East Godavari*. Search both.
2. **A `200 OK` is not evidence the resource exists.** MeeBhoomi returns its
   login page for every path; DTCP publishes links that 404. Check content
   length and actual body, not status codes.
3. **Ignore the SEO cluster.** `meebhoomiap.com`, `meebhoomi.net.in`,
   `meebhoomis.com`, `bhulekhindia.in`, `swarnagramam.com` and similar are
   scrapers describing a portal flow that no longer exists.
4. **Satellite imagery is not a boundary.** Use it to orient, to spot
   encroachment or new construction, and to compare against a sketch — never as
   the basis for a boundary claim.
5. **Geo-blocking is the main structural obstacle**, not paywalls. The AP
   planning-authority hosts that matter most (KAUDA) simply do not answer
   non-Indian traffic.

---

## See also

- `config/gis/aoi/kakinada_valasapakala.yaml` — AOI definition
- `docs/domain/realestate/re_india/kakinada-valasapakala.md` — the Valasapakala dossier
- `scripts/python/india_land_maps/` — the two fetchers
