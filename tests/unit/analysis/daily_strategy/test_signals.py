"""
Unit tests for SignalEngine.

All inputs are synthetic — no real market data or network calls.
"""

from dataclasses import dataclass
from typing import Optional

import pytest

from assethold.analysis.daily_strategy.fetcher import MarketSnapshot
from assethold.analysis.daily_strategy.loader import Position
from assethold.analysis.daily_strategy.signals import SignalEngine, _score_to_signal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _position(
    ticker: str = "BRKB",
    shares: float = 50.0,
    tradeable: bool = True,
    account: str = "Individual - TOD",
    avg_cost: Optional[float] = 300.0,
) -> Position:
    return Position(
        account=account,
        account_number="X78707567",
        ticker=ticker,
        shares=shares,
        tradeable=tradeable,
        avg_cost_basis=avg_cost,
    )


def _snapshot(
    ticker: str = "BRKB",
    current_price: float = 300.0,
    week52_high: float = 360.0,
    week52_low: float = 240.0,
    pct_from_52w_low: float = 50.0,
    pct_from_52w_high: float = 16.7,
    rsi_14: Optional[float] = 50.0,
    sma_50: Optional[float] = 295.0,
    sma_200: Optional[float] = 280.0,
    pe_ratio: Optional[float] = 20.0,
    price_to_book: Optional[float] = 1.5,
) -> MarketSnapshot:
    return MarketSnapshot(
        ticker=ticker,
        current_price=current_price,
        week52_high=week52_high,
        week52_low=week52_low,
        pct_from_52w_low=pct_from_52w_low,
        pct_from_52w_high=pct_from_52w_high,
        rsi_14=rsi_14,
        sma_50=sma_50,
        sma_200=sma_200,
        pe_ratio=pe_ratio,
        price_to_book=price_to_book,
    )


def _engine(extra_config: Optional[dict] = None) -> SignalEngine:
    cfg = {
        "scoring": {"rsi_oversold": 30, "rsi_overbought": 70},
        "targets": {
            "BRKB": {"mode": "managed", "target_weight": 25.0},
            "VOO": {"mode": "managed", "target_weight": 25.0},
            "XOM": {"mode": "trim_only", "max_weight": 15.0},
            "RIG": {"mode": "trim_only", "max_weight": 10.0},
        },
    }
    if extra_config:
        cfg.update(extra_config)
    return SignalEngine(cfg)


# ---------------------------------------------------------------------------
# Score-to-signal label mapping
# ---------------------------------------------------------------------------


class TestScoreToSignal:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.51, "STRONG BUILD"),
            (0.50, "STRONG BUILD"),
            (0.35, "BUILD"),
            (0.20, "BUILD"),
            (0.10, "HOLD"),
            (0.00, "HOLD"),
            (-0.10, "HOLD"),
            (-0.20, "HOLD"),
            (-0.35, "TRIM"),
            (-0.50, "TRIM"),
            (-0.51, "STRONG TRIM"),
            (-1.00, "STRONG TRIM"),
        ],
    )
    def test_thresholds(self, score, expected):
        assert _score_to_signal(score) == expected


# ---------------------------------------------------------------------------
# RSI sub-signal
# ---------------------------------------------------------------------------


