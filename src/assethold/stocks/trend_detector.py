"""
Trend change detection for stock price series.

Detects:
- MA crossovers (golden cross / death cross)
- Support/resistance level breaks
- Volume spikes (>N standard deviations from mean)
- RSI overbought/oversold transitions
"""

from typing import Any

import pandas as pd

from assethold.stocks.indicators import calculate_sma, calculate_rsi


def detect_ma_crossover(
    df: pd.DataFrame,
    short_window: int = 20,
    long_window: int = 50,
    price_col: str = "close",
) -> list[dict[str, Any]]:
    """
    Detect golden cross / death cross MA crossover events.

    Returns list of event dicts: type, date, short_ma, long_ma.
    """
    if len(df) < long_window + 1:
        return []

    df = df.copy()
    short_col = f"sma_{short_window}"
    long_col = f"sma_{long_window}"

    if short_col not in df.columns:
        df = calculate_sma(df, window=short_window, column=price_col)
    if long_col not in df.columns:
        df = calculate_sma(df, window=long_window, column=price_col)

    # Drop rows where either MA is NaN
    valid = df[[short_col, long_col]].dropna()
    if len(valid) < 2:
        return []

    events: list[dict[str, Any]] = []
    # Use signed difference to track direction including equality
    # +1 = short above, -1 = short below, 0 = equal
    def _sign(s: float, l: float) -> int:
        if s > l:
            return 1
        if s < l:
            return -1
        return 0

    prev_sign = _sign(
        float(df.loc[valid.index[0], short_col]),
        float(df.loc[valid.index[0], long_col]),
    )

    for idx in valid.index[1:]:
        curr_s = float(df.loc[idx, short_col])
        curr_l = float(df.loc[idx, long_col])
        curr_sign = _sign(curr_s, curr_l)

        if prev_sign <= 0 and curr_sign > 0:
            events.append(
                {
                    "type": "golden_cross",
                    "date": df.loc[idx, "date"] if "date" in df.columns else idx,
                    "short_ma": curr_s,
                    "long_ma": curr_l,
                }
            )
        elif prev_sign >= 0 and curr_sign < 0:
            events.append(
                {
                    "type": "death_cross",
                    "date": df.loc[idx, "date"] if "date" in df.columns else idx,
                    "short_ma": curr_s,
                    "long_ma": curr_l,
                }
            )
        if curr_sign != 0:
            prev_sign = curr_sign

    return events


def detect_support_resistance_break(
    df: pd.DataFrame,
    lookback: int = 20,
    price_col: str = "close",
    buffer_pct: float = 0.01,
) -> list[dict[str, Any]]:
    """
    Detect price breaks above recent resistance or below recent support.

    Returns list of event dicts: type, date, price, level.
    """
    if len(df) <= lookback:
        return []

    events: list[dict[str, Any]] = []

    # Use reset_index positionally to avoid label issues
    df_reset = df.reset_index(drop=True)

    for i in range(lookback, len(df_reset)):
        window = df_reset.iloc[i - lookback: i]
        resistance = float(window["high"].max())
        support = float(window["low"].min())

        current_price = float(df_reset.loc[i, price_col])
        row_date = (
            df_reset.loc[i, "date"]
            if "date" in df_reset.columns
            else i
        )

        if current_price > resistance * (1 + buffer_pct):
            events.append(
                {
                    "type": "resistance_break",
                    "date": row_date,
                    "price": current_price,
                    "level": resistance,
                }
            )
        elif current_price < support * (1 - buffer_pct):
            events.append(
                {
                    "type": "support_break",
                    "date": row_date,
                    "price": current_price,
                    "level": support,
                }
            )

    return events


def detect_volume_spike(
    df: pd.DataFrame,
    threshold_std: float = 2.0,
    min_periods: int = 10,
    volume_col: str = "volume",
) -> list[dict[str, Any]]:
    """
    Detect volume spikes exceeding threshold_std standard deviations above mean.

    Returns list of event dicts: type, date, volume, mean_volume, std_multiples.
    """
    if len(df) < min_periods:
        return []

    events: list[dict[str, Any]] = []
    df_reset = df.reset_index(drop=True)
    vols = df_reset[volume_col].astype(float)

    for i in range(min_periods, len(df_reset)):
        window_vols = vols.iloc[:i]
        mean_vol = float(window_vols.mean())
        std_vol = float(window_vols.std(ddof=1))

        current_vol = float(vols.iloc[i])

        if std_vol == 0:
            # All prior volumes equal — flag if current is significantly above
            if current_vol > mean_vol * (1 + threshold_std):
                std_multiples = float("inf")
            else:
                continue
        else:
            std_multiples = (current_vol - mean_vol) / std_vol

        if std_multiples >= threshold_std:
            row_date = (
                df_reset.loc[i, "date"]
                if "date" in df_reset.columns
                else i
            )
            events.append(
                {
                    "type": "volume_spike",
                    "date": row_date,
                    "volume": current_vol,
                    "mean_volume": mean_vol,
                    "std_multiples": round(std_multiples, 2) if std_multiples != float("inf") else std_multiples,
                }
            )

    return events


