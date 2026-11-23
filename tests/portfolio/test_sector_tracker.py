"""
Unit tests for SectorTracker.

All yfinance calls are mocked — no network access required.
Sample portfolio uses tickers with known GICS sectors:
  AAPL  → Information Technology
  JPM   → Financials
  XOM   → Energy
  JNJ   → Health Care
  AMZN  → Consumer Discretionary
"""

from __future__ import annotations

import sys
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub yfinance at module level so the import chain never hits the network.
# ---------------------------------------------------------------------------
if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = MagicMock()

from assethold.portfolio.sector_tracker import (  # noqa: E402
    CONCENTRATION_THRESHOLD,
    GICS_SECTORS,
    ConcentrationWarning,
    RebalancingSuggestion,
    SectorBreakdown,
    SectorTracker,
    classify_holding,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SAMPLE_HOLDINGS: dict[str, float] = {
    "AAPL": 50_000.0,   # Information Technology — 50%
    "JPM": 20_000.0,    # Financials              — 20%
    "XOM": 15_000.0,    # Energy                  — 15%
    "JNJ": 10_000.0,    # Health Care             — 10%
    "AMZN": 5_000.0,    # Consumer Discretionary  —  5%
}

SAMPLE_SECTORS: dict[str, str] = {
    "AAPL": "Information Technology",
    "JPM": "Financials",
    "XOM": "Energy",
    "JNJ": "Health Care",
    "AMZN": "Consumer Discretionary",
}


def _make_yf_ticker(sector: Optional[str]) -> MagicMock:
    """Return a mock yfinance Ticker whose .info contains 'sector'."""
    mock = MagicMock()
    mock.info = {"sector": sector} if sector else {}
    return mock


def _tracker_with_mock_sectors(sectors: dict[str, str]) -> SectorTracker:
    """
    Build a SectorTracker that returns *sectors* for each ticker
    without hitting the network.
    """
    def _fake_yf_ticker(symbol: str) -> MagicMock:
        return _make_yf_ticker(sectors.get(symbol))

    tracker = SectorTracker()
    tracker._fetch_sector = lambda symbol: sectors.get(symbol, "Unknown")  # type: ignore[method-assign]
    return tracker


# ---------------------------------------------------------------------------
# GICS sector constant
# ---------------------------------------------------------------------------


class TestGicsSectors:
    def test_eleven_sectors_defined(self):
        assert len(GICS_SECTORS) == 11

    def test_known_sectors_present(self):
        assert "Information Technology" in GICS_SECTORS
        assert "Energy" in GICS_SECTORS
        assert "Financials" in GICS_SECTORS
        assert "Health Care" in GICS_SECTORS
        assert "Consumer Discretionary" in GICS_SECTORS

    def test_concentration_threshold_is_thirty_percent(self):
        assert CONCENTRATION_THRESHOLD == 0.30


# ---------------------------------------------------------------------------
# classify_holding — unit test of the thin yfinance wrapper
# ---------------------------------------------------------------------------


class TestClassifyHolding:
    def test_returns_sector_from_yfinance_info(self):
        mock_ticker = _make_yf_ticker("Information Technology")
        with patch("assethold.portfolio.sector_tracker.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            sector = classify_holding("AAPL")
        assert sector == "Information Technology"

    def test_returns_unknown_when_sector_missing(self):
        mock_ticker = _make_yf_ticker(None)
        with patch("assethold.portfolio.sector_tracker.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            sector = classify_holding("FAKE")
        assert sector == "Unknown"

    def test_handles_empty_info_dict(self):
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        with patch("assethold.portfolio.sector_tracker.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            sector = classify_holding("XYZ")
        assert sector == "Unknown"

    def test_handles_yfinance_exception(self):
        with patch("assethold.portfolio.sector_tracker.yf") as mock_yf:
            mock_yf.Ticker.side_effect = Exception("network error")
            sector = classify_holding("AAPL")
        assert sector == "Unknown"


# ---------------------------------------------------------------------------
# SectorTracker.build_breakdown — sector weight calculation
# ---------------------------------------------------------------------------


class TestSectorWeightCalculation:
    def test_weights_sum_to_one(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        total = sum(breakdown.weights.values())
        assert total == pytest.approx(1.0, abs=1e-9)

    def test_correct_weight_for_dominant_sector(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        # AAPL = $50k / $100k total = 50%
        assert breakdown.weights["Information Technology"] == pytest.approx(0.50, abs=1e-6)

    def test_correct_weight_for_minor_sector(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        assert breakdown.weights["Consumer Discretionary"] == pytest.approx(0.05, abs=1e-6)

    def test_total_value_stored(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        assert breakdown.total_value == pytest.approx(100_000.0, abs=1e-6)

    def test_sector_values_correct(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        assert breakdown.sector_values["Energy"] == pytest.approx(15_000.0, abs=1e-6)

    def test_unknown_sector_grouped_together(self):
        holdings = {"FAKE1": 10_000.0, "FAKE2": 10_000.0}
        sectors = {"FAKE1": "Unknown", "FAKE2": "Unknown"}
        tracker = _tracker_with_mock_sectors(sectors)
        breakdown = tracker.build_breakdown(holdings)
        assert "Unknown" in breakdown.weights
        assert breakdown.weights["Unknown"] == pytest.approx(1.0, abs=1e-9)

    def test_empty_holdings_returns_empty_breakdown(self):
        tracker = _tracker_with_mock_sectors({})
        breakdown = tracker.build_breakdown({})
        assert breakdown.weights == {}
        assert breakdown.total_value == 0.0

    def test_single_holding_has_weight_one(self):
        tracker = _tracker_with_mock_sectors({"AAPL": "Information Technology"})
        breakdown = tracker.build_breakdown({"AAPL": 75_000.0})
        assert breakdown.weights["Information Technology"] == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Concentration warnings
# ---------------------------------------------------------------------------


class TestConcentrationWarnings:
    def test_overweight_sector_triggers_warning(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        # Information Technology = 50% → above 30% threshold
        assert len(breakdown.warnings) > 0
        it_warnings = [w for w in breakdown.warnings if "Information Technology" in w.sector]
        assert len(it_warnings) == 1

    def test_warning_contains_weight_and_sector(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        it_warning = next(w for w in breakdown.warnings if "Information Technology" in w.sector)
        assert it_warning.weight == pytest.approx(0.50, abs=1e-6)
        assert it_warning.threshold == CONCENTRATION_THRESHOLD

    def test_no_warning_when_all_sectors_below_threshold(self):
        # Equally distribute $100k across 5 sectors → 20% each
        balanced: dict[str, float] = {
            "AAPL": 20_000.0,
            "JPM": 20_000.0,
            "XOM": 20_000.0,
            "JNJ": 20_000.0,
            "AMZN": 20_000.0,
        }
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(balanced)
        assert len(breakdown.warnings) == 0

    def test_exactly_at_threshold_does_not_warn(self):
        # 30% exactly should NOT trigger (> not >=)
        holdings = {
            "AAPL": 30_000.0,   # Tech 30%
            "JPM": 70_000.0,    # Financials 70% → warns
        }
        sectors = {"AAPL": "Information Technology", "JPM": "Financials"}
        tracker = _tracker_with_mock_sectors(sectors)
        breakdown = tracker.build_breakdown(holdings)
        it_warnings = [w for w in breakdown.warnings if "Information Technology" in w.sector]
        assert len(it_warnings) == 0

    def test_multiple_overweight_sectors_each_get_warning(self):
        holdings = {
            "AAPL": 40_000.0,   # Tech 40%
            "JPM": 35_000.0,    # Financials 35%
            "XOM": 25_000.0,    # Energy 25%
        }
        sectors = {
            "AAPL": "Information Technology",
            "JPM": "Financials",
            "XOM": "Energy",
        }
        tracker = _tracker_with_mock_sectors(sectors)
        breakdown = tracker.build_breakdown(holdings)
        assert len(breakdown.warnings) == 2


# ---------------------------------------------------------------------------
# Rebalancing suggestions
# ---------------------------------------------------------------------------


class TestRebalancingSuggestions:
    def _equal_target(self) -> dict[str, float]:
        """Return equal-weight target (20% per sector) for 5 sectors."""
        sectors = [
            "Information Technology", "Financials", "Energy",
            "Health Care", "Consumer Discretionary",
        ]
        return {s: 0.20 for s in sectors}

    def test_overweight_sector_gets_trim_suggestion(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        target = self._equal_target()
        suggestions = tracker.rebalancing_suggestions(breakdown, target)
        it_sug = [s for s in suggestions if s.sector == "Information Technology"]
        assert len(it_sug) == 1
        assert it_sug[0].action == "TRIM"

    def test_underweight_sector_gets_add_suggestion(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        target = self._equal_target()
        suggestions = tracker.rebalancing_suggestions(breakdown, target)
        cd_sug = [s for s in suggestions if s.sector == "Consumer Discretionary"]
        assert len(cd_sug) == 1
        assert cd_sug[0].action == "ADD"

    def test_near_target_sector_gets_hold_suggestion(self):
        # JPM = 20%, target = 20% → should be HOLD (or no suggestion)
        holdings = {"JPM": 100_000.0}
        sectors = {"JPM": "Financials"}
        tracker = _tracker_with_mock_sectors(sectors)
        breakdown = tracker.build_breakdown(holdings)
        target = {"Financials": 1.0}
        suggestions = tracker.rebalancing_suggestions(breakdown, target)
        fin_sug = [s for s in suggestions if s.sector == "Financials"]
        # At exactly target → HOLD or no suggestion
        if fin_sug:
            assert fin_sug[0].action == "HOLD"

    def test_suggestion_delta_correct_for_overweight(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        target = self._equal_target()
        suggestions = tracker.rebalancing_suggestions(breakdown, target)
        it_sug = next(s for s in suggestions if s.sector == "Information Technology")
        # delta = actual - target: 50% - 20% = +30% (positive = overweight)
        assert it_sug.delta == pytest.approx(0.30, abs=1e-6)

    def test_empty_target_returns_no_suggestions(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        suggestions = tracker.rebalancing_suggestions(breakdown, {})
        assert suggestions == []

    def test_suggestions_sorted_by_abs_delta_descending(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        target = self._equal_target()
        suggestions = tracker.rebalancing_suggestions(breakdown, target)
        deltas = [abs(s.delta) for s in suggestions]
        assert deltas == sorted(deltas, reverse=True)


# ---------------------------------------------------------------------------
# format_table — console text rendering
# ---------------------------------------------------------------------------


class TestFormatTable:
    def test_format_table_returns_string(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        table = tracker.format_table(breakdown)
        assert isinstance(table, str)
        assert len(table) > 0

    def test_format_table_contains_sector_name(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        table = tracker.format_table(breakdown)
        assert "Information Technology" in table

    def test_format_table_contains_weight_percentage(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        table = tracker.format_table(breakdown)
        # AAPL is 50% → should see "50" somewhere in table
        assert "50" in table or "50.0" in table

    def test_format_table_contains_warning_marker(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        table = tracker.format_table(breakdown)
        # IT is 50% — should be flagged
        assert "OVERWEIGHT" in table or "!" in table or "WARNING" in table

    def test_format_table_contains_total_line(self):
        tracker = _tracker_with_mock_sectors(SAMPLE_SECTORS)
        breakdown = tracker.build_breakdown(SAMPLE_HOLDINGS)
        table = tracker.format_table(breakdown)
        assert "Total" in table or "total" in table


# ---------------------------------------------------------------------------
# SectorBreakdown and ConcentrationWarning dataclasses
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_sector_breakdown_fields(self):
        breakdown = SectorBreakdown(
            sector_values={"Energy": 10_000.0},
            weights={"Energy": 1.0},
            total_value=10_000.0,
            warnings=[],
        )
        assert breakdown.total_value == 10_000.0
        assert breakdown.weights["Energy"] == 1.0

    def test_concentration_warning_fields(self):
        warning = ConcentrationWarning(
            sector="Energy",
            weight=0.45,
            threshold=0.30,
        )
        assert warning.sector == "Energy"
        assert warning.weight == 0.45
        assert warning.threshold == 0.30

    def test_rebalancing_suggestion_fields(self):
        sug = RebalancingSuggestion(
            sector="Energy",
            actual=0.45,
            target=0.10,
            delta=-0.35,
            action="TRIM",
        )
        assert sug.action == "TRIM"
        assert sug.delta == pytest.approx(-0.35)


# ---------------------------------------------------------------------------
# Integration: build_breakdown uses classify_holding (mocked yfinance)
# ---------------------------------------------------------------------------


class TestIntegrationWithMockedYfinance:
    def test_build_breakdown_calls_yfinance_for_each_ticker(self):
        call_log: list[str] = []

        def _fake_classify(symbol: str) -> str:
            call_log.append(symbol)
            return SAMPLE_SECTORS.get(symbol, "Unknown")

        tracker = SectorTracker()
        tracker._fetch_sector = _fake_classify  # type: ignore[method-assign]
        tracker.build_breakdown(SAMPLE_HOLDINGS)

        assert set(call_log) == set(SAMPLE_HOLDINGS.keys())

    def test_sector_cache_avoids_double_fetch(self):
        fetch_count: dict[str, int] = {}

        def _counting_classify(symbol: str) -> str:
            fetch_count[symbol] = fetch_count.get(symbol, 0) + 1
            return SAMPLE_SECTORS.get(symbol, "Unknown")

        tracker = SectorTracker()
        tracker._fetch_sector = _counting_classify  # type: ignore[method-assign]

        # Build twice with same holdings — each symbol fetched once per tracker instance
        tracker.build_breakdown(SAMPLE_HOLDINGS)
        tracker.build_breakdown(SAMPLE_HOLDINGS)

        # Cache should have been used on second call — each ticker fetched only once
        for count in fetch_count.values():
            assert count == 1
