# test_smoke.py - Smoke tests for assethold
"""
Smoke tests for the assethold financial asset management application.

These tests verify basic functionality and ensure the application can start
and perform fundamental operations without errors.
"""

import pytest
import sys
import os
import importlib
from pathlib import Path
import pandas as pd
import numpy as np


class TestApplicationStartup:
    """Test basic application startup and configuration."""

    def test_python_version_compatibility(self):
        """Test that Python version is compatible with assethold requirements."""
        assert sys.version_info >= (3, 8), "Python 3.8+ is required"
        assert sys.version_info < (4, 0), "Python 4.0+ not yet supported"

    def test_essential_imports_available(self):
        """Test that all essential packages can be imported."""
        essential_packages = [
            'pandas',
            'numpy',
            'flask',
            'dash',
            'plotly',
            'yfinance',
            'sqlalchemy',
            'beautifulsoup4',
            'requests'
        ]

        failed_imports = []
        for package in essential_packages:
            try:
                # Handle special cases where import name differs from package name
                import_name = package
                if package == 'beautifulsoup4':
                    import_name = 'bs4'

                importlib.import_module(import_name)
            except ImportError as e:
                failed_imports.append(f"{package}: {str(e)}")

        assert not failed_imports, f"Failed to import essential packages: {failed_imports}"

    def test_project_structure_exists(self):
        """Test that expected project structure exists."""
        project_root = Path(__file__).parent.parent
        expected_paths = [
            'pyproject.toml',
            'uv.toml',
            'README.md',
            'src',
            'tests'
        ]

        missing_paths = []
        for path in expected_paths:
            if not (project_root / path).exists():
                missing_paths.append(path)

        assert not missing_paths, f"Missing expected project structure: {missing_paths}"

    def test_environment_variables_settable(self):
        """Test that environment variables can be set for configuration."""
        test_vars = {
            'TESTING': 'true',
            'DEBUG': 'false',
            'DATABASE_URL': 'sqlite:///:memory:'
        }

        for key, value in test_vars.items():
            os.environ[key] = value
            assert os.environ.get(key) == value, f"Failed to set environment variable {key}"

        # Clean up
        for key in test_vars:
            os.environ.pop(key, None)


class TestDataProcessingCore:
    """Test core data processing functionality."""

    def test_pandas_dataframe_creation(self):
        """Test basic pandas DataFrame operations for financial data."""
        # Create sample financial data
        data = {
            'Symbol': ['AAPL', 'MSFT', 'GOOGL'],
            'Price': [180.50, 420.25, 2750.00],
            'Volume': [50000000, 25000000, 1500000],
            'Market_Cap': [3000000000000, 2800000000000, 1900000000000]
        }

        df = pd.DataFrame(data)

        # Test basic operations
        assert len(df) == 3, "DataFrame should have 3 rows"
        assert list(df.columns) == ['Symbol', 'Price', 'Volume', 'Market_Cap'], "Columns mismatch"
        assert df['Price'].dtype in [np.float64, float], "Price column should be numeric"
        assert df['Volume'].dtype in [np.int64, int], "Volume column should be integer"

    def test_financial_calculations_basic(self):
        """Test basic financial calculations work correctly."""
        # Test simple return calculation
        initial_price = 100.0
        final_price = 110.0
        expected_return = (final_price - initial_price) / initial_price

        calculated_return = (final_price - initial_price) / initial_price
        assert abs(calculated_return - expected_return) < 1e-10, "Return calculation failed"
        assert calculated_return == 0.1, "10% return calculation incorrect"

    def test_time_series_data_handling(self):
        """Test time series data can be created and manipulated."""
        # Create time series data
        dates = pd.date_range(start='2024-01-01', end='2024-01-10', freq='D')
        prices = [100 + i for i in range(len(dates))]

        ts_data = pd.Series(prices, index=dates)

        assert len(ts_data) == 10, "Time series should have 10 data points"
        assert ts_data.index[0] == pd.Timestamp('2024-01-01'), "First date incorrect"
        assert ts_data.index[-1] == pd.Timestamp('2024-01-10'), "Last date incorrect"
        assert ts_data.iloc[0] == 100, "First price incorrect"

    def test_numpy_array_operations(self):
        """Test numpy operations for financial calculations."""
        # Test basic statistical operations
        returns = np.array([0.01, -0.02, 0.03, -0.01, 0.02])

        mean_return = np.mean(returns)
        std_return = np.std(returns)
        cumulative_return = np.prod(1 + returns) - 1

        assert isinstance(mean_return, (float, np.floating)), "Mean should be float"
        assert isinstance(std_return, (float, np.floating)), "Std should be float"
        assert isinstance(cumulative_return, (float, np.floating)), "Cumulative return should be float"
        assert not np.isnan(mean_return), "Mean return should not be NaN"


