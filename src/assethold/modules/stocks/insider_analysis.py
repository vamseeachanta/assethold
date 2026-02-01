"""Insider trading and options call analysis.

Migrated from legacy_stock_analysis.py. Provides InsiderAnalysis (summary,
by-relation, by-timeline) and OptionsAnalysis (call effective value
evaluation and strike-price filtering).
"""

import logging

import pandas as pd

from assethold.common.data import (
    get_initials_from_name,
    getClosestIntegerInList,
    transform_df_datetime_to_str,
)

logger = logging.getLogger(__name__)

# Transaction types that represent selling activity
_SELL_TRANSACTION_TYPES = ("Sell", "Sale")

# Default share holding ratio when start_shares is zero or negative
_DEFAULT_HOLDING_RATIO = 1.01


def _compute_share_holding_ratio(end_shares, start_shares):
    """Compute end/start share ratio. Returns _DEFAULT_HOLDING_RATIO if start <= 0."""
    if start_shares > 0:
        return round(end_shares / start_shares, 2)
    return _DEFAULT_HOLDING_RATIO


def _compute_weighted_average_cost(df):
    """Compute share-weighted average cost. Returns None on failure."""
    total_shares = df["#Shares"].sum()
    if total_shares == 0:
        return None
    try:
        weighted_sum = (df["#Shares"] * df["Cost"]).sum()
        return round(weighted_sum / total_shares, 3)
    except (TypeError, ZeroDivisionError):
        logger.warning("Could not compute weighted average cost")
        return None


class InsiderAnalysis:
    """Analyse insider trading from a transaction DataFrame.

    Expected columns: Date, Transaction, Insider Trading, Relationship,
    #Shares, #Shares Total, Cost, share_holding_ratio.
    """

    def __init__(self):
        self.insider_df_buy = pd.DataFrame()
        self.insider_df_sell = pd.DataFrame()

    def get_insider_summary(self, insider_df):
        """Split insider transactions into buy/sell and attach tooltips.

        Returns dict with 'insider_df_buy' and 'insider_df_sell' record lists.
        """
        if len(insider_df) > 0:
            insider_df = transform_df_datetime_to_str(
                insider_df, date_format="%Y-%m-%d"
            )
            insider_df["Tooltip"] = insider_df.apply(
                self._format_summary_tooltip, axis=1
            )
            self.insider_df_buy = insider_df[
                insider_df.share_holding_ratio >= 1
            ]
            self.insider_df_sell = insider_df[
                insider_df.share_holding_ratio < 1
            ]
        else:
            self.insider_df_buy = insider_df.copy()
            self.insider_df_sell = insider_df.copy()

        return {
            "insider_df_buy": self.insider_df_buy.to_dict(orient="records"),
            "insider_df_sell": self.insider_df_sell.to_dict(orient="records"),
        }

    @staticmethod
    def _format_summary_tooltip(row):
        """Build a tooltip string for a single insider summary row."""
        return (
            f"transactionType: {row['Transaction']}, "
            f"Insider: {row['Insider Trading']}, "
            f"Relationship: {row['Relationship']}"
        )

    def get_insider_analysis_by_relation(self, insider_df):
        """Group insider trades by trader and compute share ratios.

        Returns list of record dicts (Relationship, Share Holding Ratio,
        Actions, Average Cost, Tooltip) or empty dict on error.
        """
        if len(insider_df) == 0:
            return []

        try:
            return self._analyse_by_relation(insider_df)
        except (KeyError, ValueError, IndexError):
            logger.exception("Error in insider analysis by relation")
            return {}

    def _analyse_by_relation(self, insider_df):
        """Core logic for relation-based insider analysis."""
        columns = [
            "Relationship",
            "Share Holding Ratio",
            "Actions",
            "Average Cost",
            "Tooltip",
        ]
        rows = []
        inside_traders = insider_df["Insider Trading"].unique()

        for inside_trader in inside_traders:
            df_trader = insider_df[
                insider_df["Insider Trading"] == inside_trader
            ].copy()

            end_shares = df_trader["#Shares Total"].iloc[0]
            total_traded = df_trader["#Shares"].sum()
            last_total = df_trader["#Shares Total"].iloc[-1]

            if df_trader["Transaction"].iloc[-1] in _SELL_TRANSACTION_TYPES:
                start_shares = last_total + total_traded
            else:
                start_shares = last_total - total_traded

            ratio = _compute_share_holding_ratio(end_shares, start_shares)
            average_cost = _compute_weighted_average_cost(df_trader)

            transaction_list = list(df_trader["Transaction"].unique())
            initials = get_initials_from_name(inside_trader)
            relationship = f"{df_trader['Relationship'].iloc[0]}_{initials}"
            actions = "; ".join(transaction_list)

            tooltip = (
                f"{df_trader['Relationship'].iloc[0]}, "
                f"Share End/Start # of {ratio}; "
                f"End Shares of {end_shares}; "
                f"Average Cost: {average_cost}, "
                f"Actions: {actions}"
            )
            rows.append([relationship, ratio, actions, average_cost, tooltip])

        result_df = pd.DataFrame(rows, columns=columns)
        return result_df.to_dict(orient="records")

    def get_insider_analysis_by_timeline(self, insider_df):
        """Group insider trades by date and transaction type.

        Returns list of record dicts (tradeDate, Actions, Share Holding
        Ratio, Average Cost, Tooltip) or empty dict on error.
        """
        if len(insider_df) == 0:
            return []

        try:
            return self._analyse_by_timeline(insider_df)
        except (KeyError, ValueError, IndexError):
            logger.exception("Error in insider analysis by timeline")
            return {}

    def _analyse_by_timeline(self, insider_df):
        """Core logic for timeline-based insider analysis."""
        columns = [
            "tradeDate",
            "Actions",
            "Share Holding Ratio",
            "Average Cost",
            "Tooltip",
        ]
        rows = []
        trade_dates = insider_df["Date"].unique()

        for trade_date in trade_dates:
            df_date = insider_df[insider_df["Date"] == trade_date].copy()
            unique_transactions = df_date["Transaction"].unique()

            for transaction_type in unique_transactions:
                df_txn = df_date[
                    df_date["Transaction"] == transaction_type
                ].copy()

                end_shares = df_txn["#Shares Total"].sum()
                shares = df_txn["#Shares"].sum()

                if transaction_type in _SELL_TRANSACTION_TYPES:
                    start_shares = end_shares + shares
                else:
                    start_shares = end_shares - shares

                ratio = _compute_share_holding_ratio(end_shares, start_shares)
                average_cost = _compute_weighted_average_cost(df_txn)

                tooltip = f"Average Cost: {average_cost}; "
                for i in range(len(df_txn)):
                    trader_name = df_txn["Insider Trading"].iloc[i]
                    initials = get_initials_from_name(trader_name)
                    rel = df_date["Relationship"].iloc[0]
                    tooltip += f"{rel}_{initials}; "

                rows.append([
                    trade_date, transaction_type, ratio, average_cost, tooltip
                ])

        result_df = pd.DataFrame(rows, columns=columns)
        result_df["tradeDate"] = result_df["tradeDate"].dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return result_df.to_dict(orient="records")


