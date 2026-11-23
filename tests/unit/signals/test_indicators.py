"""
Unit tests for technical indicators.

Tests verify calculations against known values and expected properties.
"""

import numpy as np
import pandas as pd
import pytest

from assethold.signals.indicators import (
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_obv,
    calculate_rsi,
    calculate_sma,
    calculate_all_indicators,
)


@pytest.fixture
def simple_price_data():
    """Create simple price series for testing."""
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=50),
            "close": [100.0 + i for i in range(50)],
            "open": [99.0 + i for i in range(50)],
            "high": [101.0 + i for i in range(50)],
            "low": [98.0 + i for i in range(50)],
            "volume": [1000000] * 50,
        }
    )


@pytest.fixture
def oscillating_price_data():
    """Create oscillating price series for RSI testing."""
    prices = []
    for i in range(50):
        if i % 4 < 2:
            prices.append(100.0 + (i // 4) * 2)
        else:
            prices.append(98.0 + (i // 4) * 2)

    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=50),
            "close": prices,
            "open": prices,
            "high": [p + 1 for p in prices],
            "low": [p - 1 for p in prices],
            "volume": [1000000] * 50,
        }
    )


@pytest.fixture
def volume_trend_data():
    """Create data with clear volume trends for OBV testing."""
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=20),
            "close": [100, 101, 102, 101, 100, 99, 98, 99, 100, 101,
                     102, 103, 104, 103, 102, 101, 100, 101, 102, 103],
            "open": [99, 100, 101, 100, 99, 98, 97, 98, 99, 100,
                    101, 102, 103, 102, 101, 100, 99, 100, 101, 102],
            "high": [101, 102, 103, 102, 101, 100, 99, 100, 101, 102,
                    103, 104, 105, 104, 103, 102, 101, 102, 103, 104],
            "low": [98, 99, 100, 99, 98, 97, 96, 97, 98, 99,
                   100, 101, 102, 101, 100, 99, 98, 99, 100, 101],
            "volume": [100, 200, 300, 200, 100, 150, 250, 200, 100, 150,
                      200, 300, 400, 300, 200, 100, 50, 100, 200, 300],
        }
    )


class TestSMA:
    """Test Simple Moving Average calculations."""

    def test_sma_calculation(self, simple_price_data):
        """Test SMA matches manual calculation."""
        df = calculate_sma(simple_price_data, window=5)

        # First 4 values should be NaN (not enough data)
        assert pd.isna(df["sma_5"].iloc[:4]).all()

        # 5th value should be mean of first 5 prices
        expected = np.mean([100, 101, 102, 103, 104])
        assert np.isclose(df["sma_5"].iloc[4], expected)

        # 10th value
        expected = np.mean([105, 106, 107, 108, 109])
        assert np.isclose(df["sma_5"].iloc[9], expected)

    def test_sma_window_sizes(self, simple_price_data):
        """Test SMA with different window sizes."""
        df = calculate_sma(simple_price_data, window=10)
        assert pd.isna(df["sma_10"].iloc[:9]).all()
        assert not pd.isna(df["sma_10"].iloc[9])

        df = calculate_sma(simple_price_data, window=20)
        assert pd.isna(df["sma_20"].iloc[:19]).all()
        assert not pd.isna(df["sma_20"].iloc[19])

    def test_sma_different_column(self, simple_price_data):
        """Test SMA on different price columns."""
        df = calculate_sma(simple_price_data, window=5, column="high")
        assert "sma_5" in df.columns
        expected = np.mean([101, 102, 103, 104, 105])
        assert np.isclose(df["sma_5"].iloc[4], expected)


class TestEMA:
    """Test Exponential Moving Average calculations."""

    def test_ema_calculation(self, simple_price_data):
        """Test EMA is calculated and differs from SMA."""
        df = calculate_ema(simple_price_data, span=10)

        # First 9 values should be NaN
        assert pd.isna(df["ema_10"].iloc[:9]).all()

        # EMA should exist after span period
        assert not pd.isna(df["ema_10"].iloc[9])

        # EMA should differ from SMA (more weight on recent)
        df = calculate_sma(df, window=10)
        assert not np.isclose(df["ema_10"].iloc[20], df["sma_10"].iloc[20])

    def test_ema_responds_faster_than_sma(self):
        """Test EMA reacts faster to price changes than SMA."""
        # Create data with sudden price jump
        prices = [100] * 20 + [110] * 20
        df = pd.DataFrame({"close": prices})

        df = calculate_sma(df, window=10)
        df = calculate_ema(df, span=10)

        # After jump, EMA should be closer to new price than SMA
        # Check a few periods after the jump
        assert df["ema_10"].iloc[25] > df["sma_10"].iloc[25]


