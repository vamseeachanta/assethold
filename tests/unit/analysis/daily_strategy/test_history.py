"""
Unit tests for HistoryStore, SignalRecord, and SignalChange.

No network access; no yfinance; all I/O uses tmp_path.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from assethold.analysis.daily_strategy.history import (
    HistoryStore,
    SignalChange,
    SignalRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIGNAL_ORDER = {
    "STRONG BUILD": 0,
    "BUILD": 1,
    "HOLD": 2,
    "TRIM": 3,
    "STRONG TRIM": 4,
}


def _store(tmp_path: Path) -> HistoryStore:
    return HistoryStore(history_dir=tmp_path)


def _mock_signal(ticker: str, signal: str, score: float, tradeable: bool = True) -> MagicMock:
    """Build a minimal PositionSignal-like mock."""
    sig = MagicMock()
    sig.position.ticker = ticker
    sig.position.tradeable = tradeable
    sig.signal = signal
    sig.score = score
    sig.snapshot = MagicMock() if tradeable else None
    return sig


def _day(offset: int = 0) -> date:
    return date.today() + timedelta(days=offset)


# ---------------------------------------------------------------------------
# SignalRecord
# ---------------------------------------------------------------------------


class TestSignalRecord:
    def test_frozen(self):
        r = SignalRecord(date=date.today(), ticker="BRKB", signal="HOLD", score=0.0)
        with pytest.raises((AttributeError, TypeError)):
            r.ticker = "XOM"  # type: ignore[misc]

    def test_fields(self):
        today = date.today()
        r = SignalRecord(date=today, ticker="XOM", signal="TRIM", score=-0.3)
        assert r.date == today
        assert r.ticker == "XOM"
        assert r.signal == "TRIM"
        assert r.score == pytest.approx(-0.3)


# ---------------------------------------------------------------------------
# SignalChange
# ---------------------------------------------------------------------------


class TestSignalChange:
    def test_improved_when_score_rises(self):
        c = SignalChange("BRKB", "HOLD", "BUILD", prev_score=0.1, curr_score=0.3)
        assert c.improved is True

    def test_not_improved_when_score_falls(self):
        c = SignalChange("XOM", "HOLD", "TRIM", prev_score=0.0, curr_score=-0.3)
        assert c.improved is False

    def test_format_contains_ticker_and_signals(self):
        c = SignalChange("BRKB", "HOLD", "BUILD", prev_score=0.1, curr_score=0.3)
        text = c.format()
        assert "BRKB" in text
        assert "HOLD" in text
        assert "BUILD" in text

    def test_format_contains_scores(self):
        c = SignalChange("BRKB", "HOLD", "BUILD", prev_score=0.123, curr_score=0.456)
        text = c.format()
        assert "+0.123" in text
        assert "+0.456" in text

    def test_format_up_arrow_when_improved(self):
        c = SignalChange("BRKB", "HOLD", "BUILD", prev_score=0.1, curr_score=0.3)
        assert "↑" in c.format()

    def test_format_down_arrow_when_worsened(self):
        c = SignalChange("XOM", "HOLD", "TRIM", prev_score=0.0, curr_score=-0.3)
        assert "↓" in c.format()


# ---------------------------------------------------------------------------
# HistoryStore.record + _load
# ---------------------------------------------------------------------------


class TestRecord:
    def test_record_creates_csv(self, tmp_path):
        store = _store(tmp_path)
        signals = [_mock_signal("BRKB", "HOLD", 0.0)]
        store.record(signals, report_date=_day())
        assert (tmp_path / "signals.csv").exists()

    def test_record_writes_header(self, tmp_path):
        store = _store(tmp_path)
        store.record([_mock_signal("BRKB", "HOLD", 0.0)], report_date=_day())
        with (tmp_path / "signals.csv").open() as f:
            header = f.readline().strip()
        assert "date" in header and "ticker" in header and "signal" in header

    def test_record_appends_rows(self, tmp_path):
        store = _store(tmp_path)
        d = _day()
        store.record([_mock_signal("BRKB", "HOLD", 0.0)], report_date=d)
        store.record([_mock_signal("XOM", "TRIM", -0.3)], report_date=d + timedelta(days=1))
        with (tmp_path / "signals.csv").open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2

    def test_record_skips_nontradeable(self, tmp_path):
        store = _store(tmp_path)
        signals = [
            _mock_signal("BRKB", "HOLD", 0.0, tradeable=True),
            _mock_signal("QPIGQ", "HOLD", 0.0, tradeable=False),
        ]
        store.record(signals, report_date=_day())
        with (tmp_path / "signals.csv").open() as f:
            rows = list(csv.DictReader(f))
        tickers = {r["ticker"] for r in rows}
        assert "BRKB" in tickers
        assert "QPIGQ" not in tickers

    def test_record_deduplicates_same_ticker_multiple_accounts(self, tmp_path):
        store = _store(tmp_path)
        # Same ticker, two accounts → one row per ticker
        signals = [
            _mock_signal("BRKB", "BUILD", 0.3),
            _mock_signal("BRKB", "HOLD", 0.1),
        ]
        store.record(signals, report_date=_day())
        with (tmp_path / "signals.csv").open() as f:
            rows = list(csv.DictReader(f))
        brkb_rows = [r for r in rows if r["ticker"] == "BRKB"]
        assert len(brkb_rows) == 1

    def test_record_default_date_is_today(self, tmp_path):
        store = _store(tmp_path)
        store.record([_mock_signal("BRKB", "HOLD", 0.0)])
        with (tmp_path / "signals.csv").open() as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["date"] == date.today().isoformat()

    def test_record_creates_history_dir_if_missing(self, tmp_path):
        history_dir = tmp_path / "sub" / "dir"
        store = HistoryStore(history_dir=history_dir)
        store.record([_mock_signal("BRKB", "HOLD", 0.0)], report_date=_day())
        assert history_dir.is_dir()


# ---------------------------------------------------------------------------
# HistoryStore.previous
# ---------------------------------------------------------------------------


class TestPrevious:
    def test_empty_history_returns_empty_dict(self, tmp_path):
        assert _store(tmp_path).previous() == {}

    def test_returns_most_recent_day(self, tmp_path):
        store = _store(tmp_path)
        today = date.today()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        store.record([_mock_signal("BRKB", "HOLD", 0.0)], report_date=two_days_ago)
        store.record([_mock_signal("BRKB", "BUILD", 0.25)], report_date=yesterday)

        prev = store.previous(before=today)
        assert prev["BRKB"].signal == "BUILD"
        assert prev["BRKB"].date == yesterday

    def test_excludes_today(self, tmp_path):
        store = _store(tmp_path)
        today = date.today()
        store.record([_mock_signal("BRKB", "HOLD", 0.0)], report_date=today)
        prev = store.previous(before=today)
        assert prev == {}

    def test_multiple_tickers_all_returned(self, tmp_path):
        store = _store(tmp_path)
        yesterday = date.today() - timedelta(days=1)
        store.record(
            [_mock_signal("BRKB", "HOLD", 0.0), _mock_signal("XOM", "TRIM", -0.3)],
            report_date=yesterday,
        )
        prev = store.previous()
        assert "BRKB" in prev
        assert "XOM" in prev


# ---------------------------------------------------------------------------
# HistoryStore.changes
# ---------------------------------------------------------------------------


class TestChanges:
    def test_no_history_returns_empty(self, tmp_path):
        store = _store(tmp_path)
        signals = [_mock_signal("BRKB", "BUILD", 0.25)]
        assert store.changes(signals) == []

    def test_detects_changed_signal(self, tmp_path):
        store = _store(tmp_path)
        yesterday = date.today() - timedelta(days=1)
        store.record([_mock_signal("BRKB", "HOLD", 0.05)], report_date=yesterday)

        signals = [_mock_signal("BRKB", "BUILD", 0.28)]
        changes = store.changes(signals)
        assert len(changes) == 1
        assert changes[0].ticker == "BRKB"
        assert changes[0].prev_signal == "HOLD"
        assert changes[0].curr_signal == "BUILD"

    def test_unchanged_signal_not_reported(self, tmp_path):
        store = _store(tmp_path)
        yesterday = date.today() - timedelta(days=1)
        store.record([_mock_signal("BRKB", "HOLD", 0.05)], report_date=yesterday)

        signals = [_mock_signal("BRKB", "HOLD", 0.07)]
        assert store.changes(signals) == []

    def test_multiple_tickers_only_changed_returned(self, tmp_path):
        store = _store(tmp_path)
        yesterday = date.today() - timedelta(days=1)
        store.record(
            [_mock_signal("BRKB", "HOLD", 0.05), _mock_signal("XOM", "TRIM", -0.3)],
            report_date=yesterday,
        )
        signals = [_mock_signal("BRKB", "BUILD", 0.28), _mock_signal("XOM", "TRIM", -0.35)]
        changes = store.changes(signals)
        assert len(changes) == 1
        assert changes[0].ticker == "BRKB"

    def test_improvements_sorted_first(self, tmp_path):
        store = _store(tmp_path)
        yesterday = date.today() - timedelta(days=1)
        store.record(
            [_mock_signal("XOM", "HOLD", 0.05), _mock_signal("BRKB", "HOLD", 0.05)],
            report_date=yesterday,
        )
        # BRKB improves, XOM worsens
        signals = [_mock_signal("BRKB", "BUILD", 0.3), _mock_signal("XOM", "TRIM", -0.25)]
        changes = store.changes(signals)
        assert changes[0].ticker == "BRKB"  # improvement first
        assert changes[1].ticker == "XOM"

    def test_ticker_not_in_history_skipped(self, tmp_path):
        store = _store(tmp_path)
        yesterday = date.today() - timedelta(days=1)
        store.record([_mock_signal("BRKB", "HOLD", 0.05)], report_date=yesterday)

        # VOO is new — not in history → should not appear in changes
        signals = [_mock_signal("BRKB", "HOLD", 0.05), _mock_signal("VOO", "BUILD", 0.3)]
        changes = store.changes(signals)
        assert all(c.ticker != "VOO" for c in changes)


# ---------------------------------------------------------------------------
# Malformed CSV rows are skipped gracefully
# ---------------------------------------------------------------------------


class TestMalformedCsv:
    def test_bad_rows_skipped(self, tmp_path):
        csv_path = tmp_path / "signals.csv"
        csv_path.write_text(
            "date,ticker,signal,score\n"
            "not-a-date,BRKB,HOLD,0.0\n"
            "2025-01-01,XOM,TRIM,-0.3\n"
        )
        store = _store(tmp_path)
        records = store._load()
        # The bad-date row is skipped; XOM row loads fine
        assert len(records) == 1
        assert records[0].ticker == "XOM"
