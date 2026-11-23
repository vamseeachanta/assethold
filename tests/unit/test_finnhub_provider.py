"""Unit tests for the Finnhub fallback data provider.

All tests mock the finnhub client -- no API calls, no API key needed.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import time

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_finnhub_module():
    """Create a mock finnhub module with a Client class."""
    mock_module = MagicMock()
    mock_client = MagicMock()
    mock_module.Client.return_value = mock_client
    return mock_module, mock_client


@pytest.fixture
def sample_candles():
    """Sample OHLCV candle data as Finnhub returns it."""
    now = int(time.time())
    return {
        "c": [150.0, 152.5, 148.0],
        "h": [155.0, 153.0, 150.0],
        "l": [148.0, 150.0, 146.0],
        "o": [149.0, 151.0, 149.5],
        "s": "ok",
        "t": [now - 172800, now - 86400, now],
        "v": [1000000, 1200000, 900000],
    }


@pytest.fixture
def sample_profile():
    """Sample company profile as Finnhub returns it."""
    return {
        "country": "US",
        "currency": "USD",
        "exchange": "NASDAQ",
        "finnhubIndustry": "Technology",
        "ipo": "1980-12-12",
        "logo": "https://example.com/logo.png",
        "marketCapitalization": 2500000.0,
        "name": "Apple Inc",
        "phone": "1234567890",
        "shareOutstanding": 15000.0,
        "ticker": "AAPL",
        "weburl": "https://apple.com",
    }


@pytest.fixture
def sample_insider_transactions():
    """Sample insider transactions as Finnhub returns them."""
    return {
        "data": [
            {
                "name": "John Doe",
                "share": 5000,
                "change": 5000,
                "filingDate": "2024-01-15",
                "transactionDate": "2024-01-10",
                "transactionCode": "P",
                "transactionPrice": 150.0,
            },
            {
                "name": "Jane Smith",
                "share": -3000,
                "change": -3000,
                "filingDate": "2024-01-20",
                "transactionDate": "2024-01-18",
                "transactionCode": "S",
                "transactionPrice": 155.0,
            },
        ],
        "symbol": "AAPL",
    }


# ---------------------------------------------------------------------------
# TestFinnhubAvailability
# ---------------------------------------------------------------------------
class TestFinnhubAvailability:
    """Tests for is_available() function."""

    def test_available_when_package_and_key_present(self):
        mock_module = MagicMock()
        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            result = finnhub_provider.is_available()
            assert result is True

    def test_unavailable_when_no_package(self):
        with patch.dict("sys.modules", {"finnhub": None}):
            from assethold.modules.stocks.providers import finnhub_provider

            result = finnhub_provider.is_available()
            assert result is False

    def test_unavailable_when_no_api_key(self):
        mock_module = MagicMock()
        env = {k: v for k, v in __import__("os").environ.items() if k != "FINNHUB_API_KEY"}
        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", env, clear=True),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            result = finnhub_provider.is_available()
            assert result is False


# ---------------------------------------------------------------------------
# TestFinnhubDailyOHLCV
# ---------------------------------------------------------------------------
class TestFinnhubDailyOHLCV:
    """Tests for get_daily_ohlcv() function."""

    def test_returns_dataframe_with_correct_columns(
        self, mock_finnhub_module, sample_candles
    ):
        mock_module, mock_client = mock_finnhub_module
        mock_client.stock_candles.return_value = sample_candles

        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            df = finnhub_provider.get_daily_ohlcv("AAPL", period="2y")

        expected_cols = {"Date", "Open", "High", "Low", "Close", "Volume"}
        assert set(df.columns) == expected_cols
        assert len(df) == 3

    def test_converts_timestamps_to_datetime(
        self, mock_finnhub_module, sample_candles
    ):
        mock_module, mock_client = mock_finnhub_module
        mock_client.stock_candles.return_value = sample_candles

        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            df = finnhub_provider.get_daily_ohlcv("AAPL", period="1y")

        assert pd.api.types.is_datetime64_any_dtype(df["Date"])

    def test_period_to_timestamp_conversion(self):
        from assethold.modules.stocks.providers import finnhub_provider

        now = int(time.time())
        from_ts, to_ts = finnhub_provider._period_to_timestamps("2y")

        expected_from = now - (2 * 365 * 86400)
        # Allow 2 seconds of tolerance for execution time
        assert abs(to_ts - now) < 2
        assert abs(from_ts - expected_from) < 2

    def test_period_to_timestamp_months(self):
        from assethold.modules.stocks.providers import finnhub_provider

        now = int(time.time())
        from_ts, to_ts = finnhub_provider._period_to_timestamps("6mo")

        expected_from = now - (6 * 30 * 86400)
        assert abs(to_ts - now) < 2
        assert abs(from_ts - expected_from) < 2

    def test_period_to_timestamp_days(self):
        from assethold.modules.stocks.providers import finnhub_provider

        now = int(time.time())
        from_ts, to_ts = finnhub_provider._period_to_timestamps("5d")

        expected_from = now - (5 * 1 * 86400)
        assert abs(to_ts - now) < 2
        assert abs(from_ts - expected_from) < 2

    def test_period_to_timestamp_weeks(self):
        from assethold.modules.stocks.providers import finnhub_provider

        now = int(time.time())
        from_ts, to_ts = finnhub_provider._period_to_timestamps("4wk")

        expected_from = now - (4 * 7 * 86400)
        assert abs(to_ts - now) < 2
        assert abs(from_ts - expected_from) < 2

    def test_raises_on_no_data(self, mock_finnhub_module):
        mock_module, mock_client = mock_finnhub_module
        mock_client.stock_candles.return_value = {"s": "no_data"}

        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            with pytest.raises(ValueError, match="No candle data"):
                finnhub_provider.get_daily_ohlcv("INVALID", period="2y")


# ---------------------------------------------------------------------------
# TestFinnhubCompanyInfo
# ---------------------------------------------------------------------------
class TestFinnhubCompanyInfo:
    """Tests for get_company_info() function."""

    def test_returns_dict_with_yfinance_compatible_keys(
        self, mock_finnhub_module, sample_profile
    ):
        mock_module, mock_client = mock_finnhub_module
        mock_client.company_profile2.return_value = sample_profile

        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            info = finnhub_provider.get_company_info("AAPL")

        expected_keys = {
            "longName",
            "marketCap",
            "sector",
            "industry",
            "website",
            "country",
            "currency",
            "exchange",
            "symbol",
            "logo",
        }
        assert expected_keys.issubset(set(info.keys()))
        assert info["longName"] == "Apple Inc"
        assert info["sector"] == "Technology"
        assert info["industry"] == "Technology"
        assert info["website"] == "https://apple.com"
        assert info["country"] == "US"
        assert info["currency"] == "USD"
        assert info["exchange"] == "NASDAQ"
        assert info["symbol"] == "AAPL"

    def test_market_cap_uses_correct_value(
        self, mock_finnhub_module, sample_profile
    ):
        mock_module, mock_client = mock_finnhub_module
        mock_client.company_profile2.return_value = sample_profile

        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            info = finnhub_provider.get_company_info("AAPL")

        # Finnhub returns marketCapitalization in millions
        assert info["marketCap"] == 2500000.0 * 1e6

    def test_handles_missing_fields_gracefully(self, mock_finnhub_module):
        mock_module, mock_client = mock_finnhub_module
        # Minimal profile with only a few fields
        mock_client.company_profile2.return_value = {
            "name": "Test Corp",
            "ticker": "TEST",
        }

        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            info = finnhub_provider.get_company_info("TEST")

        # Should not raise KeyError; missing fields get defaults
        assert info["longName"] == "Test Corp"
        assert info["marketCap"] == 0.0
        assert info["sector"] == ""
        assert info["industry"] == ""
        assert info["website"] == ""


# ---------------------------------------------------------------------------
# TestFinnhubInsiderTransactions
# ---------------------------------------------------------------------------
class TestFinnhubInsiderTransactions:
    """Tests for get_insider_transactions() function."""

    def test_returns_dataframe_with_correct_columns(
        self, mock_finnhub_module, sample_insider_transactions
    ):
        mock_module, mock_client = mock_finnhub_module
        mock_client.stock_insider_transactions.return_value = (
            sample_insider_transactions
        )

        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            df = finnhub_provider.get_insider_transactions("AAPL")

        expected_cols = {
            "Insider Trading",
            "Relationship",
            "Date",
            "Transaction",
            "Cost",
            "#Shares",
            "Value($)",
            "#Shares Total",
        }
        assert set(df.columns) == expected_cols
        assert len(df) == 2

    def test_maps_transaction_types(
        self, mock_finnhub_module, sample_insider_transactions
    ):
        mock_module, mock_client = mock_finnhub_module
        mock_client.stock_insider_transactions.return_value = (
            sample_insider_transactions
        )

        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            df = finnhub_provider.get_insider_transactions("AAPL")

        assert df.iloc[0]["Transaction"] == "Purchase"
        assert df.iloc[1]["Transaction"] == "Sale"

    def test_calculates_value_correctly(
        self, mock_finnhub_module, sample_insider_transactions
    ):
        mock_module, mock_client = mock_finnhub_module
        mock_client.stock_insider_transactions.return_value = (
            sample_insider_transactions
        )

        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            df = finnhub_provider.get_insider_transactions("AAPL")

        # Purchase: 150.0 * abs(5000) = 750000.0
        assert df.iloc[0]["Value($)"] == 750000.0
        # Sale: 155.0 * abs(-3000) = 465000.0
        assert df.iloc[1]["Value($)"] == 465000.0

    def test_uses_absolute_share_count(
        self, mock_finnhub_module, sample_insider_transactions
    ):
        mock_module, mock_client = mock_finnhub_module
        mock_client.stock_insider_transactions.return_value = (
            sample_insider_transactions
        )

        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            df = finnhub_provider.get_insider_transactions("AAPL")

        assert df.iloc[0]["#Shares"] == 5000
        assert df.iloc[1]["#Shares"] == 3000

    def test_empty_transactions_returns_empty_dataframe(
        self, mock_finnhub_module
    ):
        mock_module, mock_client = mock_finnhub_module
        mock_client.stock_insider_transactions.return_value = {
            "data": [],
            "symbol": "AAPL",
        }

        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            df = finnhub_provider.get_insider_transactions("AAPL")

        expected_cols = {
            "Insider Trading",
            "Relationship",
            "Date",
            "Transaction",
            "Cost",
            "#Shares",
            "Value($)",
            "#Shares Total",
        }
        assert set(df.columns) == expected_cols
        assert len(df) == 0

    def test_handles_no_data_key(self, mock_finnhub_module):
        mock_module, mock_client = mock_finnhub_module
        mock_client.stock_insider_transactions.return_value = {}

        with (
            patch.dict("sys.modules", {"finnhub": mock_module}),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
        ):
            from assethold.modules.stocks.providers import finnhub_provider

            df = finnhub_provider.get_insider_transactions("AAPL")

        assert len(df) == 0