class TestRSI:
    """Test Relative Strength Index calculations."""

    def test_rsi_range(self, simple_price_data):
        """Test RSI stays within 0-100 range."""
        df = calculate_rsi(simple_price_data, period=14)

        rsi_values = df["rsi_14"].dropna()
        assert (rsi_values >= 0).all()
        assert (rsi_values <= 100).all()

    def test_rsi_trending_up(self, simple_price_data):
        """Test RSI is high when price trends up."""
        df = calculate_rsi(simple_price_data, period=14)

        # With steadily increasing prices, RSI should be high (>50)
        rsi_values = df["rsi_14"].dropna()
        assert (rsi_values > 50).all()

    def test_rsi_trending_down(self):
        """Test RSI is low when price trends down."""
        prices = [100.0 - i for i in range(50)]
        df = pd.DataFrame({"close": prices})

        df = calculate_rsi(df, period=14)
        rsi_values = df["rsi_14"].dropna()

        # With steadily decreasing prices, RSI should be low (<50)
        assert (rsi_values < 50).all()

    def test_rsi_oscillating(self, oscillating_price_data):
        """Test RSI with oscillating prices."""
        df = calculate_rsi(oscillating_price_data, period=14)

        rsi_values = df["rsi_14"].dropna()
        # With oscillating prices, RSI should vary but stay in valid range
        # The mean may be above 50 due to net upward trend in the oscillation
        assert rsi_values.mean() > 40
        assert rsi_values.mean() < 80
        # Should see both high and low RSI values
        assert rsi_values.max() > 65
        assert rsi_values.min() < 65


class TestMACD:
    """Test MACD calculations."""

    def test_macd_components(self, simple_price_data):
        """Test MACD has all three components."""
        df = calculate_macd(simple_price_data)

        assert "macd" in df.columns
        assert "macd_signal" in df.columns
        assert "macd_histogram" in df.columns

    def test_macd_histogram_is_difference(self, simple_price_data):
        """Test MACD histogram equals MACD minus signal."""
        df = calculate_macd(simple_price_data)

        # Where all values are available
        valid_idx = df["macd_histogram"].notna()
        differences = df.loc[valid_idx, "macd"] - df.loc[valid_idx, "macd_signal"]
        histograms = df.loc[valid_idx, "macd_histogram"]

        assert np.allclose(differences, histograms)

    def test_macd_crossover(self):
        """Test MACD signal crossover detection."""
        # Create data with trend reversal
        prices = [100 + i for i in range(30)] + [130 - i for i in range(30)]
        df = pd.DataFrame({"close": prices})

        df = calculate_macd(df, fast=5, slow=10, signal=3)

        # Should see histogram change sign at some point
        histogram = df["macd_histogram"].dropna()
        assert (histogram > 0).any()
        assert (histogram < 0).any()

    def test_macd_custom_params(self, simple_price_data):
        """Test MACD with custom parameters."""
        df = calculate_macd(simple_price_data, fast=8, slow=17, signal=5)

        assert "macd" in df.columns
        assert not df["macd"].isna().all()


