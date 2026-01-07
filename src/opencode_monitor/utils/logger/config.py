"""
Logging configuration for OpenCode Monitor.

Provides configuration settings and environment variable handling for the logging system.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Environment variable names
DEBUG_ENV = "OPENCODE_DEBUG"
LOG_LEVEL_ENV = "OPENCODE_LOG_LEVEL"
LOG_CONSOLE_ENV = "OPENCODE_LOG_CONSOLE"

# Default log directory (macOS standard location)
LOG_DIR = Path.home() / "Library/Logs/OpenCodeMonitor"  # nosec B108

# Log file names
HUMAN_LOG_FILE = "opencode-monitor.log"
JSON_LOG_FILE = "opencode-monitor.json"
CRASH_LOG_FILE = "crash.log"

# Log level mapping
LOG_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


@dataclass
class LogConfig:
    """Configuration for the logging system.

    Attributes:
        log_dir: Directory where log files are stored
        human_log_max_bytes: Maximum size of human-readable log file before rotation
        human_log_backup_count: Number of backup files to keep for human logs
        json_log_max_bytes: Maximum size of JSON log file before rotation
        json_log_backup_count: Number of backup files to keep for JSON logs
        default_level: Default logging level
        console_enabled: Whether to output logs to console
    """

    log_dir: Path = field(default_factory=lambda: LOG_DIR)
    human_log_max_bytes: int = 10 * 1024 * 1024  # 10MB
    human_log_backup_count: int = 5
    json_log_max_bytes: int = 20 * 1024 * 1024  # 20MB
    json_log_backup_count: int = 3
    default_level: int = logging.INFO
    console_enabled: bool = False

    @property
    def human_log_path(self) -> Path:
        """Full path to the human-readable log file."""
        return self.log_dir / HUMAN_LOG_FILE

    @property
    def json_log_path(self) -> Path:
        """Full path to the JSON log file."""
        return self.log_dir / JSON_LOG_FILE

    @property
    def crash_log_path(self) -> Path:
        """Full path to the crash log file."""
        return self.log_dir / CRASH_LOG_FILE


def get_config() -> LogConfig:
    """Create a LogConfig from environment variables.

    Environment variables:
        OPENCODE_DEBUG: Set to '1', 'true', or 'yes' to enable debug mode
        OPENCODE_LOG_LEVEL: Set log level ('debug', 'info', 'warning', 'error', 'critical')
        OPENCODE_LOG_CONSOLE: Set to '1', 'true', or 'yes' to enable console output

    Returns:
        LogConfig with settings from environment, falling back to defaults.
    """
    config = LogConfig()

    # Check debug mode
    debug_mode = os.environ.get(DEBUG_ENV, "").lower() in ("1", "true", "yes")
    if debug_mode:
        config.default_level = logging.DEBUG
        config.console_enabled = True

    # Check explicit log level
    log_level_str = os.environ.get(LOG_LEVEL_ENV, "").lower()
    if log_level_str in LOG_LEVEL_MAP:
        config.default_level = LOG_LEVEL_MAP[log_level_str]

    # Check console output
    console_env = os.environ.get(LOG_CONSOLE_ENV, "").lower()
    if console_env in ("1", "true", "yes"):
        config.console_enabled = True
    elif console_env in ("0", "false", "no"):
        config.console_enabled = False

    return config


def ensure_log_directory(config: Optional[LogConfig] = None) -> Path:
    """Ensure the log directory exists.

    Args:
        config: Optional LogConfig. If not provided, uses default LOG_DIR.

    Returns:
        Path to the log directory.
    """
    log_dir = config.log_dir if config else LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir
