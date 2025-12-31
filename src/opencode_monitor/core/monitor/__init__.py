"""
OpenCode instance monitoring module.

This module provides functions to detect, monitor, and fetch data
from OpenCode instances running on the system.
"""

from .ports import find_opencode_ports, get_tty_for_port
from .ask_user import (
    OPENCODE_STORAGE_PATH,
    AskUserResult,
    check_pending_ask_user_from_disk,
    _find_latest_notify_ask_user,
    _has_activity_after_notify,
)
from .helpers import extract_tools_from_messages, count_todos
from .fetcher import fetch_instance, fetch_all_instances

__all__ = [
    # Configuration
    "OPENCODE_STORAGE_PATH",
    # Data classes
    "AskUserResult",
    # Port detection
    "find_opencode_ports",
    "get_tty_for_port",
    # Ask user detection
    "check_pending_ask_user_from_disk",
    "_find_latest_notify_ask_user",
    "_has_activity_after_notify",
    # Message/todo helpers
    "extract_tools_from_messages",
    "count_todos",
    # Instance fetching
    "fetch_instance",
    "fetch_all_instances",
]
