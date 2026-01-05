"""
Real-time agent trace builder.

Creates agent_traces immediately when task tool parts are completed,
instead of waiting for batch processing.

Features:
- Immediate trace creation on task completion
- Parent trace resolution
- Token aggregation from child session
- Status tracking (running/completed/error)
"""

from datetime import datetime
from typing import Optional
import uuid

from ...db import AnalyticsDB
from ..parsers import ParsedDelegation, ParsedPart
from ....utils.logger import debug
from .helpers import determine_status, extract_prompt


# Constants for root session traces
ROOT_TRACE_PREFIX = "root_"
ROOT_AGENT_TYPE = "user"


class TraceBuilder:
    """Builds agent traces in real-time from delegation events.

    Creates and updates agent_traces table when task tool parts
    are processed, enabling real-time trace visibility.
    """

    def __init__(self, db: AnalyticsDB):
        """Initialize the trace builder.

        Args:
            db: Database instance for reading/writing traces
        """
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Ensure agent_traces table exists with all columns."""
        conn = self._db.connect()
        # Table should already exist from db.py schema, but ensure it
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
        except Exception:
            pass  # Table exists

    def create_trace_from_delegation(
        self,
        delegation: ParsedDelegation,
        part: ParsedPart,
    ) -> Optional[str]:
        """Create or update a trace from a delegation.

        Called when a task tool part is processed. Creates the trace
        immediately if completed, or updates an existing trace.

        Args:
            delegation: Parsed delegation data
            part: Parsed part data with timing info

        Returns:
            The trace_id if created/updated, None on error
        """
        if not delegation.child_agent:
            return None

        trace_id = delegation.id or str(uuid.uuid4())
        status = determine_status(part.tool_status)

        # Resolve parent agent from message
        parent_agent = self._resolve_parent_agent(delegation.message_id)

        # Get prompt from delegation
        prompt_input = extract_prompt(part.arguments)

        # Resolve parent trace immediately (don't wait for batch resolution)
        parent_trace_id = None
        if delegation.session_id:
            parent_trace_id = self._resolve_parent_trace_id(
                delegation.session_id, trace_id
            )

        conn = self._db.connect()

        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_traces
                (trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
                 prompt_input, prompt_output, started_at, ended_at, duration_ms,
                 tokens_in, tokens_out, status, tools_used, child_session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    trace_id,
                    delegation.session_id or "",
                    parent_trace_id,  # Resolved immediately
                    parent_agent,
                    delegation.child_agent,
                    prompt_input,
                    None,  # prompt_output
                    part.created_at or datetime.now(),
                    part.ended_at,
                    part.duration_ms,
                    None,  # tokens_in - resolved later
                    None,  # tokens_out - resolved later
                    status,
                    [],  # tools_used
                    delegation.child_session_id,
                ],
            )

            debug(
                f"[TraceBuilder] Created trace {trace_id} for {delegation.child_agent}"
            )

            # Update tokens from child session messages (may already be indexed)
            if delegation.child_session_id:
                self.update_trace_tokens(delegation.child_session_id)

            return trace_id

        except Exception as e:
            debug(f"[TraceBuilder] Failed to create trace: {e}")
            return None

    def update_trace_tokens(self, child_session_id: str) -> None:
        """Update trace tokens from child session messages.

        Called after messages are indexed to aggregate token counts.

        Args:
            child_session_id: The child session ID to aggregate tokens from
        """
        conn = self._db.connect()

        try:
            # Get total tokens from child session
            result = conn.execute(
                """
                SELECT
                    COALESCE(SUM(tokens_input), 0),
                    COALESCE(SUM(tokens_output), 0)
                FROM messages
                WHERE session_id = ?
                """,
                [child_session_id],
            ).fetchone()

            if result and (result[0] > 0 or result[1] > 0):
                conn.execute(
                    """
                    UPDATE agent_traces
                    SET tokens_in = ?, tokens_out = ?
                    WHERE child_session_id = ?
                    """,
                    [result[0], result[1], child_session_id],
                )

        except Exception as e:
            debug(f"[TraceBuilder] Failed to update tokens: {e}")

    def backfill_missing_tokens(self) -> int:
        """Backfill tokens for all traces with child_session_id but no tokens.

        This fixes traces that were created before their child session
        messages were indexed.

        Returns:
            Number of traces updated
        """
        conn = self._db.connect()

        try:
            # Find traces with child_session but no tokens
            traces = conn.execute(
                """
                SELECT child_session_id
                FROM agent_traces
                WHERE child_session_id IS NOT NULL
                  AND (tokens_in IS NULL OR tokens_in = 0)
                  AND (tokens_out IS NULL OR tokens_out = 0)
                """
            ).fetchall()

            updated = 0
            for (child_session_id,) in traces:
                # Get tokens from child session
                result = conn.execute(
                    """
                    SELECT
                        COALESCE(SUM(tokens_input), 0),
                        COALESCE(SUM(tokens_output), 0)
                    FROM messages
                    WHERE session_id = ?
                    """,
                    [child_session_id],
                ).fetchone()

                if result and (result[0] > 0 or result[1] > 0):
                    conn.execute(
                        """
                        UPDATE agent_traces
                        SET tokens_in = ?, tokens_out = ?
                        WHERE child_session_id = ?
                        """,
                        [result[0], result[1], child_session_id],
                    )
                    updated += 1

            if updated > 0:
                debug(f"[TraceBuilder] Backfilled tokens for {updated} traces")

            return updated

        except Exception as e:
            debug(f"[TraceBuilder] Failed to backfill tokens: {e}")
            return 0

    def resolve_parent_traces(self) -> int:
        """Resolve parent_trace_id for traces based on session membership.

        A trace's parent is the trace whose child_session_id matches
        the trace's session_id.

        Returns:
            Number of traces updated
        """
        conn = self._db.connect()
        total_updated = 0

        try:
            # Step 1: Set parent_trace_id for traces without one
            # IMPORTANT: Exclude root traces (root_% without _seg) - they should NEVER have a parent
            result = conn.execute("""
                UPDATE agent_traces t1
                SET parent_trace_id = (
                    SELECT t2.trace_id
                    FROM agent_traces t2
                    WHERE t2.child_session_id = t1.session_id
                      AND t2.trace_id != t1.trace_id
                    LIMIT 1
                )
                WHERE parent_trace_id IS NULL
                  AND NOT (t1.trace_id LIKE 'root_%' AND t1.trace_id NOT LIKE '%_seg%')
                  AND EXISTS (
                    SELECT 1 FROM agent_traces t2
                    WHERE t2.child_session_id = t1.session_id
                      AND t2.trace_id != t1.trace_id
                )
            """)
            updated = result.rowcount if hasattr(result, "rowcount") else 0
            total_updated += updated

            # Step 2: Update parent_agent from parent's subagent_type
            # This runs even if parent_trace_id was already set (to fix stale data)
            result = conn.execute("""
                UPDATE agent_traces t1
                SET parent_agent = (
                    SELECT t2.subagent_type
                    FROM agent_traces t2
                    WHERE t2.trace_id = t1.parent_trace_id
                )
                WHERE parent_trace_id IS NOT NULL
                  AND (
                    parent_agent IS NULL
                    OR parent_agent = 'user'
                    OR parent_agent != (
                        SELECT t2.subagent_type
                        FROM agent_traces t2
                        WHERE t2.trace_id = t1.parent_trace_id
                    )
                  )
            """)
            updated = result.rowcount if hasattr(result, "rowcount") else 0
            total_updated += updated

            if total_updated > 0:
                debug(f"[TraceBuilder] Resolved {total_updated} parent traces")
            return total_updated

        except Exception as e:
            debug(f"[TraceBuilder] Failed to resolve parent traces: {e}")
            return 0

    def update_root_trace_agents(self) -> int:
        """Update root traces subagent_type from their session's first message.

        Root traces are created before messages are indexed, so they have
        subagent_type='user'. This method updates them with the actual agent
        type from the first assistant message in their session.

        Returns:
            Number of traces updated
        """
        conn = self._db.connect()

        try:
            # Update root traces with agent from first assistant message
            result = conn.execute("""
                UPDATE agent_traces
                SET subagent_type = (
                    SELECT m.agent
                    FROM messages m
                    WHERE m.session_id = agent_traces.child_session_id
                      AND m.role = 'assistant'
                      AND m.agent IS NOT NULL
                      AND m.agent != ''
                    ORDER BY m.created_at ASC
                    LIMIT 1
                )
                WHERE trace_id LIKE 'root_%'
                  AND subagent_type = 'user'
                  AND EXISTS (
                    SELECT 1 FROM messages m
                    WHERE m.session_id = agent_traces.child_session_id
                      AND m.role = 'assistant'
                      AND m.agent IS NOT NULL
                      AND m.agent != ''
                )
            """)

            updated = result.rowcount if hasattr(result, "rowcount") else 0
            if updated > 0:
                debug(f"[TraceBuilder] Updated {updated} root trace agents")
            return updated

        except Exception as e:
            debug(f"[TraceBuilder] Failed to update root trace agents: {e}")
            return 0

    def _resolve_parent_trace_id(self, session_id: str, trace_id: str) -> Optional[str]:
        """Resolve parent trace ID for a delegation trace.

        A delegation trace's parent is the trace whose child_session_id
        matches the delegation's session_id.

        Args:
            session_id: Session ID of the delegation trace
            trace_id: Trace ID to exclude from search

        Returns:
            Parent trace ID or None
        """
        conn = self._db.connect()
        try:
            result = conn.execute(
                """
                SELECT trace_id
                FROM agent_traces
                WHERE child_session_id = ?
                  AND trace_id != ?
                LIMIT 1
                """,
                [session_id, trace_id],
            ).fetchone()
            return result[0] if result else None
        except Exception:
            return None

    def _resolve_parent_agent(self, message_id: Optional[str]) -> Optional[str]:
        """Resolve parent agent from message.

        Args:
            message_id: Message ID containing the task tool call

        Returns:
            Agent name or None
        """
        if not message_id:
            return None

        conn = self._db.connect()
        try:
            result = conn.execute(
                "SELECT agent FROM messages WHERE id = ?",
                [message_id],
            ).fetchone()
            return result[0] if result else None
        except Exception:
            return None

    def create_root_trace(
        self,
        session_id: str,
        title: Optional[str],
        agent: Optional[str],
        first_message: Optional[str],
        created_at: Optional[datetime],
        updated_at: Optional[datetime],
    ) -> Optional[str]:
        """Create a trace for a root session (user-initiated).

        Root sessions are sessions without a parentID, representing
        direct user conversations.

        Args:
            session_id: Session ID
            title: Session title
            agent: Primary agent for the session
            first_message: First user message content
            created_at: Session creation time
            updated_at: Session update time

        Returns:
            The trace_id if created, None on error
        """
        trace_id = f"{ROOT_TRACE_PREFIX}{session_id}"

        # Calculate duration
        duration_ms = None
        if created_at and updated_at:
            delta = updated_at - created_at
            duration_ms = int(delta.total_seconds() * 1000)

        conn = self._db.connect()

        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_traces
                (trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
                 prompt_input, prompt_output, started_at, ended_at, duration_ms,
                 tokens_in, tokens_out, status, tools_used, child_session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    trace_id,
                    session_id,
                    None,  # Root has no parent
                    ROOT_AGENT_TYPE,  # "user"
                    agent or ROOT_AGENT_TYPE,
                    first_message or title or "(No prompt)",
                    None,
                    created_at or datetime.now(),
                    updated_at,
                    duration_ms,
                    None,
                    None,
                    "completed" if updated_at else "running",
                    [],
                    session_id,  # Root's child_session_id is itself
                ],
            )

            debug(f"[TraceBuilder] Created root trace {trace_id}")
            return trace_id

        except Exception as e:
            debug(f"[TraceBuilder] Failed to create root trace: {e}")
            return None

    def create_conversation_segments(self, session_id: str) -> int:
        """Create trace segments for agent changes within a session.

        When a user switches agents mid-session (e.g., from @build to @plan),
        this creates separate trace segments for each agent block.

        Args:
            session_id: Session ID to analyze

        Returns:
            Number of segments created
        """
        conn = self._db.connect()

        try:
            # Get all assistant messages for this session, ordered by time
            messages = conn.execute(
                """
                SELECT id, agent, created_at, completed_at,
                       tokens_input, tokens_output
                FROM messages
                WHERE session_id = ?
                  AND role = 'assistant'
                  AND agent IS NOT NULL
                  AND agent != ''
                ORDER BY created_at ASC
                """,
                [session_id],
            ).fetchall()

            if not messages:
                return 0

            # Detect agent segments
            segments = []
            current_agent = None
            segment_start = None
            segment_end = None
            segment_tokens_in = 0
            segment_tokens_out = 0

            for msg in messages:
                msg_agent = msg[1]
                msg_created = msg[2]
                msg_completed = msg[3] or msg_created
                msg_tokens_in = msg[4] or 0
                msg_tokens_out = msg[5] or 0

                # Skip internal agents
                if msg_agent in ("compaction", "summarizer", "title"):
                    continue

                if msg_agent != current_agent:
                    # Save previous segment
                    if current_agent is not None:
                        segments.append(
                            {
                                "agent": current_agent,
                                "start": segment_start,
                                "end": segment_end,
                                "tokens_in": segment_tokens_in,
                                "tokens_out": segment_tokens_out,
                            }
                        )

                    # Start new segment
                    current_agent = msg_agent
                    segment_start = msg_created
                    segment_tokens_in = 0
                    segment_tokens_out = 0

                # Update segment
                segment_end = msg_completed
                segment_tokens_in += msg_tokens_in
                segment_tokens_out += msg_tokens_out

            # Save last segment
            if current_agent is not None:
                segments.append(
                    {
                        "agent": current_agent,
                        "start": segment_start,
                        "end": segment_end,
                        "tokens_in": segment_tokens_in,
                        "tokens_out": segment_tokens_out,
                    }
                )

            # Only create segment traces if there are multiple agents
            if len(segments) <= 1:
                # Single agent - update root trace with correct agent
                if segments:
                    self._update_root_trace_agent(session_id, segments[0])
                return 0

            # Delete old root trace (will be replaced by segments)
            root_trace_id = f"{ROOT_TRACE_PREFIX}{session_id}"

            # Create segment traces
            created = 0
            for i, seg in enumerate(segments):
                segment_trace_id = f"{ROOT_TRACE_PREFIX}{session_id}_seg{i}"

                # Calculate duration
                duration_ms = None
                if seg["start"] and seg["end"]:
                    delta = seg["end"] - seg["start"]
                    duration_ms = int(delta.total_seconds() * 1000)

                conn.execute(
                    """
                    INSERT OR REPLACE INTO agent_traces
                    (trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
                     prompt_input, prompt_output, started_at, ended_at, duration_ms,
                     tokens_in, tokens_out, status, tools_used, child_session_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        segment_trace_id,
                        session_id,
                        root_trace_id if i > 0 else None,  # First segment has no parent
                        ROOT_AGENT_TYPE if i == 0 else segments[i - 1]["agent"],
                        seg["agent"],
                        f"(segment {i}: @{seg['agent']})",
                        None,
                        seg["start"],
                        seg["end"],
                        duration_ms,
                        seg["tokens_in"],
                        seg["tokens_out"],
                        "completed",
                        [],
                        session_id,
                    ],
                )
                created += 1

            # Update root trace to point to first segment
            if created > 0:
                conn.execute(
                    """
                    UPDATE agent_traces
                    SET subagent_type = ?
                    WHERE trace_id = ?
                    """,
                    [segments[0]["agent"], root_trace_id],
                )

            debug(f"[TraceBuilder] Created {created} segments for {session_id}")
            return created

        except Exception as e:
            debug(f"[TraceBuilder] Failed to create segments: {e}")
            return 0

    def analyze_all_sessions_for_segments(self) -> int:
        """Analyze all root sessions and create segments where needed.

        Finds sessions with multiple agents and creates segment traces.
        Only processes sessions that haven't been segmented yet.

        Returns:
            Total number of segments created
        """
        conn = self._db.connect()

        try:
            # Find root sessions that might need segmentation
            # (have messages with different agents)
            # EXCLUDE sessions that already have segment traces
            sessions = conn.execute(
                """
                SELECT DISTINCT m.session_id
                FROM messages m
                JOIN agent_traces t ON t.session_id = m.session_id
                WHERE t.trace_id LIKE 'root_%'
                  AND t.trace_id NOT LIKE '%_seg%'
                  AND m.role = 'assistant'
                  AND m.agent IS NOT NULL
                  AND m.agent NOT IN ('compaction', 'summarizer', 'title')
                  AND NOT EXISTS (
                      SELECT 1 FROM agent_traces seg
                      WHERE seg.session_id = m.session_id
                        AND seg.trace_id LIKE '%_seg%'
                  )
                GROUP BY m.session_id
                HAVING COUNT(DISTINCT m.agent) > 1
                """
            ).fetchall()

            total_created = 0
            for (session_id,) in sessions:
                created = self.create_conversation_segments(session_id)
                total_created += created

            if total_created > 0:
                debug(
                    f"[TraceBuilder] Created {total_created} segments across {len(sessions)} sessions"
                )

            return total_created

        except Exception as e:
            debug(f"[TraceBuilder] Failed to analyze sessions: {e}")
            return 0

    def _update_root_trace_agent(self, session_id: str, segment: dict) -> None:
        """Update root trace with agent and timing from single segment."""
        conn = self._db.connect()
        trace_id = f"{ROOT_TRACE_PREFIX}{session_id}"

        duration_ms = None
        if segment["start"] and segment["end"]:
            delta = segment["end"] - segment["start"]
            duration_ms = int(delta.total_seconds() * 1000)

        try:
            conn.execute(
                """
                UPDATE agent_traces
                SET subagent_type = ?,
                    tokens_in = ?,
                    tokens_out = ?,
                    duration_ms = COALESCE(duration_ms, ?)
                WHERE trace_id = ?
                """,
                [
                    segment["agent"],
                    segment["tokens_in"],
                    segment["tokens_out"],
                    duration_ms,
                    trace_id,
                ],
            )
        except Exception as e:
            debug(f"[TraceBuilder] Failed to update root trace: {e}")

    def get_stats(self) -> dict:
        """Get trace statistics.

        Returns:
            Dict with trace counts by status
        """
        conn = self._db.connect()

        try:
            total = conn.execute("SELECT COUNT(*) FROM agent_traces").fetchone()[0]

            by_status = conn.execute("""
                SELECT status, COUNT(*) FROM agent_traces
                GROUP BY status
            """).fetchall()

            root_count = conn.execute("""
                SELECT COUNT(*) FROM agent_traces
                WHERE trace_id LIKE 'root_%'
            """).fetchone()[0]

            delegation_count = conn.execute("""
                SELECT COUNT(*) FROM agent_traces
                WHERE trace_id NOT LIKE 'root_%'
            """).fetchone()[0]

            return {
                "total": total,
                "by_status": {row[0]: row[1] for row in by_status},
                "root_traces": root_count,
                "delegation_traces": delegation_count,
            }

        except Exception as e:
            debug(f"[TraceBuilder] Failed to get stats: {e}")
            return {
                "total": 0,
                "by_status": {},
                "root_traces": 0,
                "delegation_traces": 0,
            }
