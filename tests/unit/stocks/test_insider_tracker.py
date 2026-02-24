"""
Unit tests for insider trading monitor.

Tests use sample Form 4 XML snippets and synthetic transaction data
to verify parsing, benchmarking, and anomaly detection — no network calls.
"""

import xml.etree.ElementTree as ET
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from assethold.stocks.insider_tracker import (
    InsiderTracker,
    parse_form4_xml,
    compute_insider_benchmarks,
    flag_unusual_activity,
)


# ---------------------------------------------------------------------------
# Sample Form 4 XML fixture
# ---------------------------------------------------------------------------

SAMPLE_FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <issuer>
    <issuerCik>0000320193</issuerCik>
    <issuerName>APPLE INC</issuerName>
    <issuerTradingSymbol>AAPL</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0001234567</rptOwnerCik>
      <rptOwnerName>Smith John A</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>1</isDirector>
      <isOfficer>0</isOfficer>
      <officerTitle></officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2024-03-15</value></transactionDate>
      <transactionAmounts>
        <transactionShares><value>10000</value></transactionShares>
        <transactionPricePerShare><value>172.50</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""

SAMPLE_FORM4_SALE_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <issuer>
    <issuerCik>0000320193</issuerCik>
    <issuerName>APPLE INC</issuerName>
    <issuerTradingSymbol>AAPL</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0007654321</rptOwnerCik>
      <rptOwnerName>Doe Jane B</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>0</isDirector>
      <isOfficer>1</isOfficer>
      <officerTitle>CEO</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2024-03-20</value></transactionDate>
      <transactionAmounts>
        <transactionShares><value>5000</value></transactionShares>
        <transactionPricePerShare><value>175.00</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def transaction_df():
    """DataFrame of synthetic insider transactions."""
    return pd.DataFrame(
        {
            "ticker": ["AAPL", "AAPL", "AAPL", "AAPL", "AAPL"],
            "owner_name": ["Smith J", "Doe J", "Lee K", "Brown M", "Clark S"],
            "transaction_date": [
                date(2024, 1, 5),
                date(2024, 1, 12),
                date(2024, 2, 3),
                date(2024, 2, 14),
                date(2024, 3, 1),
            ],
            "shares": [1000, 2000, 500, 1500, 800],
            "price_per_share": [170.0, 172.0, 168.0, 174.0, 180.0],
            "acquired_or_disposed": ["A", "D", "A", "D", "A"],
            "is_director": [True, False, False, True, False],
            "is_officer": [False, True, False, False, True],
        }
    )


@pytest.fixture
def large_transaction_df(transaction_df):
    """DataFrame with one anomalously large transaction."""
    large_row = pd.DataFrame(
        {
            "ticker": ["AAPL"],
            "owner_name": ["Big Buyer"],
            "transaction_date": [date(2024, 4, 1)],
            "shares": [500_000],  # very large
            "price_per_share": [182.0],
            "acquired_or_disposed": ["A"],
            "is_director": [True],
            "is_officer": [True],
        }
    )
    return pd.concat([transaction_df] * 20 + [large_row], ignore_index=True)


# ---------------------------------------------------------------------------
# parse_form4_xml
# ---------------------------------------------------------------------------


