# ABOUTME: Unit tests for fundamentals scoring — P/E, P/B, EV/EBITDA scoring and ranking.
# ABOUTME: Tests individual metric scorers, composite scoring, ranking, and sector percentiles.

import pytest
from assethold.fundamentals import (
    score_pe_ratio,
    score_pb_ratio,
    score_ev_ebitda,
    FundamentalsScorer,
    SectorPeerRanker,
    _percentile_rank_lower_is_better,
    _percentile_rank_higher_is_better,
)


class TestScorePeRatio:
    def test_none_returns_zero(self):
        assert score_pe_ratio(None) == 0.0

    def test_negative_returns_zero(self):
        assert score_pe_ratio(-5.0) == 0.0

    def test_zero_returns_zero(self):
        assert score_pe_ratio(0.0) == 0.0

    def test_very_low_pe(self):
        assert score_pe_ratio(5.0) == 10.0

    def test_low_pe(self):
        assert score_pe_ratio(12.0) == 8.0

    def test_moderate_pe(self):
        assert score_pe_ratio(17.0) == 6.0

    def test_high_pe(self):
        assert score_pe_ratio(22.0) == 4.0

    def test_very_high_pe(self):
        assert score_pe_ratio(30.0) == 2.0

    def test_boundary_at_10(self):
        assert score_pe_ratio(9.99) == 10.0
        assert score_pe_ratio(10.0) == 8.0

    def test_boundary_at_15(self):
        assert score_pe_ratio(14.99) == 8.0
        assert score_pe_ratio(15.0) == 6.0


class TestScorePbRatio:
    def test_none_returns_zero(self):
        assert score_pb_ratio(None) == 0.0

    def test_negative_returns_zero(self):
        assert score_pb_ratio(-1.0) == 0.0

    def test_below_one(self):
        assert score_pb_ratio(0.5) == 10.0

    def test_one_to_two(self):
        assert score_pb_ratio(1.5) == 8.0

    def test_two_to_three(self):
        assert score_pb_ratio(2.5) == 6.0

    def test_three_to_five(self):
        assert score_pb_ratio(4.0) == 4.0

    def test_above_five(self):
        assert score_pb_ratio(10.0) == 2.0


class TestScoreEvEbitda:
    def test_none_returns_zero(self):
        assert score_ev_ebitda(None) == 0.0

    def test_negative_returns_zero(self):
        assert score_ev_ebitda(-3.0) == 0.0

    def test_below_8(self):
        assert score_ev_ebitda(6.0) == 10.0

    def test_8_to_12(self):
        assert score_ev_ebitda(10.0) == 8.0

    def test_12_to_16(self):
        assert score_ev_ebitda(14.0) == 6.0

    def test_16_to_20(self):
        assert score_ev_ebitda(18.0) == 4.0

    def test_above_20(self):
        assert score_ev_ebitda(25.0) == 2.0


class TestFundamentalsScorer:
    def setup_method(self):
        self.scorer = FundamentalsScorer()

    def test_score_all_metrics_present(self):
        data = {"pe": 8.0, "pb": 0.8, "ev_ebitda": 6.0}
        score = self.scorer.score(data)
        expected = 10.0 * 0.35 + 10.0 * 0.35 + 10.0 * 0.30
        assert score == pytest.approx(expected)

    def test_score_all_none(self):
        data = {"pe": None, "pb": None, "ev_ebitda": None}
        assert self.scorer.score(data) == 0.0

    def test_score_missing_keys(self):
        data = {"ticker": "AAPL"}
        assert self.scorer.score(data) == 0.0

    def test_score_mixed_values(self):
        data = {"pe": 12.0, "pb": 4.0, "ev_ebitda": 25.0}
        expected = 8.0 * 0.35 + 4.0 * 0.35 + 2.0 * 0.30
        assert self.scorer.score(data) == pytest.approx(expected)

    def test_rank_orders_by_score_descending(self):
        holdings = [
            {"ticker": "A", "pe": 30.0, "pb": 10.0, "ev_ebitda": 25.0},
            {"ticker": "B", "pe": 8.0, "pb": 0.8, "ev_ebitda": 6.0},
            {"ticker": "C", "pe": 17.0, "pb": 2.5, "ev_ebitda": 14.0},
        ]
        ranked = self.scorer.rank(holdings)
        assert ranked[0]["ticker"] == "B"
        assert ranked[-1]["ticker"] == "A"
        assert all("score" in h for h in ranked)

    def test_rank_preserves_original_data(self):
        holdings = [{"ticker": "X", "pe": 5.0, "pb": 0.5, "ev_ebitda": 3.0}]
        ranked = self.scorer.rank(holdings)
        assert ranked[0]["ticker"] == "X"

    def test_rank_empty_list(self):
        assert self.scorer.rank([]) == []


