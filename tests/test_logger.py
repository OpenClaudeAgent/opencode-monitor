"""
Tests for the logger module.
"""

import logging
from unittest.mock import patch, MagicMock

import pytest


class TestSetupLogger:
    """Tests for setup_logger function."""

    def test_setup_logger_returns_logger(self):
        """setup_logger should return a Logger instance."""
        from opencode_monitor.utils.logger import setup_logger

        # Use a unique name to avoid conflicts with the global logger
        logger = setup_logger("test_logger_unique")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger_unique"

    def test_setup_logger_avoids_duplicate_handlers(self):
        """Calling setup_logger twice with same name should return existing logger."""
        from opencode_monitor.utils.logger import setup_logger

        # Create logger with handlers
        logger_name = "test_duplicate_handlers"
        logger1 = setup_logger(logger_name)
        handler_count_after_first = len(logger1.handlers)

        # Call again - should return same logger without adding handlers
        logger2 = setup_logger(logger_name)
        handler_count_after_second = len(logger2.handlers)

        assert logger1 is logger2
        assert handler_count_after_first == handler_count_after_second

    def test_setup_logger_debug_mode_enabled(self):
        """Logger should be DEBUG level when OPENCODE_DEBUG is set."""
        from opencode_monitor.utils.logger import setup_logger

        with patch.dict("os.environ", {"OPENCODE_DEBUG": "1"}):
            logger = setup_logger("test_debug_mode")
            assert logger.level == logging.DEBUG

    def test_setup_logger_debug_mode_disabled(self):
        """Logger should be INFO level when OPENCODE_DEBUG is not set."""
        from opencode_monitor.utils.logger import setup_logger

        with patch.dict("os.environ", {"OPENCODE_DEBUG": ""}, clear=False):
            logger = setup_logger("test_info_mode")
            assert logger.level == logging.INFO


class TestLoggingFunctions:
    """Tests for convenience logging functions."""

    def test_info_logs_message(self):
        """info() should log at INFO level."""
        from opencode_monitor.utils import logger

        with patch.object(logger.log, "info") as mock_info:
            logger.info("Test info message")
            mock_info.assert_called_once_with("Test info message")

    def test_info_logs_with_args(self):
        """info() should pass format args to logger."""
        from opencode_monitor.utils import logger

        with patch.object(logger.log, "info") as mock_info:
            logger.info("Value is %d", 42)
            mock_info.assert_called_once_with("Value is %d", 42)

    def test_warn_logs_message(self):
        """warn() should log at WARNING level."""
        from opencode_monitor.utils import logger

        with patch.object(logger.log, "warning") as mock_warning:
            logger.warn("Test warning message")
            mock_warning.assert_called_once_with("Test warning message")

    def test_warn_logs_with_args(self):
        """warn() should pass format args to logger."""
        from opencode_monitor.utils import logger

        with patch.object(logger.log, "warning") as mock_warning:
            logger.warn("Warning: %s occurred", "error")
            mock_warning.assert_called_once_with("Warning: %s occurred", "error")

    def test_error_logs_message(self):
        """error() should log at ERROR level."""
        from opencode_monitor.utils import logger

        with patch.object(logger.log, "error") as mock_error:
            logger.error("Test error message")
            mock_error.assert_called_once_with("Test error message")

    def test_error_logs_with_args(self):
        """error() should pass format args to logger."""
        from opencode_monitor.utils import logger

        with patch.object(logger.log, "error") as mock_error:
            logger.error("Error code: %d - %s", 500, "Internal error")
            mock_error.assert_called_once_with(
                "Error code: %d - %s", 500, "Internal error"
            )

    def test_debug_logs_message(self):
        """debug() should log at DEBUG level."""
        from opencode_monitor.utils import logger

        with patch.object(logger.log, "debug") as mock_debug:
            logger.debug("Test debug message")
            mock_debug.assert_called_once_with("Test debug message")
