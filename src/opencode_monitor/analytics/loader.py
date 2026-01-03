"""
JSON data loader for OpenCode storage.

Uses DuckDB's native JSON reading for maximum performance.
Supports both delegation traces (task tool) and root sessions (direct conversations).
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .db import AnalyticsDB
from .models import AgentTrace
from ..utils.logger import info, debug, error
from ..utils.datetime import ms_to_datetime


# Constants for root session traces
ROOT_TRACE_PREFIX = "root_"
ROOT_AGENT_TYPE = "user"  # Root sessions are direct user conversations


def get_opencode_storage_path() -> Path:
    """Get the path to OpenCode storage directory."""
    return Path.home() / ".local" / "share" / "opencode" / "storage"


def load_sessions_fast(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load session data using DuckDB's JSON reader."""
    conn = db.connect()
    session_dir = storage_path / "session"

    if not session_dir.exists():
        return 0

    json_pattern = str(session_dir) + "/**/*.json"
    cutoff_ts = int((datetime.now() - timedelta(days=max_days)).timestamp() * 1000)

    try:
        # Load base columns (always present in all JSON files)
        conn.execute(f"""
            INSERT OR REPLACE INTO sessions (id, project_id, directory, title, created_at, updated_at)
            SELECT
                id,
                projectID as project_id,
                directory,
                title,
                epoch_ms(time.created) as created_at,
                epoch_ms(time.updated) as updated_at
            FROM read_json_auto('{json_pattern}', 
                                maximum_object_size=50000000,
                                ignore_errors=true)
            WHERE id IS NOT NULL
              AND time.created >= {cutoff_ts}
        """)

        # Update enriched columns if available in JSON (newer OpenCode versions)
        try:
            conn.execute(f"""
                UPDATE sessions SET
                    parent_id = src.parentID,
                    version = src.version,
                    additions = COALESCE(src.summary.additions, 0),
                    deletions = COALESCE(src.summary.deletions, 0),
                    files_changed = COALESCE(src.summary.files, 0)
                FROM (
                    SELECT id, parentID, version, summary
                    FROM read_json_auto('{json_pattern}',
                                        maximum_object_size=50000000,
                                        union_by_name=true,
                                        ignore_errors=true)
                    WHERE parentID IS NOT NULL OR version IS NOT NULL OR summary IS NOT NULL
                ) src
                WHERE sessions.id = src.id
            """)
        except Exception:
            pass  # Enriched columns not available in this data

        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        info(f"Loaded {count} sessions")
        return count
    except Exception as e:  # Intentional catch-all: DuckDB can raise various errors
        error(f"Session load failed: {e}")
        return 0


