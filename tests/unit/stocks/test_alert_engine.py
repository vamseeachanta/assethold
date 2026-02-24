"""
Unit tests for the alert engine.

Tests verify that the engine aggregates events from detectors,
assigns severity correctly, and produces well-formed output.
"""

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from assethold.stocks.alert_engine import (
    AlertEngine,
    AlertEvent,
    Severity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_trend_events():
    """Synthetic trend detection events."""
    return {
        "ma_crossovers": [
            {"type": "golden_cross", "date": datetime(2024, 3, 15), "short_ma": 150.0, "long_ma": 148.0},
        ],
        "sr_breaks": [
            {"type": "resistance_break", "date": datetime(2024, 3, 16), "price": 160.0, "level": 155.0},
        ],
        "volume_spikes": [
            {
                "type": "volume_spike",
                "date": datetime(2024, 3, 17),
                "volume": 5_000_000,
                "mean_volume": 1_000_000,
                "std_multiples": 3.2,
            },
        ],
        "rsi_transitions": [
            {"type": "rsi_overbought", "date": datetime(2024, 3, 18), "rsi": 74.5},
        ],
    }


@pytest.fixture
def sample_insider_flags():
    """Synthetic insider unusual activity flags."""
    return [
        {
            "type": "unusual_insider_activity",
            "owner_name": "Big Buyer",
            "shares": 500_000,
            "transaction_date": date(2024, 3, 15),
            "reason": "large transaction: 8.3 std above mean",
        }
    ]


@pytest.fixture
def engine():
    """AlertEngine with default configuration."""
    return AlertEngine()


# ---------------------------------------------------------------------------
# AlertEvent dataclass
# ---------------------------------------------------------------------------


class TestAlertEvent:
    """Tests for the AlertEvent data structure."""

    def test_create_alert_event(self):
        """AlertEvent can be created with required fields."""
        event = AlertEvent(
            ticker="AAPL",
            event_type="golden_cross",
            severity=Severity.WARNING,
            message="Golden cross detected",
            timestamp=datetime(2024, 3, 15),
            metadata={"short_ma": 150.0},
        )
        assert event.ticker == "AAPL"
        assert event.event_type == "golden_cross"
        assert event.severity == Severity.WARNING

    def test_alert_event_to_dict(self):
        """AlertEvent.to_dict() returns serializable dict."""
        event = AlertEvent(
            ticker="AAPL",
            event_type="volume_spike",
            severity=Severity.CRITICAL,
            message="Extreme volume spike",
            timestamp=datetime(2024, 3, 17),
            metadata={"std_multiples": 5.0},
        )
        d = event.to_dict()
        assert isinstance(d, dict)
        assert d["ticker"] == "AAPL"
        assert d["event_type"] == "volume_spike"
        assert "severity" in d
        assert "message" in d
        assert "timestamp" in d


# ---------------------------------------------------------------------------
# Severity enum
# ---------------------------------------------------------------------------


class TestSeverity:
    """Tests for the Severity enumeration."""

    def test_severity_values_exist(self):
        """INFO, WARNING, CRITICAL all exist."""
        assert Severity.INFO
        assert Severity.WARNING
        assert Severity.CRITICAL

    def test_severity_ordering(self):
        """CRITICAL > WARNING > INFO in value."""
        assert Severity.CRITICAL.value > Severity.WARNING.value
        assert Severity.WARNING.value > Severity.INFO.value


# ---------------------------------------------------------------------------
# AlertEngine.build_alerts
# ---------------------------------------------------------------------------


class TestAlertEngineBuildAlerts:
    """Tests for alert generation from trend and insider events."""

    def test_build_alerts_returns_list(self, engine, sample_trend_events):
        """build_alerts returns a list of AlertEvent."""
        alerts = engine.build_alerts("AAPL", sample_trend_events, [])
        assert isinstance(alerts, list)

    def test_alerts_for_each_event(self, engine, sample_trend_events):
        """One alert is generated per source event."""
        all_events = (
            len(sample_trend_events["ma_crossovers"])
            + len(sample_trend_events["sr_breaks"])
            + len(sample_trend_events["volume_spikes"])
            + len(sample_trend_events["rsi_transitions"])
        )
        alerts = engine.build_alerts("AAPL", sample_trend_events, [])
        assert len(alerts) == all_events

    def test_insider_flags_generate_alerts(self, engine, sample_insider_flags):
        """Insider flags are converted to alerts."""
        alerts = engine.build_alerts("AAPL", {}, sample_insider_flags)
        assert len(alerts) == len(sample_insider_flags)

    def test_volume_spike_large_is_critical(self, engine):
        """Volume spike > 3σ gets CRITICAL severity."""
        trend_events = {
            "ma_crossovers": [],
            "sr_breaks": [],
            "volume_spikes": [
                {
                    "type": "volume_spike",
                    "date": datetime(2024, 3, 17),
                    "volume": 10_000_000,
                    "mean_volume": 1_000_000,
                    "std_multiples": 4.5,
                }
            ],
            "rsi_transitions": [],
        }
        alerts = engine.build_alerts("AAPL", trend_events, [])
        assert any(a.severity == Severity.CRITICAL for a in alerts)

    def test_rsi_overbought_is_warning(self, engine):
        """RSI overbought event maps to WARNING severity."""
        trend_events = {
            "ma_crossovers": [],
            "sr_breaks": [],
            "volume_spikes": [],
            "rsi_transitions": [
                {"type": "rsi_overbought", "date": datetime(2024, 3, 18), "rsi": 74.5}
            ],
        }
        alerts = engine.build_alerts("AAPL", trend_events, [])
        assert any(a.severity == Severity.WARNING for a in alerts)

    def test_golden_cross_is_info(self, engine):
        """Golden cross maps to INFO severity by default."""
        trend_events = {
            "ma_crossovers": [
                {"type": "golden_cross", "date": datetime(2024, 3, 15), "short_ma": 150.0, "long_ma": 148.0}
            ],
            "sr_breaks": [],
            "volume_spikes": [],
            "rsi_transitions": [],
        }
        alerts = engine.build_alerts("AAPL", trend_events, [])
        assert any(a.severity == Severity.INFO for a in alerts)

    def test_all_alerts_have_ticker(self, engine, sample_trend_events, sample_insider_flags):
        """All alerts are tagged with the correct ticker."""
        alerts = engine.build_alerts("XOM", sample_trend_events, sample_insider_flags)
        assert all(a.ticker == "XOM" for a in alerts)

    def test_empty_events_no_alerts(self, engine):
        """No alerts generated for empty event sets."""
        alerts = engine.build_alerts("AAPL", {}, [])
        assert alerts == []


# ---------------------------------------------------------------------------
# AlertEngine.run_watchlist
# ---------------------------------------------------------------------------


class TestAlertEngineRunWatchlist:
    """Tests for full watchlist run producing structured output."""

    def test_run_watchlist_returns_dict(self, engine):
        """run_watchlist returns a dict keyed by ticker."""
        ticker_results = {
            "AAPL": {
                "trend_events": {
                    "ma_crossovers": [],
                    "sr_breaks": [],
                    "volume_spikes": [],
                    "rsi_transitions": [],
                },
                "insider_flags": [],
            }
        }
        result = engine.run_watchlist(ticker_results)
        assert isinstance(result, dict)
        assert "AAPL" in result

    def test_run_watchlist_produces_alert_list(self, engine, sample_trend_events, sample_insider_flags):
        """Each ticker maps to a list of AlertEvent objects."""
        ticker_results = {
            "AAPL": {
                "trend_events": sample_trend_events,
                "insider_flags": sample_insider_flags,
            }
        }
        result = engine.run_watchlist(ticker_results)
        assert isinstance(result["AAPL"], list)
        assert all(isinstance(a, AlertEvent) for a in result["AAPL"])


# ---------------------------------------------------------------------------
# AlertEngine.to_json / write_report
# ---------------------------------------------------------------------------


class TestAlertEngineOutput:
    """Tests for output serialization."""

    def test_to_json_returns_string(self, engine, sample_trend_events):
        """to_json returns a non-empty JSON string."""
        import json

        alerts = engine.build_alerts("AAPL", sample_trend_events, [])
        json_output = engine.to_json(alerts)

        assert isinstance(json_output, str)
        parsed = json.loads(json_output)
        assert isinstance(parsed, list)
        assert len(parsed) == len(alerts)

    def test_write_json_report(self, engine, sample_trend_events, tmp_path):
        """write_json_report writes a valid JSON file."""
        import json

        alerts = engine.build_alerts("AAPL", sample_trend_events, [])
        out_path = tmp_path / "alerts.json"
        engine.write_json_report(alerts, out_path)

        assert out_path.exists()
        with open(out_path) as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_write_markdown_report(self, engine, sample_trend_events, tmp_path):
        """write_markdown_report writes a non-empty markdown file."""
        alerts = engine.build_alerts("AAPL", sample_trend_events, [])
        out_path = tmp_path / "report.md"
        engine.write_markdown_report(alerts, out_path)

        assert out_path.exists()
        content = out_path.read_text()
        assert len(content) > 0
        assert "AAPL" in content
