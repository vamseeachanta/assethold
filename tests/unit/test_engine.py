"""
Unit tests for the assethold engine module.

Tests core engine functionality including configuration loading,
validation, and routing to appropriate handlers.
"""

import pytest
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import logging

from assethold.engine import engine, validate_arguments_run_methods


class TestValidateArgumentsRunMethods:
    """Tests for validate_arguments_run_methods function."""

    def test_inputfile_argument_takes_priority(self):
        """Test that explicit inputfile argument takes priority over sys.argv."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write('test: data')
            f.flush()
            temp_path = f.name

        try:
            result = validate_arguments_run_methods(temp_path)
            assert result == temp_path
        finally:
            os.unlink(temp_path)

    def test_inputfile_argument_with_nonexistent_file_raises_error(self):
        """Test that nonexistent inputfile raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            validate_arguments_run_methods('/nonexistent/file.yml')
        assert 'not found' in str(exc_info.value).lower()

    def test_sys_argv_used_when_no_argument(self, monkeypatch):
        """Test that sys.argv is used when no inputfile argument provided."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write('test: data')
            f.flush()
            temp_path = f.name

        try:
            monkeypatch.setattr(sys, 'argv', ['script.py', temp_path])
            result = validate_arguments_run_methods(None)
            assert result == temp_path
        finally:
            os.unlink(temp_path)

    def test_sys_argv_nonexistent_file_raises_error(self, monkeypatch):
        """Test that sys.argv with nonexistent file raises FileNotFoundError."""
        monkeypatch.setattr(sys, 'argv', ['script.py', '/nonexistent/file.yml'])
        with pytest.raises(FileNotFoundError) as exc_info:
            validate_arguments_run_methods(None)
        assert 'not found' in str(exc_info.value).lower()

    def test_no_arguments_raises_value_error(self, monkeypatch):
        """Test that missing both inputfile and sys.argv raises ValueError."""
        monkeypatch.setattr(sys, 'argv', ['script.py'])  # No additional args
        with pytest.raises(ValueError) as exc_info:
            validate_arguments_run_methods(None)
        assert 'no input file provided' in str(exc_info.value).lower()

    def test_sys_argv_without_second_element_raises_error(self, monkeypatch):
        """Test error when sys.argv has no second element (filename)."""
        monkeypatch.setattr(sys, 'argv', ['script.py'])
        with pytest.raises(ValueError) as exc_info:
            validate_arguments_run_methods(None)
        assert 'no input file provided' in str(exc_info.value).lower()


class TestEngineBasic:
    """Tests for engine function - basic functionality."""

    def test_engine_requires_basename_in_config(self):
        """Test that engine raises error when config is missing basename."""
        cfg = {}  # Missing 'basename' key
        with pytest.raises(KeyError):
            engine(cfg=cfg, config_flag=False)

    def test_engine_with_invalid_basename_raises_exception(self):
        """Test that engine raises exception for unrecognized basename."""
        cfg = {'basename': 'invalid_module'}
        with patch('assethold.engine.FileManagement'):
            with pytest.raises(Exception) as exc_info:
                engine(cfg=cfg, config_flag=False)
            assert 'not found' in str(exc_info.value).lower()

    def test_engine_logs_start_and_end_messages(self):
        """Test that engine logs application start and end messages."""
        cfg = {'basename': 'stocks'}

        with patch('assethold.engine.FileManagement'):
            with patch('assethold.engine.logging') as mock_logging:
                with patch('assethold.engine.Stocks') as mock_stocks:
                    with patch('assethold.engine.save_application_cfg'):
                        mock_stocks_instance = MagicMock()
                        mock_stocks_instance.router.return_value = cfg
                        mock_stocks.return_value = mock_stocks_instance

                        engine(cfg=cfg, config_flag=False)

                        # Verify logging calls
                        assert mock_logging.info.call_count >= 2
                        calls = [str(call) for call in mock_logging.info.call_args_list]
                        assert any('START' in str(call) for call in calls)
                        assert any('END' in str(call) for call in calls)

    def test_engine_calls_file_management_router_when_config_flag_true(self):
        """Test that FileManagement.router is called when config_flag is True."""
        cfg = {'basename': 'stocks'}

        with patch('assethold.engine.FileManagement') as mock_fm_class:
            with patch('assethold.engine.logging'):
                with patch('assethold.engine.Stocks') as mock_stocks:
                    with patch('assethold.engine.save_application_cfg'):
                        mock_fm = MagicMock()
                        mock_fm.router.return_value = cfg
                        mock_fm_class.return_value = mock_fm

                        mock_stocks_instance = MagicMock()
                        mock_stocks_instance.router.return_value = cfg
                        mock_stocks.return_value = mock_stocks_instance

                        result = engine(cfg=cfg, config_flag=True)

                        # Verify FileManagement.router was called
                        mock_fm.router.assert_called_once()

    def test_engine_skips_file_management_router_when_config_flag_false(self):
        """Test that FileManagement.router is skipped when config_flag is False."""
        cfg = {'basename': 'stocks'}

        with patch('assethold.engine.FileManagement') as mock_fm_class:
            with patch('assethold.engine.logging'):
                with patch('assethold.engine.Stocks') as mock_stocks:
                    with patch('assethold.engine.save_application_cfg'):
                        mock_fm = MagicMock()
                        mock_fm_class.return_value = mock_fm

                        mock_stocks_instance = MagicMock()
                        mock_stocks_instance.router.return_value = cfg
                        mock_stocks.return_value = mock_stocks_instance

                        result = engine(cfg=cfg, config_flag=False)

                        # FileManagement.router should NOT be called
                        mock_fm.router.assert_not_called()

    def test_engine_returns_config_dict(self):
        """Test that engine returns a dictionary (config)."""
        cfg = {'basename': 'stocks', 'test_key': 'test_value'}

        with patch('assethold.engine.FileManagement'):
            with patch('assethold.engine.logging'):
                with patch('assethold.engine.Stocks') as mock_stocks:
                    with patch('assethold.engine.save_application_cfg'):
                        mock_stocks_instance = MagicMock()
                        mock_stocks_instance.router.return_value = cfg
                        mock_stocks.return_value = mock_stocks_instance

                        result = engine(cfg=cfg, config_flag=False)

                        assert isinstance(result, dict)
                        assert result == cfg

    def test_engine_calls_stocks_router_for_stocks_basename(self):
        """Test that Stocks.router is called when basename is 'stocks'."""
        cfg = {'basename': 'stocks'}

        with patch('assethold.engine.FileManagement'):
            with patch('assethold.engine.logging'):
                with patch('assethold.engine.Stocks') as mock_stocks_class:
                    with patch('assethold.engine.save_application_cfg'):
                        mock_stocks_instance = MagicMock()
                        mock_stocks_instance.router.return_value = cfg
                        mock_stocks_class.return_value = mock_stocks_instance

                        engine(cfg=cfg, config_flag=False)

                        # Verify Stocks class was instantiated
                        mock_stocks_class.assert_called_once()
                        # Verify router was called
                        mock_stocks_instance.router.assert_called_once()

    def test_engine_calls_save_application_cfg(self):
        """Test that save_application_cfg is called with updated config."""
        cfg = {'basename': 'stocks'}

        with patch('assethold.engine.FileManagement'):
            with patch('assethold.engine.logging'):
                with patch('assethold.engine.Stocks') as mock_stocks:
                    with patch('assethold.engine.save_application_cfg') as mock_save:
                        mock_stocks_instance = MagicMock()
                        mock_stocks_instance.router.return_value = cfg
                        mock_stocks.return_value = mock_stocks_instance

                        engine(cfg=cfg, config_flag=False)

                        # Verify save_application_cfg was called
                        mock_save.assert_called_once()


class TestEngineWithFile:
    """Tests for engine function with file input."""

    def test_engine_loads_and_parses_yaml_file(self):
        """Test that engine loads config from YAML file."""
        yaml_content = 'basename: stocks\ntest_key: test_value\n'

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            temp_path = f.name

        try:
            with patch('assethold.engine.FileManagement'):
                with patch('assethold.engine.logging'):
                    with patch('assethold.engine.ymlInput') as mock_yml:
                        with patch('assethold.engine.AttributeDict') as mock_attr_dict:
                            with patch('assethold.engine.Stocks') as mock_stocks:
                                with patch('assethold.engine.save_application_cfg'):
                                    mock_config = {'basename': 'stocks'}
                                    mock_yml.return_value = mock_config
                                    mock_attr_dict.return_value = mock_config

                                    mock_stocks_instance = MagicMock()
                                    mock_stocks_instance.router.return_value = mock_config
                                    mock_stocks.return_value = mock_stocks_instance

                                    result = engine(inputfile=temp_path, config_flag=False)

                                    # Verify ymlInput was called with the file
                                    mock_yml.assert_called_once_with(temp_path, updateYml=None)
        finally:
            os.unlink(temp_path)

    def test_engine_raises_error_when_cfg_is_none_after_loading(self):
        """Test that engine raises ValueError if config is None after loading."""
        yaml_content = ''  # Empty file

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            temp_path = f.name

        try:
            with patch('assethold.engine.ymlInput') as mock_yml:
                with patch('assethold.engine.AttributeDict') as mock_attr_dict:
                    mock_yml.return_value = None
                    mock_attr_dict.return_value = None

                    with pytest.raises(ValueError) as exc_info:
                        engine(inputfile=temp_path, config_flag=False)
                    assert 'cfg is None' in str(exc_info.value)
        finally:
            os.unlink(temp_path)


class TestEngineEdgeCases:
    """Tests for edge cases and error handling."""

    def test_engine_basename_case_sensitive(self):
        """Test that basename matching is case-sensitive."""
        cfg = {'basename': 'Stocks'}  # Capital S

        with patch('assethold.engine.FileManagement'):
            with patch('assethold.engine.logging'):
                # Should raise exception because 'Stocks' != 'stocks'
                with pytest.raises(Exception) as exc_info:
                    engine(cfg=cfg, config_flag=False)
                assert 'not found' in str(exc_info.value).lower()

    def test_engine_with_extra_config_keys(self):
        """Test that engine handles config with extra keys."""
        cfg = {
            'basename': 'stocks',
            'extra_key': 'extra_value',
            'another_key': 123
        }

        with patch('assethold.engine.FileManagement'):
            with patch('assethold.engine.logging'):
                with patch('assethold.engine.Stocks') as mock_stocks:
                    with patch('assethold.engine.save_application_cfg'):
                        mock_stocks_instance = MagicMock()
                        mock_stocks_instance.router.return_value = cfg
                        mock_stocks.return_value = mock_stocks_instance

                        result = engine(cfg=cfg, config_flag=False)

                        # All keys should be preserved
                        assert result['extra_key'] == 'extra_value'
                        assert result['another_key'] == 123

    def test_engine_basename_in_condition(self):
        """Test that basename condition uses 'in' operator correctly."""
        # Test with 'stocks' substring
        cfg = {'basename': 'stocks'}

        with patch('assethold.engine.FileManagement'):
            with patch('assethold.engine.logging'):
                with patch('assethold.engine.Stocks') as mock_stocks:
                    with patch('assethold.engine.save_application_cfg'):
                        mock_stocks_instance = MagicMock()
                        mock_stocks_instance.router.return_value = cfg
                        mock_stocks.return_value = mock_stocks_instance

                        # Should succeed - 'stocks' in 'stocks'
                        result = engine(cfg=cfg, config_flag=False)
                        assert result is not None
