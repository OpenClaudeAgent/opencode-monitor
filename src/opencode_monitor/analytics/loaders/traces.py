"""Agent traces data loader."""

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ..db import AnalyticsDB
from ..models import AgentTrace
from ...utils.logger import info, debug
from ...utils.datetime import ms_to_datetime
from .enrichment import get_session_agent, get_first_user_message


# Constants for root session traces
ROOT_TRACE_PREFIX = "root_"
ROOT_AGENT_TYPE = "user"  # Root sessions are direct user conversations


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
