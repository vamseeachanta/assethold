"""
Unit tests for DailyStrategyReport.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# Stub yfinance so fetcher module imports cleanly.
if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = MagicMock()

from assethold.analysis.daily_strategy.fetcher import MarketSnapshot
from assethold.analysis.daily_strategy.loader import Position
from assethold.analysis.daily_strategy.report import DailyStrategyReport
from assethold.analysis.daily_strategy.signals import PositionSignal
from assethold.risk_metrics import position_risk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pos(ticker: str, shares: float = 50.0, account: str = "Individual - TOD") -> Position:
    return Position(
        account=account,
        account_number="X78707567",
        ticker=ticker,
        shares=shares,
        tradeable=True,
        avg_cost_basis=300.0,
    )


def _snap(ticker: str, price: float = 310.0) -> MarketSnapshot:
    return MarketSnapshot(
        ticker=ticker,
        current_price=price,
        week52_high=360.0,
        week52_low=240.0,
        pct_from_52w_low=58.3,
        pct_from_52w_high=13.9,
        rsi_14=55.0,
        sma_50=305.0,
        sma_200=290.0,
        pe_ratio=21.0,
        price_to_book=1.6,
    )


def _sig(
    ticker: str = "BRKB",
    signal: str = "HOLD",
    score: float = 0.0,
    shares: float = 50.0,
    account: str = "Individual - TOD",
) -> PositionSignal:
    return PositionSignal(
        position=_pos(ticker, shares, account),
        snapshot=_snap(ticker),
        score=score,
        signal=signal,
        rationale=["RSI 55.0 — neutral momentum", "Price 58% of 52-week range"],
    )


def _reporter(tmp_path: Path) -> DailyStrategyReport:
    return DailyStrategyReport(output_dir=tmp_path)


# ---------------------------------------------------------------------------
# Markdown structure
# ---------------------------------------------------------------------------


class TestReportStructure:
    def test_render_returns_string(self, tmp_path):
        reporter = _reporter(tmp_path)
        md = reporter.render([_sig()], report_date=datetime(2026, 2, 17))
        assert isinstance(md, str)
        assert len(md) > 0

    def test_report_contains_date(self, tmp_path):
        reporter = _reporter(tmp_path)
        md = reporter.render([_sig()], report_date=datetime(2026, 2, 17))
        assert "2026-02-17" in md

    def test_report_contains_per_account_section(self, tmp_path):
        reporter = _reporter(tmp_path)
        md = reporter.render([_sig()], report_date=datetime(2026, 2, 17))
        assert "Per-Account View" in md
        assert "Individual - TOD" in md

    def test_report_contains_combined_section(self, tmp_path):
        reporter = _reporter(tmp_path)
        md = reporter.render([_sig()], report_date=datetime(2026, 2, 17))
        assert "Combined Portfolio" in md

    def test_report_contains_signal_details(self, tmp_path):
        reporter = _reporter(tmp_path)
        md = reporter.render([_sig("BRKB", "BUILD", 0.35)], report_date=datetime(2026, 2, 17))
        assert "Signal Details" in md
        assert "BRKB" in md

    def test_report_contains_methodology_footer(self, tmp_path):
        reporter = _reporter(tmp_path)
        md = reporter.render([_sig()], report_date=datetime(2026, 2, 17))
        assert "Methodology" in md

    def test_report_shows_ticker_and_signal(self, tmp_path):
        reporter = _reporter(tmp_path)
        md = reporter.render([_sig("XOM", "TRIM", -0.35)], report_date=datetime(2026, 2, 17))
        assert "XOM" in md
        assert "TRIM" in md


# ---------------------------------------------------------------------------
# Multiple accounts
# ---------------------------------------------------------------------------


class TestMultipleAccounts:
    def test_per_account_section_per_account(self, tmp_path):
        reporter = _reporter(tmp_path)
        signals = [
            _sig("BRKB", account="Individual - TOD"),
            _sig("VOO", account="Traditional IRA"),
        ]
        md = reporter.render(signals, report_date=datetime(2026, 2, 17))
        assert "Individual - TOD" in md
        assert "Traditional IRA" in md

    def test_combined_section_merges_same_ticker(self, tmp_path):
        reporter = _reporter(tmp_path)
        # Same ticker in two accounts
        signals = [
            _sig("BRKB", shares=50.0, account="Individual - TOD"),
            _sig("BRKB", shares=10.0, account="Traditional IRA"),
        ]
        md = reporter.render(signals, report_date=datetime(2026, 2, 17))
        # Combined table should show 60 shares total
        assert "60.000" in md


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


class TestFileIO:
    def test_write_creates_file(self, tmp_path):
        reporter = _reporter(tmp_path)
        path = reporter.write([_sig()], report_date=datetime(2026, 2, 17))
        assert path.exists()
        assert path.name == "2026-02-17.md"

    def test_write_creates_output_dir_if_missing(self, tmp_path):
        output = tmp_path / "nested" / "reports"
        reporter = DailyStrategyReport(output_dir=output)
        reporter.write([_sig()], report_date=datetime(2026, 2, 17))
        assert output.exists()

    def test_written_file_contains_date(self, tmp_path):
        reporter = _reporter(tmp_path)
        path = reporter.write([_sig()], report_date=datetime(2026, 2, 17))
        content = path.read_text()
        assert "2026-02-17" in content


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_signal_list(self, tmp_path):
        reporter = _reporter(tmp_path)
        md = reporter.render([], report_date=datetime(2026, 2, 17))
        assert "2026-02-17" in md
        assert "Combined Portfolio" in md

    def test_nontradeable_position_in_per_account(self, tmp_path):
        reporter = _reporter(tmp_path)
        nontradeable = PositionSignal(
            position=Position(
                account="CENCORA EMPLOYEE INV",
                account_number="82897",
                ticker="FID 500 INDEX",
                shares=100.0,
                tradeable=False,
                avg_cost_basis=None,
            ),
            snapshot=None,
            score=0.0,
            signal="HOLD",
            rationale=["Non-tradeable position — no market signal generated."],
        )
        md = reporter.render([nontradeable], report_date=datetime(2026, 2, 17))
        # Should not crash; non-tradeable excluded from combined portfolio value
        assert "CENCORA EMPLOYEE INV" in md


# ---------------------------------------------------------------------------
# Risk metrics wiring
# ---------------------------------------------------------------------------


def _make_risk_metrics() -> dict:
    """Build a synthetic risk_metrics dict for two tickers."""
    np.random.seed(42)
    brkb_ret = pd.Series(np.random.normal(0.001, 0.02, 252))
    xom_ret = pd.Series(np.random.normal(0.0008, 0.018, 252))
    return {
        "BRKB": position_risk(brkb_ret),
        "XOM": position_risk(xom_ret),
    }


class TestRiskMetricsWiring:
    def test_render_with_risk_metrics_does_not_crash(self, tmp_path):
        reporter = _reporter(tmp_path)
        risk_metrics = _make_risk_metrics()
        md = reporter.render(
            [_sig("BRKB"), _sig("XOM", "TRIM", -0.35)],
            report_date=datetime(2026, 2, 17),
            risk_metrics=risk_metrics,
        )
        assert isinstance(md, str)
        assert len(md) > 0

    def test_render_with_risk_metrics_contains_risk_section(self, tmp_path):
        reporter = _reporter(tmp_path)
        risk_metrics = _make_risk_metrics()
        md = reporter.render(
            [_sig("BRKB"), _sig("XOM", "TRIM", -0.35)],
            report_date=datetime(2026, 2, 17),
            risk_metrics=risk_metrics,
        )
        assert "Risk Metrics" in md

    def test_render_with_risk_metrics_contains_var_label(self, tmp_path):
        reporter = _reporter(tmp_path)
        risk_metrics = _make_risk_metrics()
        md = reporter.render(
            [_sig("BRKB")],
            report_date=datetime(2026, 2, 17),
            risk_metrics=risk_metrics,
        )
        assert "VaR" in md

    def test_render_with_risk_metrics_contains_sharpe_label(self, tmp_path):
        reporter = _reporter(tmp_path)
        risk_metrics = _make_risk_metrics()
        md = reporter.render(
            [_sig("BRKB")],
            report_date=datetime(2026, 2, 17),
            risk_metrics=risk_metrics,
        )
        assert "Sharpe" in md

    def test_render_without_risk_metrics_omits_risk_section(self, tmp_path):
        reporter = _reporter(tmp_path)
        md = reporter.render(
            [_sig("BRKB")],
            report_date=datetime(2026, 2, 17),
        )
        assert "Risk Metrics" not in md

    def test_render_risk_section_contains_ticker_names(self, tmp_path):
        reporter = _reporter(tmp_path)
        risk_metrics = _make_risk_metrics()
        md = reporter.render(
            [_sig("BRKB"), _sig("XOM", "TRIM", -0.35)],
            report_date=datetime(2026, 2, 17),
            risk_metrics=risk_metrics,
        )
        assert "BRKB" in md
        assert "XOM" in md

    def test_write_with_risk_metrics_creates_file(self, tmp_path):
        reporter = _reporter(tmp_path)
        risk_metrics = _make_risk_metrics()
        path = reporter.write(
            [_sig("BRKB")],
            report_date=datetime(2026, 2, 17),
            risk_metrics=risk_metrics,
        )
        assert path.exists()
        content = path.read_text()
        assert "Risk Metrics" in content
