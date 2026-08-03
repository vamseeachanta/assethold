# AP land-portal status log

**Auto-generated — do not hand-edit.** Regenerate with:

```bash
python3 scripts/python/india_land_maps/probe_portals.py
```

Every finding about these portals is perishable: access rules, hostnames
and published links change without notice. This log records what was
actually true on each probe date, from a **non-Indian network** — vantage
point matters, because several hosts are firewalled to Indian IP ranges.

Verdicts:

| Verdict | Meaning |
|---|---|
| `OK` | reachable |
| `CATCH_ALL` | 200 for every path - login wall, content NOT accessible |
| `GEO_BLOCKED` | DNS resolves but connection times out (blocked to non-Indian traffic) |
| `NO_DNS` | hostname does not resolve at all |
| `GONE_404` | published link is dead |
| `FORBIDDEN` | authentication required |

`CATCH_ALL` is the one to watch: those hosts answer **HTTP 200 for a path
that cannot exist**, so a 200 there is not evidence of anything.

The **Access** column is a documented human judgement, not a probe result.
Reachability and access are different axes: BhuNaksha answers 200 and 404s
honestly, yet exposes no map without a login. Re-check access by hand
whenever a reachability verdict changes.

---

## 2026-08-03

Probed 2026-08-03T03:29:03+00:00 from: US network (non-Indian egress)

| Portal | Reachability | HTTP | Access | Notes |
|---|---|---|---|---|
| [BhuNaksha AP (cadastral viewer)](https://bhunaksha.ap.gov.in/) | `OK` | 200 | login / counter | Authoritative AP cadastral maps / FMB. The only real plot-boundary source. |
| [BhuNaksha REST layer](https://bhunaksha.ap.gov.in/bhunakshalpm/rest/MapInfo/getDistrictCodes) | `GONE_404` | 404 | login | If this ever answers anonymously again, bulk map retrieval becomes possible. |
| [MeeBhoomi (Adangal / 1-B / ROR)](https://meebhoomi.ap.gov.in/) | `CATCH_ALL` | 200 | login / counter | Record of Rights and village maps. |
| [KAUDA (Kakinada Urban Dev. Authority)](https://kauda.ap.gov.in/) | `GEO_BLOCKED` | — (timed out) | india-only | Master plan + approved layouts for Valasapakala. Geo-blocked as of 2026-08-03. |
| [KAUDA Kakinada Master Plan PDF](https://kauda.ap.gov.in/documents/MasterPlans/KakinadaMasterPlan.pdf) | `GEO_BLOCKED` | — (timed out) | india-only | Zoning designation drives buildability on the Kakinada fringe. |
| [KAUDA Zonal Development Plan 2040 PDF](https://kauda.ap.gov.in/documents/downloads/KAKINADA_ZDp_2040-compressed.pdf) | `GEO_BLOCKED` | — (timed out) | india-only | Forward zoning to 2040. |
| [DTCP AP (Town & Country Planning)](https://dtcp.ap.gov.in/) | `OK` | 200 | open | Statewide planning directorate. |
| [DTCP approved-layouts page](http://dtcp.ap.gov.in/webdtcp/approvedlayouts.html) | `GONE_404` | 404 | open (link dead) | Linked from the DTCP homepage but 404 as of 2026-08-03 - recheck periodically. |
| [DTCP unauthorised-layout list (PDF)](https://dtcp.ap.gov.in/downloads/Unauthorised%20Layout%20Details.pdf) | `GONE_404` | 404 | open (link dead) | Linked from the DTCP homepage but 404 as of 2026-08-03 - recheck periodically. |
| [APDPMS / CivitPermit](https://apdpms.ap.gov.in/) | `OK` | 200 | login | Building-permit workflow; public list endpoints on :8085 are port-blocked. |
| [UCIMS (unauthorised construction)](http://ucimsapdtcp.ap.gov.in/ucims/home.aspx) | `OK` | 200 | open (login for data) | Unauthorised layout / construction regulatory picture. |
| [Bhuvan Panchayat / SISDP v4 (ISRO)](https://bhuvanpanchayat.nrsc.gov.in/) | `OK` | 200 | open (account for bulk) | Best official panchayat-scale thematic mapping; account needed for bulk download. |
| [Bhuvan main portal (ISRO)](https://bhuvan.nrsc.gov.in/) | `OK` | 200 | open (account for bulk) | Indian EO imagery and thematic layers. |
| [CCLA AP (Chief Commissioner, Land Admin.)](https://ccla.ap.gov.in/) | `OK` | 200 | open | Departmental landing page; policy and GO source. |
| [Webland AP](https://webland.ap.gov.in/) | `OK` | 200 | open | Legacy land-records front end. |
| [bhubharati.ap.gov.in](https://bhubharati.ap.gov.in/) | `NO_DNS` | — ([Errno 8] nodename nor servname pr) | n/a | Frequently cited in guides but has never resolved - kept here to stay disproved. |
| [ESRI World Imagery tiles](https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/16/26000/47000) | `OK` | 200 | open (attribution) | Satellite basemap used by fetch_basemap_tiles.py. |
| [Overpass API (OpenStreetMap)](https://overpass-api.de/api/status) | `OK` | 200 | open | Vector context used by fetch_osm_extract.py. |

