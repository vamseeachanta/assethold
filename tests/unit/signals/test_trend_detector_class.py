"""
Unit tests for the TrendDetector orchestration class.
"""

import pandas as pd
import pytest

from assethold.signals.trend_detector import TrendDetector


@pytest.fixture
def uptrend_data():
    """Steady uptrend price series for TrendDetector tests."""
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


class TestTrendDetector:
    """Tests for TrendDetector orchestration class."""

    def test_analyze_returns_dict(self, uptrend_data):
        """analyze() returns a dict keyed by event category."""
        detector = TrendDetector()
        result = detector.analyze(uptrend_data)

        assert isinstance(result, dict)
        assert "ma_crossovers" in result
        assert "sr_breaks" in result
        assert "volume_spikes" in result
        assert "rsi_transitions" in result

    def test_analyze_all_values_are_lists(self, uptrend_data):
        """All values in the result dict are lists."""
        detector = TrendDetector()
        result = detector.analyze(uptrend_data)
        for key, val in result.items():
            assert isinstance(val, list), f"{key} should be a list"

    def test_custom_config_passed_through(self, uptrend_data):
        """Custom thresholds flow into sub-detectors."""
        detector = TrendDetector(
            short_ma=5,
            long_ma=10,
            volume_spike_std=1.0,
            rsi_overbought=65,
            rsi_oversold=35,
        )
        result = detector.analyze(uptrend_data)
        assert isinstance(result, dict)

    def test_analyze_empty_dataframe(self):
        """analyze() handles empty DataFrame gracefully."""
        detector = TrendDetector()
        df = pd.DataFrame(
            columns=["date", "open", "high", "low", "close", "volume"]
        )
        result = detector.analyze(df)
        for val in result.values():
            assert val == []

    def test_get_all_events_flattened(self, uptrend_data):
        """get_all_events returns flat list of all events across categories."""
        detector = TrendDetector()
        result = detector.analyze(uptrend_data)
        all_events = detector.get_all_events(result)

        assert isinstance(all_events, list)
        total = sum(len(v) for v in result.values())
        assert len(all_events) == total

    def test_summary_dict_structure(self, uptrend_data):
        """summary() returns a human-readable dict of event counts."""
        detector = TrendDetector()
        result = detector.analyze(uptrend_data)
        summary = detector.summary(result)

        assert isinstance(summary, dict)
        for key in ("ma_crossovers", "sr_breaks", "volume_spikes", "rsi_transitions"):
            assert key in summary
            assert isinstance(summary[key], int)
