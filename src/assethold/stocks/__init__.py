"""
Stock analysis module for portfolio monitoring.

Provides data acquisition, technical indicators, and watchlist management.
"""

from assethold.stocks.data_sources import StockDataSource
from assethold.stocks.indicators import (
    calculate_sma,
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_obv,
)
from assethold.stocks.watchlist import Watchlist

__all__ = [
    "StockDataSource",
    "Watchlist",
    "calculate_sma",
    "calculate_ema",
    "calculate_rsi",
    "calculate_macd",
    "calculate_bollinger_bands",
    "calculate_obv",
]
