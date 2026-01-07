"""
Tests for the logger module.
Tests cover the new professional logging system with backward compatibility.
"""

import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opencode_monitor.utils.logger import (
    setup_logger,
    setup_logging,
    get_logger,
    debug,
    info,
    warn,
    warning,
    error,
    critical,
    exception,
    log_context,
    get_request_id,
    get_session_id,
    LogConfig,
    get_config,
)
from opencode_monitor.utils.logger.formatters import HumanFormatter, JsonFormatter
from opencode_monitor.utils.logger.context import ContextFilter


class TestSetupLogger:
    """Tests for setup_logger function (backward compatible API)."""

    def test_setup_logger_returns_configured_logger(self):
        """setup_logger returns a properly configured Logger instance."""
        result = setup_logger()

        # Verify instance type and that handlers were added
        assert isinstance(result, logging.Logger)
        assert result.name == "opencode"
        assert len(result.handlers) >= 1
        assert result.hasHandlers()

    def test_setup_logger_avoids_duplicate_handlers(self):
        """Calling setup_logger twice returns same logger without duplicating handlers."""
        logger1 = setup_logger()
        initial_handler_count = len(logger1.handlers)

        logger2 = setup_logger()

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
        # Reset logger state to test fresh initialization
        import opencode_monitor.utils.logger as logger_module

        logger_module._initialized = False
        logger_module._root_logger = None

        # Clear any existing handlers from the opencode logger
        existing_logger = logging.getLogger("opencode")
        existing_logger.handlers.clear()
        existing_logger.filters.clear()

        with patch.dict("os.environ", {"OPENCODE_DEBUG": env_value}, clear=False):
            result = setup_logger()

            assert result.level == expected_level
            assert logging.getLevelName(result.level) == level_name


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_root_logger(self):
        """get_logger() without name returns the root logger."""
        logger = get_logger()
        assert logger.name == "opencode"

    def test_get_logger_returns_child_logger(self):
        """get_logger('name') returns a child logger."""
        logger = get_logger("api")
        assert logger.name == "opencode.api"

    def test_get_logger_child_inherits_level(self):
        """Child loggers inherit level from root."""
        root_logger = get_logger()
        child_logger = get_logger("child")

        # Child should use effective level from parent
        assert child_logger.getEffectiveLevel() == root_logger.level


class TestLoggingFunctions:
    """Tests for convenience logging functions."""

    @pytest.fixture(autouse=True)
    def setup_mock_logger(self):
        """Set up a mock logger for testing."""
        self.mock_logger = MagicMock(spec=logging.Logger)
        with patch(
            "opencode_monitor.utils.logger.get_logger", return_value=self.mock_logger
        ):
            yield

    @pytest.mark.parametrize(
        "log_func,log_method,message,args",
        [
            (info, "info", "Test info message", ()),
            (warn, "warning", "Test warning message", ()),
            (warning, "warning", "Test warning message", ()),
            (error, "error", "Test error message", ()),
            (debug, "debug", "Test debug message", ()),
            (critical, "critical", "Test critical message", ()),
            (info, "info", "Value is %d", (42,)),
            (warn, "warning", "Warning: %s occurred", ("error",)),
            (error, "error", "Error code: %d - %s", (500, "Internal")),
            (debug, "debug", "Debug data: %r", ({"key": 1},)),
        ],
    )
    def test_logging_functions_delegate_correctly(
        self, log_func, log_method, message, args
    ):
        """All logging convenience functions delegate to the correct log method."""
        log_func(message, *args)

        # Verify the correct method was called
        method = getattr(self.mock_logger, log_method)
        method.assert_called_once()
        call_args = method.call_args[0]
        assert call_args[0] == message
        if args:
            assert call_args[1:] == args


class TestLogContext:
    """Tests for log context management."""

    def test_log_context_sets_request_id(self):
        """log_context sets request_id for the duration of the context."""
        assert get_request_id() is None

        with log_context(request_id="test-req-123"):
            assert get_request_id() == "test-req-123"

        assert get_request_id() is None

    def test_log_context_sets_session_id(self):
        """log_context sets session_id for the duration of the context."""
        assert get_session_id() is None

        with log_context(session_id="test-session-456"):
            assert get_session_id() == "test-session-456"

        assert get_session_id() is None

    def test_log_context_auto_generates_ids(self):
        """log_context can auto-generate IDs."""
        with log_context(auto_request_id=True, auto_session_id=True) as ctx:
            assert ctx["request_id"] is not None
            assert ctx["session_id"] is not None
            assert len(ctx["request_id"]) == 8
            assert len(ctx["session_id"]) == 12

    def test_log_context_yields_active_ids(self):
        """log_context yields the active context IDs."""
        with log_context(request_id="req-1", session_id="sess-2") as ctx:
            assert ctx["request_id"] == "req-1"
            assert ctx["session_id"] == "sess-2"


