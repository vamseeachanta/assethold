"""
Unit tests for stock data sources.

Tests use mocked yfinance to avoid external dependencies.
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from assethold.signals.data_sources import StockDataSource


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def mock_yfinance_data():
    """Create mock data returned by yfinance."""
    dates = pd.date_range("2024-01-01", periods=30)
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": [100 + i for i in range(30)],
            "High": [102 + i for i in range(30)],
            "Low": [99 + i for i in range(30)],
            "Close": [101 + i for i in range(30)],
            "Volume": [1000000 + i * 10000 for i in range(30)],
        }
    ).set_index("Date")


class TestStockDataSource:
    """Test StockDataSource class."""

    def test_initialization(self, temp_cache_dir):
        """Test data source initializes correctly."""
        source = StockDataSource(cache_dir=temp_cache_dir, cache_ttl_hours=12)

        assert source.cache_dir == temp_cache_dir
        assert source.cache_ttl == timedelta(hours=12)
        assert source.rate_limit == 2.0

    def test_default_cache_dir(self):
        """Test default cache directory is created."""
        source = StockDataSource()
        assert source.cache_dir.exists()
        # Should be relative to project root
        assert "stocks" in str(source.cache_dir)
        assert "cache" in str(source.cache_dir)

    def test_cache_path_generation(self, temp_cache_dir):
        """Test cache file path generation."""
        source = StockDataSource(cache_dir=temp_cache_dir)

        path1 = source._get_cache_path("AAPL", "2024-01-01", "2024-01-31")
        path2 = source._get_cache_path("AAPL", "2024-01-01", "2024-01-31")
        path3 = source._get_cache_path("MSFT", "2024-01-01", "2024-01-31")

        # Same ticker and dates should produce same path
        assert path1 == path2

        # Different ticker should produce different path
        assert path1 != path3

        # Path should be in cache dir
        assert path1.parent == temp_cache_dir

    def test_cache_validity_fresh(self, temp_cache_dir):
        """Test cache validity check for fresh cache."""
        source = StockDataSource(cache_dir=temp_cache_dir, cache_ttl_hours=24)

        # Create a fresh cache file
        cache_file = temp_cache_dir / "test.csv"
        cache_file.write_text("test")

        assert source._is_cache_valid(cache_file)

    def test_cache_validity_expired(self, temp_cache_dir):
        """Test cache validity check for expired cache."""
        source = StockDataSource(cache_dir=temp_cache_dir, cache_ttl_hours=1)

        # Create an old cache file
        cache_file = temp_cache_dir / "test.csv"
        cache_file.write_text("test")

        # Manually set old mtime (2 hours ago)
        old_time = datetime.now() - timedelta(hours=2)
        import os
        os.utime(cache_file, (old_time.timestamp(), old_time.timestamp()))

        assert not source._is_cache_valid(cache_file)

    def test_cache_validity_missing(self, temp_cache_dir):
        """Test cache validity check for missing file."""
        source = StockDataSource(cache_dir=temp_cache_dir)
        cache_file = temp_cache_dir / "nonexistent.csv"

        assert not source._is_cache_valid(cache_file)

    @patch("yfinance.Ticker")
    def test_fetch_success(self, mock_ticker_class, temp_cache_dir, mock_yfinance_data):
        """Test successful data fetch."""
        # Mock yfinance Ticker
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_yfinance_data
        mock_ticker_class.return_value = mock_ticker

        source = StockDataSource(cache_dir=temp_cache_dir)
        df = source.fetch("AAPL", "2024-01-01", "2024-01-31", use_cache=False)

        # Verify yfinance was called correctly
        mock_ticker_class.assert_called_once_with("AAPL")
        mock_ticker.history.assert_called_once_with(
            start="2024-01-01",
            end="2024-01-31"
        )

        # Verify output format
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
        assert len(df) == 30

    @patch("yfinance.Ticker")
    def test_fetch_caches_result(self, mock_ticker_class, temp_cache_dir, mock_yfinance_data):
        """Test fetch caches the result."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_yfinance_data
        mock_ticker_class.return_value = mock_ticker

        source = StockDataSource(cache_dir=temp_cache_dir)
        df = source.fetch("AAPL", "2024-01-01", "2024-01-31", use_cache=False)

        # Verify cache file was created
        cache_files = list(temp_cache_dir.glob("AAPL_*.csv"))
        assert len(cache_files) == 1

        # Verify cached data matches
        cached_df = pd.read_csv(cache_files[0], parse_dates=["date"])
        pd.testing.assert_frame_equal(df, cached_df)

    @patch("yfinance.Ticker")
    def test_fetch_uses_cache(self, mock_ticker_class, temp_cache_dir, mock_yfinance_data):
        """Test fetch uses cached data when available."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_yfinance_data
        mock_ticker_class.return_value = mock_ticker

        source = StockDataSource(cache_dir=temp_cache_dir)

        # First fetch (should hit network)
        df1 = source.fetch("AAPL", "2024-01-01", "2024-01-31", use_cache=True)
        assert mock_ticker_class.call_count == 1

        # Second fetch (should use cache)
        df2 = source.fetch("AAPL", "2024-01-01", "2024-01-31", use_cache=True)
        assert mock_ticker_class.call_count == 1  # Still only 1 call

        # Data should be identical
        pd.testing.assert_frame_equal(df1, df2)

    def test_fetch_invalid_ticker(self, temp_cache_dir):
        """Test fetch with invalid ticker."""
        source = StockDataSource(cache_dir=temp_cache_dir)

        with pytest.raises(ValueError, match="Ticker symbol cannot be empty"):
            source.fetch("", "2024-01-01", "2024-01-31")

    def test_fetch_invalid_date_format(self, temp_cache_dir):
        """Test fetch with invalid date format."""
        source = StockDataSource(cache_dir=temp_cache_dir)

        with pytest.raises(ValueError, match="Invalid date format"):
            source.fetch("AAPL", "01/01/2024", "2024-01-31")

        with pytest.raises(ValueError, match="Invalid date format"):
            source.fetch("AAPL", "2024-01-01", "Jan 31, 2024")

    @patch("yfinance.Ticker")
    def test_fetch_empty_result(self, mock_ticker_class, temp_cache_dir):
        """Test fetch when no data is returned."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_class.return_value = mock_ticker

        source = StockDataSource(cache_dir=temp_cache_dir)

        with pytest.raises(ConnectionError, match="Failed to fetch data"):
            source.fetch("INVALID", "2024-01-01", "2024-01-31", use_cache=False)

    @patch("yfinance.Ticker")
    def test_fetch_network_error(self, mock_ticker_class, temp_cache_dir):
        """Test fetch when network error occurs."""
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("Network error")
        mock_ticker_class.return_value = mock_ticker

        source = StockDataSource(cache_dir=temp_cache_dir)

        with pytest.raises(ConnectionError, match="Failed to fetch data"):
            source.fetch("AAPL", "2024-01-01", "2024-01-31", use_cache=False)

    @patch("yfinance.Ticker")
    def test_fetch_batch(self, mock_ticker_class, temp_cache_dir, mock_yfinance_data):
        """Test batch fetching of multiple tickers."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_yfinance_data
        mock_ticker_class.return_value = mock_ticker

        source = StockDataSource(cache_dir=temp_cache_dir, rate_limit_seconds=0.1)

        tickers = ["AAPL", "MSFT", "GOOGL"]
        results = source.fetch_batch(tickers, "2024-01-01", "2024-01-31", use_cache=False)

        # Verify all tickers were fetched
        assert len(results) == 3
        assert all(ticker in results for ticker in tickers)
        assert all(isinstance(df, pd.DataFrame) for df in results.values())

    @patch("yfinance.Ticker")
    def test_fetch_batch_with_errors(self, mock_ticker_class, temp_cache_dir):
        """Test batch fetch continues on errors."""
        def mock_history(start, end):
            # Simulate error for MSFT
            if mock_ticker_class.call_count == 2:
                raise Exception("Error")
            return pd.DataFrame({
                "Date": pd.date_range(start, periods=5),
                "Open": [100] * 5,
                "High": [101] * 5,
                "Low": [99] * 5,
                "Close": [100] * 5,
                "Volume": [1000000] * 5,
            }).set_index("Date")

        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = mock_history
        mock_ticker_class.return_value = mock_ticker

        source = StockDataSource(cache_dir=temp_cache_dir, rate_limit_seconds=0.1)

        results = source.fetch_batch(["AAPL", "MSFT", "GOOGL"], "2024-01-01", "2024-01-05")

        # AAPL and GOOGL should succeed, MSFT should be None
        assert results["AAPL"] is not None
        assert results["MSFT"] is None
        assert results["GOOGL"] is not None

    def test_clear_cache_all(self, temp_cache_dir):
        """Test clearing all cache files."""
        # Create some cache files
        (temp_cache_dir / "AAPL_abc123.csv").write_text("test")
        (temp_cache_dir / "MSFT_def456.csv").write_text("test")
        (temp_cache_dir / "GOOGL_ghi789.csv").write_text("test")

        source = StockDataSource(cache_dir=temp_cache_dir)
        deleted = source.clear_cache()

        assert deleted == 3
        assert len(list(temp_cache_dir.glob("*.csv"))) == 0

    def test_clear_cache_specific_ticker(self, temp_cache_dir):
        """Test clearing cache for specific ticker."""
        (temp_cache_dir / "AAPL_abc123.csv").write_text("test")
        (temp_cache_dir / "AAPL_xyz999.csv").write_text("test")
        (temp_cache_dir / "MSFT_def456.csv").write_text("test")

        source = StockDataSource(cache_dir=temp_cache_dir)
        deleted = source.clear_cache(ticker="AAPL")

        assert deleted == 2
        # MSFT cache should still exist
        assert (temp_cache_dir / "MSFT_def456.csv").exists()
