"""
Structured logging for OpenCode Monitor.

This module provides a professional logging system with:
- Human-readable and JSON log formats
- Log file rotation
- Request/session context tracking
- Crash handling

Backward Compatible API:
    from opencode_monitor.utils.logger import debug, info, warn, error

    debug("Debug message")
    info("Info message")
    warn("Warning message")
    error("Error message")

Enhanced API:
    from opencode_monitor.utils.logger import get_logger, setup_logging, log_context

    # Get a component-specific logger
    logger = get_logger("mycomponent")
    logger.info("Component started")

    # Use context for request tracking
    with log_context(request_id="abc123"):
        logger.info("Processing request")
"""

import logging
from typing import Any, Optional

from .config import LogConfig, get_config, ensure_log_directory
from .context import (
    ContextFilter,
    log_context,
    get_request_id,
    get_session_id,
    set_request_id,
    set_session_id,
    generate_request_id,
    generate_session_id,
)
from .crash import install_crash_handler, uninstall_crash_handler, log_crash
from .handlers import setup_handlers

# Root logger name for the application
ROOT_LOGGER_NAME = "opencode"

# Module-level state
_initialized = False
_root_logger: Optional[logging.Logger] = None


def setup_logging(config: Optional[LogConfig] = None) -> logging.Logger:
    """Initialize the logging system.

    This function should be called once at application startup.
    It sets up file handlers, formatters, and the crash handler.

    Args:
        config: Optional LogConfig. If not provided, reads from environment.

    Returns:
        The configured root logger.

    Example:
        # At application startup
        setup_logging()

        # Or with custom config
        config = LogConfig(console_enabled=True)
        setup_logging(config)
    """
    global _initialized, _root_logger

    if config is None:
        config = get_config()

    # Ensure log directory exists
    ensure_log_directory(config)

    # Get or create the root logger
    logger = logging.getLogger(ROOT_LOGGER_NAME)

    # Set up handlers
    setup_handlers(logger, config)

    # Add context filter to inject request/session IDs
    context_filter = ContextFilter()
    logger.addFilter(context_filter)

    # Install crash handler
    install_crash_handler(logger, config)

    # Prevent propagation to root logger
    logger.propagate = False

    _initialized = True
    _root_logger = logger

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.

    If name is provided, returns a child logger of the root logger.
    If name is None, returns the root logger.

    The logging system is automatically initialized if not already done.

    Args:
        name: Optional component name for the logger.

    Returns:
        A configured Logger instance.

    Example:
        # Get root logger
        logger = get_logger()

        # Get component logger
        api_logger = get_logger("api")
        api_logger.info("API started")  # Logs as "opencode.api"
    """
    global _initialized, _root_logger

    # Auto-initialize if needed
    if not _initialized:
        setup_logging()

    if name:
        return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")
    return _root_logger or logging.getLogger(ROOT_LOGGER_NAME)


# Backward-compatible simple API functions
# These maintain the exact same signature as the original logger.py


def setup_logger(name: str = "opencode") -> logging.Logger:
    """Setup and return a configured logger (backward compatible).

    This function is kept for backward compatibility with existing code.
    New code should use setup_logging() instead.

    Args:
        name: Logger name (ignored, always uses ROOT_LOGGER_NAME).

    Returns:
        The configured root logger.
    """
    return setup_logging()


def debug(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log a debug message.

    Args:
        msg: The message format string.
        *args: Arguments for message formatting.
        **kwargs: Additional keyword arguments passed to logger.debug().
    """
    get_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log an info message.

    Args:
        msg: The message format string.
        *args: Arguments for message formatting.
        **kwargs: Additional keyword arguments passed to logger.info().
    """
    get_logger().info(msg, *args, **kwargs)


def warn(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log a warning message.

    Args:
        msg: The message format string.
        *args: Arguments for message formatting.
        **kwargs: Additional keyword arguments passed to logger.warning().
    """
    get_logger().warning(msg, *args, **kwargs)


def warning(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log a warning message (alias for warn).

    Args:
        msg: The message format string.
        *args: Arguments for message formatting.
        **kwargs: Additional keyword arguments passed to logger.warning().
    """
    get_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log an error message.

    Args:
        msg: The message format string.
        *args: Arguments for message formatting.
        **kwargs: Additional keyword arguments passed to logger.error().
    """
    get_logger().error(msg, *args, **kwargs)


def critical(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log a critical message.

    Args:
        msg: The message format string.
        *args: Arguments for message formatting.
        **kwargs: Additional keyword arguments passed to logger.critical().
    """
    get_logger().critical(msg, *args, **kwargs)


def exception(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log an error message with exception info.

    This should be called from an exception handler.

    Args:
        msg: The message format string.
        *args: Arguments for message formatting.
        **kwargs: Additional keyword arguments passed to logger.exception().
    """
    get_logger().exception(msg, *args, **kwargs)


class _LazyLogger:
    """Lazy logger proxy that initializes on first use.

    This allows the `log` variable to work like the old global logger
    without initializing the logging system at import time.
    """

    _instance: Optional[logging.Logger] = None

    def __getattr__(self, name: str) -> Any:
        if self._instance is None:
            self._instance = get_logger()
        return getattr(self._instance, name)


# Backward-compatible global logger instance
# This allows existing code using `logger.log.info(...)` to continue working
log: Any = _LazyLogger()


# Public API
__all__ = [
    # Backward-compatible simple API
    "debug",
    "info",
    "warn",
    "warning",
    "error",
    "critical",
    "exception",
    "setup_logger",
    "log",
    # Enhanced API
    "setup_logging",
    "get_logger",
    "LogConfig",
    "get_config",
    # Context management
    "log_context",
    "get_request_id",
    "get_session_id",
    "set_request_id",
    "set_session_id",
    "generate_request_id",
    "generate_session_id",
    "ContextFilter",
    # Crash handling
    "install_crash_handler",
    "uninstall_crash_handler",
    "log_crash",
]
