"""Daily portfolio strategy analysis."""

from assethold.analysis.daily_strategy.loader import FidelityLoader, ComparisonLoader, Position
from assethold.analysis.daily_strategy.fetcher import MarketDataFetcher, MarketSnapshot
from assethold.analysis.daily_strategy.signals import SignalEngine, PositionSignal
from assethold.analysis.daily_strategy.report import DailyStrategyReport
from assethold.analysis.daily_strategy.html_report import DailyStrategyHtmlReport
from assethold.analysis.daily_strategy.history import HistoryStore, SignalRecord, SignalChange
from assethold.analysis.daily_strategy.tax_lots import (
    TaxLot,
    LotAging,
    RealizedLot,
    YearlyRealizedSummary,
    age_lots,
    almost_long_term_lots,
    select_trim_lots,
    match_sells_fifo,
    realized_report,
)

__all__ = [
    "FidelityLoader",
    "ComparisonLoader",
    "Position",
    "MarketDataFetcher",
    "MarketSnapshot",
    "SignalEngine",
    "PositionSignal",
    "DailyStrategyReport",
    "DailyStrategyHtmlReport",
    "HistoryStore",
    "SignalRecord",
    "SignalChange",
    "TaxLot",
    "LotAging",
    "RealizedLot",
    "YearlyRealizedSummary",
    "age_lots",
    "almost_long_term_lots",
    "select_trim_lots",
    "match_sells_fifo",
    "realized_report",
]
