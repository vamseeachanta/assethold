#!/usr/bin/env python3
"""Re-probe the Indian land-record / planning portals and emit a dated status record.

Why this exists: every finding about these portals is perishable. Access rules,
hostnames and published links change without notice - during the 2026-08-03
survey, DTCP was still publishing two layout links that both 404, and BhuNaksha
had moved behind a login since most public documentation was written. A prose
note goes stale silently; this script re-derives the facts on demand and stamps
them with the date they were true.

Usage:
    python3 scripts/python/india_land_maps/probe_portals.py
    python3 scripts/python/india_land_maps/probe_portals.py --json-only

Outputs:
    data/gis/portal_status/<YYYY-MM-DD>.json   raw dated observations
    docs/domain/realestate/re_india/portal-status-log.md   regenerated summary

Interpreting results - two traps this script is built to catch:

  CATCH-ALL LOGIN: several AP portals return HTTP 200 with an identical login
  page for *every* path, so a 200 proves nothing. Each such host is probed with
  a deliberately absent control path; if a real path returns the same byte
  count as the control, the host is flagged CATCH_ALL rather than OK.

  GEO-BLOCK: some hosts resolve in DNS but never complete a TCP handshake from
  outside India. That is reported as GEO_BLOCKED (DNS ok, connect fails), which
  is a materially different problem from a dead host.
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

USER_AGENT = "assethold-gis/0.1 (+https://github.com/vamseeachanta/assethold)"
TIMEOUT = 20

REPO_ROOT = Path(__file__).resolve().parents[3]
JSON_DIR = REPO_ROOT / "data" / "gis" / "portal_status"
LOG_MD = REPO_ROOT / "docs" / "domain" / "realestate" / "re_india" / "portal-status-log.md"

# (key, label, url, control_path_or_None, why_it_matters, access)
#
# control path = a path that certainly does not exist; used to detect catch-all
# login pages that answer 200 for everything.
#
# `access` is a DOCUMENTED fact, not a probed one - reachability and access are
# different axes. BhuNaksha answers 200 and 404s honestly, yet exposes no map
# without a login. The probe cannot infer that, so it is recorded by hand and
# must be re-checked by a human when a verdict changes.
#   open       - usable anonymously
#   login      - needs an account (Indian mobile OTP for the citizen portals)
#   counter    - realistically obtained in person (MeeSeva / MRO / surveyor)
#   india-only - blocked to non-Indian networks
TARGETS = [
    (
        "bhunaksha",
        "BhuNaksha AP (cadastral viewer)",
        "https://bhunaksha.ap.gov.in/",
        "/bhunakshalpm/28/__assethold_control__.jsp",
        "Authoritative AP cadastral maps / FMB. The only real plot-boundary source.",
        "login / counter",
    ),
    (
        "bhunaksha_rest",
        "BhuNaksha REST layer",
        "https://bhunaksha.ap.gov.in/bhunakshalpm/rest/MapInfo/getDistrictCodes",
        None,
        "If this ever answers anonymously again, bulk map retrieval becomes possible.",
        "login",
    ),
    (
        "meebhoomi",
        "MeeBhoomi (Adangal / 1-B / ROR)",
        "https://meebhoomi.ap.gov.in/",
        "/__assethold_control__.aspx",
        "Record of Rights and village maps.",
        "login / counter",
    ),
    (
        "kauda",
        "KAUDA (Kakinada Urban Dev. Authority)",
        "https://kauda.ap.gov.in/",
        None,
        "Master plan + approved layouts for Valasapakala. Geo-blocked as of 2026-08-03.",
        "india-only",
    ),
    (
        "kauda_masterplan",
        "KAUDA Kakinada Master Plan PDF",
        "https://kauda.ap.gov.in/documents/MasterPlans/KakinadaMasterPlan.pdf",
        None,
        "Zoning designation drives buildability on the Kakinada fringe.",
        "india-only",
    ),
    (
        "kauda_zdp",
        "KAUDA Zonal Development Plan 2040 PDF",
        "https://kauda.ap.gov.in/documents/downloads/KAKINADA_ZDp_2040-compressed.pdf",
        None,
        "Forward zoning to 2040.",
        "india-only",
    ),
    (
        "dtcp",
        "DTCP AP (Town & Country Planning)",
        "https://dtcp.ap.gov.in/",
        None,
        "Statewide planning directorate.",
        "open",
    ),
    (
        "dtcp_approved_layouts",
        "DTCP approved-layouts page",
        "http://dtcp.ap.gov.in/webdtcp/approvedlayouts.html",
        None,
        "Linked from the DTCP homepage but 404 as of 2026-08-03 - recheck periodically.",
        "open (link dead)",
    ),
    (
        "dtcp_unauth_layouts",
        "DTCP unauthorised-layout list (PDF)",
        "https://dtcp.ap.gov.in/downloads/Unauthorised%20Layout%20Details.pdf",
        None,
        "Linked from the DTCP homepage but 404 as of 2026-08-03 - recheck periodically.",
        "open (link dead)",
    ),
    (
        "apdpms",
        "APDPMS / CivitPermit",
        "https://apdpms.ap.gov.in/",
        None,
        "Building-permit workflow; public list endpoints on :8085 are port-blocked.",
        "login",
    ),
    (
        "ucims",
        "UCIMS (unauthorised construction)",
        "http://ucimsapdtcp.ap.gov.in/ucims/home.aspx",
        None,
        "Unauthorised layout / construction regulatory picture.",
        "open (login for data)",
    ),
    (
        "bhuvan_panchayat",
        "Bhuvan Panchayat / SISDP v4 (ISRO)",
        "https://bhuvanpanchayat.nrsc.gov.in/",
        None,
        "Best official panchayat-scale thematic mapping; account needed for bulk download.",
        "open (account for bulk)",
    ),
    (
        "bhuvan",
        "Bhuvan main portal (ISRO)",
        "https://bhuvan.nrsc.gov.in/",
        None,
        "Indian EO imagery and thematic layers.",
        "open (account for bulk)",
    ),
    (
        "ccla",
        "CCLA AP (Chief Commissioner, Land Admin.)",
        "https://ccla.ap.gov.in/",
        None,
        "Departmental landing page; policy and GO source.",
        "open",
    ),
    (
        "webland",
        "Webland AP",
        "https://webland.ap.gov.in/",
        None,
        "Legacy land-records front end.",
        "open",
    ),
    (
        "bhubharati",
        "bhubharati.ap.gov.in",
        "https://bhubharati.ap.gov.in/",
        None,
        "Frequently cited in guides but has never resolved - kept here to stay disproved.",
        "n/a",
    ),
    (
        "esri_imagery",
        "ESRI World Imagery tiles",
        "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/16/26000/47000",
        None,
        "Satellite basemap used by fetch_basemap_tiles.py.",
        "open (attribution)",
    ),
    (
        "overpass",
        "Overpass API (OpenStreetMap)",
        "https://overpass-api.de/api/status",
        None,
        "Vector context used by fetch_osm_extract.py.",
        "open",
    ),
]


def resolve(host: str) -> str | None:
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


def fetch(url: str) -> dict:
    """GET a URL, following redirects, reporting status/size/final URL or a failure kind."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
            return {
                "http_status": resp.status,
                "bytes": len(body),
                "final_url": resp.url,
                "content_type": resp.headers.get("Content-Type"),
            }
    except urllib.error.HTTPError as exc:
        return {
            "http_status": exc.code,
            "bytes": len(exc.read() or b""),
            "final_url": url,
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
        }
    except (urllib.error.URLError, TimeoutError, socket.timeout, ssl.SSLError) as exc:
        reason = getattr(exc, "reason", exc)
        return {"http_status": None, "error": str(reason)}


