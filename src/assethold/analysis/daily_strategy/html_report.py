"""
HTML report generator for daily portfolio strategy.

Produces a self-contained, interactive HTML report with Plotly charts.
All CSS is inlined; Plotly.js is loaded from CDN.

Report sections:
  1. Executive Summary   — stat cards + signal changes + action priority
  2. Technical Indicators — RSI & SMA bar charts
  3. Insider Sentiment    — table of insider trends
  4. Fundamentals         — P/E, Fwd P/E, P/B, Beta, Div Yield, Analyst Rating
  5. Portfolio Breakdown  — per-account collapsible + pie chart
  6. Signal Details       — per-ticker deep-dive cards

Comparison mode (triggered when ``comparison_mode=True``):
  Replaces section 5 with a Comparison Matrix and radar chart.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from assethold.analysis.daily_strategy.history import SignalChange
from assethold.analysis.daily_strategy.signals import PositionSignal

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

_SIGNAL_ORDER = {
    "STRONG BUILD": 0,
    "BUILD": 1,
    "HOLD": 2,
    "TRIM": 3,
    "STRONG TRIM": 4,
}

_SIGNAL_BADGE_COLOR = {
    "STRONG BUILD": "#22c55e",   # green
    "BUILD": "#4ade80",           # light green
    "HOLD": "#3b82f6",            # blue
    "TRIM": "#f97316",            # orange
    "STRONG TRIM": "#ef4444",     # red
}

_INSIDER_BADGE_COLOR = {
    "BULLISH": "#22c55e",
    "BEARISH": "#ef4444",
    "MIXED": "#f59e0b",
    "NEUTRAL": "#94a3b8",
    "N/A": "#94a3b8",
}


# ------------------------------------------------------------------
# Helper: Plotly JSON serialisation
# ------------------------------------------------------------------

def _plotly_json(data: list, layout: dict) -> str:
    """Serialise Plotly data + layout to JSON string (handles NaN)."""
    payload = {"data": data, "layout": layout}
    return json.dumps(payload, allow_nan=False, default=lambda o: None)


# ------------------------------------------------------------------
# Main report class
# ------------------------------------------------------------------

class DailyStrategyHtmlReport:
    """Generate a sectioned, interactive HTML daily-strategy report."""

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Args:
            output_dir: Directory for output files.  Defaults to
                        <repo-root>/reports/daily-strategy/.
        """
        if output_dir is None:
            # html_report.py → daily_strategy/ → analysis/ → assethold-pkg/
            # → src/ → repo-root/
            output_dir = Path(__file__).parents[4] / "reports" / "daily-strategy"
        self.output_dir = Path(output_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        signals: list[PositionSignal],
        report_date: Optional[datetime] = None,
        changes: Optional[list[SignalChange]] = None,
        comparison_mode: bool = False,
    ) -> str:
        """
        Render the full HTML report as a string.

        Args:
            signals:         Scored positions from SignalEngine.
            report_date:     Date stamp (default: today).
            changes:         Signal changes from HistoryStore.changes().
            comparison_mode: When True, replaces Portfolio Breakdown with
                             Comparison Matrix.

        Returns:
            Complete HTML string.
        """
        date = report_date or datetime.today()
        tradeable = [s for s in signals if s.position.tradeable and s.snapshot is not None]

        total_value = sum(
            s.position.shares * s.snapshot.current_price for s in tradeable
        )

        html_parts: list[str] = [
            self._head(date),
            self._body_open(),
            self._header(date, total_value),
            self._section_summary(tradeable, total_value, changes),
            self._section_technical(tradeable),
            self._section_insider(tradeable),
            self._section_fundamentals(tradeable),
        ]

        if comparison_mode:
            html_parts.append(self._section_comparison_matrix(tradeable))
        else:
            html_parts.append(self._section_portfolio(signals, tradeable, total_value))

        html_parts.append(self._section_signal_details(tradeable, total_value))
        html_parts.append(self._footer())
        html_parts.append(self._body_close())

        return "\n".join(html_parts)

    def write(
        self,
        signals: list[PositionSignal],
        report_date: Optional[datetime] = None,
        changes: Optional[list[SignalChange]] = None,
        comparison_mode: bool = False,
    ) -> Path:
        """Render and write the report to disk; return the output path."""
        date = report_date or datetime.today()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = date.strftime("%Y-%m-%d") + ".html"
        path = self.output_dir / filename
        path.write_text(
            self.generate(signals, report_date=date, changes=changes,
                          comparison_mode=comparison_mode),
            encoding="utf-8",
        )
        return path

    # ------------------------------------------------------------------
    # Document skeleton
    # ------------------------------------------------------------------

    def _head(self, date: datetime) -> str:
        title = f"Daily Strategy — {date.strftime('%Y-%m-%d')}"
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                         Oxygen, Ubuntu, Cantarell, sans-serif;
            background-color: #f5f7fa;
            padding: 20px;
            color: #2d3748;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .report-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .report-header h1 {{ font-size: 2.2em; margin-bottom: 8px; font-weight: 700; }}
        .report-header p {{ font-size: 1.05em; opacity: 0.95; margin: 4px 0; }}
        .section {{
            background: white;
            padding: 28px 30px;
            border-radius: 10px;
            margin-bottom: 24px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
        }}
        .section h2 {{
            font-size: 1.4em;
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 18px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e2e8f0;
        }}
        .section h3 {{ font-size: 1.1em; font-weight: 600; margin: 16px 0 10px; color: #4a5568; }}
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: #f8fafc;
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #e2e8f0;
        }}
        .stat-label {{
            font-size: 0.78em;
            color: #718096;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        .stat-value {{ font-size: 2em; font-weight: 700; color: #667eea; line-height: 1; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; }}
        th {{
            text-align: left;
            padding: 8px 12px;
            background: #f7f8fa;
            border-bottom: 2px solid #e2e8f0;
            font-weight: 600;
            color: #4a5568;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }}
        td {{ padding: 8px 12px; border-bottom: 1px solid #f0f2f5; }}
        tr:hover td {{ background: #f8fafc; }}
        .badge {{
            display: inline-block;
            padding: 3px 9px;
            border-radius: 12px;
            font-size: 0.78em;
            font-weight: 600;
            color: white;
        }}
        .badge-build   {{ background: #22c55e; }}
        .badge-hold    {{ background: #3b82f6; }}
        .badge-trim    {{ background: #f97316; }}
        .badge-strong-build {{ background: #16a34a; }}
        .badge-strong-trim  {{ background: #dc2626; }}
        .badge-bullish  {{ background: #22c55e; }}
        .badge-bearish  {{ background: #ef4444; }}
        .badge-mixed    {{ background: #f59e0b; }}
        .badge-neutral  {{ background: #94a3b8; }}
        .plot-box {{ margin-top: 20px; }}
        details summary {{
            cursor: pointer;
            font-weight: 600;
            padding: 8px 0;
            color: #667eea;
        }}
        details summary:hover {{ color: #764ba2; }}
        .signal-card {{
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 14px;
        }}
        .signal-card-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
        .signal-card-ticker {{ font-size: 1.3em; font-weight: 700; }}
        .signal-card-price {{ color: #718096; }}
        .signal-card-rationale {{ list-style: none; padding: 0; }}
        .signal-card-rationale li {{ padding: 3px 0; color: #4a5568; font-size: 0.9em; }}
        .signal-card-rationale li::before {{ content: "→ "; color: #a0aec0; }}
        .footer {{
            background: white;
            padding: 18px 24px;
            border-radius: 10px;
            margin-top: 24px;
            text-align: center;
            color: #718096;
            font-size: 0.85em;
        }}
        .footer p {{ margin: 4px 0; }}
        @media (max-width: 768px) {{
            .report-header {{ padding: 24px; }}
            .report-header h1 {{ font-size: 1.6em; }}
            .stat-grid {{ grid-template-columns: 1fr 1fr; }}
        }}
    </style>
</head>"""

    def _body_open(self) -> str:
        return "<body>\n<div class=\"container\">"

    def _body_close(self) -> str:
        return "</div>\n</body>\n</html>"

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _header(self, date: datetime, total_value: float) -> str:
        return f"""
    <div class="report-header">
        <h1>Daily Portfolio Strategy</h1>
        <p><strong>Date:</strong> {date.strftime('%Y-%m-%d')}</p>
        <p><strong>Portfolio value:</strong> ${total_value:,.2f}</p>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    </div>"""

    # ------------------------------------------------------------------
    # Section 1: Executive Summary
    # ------------------------------------------------------------------

    def _section_summary(
        self,
        tradeable: list[PositionSignal],
        total_value: float,
        changes: Optional[list[SignalChange]],
    ) -> str:
        builds = sum(1 for s in tradeable if "BUILD" in s.signal)
        trims = sum(1 for s in tradeable if "TRIM" in s.signal)

        # Biggest single-day mover by score magnitude
        biggest = ""
        if tradeable:
            top = max(tradeable, key=lambda s: abs(s.score))
            biggest = f"{top.position.ticker} ({top.score:+.3f})"

        stat_grid = f"""
        <div class="stat-grid">
            <div class="stat-card">
                <div class="stat-label">Portfolio Value</div>
                <div class="stat-value">${total_value:,.0f}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Positions</div>
                <div class="stat-value">{len(tradeable)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Build Signals</div>
                <div class="stat-value">{builds}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Trim Signals</div>
                <div class="stat-value">{trims}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Highest Score</div>
                <div class="stat-value" style="font-size:1.1em">{biggest or "—"}</div>
            </div>
        </div>"""

        # Signal changes table
        changes_html = ""
        if changes is not None:
            if changes:
                rows = "".join(
                    f"<tr><td>{c.ticker}</td>"
                    f"<td>{c.prev_signal}</td>"
                    f"<td>{c.curr_signal}</td>"
                    f"<td>{'↑' if c.improved else '↓'} "
                    f"{c.prev_score:+.3f} → {c.curr_score:+.3f}</td></tr>"
                    for c in changes
                )
                changes_html = f"""
        <h3>Signal Changes Since Last Run</h3>
        <table>
            <thead>
                <tr><th>Ticker</th><th>Previous</th><th>Current</th><th>Score Move</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>"""
            else:
                changes_html = "<p style='color:#718096;margin-top:12px'>No signal changes since last run.</p>"

        # Action priority table (sorted by signal strength)
        sorted_sigs = sorted(tradeable, key=lambda s: _SIGNAL_ORDER.get(s.signal, 2))
        priority_rows = "".join(
            f"<tr>"
            f"<td><strong>{s.position.ticker}</strong></td>"
            f"<td>{self._signal_badge(s.signal)}</td>"
            f"<td>{s.score:+.3f}</td>"
            f"<td>${s.snapshot.current_price:,.2f}</td>"
            f"<td>{(s.position.shares * s.snapshot.current_price / total_value * 100):.1f}%</td>"
            f"</tr>"
            for s in sorted_sigs
        )
        priority_table = f"""
        <h3 style="margin-top:20px">Action Priority</h3>
        <table>
            <thead>
                <tr><th>Ticker</th><th>Signal</th><th>Score</th>
                    <th>Price</th><th>Weight</th></tr>
            </thead>
            <tbody>{priority_rows}</tbody>
        </table>"""

        return f"""
    <div class="section">
        <h2>1. Executive Summary</h2>
        {stat_grid}
        {changes_html}
        {priority_table}
    </div>"""

    # ------------------------------------------------------------------
    # Section 2: Technical Indicators
    # ------------------------------------------------------------------

    def _section_technical(self, tradeable: list[PositionSignal]) -> str:
        rows = sorted(tradeable, key=lambda s: s.position.ticker)
        tickers = [s.position.ticker for s in rows]

        def pct_from_sma(s: PositionSignal, sma: Optional[float]) -> Optional[float]:
            if sma is None or sma == 0:
                return None
            return (s.snapshot.current_price - sma) / sma * 100

        # Table
        table_rows = "".join(
            f"<tr>"
            f"<td><strong>{s.position.ticker}</strong></td>"
            f"<td>{s.snapshot.rsi_14:.1f}" if s.snapshot.rsi_14 is not None else "<td>N/A"
            f"</td>"
            f"<td>{pct_from_sma(s, s.snapshot.sma_50):+.1f}%"
            if pct_from_sma(s, s.snapshot.sma_50) is not None else "<td>N/A"
            f"</td>"
            f"<td>{pct_from_sma(s, s.snapshot.sma_200):+.1f}%"
            if pct_from_sma(s, s.snapshot.sma_200) is not None else "<td>N/A"
            f"</td>"
            f"<td>{s.snapshot.pct_from_52w_low:.0f}%</td>"
            f"<td>{self._trend_badge(s)}</td>"
            f"</tr>"
            for s in rows
        )

        table_html = f"""
        <table>
            <thead>
                <tr><th>Ticker</th><th>RSI-14</th><th>vs SMA-50</th>
                    <th>vs SMA-200</th><th>52w Position</th><th>Trend</th></tr>
            </thead>
            <tbody>{table_rows}</tbody>
        </table>"""

        # RSI bar chart
        rsi_values = [s.snapshot.rsi_14 if s.snapshot.rsi_14 is not None else 50.0 for s in rows]
        rsi_colors = [
            "#ef4444" if (v is not None and v > 70) else
            "#22c55e" if (v is not None and v < 30) else
            "#667eea"
            for v in rsi_values
        ]
        rsi_chart = self._bar_chart(
            plot_id="rsi_chart",
            x=tickers,
            y=rsi_values,
            marker_colors=rsi_colors,
            title="RSI-14 by Ticker",
            yaxis_title="RSI",
            shapes=[
                {"type": "line", "y0": 70, "y1": 70, "x0": -0.5,
                 "x1": len(tickers) - 0.5, "line": {"color": "#ef4444", "dash": "dash", "width": 1}},
                {"type": "line", "y0": 30, "y1": 30, "x0": -0.5,
                 "x1": len(tickers) - 0.5, "line": {"color": "#22c55e", "dash": "dash", "width": 1}},
            ],
        )

        # % from SMA-50 chart
        sma50_pcts = [
            pct_from_sma(s, s.snapshot.sma_50) if pct_from_sma(s, s.snapshot.sma_50) is not None else 0.0
            for s in rows
        ]
        sma50_colors = ["#22c55e" if v < 0 else "#f97316" for v in sma50_pcts]
        sma50_chart = self._bar_chart(
            plot_id="sma50_chart",
            x=tickers,
            y=sma50_pcts,
            marker_colors=sma50_colors,
            title="% from SMA-50",
            yaxis_title="% difference",
        )

        return f"""
    <div class="section">
        <h2>2. Technical Indicators</h2>
        {table_html}
        <div class="plot-box" id="rsi_chart"></div>
        <div class="plot-box" id="sma50_chart"></div>
    </div>
    {rsi_chart}
    {sma50_chart}"""

    # ------------------------------------------------------------------
    # Section 3: Insider Sentiment
    # ------------------------------------------------------------------

    def _section_insider(self, tradeable: list[PositionSignal]) -> str:
        rows = sorted(tradeable, key=lambda s: s.position.ticker)
        table_rows = []
        for s in rows:
            insider = getattr(s.snapshot, "insider_trend", None)
            if insider is None:
                row = (
                    f"<tr><td><strong>{s.position.ticker}</strong></td>"
                    f"<td>{self._insider_badge('N/A')}</td>"
                    f"<td>—</td><td>—</td><td>—</td><td>—</td></tr>"
                )
            else:
                last = f"{insider.last_activity_days}d ago" if insider.last_activity_days is not None else "—"
                row = (
                    f"<tr><td><strong>{s.position.ticker}</strong></td>"
                    f"<td>{self._insider_badge(insider.trend)}</td>"
                    f"<td>{insider.buys_90d}</td>"
                    f"<td>{insider.sells_90d}</td>"
                    f"<td>{insider.net_shares_90d:+,.0f}</td>"
                    f"<td>{last}</td></tr>"
                )
            table_rows.append(row)

        return f"""
    <div class="section">
        <h2>3. Insider Sentiment</h2>
        <table>
            <thead>
                <tr><th>Ticker</th><th>Trend</th><th>Buys (90d)</th>
                    <th>Sells (90d)</th><th>Net Shares</th><th>Last Activity</th></tr>
            </thead>
            <tbody>{''.join(table_rows)}</tbody>
        </table>
    </div>"""

    # ------------------------------------------------------------------
    # Section 4: Fundamentals
    # ------------------------------------------------------------------

    def _section_fundamentals(self, tradeable: list[PositionSignal]) -> str:
        rows = sorted(tradeable, key=lambda s: s.position.ticker)

        def fmt_float(v: Optional[float], decimals: int = 2, suffix: str = "") -> str:
            if v is None:
                return "N/A"
            return f"{v:.{decimals}f}{suffix}"

        table_rows = "".join(
            f"<tr>"
            f"<td><strong>{s.position.ticker}</strong></td>"
            f"<td>{fmt_float(s.snapshot.pe_ratio, 1)}</td>"
            f"<td>{fmt_float(getattr(s.snapshot, 'forward_pe', None), 1)}</td>"
            f"<td>{fmt_float(s.snapshot.price_to_book, 2)}</td>"
            f"<td>{fmt_float(getattr(s.snapshot, 'beta', None), 2)}</td>"
            f"<td>{fmt_float(getattr(s.snapshot, 'dividend_yield', None), 2, '%') if getattr(s.snapshot, 'dividend_yield', None) is not None else 'N/A'}</td>"
            f"<td>{getattr(s.snapshot, 'analyst_rating', None) or 'N/A'}</td>"
            f"</tr>"
            for s in rows
        )

        return f"""
    <div class="section">
        <h2>4. Fundamentals</h2>
        <table>
            <thead>
                <tr><th>Ticker</th><th>P/E (TTM)</th><th>Fwd P/E</th>
                    <th>P/B</th><th>Beta</th><th>Div Yield</th><th>Analyst Rating</th></tr>
            </thead>
            <tbody>{table_rows}</tbody>
        </table>
    </div>"""

    # ------------------------------------------------------------------
    # Section 5a: Portfolio Breakdown (default mode)
    # ------------------------------------------------------------------

    def _section_portfolio(
        self,
        all_signals: list[PositionSignal],
        tradeable: list[PositionSignal],
        total_value: float,
    ) -> str:
        by_account: dict[str, list[PositionSignal]] = defaultdict(list)
        for sig in all_signals:
            by_account[sig.position.account].append(sig)

        account_sections = []
        for account, acct_sigs in sorted(by_account.items()):
            acct_tradeable = [s for s in acct_sigs if s.position.tradeable and s.snapshot is not None]
            rows = "".join(
                f"<tr>"
                f"<td><strong>{s.position.ticker}</strong></td>"
                f"<td>{s.position.shares:.3f}</td>"
                f"<td>${s.snapshot.current_price:,.2f}</td>"
                f"<td>${s.position.shares * s.snapshot.current_price:,.2f}</td>"
                f"<td>{self._signal_badge(s.signal)}</td>"
                f"</tr>"
                for s in sorted(acct_tradeable, key=lambda x: _SIGNAL_ORDER.get(x.signal, 2))
            )
            account_sections.append(f"""
        <details open>
            <summary>{account}</summary>
            <table style="margin-top:10px">
                <thead>
                    <tr><th>Ticker</th><th>Shares</th><th>Price</th><th>Value</th><th>Signal</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </details>""")

        # Pie chart: weight distribution across tradeable positions
        labels = [s.position.ticker for s in tradeable]
        values = [s.position.shares * s.snapshot.current_price for s in tradeable]
        pie_chart = self._pie_chart("portfolio_pie", labels, values, "Portfolio Weight Distribution")

        return f"""
    <div class="section">
        <h2>5. Portfolio Breakdown</h2>
        {''.join(account_sections)}
        <div class="plot-box" id="portfolio_pie"></div>
    </div>
    {pie_chart}"""

    # ------------------------------------------------------------------
    # Section 5b: Comparison Matrix (comparison mode)
    # ------------------------------------------------------------------

    def _section_comparison_matrix(self, tradeable: list[PositionSignal]) -> str:
        sorted_sigs = sorted(tradeable, key=lambda s: _SIGNAL_ORDER.get(s.signal, 2))
        table_rows = "".join(
            f"<tr>"
            f"<td><strong>{s.position.ticker}</strong></td>"
            f"<td>{self._signal_badge(s.signal)}</td>"
            f"<td>{s.score:+.3f}</td>"
            f"<td>${s.snapshot.current_price:,.2f}</td>"
            f"<td>{s.snapshot.rsi_14:.1f}" if s.snapshot.rsi_14 is not None else "<td>N/A"
            f"</td>"
            f"<td>{s.snapshot.pe_ratio:.1f}" if s.snapshot.pe_ratio is not None else "<td>N/A"
            f"</td>"
            f"<td>{self._insider_badge(getattr(getattr(s.snapshot, 'insider_trend', None), 'trend', 'N/A'))}</td>"
            f"</tr>"
            for s in sorted_sigs
        )

        # Radar-style bar chart: scores by ticker
        tickers = [s.position.ticker for s in sorted_sigs]
        scores = [s.score for s in sorted_sigs]
        bar_colors = [_SIGNAL_BADGE_COLOR.get(s.signal, "#94a3b8") for s in sorted_sigs]
        radar = self._bar_chart(
            plot_id="comparison_scores",
            x=tickers,
            y=scores,
            marker_colors=bar_colors,
            title="Comparison: Signal Scores",
            yaxis_title="Score [-1, +1]",
        )

        return f"""
    <div class="section">
        <h2>5. Comparison Matrix</h2>
        <table>
            <thead>
                <tr><th>Ticker</th><th>Signal</th><th>Score</th>
                    <th>Price</th><th>RSI-14</th><th>P/E</th><th>Insider</th></tr>
            </thead>
            <tbody>{table_rows}</tbody>
        </table>
        <div class="plot-box" id="comparison_scores"></div>
    </div>
    {radar}"""

    # ------------------------------------------------------------------
    # Section 6: Signal Details
    # ------------------------------------------------------------------

    def _section_signal_details(
        self, tradeable: list[PositionSignal], total_value: float
    ) -> str:
        seen: set[str] = set()
        sorted_sigs = sorted(tradeable, key=lambda s: _SIGNAL_ORDER.get(s.signal, 2))
        cards = []
        for s in sorted_sigs:
            if s.position.ticker in seen:
                continue
            seen.add(s.position.ticker)
            snap = s.snapshot
            pos = s.position
            weight = pos.shares * snap.current_price / total_value * 100 if total_value > 0 else 0

            rationale_items = "".join(f"<li>{note}</li>" for note in s.rationale)

            cost_line = ""
            if pos.avg_cost_basis:
                gain_pct = (snap.current_price - pos.avg_cost_basis) / pos.avg_cost_basis * 100
                direction = "gain" if gain_pct >= 0 else "loss"
                cost_line = (
                    f"<p style='margin-top:8px;color:#718096;font-size:0.88em'>"
                    f"Avg cost: ${pos.avg_cost_basis:,.2f} "
                    f"({direction}: {gain_pct:+.1f}%)</p>"
                )

            cards.append(f"""
        <div class="signal-card">
            <div class="signal-card-header">
                <span class="signal-card-ticker">{pos.ticker}</span>
                {self._signal_badge(s.signal)}
                <span class="signal-card-price">
                    Score: {s.score:+.3f} | ${snap.current_price:,.2f} | Weight: {weight:.1f}%
                </span>
            </div>
            <ul class="signal-card-rationale">{rationale_items}</ul>
            {cost_line}
        </div>""")

        return f"""
    <div class="section">
        <h2>6. Signal Details</h2>
        {''.join(cards)}
    </div>"""

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    def _footer(self) -> str:
        return """
    <div class="footer">
        <p>Signals: weighted composite of RSI momentum (25%), 52-week position (20%),
           price vs SMA-50 (20%), price vs SMA-200 (15%), insider trend (10%),
           portfolio weight drift (10%). P/E sector comparison deferred to v2.</p>
        <p style="margin-top:6px;color:#a0aec0">
            Market data from Yahoo Finance (yfinance). Prices delayed.
            For informational purposes only — not financial advice.
        </p>
    </div>"""

    # ------------------------------------------------------------------
    # Plotly chart helpers
    # ------------------------------------------------------------------

    def _bar_chart(
        self,
        plot_id: str,
        x: list,
        y: list,
        marker_colors: Optional[list] = None,
        title: str = "",
        yaxis_title: str = "",
        shapes: Optional[list] = None,
    ) -> str:
        """Return a <script> block that renders a Plotly bar chart."""
        trace = {
            "type": "bar",
            "x": x,
            "y": y,
            "marker": {"color": marker_colors or "#667eea"},
        }
        layout = {
            "title": title,
            "template": "plotly_white",
            "height": 300,
            "margin": {"t": 40, "b": 40, "l": 50, "r": 20},
            "yaxis": {"title": yaxis_title},
            "shapes": shapes or [],
        }
        payload = _plotly_json([trace], layout)
        return (
            f"<script>var _{plot_id}=JSON.parse({json.dumps(payload)});"
            f"Plotly.newPlot('{plot_id}', _{plot_id}.data, _{plot_id}.layout, "
            f"{{responsive:true}});</script>"
        )

    def _pie_chart(self, plot_id: str, labels: list, values: list, title: str) -> str:
        trace = {
            "type": "pie",
            "labels": labels,
            "values": values,
            "hole": 0.35,
        }
        layout = {
            "title": title,
            "template": "plotly_white",
            "height": 380,
            "margin": {"t": 40, "b": 20, "l": 20, "r": 20},
        }
        payload = _plotly_json([trace], layout)
        return (
            f"<script>var _{plot_id}=JSON.parse({json.dumps(payload)});"
            f"Plotly.newPlot('{plot_id}', _{plot_id}.data, _{plot_id}.layout, "
            f"{{responsive:true}});</script>"
        )

    # ------------------------------------------------------------------
    # Badge helpers
    # ------------------------------------------------------------------

    def _signal_badge(self, signal: str) -> str:
        color = _SIGNAL_BADGE_COLOR.get(signal, "#94a3b8")
        return f"<span class='badge' style='background:{color}'>{signal}</span>"

    def _insider_badge(self, trend: str) -> str:
        color = _INSIDER_BADGE_COLOR.get(trend, "#94a3b8")
        return f"<span class='badge' style='background:{color}'>{trend}</span>"

    def _trend_badge(self, s: PositionSignal) -> str:
        signal = s.signal
        color = _SIGNAL_BADGE_COLOR.get(signal, "#94a3b8")
        icon = {"STRONG BUILD": "▲▲", "BUILD": "▲", "HOLD": "—",
                "TRIM": "▼", "STRONG TRIM": "▼▼"}.get(signal, "")
        return f"<span class='badge' style='background:{color}'>{icon}</span>"