class TestRsiSignal:
    def test_oversold_rsi_produces_build_signal(self):
        eng = _engine()
        snap = _snapshot(rsi_14=20.0, sma_50=None, sma_200=None, pct_from_52w_low=50.0)
        sig = eng.score(_position(), snap, portfolio_value=0)
        assert sig.score > 0

    def test_overbought_rsi_produces_trim_signal(self):
        eng = _engine()
        snap = _snapshot(rsi_14=80.0, sma_50=None, sma_200=None, pct_from_52w_low=50.0)
        sig = eng.score(_position(), snap, portfolio_value=0)
        assert sig.score < 0

    def test_neutral_rsi_gives_zero_contribution(self):
        eng = _engine()
        snap_neutral = _snapshot(rsi_14=50.0, sma_50=None, sma_200=None, pct_from_52w_low=50.0)
        sig = eng.score(_position(), snap_neutral, portfolio_value=0)
        # At 52w midpoint and RSI 50, score should be near 0
        assert abs(sig.score) < 0.15

    def test_rsi_none_does_not_crash(self):
        eng = _engine()
        snap = _snapshot(rsi_14=None, sma_50=None, sma_200=None)
        sig = eng.score(_position(), snap, portfolio_value=0)
        assert sig.signal in {"STRONG BUILD", "BUILD", "HOLD", "TRIM", "STRONG TRIM"}

    def test_rsi_boundary_exactly_oversold(self):
        eng = _engine()
        rsi_score = eng._rsi_signal(30.0)
        assert rsi_score == pytest.approx(1.0)

    def test_rsi_boundary_exactly_overbought(self):
        eng = _engine()
        rsi_score = eng._rsi_signal(70.0)
        assert rsi_score == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# 52-week position sub-signal
# ---------------------------------------------------------------------------


class TestWeek52Signal:
    def test_near_52w_low_produces_positive_score(self):
        eng = _engine()
        snap = _snapshot(pct_from_52w_low=5.0, rsi_14=None, sma_50=None, sma_200=None)
        sig = eng.score(_position(), snap, portfolio_value=0)
        assert sig.score > 0

    def test_near_52w_high_produces_negative_score(self):
        eng = _engine()
        snap = _snapshot(pct_from_52w_low=95.0, rsi_14=None, sma_50=None, sma_200=None)
        sig = eng.score(_position(), snap, portfolio_value=0)
        assert sig.score < 0


# ---------------------------------------------------------------------------
# SMA sub-signals
# ---------------------------------------------------------------------------


class TestSmaSignals:
    def test_price_below_sma50_positive_contribution(self):
        eng = _engine()
        snap = _snapshot(current_price=280.0, sma_50=300.0, sma_200=None, rsi_14=50.0, pct_from_52w_low=50.0)
        sig = eng.score(_position(), snap, portfolio_value=0)
        # Below SMA-50 should push score positive
        assert sig.score > 0

    def test_price_above_sma200_negative_contribution(self):
        eng = _engine()
        snap = _snapshot(current_price=350.0, sma_50=None, sma_200=300.0, rsi_14=50.0, pct_from_52w_low=50.0)
        sig = eng.score(_position(), snap, portfolio_value=0)
        # Above SMA-200 pushes score negative
        assert sig.score < 0


# ---------------------------------------------------------------------------
# Portfolio weight sub-signal
# ---------------------------------------------------------------------------


class TestWeightSignal:
    def test_underweight_managed_pushes_build(self):
        eng = _engine()
        # Portfolio = $100k, BRKB = $10k → 10% actual vs 25% target → underweight
        pos = _position("BRKB", shares=33.33)
        snap = _snapshot("BRKB", current_price=300.0)
        sig = eng.score(pos, snap, portfolio_value=100_000)
        # Weight sub-signal should be positive (build)
        weight_notes = [n for n in sig.rationale if "target" in n.lower()]
        assert any("under target" in n for n in weight_notes)

    def test_overweight_managed_pushes_trim(self):
        eng = _engine()
        # Portfolio = $100k, BRKB = $40k → 40% actual vs 25% target → overweight
        pos = _position("BRKB", shares=133.33)
        snap = _snapshot("BRKB", current_price=300.0)
        sig = eng.score(pos, snap, portfolio_value=100_000)
        weight_notes = [n for n in sig.rationale if "target" in n.lower()]
        assert any("over target" in n for n in weight_notes)

    def test_trim_only_above_max_weight_negative(self):
        eng = _engine()
        # XOM max_weight = 15%; actual = 25% → should push trim
        pos = _position("XOM", shares=83.33)
        snap = _snapshot("XOM", current_price=300.0)
        sig = eng.score(pos, snap, portfolio_value=100_000)
        assert sig.score <= 0

    def test_zero_portfolio_value_skips_weight_signal(self):
        eng = _engine()
        sig = eng.score(_position("BRKB"), _snapshot("BRKB"), portfolio_value=0)
        weight_notes = [n for n in sig.rationale if "target" in n.lower() or "max" in n.lower()]
        assert len(weight_notes) == 0


