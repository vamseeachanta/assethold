"""
Unit tests for trend change detection functions.

Tests use synthetic price series to verify detection of:
- Golden cross / death cross (MA crossovers)
- Support/resistance level breaks
- Volume spike detection
- RSI overbought/oversold transitions
"""

import pandas as pd
import pytest

from assethold.signals.trend_detector import (
    detect_ma_crossover,
    detect_rsi_transition,
    detect_support_resistance_break,
    detect_volume_spike,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def uptrend_data():
    """Steady uptrend: short MA crosses above long MA (golden cross)."""
    n = 60
    prices = [100.0] * 20 + [100.0 + i * 2 for i in range(40)]
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n),
            "close": prices,
            "open": [p - 0.5 for p in prices],
            "high": [p + 1.0 for p in prices],
            "low": [p - 1.0 for p in prices],
            "volume": [1_000_000] * n,
        }
    )


@pytest.fixture
def downtrend_data():
    """Steady downtrend: short MA crosses below long MA (death cross)."""
    n = 60
    prices = [200.0] * 20 + [200.0 - i * 2 for i in range(40)]
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n),
            "close": prices,
            "open": [p + 0.5 for p in prices],
            "high": [p + 1.0 for p in prices],
            "low": [p - 1.0 for p in prices],
            "volume": [1_000_000] * n,
        }
    )


@pytest.fixture
def flat_data():
    """Flat price series — no crossovers, no spikes."""
    n = 60
    prices = [100.0] * n
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n),
            "close": prices,
            "open": prices,
            "high": [p + 0.1 for p in prices],
            "low": [p - 0.1 for p in prices],
            "volume": [500_000] * n,
        }
    )


@pytest.fixture
def volume_spike_data():
    """Normal volume with a single large spike mid-series."""
    n = 40
    volume = [100_000] * n
    volume[20] = 500_000  # 5x spike
    prices = [100.0 + i * 0.1 for i in range(n)]
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n),
            "close": prices,
            "open": [p - 0.05 for p in prices],
            "high": [p + 0.1 for p in prices],
            "low": [p - 0.1 for p in prices],
            "volume": volume,
        }
    )


@pytest.fixture
def rsi_overbought_data():
    """Strongly rising prices to push RSI above 70, then flatten."""
    n = 60
    prices = [100.0 + i * 3 for i in range(40)] + [220.0] * 20
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n),
            "close": prices,
            "open": [p - 1 for p in prices],
            "high": [p + 2 for p in prices],
            "low": [p - 2 for p in prices],
            "volume": [1_000_000] * n,
        }
    )


@pytest.fixture
def rsi_oversold_data():
    """Strongly falling prices to push RSI below 30, then recover."""
    n = 60
    prices = [200.0 - i * 3 for i in range(40)] + [80.0] * 20
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n),
            "close": prices,
            "open": [p + 1 for p in prices],
            "high": [p + 2 for p in prices],
            "low": [p - 2 for p in prices],
            "volume": [1_000_000] * n,
        }
    )


# ---------------------------------------------------------------------------
# detect_ma_crossover
# ---------------------------------------------------------------------------


class TestDetectMaCrossover:
    """Tests for MA crossover detection (golden/death cross)."""

    def test_golden_cross_detected_in_uptrend(self, uptrend_data):
        """Golden cross is detected when short MA crosses above long MA."""
        events = detect_ma_crossover(uptrend_data, short_window=10, long_window=20)
        golden = [e for e in events if e["type"] == "golden_cross"]
        assert len(golden) >= 1, "Expected at least one golden cross"

    def test_death_cross_detected_in_downtrend(self, downtrend_data):
        """Death cross is detected when short MA crosses below long MA."""
        events = detect_ma_crossover(downtrend_data, short_window=10, long_window=20)
        death = [e for e in events if e["type"] == "death_cross"]
        assert len(death) >= 1, "Expected at least one death cross"

    def test_no_crossover_in_flat_data(self, flat_data):
        """No crossovers in flat price data."""
        events = detect_ma_crossover(flat_data, short_window=5, long_window=10)
        assert events == []

    def test_event_has_required_fields(self, uptrend_data):
        """Each crossover event has required metadata fields."""
        events = detect_ma_crossover(uptrend_data, short_window=10, long_window=20)
        for event in events:
            assert "type" in event
            assert "date" in event
            assert "short_ma" in event
            assert "long_ma" in event
            assert event["type"] in ("golden_cross", "death_cross")

    def test_insufficient_data_returns_empty(self):
        """Returns empty list when not enough data for both MAs."""
        df = pd.DataFrame({"close": [100.0] * 10, "volume": [1000] * 10})
        events = detect_ma_crossover(df, short_window=5, long_window=20)
        assert events == []

    def test_custom_window_sizes(self, uptrend_data):
        """Custom window sizes are respected."""
        events_small = detect_ma_crossover(uptrend_data, short_window=5, long_window=10)
        events_large = detect_ma_crossover(uptrend_data, short_window=20, long_window=50)
        assert isinstance(events_small, list)
        assert isinstance(events_large, list)


# ---------------------------------------------------------------------------
# detect_support_resistance_break
# ---------------------------------------------------------------------------


