# ABOUTME: Fundamentals report output — CSV and console table (WRK-322)
# ABOUTME: Renders scored holdings DataFrame to CSV file and fixed-width console table
"""
Fundamentals report output module.

Contains FundamentalsReport, which renders a scored-and-ranked holdings
DataFrame (from FundamentalsScorer / SectorPeerRanker) to CSV and console.

Separated from fundamentals.py to keep file size within the 400-line limit.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

_DISPLAY_COLUMNS = [
    "ticker", "sector", "pe", "pb", "ev_ebitda",
    "pe_pct", "pb_pct", "ev_ebitda_pct",
    "score", "deep_value", "dividend_yield", "forward_eps",
]

_DEEP_VALUE_MARKER = " ** DEEP VALUE **"


class FundamentalsReport:
    """Render a scored-and-ranked fundamentals DataFrame to CSV and console.

    Usage::

        reporter = FundamentalsReport()
        csv_path = reporter.to_csv(df, output_dir)
        print(reporter.console_table(df))
    """

    def to_csv(self, df: pd.DataFrame, output_dir: Path) -> Path:
        """Write the fundamentals DataFrame to a dated CSV file.

        Args:
            df:         DataFrame returned by FundamentalsScorer.fetch_and_rank
                        (optionally enriched by SectorPeerRanker).
            output_dir: Directory to write into.  Created if absent.

        Returns:
            Path to the written CSV file.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.today().strftime("%Y-%m-%d")
        filename = f"fundamentals-{date_str}.csv"
        path = output_dir / filename
        df.to_csv(path, index=False)
        return path

    def console_table(self, df: pd.DataFrame) -> str:
        """Render the fundamentals DataFrame as a fixed-width console table.

        Deep-value holdings (where deep_value == True) are marked with
        " ** DEEP VALUE **" at the end of their row.

        Args:
            df: Fundamentals DataFrame (scored and ranked).

        Returns:
            Multi-line string suitable for printing.
        """
        cols = [c for c in _DISPLAY_COLUMNS if c in df.columns]
        present = df[cols].copy()

        lines: list[str] = []
        header = " | ".join(f"{c:<14}" for c in cols)
        separator = "-" * len(header)
        lines.append("Fundamentals Scoring Report")
        lines.append(separator)
        lines.append(header)
        lines.append(separator)

        for _, row in present.iterrows():
            parts = []
            for c in cols:
                val = row[c]
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    parts.append(f"{'N/A':<14}")
                elif isinstance(val, bool):
                    parts.append(f"{'True' if val else 'False':<14}")
                elif isinstance(val, float):
                    parts.append(f"{val:<14.2f}")
                else:
                    parts.append(f"{str(val):<14}")
            row_str = " | ".join(parts)
            deep = row.get("deep_value", False)
            if deep is True:
                row_str += _DEEP_VALUE_MARKER
            lines.append(row_str)

        lines.append(separator)
        return "\n".join(lines)
