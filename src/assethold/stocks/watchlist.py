"""
YAML-based stock watchlist management.
"""

from pathlib import Path
from typing import Any, Optional

import yaml


class Watchlist:
    """Manage stock watchlist from YAML configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize watchlist.

        Args:
            config_path: Path to watchlist YAML file
                        (default: config/stocks/watchlist.yml)
        """
        if config_path is None:
            config_path = (
                Path(__file__).parents[3] / "config" / "stocks" / "watchlist.yml"
            )
        self.config_path = Path(config_path)
        self._data = None

    def load(self) -> dict[str, Any]:
        """
        Load watchlist from YAML file.

        Returns:
            Dictionary with watchlist configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If YAML is malformed
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Watchlist config not found: {self.config_path}")

        try:
            with open(self.config_path) as f:
                self._data = yaml.safe_load(f)
            return self._data
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in watchlist config: {e}")

    def get_tickers(self) -> list[str]:
        """
        Get list of all tickers in watchlist.

        Returns:
            List of ticker symbols
        """
        if self._data is None:
            self.load()
        stocks = self._data.get("stocks", [])
        return [stock["ticker"] for stock in stocks]

    def get_stock_config(self, ticker: str) -> Optional[dict[str, Any]]:
        """
        Get configuration for a specific ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Stock configuration dict or None if not found
        """
        if self._data is None:
            self.load()
        stocks = self._data.get("stocks", [])
        for stock in stocks:
            if stock["ticker"].upper() == ticker.upper():
                return stock
        return None

    def get_alert_thresholds(self, ticker: str) -> Optional[dict[str, float]]:
        """
        Get alert thresholds for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with threshold values or None if not configured
        """
        config = self.get_stock_config(ticker)
        if config is None:
            return None
        return config.get("alert_thresholds")

    def get_monitoring_frequency(self, ticker: str) -> str:
        """
        Get monitoring frequency for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Frequency string (e.g., "daily", "hourly") or "daily" as default
        """
        config = self.get_stock_config(ticker)
        if config is None:
            return "daily"
        return config.get("monitoring_frequency", "daily")

    def save(self, data: dict[str, Any]) -> None:
        """
        Save watchlist configuration to YAML file.

        Args:
            data: Watchlist configuration dictionary
        """
        with open(self.config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        self._data = data

    def add_stock(
        self,
        ticker: str,
        alert_thresholds: Optional[dict[str, float]] = None,
        monitoring_frequency: str = "daily",
    ) -> None:
        """
        Add a stock to the watchlist.

        Args:
            ticker: Stock ticker symbol
            alert_thresholds: Alert threshold configuration
            monitoring_frequency: How often to monitor
        """
        if self._data is None:
            self.load()

        stocks = self._data.get("stocks", [])

        # Check if already exists
        for stock in stocks:
            if stock["ticker"].upper() == ticker.upper():
                # Update existing
                stock["alert_thresholds"] = alert_thresholds or {}
                stock["monitoring_frequency"] = monitoring_frequency
                self.save(self._data)
                return

        # Add new stock
        new_stock = {
            "ticker": ticker.upper(),
            "alert_thresholds": alert_thresholds or {},
            "monitoring_frequency": monitoring_frequency,
        }
        stocks.append(new_stock)
        self._data["stocks"] = stocks
        self.save(self._data)

    def remove_stock(self, ticker: str) -> bool:
        """
        Remove a stock from the watchlist.

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if removed, False if not found
        """
        if self._data is None:
            self.load()

        stocks = self._data.get("stocks", [])
        initial_len = len(stocks)

        stocks = [s for s in stocks if s["ticker"].upper() != ticker.upper()]

        if len(stocks) < initial_len:
            self._data["stocks"] = stocks
            self.save(self._data)
            return True
        return False
