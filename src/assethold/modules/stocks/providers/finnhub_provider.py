"""Finnhub API fallback provider returning data in yfinance-compatible format.

Gracefully degrades when finnhub-python is not installed or FINNHUB_API_KEY
is not set.
"""

import logging
import os
import re
import time
from datetime import datetime, timezone

import pandas as pd

logger = logging.getLogger(__name__)

# Columns expected by the insider-transactions consumers
_INSIDER_COLUMNS = [
    "Insider Trading",
    "Relationship",
    "Date",
    "Transaction",
    "Cost",
    "#Shares",
    "Value($)",
    "#Shares Total",
]

# Map yfinance-style period suffixes to days
_PERIOD_MULTIPLIERS = {
    "y": 365,
    "mo": 30,
    "wk": 7,
    "d": 1,
}

# Finnhub transaction codes to human-readable labels
_TRANSACTION_CODE_MAP = {
    "P": "Purchase",
    "S": "Sale",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def is_available() -> bool:
    """Return True when the finnhub package is installed and an API key is set."""
    try:
        import finnhub  # noqa: F401
    except ImportError:
        return False

    return bool(os.environ.get("FINNHUB_API_KEY"))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _get_client():
    """Create and return a finnhub Client using the env-var API key."""
    import finnhub

    return finnhub.Client(api_key=os.environ["FINNHUB_API_KEY"])


def _period_to_timestamps(period: str) -> tuple[int, int]:
    """Convert a yfinance-style period string to *(from_ts, to_ts)* unix timestamps.

    Supported formats: ``"2y"``, ``"6mo"``, ``"4wk"``, ``"5d"``.
    """
    match = re.match(r"^(\d+)(y|mo|wk|d)$", period)
    if not match:
        raise ValueError(
            f"Unsupported period format: {period!r}. "
            f"Expected e.g. '2y', '6mo', '4wk', '5d'."
        )

    count = int(match.group(1))
    unit = match.group(2)
    days = count * _PERIOD_MULTIPLIERS[unit]

    to_ts = int(time.time())
    from_ts = to_ts - days * 86400
    return from_ts, to_ts


# ---------------------------------------------------------------------------
# Data retrieval
# ---------------------------------------------------------------------------
def get_daily_ohlcv(ticker: str, period: str = "2y") -> pd.DataFrame:
    """Fetch daily OHLCV candles and return a DataFrame.

    Columns: Date, Open, High, Low, Close, Volume.

    Raises
    ------
    ValueError
        When Finnhub returns ``status == "no_data"`` for the request.
    """
    from_ts, to_ts = _period_to_timestamps(period)
    client = _get_client()
    response = client.stock_candles(ticker, "D", from_ts, to_ts)

    if response.get("s") == "no_data":
        raise ValueError(f"No candle data returned for {ticker!r} ({period})")

    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(response["t"], unit="s", utc=True),
            "Open": response["o"],
            "High": response["h"],
            "Low": response["l"],
            "Close": response["c"],
            "Volume": response["v"],
        }
    )
    return df


def get_company_info(ticker: str) -> dict:
    """Fetch company profile and return a dict with yfinance-compatible keys.

    Missing fields fall back to sensible defaults (empty string or 0.0).
    """
    client = _get_client()
    profile = client.company_profile2(symbol=ticker)

    market_cap_millions = profile.get("marketCapitalization", 0.0) or 0.0

    return {
        "longName": profile.get("name", ""),
        "marketCap": market_cap_millions * 1e6,
        "sector": profile.get("finnhubIndustry", ""),
        "industry": profile.get("finnhubIndustry", ""),
        "website": profile.get("weburl", ""),
        "country": profile.get("country", ""),
        "currency": profile.get("currency", ""),
        "exchange": profile.get("exchange", ""),
        "symbol": profile.get("ticker", ""),
        "logo": profile.get("logo", ""),
    }


def get_insider_transactions(ticker: str) -> pd.DataFrame:
    """Fetch insider transactions and return a DataFrame with finviz-style columns.

    Columns: Insider Trading, Relationship, Date, Transaction, Cost,
    #Shares, Value($), #Shares Total.
    """
    client = _get_client()
    response = client.stock_insider_transactions(symbol=ticker)

    transactions = response.get("data", [])
    if not transactions:
        return pd.DataFrame(columns=_INSIDER_COLUMNS)

    rows = []
    for txn in transactions:
        share_count = abs(txn.get("share", 0))
        price = txn.get("transactionPrice", 0.0) or 0.0
        code = txn.get("transactionCode", "")

        rows.append(
            {
                "Insider Trading": txn.get("name", ""),
                "Relationship": "",
                "Date": pd.to_datetime(txn.get("transactionDate")),
                "Transaction": _TRANSACTION_CODE_MAP.get(code, code),
                "Cost": price,
                "#Shares": share_count,
                "Value($)": price * share_count,
                "#Shares Total": txn.get("sharesAfter", 0),
            }
        )

    return pd.DataFrame(rows, columns=_INSIDER_COLUMNS)
