"""
Realtime signal generation for portfolio monitoring.

Provides lightweight data acquisition, technical indicators, trend detection,
insider tracking, alerting, and watchlist management. Complements
`assethold.modules.stocks`, which handles cached batch analysis.
"""

from assethold.signals.alert_engine import AlertEngine, AlertEvent, Severity
from assethold.signals.dashboard import (
    build_insider_timeline,
    build_macd_chart,
    build_price_chart,
    build_rsi_chart,
    save_chart,
)
from assethold.signals.data_sources import StockDataSource
from assethold.signals.indicators import (
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_obv,
    calculate_rsi,
    calculate_sma,
)
from assethold.signals.insider_tracker import (
    InsiderTracker,
    compute_insider_benchmarks,
    flag_unusual_activity,
    parse_form4_xml,
)
from assethold.signals.trend_detector import (
    TrendDetector,
    detect_ma_crossover,
    detect_rsi_transition,
    detect_support_resistance_break,
    detect_volume_spike,
)
from assethold.signals.watchlist import Watchlist

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
