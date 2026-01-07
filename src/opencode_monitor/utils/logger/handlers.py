"""
Log handlers for OpenCode Monitor.

Provides file handlers with rotation for human-readable and JSON logs.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

from .config import LogConfig, ensure_log_directory
from .formatters import HumanFormatter, JsonFormatter


def create_file_handler(config: LogConfig) -> RotatingFileHandler:
    """Create a rotating file handler for human-readable logs.

    Args:
        config: Logging configuration.

    Returns:
        Configured RotatingFileHandler for human-readable logs.
    """
    ensure_log_directory(config)

    handler = RotatingFileHandler(
        filename=config.human_log_path,
        maxBytes=config.human_log_max_bytes,
        backupCount=config.human_log_backup_count,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)  # File gets all messages
    handler.setFormatter(HumanFormatter())

    return handler


def create_json_handler(config: LogConfig) -> RotatingFileHandler:
    """Create a rotating file handler for JSON logs.

    Args:
        config: Logging configuration.

    Returns:
        Configured RotatingFileHandler for JSON logs.
    """
    ensure_log_directory(config)

    handler = RotatingFileHandler(
        filename=config.json_log_path,
        maxBytes=config.json_log_max_bytes,
        backupCount=config.json_log_backup_count,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)  # File gets all messages
    handler.setFormatter(JsonFormatter())

    return handler


def create_console_handler(config: LogConfig) -> logging.StreamHandler:
    """Create a console handler for stderr output.

    Args:
        config: Logging configuration.

    Returns:
        Configured StreamHandler for console output.
    """
    handler = logging.StreamHandler(sys.stderr)

    # Console shows warnings and above unless in debug mode
    if config.default_level == logging.DEBUG:
        handler.setLevel(logging.DEBUG)
    else:
        handler.setLevel(logging.WARNING)

    handler.setFormatter(HumanFormatter())

    return handler


def create_crash_handler(config: LogConfig) -> logging.FileHandler:
    """Create a file handler for crash logs.

    This handler is specifically for unhandled exceptions and critical errors.
    It uses append mode and never rotates to preserve crash history.

    Args:
        config: Logging configuration.

    Returns:
        Configured FileHandler for crash logs.
    """
    ensure_log_directory(config)

    handler = logging.FileHandler(
        filename=config.crash_log_path,
        mode="a",
        encoding="utf-8",
    )
    handler.setLevel(logging.ERROR)
    handler.setFormatter(HumanFormatter())

    return handler


def setup_handlers(
    logger: logging.Logger,
    config: Optional[LogConfig] = None,
    include_console: Optional[bool] = None,
) -> None:
    """Set up all handlers for a logger.

    Args:
        logger: The logger to configure.
        config: Optional LogConfig. If not provided, uses get_config().
        include_console: Override console setting. If None, uses config.console_enabled.
    """
    from .config import get_config

    if config is None:
        config = get_config()

    # Determine if console should be included
    console_enabled = (
        include_console if include_console is not None else config.console_enabled
    )

    # Clear existing handlers
    logger.handlers.clear()

    # Add file handlers
    logger.addHandler(create_file_handler(config))
    logger.addHandler(create_json_handler(config))

    # Add console handler if enabled
    if console_enabled:
        logger.addHandler(create_console_handler(config))

    # Set logger level
    logger.setLevel(config.default_level)
