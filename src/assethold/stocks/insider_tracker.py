"""
Insider trading monitor for SEC EDGAR Form 4 filings.

Provides:
- Form 4 XML parser
- Insider trading benchmark calculations
- Unusual activity flagging (large transactions, cluster buying)
"""

import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

import numpy as np
import pandas as pd


def _get_text(element: ET.Element, path: str, default: str = "") -> str:
    """Extract text from an XML element at path, returning default if absent."""
    node = element.find(path)
    if node is None or node.text is None:
        return default
    return node.text.strip()


def _parse_date(date_str: str) -> date:
    """Parse ISO date string (YYYY-MM-DD) to a date object."""
    return date.fromisoformat(date_str.strip())


def parse_form4_xml(xml_content: str) -> list[dict[str, Any]]:
    """
    Parse a SEC EDGAR Form 4 XML filing into a list of transaction dicts.

    Each dict contains:
        ticker, owner_name, transaction_date, shares,
        price_per_share, acquired_or_disposed, is_director, is_officer

    Args:
        xml_content: Raw XML string of a Form 4 filing

    Returns:
        List of transaction dicts (empty if no transactions found)

    Raises:
        ValueError: If xml_content is not parseable XML
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid Form 4 XML: {exc}") from exc

    ticker = _get_text(root, "./issuer/issuerTradingSymbol")
    owner_name = _get_text(
        root, "./reportingOwner/reportingOwnerId/rptOwnerName"
    )

    rel = root.find("./reportingOwner/reportingOwnerRelationship")
    is_director = False
    is_officer = False
    if rel is not None:
        is_director = _get_text(rel, "isDirector", "0") == "1"
        is_officer = _get_text(rel, "isOfficer", "0") == "1"

    transactions: list[dict[str, Any]] = []

    for txn in root.findall("./nonDerivativeTable/nonDerivativeTransaction"):
        date_str = _get_text(txn, "transactionDate/value")
        shares_str = _get_text(txn, "transactionAmounts/transactionShares/value")
        price_str = _get_text(
            txn,
            "transactionAmounts/transactionPricePerShare/value",
        )
        code = _get_text(
            txn,
            "transactionAmounts/transactionAcquiredDisposedCode/value",
        )

        if not (date_str and shares_str):
            continue

        try:
            txn_date = _parse_date(date_str)
            shares = int(float(shares_str))
            price = float(price_str) if price_str else 0.0
        except (ValueError, TypeError):
            continue

        transactions.append(
            {
                "ticker": ticker,
                "owner_name": owner_name,
                "transaction_date": txn_date,
                "shares": shares,
                "price_per_share": price,
                "acquired_or_disposed": code.upper(),
                "is_director": is_director,
                "is_officer": is_officer,
            }
        )

    return transactions


def compute_insider_benchmarks(df: pd.DataFrame) -> dict[str, Any]:
    """
    Compute benchmark statistics from a DataFrame of insider transactions.

    Args:
        df: DataFrame with columns: ticker, owner_name, transaction_date,
            shares, price_per_share, acquired_or_disposed,
            is_director, is_officer

    Returns:
        Dict with:
            transaction_count, total_buy_shares, total_sell_shares,
            buy_sell_ratio, mean_transaction_shares, std_transaction_shares
    """
    if df.empty:
        return {
            "transaction_count": 0,
            "total_buy_shares": 0,
            "total_sell_shares": 0,
            "buy_sell_ratio": 0.0,
            "mean_transaction_shares": 0.0,
            "std_transaction_shares": 0.0,
        }

    buys = df[df["acquired_or_disposed"] == "A"]
    sells = df[df["acquired_or_disposed"] == "D"]

    total_buys = int(buys["shares"].sum())
    total_sells = int(sells["shares"].sum())

    if total_sells > 0:
        buy_sell_ratio = total_buys / total_sells
    else:
        buy_sell_ratio = float("inf") if total_buys > 0 else 0.0

    mean_shares = float(df["shares"].mean())
    std_shares = float(df["shares"].std(ddof=1)) if len(df) > 1 else 0.0

    return {
        "transaction_count": len(df),
        "total_buy_shares": total_buys,
        "total_sell_shares": total_sells,
        "buy_sell_ratio": buy_sell_ratio,
        "mean_transaction_shares": mean_shares,
        "std_transaction_shares": std_shares,
    }


def flag_unusual_activity(
    df: pd.DataFrame,
    std_threshold: float = 3.0,
    cluster_threshold: int = 3,
) -> list[dict[str, Any]]:
    """
    Flag insider transactions that deviate significantly from norms.

    Flags two patterns:
    1. Transactions with shares > mean + std_threshold * std (large txn)
    2. Multiple insiders buying on the same day (cluster buying)

    Args:
        df: DataFrame of insider transactions
        std_threshold: Standard deviation multiplier for large transaction
        cluster_threshold: Minimum distinct insiders buying same day to flag

    Returns:
        List of flag dicts with keys: type, owner_name, shares,
        transaction_date, reason
    """
    if df.empty:
        return []

    flags: list[dict[str, Any]] = []

    # --- Large transaction detection ---
    if len(df) > 1:
        mean_shares = df["shares"].mean()
        std_shares = df["shares"].std(ddof=1)
        if std_shares > 0:
            threshold = mean_shares + std_threshold * std_shares
            large = df[df["shares"] > threshold]
            for _, row in large.iterrows():
                std_multiples = (row["shares"] - mean_shares) / std_shares
                flags.append(
                    {
                        "type": "unusual_insider_activity",
                        "owner_name": row["owner_name"],
                        "shares": int(row["shares"]),
                        "transaction_date": row["transaction_date"],
                        "reason": (
                            f"large transaction: {std_multiples:.1f} std "
                            f"above mean"
                        ),
                    }
                )

    # --- Cluster buying detection ---
    buys = df[df["acquired_or_disposed"] == "A"].copy()
    if not buys.empty:
        daily_buyers = (
            buys.groupby("transaction_date")["owner_name"]
            .nunique()
        )
        cluster_dates = daily_buyers[daily_buyers >= cluster_threshold].index

        for txn_date in cluster_dates:
            flags.append(
                {
                    "type": "unusual_insider_activity",
                    "owner_name": "multiple",
                    "shares": int(
                        buys[buys["transaction_date"] == txn_date]["shares"].sum()
                    ),
                    "transaction_date": txn_date,
                    "reason": (
                        f"cluster buying: {daily_buyers[txn_date]} insiders "
                        f"bought on {txn_date}"
                    ),
                }
            )

    return flags


class InsiderTracker:
    """
    Orchestrates Form 4 parsing, benchmarking, and anomaly detection.

    Usage::

        tracker = InsiderTracker()
        transactions = parse_form4_xml(xml_content)
        df = tracker.transactions_to_dataframe(transactions)
        result = tracker.analyze(df)
    """

    def transactions_to_dataframe(
        self, transactions: list[dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Convert a list of transaction dicts to a DataFrame.

        Args:
            transactions: List of dicts from parse_form4_xml()

        Returns:
            DataFrame with standardized columns
        """
        if not transactions:
            return pd.DataFrame(
                columns=[
                    "ticker",
                    "owner_name",
                    "transaction_date",
                    "shares",
                    "price_per_share",
                    "acquired_or_disposed",
                    "is_director",
                    "is_officer",
                ]
            )
        return pd.DataFrame(transactions)

    def analyze(
        self,
        df: pd.DataFrame,
        std_threshold: float = 3.0,
        cluster_threshold: int = 3,
    ) -> dict[str, Any]:
        """
        Compute benchmarks and flag unusual activity.

        Args:
            df: DataFrame of insider transactions
            std_threshold: Std deviation threshold for large transactions
            cluster_threshold: Min insiders buying same day for cluster flag

        Returns:
            Dict with keys: benchmarks (dict), flags (list)
        """
        return {
            "benchmarks": compute_insider_benchmarks(df),
            "flags": flag_unusual_activity(
                df,
                std_threshold=std_threshold,
                cluster_threshold=cluster_threshold,
            ),
        }