class TestFileOperations:
    """Test file I/O operations for data import/export."""

    def test_csv_file_operations(self, temp_dir):
        """Test CSV file reading and writing capabilities."""
        # Create test data
        data = pd.DataFrame({
            'Date': pd.date_range('2024-01-01', periods=5),
            'Symbol': ['AAPL'] * 5,
            'Close': [180.0, 181.0, 179.0, 182.0, 183.0]
        })

        # Test file operations
        csv_file = temp_dir / 'test_data.csv'
        data.to_csv(csv_file, index=False)

        assert csv_file.exists(), "CSV file should be created"

        # Read back and verify
        loaded_data = pd.read_csv(csv_file)
        assert len(loaded_data) == 5, "Loaded data should have 5 rows"
        assert 'Symbol' in loaded_data.columns, "Symbol column should exist"

    def test_excel_file_operations(self, temp_dir):
        """Test Excel file reading and writing capabilities."""
        # Create test data
        data = pd.DataFrame({
            'Portfolio': ['Growth', 'Income', 'Balanced'],
            'Total_Value': [100000, 75000, 150000],
            'Return_YTD': [0.12, 0.08, 0.10]
        })

        # Test Excel operations
        excel_file = temp_dir / 'test_portfolio.xlsx'
        data.to_excel(excel_file, index=False)

        assert excel_file.exists(), "Excel file should be created"

        # Read back and verify
        loaded_data = pd.read_excel(excel_file)
        assert len(loaded_data) == 3, "Loaded data should have 3 rows"
        assert 'Portfolio' in loaded_data.columns, "Portfolio column should exist"


class TestExternalConnectivity:
    """Test external service connectivity (mocked)."""

    def test_mock_api_request(self, mock_web_scraping):
        """Test that API requests can be made (using mocked response)."""
        import requests

        session = requests.Session()
        response = session.get('https://api.example.com/test')

        assert response.status_code == 200, "Mock API request should succeed"
        assert 'data' in response.json(), "Response should contain data field"

    def test_mock_financial_data_fetch(self, mock_yfinance):
        """Test financial data fetching (using mocked yfinance)."""
        import yfinance as yf

        ticker = yf.Ticker('AAPL')
        info = ticker.info

        assert 'symbol' in info, "Ticker info should contain symbol"
        assert info['symbol'] == 'AAPL', "Symbol should match requested ticker"

        # Test historical data
        hist = ticker.history(period='5d')
        assert not hist.empty, "Historical data should not be empty"
        assert 'Close' in hist.columns, "Historical data should have Close column"


class TestApplicationConfiguration:
    """Test application configuration and settings."""

    def test_testing_environment_setup(self, test_env_vars):
        """Test that testing environment is properly configured."""
        assert os.environ.get('TESTING') == 'true', "TESTING environment variable should be set"
        assert os.environ.get('DEBUG') == 'false', "DEBUG should be disabled in tests"
        assert 'sqlite:///:memory:' in os.environ.get('DATABASE_URL', ''), "Should use in-memory database for tests"

    def test_configuration_file_readable(self):
        """Test that configuration files can be read."""
        project_root = Path(__file__).parent.parent
        config_files = ['pyproject.toml', 'uv.toml']

        for config_file in config_files:
            config_path = project_root / config_file
            if config_path.exists():
                # Test that file is readable
                content = config_path.read_text()
                assert len(content) > 0, f"{config_file} should not be empty"
                assert 'assethold' in content.lower(), f"{config_file} should reference assethold project"


# Additional smoke tests for specific assethold functionality
class TestAssetHoldSpecific:
    """Smoke tests specific to assethold functionality."""

    def test_financial_libraries_compatibility(self):
        """Test that financial libraries work together."""
        try:
            import yfinance
            import pandas
            import numpy
            import ta  # Technical analysis library

            # Test basic integration
            assert hasattr(yfinance, 'Ticker'), "yfinance should have Ticker class"
            assert hasattr(pandas, 'DataFrame'), "pandas should have DataFrame class"
            assert hasattr(numpy, 'array'), "numpy should have array function"
            assert hasattr(ta, 'trend'), "ta should have trend module"

        except ImportError as e:
            pytest.fail(f"Financial library compatibility issue: {e}")

    def test_web_scraping_libraries_available(self):
        """Test that web scraping libraries are available."""
        scraping_libraries = ['bs4', 'requests', 'selenium', 'scrapy']
        available_libraries = []

        for lib in scraping_libraries:
            try:
                importlib.import_module(lib)
                available_libraries.append(lib)
            except ImportError:
                pass

        # At least basic libraries should be available
        assert 'bs4' in available_libraries, "BeautifulSoup4 should be available"
        assert 'requests' in available_libraries, "requests should be available"

    def test_dashboard_framework_available(self):
        """Test that dashboard frameworks are available."""
        try:
            import dash
            import plotly
            import flask

            assert hasattr(dash, 'Dash'), "Dash should have Dash class"
            assert hasattr(plotly, 'graph_objects'), "Plotly should have graph_objects"
            assert hasattr(flask, 'Flask'), "Flask should have Flask class"

        except ImportError as e:
            pytest.fail(f"Dashboard framework availability issue: {e}")


# Mark all tests in this file as smoke tests
pytestmark = pytest.mark.unit