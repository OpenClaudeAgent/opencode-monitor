"""
Database mock factories for security auditor tests.

Provides mock database objects and helper functions.
"""

from typing import Any
from unittest.mock import MagicMock


def create_default_auditor_stats() -> dict:
    """Create default stats dict for auditor mocking.

    Returns:
        Dict with all auditor stats initialized to 0
    """
    return {
        "total_scanned": 0,
        "total_commands": 0,
        "total_reads": 0,
        "total_writes": 0,
        "total_webfetches": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "reads_critical": 0,
        "reads_high": 0,
        "reads_medium": 0,
        "writes_critical": 0,
        "writes_high": 0,
        "writes_medium": 0,
        "webfetches_critical": 0,
        "webfetches_high": 0,
        "webfetches_medium": 0,
    }


def create_mock_db(
    stats: dict | None = None,
    scanned_ids: set | None = None,
) -> MagicMock:
    """Create a mock SecurityDatabase with default configuration.

    SecurityDatabase now includes scanner methods (merged from SecurityScannerDuckDB).

    Args:
        stats: Custom stats dict (uses defaults if None)
        scanned_ids: Set of already scanned IDs

    Returns:
        MagicMock configured as SecurityDatabase
    """
    db = MagicMock()
    db.get_stats.return_value = stats or create_default_auditor_stats()
    db.get_all_scanned_ids.return_value = scanned_ids or set()
    db.get_commands_by_level.return_value = []
    db.get_reads_by_level.return_value = []
    db.get_writes_by_level.return_value = []
    db.get_webfetches_by_level.return_value = []
    db.get_all_commands.return_value = []
    db.get_all_reads.return_value = []
    db.get_all_writes.return_value = []
    db.get_all_webfetches.return_value = []
    db.insert_command.return_value = True
    db.insert_read.return_value = True
    db.insert_write.return_value = True
    db.insert_webfetch.return_value = True
    # Scanner methods (merged from SecurityScannerDuckDB)
    db.get_unscanned_files.return_value = []
    db.get_scanned_count.return_value = 0
    db.mark_scanned_batch.return_value = 0
    db.mark_scanned.return_value = None
    db.clear_scanned.return_value = None
    return db


def create_tool_file_content(
    tool: str,
    session_id: str = "sess-001",
    timestamp: int = 1703001000000,
    **input_args: Any,
) -> dict:
    """Factory to create tool file content for auditor tests.

    Args:
        tool: Tool name (bash, read, write, edit, webfetch)
        session_id: Session ID
        timestamp: Timestamp in milliseconds
        **input_args: Additional input arguments for the tool

    Examples:
        >>> create_tool_file_content("bash", command="ls -la")
        >>> create_tool_file_content("read", filePath="/etc/passwd")
        >>> create_tool_file_content("webfetch", url="https://example.com")

    Returns:
        Tool file content dict matching OpenCode format
    """
    return {
        "type": "tool",
        "tool": tool,
        "sessionID": session_id,
        "state": {
            "input": input_args,
            "time": {"start": timestamp},
        },
    }
