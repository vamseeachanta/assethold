"""ABOUTME: Thin orchestrator that drives market-hours-aware signals across a watchlist.
ABOUTME: Owns a single StockDataSource, runs TrendDetector+AlertEngine per ticker, and
exposes a --intraday/--no-intraday/--lookback-days/--render-charts CLI."""

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from assethold.signals import dashboard
from assethold.signals.alert_engine import AlertEngine, AlertEvent
from assethold.signals.data_sources import StockDataSource
from assethold.signals.trend_detector import TrendDetector
from assethold.signals.watchlist import Watchlist

logger = logging.getLogger(__name__)


class WatchlistRunner:
    """Drive market-hours-aware signals analysis across a configured watchlist.

    Plumbs Phase 1's market_hours_aware / intraday_ttl_minutes kwargs through a
    single StockDataSource and runs the trend-detector + alert-engine pipeline
    per ticker. See docs/reports/2026-04-17-issue-39-market-hours-signals-
    consumers-plan.md for the design rationale and adversarial review history.
    """

    def __init__(
        self,
        watchlist: Watchlist,
        market_hours_aware: bool = False,
        intraday_ttl_minutes: int = 15,
        lookback_days: int = 90,
        cache_ttl_hours: int = 24,
        cache_dir: Optional[Path] = None,
        insider_flags_provider: Optional[Callable[[str], list[dict]]] = None,
        render_charts: bool = False,
        charts_output_dir: Optional[Path] = None,
        now: Callable[[], date] = date.today,
    ):
        if render_charts and charts_output_dir is None:
            raise ValueError(
                "render_charts=True requires charts_output_dir to be set"
            )

        self._watchlist = watchlist
        self._lookback_days = lookback_days
        self._render_charts = render_charts
        self._charts_output_dir = charts_output_dir
        self._insider_flags_provider = insider_flags_provider
        self._now = now

        self._source = StockDataSource(
            cache_dir=cache_dir,
            cache_ttl_hours=cache_ttl_hours,
            market_hours_aware=market_hours_aware,
            intraday_ttl_minutes=intraday_ttl_minutes,
        )
        self._detector = TrendDetector()
        self._engine = AlertEngine()

        if insider_flags_provider is None:
            logger.warning(
                "WatchlistRunner: insider_flags_provider not set; "
                "CRITICAL-severity unusual_insider_activity alerts will "
                "not fire for any ticker this run."
            )

    def _date_range(self) -> tuple[str, str]:
        end = self._now()
        start = end - timedelta(days=self._lookback_days)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    def run(self) -> dict[str, list[AlertEvent]]:
        start_date, end_date = self._date_range()
        if self._render_charts:
            self._charts_output_dir.mkdir(parents=True, exist_ok=True)

        results: dict[str, list[AlertEvent]] = {}
        for ticker in self._watchlist.get_tickers():
            df = self._source.fetch(ticker, start_date, end_date)
            if df is None or df.empty:
                results[ticker] = []
                continue

            trend_events = self._detector.analyze(df)
            insider_flags = (
                self._insider_flags_provider(ticker)
                if self._insider_flags_provider is not None
                else []
            )
            alerts = self._engine.build_alerts(ticker, trend_events, insider_flags)
            results[ticker] = alerts

            if self._render_charts:
                fig = dashboard.build_price_chart(df, ticker)
                dashboard.save_chart(
                    fig, self._charts_output_dir / f"{ticker}.html"
                )

        return results


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="watchlist_runner",
        description=(
            "Run trend detection + alert generation across the configured "
            "watchlist with optional market-hours-aware intraday freshness."
        ),
    )
    parser.add_argument(
        "--intraday",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Enable market-hours-aware intraday freshness (sub-15-min TTL "
            "during NYSE regular session). --no-intraday forces off even if "
            "the config enables it."
        ),
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Days of OHLCV history to fetch per ticker (overrides config).",
    )
    parser.add_argument(
        "--render-charts",
        action="store_true",
        help="Render a per-ticker price chart as HTML. Requires --charts-dir.",
    )
    parser.add_argument(
        "--charts-dir",
        type=str,
        default=None,
        help="Output directory for rendered charts (required with --render-charts).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    watchlist = Watchlist()
    config: dict[str, Any] = watchlist.load()
    settings: dict[str, Any] = config.get("settings", {}) or {}

    if args.intraday is not None:
        market_hours_aware = bool(args.intraday)
    else:
        market_hours_aware = bool(settings.get("market_hours_aware", False))

    if market_hours_aware:
        from assethold.utils.market_hours import is_market_open, next_open

        if not is_market_open():
            print(
                f"--intraday requires NYSE regular session open. "
                f"Next open: {next_open()}",
                file=sys.stderr,
            )
            print(
                "Note: --intraday is a wall-clock pre-flight; it is "
                "independent of --lookback-days, which controls the "
                "historical date range.",
                file=sys.stderr,
            )
            return 1

    if args.render_charts and args.charts_dir is None:
        print(
            "--render-charts requires --charts-dir PATH",
            file=sys.stderr,
        )
        return 2

    runner = WatchlistRunner(
        watchlist=watchlist,
        market_hours_aware=market_hours_aware,
        intraday_ttl_minutes=int(settings.get("intraday_ttl_minutes", 15)),
        lookback_days=(
            int(args.lookback_days)
            if args.lookback_days is not None
            else int(settings.get("lookback_days", 90))
        ),
        cache_ttl_hours=int(settings.get("cache_ttl_hours", 24)),
        render_charts=args.render_charts,
        charts_output_dir=(
            Path(args.charts_dir) if args.charts_dir else None
        ),
    )
    results = runner.run()
    _print_summary(results)
    return 0


def _print_summary(results: dict[str, list[AlertEvent]]) -> None:
    for ticker, alerts in sorted(results.items()):
        print(f"{ticker}: {len(alerts)} alert(s)")


if __name__ == "__main__":
    sys.exit(main())