# ---------------------------------------------------------------------------
# trim_only mode
# ---------------------------------------------------------------------------


class TestTrimOnlyMode:
    def test_score_never_positive_for_trim_only(self):
        eng = _engine()
        # Even with very oversold RSI and near 52w low, XOM score should be ≤ 0
        snap = _snapshot("XOM", rsi_14=15.0, pct_from_52w_low=2.0)
        sig = eng.score(_position("XOM"), snap, portfolio_value=100_000)
        assert sig.score <= 0

    def test_trim_only_can_still_hold(self):
        eng = _engine()
        snap = _snapshot("RIG", rsi_14=50.0, pct_from_52w_low=50.0, sma_50=None, sma_200=None)
        pos = _position("RIG", shares=10.0)
        sig = eng.score(pos, snap, portfolio_value=100_000)
        assert sig.signal in {"HOLD", "TRIM", "STRONG TRIM"}

    def test_trim_only_with_high_rsi_produces_trim(self):
        eng = _engine()
        snap = _snapshot("XOM", rsi_14=80.0, pct_from_52w_low=95.0)
        sig = eng.score(_position("XOM"), snap, portfolio_value=100_000)
        assert sig.signal in {"TRIM", "STRONG TRIM"}


# ---------------------------------------------------------------------------
# Rationale content
# ---------------------------------------------------------------------------


class TestRationale:
    def test_rationale_is_non_empty(self):
        eng = _engine()
        sig = eng.score(_position(), _snapshot(), portfolio_value=0)
        assert len(sig.rationale) > 0

    def test_rationale_contains_rsi_note(self):
        eng = _engine()
        sig = eng.score(_position(), _snapshot(rsi_14=65.0), portfolio_value=0)
        assert any("RSI" in note for note in sig.rationale)

    def test_rationale_contains_52w_note(self):
        eng = _engine()
        sig = eng.score(_position(), _snapshot(), portfolio_value=0)
        assert any("52-week" in note for note in sig.rationale)


# ---------------------------------------------------------------------------
# Batch scoring
# ---------------------------------------------------------------------------


class TestBatchScoring:
    def test_batch_scores_all_tradeable_positions(self):
        eng = _engine()
        positions = [_position("BRKB"), _position("XOM")]
        snapshots = {
            "BRKB": _snapshot("BRKB"),
            "XOM": _snapshot("XOM"),
        }
        results = eng.score_batch(positions, snapshots, portfolio_value=100_000)
        assert len(results) == 2

    def test_nontradeable_gets_hold_signal(self):
        eng = _engine()
        pos = _position("FID 500 INDEX", tradeable=False)
        results = eng.score_batch([pos], {}, portfolio_value=100_000)
        assert results[0].signal == "HOLD"
        assert "Non-tradeable" in results[0].rationale[0]

    def test_missing_snapshot_gives_hold(self):
        eng = _engine()
        pos = _position("BRKB", tradeable=True)
        results = eng.score_batch([pos], {}, portfolio_value=100_000)
        assert results[0].signal == "HOLD"

    def test_batch_respects_trim_only_mode(self):
        eng = _engine()
        pos = _position("XOM", shares=83.33)
        snap = _snapshot("XOM", rsi_14=15.0, pct_from_52w_low=2.0)
        results = eng.score_batch([pos], {"XOM": snap}, portfolio_value=100_000)
        assert results[0].score <= 0
