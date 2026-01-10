"""
Bulk load initial data using DuckDB's read_json_auto().

This module provides fast initial loading of OpenCode storage files
directly into the database, bypassing file-by-file processing.

Performance target: 227k files in < 30 seconds (~20k files/sec)
"""

import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ...db import AnalyticsDB

from ....utils.logger import info, debug


# Threshold for cold start detection (< 100 sessions = cold start)
COLD_START_THRESHOLD = 100


def is_cold_start(db: "AnalyticsDB") -> bool:
    """Check if this is a cold start (few/no indexed data).

    Args:
        db: Analytics database instance

    Returns:
        True if cold start (should use bulk load), False otherwise
    """
    conn = db.connect()
    try:
        result = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        session_count = result[0] if result else 0
        return session_count < COLD_START_THRESHOLD
    except Exception:
        # Table might not exist yet
        return True


def bulk_load_initial(
    db: "AnalyticsDB",
    storage_path: Path,
    stats: Optional[dict] = None,
) -> dict:
    """Perform bulk load of all storage files using read_json_auto().

    This function:
    1. Uses DuckDB's read_json_auto() to load sessions, messages, parts
    2. Marks all loaded files in file_index
    3. Creates agent_traces for root sessions

    Args:
        db: Analytics database instance
        storage_path: Path to OpenCode storage directory
        stats: Optional stats dict to update

    Returns:
        Dict with counts of loaded records
    """
    start_time = time.time()
    results = {
        "sessions": 0,
        "messages": 0,
        "parts": 0,
        "traces_created": 0,
        "files_indexed": 0,
        "duration_s": 0,
    }

    conn = db.connect()

    info("[BulkLoad] Starting bulk load...")
    info(f"[BulkLoad] Storage path: {storage_path}")

    # Ensure file_index table exists (normally created by FileTracker)
    _ensure_file_index_table(conn)

    # Step 1: Load sessions
    sessions_glob = str(storage_path / "session" / "*" / "*.json")
    sessions_loaded = _bulk_load_sessions(conn, sessions_glob)
    results["sessions"] = sessions_loaded
    info(f"[BulkLoad] Sessions loaded: {sessions_loaded}")

    # Step 2: Load messages
    messages_glob = str(storage_path / "message" / "*" / "*.json")
    messages_loaded = _bulk_load_messages(conn, messages_glob)
    results["messages"] = messages_loaded
    info(f"[BulkLoad] Messages loaded: {messages_loaded}")

    # Step 3: Load parts
    parts_glob = str(storage_path / "part" / "*" / "*.json")
    parts_loaded = _bulk_load_parts(conn, parts_glob)
    results["parts"] = parts_loaded
    info(f"[BulkLoad] Parts loaded: {parts_loaded}")

    # Step 4: Mark files as indexed in file_index
    files_indexed = _mark_files_indexed(conn, storage_path)
    results["files_indexed"] = files_indexed
    info(f"[BulkLoad] Files marked indexed: {files_indexed}")

    # Step 5: Create agent_traces for root sessions
    traces_created = _create_root_traces(conn)
    results["traces_created"] = traces_created
    info(f"[BulkLoad] Root traces created: {traces_created}")

    # Calculate duration
    duration = time.time() - start_time
    results["duration_s"] = round(duration, 2)

    # Update shared stats if provided
    if stats is not None:
        stats["sessions_indexed"] = stats.get("sessions_indexed", 0) + sessions_loaded
        stats["messages_indexed"] = stats.get("messages_indexed", 0) + messages_loaded
        stats["parts_indexed"] = stats.get("parts_indexed", 0) + parts_loaded
        stats["traces_created"] = stats.get("traces_created", 0) + traces_created
        stats["files_processed"] = stats.get("files_processed", 0) + files_indexed

    total_records = sessions_loaded + messages_loaded + parts_loaded
    speed = total_records / duration if duration > 0 else 0

    info(
        f"[BulkLoad] COMPLETE: {total_records:,} records in {duration:.1f}s "
        f"({speed:,.0f}/s)"
    )

    return results


def _ensure_file_index_table(conn) -> None:
    """Ensure file_index table exists for marking files as indexed."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_index (
            file_path VARCHAR PRIMARY KEY,
            file_type VARCHAR NOT NULL,
            mtime DOUBLE NOT NULL,
            size INTEGER NOT NULL,
            record_id VARCHAR,
            indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            error_message VARCHAR,
            status VARCHAR DEFAULT 'indexed'
        )
    """)


