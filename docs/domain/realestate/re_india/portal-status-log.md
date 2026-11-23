# AP land-portal status log

**Auto-generated — do not hand-edit.** Regenerate with:

```bash
python3 scripts/python/india_land_maps/probe_portals.py
```

Every finding about these portals is perishable: access rules, hostnames
and published links change without notice. This log records what was
actually true on each probe date, from the vantage point stated on that
snapshot — "unreachable" is meaningless without knowing from where.

Verdicts:

| Verdict | Meaning |
|---|---|
| `OK` | reachable |
| `CATCH_ALL` | 200 for every path - login wall, content NOT accessible |
| `UNREACHABLE` | DNS resolves but TCP never connects - dead host, firewall or routing; a single vantage point CANNOT distinguish these |
| `NO_DNS` | hostname does not resolve at all |
| `GONE_404` | published link is dead |
| `FORBIDDEN` | authentication required |

`CATCH_ALL` is the one to watch: those hosts answer **HTTP 200 for a path
that cannot exist**, so a 200 there is not evidence of anything.

The **Vantage point** on each snapshot is DETECTED, not assumed. An earlier
version of this log asserted hosts were *geo-blocked to non-Indian traffic*
while the probe was in fact running from Kakinada, Andhra Pradesh. Treat
`UNREACHABLE` as "could not connect", nothing more.

The **Access** column is a documented human judgement, not a probe result.
Reachability and access are different axes: BhuNaksha answers 200 and 404s
honestly, yet exposes no map without a login. Re-check access by hand
whenever a reachability verdict changes.

---

## 2026-09-04

Probed 2026-09-04T17:19:10+00:00 from: Houston, Texas, US, AS7922 Comcast Cable Communications, LLC

