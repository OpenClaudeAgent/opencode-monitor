"""
Log formatters for OpenCode Monitor.

Provides human-readable and JSON formatters for structured logging.
"""

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any


class HumanFormatter(logging.Formatter):
    """Human-readable log formatter.

    Format: YYYY-MM-DD HH:MM:SS.mmm | LEVEL | component | file:line | message

    Example:
        2024-01-15 14:23:45.123 | INFO  | opencode.api | server.py:42 | Server started
    """

    # Level name padding for alignment
    LEVEL_WIDTH = 5

    def __init__(self) -> None:
        """Initialize the formatter."""
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a human-readable string.

        Args:
            record: The log record to format.

        Returns:
            Formatted log string.
        """
        # Timestamp with milliseconds
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.") + f"{int(record.msecs):03d}"

        # Level name, padded for alignment
        level = record.levelname.ljust(self.LEVEL_WIDTH)

        # Component (logger name, shortened)
        component = self._shorten_name(record.name)

        # File location
        location = f"{record.filename}:{record.lineno}"

        # Build message
        message = record.getMessage()

        # Add context if present
        context_parts = []
        request_id = getattr(record, "request_id", None)
        session_id = getattr(record, "session_id", None)
        if request_id:
            context_parts.append(f"req={request_id}")
        if session_id:
            context_parts.append(f"session={session_id}")

        if context_parts:
            context_str = " [" + " ".join(context_parts) + "]"
            message = message + context_str

        # Format the base line
        formatted = f"{time_str} | {level} | {component} | {location} | {message}"

        # Add exception info if present
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            formatted = f"{formatted}\n{exc_text}"

        return formatted

    def _shorten_name(self, name: str, max_len: int = 20) -> str:
        """Shorten a logger name for display.

        Args:
            name: The full logger name.
            max_len: Maximum length for the shortened name.

        Returns:
            Shortened name, padded to max_len.
        """
        if len(name) <= max_len:
            return name.ljust(max_len)

        # Try to keep meaningful parts
        parts = name.split(".")
        if len(parts) >= 2:
            # Keep first and last parts
            shortened = f"{parts[0]}...{parts[-1]}"
            if len(shortened) <= max_len:
                return shortened.ljust(max_len)

        # Just truncate
        return name[: max_len - 3] + "..."


class JsonFormatter(logging.Formatter):
    """JSON Lines log formatter.

    Produces one JSON object per log line, suitable for log aggregation systems.

    Output fields:
        - timestamp: ISO 8601 format with timezone
        - level: Log level name
        - logger: Logger name (component)
        - message: Log message
        - file: Source file name
        - line: Source line number
        - function: Function name
        - request_id: Request context ID (if set)
        - session_id: Session context ID (if set)
        - exception: Exception details (if present)
    """

    def __init__(self) -> None:
        """Initialize the formatter."""
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            JSON string (single line).
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add context if present
        request_id = getattr(record, "request_id", None)
        session_id = getattr(record, "session_id", None)
        if request_id:
            log_data["request_id"] = request_id
        if session_id:
            log_data["session_id"] = session_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self._format_traceback(record.exc_info),
            }

        # Ensure single line output (JSON Lines format)
        return json.dumps(log_data, ensure_ascii=False, default=str)

    def _format_traceback(self, exc_info: tuple) -> list[str]:
        """Format exception traceback as a list of strings.

        Args:
            exc_info: Exception info tuple from sys.exc_info().

        Returns:
            List of traceback lines.
        """
        if not exc_info or not exc_info[2]:
            return []

        tb_lines = traceback.format_exception(*exc_info)
        # Split into individual lines and remove empty ones
        result = []
        for line in tb_lines:
            for subline in line.splitlines():
                if subline.strip():
                    result.append(subline)
        return result
