"""File operations data loader."""

import json
import time as time_module
from datetime import datetime, timedelta
from pathlib import Path

from ..db import AnalyticsDB
from ...utils.logger import info, debug
from ...utils.datetime import ms_to_datetime
from .utils import collect_recent_part_files, chunked


def load_file_operations(
    db: AnalyticsDB, storage_path: Path, max_days: int = 30
) -> int:
    """Load file operations from tool invocations.

    Extracts read, write, and edit operations from parts data.
    Uses chunked Python processing to avoid CPU spikes.

    Args:
        db: Analytics database instance
        storage_path: Path to OpenCode storage
        max_days: Only load operations from the last N days

    Returns:
        Number of file operations loaded
    """
    conn = db.connect()
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return 0

    # Phase 1: Collect recent files (mtime filter)
    recent_files = collect_recent_part_files(part_dir, max_days)
    if not recent_files:
        info("No recent part files found for file operations")
        return 0

    debug(f"Scanning {len(recent_files)} recent part files for file operations")

    cutoff = datetime.now() - timedelta(days=max_days)
    operations: list[dict] = []
    file_tools = {"read", "write", "edit"}

    # Phase 2: Process files in chunks (avoid CPU spikes)
    chunk_size = 500
    for chunk in chunked(recent_files, chunk_size):
        for file_path in chunk:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)

                tool_name = data.get("tool")
                if tool_name not in file_tools:
                    continue

                state = data.get("state", {})
                input_data = state.get("input", {})

                # Extract file path from tool input
                path = input_data.get("filePath") or input_data.get("path")
                if not path:
                    continue

                time_data = state.get("time", {})
                start_ts = time_data.get("start")
                timestamp = ms_to_datetime(start_ts)

                # Skip old entries
                if timestamp and timestamp < cutoff:
                    continue

                operations.append(
                    {
                        "id": data.get("id"),
                        "session_id": data.get("sessionID"),
                        "trace_id": None,
                        "operation": tool_name,
                        "file_path": path,
                        "timestamp": timestamp,
                        "risk_level": "normal",
                        "risk_reason": None,
                    }
                )

            except (json.JSONDecodeError, OSError):
                continue

        # Small sleep between chunks to let UI breathe
        time_module.sleep(0.01)

    if not operations:
        info("No file operations found")
        return 0

    for op in operations:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO file_operations
                (id, session_id, trace_id, operation, file_path, timestamp, risk_level, risk_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    op["id"],
                    op["session_id"],
                    op["trace_id"],
                    op["operation"],
                    op["file_path"],
                    op["timestamp"],
                    op["risk_level"],
                    op["risk_reason"],
                ],
            )
        except Exception as e:
            debug(f"File operation insert failed for {op.get('id', 'unknown')}: {e}")
            continue

    count = conn.execute("SELECT COUNT(*) FROM file_operations").fetchone()[0]
    info(f"Loaded {count} file operations")
    return count