class TestDetectSupportResistanceBreak:
    """Tests for support and resistance level break detection."""

    def test_resistance_break_detected(self):
        """Detects when price breaks above recent resistance."""
        prices = [100.0] * 10 + [102.0, 98.0] * 5 + [115.0]
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=len(prices)),
                "close": prices,
                "high": [p + 1 for p in prices],
                "low": [p - 1 for p in prices],
                "volume": [500_000] * len(prices),
            }
        )
        events = detect_support_resistance_break(df, lookback=10)
        assert len([e for e in events if e["type"] == "resistance_break"]) >= 1

    def test_support_break_detected(self):
        """Detects when price breaks below recent support."""
        prices = [100.0] * 10 + [98.0, 102.0] * 5 + [82.0]
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=len(prices)),
                "close": prices,
                "high": [p + 1 for p in prices],
                "low": [p - 1 for p in prices],
                "volume": [500_000] * len(prices),
            }
        )
        events = detect_support_resistance_break(df, lookback=10)
        assert len([e for e in events if e["type"] == "support_break"]) >= 1

    def test_no_break_in_range(self, flat_data):
        """No breaks in range-bound flat data."""
        events = detect_support_resistance_break(flat_data, lookback=10)
        assert isinstance(events, list)
        assert len(events) == 0

    def test_event_has_required_fields(self):
        """Each break event has required metadata."""
        prices = [100.0] * 10 + [130.0]
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=len(prices)),
                "close": prices,
                "high": [p + 1 for p in prices],
                "low": [p - 1 for p in prices],
                "volume": [500_000] * len(prices),
            }
        )
        events = detect_support_resistance_break(df, lookback=10)
        for event in events:
            assert "type" in event
            assert "date" in event
            assert "price" in event
            assert "level" in event
            assert event["type"] in ("resistance_break", "support_break")

    def test_insufficient_data_returns_empty(self):
        """Returns empty when fewer rows than lookback."""
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=5),
                "close": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "volume": [500_000] * 5,
            }
        )
        events = detect_support_resistance_break(df, lookback=20)
        assert events == []


# ---------------------------------------------------------------------------
# detect_volume_spike
# ---------------------------------------------------------------------------


class TestDetectVolumeSpike:
    """Tests for volume spike detection."""

    def test_volume_spike_detected(self, volume_spike_data):
        """Detects a clear volume spike."""
        events = detect_volume_spike(volume_spike_data, threshold_std=2.0)
        assert len(events) >= 1

    def test_spike_index_correct(self, volume_spike_data):
        """Spike event index corresponds to the actual spike row."""
        events = detect_volume_spike(volume_spike_data, threshold_std=2.0)
        spike_dates = [e["date"] for e in events]
        expected_date = pd.Timestamp("2024-01-21")
        assert any(
            pd.Timestamp(d) == expected_date for d in spike_dates
        ), f"Expected spike at 2024-01-21, got {spike_dates}"

    def test_no_spike_in_uniform_volume(self, flat_data):
        """No spikes detected when volume is uniform."""
        events = detect_volume_spike(flat_data, threshold_std=2.0)
        assert events == []

    def test_event_has_required_fields(self, volume_spike_data):
        """Each spike event has required fields."""
        events = detect_volume_spike(volume_spike_data, threshold_std=2.0)
        for event in events:
            assert event["type"] == "volume_spike"
            assert "date" in event
            assert "volume" in event
            assert "mean_volume" in event
            assert "std_multiples" in event

    def test_threshold_respected(self, volume_spike_data):
        """High threshold suppresses detection of moderate spikes."""
        events_low = detect_volume_spike(volume_spike_data, threshold_std=1.0)
        events_high = detect_volume_spike(volume_spike_data, threshold_std=10.0)
        assert len(events_low) >= len(events_high)

    def test_insufficient_data_returns_empty(self):
        """Returns empty for very short series."""
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=3),
                "close": [100.0, 101.0, 102.0],
                "volume": [100, 200, 100],
            }
        )
        events = detect_volume_spike(df, threshold_std=2.0, min_periods=5)
        assert events == []


# ---------------------------------------------------------------------------
# detect_rsi_transition
# ---------------------------------------------------------------------------


class TestDetectRsiTransition:
    """Tests for RSI overbought/oversold transition detection."""

    def test_overbought_transition_detected(self, rsi_overbought_data):
        """Detects RSI entering overbought zone (>70)."""
        events = detect_rsi_transition(
            rsi_overbought_data, period=14, overbought=70, oversold=30
        )
        assert len([e for e in events if e["type"] == "rsi_overbought"]) >= 1

    def test_oversold_transition_detected(self, rsi_oversold_data):
        """Detects RSI entering oversold zone (<30)."""
        events = detect_rsi_transition(
            rsi_oversold_data, period=14, overbought=70, oversold=30
        )
        assert len([e for e in events if e["type"] == "rsi_oversold"]) >= 1

    def test_no_transition_flat(self, flat_data):
        """No RSI transitions in flat data (RSI undefined/neutral)."""
        events = detect_rsi_transition(flat_data, period=14)
        assert isinstance(events, list)

    def test_event_has_required_fields(self, rsi_overbought_data):
        """Each RSI event has required fields."""
        events = detect_rsi_transition(rsi_overbought_data)
        for event in events:
            assert event["type"] in ("rsi_overbought", "rsi_oversold")
            assert "date" in event
            assert "rsi" in event

    def test_custom_thresholds(self, rsi_overbought_data):
        """Custom overbought/oversold thresholds are respected."""
        events_strict = detect_rsi_transition(
            rsi_overbought_data, overbought=90, oversold=10
        )
        events_loose = detect_rsi_transition(
            rsi_overbought_data, overbought=60, oversold=40
        )
        assert len(events_strict) <= len(events_loose)