def classify(url: str, main: dict, control: dict | None, dns: str | None) -> str:
    if main.get("http_status") is None:
        if dns:
            # Name resolves but the connection never completes - the signature of
            # an IP-range firewall rather than a decommissioned host.
            return "GEO_BLOCKED"
        return "NO_DNS"
    status = main["http_status"]
    if control and control.get("http_status") == 200 and main.get("bytes") == control.get("bytes"):
        return "CATCH_ALL"  # same page for a bogus path => login wall, not content
    if status == 200:
        return "OK"
    if status == 404:
        return "GONE_404"
    if status in (401, 403):
        return "FORBIDDEN"
    return f"HTTP_{status}"


VERDICT_NOTE = {
    "OK": "reachable",
    "CATCH_ALL": "200 for every path - login wall, content NOT accessible",
    "GEO_BLOCKED": "DNS resolves but connection times out (blocked to non-Indian traffic)",
    "NO_DNS": "hostname does not resolve at all",
    "GONE_404": "published link is dead",
    "FORBIDDEN": "authentication required",
}


def probe_all() -> dict:
    results = []
    for key, label, url, control_path, why, access in TARGETS:
        host = urllib.parse.urlsplit(url).netloc.split(":")[0]
        dns = resolve(host)
        print(f"[probe] {label} ...", flush=True)
        main = fetch(url)
        control = None
        if control_path:
            base = f"{urllib.parse.urlsplit(url).scheme}://{urllib.parse.urlsplit(url).netloc}"
            control = fetch(base + control_path)
        verdict = classify(url, main, control, dns)
        results.append(
            {
                "key": key,
                "label": label,
                "url": url,
                "why_it_matters": why,
                "access": access,
                "dns": dns,
                "verdict": verdict,
                "main": main,
                "control": control,
            }
        )
        print(f"[probe]   -> {verdict}")
    return {
        "probed_on": date.today().isoformat(),
        "probed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vantage_point": "US network (non-Indian egress)",
        "results": results,
    }


