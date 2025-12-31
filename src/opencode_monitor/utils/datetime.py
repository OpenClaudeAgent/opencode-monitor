"""Datetime utilities for consistent timestamp handling."""

from datetime import datetime, timezone
from typing import Optional


def parse_timestamp(timestamp: Optional[int | float]) -> Optional[datetime]:
    """Parse a timestamp (milliseconds or seconds) to datetime.

    Args:
        timestamp: Unix timestamp in milliseconds or seconds, or None

    Returns:
        datetime object (UTC) or None if timestamp is None
    """
    if timestamp is None:
        return None

    # Convert milliseconds to seconds if needed (timestamps > 1e10 are in ms)
    ts = timestamp / 1000.0 if timestamp > 1e10 else timestamp
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def format_iso(dt: Optional[datetime] = None) -> str:
    """Format datetime as ISO 8601 string.

    Args:
        dt: datetime object, or None for current time

    Returns:
        ISO 8601 formatted string
    """
    if dt is None:
        dt = datetime.now(tz=timezone.utc)
    return dt.isoformat()


def now_iso() -> str:
    """Get current time as ISO 8601 string.

    Returns:
        Current time formatted as ISO 8601
    """
    return datetime.now().isoformat()


def timestamp_to_seconds(timestamp: Optional[int | float]) -> float:
    """Normalize timestamp to seconds.

    Args:
        timestamp: Unix timestamp in milliseconds or seconds, or None

    Returns:
        Timestamp in seconds (defaults to current time if None)
    """
    import time

    if timestamp is None:
        return time.time()

    # Convert milliseconds to seconds if needed
    return timestamp / 1000.0 if timestamp > 1e10 else timestamp
