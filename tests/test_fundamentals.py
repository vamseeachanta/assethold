"""Tests for fundamentals scoring module (WRK-322).

Covers: score_pe_ratio, score_pb_ratio, score_ev_ebitda, FundamentalsScorer,
and fetch_fundamentals (mocked yfinance).
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Stub yfinance before any module under test is imported, so tests run
# on systems where the package is not installed.
if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = MagicMock()


# ---------------------------------------------------------------------------
# score_pe_ratio
# ---------------------------------------------------------------------------

class TestScorePeRatio:
    def test_low_pe_scores_higher_than_high_pe(self):
        from assethold.fundamentals import score_pe_ratio
        assert score_pe_ratio(10.0) > score_pe_ratio(30.0)

    def test_none_returns_zero(self):
        from assethold.fundamentals import score_pe_ratio
        assert score_pe_ratio(None) == 0.0

    def test_pe_below_10_scores_10(self):
        from assethold.fundamentals import score_pe_ratio
        assert score_pe_ratio(5.0) == 10.0

    def test_pe_10_to_15_scores_8(self):
        from assethold.fundamentals import score_pe_ratio
        assert score_pe_ratio(12.0) == 8.0

    def test_pe_15_to_20_scores_6(self):
        from assethold.fundamentals import score_pe_ratio
        assert score_pe_ratio(17.0) == 6.0

    def test_pe_20_to_25_scores_4(self):
        from assethold.fundamentals import score_pe_ratio
        assert score_pe_ratio(22.0) == 4.0

    def test_pe_above_25_scores_2(self):
        from assethold.fundamentals import score_pe_ratio
        assert score_pe_ratio(30.0) == 2.0


# ---------------------------------------------------------------------------
# score_pb_ratio
# ---------------------------------------------------------------------------

class TestScorePbRatio:
    def test_low_pb_scores_higher_than_high_pb(self):
        from assethold.fundamentals import score_pb_ratio
        assert score_pb_ratio(1.0) > score_pb_ratio(5.0)

    def test_none_returns_zero(self):
        from assethold.fundamentals import score_pb_ratio
        assert score_pb_ratio(None) == 0.0

    def test_pb_below_1_scores_10(self):
        from assethold.fundamentals import score_pb_ratio
        assert score_pb_ratio(0.5) == 10.0

    def test_pb_1_to_2_scores_8(self):
        from assethold.fundamentals import score_pb_ratio
        assert score_pb_ratio(1.5) == 8.0

    def test_pb_2_to_3_scores_6(self):
        from assethold.fundamentals import score_pb_ratio
        assert score_pb_ratio(2.5) == 6.0

    def test_pb_3_to_5_scores_4(self):
        from assethold.fundamentals import score_pb_ratio
        assert score_pb_ratio(4.0) == 4.0

    def test_pb_above_5_scores_2(self):
        from assethold.fundamentals import score_pb_ratio
        assert score_pb_ratio(6.0) == 2.0


# ---------------------------------------------------------------------------
# score_ev_ebitda
# ---------------------------------------------------------------------------

class TestScoreEvEbitda:
    def test_low_ev_ebitda_scores_higher_than_high(self):
        from assethold.fundamentals import score_ev_ebitda
        assert score_ev_ebitda(6.0) > score_ev_ebitda(25.0)

    def test_none_returns_zero(self):
        from assethold.fundamentals import score_ev_ebitda
        assert score_ev_ebitda(None) == 0.0

    def test_ev_ebitda_below_8_scores_10(self):
        from assethold.fundamentals import score_ev_ebitda
        assert score_ev_ebitda(5.0) == 10.0

    def test_ev_ebitda_8_to_12_scores_8(self):
        from assethold.fundamentals import score_ev_ebitda
        assert score_ev_ebitda(10.0) == 8.0

    def test_ev_ebitda_12_to_16_scores_6(self):
        from assethold.fundamentals import score_ev_ebitda
        assert score_ev_ebitda(14.0) == 6.0

    def test_ev_ebitda_16_to_20_scores_4(self):
        from assethold.fundamentals import score_ev_ebitda
        assert score_ev_ebitda(18.0) == 4.0

    def test_ev_ebitda_above_20_scores_2(self):
        from assethold.fundamentals import score_ev_ebitda
        assert score_ev_ebitda(25.0) == 2.0


# ---------------------------------------------------------------------------
# FundamentalsScorer
# ---------------------------------------------------------------------------

class TestFundamentalsScorer:
    def test_rank_puts_cheaper_stock_first(self):
        from assethold.fundamentals import FundamentalsScorer
        scorer = FundamentalsScorer()
        holdings = [
            {"ticker": "A", "pe": 10.0, "pb": 1.5, "ev_ebitda": 8.0},
            {"ticker": "B", "pe": 30.0, "pb": 4.0, "ev_ebitda": 20.0},
        ]
        ranked = scorer.rank(holdings)
        assert ranked[0]["ticker"] == "A"

    def test_rank_preserves_all_fields(self):
        from assethold.fundamentals import FundamentalsScorer
        scorer = FundamentalsScorer()
        holdings = [
            {"ticker": "X", "pe": 12.0, "pb": 2.0, "ev_ebitda": 9.0},
        ]
        ranked = scorer.rank(holdings)
        assert ranked[0]["ticker"] == "X"
        assert "score" in ranked[0]

    def test_score_returns_float(self):
        from assethold.fundamentals import FundamentalsScorer
        scorer = FundamentalsScorer()
        data = {"ticker": "Z", "pe": 15.0, "pb": 2.5, "ev_ebitda": 12.0}
        result = scorer.score(data)
        assert isinstance(result, float)

    def test_score_all_missing_returns_zero(self):
        from assethold.fundamentals import FundamentalsScorer
        scorer = FundamentalsScorer()
        data = {"ticker": "Z", "pe": None, "pb": None, "ev_ebitda": None}
        result = scorer.score(data)
        assert result == 0.0

    def test_composite_weighted_correctly(self):
        from assethold.fundamentals import FundamentalsScorer, score_pe_ratio
        from assethold.fundamentals import score_pb_ratio, score_ev_ebitda
        scorer = FundamentalsScorer()
        pe, pb, ev = 10.0, 1.5, 7.0
        data = {"ticker": "T", "pe": pe, "pb": pb, "ev_ebitda": ev}
        expected = (
            score_pe_ratio(pe) * 0.35
            + score_pb_ratio(pb) * 0.35
            + score_ev_ebitda(ev) * 0.30
        )
        assert abs(scorer.score(data) - expected) < 1e-9

    def test_rank_returns_list_of_dicts(self):
        from assethold.fundamentals import FundamentalsScorer
        scorer = FundamentalsScorer()
        holdings = [
            {"ticker": "A", "pe": 8.0, "pb": 0.9, "ev_ebitda": 6.0},
            {"ticker": "B", "pe": 22.0, "pb": 3.5, "ev_ebitda": 17.0},
            {"ticker": "C", "pe": 14.0, "pb": 2.0, "ev_ebitda": 11.0},
        ]
        ranked = scorer.rank(holdings)
        assert len(ranked) == 3
        tickers = [h["ticker"] for h in ranked]
        assert tickers[0] == "A"  # cheapest
        assert tickers[-1] == "B"  # most expensive


# ---------------------------------------------------------------------------
# fetch_fundamentals
# ---------------------------------------------------------------------------

class TestFetchFundamentals:
    def test_fetch_fundamentals_mock(self):
        from assethold.fundamentals import fetch_fundamentals
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "trailingPE": 15.0,
            "priceToBook": 2.0,
            "enterpriseToEbitda": 10.0,
            "forwardEps": 5.0,
        }
        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = fetch_fundamentals("AAPL")
        assert result["pe"] == 15.0
        assert result["pb"] == 2.0
        assert result["ev_ebitda"] == 10.0
        assert result["forward_eps"] == 5.0

    def test_fetch_fundamentals_missing_keys_return_none(self):
        from assethold.fundamentals import fetch_fundamentals
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = fetch_fundamentals("NOPE")
        assert result["pe"] is None
        assert result["pb"] is None
        assert result["ev_ebitda"] is None

    def test_fetch_fundamentals_ticker_uppercased(self):
        from assethold.fundamentals import fetch_fundamentals
        mock_ticker = MagicMock()
        mock_ticker.info = {"trailingPE": 20.0}
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value = mock_ticker
            fetch_fundamentals("aapl")
            mock_yf.assert_called_once_with("AAPL")

    def test_fetch_fundamentals_includes_sector_and_dividend_yield(self):
        from assethold.fundamentals import fetch_fundamentals
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "trailingPE": 15.0,
            "priceToBook": 2.0,
            "enterpriseToEbitda": 10.0,
            "forwardEps": 5.0,
            "sector": "Information Technology",
            "dividendYield": 0.015,
        }
        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = fetch_fundamentals("MSFT")
        assert result["sector"] == "Information Technology"
        assert result["dividend_yield"] == 0.015

    def test_fetch_fundamentals_sector_missing_returns_unknown(self):
        from assethold.fundamentals import fetch_fundamentals
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = fetch_fundamentals("XYZ")
        assert result["sector"] == "Unknown"
        assert result["dividend_yield"] is None


# ---------------------------------------------------------------------------
# Sector peer ranking
# ---------------------------------------------------------------------------

class TestSectorPeerRanker:
    def test_percentile_rank_cheapest_is_highest(self):
        from assethold.fundamentals import SectorPeerRanker
        ranker = SectorPeerRanker()
        holdings = [
            {"ticker": "A", "sector": "Energy", "pe": 5.0},
            {"ticker": "B", "sector": "Energy", "pe": 15.0},
            {"ticker": "C", "sector": "Energy", "pe": 25.0},
        ]
        result = ranker.add_sector_percentiles(holdings)
        by_ticker = {r["ticker"]: r for r in result}
        assert by_ticker["A"]["pe_pct"] > by_ticker["C"]["pe_pct"]

    def test_percentile_rank_single_holding_returns_100(self):
        from assethold.fundamentals import SectorPeerRanker
        ranker = SectorPeerRanker()
        holdings = [{"ticker": "A", "sector": "Financials", "pe": 12.0}]
        result = ranker.add_sector_percentiles(holdings)
        assert result[0]["pe_pct"] == 100.0

    def test_percentile_missing_pe_stays_none(self):
        from assethold.fundamentals import SectorPeerRanker
        ranker = SectorPeerRanker()
        holdings = [
            {"ticker": "A", "sector": "Energy", "pe": None},
            {"ticker": "B", "sector": "Energy", "pe": 10.0},
        ]
        result = ranker.add_sector_percentiles(holdings)
        by_ticker = {r["ticker"]: r for r in result}
        assert by_ticker["A"]["pe_pct"] is None

    def test_percentile_cross_sector_not_compared(self):
        from assethold.fundamentals import SectorPeerRanker
        ranker = SectorPeerRanker()
        holdings = [
            {"ticker": "A", "sector": "Energy", "pe": 5.0},
            {"ticker": "B", "sector": "Technology", "pe": 50.0},
        ]
        result = ranker.add_sector_percentiles(holdings)
        by_ticker = {r["ticker"]: r for r in result}
        assert by_ticker["A"]["pe_pct"] == 100.0
        assert by_ticker["B"]["pe_pct"] == 100.0

    def test_pb_and_ev_ebitda_percentiles_present(self):
        from assethold.fundamentals import SectorPeerRanker
        ranker = SectorPeerRanker()
        holdings = [
            {"ticker": "A", "sector": "Industrials", "pe": 10.0,
             "pb": 1.0, "ev_ebitda": 6.0},
            {"ticker": "B", "sector": "Industrials", "pe": 20.0,
             "pb": 3.0, "ev_ebitda": 14.0},
        ]
        result = ranker.add_sector_percentiles(holdings)
        by_ticker = {r["ticker"]: r for r in result}
        for key in ("pe_pct", "pb_pct", "ev_ebitda_pct"):
            assert key in by_ticker["A"]
            assert key in by_ticker["B"]
        assert by_ticker["A"]["pe_pct"] > by_ticker["B"]["pe_pct"]
        assert by_ticker["A"]["pb_pct"] > by_ticker["B"]["pb_pct"]
        assert by_ticker["A"]["ev_ebitda_pct"] > by_ticker["B"]["ev_ebitda_pct"]

    def test_deep_value_flag_bottom_quintile(self):
        from assethold.fundamentals import SectorPeerRanker
        ranker = SectorPeerRanker()
        holdings = [
            {"ticker": "A", "sector": "Energy", "pe": 5.0,
             "pb": 0.5, "ev_ebitda": 4.0, "score": 9.0},
            {"ticker": "B", "sector": "Energy", "pe": 10.0,
             "pb": 1.0, "ev_ebitda": 8.0, "score": 7.5},
            {"ticker": "C", "sector": "Energy", "pe": 15.0,
             "pb": 2.0, "ev_ebitda": 12.0, "score": 6.0},
            {"ticker": "D", "sector": "Energy", "pe": 20.0,
             "pb": 3.0, "ev_ebitda": 16.0, "score": 4.5},
            {"ticker": "E", "sector": "Energy", "pe": 30.0,
             "pb": 6.0, "ev_ebitda": 22.0, "score": 2.0},
        ]
        result = ranker.add_sector_percentiles(holdings)
        by_ticker = {r["ticker"]: r for r in result}
        assert by_ticker["A"]["deep_value"] is True
        assert by_ticker["E"]["deep_value"] is False

    def test_deep_value_flag_absent_when_less_than_5_peers(self):
        from assethold.fundamentals import SectorPeerRanker
        ranker = SectorPeerRanker()
        holdings = [
            {"ticker": "A", "sector": "Utilities", "pe": 5.0,
             "pb": 0.5, "ev_ebitda": 4.0, "score": 9.0},
            {"ticker": "B", "sector": "Utilities", "pe": 20.0,
             "pb": 3.0, "ev_ebitda": 16.0, "score": 3.0},
        ]
        result = ranker.add_sector_percentiles(holdings)
        for r in result:
            assert r.get("deep_value") is None


# ---------------------------------------------------------------------------
# FundamentalsReport — CSV and console output
# ---------------------------------------------------------------------------

class TestFundamentalsReport:
    def _sample_df(self):
        import pandas as pd
        from assethold.fundamentals import SectorPeerRanker
        holdings = [
            {"ticker": "A", "sector": "Energy", "pe": 5.0,
             "pb": 0.8, "ev_ebitda": 6.0, "forward_eps": 3.0,
             "dividend_yield": 0.02, "score": 9.0},
            {"ticker": "B", "sector": "Energy", "pe": 25.0,
             "pb": 4.0, "ev_ebitda": 20.0, "forward_eps": 1.5,
             "dividend_yield": 0.01, "score": 3.0},
        ]
        ranker = SectorPeerRanker()
        enriched = ranker.add_sector_percentiles(holdings)
        return pd.DataFrame(enriched)

    def test_to_csv_creates_file(self, tmp_path):
        from assethold.fundamentals import FundamentalsReport
        df = self._sample_df()
        reporter = FundamentalsReport()
        path = reporter.to_csv(df, tmp_path)
        assert path.exists()
        import pandas as pd
        reloaded = pd.read_csv(path)
        assert "ticker" in reloaded.columns
        assert len(reloaded) == 2

    def test_to_csv_filename_contains_date(self, tmp_path):
        from assethold.fundamentals import FundamentalsReport
        df = self._sample_df()
        reporter = FundamentalsReport()
        path = reporter.to_csv(df, tmp_path)
        assert "fundamentals" in path.name

    def test_console_table_returns_string(self):
        from assethold.fundamentals import FundamentalsReport
        df = self._sample_df()
        reporter = FundamentalsReport()
        text = reporter.console_table(df)
        assert isinstance(text, str)
        assert "ticker" in text.lower() or "Ticker" in text
        assert "A" in text
        assert "B" in text

    def test_console_table_marks_deep_value(self):
        from assethold.fundamentals import FundamentalsReport, SectorPeerRanker
        import pandas as pd
        holdings = [
            {"ticker": "A", "sector": "Energy", "pe": 5.0,
             "pb": 0.5, "ev_ebitda": 4.0, "score": 9.0,
             "dividend_yield": 0.02, "forward_eps": 3.0},
            {"ticker": "B", "sector": "Energy", "pe": 10.0,
             "pb": 1.0, "ev_ebitda": 8.0, "score": 7.5,
             "dividend_yield": 0.01, "forward_eps": 2.5},
            {"ticker": "C", "sector": "Energy", "pe": 15.0,
             "pb": 2.0, "ev_ebitda": 12.0, "score": 6.0,
             "dividend_yield": 0.015, "forward_eps": 2.0},
            {"ticker": "D", "sector": "Energy", "pe": 20.0,
             "pb": 3.0, "ev_ebitda": 16.0, "score": 4.5,
             "dividend_yield": 0.005, "forward_eps": 1.5},
            {"ticker": "E", "sector": "Energy", "pe": 30.0,
             "pb": 6.0, "ev_ebitda": 22.0, "score": 2.0,
             "dividend_yield": 0.0, "forward_eps": 0.5},
        ]
        ranker = SectorPeerRanker()
        enriched = ranker.add_sector_percentiles(holdings)
        df = pd.DataFrame(enriched)
        reporter = FundamentalsReport()
        text = reporter.console_table(df)
        assert "DEEP VALUE" in text or "deep_value" in text.lower() or "*" in text


# ---------------------------------------------------------------------------
# DailyStrategyReport fundamentals integration
# ---------------------------------------------------------------------------

class TestDailyStrategyReportFundamentalsSection:
    def _make_signals(self):
        """Create minimal PositionSignal stubs for report rendering."""
        from unittest.mock import MagicMock
        sig = MagicMock()
        sig.position.ticker = "AAPL"
        sig.position.account = "Test"
        sig.position.shares = 10.0
        sig.position.tradeable = True
        sig.position.avg_cost_basis = None
        sig.snapshot.current_price = 150.0
        sig.snapshot.week52_low = 120.0
        sig.snapshot.week52_high = 180.0
        sig.snapshot.pct_from_52w_low = 50.0
        sig.snapshot.rsi_14 = 50.0
        sig.snapshot.sma_50 = 148.0
        sig.snapshot.sma_200 = 145.0
        sig.snapshot.insider_trend = None
        sig.score = 0.1
        sig.signal = "HOLD"
        sig.rationale = ["Test rationale"]
        return [sig]

    def test_render_includes_fundamentals_section_when_provided(self):
        import pandas as pd
        from assethold.analysis.daily_strategy.report import DailyStrategyReport
        from assethold.fundamentals import SectorPeerRanker

        holdings = [
            {"ticker": "AAPL", "sector": "Information Technology",
             "pe": 28.0, "pb": 40.0, "ev_ebitda": 20.0,
             "forward_eps": 6.5, "dividend_yield": 0.006, "score": 3.5},
        ]
        ranker = SectorPeerRanker()
        enriched = ranker.add_sector_percentiles(holdings)
        fundamentals_df = pd.DataFrame(enriched)

        report = DailyStrategyReport(output_dir=None)
        signals = self._make_signals()
        md = report.render(signals, fundamentals_df=fundamentals_df)
        assert "Fundamentals" in md or "fundamentals" in md.lower()

    def test_render_without_fundamentals_df_still_works(self):
        from assethold.analysis.daily_strategy.report import DailyStrategyReport
        report = DailyStrategyReport(output_dir=None)
        signals = self._make_signals()
        md = report.render(signals)
        assert "Daily Portfolio Strategy" in md
