"""
Structured logging for OpenCode Monitor
"""

import logging
import os
import sys
from datetime import datetime

LOG_FILE = "/tmp/opencode-monitor.log"
DEBUG_ENV = "OPENCODE_DEBUG"


def setup_logger(name: str = "opencode") -> logging.Logger:
    """Setup and return a configured logger"""
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Set level based on environment
    debug_mode = os.environ.get(DEBUG_ENV, "").lower() in ("1", "true", "yes")
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    # File handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)

    # Console handler (stderr) - only warnings and above unless debug
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.WARNING)

    # Format
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Global logger instance
log = setup_logger()


def debug(msg: str, *args):
    """Log debug message"""
    log.debug(msg, *args)


def info(msg: str, *args):
    """Log info message"""
    log.info(msg, *args)


def warn(msg: str, *args):
    """Log warning message"""
    log.warning(msg, *args)


def error(msg: str, *args):
    """Log error message"""
    log.error(msg, *args)
