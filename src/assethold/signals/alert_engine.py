"""
Alert engine for stock monitoring events.

Aggregates trend detector and insider tracker outputs, assigns severity,
and produces JSON and Markdown report outputs.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any


class Severity(IntEnum):
    """Alert severity levels ordered by importance."""

    INFO = 1
    WARNING = 2
    CRITICAL = 3


# Default severity mapping: event type → severity
_DEFAULT_SEVERITY: dict[str, Severity] = {
    "golden_cross": Severity.INFO,
    "death_cross": Severity.WARNING,
    "resistance_break": Severity.INFO,
    "support_break": Severity.WARNING,
    "volume_spike": Severity.WARNING,
    "rsi_overbought": Severity.WARNING,
    "rsi_oversold": Severity.WARNING,
    "unusual_insider_activity": Severity.CRITICAL,
}

# Volume spikes above this std multiple are upgraded to CRITICAL
_VOLUME_CRITICAL_STD = 3.0


@dataclass
class AlertEvent:
    """A single alert event for a ticker."""

    ticker: str
    event_type: str
    severity: Severity
    message: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        return {
            "ticker": self.ticker,
            "event_type": self.event_type,
            "severity": self.severity.name,
            "message": self.message,
            "timestamp": self.timestamp.isoformat()
            if isinstance(self.timestamp, datetime)
            else str(self.timestamp),
            "metadata": self.metadata,
        }


def _coerce_timestamp(value: Any) -> datetime:
    """Convert pandas Timestamp, date, or datetime to datetime."""
    if isinstance(value, datetime):
        return value
    try:
        import pandas as pd

        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()
    except ImportError:
        pass
    try:
        from datetime import date

        if isinstance(value, date):
            return datetime(value.year, value.month, value.day)
    except Exception:
        pass
    return datetime.now()


def _build_message(event_type: str, metadata: dict[str, Any]) -> str:
    """Produce a human-readable message for an event."""
    templates: dict[str, str] = {
        "golden_cross": (
            "Golden cross: short MA {short_ma:.2f} crossed above "
            "long MA {long_ma:.2f}"
        ),
        "death_cross": (
            "Death cross: short MA {short_ma:.2f} crossed below "
            "long MA {long_ma:.2f}"
        ),
        "resistance_break": (
            "Resistance break: price {price:.2f} exceeded level {level:.2f}"
        ),
        "support_break": (
            "Support break: price {price:.2f} fell below level {level:.2f}"
        ),
        "volume_spike": (
            "Volume spike: {volume:,.0f} volume ({std_multiples:.1f}σ "
            "above mean {mean_volume:,.0f})"
        ),
        "rsi_overbought": "RSI overbought: RSI = {rsi:.1f} (threshold crossed)",
        "rsi_oversold": "RSI oversold: RSI = {rsi:.1f} (threshold crossed)",
        "unusual_insider_activity": "Unusual insider activity: {reason}",
    }
    template = templates.get(event_type, f"Event: {event_type}")
    try:
        return template.format(**metadata)
    except (KeyError, ValueError):
        return f"Event: {event_type}"


def _severity_for_event(
    event_type: str, metadata: dict[str, Any]
) -> Severity:
    """Determine severity for an event, with override for large volume spikes."""
    base = _DEFAULT_SEVERITY.get(event_type, Severity.INFO)
    if event_type == "volume_spike":
        std_multiples = metadata.get("std_multiples", 0.0)
        if std_multiples >= _VOLUME_CRITICAL_STD:
            return Severity.CRITICAL
    return base


class AlertEngine:
    """
    Converts detected events into structured alerts and reports.

    Usage::

        engine = AlertEngine()
        alerts = engine.build_alerts("AAPL", trend_events, insider_flags)
        engine.write_json_report(alerts, Path("alerts.json"))
        engine.write_markdown_report(alerts, Path("report.md"))
    """

    def build_alerts(
        self,
        ticker: str,
        trend_events: dict[str, list[dict[str, Any]]],
        insider_flags: list[dict[str, Any]],
    ) -> list[AlertEvent]:
        """
        Build a list of AlertEvent objects from detector outputs.

        Args:
            ticker: Stock ticker symbol
            trend_events: Output from TrendDetector.analyze()
            insider_flags: Output from flag_unusual_activity()

        Returns:
            List of AlertEvent objects
        """
        alerts: list[AlertEvent] = []

        # Trend events from each category
        category_to_events: dict[str, list[dict[str, Any]]] = {
            "ma_crossovers": [],
            "sr_breaks": [],
            "volume_spikes": [],
            "rsi_transitions": [],
        }
        category_to_events.update(trend_events)

        for category, events in category_to_events.items():
            for evt in events:
                event_type = evt.get("type", category)
                timestamp = _coerce_timestamp(evt.get("date", datetime.now()))
                metadata = {
                    k: v for k, v in evt.items() if k not in ("type", "date")
                }
                severity = _severity_for_event(event_type, metadata)
                message = _build_message(event_type, metadata)

                alerts.append(
                    AlertEvent(
                        ticker=ticker,
                        event_type=event_type,
                        severity=severity,
                        message=message,
                        timestamp=timestamp,
                        metadata=metadata,
                    )
                )

        # Insider flags
        for flag in insider_flags:
            event_type = flag.get("type", "unusual_insider_activity")
            timestamp = _coerce_timestamp(
                flag.get("transaction_date", datetime.now())
            )
            metadata = {
                k: v
                for k, v in flag.items()
                if k not in ("type", "transaction_date")
            }
            metadata["transaction_date"] = str(flag.get("transaction_date", ""))
            severity = _severity_for_event(event_type, metadata)
            message = _build_message(event_type, metadata)

            alerts.append(
                AlertEvent(
                    ticker=ticker,
                    event_type=event_type,
                    severity=severity,
                    message=message,
                    timestamp=timestamp,
                    metadata=metadata,
                )
            )

        return alerts

    def run_watchlist(
        self,
        ticker_results: dict[str, dict[str, Any]],
    ) -> dict[str, list[AlertEvent]]:
        """
        Run alert generation across a full watchlist result set.

        Args:
            ticker_results: Dict mapping ticker to dict with keys
                'trend_events' and 'insider_flags'

        Returns:
            Dict mapping ticker to list of AlertEvent
        """
        output: dict[str, list[AlertEvent]] = {}
        for ticker, data in ticker_results.items():
            trend_events = data.get("trend_events", {})
            insider_flags = data.get("insider_flags", [])
            output[ticker] = self.build_alerts(ticker, trend_events, insider_flags)
        return output

    def to_json(self, alerts: list[AlertEvent]) -> str:
        """
        Serialize a list of AlertEvent to a JSON string.

        Args:
            alerts: List of AlertEvent objects

        Returns:
            JSON-formatted string
        """
        return json.dumps(
            [a.to_dict() for a in alerts],
            indent=2,
            default=str,
        )

    def write_json_report(
        self, alerts: list[AlertEvent], output_path: Path
    ) -> None:
        """
        Write alerts as a JSON file.

        Args:
            alerts: List of AlertEvent objects
            output_path: Destination file path
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(self.to_json(alerts))

    def write_markdown_report(
        self, alerts: list[AlertEvent], output_path: Path
    ) -> None:
        """
        Write a summary Markdown report of alerts.

        Args:
            alerts: List of AlertEvent objects
            output_path: Destination file path
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = ["# Stock Alert Report\n"]

        if not alerts:
            lines.append("No alerts generated.\n")
        else:
            # Group by ticker
            by_ticker: dict[str, list[AlertEvent]] = {}
            for alert in alerts:
                by_ticker.setdefault(alert.ticker, []).append(alert)

            for ticker, ticker_alerts in sorted(by_ticker.items()):
                lines.append(f"## {ticker}\n")
                for a in sorted(ticker_alerts, key=lambda x: x.severity, reverse=True):
                    lines.append(
                        f"- **[{a.severity.name}]** `{a.event_type}` "
                        f"({a.timestamp}): {a.message}"
                    )
                lines.append("")

        with open(output_path, "w") as f:
            f.write("\n".join(lines))
