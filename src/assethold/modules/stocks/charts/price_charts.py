"""Price and volume chart functions using plotly.graph_objects.

Migrated from legacy stock_charts.py. All methods are static and return
JSON strings of plotly figure dicts for consumption by frontend components.
"""

import json

import plotly.graph_objects as go


class PriceCharts:
    """Price timeline and volume indicator charts."""

    @staticmethod
    def create_price_chart(cfg):
        """Price line chart with 50/150/200-day moving averages.

        Args:
            cfg: Dict with 'ta' (DataFrame with Date, Close,
                 50_day_rolling, 150_day_rolling, 200_day_rolling)
                 and 'ticker' (str).

        Returns:
            JSON string of the plotly figure dict.
        """
        df = cfg.get("ta", None)
        ticker = cfg["ticker"]

        fig = go.Figure()
        traces = [
            ("Close", "Close"),
            ("50_day_rolling", "50 day avg."),
            ("150_day_rolling", "150 day avg."),
            ("200_day_rolling", "200 day avg."),
        ]
        for col, name in traces:
            if col in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df["Date"], y=df[col], mode="lines", name=name
                    )
                )

        fig.update_layout(
            title=f"Stock Price Timeline: {ticker}",
            xaxis_title="Date",
            yaxis_title="Value",
        )
        return json.dumps(fig.to_dict())

    @staticmethod
    def create_volume_on_balance(cfg):
        """On-balance volume line chart.

        Args:
            cfg: Dict with 'ta' (DataFrame with volume_obv column)
                 and 'ticker' (str).

        Returns:
            JSON string of the plotly figure dict.
        """
        df = cfg.get("ta", None)
        ticker = cfg["ticker"]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df.index.tolist(),
                y=df["volume_obv"],
                mode="lines",
                name="On Balance Volume",
            )
        )
        fig.update_layout(
            title=f"On Balance Volume: {ticker}",
            xaxis_title="Date",
            yaxis_title="Value",
        )
        return json.dumps(fig.to_dict())

    @staticmethod
    def create_ob_volume_chart(cfg):
        """On-balance volume chart (alternative entry point).

        Args:
            cfg: Dict with 'ta' (DataFrame with volume_obv column)
                 and 'ticker' (str).

        Returns:
            JSON string of the plotly figure dict.
        """
        df = cfg.get("ta", None)
        ticker = cfg["ticker"]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df.index.tolist(),
                y=df["volume_obv"],
                mode="lines",
                name="On Balance Volume",
            )
        )
        fig.update_layout(
            title=f"On balance Volume : {ticker}",
            xaxis_title="Date",
            yaxis_title="Value",
        )
        return json.dumps(fig.to_dict())

    @staticmethod
    def create_volume_all_chart(cfg):
        """Combined volume indicators: EoM, EoM SMA, VWAP.

        Args:
            cfg: Dict with 'ta' (DataFrame with volume_em, volume_sma_em,
                 volume_vwap columns) and 'ticker' (str).

        Returns:
            JSON string of the plotly figure dict.
        """
        df = cfg.get("ta", None)
        ticker = cfg["ticker"]

        fig = go.Figure()
        traces = [
            ("volume_em", "Ease of Movement (EoM)"),
            ("volume_sma_em", "EoM SMA."),
            ("volume_vwap", "Vol. Wt. Avg Price"),
        ]
        for col, name in traces:
            if col in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df.index.tolist(),
                        y=df[col],
                        mode="lines",
                        name=name,
                    )
                )

        fig.update_layout(
            title=f"Volume Indicators: {ticker}",
            xaxis_title="Date",
            yaxis_title="Value",
        )
        return json.dumps(fig.to_dict())
