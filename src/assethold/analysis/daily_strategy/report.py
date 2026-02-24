"""
Daily strategy report generator.

Produces a Markdown report with two sections:
  1. Per-account — each Fidelity account on its own table
  2. Combined portfolio — all accounts merged, with final signals

Signal ordering: STRONG BUILD -> BUILD -> HOLD -> TRIM -> STRONG TRIM
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from assethold.analysis.daily_strategy.history import SignalChange
from assethold.analysis.daily_strategy.signals import PositionSignal
from assethold.portfolio.sector_tracker import SectorBreakdown, RebalancingSuggestion

_SIGNAL_ORDER = {
    "STRONG BUILD": 0,
    "BUILD": 1,
    "HOLD": 2,
    "TRIM": 3,
    "STRONG TRIM": 4,
}

_SIGNAL_EMOJI = {
    "STRONG BUILD": "▲▲",
    "BUILD": "▲",
    "HOLD": "—",
    "TRIM": "▼",
    "STRONG TRIM": "▼▼",
}


class DailyStrategyReport:
    """Render a list of PositionSignals into a Markdown report."""

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Args:
            output_dir: Directory where the report file is written.
                        Defaults to <repo-root>/reports/daily-strategy/.
        """
        if output_dir is None:
            # report.py -> daily_strategy/ -> analysis/ -> assethold-pkg/
            # -> src/ -> repo-root/
            output_dir = Path(__file__).parents[4] / "reports" / "daily-strategy"
        self.output_dir = Path(output_dir)

    def render(
        self,
        signals: list[PositionSignal],
        report_date: Optional[datetime] = None,
        changes: Optional[list[SignalChange]] = None,
        sector_breakdown: Optional[SectorBreakdown] = None,
        sector_suggestions: Optional[list[RebalancingSuggestion]] = None,
        risk_metrics: Optional[dict] = None,
        fundamentals_df: Optional[pd.DataFrame] = None,
    ) -> str:
        """
        Render the full report as a Markdown string.

        Args:
            signals:            Scored positions (all accounts).
            report_date:        Date to stamp on the report (default: today).
            changes:            Signal changes vs prior day from HistoryStore.changes().
                                When provided, a "Changes Today" section is prepended.
            sector_breakdown:   Optional sector exposure breakdown to append.
            sector_suggestions: Optional rebalancing suggestions to append.
            risk_metrics:       Optional dict mapping ticker -> position_risk() output.
                                When provided, a "Risk Metrics" section is appended.
            fundamentals_df:    Optional DataFrame from FundamentalsScorer /
                                SectorPeerRanker.  When provided, a
                                "Fundamentals Scoring" section is appended.

        Returns:
            Markdown string.
        """
        date = report_date or datetime.today()
        date_str = date.strftime("%Y-%m-%d")
        tradeable = [s for s in signals if s.position.tradeable and s.snapshot is not None]

        total_value = sum(
            s.position.shares * s.snapshot.current_price for s in tradeable
        )

        lines: list[str] = []
        lines.append(f"# Daily Portfolio Strategy — {date_str}")
        lines.append("")
        lines.append(f"**Combined portfolio value:** ${total_value:,.2f}  ")
        lines.append(f"**Positions analysed:** {len(tradeable)}  ")
        lines.append(f"**Generated:** {date.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # -- Signal changes vs prior day ------------------------------------
        if changes is not None:
            lines.append("## Changes Today")
            lines.append("")
            if changes:
                for change in changes:
                    lines.append(f"- {change.format()}")
            else:
                lines.append("*No signal changes since last run.*")
            lines.append("")
            lines.append("---")
            lines.append("")

        # -- Per-account sections -------------------------------------------
        by_account: dict[str, list[PositionSignal]] = defaultdict(list)
        for sig in signals:
            by_account[sig.position.account].append(sig)

        lines.append("## Per-Account View")
        lines.append("")

        for account, acct_signals in sorted(by_account.items()):
            lines.append(f"### {account}")
            lines.append("")
            lines.extend(self._account_table(acct_signals))
            lines.append("")

        # -- Combined portfolio section -------------------------------------
        lines.append("---")
        lines.append("")
        lines.append("## Combined Portfolio")
        lines.append("")
        lines.extend(self._combined_table(tradeable, total_value))
        lines.append("")

        # -- Detailed rationale ---------------------------------------------
        lines.append("---")
        lines.append("")
        lines.append("## Signal Details")
        lines.append("")
        seen_tickers: set[str] = set()
        sorted_tradeable = sorted(tradeable, key=lambda s: _SIGNAL_ORDER.get(s.signal, 2))
        for sig in sorted_tradeable:
            if sig.position.ticker in seen_tickers:
                continue
            seen_tickers.add(sig.position.ticker)
            lines.extend(self._signal_detail(sig, total_value))
            lines.append("")

        # -- Sector exposure ------------------------------------------------
        if sector_breakdown is not None:
            from assethold.portfolio.sector_tracker import SectorTracker
            lines.append("---")
            lines.append("")
            st = SectorTracker()
            lines.append(
                st.render_sector_section(sector_breakdown, sector_suggestions)
            )

        # -- Risk metrics section -------------------------------------------
        if risk_metrics:
            lines.append("---")
            lines.append("")
            lines.extend(self._risk_metrics_section(risk_metrics))

        # -- Fundamentals scoring section -----------------------------------
        if fundamentals_df is not None and not fundamentals_df.empty:
            lines.append("---")
            lines.append("")
            lines.extend(self._fundamentals_section(fundamentals_df))

        # -- Methodology footer ---------------------------------------------
        lines.append("---")
        lines.append("")
        lines.append("## Methodology")
        lines.append("")
        lines.append(
            "Signals are a weighted composite of RSI momentum (25%), 52-week position (20%), "
            "price vs SMA-50 (20%), price vs SMA-200 (15%), and portfolio weight drift (10%). "
            "Fundamentals scoring (P/E, P/B, EV/EBITDA) adds a sector-peer value lens (WRK-322). "
            "`managed` positions use full signal range; `trim_only` positions (individual stocks) "
            "are capped at HOLD — build signals are suppressed."
        )
        lines.append("")
        lines.append(
            "*Market data from Yahoo Finance (yfinance). Prices and ratios are delayed. "
            "This report is for informational purposes only, not financial advice.*"
        )
        lines.append("")

        return "\n".join(lines)

    def write(
        self,
        signals: list[PositionSignal],
        report_date: Optional[datetime] = None,
        changes: Optional[list[SignalChange]] = None,
        sector_breakdown: Optional[SectorBreakdown] = None,
        sector_suggestions: Optional[list[RebalancingSuggestion]] = None,
        risk_metrics: Optional[dict] = None,
        fundamentals_df: Optional[pd.DataFrame] = None,
    ) -> Path:
        """
        Render and write the report to disk.

        Returns:
            Path to the written report file.
        """
        date = report_date or datetime.today()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = date.strftime("%Y-%m-%d") + ".md"
        path = self.output_dir / filename
        path.write_text(
            self.render(
                signals,
                report_date=date,
                changes=changes,
                sector_breakdown=sector_breakdown,
                sector_suggestions=sector_suggestions,
                risk_metrics=risk_metrics,
                fundamentals_df=fundamentals_df,
            )
        )
        return path

    def print_summary(
        self,
        signals: list[PositionSignal],
        total_value: float,
    ) -> None:
        """Print a compact combined-portfolio table to stdout."""
        tradeable = [s for s in signals if s.position.tradeable and s.snapshot is not None]
        print(f"\n{'Ticker':<8} {'Signal':<14} {'Score':>6} {'Price':>8} "
              f"{'RSI':>6} {'Weight':>7}")
        print("-" * 56)
        for sig in sorted(tradeable, key=lambda s: _SIGNAL_ORDER.get(s.signal, 2)):
            price = sig.snapshot.current_price
            rsi = f"{sig.snapshot.rsi_14:.0f}" if sig.snapshot.rsi_14 else "N/A"
            weight = (sig.position.shares * price / total_value * 100) if total_value > 0 else 0
            icon = _SIGNAL_EMOJI.get(sig.signal, "")
            print(
                f"{sig.position.ticker:<8} {sig.signal + ' ' + icon:<14} "
                f"{sig.score:>6.3f} ${price:>7.2f} {rsi:>6} {weight:>6.1f}%"
            )
        print(f"\nTotal: ${total_value:,.2f}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _account_table(self, signals: list[PositionSignal]) -> list[str]:
        rows = sorted(signals, key=lambda s: _SIGNAL_ORDER.get(s.signal, 2))
        lines = [
            "| Ticker | Shares | Current Price | Value | Signal |",
            "|--------|-------:|-------------:|------:|--------|",
        ]
        for sig in rows:
            pos = sig.position
            if sig.snapshot is not None:
                price = f"${sig.snapshot.current_price:,.2f}"
                value = f"${pos.shares * sig.snapshot.current_price:,.2f}"
            else:
                price = "N/A"
                value = "N/A"
            icon = _SIGNAL_EMOJI.get(sig.signal, "")
            lines.append(
                f"| {pos.ticker} | {pos.shares:.3f} | {price} | {value} "
                f"| {sig.signal} {icon} |"
            )
        return lines

    def _combined_table(
        self, tradeable: list[PositionSignal], total_value: float
    ) -> list[str]:
        # Merge by ticker: sum shares across accounts
        by_ticker: dict[str, dict] = {}
        for sig in tradeable:
            t = sig.position.ticker
            if t not in by_ticker:
                by_ticker[t] = {"shares": 0.0, "sig": sig}
            by_ticker[t]["shares"] += sig.position.shares

        sorted_tickers = sorted(
            by_ticker.items(),
            key=lambda kv: _SIGNAL_ORDER.get(kv[1]["sig"].signal, 2),
        )

        lines = [
            "| Ticker | Total Shares | Price | Market Value | Weight | Score | Signal | Insider |",
            "|--------|-------------:|------:|-------------:|-------:|------:|--------|---------|",
        ]
        for ticker, data in sorted_tickers:
            sig = data["sig"]
            snap = sig.snapshot
            shares = data["shares"]
            price = snap.current_price
            value = shares * price
            weight = value / total_value * 100 if total_value > 0 else 0
            icon = _SIGNAL_EMOJI.get(sig.signal, "")
            insider = getattr(snap, "insider_trend", None)
            insider_cell = "N/A"
            if insider is not None:
                iicon = {"BULLISH": "▲", "BEARISH": "▼", "MIXED": "↔", "NEUTRAL": "—",
                         "N/A": "—"}.get(insider.trend, "")
                insider_cell = f"{insider.trend} {iicon}"
            lines.append(
                f"| {ticker} | {shares:.3f} | ${price:,.2f} | ${value:,.2f} "
                f"| {weight:.1f}% | {sig.score:+.3f} | {sig.signal} {icon} | {insider_cell} |"
            )
        return lines

    def _signal_detail(self, sig: PositionSignal, total_value: float) -> list[str]:
        snap = sig.snapshot
        pos = sig.position
        icon = _SIGNAL_EMOJI.get(sig.signal, "")
        value = pos.shares * snap.current_price
        weight = value / total_value * 100 if total_value > 0 else 0

        lines = [
            f"### {pos.ticker} — {sig.signal} {icon}",
            "",
            f"**Score:** {sig.score:+.3f} | "
            f"**Price:** ${snap.current_price:,.2f} | "
            f"**Portfolio weight:** {weight:.1f}%",
            "",
            f"52-week: low ${snap.week52_low:,.2f} / high ${snap.week52_high:,.2f} "
            f"(currently {snap.pct_from_52w_low:.0f}% of range)",
        ]
        if snap.rsi_14 is not None:
            lines.append(f"RSI-14: {snap.rsi_14:.1f} | ")
        if snap.sma_50:
            lines[-1] = lines[-1].rstrip(" | ")
            lines[-1] += f"SMA-50: ${snap.sma_50:,.2f} | SMA-200: ${snap.sma_200 or 0:,.2f}"

        lines.append("")
        lines.append("**Key drivers:**")
        for note in sig.rationale:
            lines.append(f"- {note}")

        if pos.avg_cost_basis:
            gain_pct = (snap.current_price - pos.avg_cost_basis) / pos.avg_cost_basis * 100
            lines.append(
                f"- Avg cost basis: ${pos.avg_cost_basis:,.2f} "
                f"({'gain' if gain_pct >= 0 else 'loss'}: {gain_pct:+.1f}%)"
            )

        insider = getattr(snap, "insider_trend", None)
        if insider is not None:
            icon = {"BULLISH": "▲", "BEARISH": "▼", "MIXED": "↔", "NEUTRAL": "—"}.get(
                insider.trend, ""
            )
            lines.append("")
            lines.append(
                f"**Insider trend (90d):** {insider.trend} {icon} — {insider.summary}"
            )
            if insider.buys_90d > 0 or insider.sells_90d > 0:
                lines.append(
                    f"  - Open-market buys: {insider.buys_90d} | "
                    f"Sells: {insider.sells_90d} | "
                    f"Net shares: {insider.net_shares_90d:+,.0f}"
                )

        return lines

    def _fundamentals_section(self, df: pd.DataFrame) -> list[str]:
        """Render fundamentals DataFrame as a Markdown section.

        Args:
            df: Scored and ranked holdings DataFrame from FundamentalsScorer /
                SectorPeerRanker.

        Returns:
            List of Markdown lines for the Fundamentals Scoring section.
        """
        lines: list[str] = ["## Fundamentals Scoring", ""]
        lines.append(
            "Value scoring (P/E, P/B, EV/EBITDA) with sector-peer percentile ranks. "
            "Composite: P/E × 0.35 + P/B × 0.35 + EV/EBITDA × 0.30 (higher = more value)."
        )
        lines.append("")

        col_map = {
            "ticker": "Ticker",
            "sector": "Sector",
            "pe": "P/E",
            "pe_pct": "P/E %ile",
            "pb": "P/B",
            "pb_pct": "P/B %ile",
            "ev_ebitda": "EV/EBITDA",
            "ev_ebitda_pct": "EV %ile",
            "score": "Score",
            "deep_value": "Deep Value",
        }
        visible = [c for c in col_map if c in df.columns]
        if not visible:
            lines.append("*No fundamentals data available.*")
            lines.append("")
            return lines

        header = "| " + " | ".join(col_map[c] for c in visible) + " |"
        sep = "| " + " | ".join("---" for _ in visible) + " |"
        lines.append(header)
        lines.append(sep)

        for _, row in df.iterrows():
            cells = []
            for c in visible:
                val = row.get(c)
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    cells.append("N/A")
                elif c == "deep_value":
                    cells.append("YES" if val is True else ("" if val is False else "N/A"))
                elif c in ("score", "pe", "pb", "ev_ebitda"):
                    cells.append(f"{val:.2f}" if isinstance(val, float) else str(val))
                elif c in ("pe_pct", "pb_pct", "ev_ebitda_pct"):
                    cells.append(f"{val:.0f}%" if isinstance(val, float) else str(val))
                else:
                    cells.append(str(val))
            lines.append("| " + " | ".join(cells) + " |")

        lines.append("")
        deep_mask = df.get("deep_value", pd.Series(dtype=object)) == True  # noqa: E712
        deep_value_rows = df[deep_mask]
        if not deep_value_rows.empty:
            tickers = ", ".join(deep_value_rows["ticker"].tolist())
            lines.append(
                f"**Deep-value opportunities (top quintile vs sector peers):** {tickers}"
            )
            lines.append("")

        return lines

    def _risk_metrics_section(self, risk_metrics: dict) -> list[str]:
        """Render a Markdown risk metrics table for all tickers in risk_metrics.

        Args:
            risk_metrics: Dict mapping ticker -> position_risk() output dict.

        Returns:
            List of Markdown lines for the Risk Metrics section.
        """
        lines = [
            "## Risk Metrics",
            "",
            "| Ticker | VaR 95% | VaR 99% | CVaR 95% | CVaR 99% | "
            "Sharpe | Sortino | Max DD | Calmar |",
            "|--------|--------:|--------:|---------:|---------:|"
            "-------:|--------:|-------:|-------:|",
        ]
        for ticker, m in sorted(risk_metrics.items()):
            calmar_val = m.get("calmar", float("nan"))
            calmar_str = (
                "N/A" if math.isnan(calmar_val)
                else f"{calmar_val:>7.2f}"
            )
            dd = m.get("max_drawdown", 0.0)
            lines.append(
                f"| {ticker} "
                f"| {m['var_95']:>7.4f} "
                f"| {m['var_99']:>7.4f} "
                f"| {m['cvar_95']:>8.4f} "
                f"| {m['cvar_99']:>8.4f} "
                f"| {m['sharpe']:>6.2f} "
                f"| {m['sortino']:>7.2f} "
                f"| {dd:>6.4f} "
                f"| {calmar_str} |"
            )
        lines.append("")
        lines.append(
            "*VaR and CVaR are historical simulation at stated confidence. "
            "Sharpe and Sortino annualised at 252 periods. "
            "Max DD is peak-to-trough drawdown.*"
        )
        lines.append("")
        return lines