def _bulk_load_sessions(conn, glob_pattern: str) -> int:
    """Bulk load sessions using read_json_auto().

    DuckDB read_json_auto returns columns directly from JSON fields.
    Nested objects use dot notation: "time".created, summary.additions

    Args:
        conn: DuckDB connection
        glob_pattern: Glob pattern for session files

    Returns:
        Number of sessions loaded
    """
    try:
        # Check how many files exist
        count_result = conn.execute(
            f"""
            SELECT COUNT(*) FROM read_json_auto(
                '{glob_pattern}',
                format='auto',
                ignore_errors=true,
                union_by_name=true,
                maximum_object_size=104857600
            )
            """
        ).fetchone()
        total_files = count_result[0] if count_result else 0

        if total_files == 0:
            return 0

        debug(f"[BulkLoad] Found {total_files} session files")

        # Count sessions before insert
        before = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        before_count = before[0] if before else 0

        # Bulk INSERT sessions
        # DuckDB read_json_auto returns columns directly from JSON fields
        # Use union_by_name=true to handle files with different schemas (e.g., parentID missing)
        conn.execute(
            f"""
            INSERT OR REPLACE INTO sessions (
                id, project_id, directory, title, parent_id, version,
                additions, deletions, files_changed, created_at, updated_at
            )
            SELECT
                id,
                "projectID" as project_id,
                directory,
                title,
                "parentID" as parent_id,
                version,
                COALESCE(summary.additions, 0) as additions,
                COALESCE(summary.deletions, 0) as deletions,
                COALESCE(summary.files, 0) as files_changed,
                epoch_ms("time".created) as created_at,
                epoch_ms("time".updated) as updated_at
            FROM read_json_auto(
                '{glob_pattern}',
                format='auto',
                ignore_errors=true,
                union_by_name=true,
                maximum_object_size=104857600
            )
            WHERE id IS NOT NULL
            """
        )

        # Count sessions after insert
        after = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        after_count = after[0] if after else 0

        return after_count - before_count

    except Exception as e:
        debug(f"[BulkLoad] Failed to load sessions: {e}")
        return 0


def _bulk_load_messages(conn, glob_pattern: str) -> int:
    """Bulk load messages using read_json_auto().

    Args:
        conn: DuckDB connection
        glob_pattern: Glob pattern for message files

    Returns:
        Number of messages loaded
    """
    try:
        # Check if any files exist
        count_result = conn.execute(
            f"""
            SELECT COUNT(*) FROM read_json_auto(
                '{glob_pattern}',
                format='auto',
                ignore_errors=true,
                union_by_name=true,
                maximum_object_size=104857600
            )
            """
        ).fetchone()
        total_files = count_result[0] if count_result else 0

        if total_files == 0:
            return 0

        # Count messages before insert
        before = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
        before_count = before[0] if before else 0

        # Bulk INSERT messages
        conn.execute(
            f"""
            INSERT OR REPLACE INTO messages (
                id, session_id, parent_id, role, agent, model_id, provider_id,
                mode, cost, finish_reason, working_dir,
                tokens_input, tokens_output, tokens_reasoning,
                tokens_cache_read, tokens_cache_write, created_at, completed_at
            )
            SELECT
                id,
                "sessionID" as session_id,
                "parentID" as parent_id,
                role,
                agent,
                "modelID" as model_id,
                "providerID" as provider_id,
                mode,
                COALESCE(cost, 0) as cost,
                finish as finish_reason,
                path.cwd as working_dir,
                COALESCE(tokens.input, 0) as tokens_input,
                COALESCE(tokens.output, 0) as tokens_output,
                COALESCE(tokens.reasoning, 0) as tokens_reasoning,
                COALESCE(tokens.cache.read, 0) as tokens_cache_read,
                COALESCE(tokens.cache.write, 0) as tokens_cache_write,
                epoch_ms("time".created) as created_at,
                epoch_ms("time".completed) as completed_at
            FROM read_json_auto(
                '{glob_pattern}',
                format='auto',
                ignore_errors=true,
                union_by_name=true,
                maximum_object_size=104857600
            )
            WHERE id IS NOT NULL
            """
        )

        # Count messages after insert
        after = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
        after_count = after[0] if after else 0

        return after_count - before_count

    except Exception as e:
        debug(f"[BulkLoad] Failed to load messages: {e}")
        return 0