| Portal | Reachability | HTTP | Access | Notes |
|---|---|---|---|---|
| [BhuNaksha AP (cadastral viewer)](https://bhunaksha.ap.gov.in/) | `UNREACHABLE` | — (timed out) | login / counter | Authoritative AP cadastral maps / FMB. The only real plot-boundary source. |
| [BhuNaksha REST layer](https://bhunaksha.ap.gov.in/bhunakshalpm/rest/MapInfo/getDistrictCodes) | `UNREACHABLE` | — (timed out) | login | If this ever answers anonymously again, bulk map retrieval becomes possible. |
| [MeeBhoomi (Adangal / 1-B / ROR)](https://meebhoomi.ap.gov.in/) | `UNREACHABLE` | — (timed out) | login / counter | Record of Rights and village maps. |
| [KAUDA (Kakinada Urban Dev. Authority)](https://kauda.ap.gov.in/) | `UNREACHABLE` | — (timed out) | host down (KAUDA merged into GUDA) | Master plan + approved layouts for Valasapakala. Host DOWN as of 2026-08-03 - fails from inside Kakinada too; KAUDA merged into GUDA. |
| [KAUDA Kakinada Master Plan PDF](https://kauda.ap.gov.in/documents/MasterPlans/KakinadaMasterPlan.pdf) | `UNREACHABLE` | — (timed out) | host down (KAUDA merged into GUDA) | Zoning designation drives buildability on the Kakinada fringe. |
| [KAUDA Zonal Development Plan 2040 PDF](https://kauda.ap.gov.in/documents/downloads/KAKINADA_ZDp_2040-compressed.pdf) | `UNREACHABLE` | — (timed out) | host down (KAUDA merged into GUDA) | Forward zoning to 2040. |
| [DTCP AP (Town & Country Planning)](https://dtcp.ap.gov.in/) | `UNREACHABLE` | — (timed out) | open | Statewide planning directorate. |
| [DTCP approved-layouts page](http://dtcp.ap.gov.in/webdtcp/approvedlayouts.html) | `UNREACHABLE` | — (timed out) | open (link dead) | Linked from the DTCP homepage but 404 as of 2026-08-03 - recheck periodically. |
| [DTCP unauthorised-layout list (PDF)](https://dtcp.ap.gov.in/downloads/Unauthorised%20Layout%20Details.pdf) | `UNREACHABLE` | — (timed out) | open (link dead) | Linked from the DTCP homepage but 404 as of 2026-08-03 - recheck periodically. |
| [APDPMS / CivitPermit](https://apdpms.ap.gov.in/) | `OK` | 200 | login | Building-permit workflow; public list endpoints on :8085 are port-blocked. |
| [UCIMS (unauthorised construction)](http://ucimsapdtcp.ap.gov.in/ucims/home.aspx) | `UNREACHABLE` | — (timed out) | open (login for data) | Unauthorised layout / construction regulatory picture. |
| [Bhuvan Panchayat / SISDP v4 (ISRO)](https://bhuvanpanchayat.nrsc.gov.in/) | `OK` | 200 | open (account for bulk) | Best official panchayat-scale thematic mapping; account needed for bulk download. |
| [Bhuvan main portal (ISRO)](https://bhuvan.nrsc.gov.in/) | `OK` | 200 | open (account for bulk) | Indian EO imagery and thematic layers. |
| [CCLA AP (Chief Commissioner, Land Admin.)](https://ccla.ap.gov.in/) | `UNREACHABLE` | — (timed out) | open | Departmental landing page; policy and GO source. |
| [Webland AP](https://webland.ap.gov.in/) | `UNREACHABLE` | — (timed out) | open | Legacy land-records front end. |
| [bhubharati.ap.gov.in](https://bhubharati.ap.gov.in/) | `NO_DNS` | — ([Errno 8] nodename nor servname pr) | n/a | Frequently cited in guides but has never resolved - kept here to stay disproved. |
| [ESRI World Imagery tiles](https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/16/26000/47000) | `OK` | 200 | open (attribution) | Satellite basemap used by fetch_basemap_tiles.py. |
| [Overpass API (OpenStreetMap)](https://overpass-api.de/api/status) | `OK` | 200 | open | Vector context used by fetch_osm_extract.py. |

## 2026-08-03

Probed 2026-08-03T07:29:29+00:00 from: Kākināda, Andhra Pradesh, IN, AS55836 Reliance Jio Infocomm Limited

| Portal | Reachability | HTTP | Access | Notes |
|---|---|---|---|---|
| [BhuNaksha AP (cadastral viewer)](https://bhunaksha.ap.gov.in/) | `OK` | 200 | login / counter | Authoritative AP cadastral maps / FMB. The only real plot-boundary source. |
| [BhuNaksha REST layer](https://bhunaksha.ap.gov.in/bhunakshalpm/rest/MapInfo/getDistrictCodes) | `GONE_404` | 404 | login | If this ever answers anonymously again, bulk map retrieval becomes possible. |
| [MeeBhoomi (Adangal / 1-B / ROR)](https://meebhoomi.ap.gov.in/) | `CATCH_ALL` | 200 | login / counter | Record of Rights and village maps. |
| [KAUDA (Kakinada Urban Dev. Authority)](https://kauda.ap.gov.in/) | `UNREACHABLE` | — (timed out) | host down (KAUDA merged into GUDA) | Master plan + approved layouts for Valasapakala. Host DOWN as of 2026-08-03 - fails from inside Kakinada too; KAUDA merged into GUDA. |
| [KAUDA Kakinada Master Plan PDF](https://kauda.ap.gov.in/documents/MasterPlans/KakinadaMasterPlan.pdf) | `UNREACHABLE` | — (timed out) | host down (KAUDA merged into GUDA) | Zoning designation drives buildability on the Kakinada fringe. |
| [KAUDA Zonal Development Plan 2040 PDF](https://kauda.ap.gov.in/documents/downloads/KAKINADA_ZDp_2040-compressed.pdf) | `UNREACHABLE` | — (timed out) | host down (KAUDA merged into GUDA) | Forward zoning to 2040. |
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

