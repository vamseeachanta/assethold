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