class TestContextFilter:
    """Tests for ContextFilter."""

    def test_context_filter_adds_request_id(self):
        """ContextFilter adds request_id to log records."""
        filter = ContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        with log_context(request_id="filter-test-req"):
            filter.filter(record)
            assert record.request_id == "filter-test-req"

    def test_context_filter_adds_session_id(self):
        """ContextFilter adds session_id to log records."""
        filter = ContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        with log_context(session_id="filter-test-sess"):
            filter.filter(record)
            assert record.session_id == "filter-test-sess"


class TestHumanFormatter:
    """Tests for HumanFormatter."""

    def test_format_basic_message(self):
        """HumanFormatter formats basic messages correctly."""
        formatter = HumanFormatter()
        record = logging.LogRecord(
            name="opencode.api",
            level=logging.INFO,
            pathname="server.py",
            lineno=42,
            msg="Server started",
            args=(),
            exc_info=None,
        )
        record.filename = "server.py"

        output = formatter.format(record)

        assert "INFO" in output
        assert "opencode.api" in output
        assert "server.py:42" in output
        assert "Server started" in output

    def test_format_includes_context(self):
        """HumanFormatter includes context IDs when present."""
        formatter = HumanFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.filename = "test.py"
        record.request_id = "req-123"
        record.session_id = "sess-456"

        output = formatter.format(record)

        assert "req=req-123" in output
        assert "session=sess-456" in output


class TestJsonFormatter:
    """Tests for JsonFormatter."""

    def test_format_produces_valid_json(self):
        """JsonFormatter produces valid JSON output."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="opencode.api",
            level=logging.INFO,
            pathname="server.py",
            lineno=42,
            msg="Server started",
            args=(),
            exc_info=None,
        )
        record.filename = "server.py"

        output = formatter.format(record)

        # Should be valid JSON
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["logger"] == "opencode.api"
        assert data["message"] == "Server started"
        assert data["file"] == "server.py"
        assert data["line"] == 42

    def test_format_includes_exception(self):
        """JsonFormatter includes exception info when present."""
        formatter = JsonFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        record.filename = "test.py"

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert data["exception"]["message"] == "Test error"
        assert isinstance(data["exception"]["traceback"], list)


class TestLogConfig:
    """Tests for LogConfig."""

    def test_default_config_values(self):
        """LogConfig has sensible defaults."""
        config = LogConfig()

        assert config.human_log_max_bytes == 10 * 1024 * 1024
        assert config.human_log_backup_count == 5
        assert config.json_log_max_bytes == 20 * 1024 * 1024
        assert config.json_log_backup_count == 3
        assert config.default_level == logging.INFO
        assert config.console_enabled is False

    def test_config_from_env_debug_mode(self):
        """get_config reads OPENCODE_DEBUG from environment."""
        with patch.dict("os.environ", {"OPENCODE_DEBUG": "1"}, clear=False):
            config = get_config()
            assert config.default_level == logging.DEBUG
            assert config.console_enabled is True

    def test_config_from_env_log_level(self):
        """get_config reads OPENCODE_LOG_LEVEL from environment."""
        with patch.dict("os.environ", {"OPENCODE_LOG_LEVEL": "warning"}, clear=False):
            config = get_config()
            assert config.default_level == logging.WARNING

    def test_log_paths(self):
        """LogConfig provides correct log file paths."""
        config = LogConfig()

        assert config.human_log_path.name == "opencode-monitor.log"
        assert config.json_log_path.name == "opencode-monitor.json"
        assert config.crash_log_path.name == "crash.log"


class TestBackwardCompatibility:
    """Tests ensuring backward compatibility with old API."""

    def test_import_debug_info_warn_error(self):
        """Can import debug, info, warn, error from logger module."""
        from opencode_monitor.utils.logger import debug, info, warn, error

        # All should be callable
        assert callable(debug)
        assert callable(info)
        assert callable(warn)
        assert callable(error)

    def test_import_setup_logger(self):
        """Can import setup_logger from logger module."""
        from opencode_monitor.utils.logger import setup_logger

        assert callable(setup_logger)
        result = setup_logger()
        assert isinstance(result, logging.Logger)

    def test_module_import_functions(self):
        """Can use module.function style like old code."""
        from opencode_monitor.utils import logger

        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warn")
        assert hasattr(logger, "error")
        assert hasattr(logger, "setup_logger")
