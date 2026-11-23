#!/usr/bin/env python3
"""OPTIONAL utility — regenerate benchmark_prices.json from Yahoo Finance.

This is the ONLY part of the tool that touches the network. analyze.py never
calls it; it reads the frozen JSON. Run this only to refresh/extend the prices,
then commit the updated benchmark_prices.json so runs stay deterministic.

Usage:  python fetch_prices.py VOO [VTI SPY ...]
"""
import json, os, sys, urllib.request
from datetime import date, datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
P1, P2 = 1575158400, 1780000000   # ~2019-12 .. ~2026-05

def fetch(ticker):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?period1={P1}&period2={P2}&interval=1d&events=div")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    res = json.load(urllib.request.urlopen(req, timeout=45))["chart"]["result"][0]
    ts = res["timestamp"]; adj = res["indicators"]["adjclose"][0]["adjclose"]
    by_month = {}
    for t, a in zip(ts, adj):
        if a is None: continue
        d = datetime.fromtimestamp(t, tz=timezone.utc).date()
        k = (d.year, d.month)
        if k not in by_month or d > by_month[k][0]:
            by_month[k] = (d, a)
    return {d.isoformat(): round(a, 4) for _, (d, a) in sorted(by_month.items())}

def main(tickers):
    path = os.path.join(HERE, "benchmark_prices.json")
    out = json.load(open(path)) if os.path.exists(path) else {}
    out["_meta"] = {"kind": "total_return_adjusted_close", "resolution": "month_end",
                    "note": "Frozen public data for deterministic reproduction."}
    for tk in tickers:
        out[tk] = fetch(tk)
        print(f"{tk}: {len(out[tk])} month-end points")
    json.dump(out, open(path, "w"), indent=1, sort_keys=True)
    print("wrote", path)

if __name__ == "__main__":
    main(sys.argv[1:] or ["VOO"])
