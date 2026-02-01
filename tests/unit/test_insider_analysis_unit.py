"""Unit tests for InsiderAnalysis and OptionsAnalysis.

Tests insider summary splitting and call option effective-value
calculation with synthetic data -- no API calls, no external
dependencies.  Uses deterministic, hand-crafted DataFrames.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from assethold.modules.stocks.insider_analysis import (
    InsiderAnalysis,
    OptionsAnalysis,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def insider_analysis():
    """Fresh InsiderAnalysis instance."""
    return InsiderAnalysis()


@pytest.fixture
def options_analysis():
    """Fresh OptionsAnalysis instance."""
    return OptionsAnalysis()


@pytest.fixture
def sample_insider_df():
    """Sample insider transactions with buys and sells.

    share_holding_ratio >= 1 indicates a buy, < 1 indicates a sell.
    """
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(
                ["2024-06-01", "2024-06-02", "2024-06-03", "2024-06-04"]
            ),
            "Transaction": ["Purchase", "Purchase", "Sale", "Purchase"],
            "Insider Trading": [
                "John Smith",
                "Jane Doe",
                "John Smith",
                "Bob Lee",
            ],
            "Relationship": ["CEO", "CFO", "CEO", "Director"],
            "#Shares": [1000, 500, 200, 300],
            "#Shares Total": [5000, 3000, 4800, 1500],
            "Cost": [150.0, 155.0, 160.0, 148.0],
            "share_holding_ratio": [1.25, 1.20, 0.96, 1.10],
        }
    )


@pytest.fixture
def empty_insider_df():
    """Empty DataFrame with correct insider columns."""
    return pd.DataFrame(
        columns=[
            "Date",
            "Transaction",
            "Insider Trading",
            "Relationship",
            "#Shares",
            "#Shares Total",
            "Cost",
            "share_holding_ratio",
        ]
    )


@pytest.fixture
def sample_call_data():
    """Sample call option chain data for a single expiration date."""
    return pd.DataFrame(
        {
            "strike": [140.0, 145.0, 150.0, 155.0, 160.0],
            "lastPrice": [12.0, 8.0, 5.0, 2.5, 1.0],
            "bid": [11.5, 7.5, 4.8, 2.3, 0.8],
        }
    )


# ---------------------------------------------------------------------------
# InsiderAnalysis.get_insider_summary
# ---------------------------------------------------------------------------
class TestInsiderSummary:

    def test_summary_returns_buy_and_sell_keys(
        self, insider_analysis, sample_insider_df
    ):
        result = insider_analysis.get_insider_summary(sample_insider_df)
        assert "insider_df_buy" in result
        assert "insider_df_sell" in result

    def test_summary_splits_buys_and_sells(
        self, insider_analysis, sample_insider_df
    ):
        result = insider_analysis.get_insider_summary(sample_insider_df)
        buys = result["insider_df_buy"]
        sells = result["insider_df_sell"]
        # 3 rows have ratio >= 1 (buys), 1 row has ratio < 1 (sell)
        assert len(buys) == 3
        assert len(sells) == 1

    def test_summary_sell_has_correct_transaction(
        self, insider_analysis, sample_insider_df
    ):
        result = insider_analysis.get_insider_summary(sample_insider_df)
        sell_records = result["insider_df_sell"]
        assert sell_records[0]["Transaction"] == "Sale"

    def test_summary_adds_tooltip_column(
        self, insider_analysis, sample_insider_df
    ):
        result = insider_analysis.get_insider_summary(sample_insider_df)
        for record in result["insider_df_buy"]:
            assert "Tooltip" in record
            assert "transactionType" in record["Tooltip"]
            assert "Insider" in record["Tooltip"]
            assert "Relationship" in record["Tooltip"]

    def test_summary_empty_df_returns_empty_lists(
        self, insider_analysis, empty_insider_df
    ):
        result = insider_analysis.get_insider_summary(empty_insider_df)
        assert result["insider_df_buy"] == []
        assert result["insider_df_sell"] == []

    def test_summary_preserves_cost_values(
        self, insider_analysis, sample_insider_df
    ):
        result = insider_analysis.get_insider_summary(sample_insider_df)
        all_records = result["insider_df_buy"] + result["insider_df_sell"]
        costs = {r["Cost"] for r in all_records}
        assert costs == {150.0, 155.0, 160.0, 148.0}

    def test_summary_internal_state_updated(
        self, insider_analysis, sample_insider_df
    ):
        """After get_insider_summary, internal buy/sell DataFrames are set."""
        insider_analysis.get_insider_summary(sample_insider_df)
        assert len(insider_analysis.insider_df_buy) == 3
        assert len(insider_analysis.insider_df_sell) == 1


# ---------------------------------------------------------------------------
# OptionsAnalysis.evaluate_call_data
# ---------------------------------------------------------------------------
class TestEvaluateCallData:

    def test_evaluate_call_data_populates_df(
        self, options_analysis, sample_call_data
    ):
        current_price = 152.0
        options_analysis.evaluate_call_data(
            "2024-07-19", sample_call_data, current_price
        )
        df = options_analysis.call_effective_value_df
        assert len(df) == 5

    def test_evaluate_call_data_columns(
        self, options_analysis, sample_call_data
    ):
        options_analysis.evaluate_call_data(
            "2024-07-19", sample_call_data, 152.0
        )
        df = options_analysis.call_effective_value_df
        expected_cols = {
            "expirationDate",
            "strike",
            "effectiveValuePerShare",
            "Tooltip",
        }
        assert set(df.columns) == expected_cols

    def test_effective_value_itm_option(
        self, options_analysis, sample_call_data
    ):
        """In-the-money call (strike=140, price=152) should have positive value."""
        current_price = 152.0
        options_analysis.evaluate_call_data(
            "2024-07-19", sample_call_data, current_price
        )
        df = options_analysis.call_effective_value_df
        row_itm = df[df["strike"] == 140.0].iloc[0]
        # contract_cost = max(12.0, 11.5) = 12.0
        # effective_value = 12.0 + (152.0 - 140.0) = 24.0
        assert row_itm["effectiveValuePerShare"] == 24.0

    def test_effective_value_atm_option(
        self, options_analysis, sample_call_data
    ):
        """Near-the-money call (strike=150, price=152)."""
        current_price = 152.0
        options_analysis.evaluate_call_data(
            "2024-07-19", sample_call_data, current_price
        )
        df = options_analysis.call_effective_value_df
        row_atm = df[df["strike"] == 150.0].iloc[0]
        # contract_cost = max(5.0, 4.8) = 5.0
        # effective_value = 5.0 + (152.0 - 150.0) = 7.0
        assert row_atm["effectiveValuePerShare"] == 7.0

    def test_effective_value_otm_option(
        self, options_analysis, sample_call_data
    ):
        """Out-of-the-money call (strike=160, price=152) is clamped >= 0."""
        current_price = 152.0
        options_analysis.evaluate_call_data(
            "2024-07-19", sample_call_data, current_price
        )
        df = options_analysis.call_effective_value_df
        row_otm = df[df["strike"] == 160.0].iloc[0]
        # contract_cost = max(1.0, 0.8) = 1.0
        # effective_value = max(1.0 + (152.0 - 160.0), 0) = max(-7.0, 0) = 0
        assert row_otm["effectiveValuePerShare"] == 0

    def test_effective_value_never_negative(
        self, options_analysis, sample_call_data
    ):
        """No effective value should ever be negative."""
        options_analysis.evaluate_call_data(
            "2024-07-19", sample_call_data, 120.0
        )
        df = options_analysis.call_effective_value_df
        assert (df["effectiveValuePerShare"] >= 0).all()

    def test_tooltip_contains_strike_and_date(
        self, options_analysis, sample_call_data
    ):
        options_analysis.evaluate_call_data(
            "2024-07-19", sample_call_data, 152.0
        )
        df = options_analysis.call_effective_value_df
        for _, row in df.iterrows():
            assert "2024-07-19" in row["Tooltip"]
            assert str(row["strike"]) in row["Tooltip"]

    def test_evaluate_call_data_zero_bid_and_last_price(self, options_analysis):
        """When both lastPrice and bid are 0, effective_value is 0."""
        call_data = pd.DataFrame(
            {
                "strike": [100.0],
                "lastPrice": [0.0],
                "bid": [0.0],
            }
        )
        options_analysis.evaluate_call_data("2024-07-19", call_data, 105.0)
        df = options_analysis.call_effective_value_df
        assert df.iloc[0]["effectiveValuePerShare"] == 0

    def test_multiple_expiration_dates(self, options_analysis, sample_call_data):
        """Calling evaluate_call_data multiple times appends rows."""
        options_analysis.evaluate_call_data(
            "2024-07-19", sample_call_data, 152.0
        )
        options_analysis.evaluate_call_data(
            "2024-08-16", sample_call_data, 152.0
        )
        df = options_analysis.call_effective_value_df
        assert len(df) == 10
        dates = df["expirationDate"].unique()
        assert set(dates) == {"2024-07-19", "2024-08-16"}
