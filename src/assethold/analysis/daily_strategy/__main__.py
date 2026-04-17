"""
CLI entry point for the daily portfolio strategy.

Usage:
    uv run python -m assethold.analysis.daily_strategy [options]

Options:
    --accounts {all,individual,ira}   Filter to a specific account type (default: all)
    --date YYYY-MM-DD                 Override today's date for the report
    --no-cache                        Bypass market data cache
    --no-write                        Print to terminal only; do not write report files
    --config PATH                     Path to daily_strategy.yaml (default: config/daily_strategy.yaml)
    --compare TICKER[,TICKER...]      Analyse arbitrary tickers alongside portfolio positions.
                                      Tickers are comma-separated (e.g. AAPL,MSFT,NVDA).
                                      When omitted, the watchlist: section in config is used
                                      automatically if non-empty.
    --intraday                        Enable market-hours-aware caching: OHLCV TTL drops to
                                      `intraday_ttl_minutes` (config knob, default 15) during
                                      the NYSE regular session. Fails loud if the market is
                                      closed at invocation time. The --date flag overrides the
                                      report date but NOT the pre-flight check.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m assethold.analysis.daily_strategy",
        description="Generate daily build/hold/trim strategy for long-term portfolio positions.",
    )
    parser.add_argument(
        "--accounts",
        choices=["all", "individual", "ira"],
        default="all",
        help="Filter positions to a specific account type (default: all)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Override today's date for the report (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass market data cache and fetch fresh data",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print to terminal only; do not write report files",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to daily_strategy.yaml (default: config/daily_strategy.yaml)",
    )
    parser.add_argument(
        "--compare",
        type=str,
        default=None,
        metavar="TICKER[,TICKER...]",
        help=(
            "Comma-separated list of tickers to analyse in comparison mode. "
            "When provided, these tickers are added as synthetic 'Watchlist' positions "
            "and the HTML report switches to Comparison Matrix layout."
        ),
    )
    parser.add_argument(
        "--intraday",
        action="store_true",
        help=(
            "Enable market-hours-aware caching. OHLCV TTL drops to the configured "
            "intraday_ttl_minutes during the NYSE regular session. Fails loud if "
            "the market is closed at invocation time."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    # --intraday pre-flight: fail loud if NYSE regular session is not open NOW
    # (independent of --date, which only controls the report date).
    if args.intraday:
        from assethold.utils.market_hours import is_market_open, next_open
        if not is_market_open():
            try:
                next_open_ts = next_open()
                next_open_str = next_open_ts.strftime("%Y-%m-%d %H:%M %Z")
            except ValueError:
                next_open_str = "unknown"
            print(
                f"ERROR: market is closed. Next open: {next_open_str}",
                file=sys.stderr,
            )
            return 1

    # Parse the report date
    report_date: datetime | None = None
    if args.date:
        try:
            report_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(f"ERROR: Invalid date format '{args.date}'. Use YYYY-MM-DD.", file=sys.stderr)
            return 1

    # Load config
    from assethold.analysis.daily_strategy.loader import _load_yaml, _default_config_path

    config_path = Path(args.config) if args.config else _default_config_path()
    config = _load_yaml(config_path)

    # Load positions from Fidelity CSVs
    from assethold.analysis.daily_strategy.loader import FidelityLoader, ComparisonLoader

    loader = FidelityLoader(config_path=config_path)
    try:
        positions = loader.load()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            "Set FIDELITY_DATA_DIR or update loader.data_dir in config/daily_strategy.yaml.",
            file=sys.stderr,
        )
        return 1

    if not positions:
        print("No positions found in Fidelity data.", file=sys.stderr)
        return 0

    # Account filter
    filter_map = {
        "individual": "individual - tod",
        "ira": "traditional ira",
    }
    if args.accounts != "all":
        keyword = filter_map[args.accounts]
        positions = [p for p in positions if keyword in p.account.lower()]

    # --compare flag / watchlist config
    comparison_mode = False
    compare_tickers: list[str] = []

    if args.compare:
        compare_tickers = [t.strip().upper() for t in args.compare.split(",") if t.strip()]
    elif config.get("watchlist"):
        compare_tickers = [t.upper() for t in config["watchlist"] if t]

    if compare_tickers:
        comparison_mode = True
        comp_loader = ComparisonLoader()
        watchlist_positions = comp_loader.load_tickers(compare_tickers)
        # Merge: keep existing portfolio positions + add watchlist synthetics
        existing_tickers = {p.ticker for p in positions}
        for wp in watchlist_positions:
            if wp.ticker not in existing_tickers:
                positions.append(wp)
        print(f"Comparison mode: added {len(watchlist_positions)} watchlist ticker(s): "
              f"{', '.join(compare_tickers)}")

    tradeable = [p for p in positions if p.tradeable]
    tickers = list({p.ticker for p in tradeable})

    # Ticker alias map: Fidelity symbol → Yahoo Finance symbol
    raw_aliases = config.get("ticker_aliases", {})
    alias_map = {k.upper(): v.upper() for k, v in raw_aliases.items()}
    reverse_alias = {v: k for k, v in alias_map.items()}

    print(f"Loaded {len(positions)} positions ({len(tradeable)} tradeable) across {len(tickers)} tickers.")

    # Fetch market data
    from assethold.analysis.daily_strategy.fetcher import MarketDataFetcher

    fetcher = MarketDataFetcher(
        price_cache_ttl_hours=0 if args.no_cache else int(
            config.get("scoring", {}).get("price_cache_ttl_hours", 4)
        ),
        info_cache_ttl_hours=0 if args.no_cache else int(
            config.get("scoring", {}).get("info_cache_ttl_hours", 24)
        ),
        history_days=int(config.get("scoring", {}).get("sma_history_days", 252)),
        market_hours_aware=args.intraday,
        intraday_ttl_minutes=int(
            config.get("scoring", {}).get("intraday_ttl_minutes", 15)
        ),
    )

    fetch_tickers = [alias_map.get(t, t) for t in tickers]
    print(f"Fetching market data for: {', '.join(fetch_tickers)} ...")
    snapshots_raw = fetcher.fetch_batch(fetch_tickers)
    # Re-key snapshots back to Fidelity tickers
    snapshots = {reverse_alias.get(t, t): s for t, s in snapshots_raw.items()}

    failed = [t for t, s in snapshots.items() if s is None]
    if failed:
        print(f"WARNING: Could not fetch data for: {', '.join(failed)}", file=sys.stderr)

    # Score positions
    from assethold.analysis.daily_strategy.signals import SignalEngine

    engine = SignalEngine(config)
    # Portfolio value excludes synthetic watchlist shares (shares=0)
    total_value = sum(
        p.shares * snapshots[p.ticker].current_price
        for p in tradeable
        if snapshots.get(p.ticker) is not None and p.shares > 0
    )
    signals = engine.score_batch(positions, snapshots, portfolio_value=total_value)

    # Sector exposure tracker
    from assethold.portfolio.sector_tracker import SectorTracker

    sector_tracker = SectorTracker()
    holdings_by_value: dict[str, float] = {}
    for p in tradeable:
        snap = snapshots.get(p.ticker)
        if snap is not None and p.shares > 0:
            holdings_by_value[p.ticker] = p.shares * snap.current_price

    sector_breakdown = sector_tracker.build_breakdown(holdings_by_value)
    print(sector_tracker.format_table(sector_breakdown))

    # Signal history: detect changes vs prior day
    from assethold.analysis.daily_strategy.history import HistoryStore

    history = HistoryStore()
    report_date_obj = report_date.date() if report_date else None
    changes = history.changes(signals, report_date=report_date_obj)
    if changes:
        print("\nSignal changes since last run:")
        for change in changes:
            print(f"  {change.format()}")

    # Record today's signals (only when writing the report)
    if not args.no_write:
        history.record(signals, report_date=report_date_obj)

    # Render Markdown report
    from assethold.analysis.daily_strategy.report import DailyStrategyReport

    reporter = DailyStrategyReport()
    reporter.print_summary(signals, total_value)

    if not args.no_write:
        md_path = reporter.write(
            signals,
            report_date=report_date,
            changes=changes,
            sector_breakdown=sector_breakdown,
        )
        print(f"\nMarkdown report: {md_path}")

        # Render HTML report (primary output)
        from assethold.analysis.daily_strategy.html_report import DailyStrategyHtmlReport

        html_reporter = DailyStrategyHtmlReport()
        html_path = html_reporter.write(
            signals,
            report_date=report_date,
            changes=changes,
            comparison_mode=comparison_mode,
        )
        print(f"HTML report:     {html_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
