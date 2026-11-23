"""
Plotly-based dashboard for stock analysis visualization.

Generates charts for:
- Price with MA overlays
- RSI
- MACD
- Insider activity timeline
"""

from pathlib import Path
from typing import Any, Optional

import pandas as pd


def _require_plotly() -> Any:
    """Import plotly.graph_objects, raising ImportError with install hint."""
    try:
        import plotly.graph_objects as go
        return go
    except ImportError as exc:
        raise ImportError(
            "plotly is required for dashboard charts. "
            "Install with: pip install plotly"
        ) from exc


def build_price_chart(
    df: pd.DataFrame,
    ticker: str,
    ma_columns: Optional[list[str]] = None,
) -> Any:
    """
    Build a candlestick price chart with optional MA overlays.

    Args:
        df: DataFrame with columns: date, open, high, low, close
        ticker: Stock ticker symbol for chart title
        ma_columns: List of MA column names to overlay (e.g. ['sma_20', 'ema_50'])

    Returns:
        plotly.graph_objects.Figure
    """
    go = _require_plotly()

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=ticker,
        )
    )

    if ma_columns:
        for col in ma_columns:
            if col in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df["date"],
                        y=df[col],
                        name=col.upper(),
                        line={"width": 1.5},
                    )
                )

    fig.update_layout(
        title=f"{ticker} — Price with MA Overlays",
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
    )
    return fig


def build_rsi_chart(df: pd.DataFrame, ticker: str, rsi_period: int = 14) -> Any:
    """
    Build an RSI chart with overbought/oversold reference lines.

    Args:
        df: DataFrame with RSI column (rsi_{period})
        ticker: Stock ticker symbol for chart title
        rsi_period: RSI period used when computing the column

    Returns:
        plotly.graph_objects.Figure
    """
    go = _require_plotly()

    rsi_col = f"rsi_{rsi_period}"
    fig = go.Figure()

    if rsi_col in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df[rsi_col],
                name=f"RSI ({rsi_period})",
                line={"color": "orange", "width": 1.5},
            )
        )

    # Reference lines
    for level, color, label in [
        (70, "red", "Overbought"),
        (30, "green", "Oversold"),
        (50, "gray", "Midline"),
    ]:
        fig.add_hline(
            y=level,
            line_dash="dash",
            line_color=color,
            annotation_text=label,
        )

    fig.update_layout(
        title=f"{ticker} — RSI ({rsi_period})",
        xaxis_title="Date",
        yaxis_title="RSI",
        yaxis={"range": [0, 100]},
        template="plotly_dark",
    )
    return fig


def build_macd_chart(df: pd.DataFrame, ticker: str) -> Any:
    """
    Build a MACD chart with MACD line, signal line, and histogram.

    Args:
        df: DataFrame with columns: date, macd, macd_signal, macd_histogram
        ticker: Stock ticker symbol for chart title

    Returns:
        plotly.graph_objects.Figure
    """
    go = _require_plotly()

    fig = go.Figure()

    if "macd" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["macd"],
                name="MACD",
                line={"color": "blue", "width": 1.5},
            )
        )

    if "macd_signal" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["macd_signal"],
                name="Signal",
                line={"color": "red", "width": 1.5},
            )
        )

    if "macd_histogram" in df.columns:
        histogram = df["macd_histogram"]
        colors = ["green" if v >= 0 else "red" for v in histogram.fillna(0)]
        fig.add_trace(
            go.Bar(
                x=df["date"],
                y=histogram,
                name="Histogram",
                marker_color=colors,
                opacity=0.6,
            )
        )

    fig.update_layout(
        title=f"{ticker} — MACD",
        xaxis_title="Date",
        yaxis_title="MACD",
        template="plotly_dark",
    )
    return fig


def build_insider_timeline(
    insider_df: pd.DataFrame,
    ticker: str,
) -> Any:
    """
    Build a scatter plot of insider buy/sell transactions over time.

    Args:
        insider_df: DataFrame with columns: transaction_date, shares,
            acquired_or_disposed, owner_name
        ticker: Stock ticker symbol for chart title

    Returns:
        plotly.graph_objects.Figure
    """
    go = _require_plotly()

    fig = go.Figure()

    if insider_df.empty:
        fig.update_layout(title=f"{ticker} — Insider Activity (no data)")
        return fig

    buys = insider_df[insider_df["acquired_or_disposed"] == "A"]
    sells = insider_df[insider_df["acquired_or_disposed"] == "D"]

    if not buys.empty:
        fig.add_trace(
            go.Scatter(
                x=buys["transaction_date"],
                y=buys["shares"],
                mode="markers",
                name="Buys",
                marker={"color": "green", "size": 10, "symbol": "triangle-up"},
                text=buys["owner_name"],
                hovertemplate=(
                    "%{text}<br>Date: %{x}<br>Shares: %{y:,}<extra></extra>"
                ),
            )
        )

    if not sells.empty:
        fig.add_trace(
            go.Scatter(
                x=sells["transaction_date"],
                y=sells["shares"],
                mode="markers",
                name="Sells",
                marker={"color": "red", "size": 10, "symbol": "triangle-down"},
                text=sells["owner_name"],
                hovertemplate=(
                    "%{text}<br>Date: %{x}<br>Shares: %{y:,}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=f"{ticker} — Insider Activity",
        xaxis_title="Date",
        yaxis_title="Shares",
        template="plotly_dark",
    )
    return fig


def save_chart(fig: Any, output_path: Path, fmt: str = "html") -> None:
    """
    Save a Plotly figure to disk.

    Args:
        fig: Plotly Figure object
        output_path: Destination path (extension determines format if not set)
        fmt: Output format — 'html' (interactive) or 'png' (static)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "html":
        fig.write_html(str(output_path))
    elif fmt == "png":
        fig.write_image(str(output_path))
    else:
        raise ValueError(f"Unsupported format: {fmt!r}. Use 'html' or 'png'.")