class TestPercentileRank:
    def test_lower_is_better_cheapest_gets_100(self):
        values = [5.0, 10.0, 15.0, 20.0]
        pct = _percentile_rank_lower_is_better(values, 0)
        assert pct == 100.0

    def test_lower_is_better_most_expensive_gets_25(self):
        values = [5.0, 10.0, 15.0, 20.0]
        pct = _percentile_rank_lower_is_better(values, 3)
        assert pct == 25.0

    def test_lower_is_better_none_target(self):
        values = [5.0, None, 15.0]
        assert _percentile_rank_lower_is_better(values, 1) is None

    def test_lower_is_better_single_value(self):
        values = [10.0]
        assert _percentile_rank_lower_is_better(values, 0) == 100.0

    def test_higher_is_better_best_gets_100(self):
        values = [2.0, 5.0, 8.0, 10.0]
        pct = _percentile_rank_higher_is_better(values, 3)
        assert pct == 100.0

    def test_higher_is_better_worst_gets_25(self):
        values = [2.0, 5.0, 8.0, 10.0]
        pct = _percentile_rank_higher_is_better(values, 0)
        assert pct == 25.0


class TestSectorPeerRanker:
    def setup_method(self):
        self.ranker = SectorPeerRanker()

    def test_adds_percentile_keys(self):
        holdings = [
            {"ticker": "A", "sector": "Tech", "pe": 10.0, "pb": 1.0, "ev_ebitda": 8.0, "score": 7.0},
            {"ticker": "B", "sector": "Tech", "pe": 20.0, "pb": 3.0, "ev_ebitda": 16.0, "score": 4.0},
        ]
        enriched = self.ranker.add_sector_percentiles(holdings)
        assert "pe_pct" in enriched[0]
        assert "pb_pct" in enriched[0]
        assert "ev_ebitda_pct" in enriched[0]

    def test_deep_value_none_when_too_few_peers(self):
        holdings = [
            {"ticker": "A", "sector": "Energy", "pe": 5.0, "pb": 0.5, "ev_ebitda": 4.0, "score": 9.0},
        ]
        enriched = self.ranker.add_sector_percentiles(holdings)
        assert enriched[0]["deep_value"] is None

    def test_deep_value_flag_with_enough_peers(self):
        holdings = [
            {"ticker": f"T{i}", "sector": "Tech", "pe": 10.0 + i * 5, "pb": 1.0 + i, "ev_ebitda": 8.0 + i * 4, "score": 10.0 - i}
            for i in range(6)
        ]
        enriched = self.ranker.add_sector_percentiles(holdings)
        assert enriched[0]["deep_value"] is True
        assert enriched[-1]["deep_value"] is False

    def test_different_sectors_ranked_independently(self):
        holdings = [
            {"ticker": "A", "sector": "Tech", "pe": 5.0, "pb": 0.5, "ev_ebitda": 4.0, "score": 9.0},
            {"ticker": "B", "sector": "Energy", "pe": 25.0, "pb": 5.0, "ev_ebitda": 20.0, "score": 2.0},
        ]
        enriched = self.ranker.add_sector_percentiles(holdings)
        # Each is the only member of its sector, so both get 100% on all metrics
        assert enriched[0]["pe_pct"] == 100.0
        assert enriched[1]["pe_pct"] == 100.0
