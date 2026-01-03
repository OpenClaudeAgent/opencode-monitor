"""
JSON data loader for OpenCode storage.

Uses DuckDB's native JSON reading for maximum performance.
Supports both delegation traces (task tool) and root sessions (direct conversations).
"""

import json
import uuid
from dataclasses import dataclass
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
        # Use temp table for deduplication, then insert only new records
        conn.execute("DROP TABLE IF EXISTS _tmp_sessions")
        conn.execute(f"""
            CREATE TEMP TABLE _tmp_sessions AS
            SELECT id, project_id, directory, title, created_at, updated_at
            FROM (
                SELECT
                    id,
                    projectID as project_id,
                    directory,
                    title,
                    epoch_ms(time.created) as created_at,
                    epoch_ms(time.updated) as updated_at,
                    ROW_NUMBER() OVER (PARTITION BY id ORDER BY time.updated DESC) as rn
                FROM read_json_auto('{json_pattern}', 
                                    maximum_object_size=50000000,
                                    ignore_errors=true)
                WHERE id IS NOT NULL
                  AND time.created >= {cutoff_ts}
            ) deduped
            WHERE rn = 1
        """)

        # Insert only new records, skip existing (incremental load)
        conn.execute("""
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            SELECT id, project_id, directory, title, created_at, updated_at FROM _tmp_sessions
            ON CONFLICT (id) DO NOTHING
        """)
        conn.execute("DROP TABLE IF EXISTS _tmp_sessions")

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
        # Use temp table for deduplication, then insert only new records
        conn.execute("DROP TABLE IF EXISTS _tmp_messages")
        conn.execute(f"""
            CREATE TEMP TABLE _tmp_messages AS
            SELECT id, session_id, parent_id, role, agent, model_id, provider_id,
                   tokens_input, tokens_output, tokens_reasoning,
                   tokens_cache_read, tokens_cache_write, created_at, completed_at
            FROM (
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
                    epoch_ms(time.completed) as completed_at,
                    ROW_NUMBER() OVER (PARTITION BY id ORDER BY time.created DESC) as rn
                FROM read_json_auto('{json_pattern}', 
                                    maximum_object_size=50000000,
                                    ignore_errors=true)
                WHERE id IS NOT NULL
                  AND time.created >= {cutoff_ts}
            ) deduped
            WHERE rn = 1
        """)

        # Insert only new records, skip existing (incremental load)
        conn.execute("""
            INSERT INTO messages (id, session_id, parent_id, role, agent, model_id, provider_id,
                                  tokens_input, tokens_output, tokens_reasoning,
                                  tokens_cache_read, tokens_cache_write, created_at, completed_at)
            SELECT id, session_id, parent_id, role, agent, model_id, provider_id,
                   tokens_input, tokens_output, tokens_reasoning,
                   tokens_cache_read, tokens_cache_write, created_at, completed_at
            FROM _tmp_messages
            ON CONFLICT (id) DO NOTHING
        """)
        conn.execute("DROP TABLE IF EXISTS _tmp_messages")

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


def _collect_recent_part_files(part_dir: Path, max_days: int) -> list[str]:
    """Collect part files from recent directories using mtime filter.

    This is much faster than letting DuckDB scan all files with a glob pattern.

    Args:
        part_dir: Path to the part directory
        max_days: Only include files from directories modified in the last N days

    Returns:
        List of file paths as strings
    """
    cutoff_ts = (datetime.now() - timedelta(days=max_days)).timestamp()
    recent_files: list[str] = []

    for msg_dir in part_dir.iterdir():
        if not msg_dir.is_dir():
            continue
        try:
            if msg_dir.stat().st_mtime < cutoff_ts:
                continue
        except OSError:
            continue

        for f in msg_dir.iterdir():
            if f.suffix == ".json":
                recent_files.append(str(f))

    return recent_files


