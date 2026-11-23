"""Insider trading chart functions using plotly.graph_objects.

Migrated from legacy stock_charts.py. Provides bubble charts for insider
buy/sell activity, relative holding charts, and aggregation charts by
relationship and timeline.
"""

import datetime
import json

import plotly.graph_objects as go


def _compute_sizeref(sizeref_max, sizemax=40):
    """Compute the plotly sizeref for bubble area scaling.

    Replicates the legacy Visualization.get_custom_size_ref formula.

    Args:
        sizeref_max: Maximum data value to scale against.
        sizemax: Maximum marker pixel diameter.

    Returns:
        Float sizeref value for plotly marker.sizeref.
    """
    return 2 * sizeref_max / (sizemax**2)


def _max_shares_across(df_buy, df_sell, col="#Shares"):
    """Return the max value of col across both buy and sell DataFrames."""
    ref1 = df_buy[col].max() if len(df_buy) > 0 else 100
    ref2 = df_sell[col].max() if len(df_sell) > 0 else 100
    return max(ref1, ref2)


class InsiderCharts:
    """Insider trading activity charts."""

    @staticmethod
    def create_insider_chart(cfg):
        """Combined insider chart: buys + sells + share price overlay.

        Merges the data traces from insider_buy, insider_sell, and
        insider_share_price into a single figure.

        Args:
            cfg: Dict with 'ticker', 'df_insider_buy', 'df_insider_sell',
                 and 'ta' (price DataFrame).

        Returns:
            JSON string of the combined plotly figure dict.
        """
        data1 = json.loads(InsiderCharts.create_insider_buy_chart(cfg))
        data2 = json.loads(InsiderCharts.create_insider_sell_chart(cfg))
        data3 = json.loads(InsiderCharts.create_insider_share_price_chart(cfg))

        combined = data1.copy()
        combined["data"] = data1["data"] + data2["data"] + data3["data"]
        return json.dumps(combined)

    @staticmethod
    def create_insider_buy_chart(cfg):
        """Bubble chart of insider buy transactions.

        Bubble size is proportional to number of shares purchased.

        Args:
            cfg: Dict with 'ticker', 'df_insider_buy' (DataFrame with
                 Date, Cost, #Shares, Tooltip), 'df_insider_sell'.

        Returns:
            JSON string of the plotly figure dict.
        """
        ticker = cfg["ticker"]
        df = cfg["df_insider_buy"]
        df_sell = cfg["df_insider_sell"]

        sizeref_max = _max_shares_across(df, df_sell)
        sizeref = _compute_sizeref(sizeref_max)

        fig = go.Figure()
        if len(df) > 0:
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=df["Cost"],
                    mode="markers",
                    name="Bought",
                    text=df.get("Tooltip", None),
                    marker=dict(
                        size=df["#Shares"],
                        sizemode="area",
                        sizeref=sizeref,
                        sizemin=4,
                        color="rgb(44, 160, 101)",
                    ),
                )
            )

        fig.update_layout(
            title=f"Insider Buy Cost and Volumes: {ticker}",
            yaxis_title="Cost Basis (USD)",
        )
        return json.dumps(fig.to_dict())

    @staticmethod
    def create_insider_sell_chart(cfg):
        """Bubble chart of insider sell transactions.

        Bubble size is proportional to number of shares sold.

        Args:
            cfg: Dict with 'ticker', 'df_insider_sell' (DataFrame with
                 Date, Cost, #Shares, Tooltip), 'df_insider_buy'.

        Returns:
            JSON string of the plotly figure dict.
        """
        ticker = cfg["ticker"]
        df = cfg["df_insider_sell"]
        df_buy = cfg["df_insider_buy"]

        sizeref_max = _max_shares_across(df_buy, df)
        sizeref = _compute_sizeref(sizeref_max)

        fig = go.Figure()
        if len(df) > 0:
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=df["Cost"],
                    mode="markers",
                    name="Sold",
                    text=df.get("Tooltip", None),
                    marker=dict(
                        size=df["#Shares"],
                        sizemode="area",
                        sizeref=sizeref,
                        sizemin=4,
                        color="rgb(255, 65, 54)",
                    ),
                )
            )

        fig.update_layout(
            title=f"Insider Sale Cost and Volumes: {ticker}",
            yaxis_title="Cost Basis (USD)",
        )
        return json.dumps(fig.to_dict())

    @staticmethod
    def create_insider_share_price_chart(cfg):
        """Share price line filtered to the insider trading date range.

        Filters the price data to start from the earliest insider
        transaction date.

        Args:
            cfg: Dict with 'ticker', 'ta' (DataFrame with Date, Close),
                 'df_insider_buy', 'df_insider_sell'.

        Returns:
            JSON string of the plotly figure dict.
        """
        ticker = cfg["ticker"]
        df = cfg["ta"].copy()
        df_buy = cfg["df_insider_buy"]
        df_sell = cfg["df_insider_sell"]

        buy_min = df_buy["Date"].min() if len(df_buy) > 0 else datetime.datetime.now()
        sell_min = (
            df_sell["Date"].min() if len(df_sell) > 0 else datetime.datetime.now()
        )
        min_date = min(buy_min, sell_min)
        df = df[df["Date"] >= min_date]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["Close"],
                mode="lines",
                name="Share Price, Close",
            )
        )
        fig.update_layout(
            title=f"Stock Price Timeline: {ticker}",
            xaxis_title="Date",
            yaxis_title="Value",
        )
        return json.dumps(fig.to_dict())

    @staticmethod
    def create_insider_relative_sale_chart(cfg):
        """Relative insider sales with starting holdings overlay.

        Shows two bubble series (starting holdings in grey, sold shares
        in red) plus the share price line.

        Args:
            cfg: Dict with 'ticker', 'df_insider_sell' (DataFrame with
                 Date, Cost, #Shares, #Shares Total, start_shares, Tooltip),
                 'df_insider_buy', 'ta'.

        Returns:
            Plotly figure dict (not JSON string, matching legacy behavior).
        """
        ticker = cfg["ticker"]
        df = cfg["df_insider_sell"]

        sizeref_max = df["start_shares"].max() if len(df) > 0 else 100
        sizeref = _compute_sizeref(sizeref_max)

        fig = go.Figure()

        # Trace 1: starting shares (grey bubbles)
        if len(df) > 0:
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=df["Cost"],
                    mode="markers",
                    name="Shares at Start",
                    text=df.get("Tooltip", None),
                    marker=dict(
                        size=df["#Shares Total"],
                        sizemode="area",
                        sizeref=sizeref,
                        sizemin=4,
                        color="rgb(161, 161, 157)",
                    ),
                )
            )

            # Trace 2: sold shares (red bubbles)
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=df["Cost"],
                    mode="markers",
                    name="Sold",
                    marker=dict(
                        size=df["#Shares"],
                        sizemode="area",
                        sizeref=sizeref,
                        sizemin=4,
                        color="rgb(255, 65, 54)",
                    ),
                )
            )

        fig.update_layout(
            title=f"Insider Sale Cost and Volumes: {ticker}",
            yaxis_title="Cost Basis (USD)",
        )

        # Merge share price overlay
        price_data = json.loads(
            InsiderCharts.create_insider_share_price_chart(cfg)
        )
        result = fig.to_dict()
        result["data"] = list(result["data"]) + price_data["data"]
        return result

    @staticmethod
    def create_insider_relative_buy_chart(cfg):
        """Relative insider buys with ending holdings overlay.

        Shows two bubble series (ending holdings in grey, bought shares
        in green) plus the share price line.

        Args:
            cfg: Dict with 'ticker', 'df_insider_buy' (DataFrame with
                 Date, Cost, #Shares, #Shares Total, Tooltip),
                 'df_insider_sell', 'ta'.

        Returns:
            Plotly figure dict (not JSON string, matching legacy behavior).
        """
        ticker = cfg["ticker"]
        df = cfg["df_insider_buy"]

        sizeref_max = df["#Shares Total"].max() if len(df) > 0 else 100
        sizeref = _compute_sizeref(sizeref_max)

        fig = go.Figure()

        # Trace 1: ending shares (grey bubbles)
        if len(df) > 0:
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=df["Cost"],
                    mode="markers",
                    name="Shares at End",
                    text=df.get("Tooltip", None),
                    marker=dict(
                        size=df["#Shares Total"],
                        sizemode="area",
                        sizeref=sizeref,
                        sizemin=4,
                        color="rgb(161, 161, 157)",
                    ),
                )
            )

            # Trace 2: bought shares (green bubbles)
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=df["Cost"],
                    mode="markers",
                    name="Buy",
                    text=df.get("Tooltip", None),
                    marker=dict(
                        size=df["#Shares"],
                        sizemode="area",
                        sizeref=sizeref,
                        sizemin=4,
                        color="rgb(44, 160, 101)",
                    ),
                )
            )

        fig.update_layout(
            title=f"Insider Buy Cost and Volumes: {ticker}",
            yaxis_title="Cost Basis (USD)",
        )

        # Merge share price overlay
        price_data = json.loads(
            InsiderCharts.create_insider_share_price_chart(cfg)
        )
        result = fig.to_dict()
        result["data"] = list(result["data"]) + price_data["data"]
        return result

    @staticmethod
    def create_insider_by_relation_chart(cfg):
        """Bar chart of share holding ratio by insider relationship.

        Includes a horizontal reference line at ratio = 1.0 (dashed red).

        Args:
            cfg: Dict with 'ticker', 'df_insider_by_relation' (DataFrame
                 with Relationship, Share Holding Ratio, Tooltip).

        Returns:
            Plotly figure dict (not JSON string, matching legacy behavior).
        """
        ticker = cfg["ticker"]
        df = cfg["df_insider_by_relation"]

        fig = go.Figure()
        if len(df) > 0:
            fig.add_trace(
                go.Bar(
                    x=df["Relationship"],
                    y=df["Share Holding Ratio"],
                    name="Share Holding Ratio",
                    text=df.get("Tooltip", None),
                )
            )

        fig.update_layout(
            title=f"Share Holding (End/Start) Ratio by Insider: {ticker}",
            xaxis=dict(tickangle=-45),
            yaxis=dict(range=[0, 3], title="Share Ratio (End/Start)"),
            shapes=[
                dict(
                    type="line",
                    xref="paper",
                    x0=0,
                    y0=1,
                    x1=1,
                    y1=1,
                    line=dict(color="rgb(255,0,0)", width=1, dash="dash"),
                )
            ],
        )
        return fig.to_dict()

    @staticmethod
    def create_insider_by_timeline_chart(cfg):
        """Bar chart of share holding ratio by trade date.

        Groups bars by the Actions column and includes a horizontal
        reference line at ratio = 1.0 (dashed red).

        Args:
            cfg: Dict with 'ticker', 'df_insider_by_timeline' (DataFrame
                 with tradeDate, Share Holding Ratio, Actions, Tooltip).

        Returns:
            Plotly figure dict (not JSON string, matching legacy behavior).
        """
        ticker = cfg["ticker"]
        df = cfg["df_insider_by_timeline"]

        fig = go.Figure()
        if len(df) > 0 and "Actions" in df.columns:
            for action_name, group in df.groupby("Actions"):
                fig.add_trace(
                    go.Bar(
                        x=group["tradeDate"],
                        y=group["Share Holding Ratio"],
                        name=str(action_name),
                        text=group.get("Tooltip", None),
                    )
                )
        elif len(df) > 0:
            fig.add_trace(
                go.Bar(
                    x=df["tradeDate"],
                    y=df["Share Holding Ratio"],
                    name="Share Holding Ratio",
                    text=df.get("Tooltip", None),
                )
            )

        fig.update_layout(
            title=f"Share Holding (End/Start) Ratio by Timeline : {ticker}",
            xaxis=dict(
                tickangle=-45,
                type="category",
                categoryorder="category ascending",
            ),
            yaxis=dict(range=[0, 3], title="Share Ratio (End/Start)"),
            barmode="group",
            shapes=[
                dict(
                    type="line",
                    xref="paper",
                    x0=0,
                    y0=1,
                    x1=1,
                    y1=1,
                    line=dict(color="rgb(255,0,0)", width=1, dash="dash"),
                )
            ],
        )
        return fig.to_dict()
