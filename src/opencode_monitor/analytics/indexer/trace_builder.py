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

from ..db import AnalyticsDB
from ..models import AgentTrace
from .parsers import ParsedDelegation, ParsedPart
from ...utils.logger import debug, info


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
        status = self._determine_status(part.tool_status)

        # Resolve parent agent from message
        parent_agent = self._resolve_parent_agent(delegation.message_id)

        # Get prompt from delegation
        prompt_input = self._extract_prompt(part.arguments)

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
                    None,  # parent_trace_id resolved later
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

    def resolve_parent_traces(self) -> int:
        """Resolve parent_trace_id for traces based on session membership.

        A trace's parent is the trace whose child_session_id matches
        the trace's session_id.

        Returns:
            Number of traces updated
        """
        conn = self._db.connect()

        try:
            # Build mapping of child_session_id -> trace_id
            result = conn.execute("""
                UPDATE agent_traces t1
                SET parent_trace_id = (
                    SELECT t2.trace_id
                    FROM agent_traces t2
                    WHERE t2.child_session_id = t1.session_id
                      AND t2.trace_id != t1.trace_id
                    LIMIT 1
                ),
                parent_agent = (
                    SELECT t2.subagent_type
                    FROM agent_traces t2
                    WHERE t2.child_session_id = t1.session_id
                      AND t2.trace_id != t1.trace_id
                    LIMIT 1
                )
                WHERE parent_trace_id IS NULL
                  AND EXISTS (
                    SELECT 1 FROM agent_traces t2
                    WHERE t2.child_session_id = t1.session_id
                      AND t2.trace_id != t1.trace_id
                )
            """)

            updated = result.rowcount if hasattr(result, "rowcount") else 0
            if updated > 0:
                debug(f"[TraceBuilder] Resolved {updated} parent traces")
            return updated

        except Exception as e:
            debug(f"[TraceBuilder] Failed to resolve parent traces: {e}")
            return 0

    def _determine_status(self, tool_status: Optional[str]) -> str:
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

    def _extract_prompt(self, arguments: Optional[str]) -> str:
        """Extract prompt from task tool arguments.

        Args:
            arguments: JSON string of tool arguments

        Returns:
            Prompt text or empty string
        """
        if not arguments:
            return ""

        import json

        try:
            data = json.loads(arguments)
            return data.get("prompt", "") or ""
        except (json.JSONDecodeError, TypeError):
            return ""

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
