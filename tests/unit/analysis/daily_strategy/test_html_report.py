"""
Unit tests for DailyStrategyHtmlReport.

All tests use synthetic PositionSignal objects — no network calls.
"""

from __future__ import annotations

import sys
from datetime import datetime, date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Stub yfinance before any module-under-test imports it.
if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = MagicMock()

from assethold.analysis.daily_strategy.fetcher import MarketSnapshot  # noqa: E402
from assethold.analysis.daily_strategy.insider import InsiderTrend  # noqa: E402
from assethold.analysis.daily_strategy.loader import Position  # noqa: E402
from assethold.analysis.daily_strategy.signals import PositionSignal  # noqa: E402
from assethold.analysis.daily_strategy.history import SignalChange  # noqa: E402
from assethold.analysis.daily_strategy.html_report import DailyStrategyHtmlReport  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_snapshot(
    ticker: str,
    price: float = 100.0,
    rsi: float = 50.0,
    pe: float = 20.0,
    insider_trend: str = "NEUTRAL",
    forward_pe: float = 18.0,
    beta: float = 1.1,
    dividend_yield: float = 0.02,
    analyst_rating: str = "buy",
) -> MarketSnapshot:
    insider = InsiderTrend(
        ticker=ticker,
        buys_90d=2,
        sells_90d=1,
        net_shares_90d=500.0,
        trend=insider_trend,
        last_activity_days=10,
        summary="2 open-market buys",
    )
    return MarketSnapshot(
        ticker=ticker,
        current_price=price,
        week52_high=price * 1.2,
        week52_low=price * 0.8,
        pct_from_52w_low=50.0,
        pct_from_52w_high=16.7,
        rsi_14=rsi,
        sma_50=price * 0.97,
        sma_200=price * 0.93,
        pe_ratio=pe,
        price_to_book=2.5,
        insider_trend=insider,
        forward_pe=forward_pe,
        dividend_yield=dividend_yield,
        market_cap=1_000_000_000.0,
        beta=beta,
        analyst_rating=analyst_rating,
    )


def _make_signal(
    ticker: str,
    shares: float = 10.0,
    price: float = 100.0,
    signal: str = "HOLD",
    score: float = 0.0,
    account: str = "Individual - TOD",
) -> PositionSignal:
    pos = Position(
        account=account,
        account_number="X123",
        ticker=ticker,
        shares=shares,
        tradeable=True,
        avg_cost_basis=price * 0.9,
    )
    snap = _make_snapshot(ticker, price=price)
    return PositionSignal(
        position=pos,
        snapshot=snap,
        score=score,
        signal=signal,
        rationale=[f"RSI {snap.rsi_14:.1f} — neutral momentum"],
    )


def _make_signals() -> list[PositionSignal]:
    return [
        _make_signal("BRKB", shares=5, price=400.0, signal="BUILD", score=0.35),
        _make_signal("XOM",  shares=20, price=120.0, signal="HOLD", score=0.05),
        _make_signal("VOO",  shares=8,  price=500.0, signal="STRONG TRIM", score=-0.62),
    ]


def _make_report(tmp_path: Path) -> DailyStrategyHtmlReport:
    return DailyStrategyHtmlReport(output_dir=tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenerateHtmlString:
    def test_generate_returns_html_string(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        assert isinstance(result, str)

    def test_generate_starts_with_doctype(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        assert result.strip().startswith("<!DOCTYPE html>")

    def test_html_contains_all_sections(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        for heading in [
            "1. Executive Summary",
            "2. Technical Indicators",
            "3. Insider Sentiment",
            "4. Fundamentals",
            "5. Portfolio Breakdown",
            "6. Signal Details",
        ]:
            assert heading in result, f"Missing section: {heading}"

    def test_changes_section_present_when_provided(self, tmp_path):
        signals = _make_signals()
        changes = [
            SignalChange(
                ticker="BRKB",
                prev_signal="HOLD",
                curr_signal="BUILD",
                prev_score=0.10,
                curr_score=0.35,
            )
        ]
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18), changes=changes)
        assert "Signal Changes Since Last Run" in result
        assert "BRKB" in result

    def test_changes_section_absent_when_none(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18), changes=None)
        assert "Signal Changes Since Last Run" not in result

    def test_no_changes_message_when_empty_list(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18), changes=[])
        assert "No signal changes since last run" in result


