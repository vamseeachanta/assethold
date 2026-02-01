"""Unit tests for StockAnalysis breakout analysis logic.

Tests breakout condition checks with synthetic data -- no API calls,
no file I/O, no external dependencies.  Uses a fixed random seed for
deterministic, reproducible results.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock

from assethold.modules.stocks.stock_analysis import StockAnalysis
from assethold.modules.stocks.stocks import Stocks

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Fixed seed for determinism
# ---------------------------------------------------------------------------
_RNG = np.random.RandomState(42)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def stock_analysis():
    """StockAnalysis with no external deps needed for breakout checks."""
    return StockAnalysis(cfg=None)


@pytest.fixture
def bullish_data():
    """DataFrame where all breakout conditions are True.

    Price > 50-day > 150-day > 200-day moving averages, all trending up.
    """
    rng = np.random.RandomState(42)
    dates = pd.date_range(end=datetime.now(), periods=250, freq="D")
    # Steady uptrend: base 100 rising ~0.5/day with small noise
    close = 100 + np.arange(250) * 0.5 + rng.normal(0, 1, 250)
    df = pd.DataFrame({"Date": dates, "Close": close})
    df["50_day_rolling"] = df["Close"].rolling(50).mean()
    df["150_day_rolling"] = df["Close"].rolling(150).mean()
    df["200_day_rolling"] = df["Close"].rolling(200).mean()
    return df


@pytest.fixture
def bearish_data():
    """DataFrame where breakout conditions are False.

    Price < 50-day < 150-day < 200-day moving averages, trending down.
    """
    rng = np.random.RandomState(42)
    dates = pd.date_range(end=datetime.now(), periods=250, freq="D")
    # Steady downtrend: base 200 falling ~0.5/day with small noise
    close = 200 - np.arange(250) * 0.5 + rng.normal(0, 1, 250)
    df = pd.DataFrame({"Date": dates, "Close": close})
    df["50_day_rolling"] = df["Close"].rolling(50).mean()
    df["150_day_rolling"] = df["Close"].rolling(150).mean()
    df["200_day_rolling"] = df["Close"].rolling(200).mean()
    return df


# ---------------------------------------------------------------------------
# check_if_price_above_150_and_200_moving
# ---------------------------------------------------------------------------
class TestPriceAbove150And200:

    def test_price_above_150_and_200_bullish(self, stock_analysis, bullish_data):
        result = stock_analysis.check_if_price_above_150_and_200_moving(bullish_data)
        description, value = result
        assert bool(value) is True

    def test_price_above_150_and_200_bearish(self, stock_analysis, bearish_data):
        result = stock_analysis.check_if_price_above_150_and_200_moving(bearish_data)
        description, value = result
        assert bool(value) is False


# ---------------------------------------------------------------------------
# check_if_150_moving_above_200_moving
# ---------------------------------------------------------------------------
class TestMA150Above200:

    def test_150_above_200_bullish(self, stock_analysis, bullish_data):
        result = stock_analysis.check_if_150_moving_above_200_moving(bullish_data)
        description, value = result
        assert bool(value) is True

    def test_150_above_200_bearish(self, stock_analysis, bearish_data):
        result = stock_analysis.check_if_150_moving_above_200_moving(bearish_data)
        description, value = result
        assert bool(value) is False


# ---------------------------------------------------------------------------
# check_if_50_day_above_150_and_200_moving
# ---------------------------------------------------------------------------
class TestMA50Above150And200:

    def test_50_above_150_and_200_bullish(self, stock_analysis, bullish_data):
        result = stock_analysis.check_if_50_day_above_150_and_200_moving(bullish_data)
        description, value = result
        assert bool(value) is True

    def test_50_above_150_and_200_bearish(self, stock_analysis, bearish_data):
        result = stock_analysis.check_if_50_day_above_150_and_200_moving(bearish_data)
        description, value = result
        assert bool(value) is False


# ---------------------------------------------------------------------------
# check_if_price_above_50_moving
# ---------------------------------------------------------------------------
class TestPriceAbove50:

    def test_price_above_50_bullish(self, stock_analysis, bullish_data):
        result = stock_analysis.check_if_price_above_50_moving(bullish_data)
        description, value_str = result
        assert "True" in str(value_str)

    def test_price_above_50_bearish(self, stock_analysis, bearish_data):
        result = stock_analysis.check_if_price_above_50_moving(bearish_data)
        description, value_str = result
        assert "False" in str(value_str)


# ---------------------------------------------------------------------------
# Return format validation
# ---------------------------------------------------------------------------
class TestBreakoutReturnFormat:

    def test_breakout_returns_correct_format(self, stock_analysis, bullish_data):
        """Each breakout check returns a [str, value] pair."""
        checks = [
            stock_analysis.check_if_price_above_150_and_200_moving(bullish_data),
            stock_analysis.check_if_150_moving_above_200_moving(bullish_data),
            stock_analysis.check_if_50_day_above_150_and_200_moving(bullish_data),
            stock_analysis.check_if_price_above_50_moving(bullish_data),
        ]
        for result in checks:
            assert isinstance(result, list), "Result should be a list"
            assert len(result) == 2, "Result should have exactly 2 elements"
            assert isinstance(result[0], str), "First element should be a description string"

    def test_description_strings_are_non_empty(self, stock_analysis, bullish_data):
        """Descriptions returned by each check are meaningful, non-empty strings."""
        checks = [
            stock_analysis.check_if_price_above_150_and_200_moving(bullish_data),
            stock_analysis.check_if_150_moving_above_200_moving(bullish_data),
            stock_analysis.check_if_50_day_above_150_and_200_moving(bullish_data),
            stock_analysis.check_if_price_above_50_moving(bullish_data),
        ]
        for result in checks:
            assert len(result[0].strip()) > 0


# ---------------------------------------------------------------------------
# Stocks DI / constructor
# ---------------------------------------------------------------------------
class TestStocksDI:

    def test_stocks_di_accepts_mock_dependencies(self):
        """Stocks can be created with mock data_provider and analyzer."""
        mock_provider = Mock()
        mock_analyzer = Mock()
        stocks = Stocks(data_provider=mock_provider, analyzer=mock_analyzer)
        assert stocks.data_provider is mock_provider
        assert stocks.analyzer is mock_analyzer

    def test_stocks_defaults_when_no_args(self):
        """Stocks creates default data_provider and analyzer when none given."""
        stocks = Stocks()
        assert stocks.data_provider is not None
        assert stocks.analyzer is not None
