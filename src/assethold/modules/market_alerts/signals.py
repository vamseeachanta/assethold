"""Signal rules over quotes: price move vs previous close + a few fundamentals rules.

Each rule is pure (quote + thresholds -> list[Alert]) so rules compose and are trivially
testable. Add MA-crossover / RSI / etc. as more price history is wired in.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from assethold.modules.market_alerts.marketdata import Quote


@dataclass
class Alert:
    ticker: str
    kind: str       # "move" | "valuation" | "yield" | "data"
    severity: str   # "info" | "warn"
    message: str


def evaluate(quote: Quote, signals_cfg: dict) -> List[Alert]:
    sig = signals_cfg or {}
    alerts: List[Alert] = []

    if quote.error:
        return [Alert(quote.ticker, "data", "warn", f"no data ({quote.error})")]

    thr = sig.get("price_move_pct")
    if thr is not None and quote.pct_change is not None and abs(quote.pct_change) >= thr:
        direction = "up" if quote.pct_change >= 0 else "down"
        alerts.append(Alert(
            quote.ticker, "move", "warn",
            f"{quote.pct_change:+.2f}% vs prev close ({direction}, threshold {thr:g}%)",
        ))

    fund = sig.get("fundamentals", {}) or {}
    pe_max = fund.get("pe_max")
    if pe_max is not None and quote.pe is not None and quote.pe > pe_max:
        alerts.append(Alert(
            quote.ticker, "valuation", "info",
            f"P/E {quote.pe:.1f} > {pe_max:g} (rich vs target)",
        ))

    dy_min = fund.get("div_yield_min")  # configured in percent
    if dy_min is not None and quote.dividend_yield is not None:
        dy_pct = quote.dividend_yield * 100.0
        if dy_pct >= dy_min:
            alerts.append(Alert(
                quote.ticker, "yield", "info",
                f"dividend yield {dy_pct:.2f}% >= {dy_min:g}%",
            ))

    return alerts
