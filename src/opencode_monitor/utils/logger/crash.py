"""
Crash handler for OpenCode Monitor.

Provides unhandled exception logging to ensure crashes are recorded.
"""

import logging
import sys
import traceback
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Callable, Optional, Type

from .config import LogConfig, ensure_log_directory, get_config

# Type alias for excepthook
ExceptHook = Callable[
    [Type[BaseException], BaseException, Optional[TracebackType]], Any
]

# Module-level state
_original_excepthook: Optional[ExceptHook] = None
_crash_logger: Optional[logging.Logger] = None


def crash_handler(
    exc_type: Type[BaseException],
    exc_value: BaseException,
    exc_traceback: Optional[TracebackType],
) -> None:
    """Handle uncaught exceptions by logging them.

    This function is installed as sys.excepthook to catch all unhandled exceptions.
    It logs the full exception details to both the crash log and the main logger.

    Args:
        exc_type: The exception class.
        exc_value: The exception instance.
        exc_traceback: The traceback object.
    """
    # Don't handle KeyboardInterrupt - let it pass through
    if issubclass(exc_type, KeyboardInterrupt):
        if _original_excepthook:
            _original_excepthook(exc_type, exc_value, exc_traceback)
        return

    # Format the exception
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    tb_text = "".join(tb_lines)

    # Log to crash logger if available
    if _crash_logger:
        _crash_logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    # Also write directly to crash log file as a safety measure
    try:
        config = get_config()
        ensure_log_directory(config)
        with open(config.crash_log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(f"CRASH at {timestamp}\n")
            f.write(f"{'=' * 80}\n")
            f.write(tb_text)
            f.write("\n")
    except Exception:
        # If we can't write to crash log, at least try stderr
        pass

    # Print to stderr as well
    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"UNHANDLED EXCEPTION at {timestamp}", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)
    print(tb_text, file=sys.stderr)

    # Call original excepthook if available
    if _original_excepthook:
        _original_excepthook(exc_type, exc_value, exc_traceback)


def install_crash_handler(
    logger: logging.Logger, config: Optional[LogConfig] = None
) -> None:
    """Install the crash handler as sys.excepthook.

    This should be called once during application startup to ensure
    all unhandled exceptions are logged.

    Args:
        logger: The logger to use for crash logging.
        config: Optional LogConfig for crash log location.
    """
    global _original_excepthook, _crash_logger

    # Save original excepthook
    if _original_excepthook is None:
        _original_excepthook = sys.excepthook

    # Store logger reference
    _crash_logger = logger

    # Install our handler
    sys.excepthook = crash_handler


def uninstall_crash_handler() -> None:
    """Restore the original sys.excepthook.

    This is primarily useful for testing.
    """
    global _original_excepthook, _crash_logger

    if _original_excepthook is not None:
        sys.excepthook = _original_excepthook
        _original_excepthook = None

    _crash_logger = None


def log_crash(
    logger: logging.Logger,
    exc_type: Type[BaseException],
    exc_value: BaseException,
    exc_traceback: Optional[TracebackType],
    context: Optional[str] = None,
) -> None:
    """Manually log a crash/exception.

    Use this function to log exceptions that are caught but still represent
    critical failures that should be recorded in the crash log.

    Args:
        logger: The logger to use.
        exc_type: The exception class.
        exc_value: The exception instance.
        exc_traceback: The traceback object.
        context: Optional context string describing where the crash occurred.
    """
    message = "Critical error"
    if context:
        message = f"Critical error in {context}"

    logger.critical(
        message,
        exc_info=(exc_type, exc_value, exc_traceback),
    )