class OptionsAnalysis:
    """Evaluate call and put option data relative to current price."""

    _CALL_COLUMNS = [
        "expirationDate",
        "strike",
        "effectiveValuePerShare",
        "Tooltip",
    ]

    def __init__(self):
        self.call_effective_value_df = pd.DataFrame()
        self.call_effective_value_df_filtered = pd.DataFrame()

    def call_analysis(self, option_data, current_price):
        """Evaluate all call options across expiration dates.

        Args:
            option_data: Dict keyed by expiration date, values have
                         'calls' and 'puts' DataFrames.
            current_price: Current stock price.

        Returns:
            List of record dicts with call effective value data.
        """
        self.call_effective_value_df = pd.DataFrame(
            columns=self._CALL_COLUMNS
        )

        for option_date in option_data:
            call_data = option_data[option_date]["calls"]
            put_data = option_data[option_date]["puts"]
            self.evaluate_call_data(option_date, call_data, current_price)
            self.evaluate_put_data(option_date, put_data, current_price)

        return self.call_effective_value_df.to_dict(orient="records")

    def evaluate_call_data(self, option_date, call_data, current_price):
        """Calculate effective value per share for each call option row.

        contract_cost = max(lastPrice, bid); effective value is clamped >= 0.
        """
        if self.call_effective_value_df.empty:
            self.call_effective_value_df = pd.DataFrame(
                columns=self._CALL_COLUMNS
            )

        for i in range(len(call_data)):
            strike = call_data["strike"].iloc[i]
            last_price = call_data["lastPrice"].iloc[i]
            bid = call_data["bid"].iloc[i]
            contract_cost = max(last_price, bid)
            tooltip = f"{strike}, {option_date}"

            if contract_cost > 0:
                effective_value = contract_cost + (current_price - strike)
                effective_value = max(effective_value, 0)
            else:
                effective_value = 0

            row = [option_date, strike, effective_value, tooltip]
            self.call_effective_value_df.loc[
                len(self.call_effective_value_df)
            ] = row

    def evaluate_put_data(self, option_date, put_data, current_price):
        """Evaluate put option data. Not yet implemented."""
        pass

    def filter_call_analysis_data(self, n, current_price):
        """Filter call results to n/2 strikes on each side of current_price.

        Returns filtered DataFrame of call effective values.
        """
        if self.call_effective_value_df.empty:
            logger.warning(
                "No call analysis data to filter. Run call_analysis first."
            )
            self.call_effective_value_df_filtered = pd.DataFrame()
            return self.call_effective_value_df_filtered

        current_price_int = int(current_price)
        strike_prices = sorted(
            self.call_effective_value_df["strike"].unique().tolist()
        )
        _closest_value, closest_index = getClosestIntegerInList(
            strike_prices, current_price_int
        )

        neighbours = int(n / 2)
        start_index = max(closest_index - neighbours, 0)
        end_index = min(closest_index + neighbours, len(strike_prices))

        strike_prices_filtered = strike_prices[start_index:end_index]
        self.call_effective_value_df_filtered = (
            self.call_effective_value_df[
                self.call_effective_value_df["strike"].isin(
                    strike_prices_filtered
                )
            ].copy()
        )
        return self.call_effective_value_df_filtered