def load_messages_fast(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load message data using DuckDB's JSON reader."""
    conn = db.connect()
    message_dir = storage_path / "message"

    if not message_dir.exists():
        return 0

    json_pattern = str(message_dir) + "/**/*.json"
    cutoff_ts = int((datetime.now() - timedelta(days=max_days)).timestamp() * 1000)

    try:
        # Load base columns (always present in all JSON files)
        conn.execute(f"""
            INSERT OR REPLACE INTO messages (id, session_id, parent_id, role, agent, model_id, provider_id,
                                             tokens_input, tokens_output, tokens_reasoning,
                                             tokens_cache_read, tokens_cache_write, created_at, completed_at)
            SELECT
                id,
                sessionID as session_id,
                parentID as parent_id,
                role,
                agent,
                modelID as model_id,
                providerID as provider_id,
                COALESCE(tokens.input, 0) as tokens_input,
                COALESCE(tokens.output, 0) as tokens_output,
                COALESCE(tokens.reasoning, 0) as tokens_reasoning,
                COALESCE(tokens.cache.read, 0) as tokens_cache_read,
                COALESCE(tokens.cache.write, 0) as tokens_cache_write,
                epoch_ms(time.created) as created_at,
                epoch_ms(time.completed) as completed_at
            FROM read_json_auto('{json_pattern}', 
                                maximum_object_size=50000000,
                                ignore_errors=true)
            WHERE id IS NOT NULL
              AND time.created >= {cutoff_ts}
        """)

        # Update enriched columns if available (newer OpenCode versions)
        try:
            conn.execute(f"""
                UPDATE messages SET
                    mode = src.mode,
                    cost = COALESCE(src.cost, 0),
                    finish_reason = src.finish,
                    working_dir = src.path.cwd
                FROM (
                    SELECT id, mode, cost, finish, path
                    FROM read_json_auto('{json_pattern}',
                                        maximum_object_size=50000000,
                                        union_by_name=true,
                                        ignore_errors=true)
                    WHERE mode IS NOT NULL OR cost IS NOT NULL OR finish IS NOT NULL OR path IS NOT NULL
                ) src
                WHERE messages.id = src.id
            """)
        except Exception:
            pass  # Enriched columns not available in this data

        count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        info(f"Loaded {count} messages")
        return count
    except Exception as e:  # Intentional catch-all: DuckDB can raise various errors
        error(f"Message load failed: {e}")
        return 0


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
    batch = []
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
                                    None,
                                    None,
                                    created_at,
                                    None,  # arguments (only for tools)
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

                        if tool_name:
                            batch.append(
                                (
                                    part_id,
                                    session_id,
                                    message_id,
                                    part_type,
                                    None,
                                    tool_name,
                                    tool_status,
                                    created_at,
                                    arguments,
                                )
                            )
                            tool_count += 1

                    # Batch insert
                    if len(batch) >= batch_size:
                        conn.executemany(
                            """INSERT OR REPLACE INTO parts 
                               (id, session_id, message_id, part_type, content, tool_name, tool_status, created_at, arguments)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                   (id, session_id, message_id, part_type, content, tool_name, tool_status, created_at, arguments)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                batch,
            )

        total = text_count + tool_count
        info(f"Loaded {total} parts ({text_count} text, {tool_count} tools)")
        return total

    except Exception as e:  # Intentional catch-all: various errors possible
        error(f"Parts load failed: {e}")
        return 0


def load_skills(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load skill usage from skill tool invocations."""
    conn = db.connect()
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=max_days)
    skill_id = 0
    skills = []

    for msg_dir in part_dir.iterdir():
        if not msg_dir.is_dir():
            continue

        for part_file in msg_dir.glob("*.json"):
            try:
                with open(part_file) as f:
                    data = json.load(f)

                if data.get("tool") != "skill":
                    continue

                state = data.get("state", {})
                skill_name = state.get("input", {}).get("name")
                if not skill_name:
                    continue

                time_data = data.get("time", {})
                start_ts = time_data.get("start")
                loaded_at = ms_to_datetime(start_ts)
                if loaded_at and loaded_at < cutoff:
                    continue

                skill_id += 1
                skills.append(
                    {
                        "id": skill_id,
                        "message_id": data.get("messageID"),
                        "session_id": data.get("sessionID"),
                        "skill_name": skill_name,
                        "loaded_at": loaded_at,
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue

    if not skills:
        info("No skills found")
        return 0

    for s in skills:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO skills
                (id, message_id, session_id, skill_name, loaded_at)
                VALUES (?, ?, ?, ?, ?)""",
                [
                    s["id"],
                    s["message_id"],
                    s["session_id"],
                    s["skill_name"],
                    s["loaded_at"],
                ],
            )
        except Exception as e:  # Intentional catch-all: skip individual insert failures
            debug(f"Skill insert failed for {s.get('skill_name', 'unknown')}: {e}")
            continue

    count = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
    info(f"Loaded {count} skills")
    return count


def load_delegations(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load agent delegations from task tool invocations."""
    conn = db.connect()
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=max_days)
    delegations = []

    for msg_dir in part_dir.iterdir():
        if not msg_dir.is_dir():
            continue

        for part_file in msg_dir.glob("*.json"):
            try:
                with open(part_file) as f:
                    data = json.load(f)

                if data.get("tool") != "task":
                    continue

                state = data.get("state", {})
                input_data = state.get("input", {})
                subagent_type = input_data.get("subagent_type")
                if not subagent_type:
                    continue

                time_data = state.get("time", {})
                created_ts = time_data.get("start")
                created_at = ms_to_datetime(created_ts)
                if created_at and created_at < cutoff:
                    continue

                delegations.append(
                    {
                        "id": data.get("id"),
                        "message_id": data.get("messageID"),
                        "session_id": data.get("sessionID"),
                        "child_agent": subagent_type,
                        "child_session_id": state.get("metadata", {}).get("sessionId"),
                        "created_at": created_at,
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue

    if not delegations:
        info("No delegations found")
        return 0

    for d in delegations:
        try:
            parent_agent = conn.execute(
                "SELECT agent FROM messages WHERE id = ?", [d["message_id"]]
            ).fetchone()
            conn.execute(
                """INSERT OR REPLACE INTO delegations
                (id, message_id, session_id, parent_agent, child_agent, child_session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    d["id"],
                    d["message_id"],
                    d["session_id"],
                    parent_agent[0] if parent_agent else None,
                    d["child_agent"],
                    d["child_session_id"],
                    d["created_at"],
                ],
            )
        except Exception as e:  # Intentional catch-all: skip individual insert failures
            debug(f"Delegation insert failed for {d.get('id', 'unknown')}: {e}")
            continue

    count = conn.execute("SELECT COUNT(*) FROM delegations").fetchone()[0]
    info(f"Loaded {count} delegations")
    return count


def get_first_user_message(message_dir: Path, session_id: str) -> Optional[str]:
    """Get the first user message content for a session.

    Args:
        message_dir: Path to OpenCode message storage
        session_id: The session ID to find messages for

    Returns:
        The first user message content, or None if not found
    """
    session_msg_dir = message_dir / session_id
    if not session_msg_dir.exists():
        return None

    # Find all message files and sort by timestamp
    messages = []
    for msg_file in session_msg_dir.glob("*.json"):
        try:
            with open(msg_file) as f:
                data = json.load(f)
            if data.get("role") == "user":
                time_data = data.get("time", {})
                created = time_data.get("created", 0)
                messages.append((created, data))
        except (json.JSONDecodeError, OSError):
            continue

    if not messages:
        return None

    # Sort by creation time and get the first
    messages.sort(key=lambda x: x[0])
    first_msg = messages[0][1]

    # Extract content from summary (title + body if available)
    summary = first_msg.get("summary", {})
    title = summary.get("title", "")
    body = summary.get("body", "")

    if title and body:
        return f"{title}\n\n{body}"
    elif title:
        return title
    elif body:
        return body

    return "(No message content)"


def extract_root_sessions(storage_path: Path, max_days: int = 30) -> list[AgentTrace]:
    """Extract root sessions (direct conversations, not delegations).

    Root sessions are sessions where parentID is null, meaning they were
    started directly by the user rather than created via task delegation.

    Args:
        storage_path: Path to OpenCode storage
        max_days: Only extract sessions from the last N days

    Returns:
        List of AgentTrace objects representing root sessions
    """
    session_dir = storage_path / "session"
    message_dir = storage_path / "message"

    if not session_dir.exists():
        return []

    cutoff = datetime.now() - timedelta(days=max_days)
    traces: list[AgentTrace] = []

    # Sessions are organized in subdirectories by project
    for project_dir in session_dir.iterdir():
        if not project_dir.is_dir():
            continue

        for session_file in project_dir.glob("*.json"):
            try:
                with open(session_file) as f:
                    data = json.load(f)

                # Only process root sessions (no parent)
                if data.get("parentID") is not None:
                    continue

                session_id = data.get("id")
                if not session_id:
                    continue

                # Check time filter
                time_data = data.get("time", {})
                created_ts = time_data.get("created")
                created_at = ms_to_datetime(created_ts)

                if created_at and created_at < cutoff:
                    continue

                updated_ts = time_data.get("updated")
                updated_at = ms_to_datetime(updated_ts)

                # Calculate duration if we have both timestamps
                duration_ms = None
                if created_ts and updated_ts:
                    duration_ms = updated_ts - created_ts

                # Get the first user message as prompt
                first_message = get_first_user_message(message_dir, session_id)

                # Create trace for root session
                trace = AgentTrace(
                    trace_id=f"{ROOT_TRACE_PREFIX}{session_id}",
                    session_id=session_id,
                    parent_trace_id=None,  # ROOT - no parent
                    parent_agent=None,
                    subagent_type=ROOT_AGENT_TYPE,
                    prompt_input=first_message or data.get("title", "(No prompt)"),
                    prompt_output=None,  # Conversation ongoing
                    started_at=created_at,
                    ended_at=updated_at,
                    duration_ms=duration_ms,
                    tokens_in=None,  # Will be resolved from messages
                    tokens_out=None,
                    status="completed" if updated_at else "running",
                    tools_used=[],
                    child_session_id=session_id,  # Self-reference for hierarchy
                )
                traces.append(trace)

            except (json.JSONDecodeError, OSError):
                continue

    info(f"Extracted {len(traces)} root sessions")
    return traces


def extract_traces(storage_path: Path, max_days: int = 30) -> list[AgentTrace]:
    """Extract agent traces from task tool invocations.

    Parses the part files to find tool calls with name="task",
    extracts full prompt input/output, timing, and nested tool usage.

    Args:
        storage_path: Path to OpenCode storage
        max_days: Only extract traces from the last N days

    Returns:
        List of AgentTrace objects with full execution context
    """
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return []

    cutoff = datetime.now() - timedelta(days=max_days)
    traces: list[AgentTrace] = []

    for msg_dir in part_dir.iterdir():
        if not msg_dir.is_dir():
            continue

        for part_file in msg_dir.glob("*.json"):
            try:
                with open(part_file) as f:
                    data = json.load(f)

                if data.get("tool") != "task":
                    continue

                state = data.get("state", {})
                input_data = state.get("input", {})
                subagent_type = input_data.get("subagent_type")
                if not subagent_type:
                    continue

                # Extract timing
                time_data = state.get("time", {})
                start_ts = time_data.get("start")
                end_ts = time_data.get("end")
                started_at = ms_to_datetime(start_ts)
                ended_at = ms_to_datetime(end_ts)

                if started_at and started_at < cutoff:
                    continue

                # Calculate duration
                duration_ms = None
                if start_ts and end_ts:
                    duration_ms = end_ts - start_ts

                # Determine status
                status = state.get("status", "running")
                if status == "completed":
                    status = "completed"
                elif status == "error" or status == "failed":
                    status = "error"
                else:
                    status = "running"

                # Extract tools used from metadata.summary
                tools_used = []
                metadata = state.get("metadata", {})
                summary = metadata.get("summary", [])
                for item in summary:
                    tool_name = item.get("tool")
                    if tool_name:
                        tools_used.append(tool_name)

                # Create trace
                trace = AgentTrace(
                    trace_id=data.get("id", str(uuid.uuid4())),
                    session_id=data.get("sessionID", ""),
                    parent_trace_id=None,  # Will be resolved later
                    parent_agent=None,  # Will be resolved from message
                    subagent_type=subagent_type,
                    prompt_input=input_data.get("prompt", ""),
                    prompt_output=state.get("output"),
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_ms=duration_ms,
                    tokens_in=None,  # Would need message lookup
                    tokens_out=None,
                    status=status,
                    tools_used=tools_used,
                    child_session_id=metadata.get("sessionId"),
                )
                traces.append(trace)

            except (json.JSONDecodeError, OSError):
                continue

    info(f"Extracted {len(traces)} agent traces")
    return traces


def load_traces(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load agent traces into the database.

    Extracts traces from both:
    1. Task tool invocations (delegation traces)
    2. Root sessions (direct user conversations)

    This creates a unified hierarchy where root sessions are at the top
    and delegation traces are nested under them.

    Args:
        db: Analytics database instance
        storage_path: Path to OpenCode storage
        max_days: Only load traces from the last N days

    Returns:
        Number of traces loaded
    """
    conn = db.connect()

    # Ensure table exists (for legacy databases)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_traces (
                trace_id VARCHAR PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                parent_trace_id VARCHAR,
                parent_agent VARCHAR,
                subagent_type VARCHAR NOT NULL,
                prompt_input TEXT NOT NULL,
                prompt_output TEXT,
                started_at TIMESTAMP NOT NULL,
                ended_at TIMESTAMP,
                duration_ms INTEGER,
                tokens_in INTEGER,
                tokens_out INTEGER,
                status VARCHAR DEFAULT 'running',
                tools_used TEXT[],
                child_session_id VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    except Exception:  # Intentional catch-all: table may already exist
        pass

    # Extract delegation traces from task tool invocations
    delegation_traces = extract_traces(storage_path, max_days)

    # Extract root sessions (direct conversations)
    root_traces = extract_root_sessions(storage_path, max_days)

    # Merge both types of traces
    traces = root_traces + delegation_traces

    if not traces:
        info("No traces found")
        return 0

    # Build child_session_id -> parent_trace mapping
    # A trace with child_session_id = "ses_xyz" is the parent of traces in session "ses_xyz"
    parent_trace_by_child_session: dict[str, AgentTrace] = {}
    for trace in traces:
        if trace.child_session_id:
            parent_trace_by_child_session[trace.child_session_id] = trace

    # Resolve parent_trace_id based on session membership
    for trace in traces:
        if trace.session_id in parent_trace_by_child_session:
            parent = parent_trace_by_child_session[trace.session_id]
            trace.parent_trace_id = parent.trace_id
            trace.parent_agent = parent.subagent_type

    # Also try to resolve parent_agent from messages table for root traces
    for trace in traces:
        if trace.parent_agent:
            continue  # Already resolved
        try:
            # Get the message that made this task call
            result = conn.execute(
                "SELECT agent FROM messages WHERE id = ?",
                [trace.session_id.replace("ses_", "msg_")],  # Approximate lookup
            ).fetchone()
            if result:
                trace.parent_agent = result[0]
        except Exception:  # Intentional catch-all: skip lookup failures
            pass

    # Resolve tokens from child session messages
    for trace in traces:
        if not trace.child_session_id:
            continue
        try:
            # Sum tokens from all messages in the child session
            result = conn.execute(
                """SELECT 
                    COALESCE(SUM(tokens_input), 0) as total_in,
                    COALESCE(SUM(tokens_output), 0) as total_out
                FROM messages 
                WHERE session_id = ?""",
                [trace.child_session_id],
            ).fetchone()
            if result and (result[0] > 0 or result[1] > 0):
                trace.tokens_in = result[0]
                trace.tokens_out = result[1]
        except Exception:  # Intentional catch-all: skip token lookup failures
            pass

    # Insert traces
    for trace in traces:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO agent_traces
                (trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
                 prompt_input, prompt_output, started_at, ended_at, duration_ms,
                 tokens_in, tokens_out, status, tools_used, child_session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    trace.trace_id,
                    trace.session_id,
                    trace.parent_trace_id,
                    trace.parent_agent,
                    trace.subagent_type,
                    trace.prompt_input,
                    trace.prompt_output,
                    trace.started_at,
                    trace.ended_at,
                    trace.duration_ms,
                    trace.tokens_in,
                    trace.tokens_out,
                    trace.status,
                    trace.tools_used,
                    trace.child_session_id,
                ],
            )
        except Exception as e:  # Intentional catch-all: skip individual insert failures
            debug(f"Trace insert failed for {trace.trace_id}: {e}")
            continue

    count = conn.execute("SELECT COUNT(*) FROM agent_traces").fetchone()[0]
    info(f"Loaded {count} traces")
    return count


def load_file_operations(
    db: AnalyticsDB, storage_path: Path, max_days: int = 30
) -> int:
    """Load file operations from tool invocations.

    Extracts read, write, and edit operations from parts data.

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

    cutoff = datetime.now() - timedelta(days=max_days)
    operations: list[dict] = []
    file_tools = {"read", "write", "edit"}

    for msg_dir in part_dir.iterdir():
        if not msg_dir.is_dir():
            continue

        for part_file in msg_dir.glob("*.json"):
            try:
                with open(part_file) as f:
                    data = json.load(f)

                tool_name = data.get("tool")
                if tool_name not in file_tools:
                    continue

                state = data.get("state", {})
                input_data = state.get("input", {})

                # Extract file path from tool input
                file_path = input_data.get("filePath") or input_data.get("path")
                if not file_path:
                    continue

                time_data = state.get("time", {})
                start_ts = time_data.get("start")
                timestamp = ms_to_datetime(start_ts)
                if timestamp and timestamp < cutoff:
                    continue

                # Determine operation type
                operation = tool_name  # read, write, or edit

                operations.append(
                    {
                        "id": data.get("id"),
                        "session_id": data.get("sessionID"),
                        "trace_id": None,  # Will be resolved later if needed
                        "operation": operation,
                        "file_path": file_path,
                        "timestamp": timestamp,
                        "risk_level": "normal",  # Can be enriched by security module
                        "risk_reason": None,
                    }
                )

            except (json.JSONDecodeError, OSError):
                continue

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


def load_opencode_data(
    db: Optional[AnalyticsDB] = None,
    storage_path: Optional[Path] = None,
    clear_first: bool = True,
    max_days: int = 30,
    skip_parts: bool = True,
) -> dict:
    """Load OpenCode data into the analytics database.

    Uses DuckDB's native JSON reading for fast bulk loading.

    Args:
        db: Analytics database instance (creates new if not provided)
        storage_path: Path to OpenCode storage (uses default if not provided)
        clear_first: Whether to clear existing data before loading
        max_days: Only load data from the last N days (default 30)
        skip_parts: Skip loading parts (slow with many files), default True

    Returns:
        Dict with counts of loaded items
    """
    if db is None:
        db = AnalyticsDB()

    if storage_path is None:
        storage_path = get_opencode_storage_path()

    if not storage_path.exists():
        error(f"OpenCode storage not found: {storage_path}")
        return {"sessions": 0, "messages": 0, "parts": 0, "error": "Storage not found"}

    info(f"Loading OpenCode data (last {max_days} days)...")

    if clear_first:
        db.clear_data()

    sessions = load_sessions_fast(db, storage_path, max_days)
    messages = load_messages_fast(db, storage_path, max_days)

    # Parts loading is slow (can be 70k+ files) - skip by default
    if skip_parts:
        parts = 0
        info("Skipping parts (use skip_parts=False to load)")
    else:
        parts = load_parts_fast(db, storage_path, max_days)

    delegations = load_delegations(db, storage_path, max_days)
    skills = load_skills(db, storage_path, max_days)
    traces = load_traces(db, storage_path, max_days)

    # Load file operations (from parts, relatively fast)
    file_operations = load_file_operations(db, storage_path, max_days)

    result = {
        "sessions": sessions,
        "messages": messages,
        "parts": parts,
        "delegations": delegations,
        "skills": skills,
        "traces": traces,
        "file_operations": file_operations,
    }

    info(
        f"Total: {sessions} sessions, {messages} messages, {parts} parts, "
        f"{delegations} delegations, {skills} skills, {traces} traces, "
        f"{file_operations} file_operations"
    )
    return result
