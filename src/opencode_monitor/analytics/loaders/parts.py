"""Parts (text and tool) data loader."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..db import AnalyticsDB
from ...utils.logger import info, debug, error
from ...utils.datetime import ms_to_datetime

# Type alias for part tuple (id, session_id, message_id, part_type, content, tool_name,
# tool_status, created_at, arguments, call_id, ended_at, duration_ms, error_message)
PartTuple = tuple[
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    datetime | None,
    Any,
    Any,
    datetime | None,
    Any,
    Any,
]


def load_parts_fast(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load part data by iterating through message directories.

    Loads both:
    - Text parts (user prompts, assistant responses)
    - Tool parts (tool invocations)

    Uses Python file iteration instead of DuckDB's read_json_auto
    for better performance with large numbers of files.
    """
    conn = db.connect()
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=max_days)
    cutoff_ts = cutoff.timestamp()

    text_count = 0
    tool_count = 0
    batch: list[PartTuple] = []
    batch_size = 500

    try:
        # Iterate through message directories
        for msg_dir in part_dir.iterdir():
            if not msg_dir.is_dir():
                continue

            # Check directory modification time for quick filtering
            try:
                if msg_dir.stat().st_mtime < cutoff_ts:
                    continue
            except OSError:
                continue

            # Process part files in this message directory
            for part_file in msg_dir.iterdir():
                if not part_file.suffix == ".json":
                    continue

                try:
                    with open(part_file, "r") as f:
                        data = json.load(f)

                    part_id = data.get("id")
                    if not part_id:
                        continue

                    session_id = data.get("sessionID")
                    message_id = data.get("messageID")
                    part_type = data.get("type")

                    # Get timestamp
                    time_data = data.get("time", {})
                    ts = time_data.get("start") or time_data.get("created")
                    created_at = ms_to_datetime(ts) if ts else None

                    if part_type == "text":
                        content = data.get("text")
                        if content:
                            batch.append(
                                (
                                    part_id,
                                    session_id,
                                    message_id,
                                    part_type,
                                    content,
                                    None,  # tool_name
                                    None,  # tool_status
                                    created_at,
                                    None,  # arguments
                                    None,  # call_id
                                    None,  # ended_at
                                    None,  # duration_ms
                                    None,  # error_message
                                )
                            )
                            text_count += 1
                    elif part_type == "tool":
                        tool_name = data.get("tool")
                        state = data.get("state", {})
                        tool_status = (
                            state.get("status") if isinstance(state, dict) else None
                        )
                        # Extract tool arguments from state.input
                        tool_input = (
                            state.get("input", {}) if isinstance(state, dict) else {}
                        )
                        arguments = json.dumps(tool_input) if tool_input else None

                        # Plan 36: Extract enriched fields
                        call_id = data.get("callID")

                        # Timing: get end timestamp and calculate duration
                        start_ts = time_data.get("start")
                        end_ts = time_data.get("end")
                        ended_at = ms_to_datetime(end_ts) if end_ts else None
                        duration_ms = (
                            (end_ts - start_ts) if (start_ts and end_ts) else None
                        )

                        # Error message from state
                        error_message = (
                            state.get("error") if isinstance(state, dict) else None
                        )

                        if tool_name:
                            batch.append(
                                (
                                    part_id,
                                    session_id,
                                    message_id,
                                    part_type,
                                    None,  # content
                                    tool_name,
                                    tool_status,
                                    created_at,
                                    arguments,
                                    call_id,
                                    ended_at,
                                    duration_ms,
                                    error_message,
                                )
                            )
                            tool_count += 1

                    # Batch insert
                    if len(batch) >= batch_size:
                        conn.executemany(
                            """INSERT OR REPLACE INTO parts 
                               (id, session_id, message_id, part_type, content, tool_name, tool_status, 
                                created_at, arguments, call_id, ended_at, duration_ms, error_message)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            batch,
                        )
                        batch = []

                except (json.JSONDecodeError, OSError) as e:
                    debug(f"Error reading part file {part_file}: {e}")
                    continue

        # Insert remaining batch
        if batch:
            conn.executemany(
                """INSERT OR REPLACE INTO parts 
                   (id, session_id, message_id, part_type, content, tool_name, tool_status, 
                    created_at, arguments, call_id, ended_at, duration_ms, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                batch,
            )

        total = text_count + tool_count
        info(f"Loaded {total} parts ({text_count} text, {tool_count} tools)")
        return total

    except Exception as e:  # Intentional catch-all: various errors possible
        error(f"Parts load failed: {e}")
        return 0