def _bulk_load_parts(conn, glob_pattern: str) -> int:
    """Bulk load parts using read_json_auto().

    Parts have complex structure that varies by type (text, tool, reasoning, etc.)
    We load the common fields and extract tool-specific fields where present.

    Args:
        conn: DuckDB connection
        glob_pattern: Glob pattern for part files

    Returns:
        Number of parts loaded
    """
    try:
        # Check if any files exist
        count_result = conn.execute(
            f"""
            SELECT COUNT(*) FROM read_json_auto(
                '{glob_pattern}',
                format='auto',
                ignore_errors=true,
                union_by_name=true,
                maximum_object_size=104857600
            )
            """
        ).fetchone()
        total_files = count_result[0] if count_result else 0

        if total_files == 0:
            return 0

        # Count parts before insert
        before = conn.execute("SELECT COUNT(*) FROM parts").fetchone()
        before_count = before[0] if before else 0

        # Bulk INSERT parts with conditional field extraction
        # Note: JSON field 'text' holds text content, 'state.output' holds tool result
        conn.execute(
            f"""
            INSERT OR REPLACE INTO parts (
                id, session_id, message_id, part_type, content, 
                tool_name, tool_status, call_id, tool_title,
                created_at, ended_at, duration_ms, arguments, error_message
            )
            SELECT
                id,
                "sessionID" as session_id,
                "messageID" as message_id,
                "type" as part_type,
                -- Content: cast to VARCHAR to handle JSON-typed nulls
                -- text field may be JSON type when null, state.output is always VARCHAR
                CASE 
                    WHEN "type" = 'text' THEN text::VARCHAR
                    WHEN "type" = 'tool' THEN LEFT(state.output::VARCHAR, 10000)
                    ELSE NULL
                END as content,
                -- Tool specific fields
                tool as tool_name,
                state.status as tool_status,
                "callID" as call_id,
                state.title as tool_title,
                -- Timestamps (milliseconds to timestamp)
                CASE 
                    WHEN state."time".start IS NOT NULL 
                    THEN epoch_ms(state."time".start)
                    ELSE NULL
                END as created_at,
                CASE
                    WHEN state."time"."end" IS NOT NULL
                    THEN epoch_ms(state."time"."end")
                    ELSE NULL
                END as ended_at,
                -- Duration calculated from timestamps
                CASE
                    WHEN state."time".start IS NOT NULL 
                         AND state."time"."end" IS NOT NULL
                    THEN CAST(state."time"."end" - state."time".start AS INTEGER)
                    ELSE NULL
                END as duration_ms,
                -- Tool arguments (truncated for safety, convert struct to string)
                LEFT(CAST(state.input AS VARCHAR), 50000) as arguments,
                -- Error message: try to get from metadata, but may not exist
                NULL as error_message  -- Populated by later processing if needed
            FROM read_json_auto(
                '{glob_pattern}',
                format='auto',
                ignore_errors=true,
                union_by_name=true,
                maximum_object_size=104857600
            )
            WHERE id IS NOT NULL
            """
        )

        # Count parts after insert
        after = conn.execute("SELECT COUNT(*) FROM parts").fetchone()
        after_count = after[0] if after else 0

        return after_count - before_count

    except Exception as e:
        # Note: DuckDB's ignore_errors doesn't work for malformed JSON in 'auto' format
        # If files have invalid escape sequences, bulk load will fail for parts
        # The Reconciler will handle these files incrementally via BatchProcessor
        debug(
            f"[BulkLoad] Parts bulk load failed (will use incremental): "
            f"{type(e).__name__}: {str(e)[:100]}"
        )
        info(
            "[BulkLoad] Parts contain malformed JSON - falling back to incremental indexing"
        )
        return 0


