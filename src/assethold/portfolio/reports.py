# ABOUTME: Daily portfolio report generator for terminal output.
# ABOUTME: Shows positions, allocation vs target, trim/accumulate signals, DCA cadence, dividends.

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from assethold.portfolio.allocation import (
    AllocationRow,
    allocation_to_dataframe,
    compute_allocation,
    fetch_prices,
    new_money_split,
)
from assethold.portfolio.ingest import load_all_csvs, load_config
from assethold.portfolio.positions import (
    buying_cadence,
    compute_positions,
    dividend_summary,
    positions_to_dataframe,
)


def _header(title: str) -> str:
    width = 72
    return f"\n{'=' * width}\n  {title}\n{'=' * width}"


def _format_currency(val: float) -> str:
    return f"${val:,.2f}"


def _format_pct(val: float) -> str:
    return f"{val:+.2f}%"


def generate_report(
    data_dir: Path,
    config_path: Optional[Path] = None,
    new_money: Optional[float] = None,
) -> str:
    """Generate the full daily portfolio report as a string.

    Args:
        data_dir: Directory with Fidelity CSV exports.
        config_path: Path to targets.yaml.  Auto-detected if None.
        new_money: Optional dollar amount for new-money split calculation.

    Returns:
        Formatted report string for terminal display.
    """
    config = load_config(config_path)
    target_alloc = config.get("target_allocation", {})
    dca_config = config.get("dca_cadence", {})
    legacy_config = config.get("legacy_positions", {})
    split_config = config.get("new_money_split", {})

    # Ingest all transactions.
    txns = load_all_csvs(data_dir, config=config)

    # Compute positions.
    positions = compute_positions(txns)
    pos_df = positions_to_dataframe(positions)

    # Fetch live prices for all held symbols.
    held_symbols = [sym for sym, pos in positions.items() if pos.shares > 0]
    prices = fetch_prices(held_symbols)

    # Compute allocation.
    alloc_rows = compute_allocation(
        positions,
        target_alloc,
        prices=prices,
        trim_threshold_pct=config.get("trim_rules", {}).get("threshold_pct", 5.0),
    )

    lines: list[str] = []
    now = datetime.now()
    lines.append(f"\n  Portfolio Daily Report — {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"  Data: {len(txns)} transactions from {data_dir.name}/")

    # ── Section 1: Current Positions ──
    lines.append(_header("CURRENT POSITIONS"))
    total_value = 0.0
    total_cost = 0.0
    for _, row in pos_df.iterrows():
        sym = row["symbol"]
        shares = row["shares"]
        price = prices.get(sym, 0.0)
        mv = shares * price
        total_value += mv
        total_cost += row["total_cost"]
        gain = mv - row["total_cost"]
        gain_pct = (gain / row["total_cost"] * 100) if row["total_cost"] > 0 else 0
        lines.append(
            f"  {sym:<6} {shares:>10.2f} sh  "
            f"@ {_format_currency(price):>10}  "
            f"= {_format_currency(mv):>12}  "
            f"cost {_format_currency(row['avg_cost']):>8}  "
            f"gain {_format_pct(gain_pct):>8}"
        )

    lines.append(f"\n  Total Portfolio Value: {_format_currency(total_value)}")
    lines.append(f"  Total Cost Basis:     {_format_currency(total_cost)}")
    total_gain = total_value - total_cost
    total_gain_pct = (total_gain / total_cost * 100) if total_cost > 0 else 0
    lines.append(
        f"  Total Gain/Loss:      {_format_currency(total_gain)} ({_format_pct(total_gain_pct)})"
    )

    # ── Section 2: Allocation vs Target ──
    lines.append(_header("ALLOCATION vs TARGET"))
    alloc_df = allocation_to_dataframe(alloc_rows)
    if not alloc_df.empty:
        for _, r in alloc_df.iterrows():
            signal_marker = ""
            if r["Signal"] == "trim":
                signal_marker = " << TRIM"
            elif r["Signal"] == "accumulate":
                signal_marker = " >> ACCUMULATE"
            lines.append(
                f"  {r['Symbol']:<6}  "
                f"current {r['Current %']:>6.2f}%  "
                f"target {r['Target %']:>6.2f}%  "
                f"delta {_format_pct(r['Delta %']):>8}"
                f"{signal_marker}"
            )

    # ── Section 3: Legacy Position Alerts ──
    if legacy_config:
        lines.append(_header("LEGACY POSITION ALERTS"))
        for sym, cfg in legacy_config.items():
            pos = positions.get(sym)
            if not pos or pos.shares <= 0:
                continue
            price = prices.get(sym, 0.0)
            action = cfg.get("action", "")
            if action == "reduce" and "exit_above" in cfg:
                exit_price = cfg["exit_above"]
                status = "SELL SIGNAL" if price > exit_price else "hold (below exit)"
                lines.append(
                    f"  {sym:<6}  {pos.shares:.0f} sh @ {_format_currency(price)}  "
                    f"exit above {_format_currency(exit_price)}  → {status}"
                )
            elif action == "tax_loss_harvest":
                gain = (price - pos.avg_cost) * pos.shares
                status = "HARVEST LOSS" if gain < 0 else "in profit (hold)"
                lines.append(
                    f"  {sym:<6}  {pos.shares:.0f} sh @ {_format_currency(price)}  "
                    f"avg cost {_format_currency(pos.avg_cost)}  → {status}"
                )

    # ── Section 4: DCA Cadence ──
    lines.append(_header("DCA CADENCE CHECK"))
    for sym, dca in dca_config.items():
        target_days = dca.get("interval_days", 0)
        target_lot = dca.get("lot_size_usd", 0)
        cadence_df = buying_cadence(txns, sym)
        if cadence_df.empty:
            lines.append(f"  {sym:<6}  No buy history")
            continue

        avg_gap = cadence_df["days_since_last"].dropna().mean()
        last_buy = cadence_df["run_date"].max()
        days_since = (pd.Timestamp.now() - last_buy).days if pd.notna(last_buy) else 0
        avg_lot = cadence_df["amount"].abs().mean()

        overdue = days_since > target_days * 1.5
        status = "OVERDUE" if overdue else "on track"

        lines.append(
            f"  {sym:<6}  "
            f"avg gap {avg_gap:.1f}d (target {target_days}d)  "
            f"last buy {days_since}d ago  "
            f"avg lot {_format_currency(avg_lot)} (target {_format_currency(target_lot)})  "
            f"→ {status}"
        )

    # ── Section 5: Dividend Summary ──
    lines.append(_header("DIVIDEND SUMMARY"))
    div_df = dividend_summary(txns)
    if not div_df.empty:
        current_year = now.year
        recent = div_df[div_df["year"] >= current_year - 1]
        for _, r in recent.iterrows():
            lines.append(
                f"  {r['symbol']:<6}  {int(r['year'])}  {_format_currency(r['total_dividends'])}"
            )
        total_divs = div_df["total_dividends"].sum()
        lines.append(f"\n  All-time dividends received: {_format_currency(total_divs)}")

    # ── Section 6: New Money Split (if requested) ──
    if new_money and new_money > 0:
        lines.append(_header(f"NEW MONEY SPLIT — {_format_currency(new_money)}"))
        split = new_money_split(new_money, split_config, prices)
        for sym, dollars, shares in split.allocations:
            price = prices.get(sym, 0.0)
            lines.append(
                f"  {sym:<6}  {_format_currency(dollars):>10}  "
                f"→ {shares} shares @ {_format_currency(price)}"
            )

    lines.append(f"\n{'─' * 72}")
    return "\n".join(lines)


def main() -> None:
    """CLI entry point for daily portfolio report."""
    parser = argparse.ArgumentParser(
        description="Generate daily portfolio allocation report"
    )
    parser.add_argument(
        "data_dir",
        type=Path,
        help="Directory containing Fidelity CSV exports",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to targets.yaml (default: config/targets.yaml)",
    )
    parser.add_argument(
        "--new-money",
        type=float,
        default=None,
        help="Dollar amount of new money to deploy",
    )

    args = parser.parse_args()
    report = generate_report(args.data_dir, args.config, args.new_money)
    print(report)


if __name__ == "__main__":
    main()