def detect_rsi_transition(
    df: pd.DataFrame,
    period: int = 14,
    overbought: float = 70.0,
    oversold: float = 30.0,
    price_col: str = "close",
) -> list[dict[str, Any]]:
    """
    Detect RSI entries into overbought or oversold zones.

    Returns list of event dicts: type, date, rsi.
    """
    if len(df) < period + 1:
        return []

    df = df.copy()
    rsi_col = f"rsi_{period}"

    if rsi_col not in df.columns:
        df = calculate_rsi(df, period=period, column=price_col)

    rsi_series = df[rsi_col].reset_index(drop=True)
    dates = (
        df["date"].reset_index(drop=True)
        if "date" in df.columns
        else pd.RangeIndex(len(df))
    )

    events: list[dict[str, Any]] = []
    valid_idx = rsi_series.dropna().index

    if len(valid_idx) < 1:
        return []

    first_idx = valid_idx[0]
    first_rsi = float(rsi_series.iloc[first_idx])

    # Fire immediately if the first valid RSI starts in an extreme zone
    if first_rsi > overbought:
        events.append(
            {
                "type": "rsi_overbought",
                "date": dates.iloc[first_idx],
                "rsi": round(first_rsi, 2),
            }
        )
    elif first_rsi < oversold:
        events.append(
            {
                "type": "rsi_oversold",
                "date": dates.iloc[first_idx],
                "rsi": round(first_rsi, 2),
            }
        )

    if len(valid_idx) < 2:
        return events

    prev_rsi = first_rsi

    for idx in valid_idx[1:]:
        curr_rsi = float(rsi_series.iloc[idx])

        if prev_rsi <= overbought and curr_rsi > overbought:
            events.append(
                {
                    "type": "rsi_overbought",
                    "date": dates.iloc[idx],
                    "rsi": round(curr_rsi, 2),
                }
            )
        elif prev_rsi >= oversold and curr_rsi < oversold:
            events.append(
                {
                    "type": "rsi_oversold",
                    "date": dates.iloc[idx],
                    "rsi": round(curr_rsi, 2),
                }
            )
        prev_rsi = curr_rsi

    return events


class TrendDetector:
    """
    Orchestrates all trend change detection on a single price DataFrame.

    Usage::

        detector = TrendDetector(short_ma=20, long_ma=50)
        result = detector.analyze(df)
        all_events = detector.get_all_events(result)
    """

    def __init__(
        self,
        short_ma: int = 20,
        long_ma: int = 50,
        sr_lookback: int = 20,
        volume_spike_std: float = 2.0,
        rsi_period: int = 14,
        rsi_overbought: float = 70.0,
        rsi_oversold: float = 30.0,
    ):
        """Initialize TrendDetector with configurable thresholds."""
        self.short_ma = short_ma
        self.long_ma = long_ma
        self.sr_lookback = sr_lookback
        self.volume_spike_std = volume_spike_std
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold

    def analyze(self, df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
        """Run all detectors; returns dict: ma_crossovers, sr_breaks, volume_spikes, rsi_transitions."""
        if df.empty:
            return {
                "ma_crossovers": [],
                "sr_breaks": [],
                "volume_spikes": [],
                "rsi_transitions": [],
            }

        return {
            "ma_crossovers": detect_ma_crossover(
                df, short_window=self.short_ma, long_window=self.long_ma
            ),
            "sr_breaks": detect_support_resistance_break(
                df, lookback=self.sr_lookback
            ),
            "volume_spikes": detect_volume_spike(
                df, threshold_std=self.volume_spike_std
            ),
            "rsi_transitions": detect_rsi_transition(
                df,
                period=self.rsi_period,
                overbought=self.rsi_overbought,
                oversold=self.rsi_oversold,
            ),
        }

    def get_all_events(
        self, analysis_result: dict[str, list[dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """Return flat list of all events across all categories."""
        all_events: list[dict[str, Any]] = []
        for events in analysis_result.values():
            all_events.extend(events)
        return all_events

    def summary(
        self, analysis_result: dict[str, list[dict[str, Any]]]
    ) -> dict[str, int]:
        """Return dict of event counts by category."""
        return {key: len(val) for key, val in analysis_result.items()}