def render_markdown(records: list[dict]) -> str:
    """Render every dated snapshot, newest first, so drift over time stays visible."""
    out = [
        "# AP land-portal status log",
        "",
        "**Auto-generated — do not hand-edit.** Regenerate with:",
        "",
        "```bash",
        "python3 scripts/python/india_land_maps/probe_portals.py",
        "```",
        "",
        "Every finding about these portals is perishable: access rules, hostnames",
        "and published links change without notice. This log records what was",
        "actually true on each probe date, from a **non-Indian network** — vantage",
        "point matters, because several hosts are firewalled to Indian IP ranges.",
        "",
        "Verdicts:",
        "",
        "| Verdict | Meaning |",
        "|---|---|",
    ]
    for k, v in VERDICT_NOTE.items():
        out.append(f"| `{k}` | {v} |")
    out += [
        "",
        "`CATCH_ALL` is the one to watch: those hosts answer **HTTP 200 for a path",
        "that cannot exist**, so a 200 there is not evidence of anything.",
        "",
        "The **Access** column is a documented human judgement, not a probe result.",
        "Reachability and access are different axes: BhuNaksha answers 200 and 404s",
        "honestly, yet exposes no map without a login. Re-check access by hand",
        "whenever a reachability verdict changes.",
        "",
        "---",
        "",
    ]

    for rec in records:
        out.append(f"## {rec['probed_on']}")
        out.append("")
        out.append(f"Probed {rec['probed_at_utc']} from: {rec['vantage_point']}")
        out.append("")
        out.append("| Portal | Reachability | HTTP | Access | Notes |")
        out.append("|---|---|---|---|---|")
        for r in rec["results"]:
            m = r["main"]
            http = m.get("http_status")
            http_s = str(http) if http else f"— ({m.get('error', 'failed')[:34]})"
            out.append(
                f"| [{r['label']}]({r['url']}) | `{r['verdict']}` | {http_s} "
                f"| {r.get('access', '?')} | {r['why_it_matters']} |"
            )
        out.append("")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json-only", action="store_true", help="skip markdown regeneration")
    args = ap.parse_args()

    snapshot = probe_all()
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    json_path = JSON_DIR / f"{snapshot['probed_on']}.json"
    json_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"\n[probe] wrote {json_path}")

    if not args.json_only:
        records = []
        for p in sorted(JSON_DIR.glob("*.json"), reverse=True):
            try:
                records.append(json.loads(p.read_text(encoding="utf-8")))
            except json.JSONDecodeError as exc:
                print(f"[probe] skipping unreadable {p.name}: {exc}", file=sys.stderr)
        LOG_MD.write_text(render_markdown(records), encoding="utf-8")
        print(f"[probe] wrote {LOG_MD} ({len(records)} dated snapshot(s))")

    counts: dict[str, int] = {}
    for r in snapshot["results"]:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print("\n[probe] summary: " + ", ".join(f"{v}x {k}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