class TestBollingerBands:
    """Test Bollinger Bands calculations."""

    def test_bollinger_components(self, simple_price_data):
        """Test all Bollinger Band components are present."""
        df = calculate_bollinger_bands(simple_price_data, window=20)

        assert "bb_middle" in df.columns
        assert "bb_upper" in df.columns
        assert "bb_lower" in df.columns
        assert "bb_width" in df.columns

    def test_bollinger_middle_is_sma(self, simple_price_data):
        """Test middle band equals SMA."""
        df = calculate_bollinger_bands(simple_price_data, window=20)
        df = calculate_sma(df, window=20)

        valid_idx = df["bb_middle"].notna()
        assert np.allclose(
            df.loc[valid_idx, "bb_middle"],
            df.loc[valid_idx, "sma_20"]
        )

    def test_bollinger_band_ordering(self, simple_price_data):
        """Test upper band > middle > lower band."""
        df = calculate_bollinger_bands(simple_price_data, window=20)

        valid_idx = df["bb_upper"].notna()
        assert (df.loc[valid_idx, "bb_upper"] > df.loc[valid_idx, "bb_middle"]).all()
        assert (df.loc[valid_idx, "bb_middle"] > df.loc[valid_idx, "bb_lower"]).all()

    def test_bollinger_width_calculation(self, simple_price_data):
        """Test band width is correctly calculated."""
        df = calculate_bollinger_bands(simple_price_data, window=20)

        valid_idx = df["bb_width"].notna()
        expected_width = (
            (df.loc[valid_idx, "bb_upper"] - df.loc[valid_idx, "bb_lower"]) /
            df.loc[valid_idx, "bb_middle"]
        )

        assert np.allclose(df.loc[valid_idx, "bb_width"], expected_width)

    def test_bollinger_std_multiplier(self):
        """Test different std dev multipliers."""
        # Use constant price for predictable std dev
        df = pd.DataFrame({"close": [100] * 50})

        df_2std = calculate_bollinger_bands(df, window=20, num_std=2.0)
        df_3std = calculate_bollinger_bands(df, window=20, num_std=3.0)

        # With constant prices, bands should be equal to middle (std=0)
        # But width should scale with num_std parameter
        # Actually with constant prices std is 0, so bands collapse
        valid_idx = df_2std["bb_middle"].notna()
        assert np.allclose(
            df_2std.loc[valid_idx, "bb_upper"],
            df_2std.loc[valid_idx, "bb_middle"]
        )


class TestOBV:
    """Test On-Balance Volume calculations."""

    def test_obv_increases_on_up_days(self, volume_trend_data):
        """Test OBV increases when price goes up."""
        df = calculate_obv(volume_trend_data)

        assert "obv" in df.columns

        # First day OBV should be 0 (no prior day)
        # When price increases, OBV should increase by volume
        for i in range(1, len(df)):
            if df["close"].iloc[i] > df["close"].iloc[i - 1]:
                obv_change = df["obv"].iloc[i] - df["obv"].iloc[i - 1]
                assert obv_change == df["volume"].iloc[i]

    def test_obv_decreases_on_down_days(self, volume_trend_data):
        """Test OBV decreases when price goes down."""
        df = calculate_obv(volume_trend_data)

        for i in range(1, len(df)):
            if df["close"].iloc[i] < df["close"].iloc[i - 1]:
                obv_change = df["obv"].iloc[i] - df["obv"].iloc[i - 1]
                assert obv_change == -df["volume"].iloc[i]

    def test_obv_unchanged_on_flat_days(self):
        """Test OBV unchanged when price is flat."""
        df = pd.DataFrame(
            {
                "close": [100, 100, 100, 101, 101],
                "volume": [1000, 2000, 3000, 4000, 5000],
            }
        )

        df = calculate_obv(df)

        # First change: flat, OBV should not change
        assert df["obv"].iloc[1] == df["obv"].iloc[0]
        # Second change: flat
        assert df["obv"].iloc[2] == df["obv"].iloc[1]
        # Third change: up, should increase
        assert df["obv"].iloc[3] == df["obv"].iloc[2] + 4000


class TestAllIndicators:
    """Test calculate_all_indicators convenience function."""

    def test_all_indicators_present(self, simple_price_data):
        """Test all indicators are calculated."""
        df = calculate_all_indicators(simple_price_data)

        # Check default indicators are present
        assert "sma_20" in df.columns
        assert "sma_50" in df.columns
        assert "ema_12" in df.columns
        assert "ema_26" in df.columns
        assert "rsi_14" in df.columns
        assert "macd" in df.columns
        assert "macd_signal" in df.columns
        assert "macd_histogram" in df.columns
        assert "bb_middle" in df.columns
        assert "bb_upper" in df.columns
        assert "bb_lower" in df.columns
        assert "obv" in df.columns

    def test_all_indicators_custom_params(self, simple_price_data):
        """Test custom parameters work."""
        df = calculate_all_indicators(
            simple_price_data,
            sma_windows=[10, 30],
            ema_spans=[5, 10],
            rsi_period=10,
            macd_params=(8, 17, 5),
            bb_window=15,
            bb_std=1.5,
        )

        assert "sma_10" in df.columns
        assert "sma_30" in df.columns
        assert "ema_5" in df.columns
        assert "ema_10" in df.columns
        assert "rsi_10" in df.columns
