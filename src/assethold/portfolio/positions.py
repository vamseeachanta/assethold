# ABOUTME: Net position and cost-basis calculator from Fidelity transaction history.
# ABOUTME: Computes shares held, average cost, total invested, and dividend income per symbol.

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class Position:
    """Snapshot of a single-symbol position."""

    symbol: str
    shares: float
    avg_cost: float
    total_cost: float
    total_dividends: float
    buy_count: int
    sell_count: int
    last_buy_date: Optional[pd.Timestamp]
    last_sell_date: Optional[pd.Timestamp]


def compute_positions(transactions: pd.DataFrame) -> dict[str, Position]:
    """Compute net positions from a normalized transaction DataFrame.

    Uses average-cost method: when shares are sold, the cost basis shrinks
    proportionally (shares_sold / shares_held * total_cost removed).

    Args:
        transactions: DataFrame from ingest.load_all_csvs with columns
            symbol, action_type, quantity, price, amount, run_date.

    Returns:
        Dict mapping symbol -> Position for every symbol with activity.
    """
    positions: dict[str, _Accumulator] = {}

    for _, row in transactions.iterrows():
        symbol = row["symbol"]
        if not symbol or pd.isna(symbol):
            continue

        if symbol not in positions:
            positions[symbol] = _Accumulator(symbol)

        acc = positions[symbol]
        action = row.get("action_type", "")
        qty = abs(row["quantity"]) if pd.notna(row.get("quantity")) else 0.0
        price = row["price"] if pd.notna(row.get("price")) else 0.0
        amount = row["amount"] if pd.notna(row.get("amount")) else 0.0
        run_date = row["run_date"]

        if action == "buy":
            cost = abs(amount) if amount else qty * price
            acc.shares += qty
            acc.total_cost += cost
            acc.buy_count += 1
            acc.last_buy_date = run_date
        elif action == "sell":
            if acc.shares > 0:
                # Average-cost: remove proportional cost basis.
                fraction = min(qty / acc.shares, 1.0)
                acc.total_cost -= acc.total_cost * fraction
            acc.shares -= qty
            acc.sell_count += 1
            acc.last_sell_date = run_date
        elif action == "dividend":
            acc.total_dividends += abs(amount) if amount else 0.0

    return {
        sym: Position(
            symbol=sym,
            shares=round(acc.shares, 4),
            avg_cost=round(acc.total_cost / acc.shares, 4) if acc.shares > 0 else 0.0,
            total_cost=round(acc.total_cost, 2),
            total_dividends=round(acc.total_dividends, 2),
            buy_count=acc.buy_count,
            sell_count=acc.sell_count,
            last_buy_date=acc.last_buy_date,
            last_sell_date=acc.last_sell_date,
        )
        for sym, acc in positions.items()
        if acc.shares > 0.01 or acc.total_dividends > 0
    }


def positions_to_dataframe(positions: dict[str, Position]) -> pd.DataFrame:
    """Convert positions dict to a summary DataFrame."""
    rows = []
    for pos in positions.values():
        rows.append({
            "symbol": pos.symbol,
            "shares": pos.shares,
            "avg_cost": pos.avg_cost,
            "total_cost": pos.total_cost,
            "total_dividends": pos.total_dividends,
            "buy_count": pos.buy_count,
            "sell_count": pos.sell_count,
            "last_buy_date": pos.last_buy_date,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("total_cost", ascending=False).reset_index(drop=True)
    return df


def buying_cadence(
    transactions: pd.DataFrame, symbol: str
) -> pd.DataFrame:
    """Return buy-date history and inter-purchase gaps for a symbol.

    Returns DataFrame with columns: run_date, quantity, amount, days_since_last.
    """
    buys = transactions[
        (transactions["symbol"] == symbol) & (transactions["action_type"] == "buy")
    ].sort_values("run_date").copy()

    if buys.empty:
        return buys

    buys["days_since_last"] = buys["run_date"].diff().dt.days
    return buys[["run_date", "quantity", "amount", "days_since_last"]].reset_index(
        drop=True
    )


def dividend_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    """Summarize dividend income by symbol and year."""
    divs = transactions[transactions["action_type"] == "dividend"].copy()
    if divs.empty:
        return pd.DataFrame(columns=["symbol", "year", "total_dividends"])

    divs["year"] = divs["run_date"].dt.year
    summary = (
        divs.groupby(["symbol", "year"])["amount"]
        .sum()
        .abs()
        .reset_index()
        .rename(columns={"amount": "total_dividends"})
        .sort_values(["year", "total_dividends"], ascending=[True, False])
        .reset_index(drop=True)
    )
    return summary


class _Accumulator:
    """Mutable accumulator for building a Position."""

    __slots__ = (
        "symbol",
        "shares",
        "total_cost",
        "total_dividends",
        "buy_count",
        "sell_count",
        "last_buy_date",
        "last_sell_date",
    )

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.shares = 0.0
        self.total_cost = 0.0
        self.total_dividends = 0.0
        self.buy_count = 0
        self.sell_count = 0
        self.last_buy_date: Optional[pd.Timestamp] = None
        self.last_sell_date: Optional[pd.Timestamp] = None
