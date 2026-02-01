"""Institutional holdings chart functions using plotly.graph_objects.

Migrated from legacy stock_charts.py. Provides bubble and overlay charts
for institutional holder volume data.
"""

import json

import plotly.graph_objects as go


def _compute_sizeref(sizeref_max, sizemax=40):
    """Compute the plotly sizeref for bubble area scaling.

    Args:
        sizeref_max: Maximum data value to scale against.
        sizemax: Maximum marker pixel diameter.

    Returns:
        Float sizeref value for plotly marker.sizeref.
    """
    return 2 * sizeref_max / (sizemax**2)


class InstitutionalCharts:
    """Institutional holder activity charts."""

    @staticmethod
    def create_institution_chart(cfg):
        """Combined institutional holdings bubble chart with price overlay.

        Merges the institutional volume bubbles and the insider share
        price line into a single figure.

        Args:
            cfg: Dict with 'ticker', 'df_institutional_holders' (DataFrame
                 with Shares, end_date, Holder), plus 'ta',
                 'df_insider_buy', 'df_insider_sell' for the price overlay.

        Returns:
            JSON string of the combined plotly figure dict.
        """
        from assethold.modules.stocks.charts.insider_charts import (
            InsiderCharts,
        )

        vol_data = json.loads(
            InstitutionalCharts.create_institution_volume_chart(cfg)
        )
        price_data = json.loads(
            InsiderCharts.create_insider_share_price_chart(cfg)
        )

        combined = vol_data.copy()
        combined["data"] = vol_data["data"] + price_data["data"]
        return json.dumps(combined)

    @staticmethod
    def create_institution_volume_chart(cfg):
        """Bubble chart of institutional holder share volumes.

        Bubble size is proportional to number of shares held.

        Args:
            cfg: Dict with 'ticker', 'df_institutional_holders' (DataFrame
                 with end_date, Shares, Holder columns).

        Returns:
            JSON string of the plotly figure dict.
        """
        ticker = cfg["ticker"]
        df = cfg["df_institutional_holders"]

        sizeref_max = df["Shares"].max() if len(df) > 0 else 100
        sizeref = _compute_sizeref(sizeref_max)

        fig = go.Figure()
        if len(df) > 0:
            fig.add_trace(
                go.Scatter(
                    x=df["end_date"],
                    y=df["Shares"],
                    mode="markers",
                    name="Institution Volume(#)",
                    text=df.get("Holder", None),
                    marker=dict(
                        size=df["Shares"],
                        sizemode="area",
                        sizeref=sizeref,
                        sizemin=4,
                    ),
                )
            )

        fig.update_layout(
            title=f"Institution Volumes: {ticker}",
            yaxis2=dict(
                title="Shares",
                titlefont=dict(color="rgb(148, 103, 189)"),
                tickfont=dict(color="rgb(148, 103, 189)"),
            ),
        )
        return json.dumps(fig.to_dict())
