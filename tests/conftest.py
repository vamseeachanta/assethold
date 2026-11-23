# ABOUTME: Pytest configuration and shared fixtures for assethold financial testing.
# ABOUTME: Mocks heavy external dependencies and provides reusable financial data fixtures.

import sys
from unittest.mock import MagicMock

# Mock heavy external dependencies that may not be installed
_mock_modules = [
    'ffn', 'yfinance', 'yahoo_fin', 'yahoo_fin.stock_info',
    'finvizfinance', 'finvizfinance.quote', 'sec_edgar_downloader',
    'ta', 'diskcache', 'finnhub', 'plotly', 'plotly.express',
    'plotly.graph_objects', 'plotly.subplots', 'plotly.io',
    'dash', 'dash_bootstrap_components',
]

for module_name in _mock_modules:
    sys.modules[module_name] = MagicMock()

import pytest
import os
import tempfile
from pathlib import Path
from typing import Generator, Any, Dict
from unittest.mock import Mock, patch
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

os.environ['TESTING'] = 'true'


@pytest.fixture(scope="session")
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="function")
def mock_logger():
    """Mock logger for testing."""
    return Mock()


@pytest.fixture(scope="function")
def sample_asset_data() -> Dict[str, Any]:
    """Sample asset data for testing financial operations."""
    return {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "market_cap": 3000000000000,
        "price": 180.50,
        "pe_ratio": 25.5,
        "dividend_yield": 0.44,
        "beta": 1.2,
        "metadata": {
            "exchange": "NASDAQ",
            "last_updated": "2025-01-01T00:00:00Z",
            "tags": ["tech", "large-cap"]
        }
    }


@pytest.fixture(scope="function")
def sample_portfolio_data() -> Dict[str, Any]:
    """Sample portfolio data for testing."""
    return {
        "portfolio_id": "test_portfolio_001",
        "name": "Test Portfolio",
        "description": "A test portfolio for testing purposes",
        "total_value": 100000.00,
        "cash_balance": 5000.00,
        "positions": [
            {"symbol": "AAPL", "shares": 100, "avg_cost": 150.00},
            {"symbol": "MSFT", "shares": 50, "avg_cost": 300.00},
            {"symbol": "GOOGL", "shares": 25, "avg_cost": 2500.00}
        ],
        "created_at": "2025-01-01T00:00:00Z"
    }


@pytest.fixture(scope="function")
def sample_price_data() -> pd.DataFrame:
    """Sample price data DataFrame for testing."""
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    prices = np.random.uniform(100, 200, len(dates))

    return pd.DataFrame({
        'Date': dates,
        'Open': prices * np.random.uniform(0.99, 1.01, len(dates)),
        'High': prices * np.random.uniform(1.01, 1.05, len(dates)),
        'Low': prices * np.random.uniform(0.95, 0.99, len(dates)),
        'Close': prices,
        'Volume': np.random.randint(1000000, 10000000, len(dates))
    }).set_index('Date')


@pytest.fixture(scope="function")
def sample_financial_statement() -> Dict[str, Any]:
    """Sample financial statement data for testing."""
    return {
        "symbol": "AAPL",
        "period": "Q4 2024",
        "revenue": 123456789000,
        "gross_profit": 67890123000,
        "operating_income": 45678901000,
        "net_income": 34567890000,
        "total_assets": 456789012000,
        "total_liabilities": 234567890000,
        "shareholders_equity": 222221122000,
        "cash_and_equivalents": 45678901000,
        "debt": 98765432000
    }


@pytest.fixture(scope="function")
def temp_excel_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary Excel file for testing."""
    test_file = temp_dir / "test_data.xlsx"
    df = pd.DataFrame({
        'Symbol': ['AAPL', 'MSFT', 'GOOGL'],
        'Price': [180.50, 420.25, 2750.00],
        'Volume': [50000000, 25000000, 1500000]
    })
    df.to_excel(test_file, index=False)
    yield test_file


@pytest.fixture(scope="function")
def temp_csv_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary CSV file for testing."""
    test_file = temp_dir / "test_data.csv"
    df = pd.DataFrame({
        'Date': pd.date_range('2024-01-01', periods=100),
        'Symbol': ['AAPL'] * 100,
        'Close': np.random.uniform(150, 200, 100)
    })
    df.to_csv(test_file, index=False)
    yield test_file


