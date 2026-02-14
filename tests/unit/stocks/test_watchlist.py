"""
Unit tests for watchlist management.
"""

from pathlib import Path

import pytest
import yaml

from assethold.stocks.watchlist import Watchlist


@pytest.fixture
def sample_watchlist_data():
    """Sample watchlist configuration."""
    return {
        "stocks": [
            {
                "ticker": "AAPL",
                "alert_thresholds": {
                    "rsi_oversold": 30,
                    "rsi_overbought": 70,
                },
                "monitoring_frequency": "daily",
            },
            {
                "ticker": "MSFT",
                "alert_thresholds": {
                    "rsi_oversold": 30,
                    "rsi_overbought": 70,
                },
                "monitoring_frequency": "hourly",
            },
            {
                "ticker": "XOM",
                "alert_thresholds": {
                    "rsi_oversold": 35,
                    "rsi_overbought": 65,
                },
                "monitoring_frequency": "daily",
            },
        ],
        "settings": {
            "default_monitoring_frequency": "daily",
        },
    }


@pytest.fixture
def temp_watchlist_file(tmp_path, sample_watchlist_data):
    """Create temporary watchlist file."""
    config_path = tmp_path / "watchlist.yml"
    with open(config_path, "w") as f:
        yaml.dump(sample_watchlist_data, f)
    return config_path


