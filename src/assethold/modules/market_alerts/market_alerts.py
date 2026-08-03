"""market_alerts workflow: positions + live quotes -> signals -> alerts + snapshot.

Generic engine (no account PII). Positions are dollar-denominated (USD allocation per
ticker), so portfolio weights and the weighted move come from allocations, not share
counts. Holdings may be a hypothetical watchlist or sourced from a positions export by
the caller; this workflow only sees what the cfg provides.

cfg section ("market_alerts"):
    data:      {source: yfinance|fixture}
    positions: [{ticker, usd}, ...]
    signals:   {price_move_pct, fundamentals: {pe_max, div_yield_min}}
    outputs:   {snapshot_csv, alerts_json}   # paths; the caller decides where
"""
from __future__ import annotations

import csv
from typing import List, Optional

from assethold.modules.market_alerts import signals as signal_rules
from assethold.modules.market_alerts.marketdata import MarketDataProvider, get_provider
from assethold.modules.market_alerts.signals import Alert
from assethold.modules.workflow_io import output_path, record_outputs, section, write_json


class MarketAlertsWorkflow:
    """Fetch quotes for the configured positions, run signals, write snapshot + alerts."""

    def router(self, cfg: dict, provider: Optional[MarketDataProvider] = None) -> dict:
        settings = section(cfg, "market_alerts")
        positions = settings.get("positions", []) or []
        signals_cfg = settings.get("signals", {}) or {}
        outputs = settings.get("outputs", {}) or {}

        if provider is None:
            data_cfg = settings.get("data", {}) or {}
            provider = get_provider(
                data_cfg.get("source", "yfinance"),
                quotes=data_cfg.get("quotes", {}),  # used only by the 'fixture' source
            )

        total = sum(float(p.get("usd", 0)) for p in positions) or 1.0
        holdings: List[dict] = []
        alerts: List[Alert] = []
        weighted_move = 0.0
        have_move = False

        for p in positions:
            ticker = p["ticker"]
            usd = float(p.get("usd", 0))
            weight = usd / total
            quote = provider.get_quote(ticker)
            if quote.pct_change is not None:
                weighted_move += weight * quote.pct_change
                have_move = True
            holdings.append({
                "ticker": ticker, "usd": usd, "weight": weight,
                "price": quote.price, "prev_close": quote.prev_close,
                "pct_change": quote.pct_change, "pe": quote.pe,
                "dividend_yield": quote.dividend_yield,
            })
            alerts.extend(signal_rules.evaluate(quote, signals_cfg))

        portfolio = {
            "total_usd": total,
            "weighted_move_pct": weighted_move if have_move else None,
            "holdings": holdings,
        }

        # Book-level move alert: fires when the dollar-weighted portfolio move crosses a
        # threshold even if no single position does. Useful for a concentrated book.
        pm = portfolio["weighted_move_pct"]
        pm_thr = signals_cfg.get("portfolio_move_pct")
        if pm is not None and pm_thr is not None and abs(pm) >= pm_thr:
            direction = "up" if pm >= 0 else "down"
            alerts.append(Alert(
                "PORTFOLIO", "portfolio_move", "warn",
                f"book {pm:+.2f}% ({direction}, threshold {pm_thr:g}%)",
            ))

        written = []
        if "snapshot_csv" in outputs:
            written.append(_write_snapshot_csv(outputs["snapshot_csv"], holdings))
        if "alerts_json" in outputs:
            written.append(write_json(outputs["alerts_json"], {
                "total_usd": total,
                "weighted_move_pct": portfolio["weighted_move_pct"],
                "alerts": [a.__dict__ for a in alerts],
            }))

        print(render_console(portfolio, alerts))

        cfg["market_alerts_result"] = {
            "portfolio": portfolio,
            "alerts": [a.__dict__ for a in alerts],
        }
        return record_outputs(cfg, "market_alerts", written)


def _write_snapshot_csv(path: str, holdings: List[dict]):
    target = output_path(path)
    cols = ["ticker", "usd", "weight", "price", "prev_close", "pct_change", "pe", "dividend_yield"]
    # newline="" stops the text layer translating, and lineterminator="\n"
    # overrides csv's own "\r\n" default - without the second half this writes
    # CRLF on every platform, which is merely inconsistent with the other
    # workflows today but becomes platform-dependent the moment newline="" is
    # dropped. Emitted artifacts are content-hashed; see assethold#85.
    with target.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for h in holdings:
            w.writerow({k: h.get(k) for k in cols})
    return target


_SEV_MARK = {"warn": "⚠", "info": "•"}


def render_console(portfolio: dict, alerts: List[Alert]) -> str:
    lines = ["=" * 60, f"Market alerts — portfolio (${portfolio['total_usd']:,.0f})", "=" * 60]
    lines.append(f"{'Ticker':<8}{'Weight':>8}{'Price':>12}{'Δ% prev':>10}")
    for h in portfolio["holdings"]:
        px = f"{h['price']:.2f}" if h["price"] is not None else "n/a"
        pc = f"{h['pct_change']:+.2f}" if h["pct_change"] is not None else "n/a"
        lines.append(f"{h['ticker']:<8}{h['weight']*100:>7.1f}%{px:>12}{pc:>10}")
    pm = portfolio["weighted_move_pct"]
    lines.append("-" * 60)
    lines.append(f"Portfolio weighted move: {pm:+.2f}%" if pm is not None else "Portfolio weighted move: n/a")
    lines.append("")
    if alerts:
        lines.append(f"ALERTS ({len(alerts)}):")
        for a in alerts:
            lines.append(f"  {_SEV_MARK.get(a.severity, '-')} [{a.kind}] {a.ticker}: {a.message}")
    else:
        lines.append("No alerts (all thresholds clear).")
    return "\n".join(lines)
