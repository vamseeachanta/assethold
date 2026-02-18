"""
Signal history store for daily portfolio strategy.

Appends each day's combined signals to a persistent CSV so that
subsequent runs can detect and surface changes:

    BRKB: HOLD → BUILD ▲  (score +0.12 → +0.28)
    XOM:  TRIM → HOLD      (score -0.31 → -0.18)

History file: <history_dir>/signals.csv
Columns: date, ticker, signal, score
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from assethold.analysis.daily_strategy.signals import PositionSignal


@dataclass(frozen=True)
class SignalRecord:
    """One ticker's signal on one date."""

    date: date
    ticker: str
    signal: str
    score: float


@dataclass(frozen=True)
class SignalChange:
    """A signal that moved between two consecutive dates."""

    ticker: str
    prev_signal: str
    curr_signal: str
    prev_score: float
    curr_score: float

    @property
    def improved(self) -> bool:
        """True when the signal moved in the build direction."""
        return self.curr_score > self.prev_score

    def format(self) -> str:
        direction = "↑" if self.improved else "↓"
        return (
            f"{self.ticker}: {self.prev_signal} → {self.curr_signal} {direction}"
            f"  (score {self.prev_score:+.3f} → {self.curr_score:+.3f})"
        )


_SIGNAL_ORDER = {
    "STRONG BUILD": 0,
    "BUILD": 1,
    "HOLD": 2,
    "TRIM": 3,
    "STRONG TRIM": 4,
}

_CSV_FIELDS = ["date", "ticker", "signal", "score"]


class HistoryStore:
    """
    Persist and query daily signal snapshots.

    The store keeps one CSV at ``{history_dir}/signals.csv`` and grows it
    by appending a row per ticker each time ``record()`` is called.  It
    never re-writes old rows, so the file is safe to examine or import into
    a spreadsheet at any time.
    """

    def __init__(self, history_dir: Optional[Path] = None):
        """
        Args:
            history_dir: Directory for signals.csv.  Defaults to
                         <repo-root>/reports/daily-strategy/history/.
        """
        if history_dir is None:
            # history.py → daily_strategy/ → analysis/ → assethold-pkg/
            # → src/ → repo-root/
            history_dir = (
                Path(__file__).parents[4] / "reports" / "daily-strategy" / "history"
            )
        self._history_dir = Path(history_dir)
        self._csv_path = self._history_dir / "signals.csv"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, signals: list[PositionSignal], report_date: Optional[date] = None) -> None:
        """
        Append today's combined (de-duplicated by ticker) signals to the CSV.

        Args:
            signals:     Scored positions from SignalEngine.score_batch().
            report_date: Date stamp (default: today).
        """
        today = report_date or date.today()
        records = self._combine(signals, today)
        self._append(records)

    def previous(self, before: Optional[date] = None) -> dict[str, SignalRecord]:
        """
        Return the most recent signal record for each ticker before *before*.

        Args:
            before: Exclusive upper bound (default: today).

        Returns:
            ``{ticker: SignalRecord}`` mapping, empty if no history exists.
        """
        cutoff = before or date.today()
        rows = self._load()
        # Keep only rows strictly before the cutoff date
        eligible = [r for r in rows if r.date < cutoff]
        if not eligible:
            return {}
        # Latest date available
        latest_date = max(r.date for r in eligible)
        return {r.ticker: r for r in eligible if r.date == latest_date}

    def changes(
        self,
        current: list[PositionSignal],
        report_date: Optional[date] = None,
    ) -> list[SignalChange]:
        """
        Compare today's signals against the most recent stored day.

        Returns a list of :class:`SignalChange` for tickers whose signal
        label changed.  Tickers with no history entry are silently skipped.
        """
        today = report_date or date.today()
        prev = self.previous(before=today)
        if not prev:
            return []

        curr_map = {
            r.ticker: r for r in self._combine(current, today)
        }

        result: list[SignalChange] = []
        for ticker, curr_rec in curr_map.items():
            prev_rec = prev.get(ticker)
            if prev_rec is None or prev_rec.signal == curr_rec.signal:
                continue
            result.append(
                SignalChange(
                    ticker=ticker,
                    prev_signal=prev_rec.signal,
                    curr_signal=curr_rec.signal,
                    prev_score=prev_rec.score,
                    curr_score=curr_rec.score,
                )
            )

        # Sort: improvements first, then by ticker
        result.sort(key=lambda c: (not c.improved, c.ticker))
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _combine(signals: list[PositionSignal], today: date) -> list[SignalRecord]:
        """De-duplicate by ticker (same ticker in multiple accounts → one record)."""
        seen: dict[str, SignalRecord] = {}
        tradeable = [s for s in signals if s.position.tradeable and s.snapshot is not None]
        # Sort so the stronger signal wins when de-duplicating
        sorted_sigs = sorted(tradeable, key=lambda s: _SIGNAL_ORDER.get(s.signal, 2))
        for sig in sorted_sigs:
            t = sig.position.ticker
            if t not in seen:
                seen[t] = SignalRecord(
                    date=today,
                    ticker=t,
                    signal=sig.signal,
                    score=sig.score,
                )
        return list(seen.values())

    def _append(self, records: list[SignalRecord]) -> None:
        self._history_dir.mkdir(parents=True, exist_ok=True)
        write_header = not self._csv_path.exists()
        with self._csv_path.open("a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
            if write_header:
                writer.writeheader()
            for r in records:
                writer.writerow(
                    {
                        "date": r.date.isoformat(),
                        "ticker": r.ticker,
                        "signal": r.signal,
                        "score": f"{r.score:.4f}",
                    }
                )

    def _load(self) -> list[SignalRecord]:
        if not self._csv_path.exists():
            return []
        records: list[SignalRecord] = []
        with self._csv_path.open(newline="") as f:
            for row in csv.DictReader(f):
                try:
                    records.append(
                        SignalRecord(
                            date=date.fromisoformat(row["date"]),
                            ticker=row["ticker"],
                            signal=row["signal"],
                            score=float(row["score"]),
                        )
                    )
                except (KeyError, ValueError):
                    continue  # skip malformed rows
        return records