class TestWatchlist:
    """Test Watchlist class."""

    def test_initialization(self, temp_watchlist_file):
        """Test watchlist initializes correctly."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        assert watchlist.config_path == temp_watchlist_file

    def test_load_success(self, temp_watchlist_file, sample_watchlist_data):
        """Test loading watchlist from file."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        data = watchlist.load()

        assert data == sample_watchlist_data
        assert len(data["stocks"]) == 3

    def test_load_missing_file(self, tmp_path):
        """Test loading from non-existent file raises error."""
        config_path = tmp_path / "nonexistent.yml"
        watchlist = Watchlist(config_path=config_path)

        with pytest.raises(FileNotFoundError):
            watchlist.load()

    def test_load_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML raises error."""
        config_path = tmp_path / "invalid.yml"
        config_path.write_text("invalid: yaml: content: [")

        watchlist = Watchlist(config_path=config_path)

        with pytest.raises(ValueError, match="Invalid YAML"):
            watchlist.load()

    def test_get_tickers(self, temp_watchlist_file):
        """Test getting list of tickers."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        tickers = watchlist.get_tickers()

        assert tickers == ["AAPL", "MSFT", "XOM"]

    def test_get_tickers_auto_loads(self, temp_watchlist_file):
        """Test get_tickers auto-loads if not loaded."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        # Don't call load() explicitly
        tickers = watchlist.get_tickers()

        assert len(tickers) == 3

    def test_get_stock_config(self, temp_watchlist_file):
        """Test getting config for specific stock."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        config = watchlist.get_stock_config("AAPL")

        assert config["ticker"] == "AAPL"
        assert config["alert_thresholds"]["rsi_oversold"] == 30
        assert config["monitoring_frequency"] == "daily"

    def test_get_stock_config_case_insensitive(self, temp_watchlist_file):
        """Test ticker lookup is case-insensitive."""
        watchlist = Watchlist(config_path=temp_watchlist_file)

        config1 = watchlist.get_stock_config("AAPL")
        config2 = watchlist.get_stock_config("aapl")
        config3 = watchlist.get_stock_config("AaPl")

        assert config1 == config2 == config3

    def test_get_stock_config_not_found(self, temp_watchlist_file):
        """Test getting config for non-existent ticker."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        config = watchlist.get_stock_config("GOOGL")

        assert config is None

    def test_get_alert_thresholds(self, temp_watchlist_file):
        """Test getting alert thresholds."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        thresholds = watchlist.get_alert_thresholds("AAPL")

        assert thresholds["rsi_oversold"] == 30
        assert thresholds["rsi_overbought"] == 70

    def test_get_alert_thresholds_not_found(self, temp_watchlist_file):
        """Test getting thresholds for non-existent ticker."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        thresholds = watchlist.get_alert_thresholds("GOOGL")

        assert thresholds is None

    def test_get_monitoring_frequency(self, temp_watchlist_file):
        """Test getting monitoring frequency."""
        watchlist = Watchlist(config_path=temp_watchlist_file)

        assert watchlist.get_monitoring_frequency("AAPL") == "daily"
        assert watchlist.get_monitoring_frequency("MSFT") == "hourly"

    def test_get_monitoring_frequency_default(self, temp_watchlist_file):
        """Test default monitoring frequency for non-existent ticker."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        freq = watchlist.get_monitoring_frequency("GOOGL")

        assert freq == "daily"

    def test_save(self, tmp_path, sample_watchlist_data):
        """Test saving watchlist to file."""
        config_path = tmp_path / "new_watchlist.yml"
        watchlist = Watchlist(config_path=config_path)

        watchlist.save(sample_watchlist_data)

        # Verify file was created
        assert config_path.exists()

        # Verify content
        with open(config_path) as f:
            saved_data = yaml.safe_load(f)
        assert saved_data == sample_watchlist_data

    def test_add_stock_new(self, temp_watchlist_file):
        """Test adding new stock to watchlist."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        watchlist.load()

        watchlist.add_stock(
            "GOOGL",
            alert_thresholds={"rsi_oversold": 25, "rsi_overbought": 75},
            monitoring_frequency="daily",
        )

        tickers = watchlist.get_tickers()
        assert "GOOGL" in tickers
        assert len(tickers) == 4

        config = watchlist.get_stock_config("GOOGL")
        assert config["alert_thresholds"]["rsi_oversold"] == 25

    def test_add_stock_update_existing(self, temp_watchlist_file):
        """Test updating existing stock in watchlist."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        watchlist.load()

        initial_tickers = watchlist.get_tickers()

        watchlist.add_stock(
            "AAPL",
            alert_thresholds={"rsi_oversold": 25, "rsi_overbought": 75},
            monitoring_frequency="hourly",
        )

        # Should not add duplicate
        assert watchlist.get_tickers() == initial_tickers

        # Should update config
        config = watchlist.get_stock_config("AAPL")
        assert config["alert_thresholds"]["rsi_oversold"] == 25
        assert config["monitoring_frequency"] == "hourly"

    def test_add_stock_persists(self, temp_watchlist_file):
        """Test added stock is persisted to file."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        watchlist.load()

        watchlist.add_stock("GOOGL", monitoring_frequency="daily")

        # Load fresh instance
        watchlist2 = Watchlist(config_path=temp_watchlist_file)
        assert "GOOGL" in watchlist2.get_tickers()

    def test_remove_stock(self, temp_watchlist_file):
        """Test removing stock from watchlist."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        watchlist.load()

        removed = watchlist.remove_stock("MSFT")

        assert removed is True
        assert "MSFT" not in watchlist.get_tickers()
        assert len(watchlist.get_tickers()) == 2

    def test_remove_stock_case_insensitive(self, temp_watchlist_file):
        """Test removing stock is case-insensitive."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        watchlist.load()

        removed = watchlist.remove_stock("msft")

        assert removed is True
        assert "MSFT" not in watchlist.get_tickers()

    def test_remove_stock_not_found(self, temp_watchlist_file):
        """Test removing non-existent stock."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        watchlist.load()

        removed = watchlist.remove_stock("GOOGL")

        assert removed is False
        assert len(watchlist.get_tickers()) == 3

    def test_remove_stock_persists(self, temp_watchlist_file):
        """Test removed stock is persisted to file."""
        watchlist = Watchlist(config_path=temp_watchlist_file)
        watchlist.load()

        watchlist.remove_stock("MSFT")

        # Load fresh instance
        watchlist2 = Watchlist(config_path=temp_watchlist_file)
        assert "MSFT" not in watchlist2.get_tickers()

    def test_default_config_path(self):
        """Test default config path points to project config directory."""
        watchlist = Watchlist()
        assert "config" in str(watchlist.config_path)
        assert "stocks" in str(watchlist.config_path)
        assert watchlist.config_path.name == "watchlist.yml"