@pytest.fixture(scope="function")
def mock_yfinance():
    """Mock yfinance for testing financial data fetching."""
    with patch('yfinance.Ticker') as mock_ticker:
        mock_info = {
            'longName': 'Apple Inc.',
            'symbol': 'AAPL',
            'marketCap': 3000000000000,
            'beta': 1.2,
            'dividendYield': 0.0044
        }

        mock_hist = pd.DataFrame({
            'Open': [180.0, 181.0, 179.0],
            'High': [182.0, 183.0, 181.0],
            'Low': [179.0, 180.0, 178.0],
            'Close': [181.0, 182.0, 180.0],
            'Volume': [50000000, 48000000, 52000000]
        }, index=pd.date_range('2024-01-01', periods=3))

        mock_ticker.return_value.info = mock_info
        mock_ticker.return_value.history.return_value = mock_hist
        yield mock_ticker


@pytest.fixture(scope="function")
def mock_web_scraping():
    """Mock web scraping libraries for testing."""
    with patch('requests.Session') as mock_session:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>Test financial data</body></html>'
        mock_response.json.return_value = {
            "status": "success",
            "data": {"price": 180.50, "volume": 50000000}
        }
        mock_session.return_value.get.return_value = mock_response
        yield mock_session


@pytest.fixture(scope="function")
def mock_database():
    """Mock SQLAlchemy database for testing."""
    with patch('sqlalchemy.create_engine') as mock_engine:
        mock_connection = Mock()
        mock_engine.return_value.connect.return_value = mock_connection
        mock_connection.execute.return_value.fetchall.return_value = []
        mock_connection.execute.return_value.fetchone.return_value = None
        yield mock_engine


@pytest.fixture(scope="function")
def test_env_vars():
    """Set test environment variables for assethold."""
    test_vars = {
        'TESTING': 'true',
        'DEBUG': 'false',
        'DATABASE_URL': 'sqlite:///:memory:',
        'ALPHA_VANTAGE_API_KEY': 'test-av-key',
        'FINNHUB_API_KEY': 'test-finnhub-key',
        'FLASK_ENV': 'testing',
        'SECRET_KEY': 'test-secret-key-for-testing'
    }

    original_values = {}
    for key, value in test_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value

    yield test_vars

    for key, original_value in original_values.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


@pytest.fixture(scope="function")
def mock_flask_app():
    """Mock Flask application for testing."""
    from flask import Flask

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False

    with app.test_client() as client:
        with app.app_context():
            yield client


@pytest.fixture(scope="function")
def mock_time():
    """Mock time functions for consistent testing."""
    import time
    import datetime

    fixed_time = datetime.datetime(2025, 1, 1, 12, 0, 0)
    fixed_timestamp = fixed_time.timestamp()

    with patch('time.time', return_value=fixed_timestamp), \
         patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = fixed_time
        mock_datetime.utcnow.return_value = fixed_time
        yield fixed_time


@pytest.fixture(scope="function")
def captured_logs(caplog):
    """Capture log messages for testing."""
    import logging
    caplog.set_level(logging.DEBUG)
    yield caplog


@pytest.fixture(scope="function")
def benchmark_settings():
    """Settings for benchmark tests."""
    return {
        'max_time': 2.0,
        'min_rounds': 5,
        'warmup': True,
    }


def pytest_configure(config):
    """Configure pytest markers for assethold testing."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "api: mark test as an API test")
    config.addinivalue_line("markers", "database: mark test as requiring database")
    config.addinivalue_line("markers", "external: mark test as requiring external services")
    config.addinivalue_line("markers", "financial: mark test as financial calculation test")
    config.addinivalue_line("markers", "scraping: mark test as web scraping test")
    config.addinivalue_line("markers", "dashboard: mark test as dashboard/UI test")
    config.addinivalue_line("markers", "live_data: mark test as requiring live market data")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.slow)

        if "financial" in item.name.lower() or "portfolio" in item.name.lower():
            item.add_marker(pytest.mark.financial)
        if "scraping" in item.name.lower() or "scrape" in item.name.lower():
            item.add_marker(pytest.mark.scraping)
        if "dashboard" in item.name.lower() or "dash" in item.name.lower():
            item.add_marker(pytest.mark.dashboard)
