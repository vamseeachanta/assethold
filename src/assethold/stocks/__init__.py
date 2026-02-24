"""
Stock analysis module for portfolio monitoring.

Provides data acquisition, technical indicators, trend detection,
insider tracking, alerting, and watchlist management.
"""

from assethold.stocks.alert_engine import AlertEngine, AlertEvent, Severity
from assethold.stocks.dashboard import (
    build_insider_timeline,
    build_macd_chart,
    build_price_chart,
    build_rsi_chart,
    save_chart,
)
from assethold.stocks.data_sources import StockDataSource
from assethold.stocks.indicators import (
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_obv,
    calculate_rsi,
    calculate_sma,
)
from assethold.stocks.insider_tracker import (
    InsiderTracker,
    compute_insider_benchmarks,
    flag_unusual_activity,
    parse_form4_xml,
)
from assethold.stocks.trend_detector import (
    TrendDetector,
    detect_ma_crossover,
    detect_rsi_transition,
    detect_support_resistance_break,
    detect_volume_spike,
)
from assethold.stocks.watchlist import Watchlist

__all__ = [
    "AlertEngine",
    "AlertEvent",
    "Severity",
    "StockDataSource",
    "Watchlist",
    "TrendDetector",
    "InsiderTracker",
    "calculate_bollinger_bands",
    "calculate_ema",
    "calculate_macd",
    "calculate_obv",
    "calculate_rsi",
    "calculate_sma",
    "build_insider_timeline",
    "build_macd_chart",
    "build_price_chart",
    "build_rsi_chart",
    "save_chart",
    "compute_insider_benchmarks",
    "detect_ma_crossover",
    "detect_rsi_transition",
    "detect_support_resistance_break",
    "detect_volume_spike",
    "flag_unusual_activity",
    "parse_form4_xml",
]
