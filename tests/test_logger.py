"""
Tests for the logger module.
Consolidated: 11 tests → 4 tests with stronger assertions.
"""

import logging
from unittest.mock import patch

import pytest

from opencode_monitor.utils.logger import setup_logger
from opencode_monitor.utils import logger


class TestSetupLogger:
    """Tests for setup_logger function."""

    def test_setup_logger_returns_configured_logger(self):
        """setup_logger returns a properly configured Logger instance."""
        unique_name = "test_logger_configured"
        result = setup_logger(unique_name)

        # Verify instance type, name, and that handlers were added
        assert isinstance(result, logging.Logger)
        assert result.name == unique_name
        assert len(result.handlers) >= 1
        assert result.hasHandlers()

    def test_setup_logger_avoids_duplicate_handlers(self):
        """Calling setup_logger twice returns same logger without duplicating handlers."""
        logger_name = "test_duplicate_handlers"

        logger1 = setup_logger(logger_name)
        initial_handler_count = len(logger1.handlers)

        logger2 = setup_logger(logger_name)

        # Same instance, same handler count
        assert logger1 is logger2
        assert len(logger2.handlers) == initial_handler_count
        assert initial_handler_count >= 1  # Should have at least one handler

    @pytest.mark.parametrize(
        "env_value,expected_level,level_name",
        [
            ("1", logging.DEBUG, "DEBUG"),
            ("true", logging.DEBUG, "DEBUG"),
            ("", logging.INFO, "INFO"),
        ],
    )
    def test_setup_logger_respects_debug_env(
        self, env_value, expected_level, level_name
    ):
        """Logger level is controlled by OPENCODE_DEBUG environment variable."""
        unique_name = f"test_level_{level_name.lower()}"

        with patch.dict("os.environ", {"OPENCODE_DEBUG": env_value}, clear=False):
            result = setup_logger(unique_name)

            assert result.level == expected_level
            assert result.name == unique_name
            assert logging.getLevelName(result.level) == level_name


class TestLoggingFunctions:
    """Tests for convenience logging functions."""

    @pytest.mark.parametrize(
        "log_func,log_method,message,args,expected_call",
        [
            # Simple messages
            (logger.info, "info", "Test info message", (), ("Test info message",)),
            (
                logger.warn,
                "warning",
                "Test warning message",
                (),
                ("Test warning message",),
            ),
            (logger.error, "error", "Test error message", (), ("Test error message",)),
            (logger.debug, "debug", "Test debug message", (), ("Test debug message",)),
            # Messages with format args
            (logger.info, "info", "Value is %d", (42,), ("Value is %d", 42)),
            (
                logger.warn,
                "warning",
                "Warning: %s occurred",
                ("error",),
                ("Warning: %s occurred", "error"),
            ),
            (
                logger.error,
                "error",
                "Error code: %d - %s",
                (500, "Internal"),
                ("Error code: %d - %s", 500, "Internal"),
            ),
            (
                logger.debug,
                "debug",
                "Debug data: %r",
                ({"key": 1},),
                ("Debug data: %r", {"key": 1}),
            ),
        ],
    )
    def test_logging_functions_delegate_correctly(
        self, log_func, log_method, message, args, expected_call
    ):
        """All logging convenience functions delegate to the correct log method with proper args."""
        with patch.object(logger.log, log_method) as mock_method:
            log_func(message, *args)

            mock_method.assert_called_once()
            assert mock_method.call_args[0] == expected_call
