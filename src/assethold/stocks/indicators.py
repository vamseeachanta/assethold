"""
Technical indicators calculated using pure pandas/numpy.

All functions take a DataFrame with price data and return
the same DataFrame with indicator columns added.
"""

import numpy as np
import pandas as pd


def calculate_sma(df: pd.DataFrame, window: int = 20, column: str = "close") -> pd.DataFrame:
    """
    Calculate Simple Moving Average.

    Args:
        df: DataFrame with price data
        window: Number of periods for moving average
        column: Column to calculate SMA on

    Returns:
        DataFrame with new column: sma_{window}
    """
    df = df.copy()
    df[f"sma_{window}"] = df[column].rolling(window=window, min_periods=window).mean()
    return df


def calculate_ema(df: pd.DataFrame, span: int = 20, column: str = "close") -> pd.DataFrame:
    """
    Calculate Exponential Moving Average.

    Args:
        df: DataFrame with price data
        span: Number of periods for EMA span
        column: Column to calculate EMA on

    Returns:
        DataFrame with new column: ema_{span}
    """
    df = df.copy()
    df[f"ema_{span}"] = df[column].ewm(span=span, adjust=False, min_periods=span).mean()
    return df


def calculate_rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.DataFrame:
    """
    Calculate Relative Strength Index.

    RSI = 100 - (100 / (1 + RS))
    where RS = Average Gain / Average Loss over period

    Args:
        df: DataFrame with price data
        period: Number of periods (typically 14)
        column: Column to calculate RSI on

    Returns:
        DataFrame with new column: rsi_{period}
    """
    df = df.copy()

    # Calculate price changes
    delta = df[column].diff()

    # Separate gains and losses
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)

    # Calculate average gains and losses using EMA
    avg_gains = gains.ewm(span=period, adjust=False, min_periods=period).mean()
    avg_losses = losses.ewm(span=period, adjust=False, min_periods=period).mean()

    # Calculate RS and RSI
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))

    df[f"rsi_{period}"] = rsi
    return df


def calculate_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = "close",
) -> pd.DataFrame:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    MACD Line = EMA(fast) - EMA(slow)
    Signal Line = EMA(MACD, signal)
    Histogram = MACD - Signal

    Args:
        df: DataFrame with price data
        fast: Fast EMA period (typically 12)
        slow: Slow EMA period (typically 26)
        signal: Signal line EMA period (typically 9)
        column: Column to calculate MACD on

    Returns:
        DataFrame with new columns: macd, macd_signal, macd_histogram
    """
    df = df.copy()

    # Calculate fast and slow EMAs
    ema_fast = df[column].ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = df[column].ewm(span=slow, adjust=False, min_periods=slow).mean()

    # MACD line
    macd_line = ema_fast - ema_slow

    # Signal line
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()

    # Histogram
    histogram = macd_line - signal_line

    df["macd"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_histogram"] = histogram

    return df


def calculate_bollinger_bands(
    df: pd.DataFrame,
    window: int = 20,
    num_std: float = 2.0,
    column: str = "close",
) -> pd.DataFrame:
    """
    Calculate Bollinger Bands.

    Middle Band = SMA(window)
    Upper Band = Middle Band + (std_dev * num_std)
    Lower Band = Middle Band - (std_dev * num_std)

    Args:
        df: DataFrame with price data
        window: Number of periods (typically 20)
        num_std: Number of standard deviations (typically 2)
        column: Column to calculate bands on

    Returns:
        DataFrame with new columns: bb_middle, bb_upper, bb_lower, bb_width
    """
    df = df.copy()

    # Calculate middle band (SMA)
    middle = df[column].rolling(window=window, min_periods=window).mean()

    # Calculate standard deviation
    std = df[column].rolling(window=window, min_periods=window).std()

    # Calculate upper and lower bands
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)

    # Calculate band width (normalized)
    width = (upper - lower) / middle

    df["bb_middle"] = middle
    df["bb_upper"] = upper
    df["bb_lower"] = lower
    df["bb_width"] = width

    return df


def calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate On-Balance Volume.

    OBV increases by volume on up days, decreases by volume on down days.

    Args:
        df: DataFrame with price and volume data

    Returns:
        DataFrame with new column: obv
    """
    df = df.copy()

    # Calculate price direction
    price_change = df["close"].diff()
    direction = np.where(price_change > 0, 1, np.where(price_change < 0, -1, 0))

    # Calculate OBV
    obv = (direction * df["volume"]).cumsum()

    df["obv"] = obv
    return df


def calculate_all_indicators(
    df: pd.DataFrame,
    sma_windows: list[int] = None,
    ema_spans: list[int] = None,
    rsi_period: int = 14,
    macd_params: tuple[int, int, int] = (12, 26, 9),
    bb_window: int = 20,
    bb_std: float = 2.0,
) -> pd.DataFrame:
    """
    Calculate all technical indicators at once.

    Args:
        df: DataFrame with OHLCV data
        sma_windows: List of SMA windows (default: [20, 50])
        ema_spans: List of EMA spans (default: [12, 26])
        rsi_period: RSI period (default: 14)
        macd_params: MACD (fast, slow, signal) tuple (default: (12, 26, 9))
        bb_window: Bollinger Bands window (default: 20)
        bb_std: Bollinger Bands std dev multiplier (default: 2.0)

    Returns:
        DataFrame with all indicator columns added
    """
    if sma_windows is None:
        sma_windows = [20, 50]
    if ema_spans is None:
        ema_spans = [12, 26]

    # Calculate SMAs
    for window in sma_windows:
        df = calculate_sma(df, window=window)

    # Calculate EMAs
    for span in ema_spans:
        df = calculate_ema(df, span=span)

    # Calculate RSI
    df = calculate_rsi(df, period=rsi_period)

    # Calculate MACD
    df = calculate_macd(df, fast=macd_params[0], slow=macd_params[1], signal=macd_params[2])

    # Calculate Bollinger Bands
    df = calculate_bollinger_bands(df, window=bb_window, num_std=bb_std)

    # Calculate OBV
    df = calculate_obv(df)

    return df
