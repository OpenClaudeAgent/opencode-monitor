"""
Helper functions for trace building.

Pure utility functions extracted from TraceBuilder for better testability.
"""

import json
from typing import Optional


def determine_status(tool_status: Optional[str]) -> str:
    """Determine trace status from tool status.

    Args:
        tool_status: Raw tool status string

    Returns:
        Normalized status (running/completed/error)
    """
    if not tool_status:
        return "running"

    status_lower = tool_status.lower()
    if status_lower in ("completed", "success"):
        return "completed"
    elif status_lower in ("error", "failed"):
        return "error"
    else:
        return "running"


def extract_prompt(arguments: Optional[str]) -> str:
    """Extract prompt from task tool arguments.

    Args:
        arguments: JSON string of tool arguments

    Returns:
        Prompt text or empty string
    """
    if not arguments:
        return ""

    try:
        data = json.loads(arguments)
        return data.get("prompt", "") or ""
    except (json.JSONDecodeError, TypeError):
        return ""
