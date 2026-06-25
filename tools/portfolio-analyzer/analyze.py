#!/usr/bin/env python3
"""Portfolio Returns Analyzer — deterministic, offline, self-contained.

Reads a config (YAML) + a FROZEN benchmark price file, computes returns
(XIRR/TWR), a dollar-matched benchmark clone, cash drag, drawdown & volatility,
and emits a single self-contained interactive dashboard.html (ECharts vendored).

DETERMINISM GUARANTEES (any AI provider / machine reproduces byte-identical output):
  * No network. Benchmark prices are read from benchmark_prices.json (frozen).
  * No system clock / no randomness. The "generated" label is config.portfolio.as_of.
  * Stable iteration order (everything sorted); fixed rounding; pinned ECharts file.
Only dependency: PyYAML (stdlib otherwise). Usage:  python analyze.py [config.yaml]
"""
import json, os, sys, bisect, statistics
from datetime import date, datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))

def to_date(v):
    if isinstance(v, date): return v
    if isinstance(v, datetime): return v.date()
    return date.fromisoformat(str(v))

# ---------- load inputs (deterministic; no network) ----------
def load_yaml(path):
    import yaml
    with open(path) as fh: return yaml.safe_load(fh)

cfg_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "config.example.yaml")
CFG = load_yaml(cfg_path)
PRICES = json.load(open(os.path.join(HERE, "benchmark_prices.json")))
BENCH = CFG["benchmark"]["primary"]
PX = {to_date(k): v for k, v in PRICES[BENCH].items()}
PXD = sorted(PX)

def price_at(d):
    """Nearest frozen month-end price to date d (deterministic)."""
    if d in PX: return PX[d]
    i = bisect.bisect_left(PXD, d)
    cand = []
    if i < len(PXD): cand.append(PXD[i])
    if i > 0: cand.append(PXD[i-1])
    best = min(cand, key=lambda x: abs((x-d).days))
    return PX[best]

# ---------- math ----------
def xirr(cf):
    cf = sorted(cf)
    t0 = cf[0][0]
    yrs = lambda d: (d - t0).days / 365.0
    f  = lambda r: sum(a / (1+r)**yrs(d) for d, a in cf)
    df = lambda r: sum(-yrs(d) * a / (1+r)**(yrs(d)+1) for d, a in cf)
    r = 0.1
    for _ in range(200):
        d1 = df(r)
        if abs(d1) < 1e-12: break
        nr = max(r - f(r)/d1, -0.999)
        if abs(nr - r) < 1e-10: r = nr; break
        r = nr
    return r

def modified_dietz(begin, end, flows, d0, d1):
    days = (d1 - d0).days or 1
    net = sum(a for _, a in flows)
    w = sum((d1 - d).days / days * a for d, a in flows)
    denom = begin + w
    return (end - begin - net) / denom if denom else 0.0

def clone_value(flows, end_d):
    """Dollar-matched: invest each dated flow into the benchmark at that date's price."""
    shares = 0.0
    for d, a in sorted(flows):
        p = price_at(d)
        if p: shares = max(0.0, shares + a / p)
    return shares * price_at(end_d)

def ms(d):  # UTC-pinned epoch ms — identical on any machine/timezone (determinism)
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)

# ---------- per-account build ----------
def build_account(acc):
    ye = {to_date(k): float(v) for k, v in acc["year_end"].items()}
    cash = {to_date(k): float(v) for k, v in (acc.get("cash") or {}).items()}
    flows = sorted((to_date(f["date"]), float(f["amount"])) for f in (acc.get("external_flows") or []))
    dates = sorted(ye)
    years = []
    for i in range(1, len(dates)):
        d0, d1 = dates[i-1], dates[i]
        start, end = ye[d0], ye[d1]
        fl = [(d, a) for d, a in flows if d0 < d <= d1]
        nf = sum(a for _, a in fl)
        gain = end - start - nf
        twr = modified_dietz(start, end, fl, d0, d1)
        cf = [(d0, -start)] + [(d, -a) for d, a in fl] + [(d1, end)]
        xr = xirr(cf)
        c = cash.get(d1)
        rec = {"year": d1.year, "start": round(start, 2), "end": round(end, 2),
               "net_flow": round(nf, 2), "gain": round(gain, 2),
               "twr": round(twr, 4), "xirr": round(xr, 4)}
        if c is not None:
            rec.update({"cash": round(c, 2), "invested": round(end - c, 2),
                        "cash_pct": round(c/end, 4) if end else 0})
        years.append(rec)
    # risk from TWR index (annual resolution)
    rets = [r["twr"] for r in years]
    idx, peak, mdd = 1.0, 1.0, 0.0
    for r in rets:
        idx *= (1+r); peak = max(peak, idx); mdd = min(mdd, idx/peak - 1)
    vol = statistics.pstdev(rets) if len(rets) > 1 else 0.0
    # lifetime + clone
    life_cf = [(dates[0], -ye[dates[0]])] + [(d, -a) for d, a in flows] + [(dates[-1], ye[dates[-1]])]
    life = xirr(life_cf)
    clone_end = round(clone_value(flows, dates[-1]), 2)
    net_contrib = round(sum(a for _, a in flows), 2)
    # monthly "you vs benchmark" series (deterministic, frozen prices)
    curve, wc = [], []
    shares, cum, fi = 0.0, 0.0, 0
    span = [d for d in PXD if dates[0] <= d <= dates[-1]]
    fl_sorted = flows
    for d in span:
        while fi < len(fl_sorted) and fl_sorted[fi][0] <= d:
            fd, fa = fl_sorted[fi]; shares = max(0.0, shares + fa/price_at(fd)); cum += fa; fi += 1
        curve.append([ms(d), round(shares*price_at(d), 2)])
        wc.append([ms(d), round(cum, 2)])
    cc = 0.0; events = []
    for d, a in flows:
        cc += a; events.append({"t": ms(d), "amt": round(a, 2), "cum": round(cc, 2),
                                "type": "in" if a >= 0 else "out"})
    marks = [[ms(d), round(ye[d], 2)] for d in dates]
    return {"id": acc["id"], "type": acc.get("type", ""), "years": years,
            "risk": {"max_drawdown": round(mdd, 4), "vol_annual": round(vol, 4)},
            "lifetime_xirr": round(life, 4), "net_contributed": net_contrib,
            "clone_end": clone_end, "end_value": round(ye[dates[-1]], 2),
            "daily": {"clone": curve, "working_capital": wc, "events": events, "actual": marks}}