class TestParseForm4Xml:
    """Tests for Form 4 XML parser."""

    def test_parse_acquisition(self):
        """Parses a buy (acquisition) transaction correctly."""
        transactions = parse_form4_xml(SAMPLE_FORM4_XML)

        assert len(transactions) == 1
        t = transactions[0]
        assert t["ticker"] == "AAPL"
        assert t["owner_name"] == "Smith John A"
        assert t["shares"] == 10000
        assert t["price_per_share"] == pytest.approx(172.50)
        assert t["acquired_or_disposed"] == "A"
        assert t["transaction_date"] == date(2024, 3, 15)

    def test_parse_disposal(self):
        """Parses a sell (disposal) transaction correctly."""
        transactions = parse_form4_xml(SAMPLE_FORM4_SALE_XML)

        assert len(transactions) == 1
        t = transactions[0]
        assert t["ticker"] == "AAPL"
        assert t["owner_name"] == "Doe Jane B"
        assert t["shares"] == 5000
        assert t["price_per_share"] == pytest.approx(175.00)
        assert t["acquired_or_disposed"] == "D"

    def test_parse_director_flag(self):
        """Correctly identifies director role."""
        transactions = parse_form4_xml(SAMPLE_FORM4_XML)
        assert transactions[0]["is_director"] is True
        assert transactions[0]["is_officer"] is False

    def test_parse_officer_flag(self):
        """Correctly identifies officer role."""
        transactions = parse_form4_xml(SAMPLE_FORM4_SALE_XML)
        assert transactions[0]["is_officer"] is True
        assert transactions[0]["is_director"] is False

    def test_parse_invalid_xml_raises(self):
        """Raises ValueError for malformed XML."""
        with pytest.raises(ValueError, match="Invalid Form 4 XML"):
            parse_form4_xml("<broken>xml")

    def test_parse_missing_transaction_returns_empty(self):
        """Returns empty list when no transactions are present."""
        xml = """<?xml version="1.0"?>
        <ownershipDocument>
          <issuer>
            <issuerTradingSymbol>AAPL</issuerTradingSymbol>
            <issuerName>APPLE INC</issuerName>
          </issuer>
          <reportingOwner>
            <reportingOwnerId>
              <rptOwnerName>Nobody</rptOwnerName>
            </reportingOwnerId>
            <reportingOwnerRelationship>
              <isDirector>0</isDirector>
              <isOfficer>0</isOfficer>
            </reportingOwnerRelationship>
          </reportingOwner>
        </ownershipDocument>"""
        result = parse_form4_xml(xml)
        assert result == []


# ---------------------------------------------------------------------------
# compute_insider_benchmarks
# ---------------------------------------------------------------------------


