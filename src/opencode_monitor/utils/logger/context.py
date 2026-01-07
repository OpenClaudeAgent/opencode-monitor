"""
Logging context management for OpenCode Monitor.

Provides context variables for request and session tracking in logs.
"""

import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator, Optional

# Context variables for tracking
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)


def get_request_id() -> Optional[str]:
    """Get the current request ID from context.

    Returns:
        The current request ID, or None if not set.
    """
    return request_id_var.get()


def set_request_id(request_id: Optional[str]) -> None:
    """Set the current request ID in context.

    Args:
        request_id: The request ID to set, or None to clear.
    """
    request_id_var.set(request_id)


def get_session_id() -> Optional[str]:
    """Get the current session ID from context.

    Returns:
        The current session ID, or None if not set.
    """
    return session_id_var.get()


def set_session_id(session_id: Optional[str]) -> None:
    """Set the current session ID in context.

    Args:
        session_id: The session ID to set, or None to clear.
    """
    session_id_var.set(session_id)


def generate_request_id() -> str:
    """Generate a new unique request ID.

    Returns:
        A new UUID-based request ID (shortened to 8 characters).
    """
    return uuid.uuid4().hex[:8]


def generate_session_id() -> str:
    """Generate a new unique session ID.

    Returns:
        A new UUID-based session ID (shortened to 12 characters).
    """
    return uuid.uuid4().hex[:12]


@contextmanager
def log_context(
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    auto_request_id: bool = False,
    auto_session_id: bool = False,
) -> Generator[dict[str, Optional[str]], None, None]:
    """Context manager for setting log context.

    Sets request_id and/or session_id for the duration of the context.
    Values are automatically restored when the context exits.

    Args:
        request_id: Request ID to set. If None and auto_request_id is True, generates one.
        session_id: Session ID to set. If None and auto_session_id is True, generates one.
        auto_request_id: If True, auto-generate request_id if not provided.
        auto_session_id: If True, auto-generate session_id if not provided.

    Yields:
        Dictionary with the active context IDs.

    Example:
        with log_context(request_id="abc123"):
            logger.info("Processing request")  # Includes request_id in log

        with log_context(auto_request_id=True) as ctx:
            logger.info(f"Request {ctx['request_id']}")
    """
    # Save previous values
    old_request_id = request_id_var.get()
    old_session_id = session_id_var.get()

    # Determine new values
    new_request_id = request_id
    if new_request_id is None and auto_request_id:
        new_request_id = generate_request_id()

    new_session_id = session_id
    if new_session_id is None and auto_session_id:
        new_session_id = generate_session_id()

    # Set new values (only if provided or auto-generated)
    if new_request_id is not None:
        request_id_var.set(new_request_id)
    if new_session_id is not None:
        session_id_var.set(new_session_id)

    try:
        yield {
            "request_id": request_id_var.get(),
            "session_id": session_id_var.get(),
        }
    finally:
        # Restore previous values
        request_id_var.set(old_request_id)
        session_id_var.set(old_session_id)


class ContextFilter(logging.Filter):
    """Logging filter that adds context variables to log records.

    This filter adds request_id and session_id attributes to log records,
    allowing formatters to include them in the output.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context variables to the log record.

        Args:
            record: The log record to modify.

        Returns:
            Always returns True (record is always processed).
        """
        record.request_id = request_id_var.get()
        record.session_id = session_id_var.get()
        return True
