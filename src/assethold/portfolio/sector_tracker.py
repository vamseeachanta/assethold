"""
GICS sector exposure tracker.

Classifies portfolio holdings by GICS sector using yfinance, calculates
market-value-weighted sector exposures, flags concentration risk (>30%
single sector), and produces rebalancing suggestions.

Usage::

    from assethold.portfolio.sector_tracker import SectorTracker

    tracker = SectorTracker()
    holdings = {"AAPL": 50_000.0, "JPM": 20_000.0, "XOM": 30_000.0}
    breakdown = tracker.build_breakdown(holdings)
    print(tracker.format_table(breakdown))

Wire into daily strategy output via the render_sector_section() helper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

try:
    import yfinance as yf  # type: ignore[import]
except ImportError:
    yf = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# GICS sector constants
# ---------------------------------------------------------------------------

GICS_SECTORS: list[str] = [
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Health Care",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
    "Utilities",
]

CONCENTRATION_THRESHOLD: float = 0.30  # 30% — warn when exceeded

# Tolerance band around target before a suggestion is emitted (±2%)
_REBALANCE_TOLERANCE: float = 0.02


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ConcentrationWarning:
    """A sector that exceeds the concentration threshold."""

    sector: str
    weight: float       # Actual weight as a fraction (0–1)
    threshold: float    # Threshold that was breached


@dataclass
class RebalancingSuggestion:
    """Rebalancing action for a single sector."""

    sector: str
    actual: float       # Current weight as a fraction
    target: float       # Target weight as a fraction
    delta: float        # actual - target (negative = overweight from target POV)
    action: str         # "TRIM" | "ADD" | "HOLD"


@dataclass
class SectorBreakdown:
    """Full sector exposure report for a portfolio snapshot."""

    sector_values: dict[str, float]           # Sector → total market value ($)
    weights: dict[str, float]                 # Sector → weight as fraction (0–1)
    total_value: float                        # Sum of all holding values ($)
    warnings: list[ConcentrationWarning] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def classify_holding(symbol: str) -> str:
    """
    Return the GICS sector for *symbol* by querying yfinance.

    Args:
        symbol: Ticker symbol (case-insensitive).

    Returns:
        Sector string from yfinance .info['sector'], or "Unknown" on any error.
    """
    if yf is None:
        return "Unknown"
    try:
        info = yf.Ticker(symbol.upper()).info or {}
        return str(info.get("sector", "Unknown") or "Unknown")
    except Exception:
        return "Unknown"


# ---------------------------------------------------------------------------
# SectorTracker
# ---------------------------------------------------------------------------


class SectorTracker:
    """
    Classify portfolio holdings by GICS sector, compute weights, and flag
    over-concentration.

    Internal sector lookups are cached per-instance so repeated calls to
    build_breakdown() with the same tickers avoid redundant network calls.
    """

    def __init__(self) -> None:
        self._sector_cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_breakdown(
        self,
        holdings: dict[str, float],
    ) -> SectorBreakdown:
        """
        Build a full sector breakdown for a portfolio snapshot.

        Args:
            holdings: Mapping of ticker → market value ($).  Values must be
                      non-negative; zero-value holdings are ignored.

        Returns:
            SectorBreakdown with weights, warnings, and total value.
        """
        if not holdings:
            return SectorBreakdown(
                sector_values={},
                weights={},
                total_value=0.0,
                warnings=[],
            )

        sector_values: dict[str, float] = {}
        for ticker, value in holdings.items():
            if value <= 0:
                continue
            sector = self._get_sector(ticker)
            sector_values[sector] = sector_values.get(sector, 0.0) + value

        total_value = sum(sector_values.values())
        if total_value == 0.0:
            return SectorBreakdown(
                sector_values=sector_values,
                weights={},
                total_value=0.0,
                warnings=[],
            )

        weights = {s: v / total_value for s, v in sector_values.items()}
        warnings = self._check_concentration(weights)

        return SectorBreakdown(
            sector_values=sector_values,
            weights=weights,
            total_value=total_value,
            warnings=warnings,
        )

    def rebalancing_suggestions(
        self,
        breakdown: SectorBreakdown,
        target: dict[str, float],
    ) -> list[RebalancingSuggestion]:
        """
        Generate sector-level rebalancing suggestions.

        Args:
            breakdown: Current portfolio sector breakdown.
            target:    Target sector weights as fractions (0–1).  Only sectors
                       present in *target* are evaluated.

        Returns:
            List of RebalancingSuggestion objects sorted by |delta| descending.
        """
        if not target:
            return []

        suggestions: list[RebalancingSuggestion] = []
        for sector, target_weight in target.items():
            actual_weight = breakdown.weights.get(sector, 0.0)
            delta = actual_weight - target_weight
            if delta > _REBALANCE_TOLERANCE:
                action = "TRIM"
            elif delta < -_REBALANCE_TOLERANCE:
                action = "ADD"
            else:
                action = "HOLD"
            suggestions.append(
                RebalancingSuggestion(
                    sector=sector,
                    actual=actual_weight,
                    target=target_weight,
                    delta=delta,
                    action=action,
                )
            )

        suggestions.sort(key=lambda s: abs(s.delta), reverse=True)
        return suggestions

    def format_table(self, breakdown: SectorBreakdown) -> str:
        """
        Render the sector breakdown as a plain-text console table.

        Sectors exceeding the concentration threshold are marked OVERWEIGHT.

        Args:
            breakdown: Output of build_breakdown().

        Returns:
            Multi-line string suitable for printing.
        """
        if not breakdown.weights:
            return "No sector data available.\n"

        overweight_sectors = {w.sector for w in breakdown.warnings}
        sorted_items = sorted(
            breakdown.weights.items(), key=lambda kv: kv[1], reverse=True
        )

        header = f"{'Sector':<30} {'Weight':>7}  {'Value ($)':>14}  {'Status'}"
        separator = "-" * 68
        lines: list[str] = [
            "",
            "== Sector Exposure Breakdown ==",
            header,
            separator,
        ]

        for sector, weight in sorted_items:
            value = breakdown.sector_values.get(sector, 0.0)
            pct_str = f"{weight * 100:.1f}%"
            value_str = f"${value:,.0f}"
            status = "OVERWEIGHT !" if sector in overweight_sectors else ""
            lines.append(
                f"{sector:<30} {pct_str:>7}  {value_str:>14}  {status}"
            )

        lines.append(separator)
        total_str = f"${breakdown.total_value:,.0f}"
        lines.append(f"{'Total':<30} {'100.0%':>7}  {total_str:>14}")
        lines.append("")

        if breakdown.warnings:
            lines.append("Concentration warnings:")
            for w in breakdown.warnings:
                lines.append(
                    f"  WARNING: {w.sector} at {w.weight * 100:.1f}% "
                    f"exceeds {w.threshold * 100:.0f}% threshold"
                )
            lines.append("")

        return "\n".join(lines)

    def render_sector_section(
        self,
        breakdown: SectorBreakdown,
        suggestions: Optional[list[RebalancingSuggestion]] = None,
    ) -> str:
        """
        Render the sector breakdown as a Markdown section for the daily
        strategy report.

        Args:
            breakdown:   Output of build_breakdown().
            suggestions: Optional rebalancing suggestions from
                         rebalancing_suggestions().

        Returns:
            Markdown string suitable for appending to DailyStrategyReport output.
        """
        lines: list[str] = ["## Sector Exposure", ""]

        if not breakdown.weights:
            lines.append("*No sector data available.*")
            lines.append("")
            return "\n".join(lines)

        lines.append(
            f"**Total portfolio value:** ${breakdown.total_value:,.2f}  "
        )
        lines.append("")

        # Sector table
        lines.append("| Sector | Weight | Market Value | Status |")
        lines.append("|--------|-------:|-------------:|--------|")
        overweight_sectors = {w.sector for w in breakdown.warnings}
        for sector, weight in sorted(
            breakdown.weights.items(), key=lambda kv: kv[1], reverse=True
        ):
            value = breakdown.sector_values.get(sector, 0.0)
            status = "OVERWEIGHT" if sector in overweight_sectors else ""
            lines.append(
                f"| {sector} | {weight * 100:.1f}% | "
                f"${value:,.0f} | {status} |"
            )

        lines.append("")

        # Concentration warnings
        if breakdown.warnings:
            lines.append("### Concentration Warnings")
            lines.append("")
            for w in breakdown.warnings:
                lines.append(
                    f"- **{w.sector}** at {w.weight * 100:.1f}% exceeds "
                    f"{w.threshold * 100:.0f}% threshold"
                )
            lines.append("")

        # Rebalancing suggestions
        if suggestions:
            lines.append("### Rebalancing Suggestions")
            lines.append("")
            lines.append("| Sector | Action | Current | Target | Delta |")
            lines.append("|--------|--------|--------:|-------:|------:|")
            for sug in suggestions:
                if sug.action == "HOLD":
                    continue
                lines.append(
                    f"| {sug.sector} | {sug.action} | "
                    f"{sug.actual * 100:.1f}% | "
                    f"{sug.target * 100:.1f}% | "
                    f"{sug.delta * 100:+.1f}% |"
                )
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_sector(self, ticker: str) -> str:
        """Return sector for *ticker*, using instance cache."""
        ticker = ticker.upper().strip()
        if ticker not in self._sector_cache:
            self._sector_cache[ticker] = self._fetch_sector(ticker)
        return self._sector_cache[ticker]

    def _fetch_sector(self, symbol: str) -> str:
        """Thin wrapper around classify_holding for easy test substitution."""
        return classify_holding(symbol)

    @staticmethod
    def _check_concentration(
        weights: dict[str, float],
    ) -> list[ConcentrationWarning]:
        """Return a warning for each sector that exceeds CONCENTRATION_THRESHOLD."""
        warnings: list[ConcentrationWarning] = []
        for sector, weight in weights.items():
            if weight > CONCENTRATION_THRESHOLD:
                warnings.append(
                    ConcentrationWarning(
                        sector=sector,
                        weight=weight,
                        threshold=CONCENTRATION_THRESHOLD,
                    )
                )
        return warnings
