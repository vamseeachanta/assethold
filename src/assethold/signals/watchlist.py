"""
YAML-based stock watchlist management.
"""

from pathlib import Path
from typing import Any, Optional, cast

import yaml


class Watchlist:
    """Manage stock watchlist from YAML configuration.

    The YAML has two top-level blocks: ``stocks:`` (per-ticker config, read
    by the accessor methods below) and ``settings:`` (global knobs). The
    ``settings:`` block is *not* read by this class directly; it is consumed
    by callers via ``load()["settings"]``. In particular
    ``settings.cache_ttl_hours`` is wired through ``watchlist_runner.main`` to
    ``StockDataSource(cache_ttl_hours=...)`` so the cache freshness TTL is
    tunable from one config value (see issue #42; it was orphan config before).

    Cache-TTL precedence for ``StockDataSource`` consumers:

    1. Explicit ``cache_ttl_hours=`` constructor argument (highest).
    2. ``settings.cache_ttl_hours`` from ``watchlist.yml`` (read by
       ``watchlist_runner.main``).
    3. The ``StockDataSource`` default of 24h (lowest).

    Note: the ``daily_strategy`` pipeline (``MarketDataFetcher``) deliberately
    does *not* read this ``settings:`` block. It owns a separate
    ``daily_strategy.yaml:price_cache_ttl_hours`` knob; merging the two is
    tracked as a distinct deduplication concern and is out of scope for #42.
    """

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
        self._data: Optional[dict[str, Any]] = None

    def _ensure_data(self) -> dict[str, Any]:
        """Load and return watchlist data if it is not already cached."""
        if self._data is None:
            return self.load()
        return self._data

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
                loaded = yaml.safe_load(f)
            if loaded is None:
                loaded = {}
            if not isinstance(loaded, dict):
                raise ValueError("Watchlist config must contain a YAML mapping")
            self._data = cast(dict[str, Any], loaded)
            return self._data
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in watchlist config: {e}")

    def get_tickers(self) -> list[str]:
        """
        Get list of all tickers in watchlist.

        Returns:
            List of ticker symbols
        """
        data = self._ensure_data()
        stocks = data.get("stocks", [])
        if not isinstance(stocks, list):
            return []
        return [
            ticker
            for stock in stocks
            if isinstance(stock, dict)
            if isinstance(ticker := stock.get("ticker"), str)
        ]

    def get_stock_config(self, ticker: str) -> Optional[dict[str, Any]]:
        """
        Get configuration for a specific ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Stock configuration dict or None if not found
        """
        data = self._ensure_data()
        stocks = data.get("stocks", [])
        if not isinstance(stocks, list):
            return None
        for stock in stocks:
            if not isinstance(stock, dict):
                continue
            stock_config = cast(dict[str, Any], stock)
            stock_ticker = stock_config.get("ticker")
            if isinstance(stock_ticker, str) and stock_ticker.upper() == ticker.upper():
                return stock_config
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
        thresholds = config.get("alert_thresholds")
        if not isinstance(thresholds, dict):
            return None
        return cast(dict[str, float], thresholds)

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
        frequency = config.get("monitoring_frequency", "daily")
        if not isinstance(frequency, str):
            return "daily"
        return frequency

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
        data = self._ensure_data()

        stocks_value = data.get("stocks", [])
        stocks = stocks_value if isinstance(stocks_value, list) else []

        # Check if already exists
        for stock in stocks:
            if not isinstance(stock, dict):
                continue
            stock_ticker = stock.get("ticker")
            if isinstance(stock_ticker, str) and stock_ticker.upper() == ticker.upper():
                # Update existing
                stock["alert_thresholds"] = alert_thresholds or {}
                stock["monitoring_frequency"] = monitoring_frequency
                self.save(data)
                return

        # Add new stock
        new_stock = {
            "ticker": ticker.upper(),
            "alert_thresholds": alert_thresholds or {},
            "monitoring_frequency": monitoring_frequency,
        }
        stocks.append(new_stock)
        data["stocks"] = stocks
        self.save(data)

    def remove_stock(self, ticker: str) -> bool:
        """
        Remove a stock from the watchlist.

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if removed, False if not found
        """
        data = self._ensure_data()

        stocks_value = data.get("stocks", [])
        stocks = stocks_value if isinstance(stocks_value, list) else []
        initial_len = len(stocks)

        stocks = [
            stock
            for stock in stocks
            if not (
                isinstance(stock, dict)
                and isinstance(stock_ticker := stock.get("ticker"), str)
                and stock_ticker.upper() == ticker.upper()
            )
        ]

        if len(stocks) < initial_len:
            data["stocks"] = stocks
            self.save(data)
            return True
        return False