def _mark_files_indexed(conn, storage_path: Path) -> int:
    """Mark all bulk-loaded files as indexed in file_index.

    Uses read_json_auto to get file paths and bulk insert into file_index.

    Args:
        conn: DuckDB connection
        storage_path: Path to storage directory

    Returns:
        Number of files marked as indexed
    """
    total_marked = 0

    for file_type, subdir in [
        ("session", "session"),
        ("message", "message"),
        ("part", "part"),
    ]:
        glob_pattern = str(storage_path / subdir / "*" / "*.json")

        try:
            # Count before
            before = conn.execute(
                f"SELECT COUNT(*) FROM file_index WHERE file_type = '{file_type}'"
            ).fetchone()
            before_count = before[0] if before else 0

            # Insert file index entries with file metadata
            # filename=true adds a 'filename' column with the file path
            conn.execute(
                f"""
                INSERT OR REPLACE INTO file_index (
                    file_path, file_type, mtime, size, record_id, status
                )
                SELECT
                    filename as file_path,
                    '{file_type}' as file_type,
                    0.0 as mtime,
                    0 as size,
                    id as record_id,
                    'indexed' as status
                FROM read_json_auto(
                    '{glob_pattern}',
                    format='auto',
                    ignore_errors=true,
                union_by_name=true,
                    filename=true,
                    maximum_object_size=104857600
                )
                WHERE id IS NOT NULL
                """
            )

            # Count after
            after = conn.execute(
                f"SELECT COUNT(*) FROM file_index WHERE file_type = '{file_type}'"
            ).fetchone()
            after_count = after[0] if after else 0

            total_marked += after_count - before_count

        except Exception as e:
            debug(f"[BulkLoad] Failed to mark {file_type} files: {e}")

    return total_marked


def _create_root_traces(conn) -> int:
    """Create agent_traces for root sessions (sessions without parent).

    Root sessions are user-initiated sessions that don't have a parentID.
    They get a special trace with trace_id = 'root_{session_id}'.

    Args:
        conn: DuckDB connection

    Returns:
        Number of traces created
    """
    try:
        # Count before
        before = conn.execute(
            "SELECT COUNT(*) FROM agent_traces WHERE trace_id LIKE 'root_%'"
        ).fetchone()
        before_count = before[0] if before else 0

        # Insert root traces for sessions without parent_id
        conn.execute(
            """
            INSERT OR REPLACE INTO agent_traces (
                trace_id, session_id, parent_trace_id, parent_agent,
                subagent_type, prompt_input, prompt_output,
                started_at, ended_at, duration_ms,
                tokens_in, tokens_out, status, tools_used, child_session_id
            )
            SELECT
                'root_' || s.id as trace_id,
                s.id as session_id,
                NULL as parent_trace_id,
                'user' as parent_agent,
                -- Use first assistant agent or 'user' as subagent_type
                COALESCE(
                    (SELECT m.agent FROM messages m 
                     WHERE m.session_id = s.id AND m.role = 'assistant' AND m.agent IS NOT NULL
                     ORDER BY m.created_at LIMIT 1),
                    'user'
                ) as subagent_type,
                COALESCE(s.title, '(No prompt)') as prompt_input,
                NULL as prompt_output,
                s.created_at as started_at,
                s.updated_at as ended_at,
                -- Duration in ms
                CASE 
                    WHEN s.created_at IS NOT NULL AND s.updated_at IS NOT NULL
                    THEN CAST(
                        EXTRACT(EPOCH FROM (s.updated_at - s.created_at)) * 1000 
                        AS INTEGER
                    )
                    ELSE NULL
                END as duration_ms,
                -- Aggregate tokens from messages
                (SELECT COALESCE(SUM(tokens_input), 0) FROM messages m WHERE m.session_id = s.id) as tokens_in,
                (SELECT COALESCE(SUM(tokens_output), 0) FROM messages m WHERE m.session_id = s.id) as tokens_out,
                'completed' as status,
                ARRAY[]::VARCHAR[] as tools_used,
                s.id as child_session_id
            FROM sessions s
            WHERE s.parent_id IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM agent_traces t WHERE t.trace_id = 'root_' || s.id
              )
            """
        )

        # Count after
        after = conn.execute(
            "SELECT COUNT(*) FROM agent_traces WHERE trace_id LIKE 'root_%'"
        ).fetchone()
        after_count = after[0] if after else 0

        return after_count - before_count

    except Exception as e:
        debug(f"[BulkLoad] Failed to create root traces: {e}")
        return 0