accts = [build_account(a) for a in CFG["accounts"]]
ACC = {a["id"]: a for a in accts}

# combined (sum by year, recompute twr/xirr/risk)
def combined(accts):
    yrs = sorted({r["year"] for a in accts for r in a["years"]})
    allflows = sorted((to_date(f["date"]), float(f["amount"]))
                      for a in CFG["accounts"] for f in (a.get("external_flows") or []))
    def total_end(y):
        s = 0.0
        for a in CFG["accounts"]:
            ye = {to_date(k): float(v) for k, v in a["year_end"].items()}
            m = [ye[d] for d in ye if d.year == y]
            if m: s += m[0]
        return s
    rows = []
    for y in yrs:
        start, end = total_end(y-1), total_end(y)
        fl = [(d, a) for d, a in allflows if d.year == y]
        nf = sum(a for _, a in fl)
        twr = modified_dietz(start, end, fl, date(y-1, 12, 31), date(y, 12, 31))
        xr = xirr([(date(y-1, 12, 31), -start)] + [(d, -a) for d, a in fl] + [(date(y, 12, 31), end)])
        rows.append({"year": y, "start": round(start, 2), "end": round(end, 2),
                     "net_flow": round(nf, 2), "gain": round(end-start-nf, 2),
                     "twr": round(twr, 4), "xirr": round(xr, 4)})
    rets = [r["twr"] for r in rows]; idx=peak=1.0; mdd=0.0
    for r in rets: idx*=(1+r); peak=max(peak,idx); mdd=min(mdd, idx/peak-1)
    # combined daily
    curve, wc = [], []; shares=cum=0.0; fi=0
    span = [d for d in PXD if rows and date(rows[0]["year"]-1,12,31) <= d]
    for d in span:
        while fi < len(allflows) and allflows[fi][0] <= d:
            fd, fa = allflows[fi]; shares=max(0.0, shares+fa/price_at(fd)); cum+=fa; fi+=1
        curve.append([ms(d), round(shares*price_at(d),2)]); wc.append([ms(d), round(cum,2)])
    cc=0.0; events=[]
    for d,a in allflows: cc+=a; events.append({"t":ms(d),"amt":round(a,2),"cum":round(cc,2),"type":"in" if a>=0 else "out"})
    marks=[[ms(date(y,12,31)), round(total_end(y),2)] for y in yrs]
    life = xirr([(date(yrs[0]-1,12,31), -total_end(yrs[0]-1))] + [(d,-a) for d,a in allflows] + [(date(yrs[-1],12,31), total_end(yrs[-1]))])
    return {"id":"combined","type":"all","years":rows,
            "risk":{"max_drawdown":round(mdd,4),"vol_annual":round(statistics.pstdev(rets) if len(rets)>1 else 0,4)},
            "lifetime_xirr":round(life,4),"net_contributed":round(sum(a for _,a in allflows),2),
            "clone_end":round(clone_value(allflows, date(yrs[-1],12,31)),2),"end_value":round(total_end(yrs[-1]),2),
            "daily":{"clone":curve,"working_capital":wc,"events":events,"actual":marks}}
ACC["combined"] = combined(accts)

DATA = {"meta": {"owner": CFG["portfolio"]["owner"], "as_of": str(CFG["portfolio"]["as_of"]),
                 "benchmark": BENCH, "cash_rate": CFG["benchmark"].get("cash_rate_apy")},
        "order": [a["id"] for a in accts] + ["combined"],
        "accounts": ACC}

# ---------- emit dashboard ----------
ECHARTS = open(os.path.join(HERE, "echarts.min.js")).read()
APP = open(os.path.join(HERE, "app.js")).read()
TEMPLATE = open(os.path.join(HERE, "template.html")).read()
html = (TEMPLATE
        .replace("/*__ECHARTS__*/", ECHARTS)
        .replace("/*__DATA__*/", json.dumps(DATA, sort_keys=True))
        .replace("/*__APP__*/", APP)
        .replace("__OWNER__", str(DATA["meta"]["owner"]))
        .replace("__ASOF__", str(DATA["meta"]["as_of"]))
        .replace("__BENCH__", BENCH))
out = os.path.join(HERE, CFG.get("options", {}).get("output", "dashboard.html"))
with open(out, "w") as fh: fh.write(html)
print(f"wrote {out} ({round(len(html)/1024)} KB)")
for aid in DATA["order"]:
    a = ACC[aid]
    print(f"  {aid:12} end ${a['end_value']:>10,.0f}  vs benchmark-clone ${a['clone_end']:>10,.0f}  "
          f"lifetime XIRR {a['lifetime_xirr']*100:5.1f}%  MDD {a['risk']['max_drawdown']*100:5.1f}%")
