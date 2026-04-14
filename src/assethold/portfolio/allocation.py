# ABOUTME: Allocation monitor comparing current portfolio weights to target allocation.
# ABOUTME: Detects trim/accumulate signals and calculates new-money deployment splits.

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

try:
    import yfinance as yf  # type: ignore[import]
except ImportError:
    yf = None  # type: ignore[assignment]

from assethold.portfolio.positions import Position

# Fidelity uses different ticker symbols than Yahoo Finance for some stocks.
YAHOO_TICKER_MAP: dict[str, str] = {
    "BRKB": "BRK-B",
    "BRKA": "BRK-A",
}


@dataclass
class AllocationRow:
    """One row in the allocation comparison table."""

    symbol: str
    shares: float
    price: float
    market_value: float
    current_pct: float
    target_pct: float
    delta_pct: float
    signal: str  # "trim", "accumulate", or "hold"


@dataclass
class NewMoneySplit:
    """How to deploy a given dollar amount across target symbols."""

    total_usd: float
    allocations: list[tuple[str, float, int]]  # (symbol, dollars, shares)


def fetch_prices(symbols: list[str]) -> dict[str, float]:
    """Fetch current market prices via yfinance.

    Returns dict mapping symbol -> last close price.  Symbols that fail
    to fetch are silently omitted.
    """
    if yf is None:
        raise ImportError("yfinance is required for live price fetching")

    prices: dict[str, float] = {}
    for sym in symbols:
        try:
            yf_sym = YAHOO_TICKER_MAP.get(sym, sym)
            ticker = yf.Ticker(yf_sym)
            hist = ticker.history(period="5d")
            if not hist.empty:
                prices[sym] = float(hist["Close"].iloc[-1])
        except Exception:
            pass
    return prices


def compute_allocation(
    positions: dict[str, Position],
    target_allocation: dict[str, float],
    prices: Optional[dict[str, float]] = None,
    trim_threshold_pct: float = 5.0,
) -> list[AllocationRow]:
    """Compare current portfolio allocation to targets.

    Args:
        positions: Current positions keyed by symbol.
        target_allocation: Target weights from config (symbol -> fraction).
        prices: Current prices (symbol -> price).  If None, fetches live.
        trim_threshold_pct: Flag positions this many pct points over target.

    Returns:
        List of AllocationRow sorted by delta (most over-weight first).
    """
    # Only consider symbols that are in either positions or targets.
    all_symbols = sorted(
        set(positions.keys()) | set(target_allocation.keys()) - {"CASH"}
    )

    if prices is None:
        prices = fetch_prices(all_symbols)

    # Compute market values.
    rows = []
    total_value = 0.0
    for sym in all_symbols:
        pos = positions.get(sym)
        shares = pos.shares if pos else 0.0
        price = prices.get(sym, 0.0)
        mv = shares * price
        total_value += mv
        rows.append((sym, shares, price, mv))

    if total_value <= 0:
        return []

    result = []
    for sym, shares, price, mv in rows:
        current_pct = (mv / total_value) * 100
        target_pct = target_allocation.get(sym, 0.0) * 100
        delta = current_pct - target_pct

        if delta > trim_threshold_pct:
            signal = "trim"
        elif delta < -trim_threshold_pct:
            signal = "accumulate"
        else:
            signal = "hold"

        result.append(AllocationRow(
            symbol=sym,
            shares=shares,
            price=round(price, 2),
            market_value=round(mv, 2),
            current_pct=round(current_pct, 2),
            target_pct=round(target_pct, 2),
            delta_pct=round(delta, 2),
            signal=signal,
        ))

    result.sort(key=lambda r: r.delta_pct, reverse=True)
    return result


def new_money_split(
    amount_usd: float,
    split_config: dict[str, float],
    prices: Optional[dict[str, float]] = None,
) -> NewMoneySplit:
    """Calculate how to split new money across target symbols.

    Args:
        amount_usd: Total dollars to deploy.
        split_config: Weight dict from config (e.g. {VOO: 0.55, BRKB: 0.45}).
        prices: Current prices.  Fetched live if None.

    Returns:
        NewMoneySplit with per-symbol dollar amounts and whole share counts.
    """
    symbols = list(split_config.keys())
    if prices is None:
        prices = fetch_prices(symbols)

    allocations = []
    for sym, weight in split_config.items():
        dollars = amount_usd * weight
        price = prices.get(sym, 0.0)
        shares = int(dollars // price) if price > 0 else 0
        allocations.append((sym, round(dollars, 2), shares))

    return NewMoneySplit(total_usd=amount_usd, allocations=allocations)


def allocation_to_dataframe(rows: list[AllocationRow]) -> pd.DataFrame:
    """Convert allocation rows to a DataFrame for display."""
    if not rows:
        return pd.DataFrame()
    data = [
        {
            "Symbol": r.symbol,
            "Shares": r.shares,
            "Price": r.price,
            "Market Value": r.market_value,
            "Current %": r.current_pct,
            "Target %": r.target_pct,
            "Delta %": r.delta_pct,
            "Signal": r.signal,
        }
        for r in rows
    ]
    return pd.DataFrame(data)
