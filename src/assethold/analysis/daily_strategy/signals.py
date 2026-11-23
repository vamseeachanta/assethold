"""
Signal engine for daily portfolio strategy.

Scores each position against market data and returns a human-readable
recommendation: STRONG BUILD, BUILD, HOLD, TRIM, or STRONG TRIM.

Scoring model (weighted sum in [-1.0, +1.0]):

    Sub-signal          Weight   Logic
    ─────────────────   ──────   ────────────────────────────────────────────
    RSI momentum         0.25    RSI<30 → +1.0, RSI>70 → -1.0, linear between
    52-week position     0.20    Near 52w low → +1.0, near high → -1.0
    Price vs SMA-50      0.20    Below SMA-50 → +0.5, above → -0.5
    Price vs SMA-200     0.15    Below SMA-200 → +0.75, above → -0.5
    Portfolio weight     0.10    Drift from target triggers build/trim
    P/E vs sector        0.10    Deferred (returns 0.0 in v1)

Weights are renormalized when sub-signals are unavailable (e.g. no P/E data).

Position mode (from config):
    managed   — full signal range, all sub-signals active
    trim_only — build sub-signals suppressed; score clamped to ≤ 0.
                Used for individual stocks held for long-term opportunity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from assethold.analysis.daily_strategy.fetcher import MarketSnapshot
from assethold.analysis.daily_strategy.loader import Position

# Score → signal label thresholds
_THRESHOLDS = [
    (0.50, "STRONG BUILD"),
    (0.20, "BUILD"),
    (-0.20, "HOLD"),
    (-0.50, "TRIM"),
]


def _score_to_signal(score: float) -> str:
    for threshold, label in _THRESHOLDS:
        if score >= threshold:
            return label
    return "STRONG TRIM"


@dataclass
class PositionSignal:
    """Scored recommendation for a single position."""

    position: Position
    snapshot: MarketSnapshot
    score: float           # [-1.0, +1.0]
    signal: str            # STRONG BUILD | BUILD | HOLD | TRIM | STRONG TRIM
    rationale: list[str] = field(default_factory=list)


@dataclass
class _SubSignal:
    name: str
    value: float     # [-1.0, +1.0]
    weight: float
    note: str        # human-readable explanation


class SignalEngine:
    """Score portfolio positions and generate daily strategy recommendations."""

    _DEFAULT_WEIGHTS = {
        "rsi": 0.25,
        "week52": 0.20,
        "sma50": 0.20,
        "sma200": 0.15,
        "weight": 0.10,
        "pe": 0.10,
    }

    def __init__(self, config: Optional[dict[str, Any]] = None):
        """
        Args:
            config: Full daily_strategy.yaml dict (or just the relevant sections).
                    When None, default weights and thresholds are used.
        """
        cfg = config or {}
        scoring = cfg.get("scoring", {})

        self._rsi_oversold: float = float(scoring.get("rsi_oversold", 30))
        self._rsi_overbought: float = float(scoring.get("rsi_overbought", 70))

        # Per-ticker target configuration: {ticker: {mode, target_weight, max_weight}}
        self._targets: dict[str, dict[str, Any]] = {
            k.upper(): v for k, v in cfg.get("targets", {}).items()
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(
        self,
        position: Position,
        snapshot: MarketSnapshot,
        portfolio_value: float = 0.0,
    ) -> PositionSignal:
        """
        Score a single position.

        Args:
            position:        The holding to evaluate.
            snapshot:        Current market data for the ticker.
            portfolio_value: Total combined portfolio value (USD) used to
                             compute position weight.  Pass 0 to skip weight signal.

        Returns:
            PositionSignal with score, label, and rationale.
        """
        ticker_cfg = self._targets.get(position.ticker.upper(), {})
        mode = ticker_cfg.get("mode", "managed")

        sub_signals = self._build_sub_signals(
            position, snapshot, portfolio_value, ticker_cfg, mode
        )

        # Weighted sum with renormalization for missing sub-signals
        total_weight = sum(s.weight for s in sub_signals if s.value is not None)
        if total_weight == 0:
            raw_score = 0.0
        else:
            raw_score = sum(
                s.value * s.weight for s in sub_signals if s.value is not None
            ) / total_weight

        # trim_only mode: clamp score to ≤ 0 (no build signals)
        score = max(-1.0, min(1.0, raw_score))
        if mode == "trim_only":
            score = min(0.0, score)

        signal = _score_to_signal(score)
        rationale = [s.note for s in sub_signals if s.value is not None]

        return PositionSignal(
            position=position,
            snapshot=snapshot,
            score=round(score, 3),
            signal=signal,
            rationale=rationale,
        )

    def score_batch(
        self,
        positions: list[Position],
        snapshots: dict[str, Optional[MarketSnapshot]],
        portfolio_value: float = 0.0,
    ) -> list[PositionSignal]:
        """
        Score a list of positions, skipping non-tradeable ones.

        Non-tradeable positions (employee account funds) are returned with a
        HOLD signal and a note explaining why they are not scored.
        """
        results: list[PositionSignal] = []
        for pos in positions:
            snap = snapshots.get(pos.ticker)
            if not pos.tradeable or snap is None:
                results.append(
                    PositionSignal(
                        position=pos,
                        snapshot=snap,  # type: ignore[arg-type]
                        score=0.0,
                        signal="HOLD",
                        rationale=["Non-tradeable position — no market signal generated."],
                    )
                )
                continue
            results.append(self.score(pos, snap, portfolio_value))
        return results

    # ------------------------------------------------------------------
    # Sub-signal builders
    # ------------------------------------------------------------------

    def _build_sub_signals(
        self,
        position: Position,
        snap: MarketSnapshot,
        portfolio_value: float,
        ticker_cfg: dict[str, Any],
        mode: str,
    ) -> list[_SubSignal]:
        sigs: list[_SubSignal] = []

        # --- RSI momentum ---
        if snap.rsi_14 is not None:
            val = self._rsi_signal(snap.rsi_14)
            if mode == "trim_only":
                val = min(0.0, val)  # suppress build signal
            rsi_str = f"{snap.rsi_14:.1f}"
            if val > 0.3:
                note = f"RSI {rsi_str} — oversold, buying opportunity"
            elif val < -0.3:
                note = f"RSI {rsi_str} — overbought, consider trimming"
            else:
                note = f"RSI {rsi_str} — neutral momentum"
            sigs.append(_SubSignal("rsi", val, self._DEFAULT_WEIGHTS["rsi"], note))

        # --- 52-week position ---
        pct_low = snap.pct_from_52w_low  # 0 = at 52w low, 100 = at 52w high
        val_52w = round(1.0 - 2.0 * (pct_low / 100.0), 3)  # maps [0,100] → [+1,-1]
        if mode == "trim_only":
            val_52w = min(0.0, val_52w)
        price_range_note = (
            f"Price is {pct_low:.0f}% of 52-week range "
            f"(low ${snap.week52_low:.2f} / high ${snap.week52_high:.2f})"
        )
        sigs.append(_SubSignal("week52", val_52w, self._DEFAULT_WEIGHTS["week52"], price_range_note))

        # --- Price vs SMA-50 ---
        if snap.sma_50 is not None:
            raw = (snap.sma_50 - snap.current_price) / snap.sma_50
            val_sma50 = max(-0.5, min(0.5, raw * 5))  # scale ±10% → ±0.5
            if mode == "trim_only":
                val_sma50 = min(0.0, val_sma50)
            rel = "below" if snap.current_price < snap.sma_50 else "above"
            pct = abs((snap.current_price - snap.sma_50) / snap.sma_50 * 100)
            note = f"Price {rel} 50-day SMA by {pct:.1f}% (SMA ${snap.sma_50:.2f})"
            sigs.append(_SubSignal("sma50", val_sma50, self._DEFAULT_WEIGHTS["sma50"], note))

        # --- Price vs SMA-200 ---
        if snap.sma_200 is not None:
            raw = (snap.sma_200 - snap.current_price) / snap.sma_200
            val_sma200 = max(-0.5, min(0.75, raw * 5))
            if mode == "trim_only":
                val_sma200 = min(0.0, val_sma200)
            rel = "below" if snap.current_price < snap.sma_200 else "above"
            pct = abs((snap.current_price - snap.sma_200) / snap.sma_200 * 100)
            note = f"Price {rel} 200-day SMA by {pct:.1f}% (SMA ${snap.sma_200:.2f})"
            sigs.append(_SubSignal("sma200", val_sma200, self._DEFAULT_WEIGHTS["sma200"], note))

        # --- Portfolio weight ---
        if portfolio_value > 0:
            pos_value = position.shares * snap.current_price
            actual_weight = pos_value / portfolio_value * 100.0
            weight_sig = self._weight_signal(actual_weight, ticker_cfg, mode)
            if weight_sig is not None:
                sigs.append(weight_sig)

        # --- Insider trend ---
        insider = getattr(snap, "insider_trend", None)
        if insider is not None and insider.trend not in ("N/A", "NEUTRAL"):
            insider_val = self._insider_signal(insider.trend)
            if mode == "trim_only":
                insider_val = min(0.0, insider_val)
            sigs.append(
                _SubSignal(
                    "insider",
                    insider_val,
                    self._DEFAULT_WEIGHTS["pe"],  # reuse the 10% P/E weight slot
                    f"Insider trend {insider.trend}: {insider.summary}",
                )
            )

        return sigs

    def _rsi_signal(self, rsi: float) -> float:
        """Map RSI [0,100] → score [-1, +1]. Linear between oversold/overbought."""
        if rsi <= self._rsi_oversold:
            return 1.0
        if rsi >= self._rsi_overbought:
            return -1.0
        mid = (self._rsi_oversold + self._rsi_overbought) / 2.0
        half_range = (self._rsi_overbought - self._rsi_oversold) / 2.0
        return round((mid - rsi) / half_range, 3)

    @staticmethod
    def _insider_signal(trend: str) -> float:
        """Map insider trend label to a sub-signal value [-1.0, +1.0]."""
        return {
            "BULLISH": 0.75,
            "MIXED": -0.1,
            "BEARISH": -0.75,
        }.get(trend, 0.0)

    def _weight_signal(
        self,
        actual_weight: float,
        ticker_cfg: dict[str, Any],
        mode: str,
    ) -> Optional[_SubSignal]:
        """Return a weight sub-signal based on mode and target/max config."""
        if mode == "managed" and "target_weight" in ticker_cfg:
            target = float(ticker_cfg["target_weight"])
            drift = (target - actual_weight) / max(target, 1.0)
            val = max(-1.0, min(1.0, drift * 2))
            if drift > 0.1:
                note = f"Position {actual_weight:.1f}% — under target {target:.0f}%, consider building"
            elif drift < -0.1:
                note = f"Position {actual_weight:.1f}% — over target {target:.0f}%, consider trimming"
            else:
                note = f"Position {actual_weight:.1f}% — near target {target:.0f}%"
            return _SubSignal("weight", val, self._DEFAULT_WEIGHTS["weight"], note)

        if mode == "trim_only" and "max_weight" in ticker_cfg:
            max_w = float(ticker_cfg["max_weight"])
            if actual_weight > max_w:
                excess = (actual_weight - max_w) / max_w
                val = -min(1.0, excess * 2)
                note = f"Position {actual_weight:.1f}% — exceeds max {max_w:.0f}%, trim recommended"
                return _SubSignal("weight", val, self._DEFAULT_WEIGHTS["weight"], note)
            note = f"Position {actual_weight:.1f}% — within max {max_w:.0f}%, hold"
            return _SubSignal("weight", 0.0, self._DEFAULT_WEIGHTS["weight"], note)

        return None