def _chunked(lst: list, chunk_size: int):
    """Yield successive chunks from a list."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i : i + chunk_size]


def load_delegations(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load agent delegations from task tool invocations.

    Uses a chunked approach for performance without freezing:
    1. Python scans directories and filters by mtime (fast)
    2. Process files in chunks to avoid memory/CPU spikes
    """
    import time as time_module

    conn = db.connect()
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return 0

    # Phase 1: Collect recent files (mtime filter)
    recent_files = _collect_recent_part_files(part_dir, max_days)
    if not recent_files:
        info("No recent part files found")
        return 0

    debug(f"Scanning {len(recent_files)} recent part files for delegations")

    cutoff = datetime.now() - timedelta(days=max_days)
    delegations: list[dict] = []

    # Phase 2: Process files in chunks (avoid CPU spikes)
    chunk_size = 500
    for chunk in _chunked(recent_files, chunk_size):
        for file_path in chunk:
            try:
                with open(file_path, "r") as f:
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
                started_at = ms_to_datetime(start_ts)

                # Skip old entries
                if started_at and started_at < cutoff:
                    continue

                metadata = state.get("metadata", {})
                delegations.append(
                    {
                        "id": data.get("id"),
                        "message_id": data.get("messageID"),
                        "session_id": data.get("sessionID"),
                        "child_agent": subagent_type,
                        "child_session_id": metadata.get("sessionId"),
                        "created_at": started_at,
                    }
                )

            except (json.JSONDecodeError, OSError):
                continue

        # Small sleep between chunks to let UI breathe
        time_module.sleep(0.01)

    if not delegations:
        info("No delegations found")
        return 0

    # Batch lookup: get all parent agents in one query
    message_ids = [d["message_id"] for d in delegations if d.get("message_id")]
    parent_agents: dict[str, str] = {}
    if message_ids:
        try:
            # Use a single query to get all agents
            placeholders = ",".join(["?" for _ in message_ids])
            results = conn.execute(
                f"SELECT id, agent FROM messages WHERE id IN ({placeholders})",
                message_ids,
            ).fetchall()
            parent_agents = {r[0]: r[1] for r in results if r[1]}
        except Exception:
            pass  # Fall back to no parent agents

    # Batch insert delegations
    for d in delegations:
        try:
            parent_agent = parent_agents.get(d.get("message_id"))
            conn.execute(
                """INSERT OR REPLACE INTO delegations
                (id, message_id, session_id, parent_agent, child_agent, child_session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    d["id"],
                    d["message_id"],
                    d["session_id"],
                    parent_agent,
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


def get_session_agent(message_dir: Path, session_id: str) -> Optional[str]:
    """Get the agent type for a session from its messages.

    OpenCode stores the agent type in the 'agent' field of message JSON files.
    This is the responding agent (e.g., 'roadmap', 'coordinateur', 'executeur').

    Args:
        message_dir: Path to OpenCode message storage
        session_id: The session ID to find messages for

    Returns:
        The agent name (e.g., 'roadmap', 'coordinateur'), or None if not found
    """
    session_msg_dir = message_dir / session_id
    if not session_msg_dir.exists():
        return None

    # Find the first message with an 'agent' field
    for msg_file in session_msg_dir.glob("*.json"):
        try:
            with open(msg_file) as f:
                data = json.load(f)
            agent = data.get("agent")
            if agent:
                return agent
        except (json.JSONDecodeError, OSError):
            continue

    return None


@dataclass
class AgentSegment:
    """A segment of messages from a single agent within a session."""

    agent: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    message_count: int
    tokens_in: int
    tokens_out: int


def get_agent_segments(message_dir: Path, session_id: str) -> list[AgentSegment]:
    """Get agent segments for a session (detect agent changes mid-conversation).

    When a user switches agents mid-session (e.g., from @roadmap to @coordinateur),
    this function identifies each contiguous segment of messages from the same agent.

    Args:
        message_dir: Path to OpenCode message storage
        session_id: The session ID to analyze

    Returns:
        List of AgentSegment objects, one per contiguous agent block.
        Excludes internal agents like 'compaction', 'summarizer', 'title'.
    """
    session_msg_dir = message_dir / session_id
    if not session_msg_dir.exists():
        return []

    # Internal agents to skip (not user-visible)
    INTERNAL_AGENTS = {"compaction", "summarizer", "title"}

    # Load all messages with timing
    messages: list[tuple[int, dict]] = []
    for msg_file in session_msg_dir.glob("*.json"):
        try:
            with open(msg_file) as f:
                data = json.load(f)
            created = data.get("time", {}).get("created", 0)
            messages.append((created, data))
        except (json.JSONDecodeError, OSError):
            continue

    if not messages:
        return []

    # Sort by creation time
    messages.sort(key=lambda x: x[0])

    # Detect agent segments
    segments: list[AgentSegment] = []
    current_agent: Optional[str] = None
    segment_start: Optional[int] = None
    segment_end: Optional[int] = None
    segment_count = 0
    segment_tokens_in = 0
    segment_tokens_out = 0

    for created_ts, msg in messages:
        agent = msg.get("agent")
        if not agent or agent in INTERNAL_AGENTS:
            continue

        if agent != current_agent:
            # Save previous segment
            if current_agent and segment_count > 0:
                segments.append(
                    AgentSegment(
                        agent=current_agent,
                        start_time=ms_to_datetime(segment_start),
                        end_time=ms_to_datetime(segment_end),
                        message_count=segment_count,
                        tokens_in=segment_tokens_in,
                        tokens_out=segment_tokens_out,
                    )
                )

            # Start new segment
            current_agent = agent
            segment_start = created_ts
            segment_count = 0
            segment_tokens_in = 0
            segment_tokens_out = 0

        # Update segment stats
        segment_end = msg.get("time", {}).get("completed") or created_ts
        segment_count += 1
        tokens = msg.get("tokens", {})
        segment_tokens_in += tokens.get("input", 0)
        segment_tokens_out += tokens.get("output", 0)

    # Save last segment
    if current_agent and segment_count > 0:
        segments.append(
            AgentSegment(
                agent=current_agent,
                start_time=ms_to_datetime(segment_start),
                end_time=ms_to_datetime(segment_end),
                message_count=segment_count,
                tokens_in=segment_tokens_in,
                tokens_out=segment_tokens_out,
            )
        )

    return segments


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


def extract_root_sessions(
    storage_path: Path,
    max_days: int = 30,
    throttle_ms: int = 10,
    segment_analysis_days: int = 1,
) -> list[AgentTrace]:
    """Extract root sessions (direct conversations, not delegations).

    Root sessions are sessions where parentID is null, meaning they were
    started directly by the user rather than created via task delegation.

    Sessions are processed from most recent to oldest with throttling to
    avoid CPU spikes. Full segment analysis (detecting mid-session agent
    switches) is only done for recent sessions.

    Args:
        storage_path: Path to OpenCode storage
        max_days: Only extract sessions from the last N days
        throttle_ms: Milliseconds to sleep between processing sessions
        segment_analysis_days: Only do full segment analysis for sessions
            within this many days (older sessions just get first agent)

    Returns:
        List of AgentTrace objects representing root sessions
    """
    import time

    session_dir = storage_path / "session"
    message_dir = storage_path / "message"

    if not session_dir.exists():
        return []

    cutoff = datetime.now() - timedelta(days=max_days)
    segment_cutoff = datetime.now() - timedelta(days=segment_analysis_days)
    traces: list[AgentTrace] = []

    # Phase 1: Collect all root sessions with metadata (fast - no message reading)
    sessions_to_process: list[tuple[datetime, Path, dict]] = []

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

                # Store for processing (will sort by date)
                sessions_to_process.append(
                    (created_at or datetime.min, session_file, data)
                )

            except (json.JSONDecodeError, OSError):
                continue

    # Phase 2: Sort by date descending (most recent first)
    sessions_to_process.sort(key=lambda x: x[0], reverse=True)
    debug(f"Processing {len(sessions_to_process)} root sessions (newest first)")

    # Phase 3: Process sessions with throttling
    for created_at, session_file, data in sessions_to_process:
        try:
            session_id = data.get("id")
            time_data = data.get("time", {})
            created_ts = time_data.get("created")
            updated_ts = time_data.get("updated")
            updated_at = ms_to_datetime(updated_ts)

            # Calculate duration if we have both timestamps
            duration_ms = None
            if created_ts and updated_ts:
                duration_ms = updated_ts - created_ts

            # Get the first user message as prompt
            first_message = get_first_user_message(message_dir, session_id)

            # Only do full segment analysis for recent sessions
            # Older sessions just get the first agent (much faster)
            if created_at and created_at >= segment_cutoff:
                segments = get_agent_segments(message_dir, session_id)
            else:
                # Fast path: just get first agent
                agent = get_session_agent(message_dir, session_id)
                segments = (
                    [
                        AgentSegment(
                            agent=agent or ROOT_AGENT_TYPE,
                            start_time=created_at,
                            end_time=updated_at,
                            message_count=0,
                            tokens_in=0,
                            tokens_out=0,
                        )
                    ]
                    if agent
                    else []
                )

            if len(segments) <= 1:
                # Single agent session - create one trace
                session_agent = segments[0].agent if segments else None
                trace = AgentTrace(
                    trace_id=f"{ROOT_TRACE_PREFIX}{session_id}",
                    session_id=session_id,
                    parent_trace_id=None,  # ROOT - no parent
                    parent_agent=ROOT_AGENT_TYPE,  # "user" - human initiated
                    subagent_type=session_agent or ROOT_AGENT_TYPE,
                    prompt_input=first_message or data.get("title", "(No prompt)"),
                    prompt_output=None,
                    started_at=created_at,
                    ended_at=updated_at,
                    duration_ms=duration_ms,
                    tokens_in=segments[0].tokens_in if segments else None,
                    tokens_out=segments[0].tokens_out if segments else None,
                    status="completed" if updated_at else "running",
                    tools_used=[],
                    child_session_id=session_id,
                )
                traces.append(trace)
            else:
                # Multi-agent session - create a trace for each segment
                # First segment: user → first_agent
                # Subsequent: previous_agent → current_agent
                parent_trace_id = None
                previous_agent = ROOT_AGENT_TYPE

                for i, segment in enumerate(segments):
                    segment_trace_id = f"{ROOT_TRACE_PREFIX}{session_id}_seg{i}"

                    # Calculate segment duration
                    segment_duration = None
                    if segment.start_time and segment.end_time:
                        delta = segment.end_time - segment.start_time
                        segment_duration = int(delta.total_seconds() * 1000)

                        trace = AgentTrace(
                            trace_id=segment_trace_id,
                            session_id=session_id,
                            parent_trace_id=parent_trace_id,
                            parent_agent=previous_agent,
                            subagent_type=segment.agent,
                            prompt_input=(first_message or "(No prompt)")
                            if i == 0
                            else f"(switched to @{segment.agent})",
                            prompt_output=None,
                            started_at=segment.start_time,
                            ended_at=segment.end_time,
                            duration_ms=segment_duration,
                            tokens_in=segment.tokens_in,
                            tokens_out=segment.tokens_out,
                            status="completed",
                            tools_used=[],
                            child_session_id=session_id,
                        )
                        traces.append(trace)

                        # Chain for next segment
                        parent_trace_id = segment_trace_id
                        previous_agent = segment.agent

            # Throttle to avoid CPU spikes
            if throttle_ms > 0:
                time.sleep(throttle_ms / 1000.0)

        except (json.JSONDecodeError, OSError):
            continue

    info(f"Extracted {len(traces)} root sessions")
    return traces


def extract_traces(storage_path: Path, max_days: int = 30) -> list[AgentTrace]:
    """Extract agent traces from task tool invocations.

    Parses the part files to find tool calls with name="task",
    extracts full prompt input/output, timing, and nested tool usage.

    Uses mtime-based directory filtering for performance.

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
    cutoff_ts = cutoff.timestamp()
    traces: list[AgentTrace] = []

    # Phase 1: Filter directories by mtime (fast)
    for msg_dir in part_dir.iterdir():
        if not msg_dir.is_dir():
            continue

        try:
            if msg_dir.stat().st_mtime < cutoff_ts:
                continue
        except OSError:
            continue

        # Phase 2: Read only task tool files from recent directories
        for part_file in msg_dir.iterdir():
            if not part_file.suffix == ".json":
                continue

            try:
                with open(part_file, "r") as f:
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
        # Skip segment traces - they already have correct parent_trace_id from extraction
        if "_seg" in trace.trace_id:
            continue

        if trace.session_id in parent_trace_by_child_session:
            parent = parent_trace_by_child_session[trace.session_id]
            # Skip self-references (root traces have child_session_id = session_id)
            if parent.trace_id == trace.trace_id:
                continue
            trace.parent_trace_id = parent.trace_id
            trace.parent_agent = parent.subagent_type

    # Batch resolve parent_agent from messages table for root traces
    traces_needing_parent = [t for t in traces if not t.parent_agent]
    if traces_needing_parent:
        msg_ids = [t.session_id.replace("ses_", "msg_") for t in traces_needing_parent]
        try:
            placeholders = ",".join(["?" for _ in msg_ids])
            results = conn.execute(
                f"SELECT id, agent FROM messages WHERE id IN ({placeholders})",
                msg_ids,
            ).fetchall()
            agent_by_msg = {r[0]: r[1] for r in results if r[1]}
            for trace in traces_needing_parent:
                msg_id = trace.session_id.replace("ses_", "msg_")
                if msg_id in agent_by_msg:
                    trace.parent_agent = agent_by_msg[msg_id]
        except Exception:
            pass  # Batch lookup failed, continue without

    # Batch resolve tokens from child session messages
    child_sessions = list({t.child_session_id for t in traces if t.child_session_id})
    if child_sessions:
        try:
            placeholders = ",".join(["?" for _ in child_sessions])
            results = conn.execute(
                f"""SELECT session_id,
                    COALESCE(SUM(tokens_input), 0) as total_in,
                    COALESCE(SUM(tokens_output), 0) as total_out
                FROM messages 
                WHERE session_id IN ({placeholders})
                GROUP BY session_id""",
                child_sessions,
            ).fetchall()
            tokens_by_session = {r[0]: (r[1], r[2]) for r in results}
            for trace in traces:
                if trace.child_session_id in tokens_by_session:
                    tokens = tokens_by_session[trace.child_session_id]
                    if tokens[0] > 0 or tokens[1] > 0:
                        trace.tokens_in = tokens[0]
                        trace.tokens_out = tokens[1]
        except Exception:
            pass  # Batch lookup failed, continue without

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
    Uses chunked Python processing to avoid CPU spikes.

    Args:
        db: Analytics database instance
        storage_path: Path to OpenCode storage
        max_days: Only load operations from the last N days

    Returns:
        Number of file operations loaded
    """
    import time as time_module

    conn = db.connect()
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return 0

    # Phase 1: Collect recent files (mtime filter)
    recent_files = _collect_recent_part_files(part_dir, max_days)
    if not recent_files:
        info("No recent part files found for file operations")
        return 0

    debug(f"Scanning {len(recent_files)} recent part files for file operations")

    cutoff = datetime.now() - timedelta(days=max_days)
    operations: list[dict] = []
    file_tools = {"read", "write", "edit"}

    # Phase 2: Process files in chunks (avoid CPU spikes)
    chunk_size = 500
    for chunk in _chunked(recent_files, chunk_size):
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
