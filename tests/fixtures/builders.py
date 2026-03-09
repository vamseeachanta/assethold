"""Deterministic fixture builders for assethold tests.

Importable without conftest — compatible with --noconftest test runs.
"""
import json
import pathlib
from unittest.mock import MagicMock

import pandas as pd

FIXTURE_DIR = pathlib.Path(__file__).parent / "data"


def ohlcv_df(ticker: str = "AAPL") -> pd.DataFrame:
    """Return deterministic OHLCV DataFrame for any ticker."""
    data = json.loads((FIXTURE_DIR / "ohlcv_sample.json").read_text())
    df = pd.DataFrame(data)
    df.index = pd.date_range("2024-01-02", periods=len(df), freq="B")
    df.index.name = "Date"
    return df


def ticker_info(ticker: str = "AAPL") -> dict:
    """Return deterministic ticker info dict."""
    info = json.loads((FIXTURE_DIR / "ticker_info_sample.json").read_text())
    info["symbol"] = ticker
    return info


def sec_filing_data(ticker: str = "AAPL") -> dict:
    """Return deterministic SEC filing data."""
    data = json.loads((FIXTURE_DIR / "sec_filing_sample.json").read_text())
    data["name"] = ticker
    return data


def mock_yfinance_ticker(ticker: str = "AAPL") -> MagicMock:
    """Return a MagicMock that mimics yfinance.Ticker for deterministic tests."""
    mock = MagicMock()
    mock.history.return_value = ohlcv_df(ticker)
    mock.info = ticker_info(ticker)
    mock.options = ("2024-06-21", "2024-09-20")
    mock.option_chain.return_value = MagicMock(
        calls=pd.DataFrame({"strike": [150.0, 155.0], "lastPrice": [5.0, 3.0]}),
        puts=pd.DataFrame({"strike": [150.0, 155.0], "lastPrice": [4.0, 6.0]}),
    )
    return mock


def mock_sec_downloader() -> MagicMock:
    """Return a MagicMock for sec_edgar_downloader.Downloader."""
    mock = MagicMock()
    mock.get.return_value = None
    return mock


def mock_finviz(ticker: str = "AAPL") -> MagicMock:
    """Return a MagicMock for finvizfinance."""
    mock = MagicMock()
    mock.ticker_fundaments.return_value = {"Sector": "Technology", "P/E": "28.5"}
    mock.ticker_description.return_value = f"{ticker} description"
    return mock