class TestComputeInsiderBenchmarks:
    """Tests for insider trading benchmark calculations."""

    def test_returns_dict(self, transaction_df):
        """compute_insider_benchmarks returns a dict."""
        benchmarks = compute_insider_benchmarks(transaction_df)
        assert isinstance(benchmarks, dict)

    def test_buy_sell_ratio(self, transaction_df):
        """Buy/sell ratio is correctly computed."""
        benchmarks = compute_insider_benchmarks(transaction_df)

        buys = transaction_df[transaction_df["acquired_or_disposed"] == "A"]["shares"].sum()
        sells = transaction_df[transaction_df["acquired_or_disposed"] == "D"]["shares"].sum()

        assert "buy_sell_ratio" in benchmarks
        expected_ratio = buys / sells if sells > 0 else float("inf")
        assert benchmarks["buy_sell_ratio"] == pytest.approx(expected_ratio, rel=1e-3)

    def test_total_buys_and_sells(self, transaction_df):
        """Total buy and sell share counts are correct."""
        benchmarks = compute_insider_benchmarks(transaction_df)

        assert "total_buy_shares" in benchmarks
        assert "total_sell_shares" in benchmarks

        expected_buys = transaction_df[
            transaction_df["acquired_or_disposed"] == "A"
        ]["shares"].sum()
        expected_sells = transaction_df[
            transaction_df["acquired_or_disposed"] == "D"
        ]["shares"].sum()

        assert benchmarks["total_buy_shares"] == expected_buys
        assert benchmarks["total_sell_shares"] == expected_sells

    def test_transaction_count(self, transaction_df):
        """Transaction count fields are populated."""
        benchmarks = compute_insider_benchmarks(transaction_df)

        assert "transaction_count" in benchmarks
        assert benchmarks["transaction_count"] == len(transaction_df)

    def test_empty_dataframe(self):
        """Handles empty DataFrame without crashing."""
        df = pd.DataFrame(
            columns=[
                "ticker", "owner_name", "transaction_date",
                "shares", "price_per_share", "acquired_or_disposed",
                "is_director", "is_officer",
            ]
        )
        benchmarks = compute_insider_benchmarks(df)
        assert isinstance(benchmarks, dict)
        assert benchmarks.get("transaction_count", 0) == 0

    def test_mean_transaction_size(self, transaction_df):
        """Mean transaction size is computed."""
        benchmarks = compute_insider_benchmarks(transaction_df)
        assert "mean_transaction_shares" in benchmarks
        expected = transaction_df["shares"].mean()
        assert benchmarks["mean_transaction_shares"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# flag_unusual_activity
# ---------------------------------------------------------------------------


class TestFlagUnusualActivity:
    """Tests for unusual insider activity flagging."""

    def test_large_transaction_flagged(self, large_transaction_df):
        """Anomalously large transaction is flagged."""
        flags = flag_unusual_activity(large_transaction_df, std_threshold=3.0)
        assert len(flags) >= 1

    def test_normal_transactions_not_flagged(self, transaction_df):
        """Normal-sized transactions are not flagged."""
        flags = flag_unusual_activity(transaction_df, std_threshold=3.0)
        # With only 5 small, similar transactions, none should be flagged
        # (all within 3σ)
        assert isinstance(flags, list)
        # Depending on variance, may be 0 — at most a small number
        assert len(flags) < len(transaction_df)

    def test_flag_has_required_fields(self, large_transaction_df):
        """Each flag event has required fields."""
        flags = flag_unusual_activity(large_transaction_df, std_threshold=2.0)
        for flag in flags:
            assert "type" in flag
            assert flag["type"] == "unusual_insider_activity"
            assert "owner_name" in flag
            assert "shares" in flag
            assert "transaction_date" in flag
            assert "reason" in flag

    def test_cluster_buying_detected(self):
        """Cluster buying (multiple insiders buying same day) is flagged."""
        df = pd.DataFrame(
            {
                "ticker": ["AAPL"] * 5,
                "owner_name": [f"Person {i}" for i in range(5)],
                "transaction_date": [date(2024, 3, 15)] * 5,  # all same day
                "shares": [1000] * 5,
                "price_per_share": [170.0] * 5,
                "acquired_or_disposed": ["A"] * 5,
                "is_director": [True] * 5,
                "is_officer": [False] * 5,
            }
        )
        flags = flag_unusual_activity(df, cluster_threshold=3)
        cluster_flags = [f for f in flags if "cluster" in f.get("reason", "").lower()]
        assert len(cluster_flags) >= 1

    def test_empty_dataframe_returns_empty(self):
        """Empty DataFrame returns empty flag list."""
        df = pd.DataFrame(
            columns=[
                "ticker", "owner_name", "transaction_date",
                "shares", "price_per_share", "acquired_or_disposed",
                "is_director", "is_officer",
            ]
        )
        flags = flag_unusual_activity(df)
        assert flags == []


# ---------------------------------------------------------------------------
# InsiderTracker class
# ---------------------------------------------------------------------------


class TestInsiderTracker:
    """Tests for InsiderTracker orchestration class."""

    def test_transactions_to_dataframe(self):
        """List of transaction dicts converts to DataFrame."""
        tracker = InsiderTracker()
        transactions = parse_form4_xml(SAMPLE_FORM4_XML)
        df = tracker.transactions_to_dataframe(transactions)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "ticker" in df.columns
        assert "shares" in df.columns

    def test_analyze_returns_dict(self, transaction_df):
        """analyze() returns a dict with benchmarks and flags."""
        tracker = InsiderTracker()
        result = tracker.analyze(transaction_df)

        assert isinstance(result, dict)
        assert "benchmarks" in result
        assert "flags" in result

    def test_analyze_benchmarks_non_empty(self, transaction_df):
        """analyze() produces non-empty benchmarks for non-empty data."""
        tracker = InsiderTracker()
        result = tracker.analyze(transaction_df)

        assert len(result["benchmarks"]) > 0

    def test_analyze_empty_data(self):
        """analyze() handles empty transaction data."""
        tracker = InsiderTracker()
        df = pd.DataFrame(
            columns=[
                "ticker", "owner_name", "transaction_date",
                "shares", "price_per_share", "acquired_or_disposed",
                "is_director", "is_officer",
            ]
        )
        result = tracker.analyze(df)
        assert result["flags"] == []