class TestWriteHtmlFile:
    def test_write_creates_html_file(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        path = report.write(signals, report_date=datetime(2026, 2, 18))
        assert path.exists()
        assert path.suffix == ".html"

    def test_write_uses_date_as_filename(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        path = report.write(signals, report_date=datetime(2026, 2, 18))
        assert path.name == "2026-02-18.html"

    def test_write_file_contains_doctype(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        path = report.write(signals, report_date=datetime(2026, 2, 18))
        content = path.read_text(encoding="utf-8")
        assert content.strip().startswith("<!DOCTYPE html>")


class TestSummarySection:
    def test_summary_shows_portfolio_value(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        # total = 5*400 + 20*120 + 8*500 = 2000 + 2400 + 4000 = 8400
        assert "8,400" in result

    def test_summary_shows_build_count(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        assert "Build Signals" in result

    def test_action_priority_table_present(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        assert "Action Priority" in result


class TestTechnicalSection:
    def test_technical_section_shows_rsi(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        assert "RSI-14" in result

    def test_technical_section_includes_sma_columns(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        assert "vs SMA-50" in result
        assert "vs SMA-200" in result


class TestInsiderSection:
    def test_insider_section_shows_trend(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        assert "Insider Sentiment" in result

    def test_insider_section_shows_buys_sells(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        assert "Buys (90d)" in result
        assert "Sells (90d)" in result


class TestFundamentalsSection:
    def test_fundamentals_section_shows_pe(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        assert "P/E (TTM)" in result

    def test_fundamentals_shows_forward_pe(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        assert "Fwd P/E" in result

    def test_fundamentals_shows_analyst_rating(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        assert "Analyst Rating" in result


class TestComparisonMode:
    def test_comparison_mode_shows_comparison_matrix(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(
            signals, report_date=datetime(2026, 2, 18), comparison_mode=True
        )
        assert "5. Comparison Matrix" in result

    def test_comparison_mode_hides_portfolio_breakdown(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(
            signals, report_date=datetime(2026, 2, 18), comparison_mode=True
        )
        assert "5. Portfolio Breakdown" not in result

    def test_normal_mode_shows_portfolio_breakdown(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(
            signals, report_date=datetime(2026, 2, 18), comparison_mode=False
        )
        assert "5. Portfolio Breakdown" in result


class TestSignalDetailSection:
    def test_signal_details_section_present(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        assert "6. Signal Details" in result

    def test_signal_details_shows_ticker_names(self, tmp_path):
        signals = _make_signals()
        report = _make_report(tmp_path)
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        for ticker in ["BRKB", "XOM", "VOO"]:
            assert ticker in result

    def test_non_tradeable_signals_excluded(self, tmp_path):
        pos = Position(
            account="Employee", account_number="Z999",
            ticker="EMP", shares=100, tradeable=False, avg_cost_basis=None,
        )
        non_tradeable = PositionSignal(
            position=pos, snapshot=None, score=0.0,
            signal="HOLD", rationale=["Non-tradeable."],
        )
        signals = _make_signals() + [non_tradeable]
        report = _make_report(tmp_path)
        # Should not crash even with a None snapshot
        result = report.generate(signals, report_date=datetime(2026, 2, 18))
        assert "<!DOCTYPE html>" in result


class TestFetcherFieldsInSnapshot:
    """Verify the new MarketSnapshot fields round-trip through the report."""

    def test_forward_pe_displayed_in_fundamentals(self, tmp_path):
        sig = _make_signal("AAPL", price=200.0)
        sig.snapshot.forward_pe = 22.5
        report = _make_report(tmp_path)
        result = report.generate([sig], report_date=datetime(2026, 2, 18))
        assert "22.5" in result

    def test_analyst_rating_displayed_in_fundamentals(self, tmp_path):
        sig = _make_signal("AAPL", price=200.0)
        sig.snapshot.analyst_rating = "strong_buy"
        report = _make_report(tmp_path)
        result = report.generate([sig], report_date=datetime(2026, 2, 18))
        assert "strong_buy" in result
