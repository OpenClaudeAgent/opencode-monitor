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
from .segments import SegmentBuilder


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
        self._segment_builder = SegmentBuilder(db)
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
            pass  # nosec B110 - table may already exist, ignore errors

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

        Uses 2 queries (count + update) for efficiency - O(1) vs O(N) queries.

        Returns:
            Number of traces updated
        """
        conn = self._db.connect()

        try:
            # Count traces that will be updated (DuckDB doesn't return rowcount)
            count_result = conn.execute(
                """
                SELECT COUNT(*) FROM agent_traces t
                WHERE t.child_session_id IS NOT NULL
                  AND (t.tokens_in IS NULL OR t.tokens_in = 0)
                  AND (t.tokens_out IS NULL OR t.tokens_out = 0)
                  AND EXISTS (
                      SELECT 1 FROM messages m
                      WHERE m.session_id = t.child_session_id
                      GROUP BY m.session_id
                      HAVING SUM(m.tokens_input) > 0 OR SUM(m.tokens_output) > 0
                  )
                """
            ).fetchone()
            will_update = count_result[0] if count_result else 0

            if will_update == 0:
                return 0

            # Update traces with aggregated tokens from messages
            conn.execute(
                """
                UPDATE agent_traces
                SET tokens_in = agg.total_in,
                    tokens_out = agg.total_out
                FROM (
                    SELECT
                        session_id,
                        COALESCE(SUM(tokens_input), 0) as total_in,
                        COALESCE(SUM(tokens_output), 0) as total_out
                    FROM messages
                    GROUP BY session_id
                    HAVING SUM(tokens_input) > 0 OR SUM(tokens_output) > 0
                ) agg
                WHERE agent_traces.child_session_id = agg.session_id
                  AND agent_traces.child_session_id IS NOT NULL
                  AND (agent_traces.tokens_in IS NULL OR agent_traces.tokens_in = 0)
                  AND (agent_traces.tokens_out IS NULL OR agent_traces.tokens_out = 0)
                """
            )

            if will_update > 0:
                debug(f"[TraceBuilder] Backfilled tokens for {will_update} traces")

            return will_update

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
        except Exception as e:
            debug(f"[TraceBuilder] Failed to resolve parent trace: {e}")
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

        Delegates to SegmentBuilder.

        Args:
            session_id: Session ID to analyze

        Returns:
            Number of segments created
        """
        return self._segment_builder.create_conversation_segments(session_id)

    def analyze_all_sessions_for_segments(self) -> int:
        """Analyze all root sessions and create segments where needed.

        Delegates to SegmentBuilder.

        Returns:
            Total number of segments created
        """
        return self._segment_builder.analyze_all_sessions_for_segments()

    def get_stats(self) -> dict:
        """Get trace statistics.

        Returns:
            Dict with trace counts by status
        """
        conn = self._db.connect()

        try:
            total_result = conn.execute("SELECT COUNT(*) FROM agent_traces").fetchone()
            total = total_result[0] if total_result else 0

            by_status = conn.execute("""
                SELECT status, COUNT(*) FROM agent_traces
                GROUP BY status
            """).fetchall()

            root_result = conn.execute("""
                SELECT COUNT(*) FROM agent_traces
                WHERE trace_id LIKE 'root_%'
            """).fetchone()
            root_count = root_result[0] if root_result else 0

            delegation_result = conn.execute("""
                SELECT COUNT(*) FROM agent_traces
                WHERE trace_id NOT LIKE 'root_%'
            """).fetchone()
            delegation_count = delegation_result[0] if delegation_result else 0

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

    # =========================================================================
    # Plan 45: Complete Tracing Architecture Methods
    # =========================================================================

    def build_all(self, session_id: Optional[str] = None) -> dict:
        """Build all trace tables (exchanges, exchange_traces, session_traces).

        Args:
            session_id: Optional session ID to build for. If None, builds for all.

        Returns:
            Dict with counts of records created for each table.
        """
        exchanges = self.build_exchanges(session_id)
        exchange_traces = self.build_exchange_traces(session_id)
        session_traces = self.build_session_traces(session_id)

        debug(
            f"[TraceBuilder] build_all complete: "
            f"exchanges={exchanges}, exchange_traces={exchange_traces}, "
            f"session_traces={session_traces}"
        )

        return {
            "exchanges": exchanges,
            "exchange_traces": exchange_traces,
            "session_traces": session_traces,
        }

    def build_exchanges(self, session_id: Optional[str] = None) -> int:
        """Build exchange records from messages.

        Groups messages into user->assistant pairs and extracts:
        - Full prompt input (first user text part)
        - Full prompt output (last assistant text part)
        - Token/cost aggregation from step_events
        - Tool call counts

        Args:
            session_id: Optional session ID filter. If None, builds for all sessions.

        Returns:
            Number of exchanges created.
        """
        conn = self._db.connect()

        try:
            # Delete existing exchanges for the session(s) and commit immediately
            # This prevents "duplicate key" errors if the transaction is interrupted
            if session_id:
                conn.execute("DELETE FROM exchanges WHERE session_id = ?", [session_id])
            else:
                conn.execute("DELETE FROM exchanges")

            # Commit the DELETE to ensure it's persisted before INSERT
            conn.commit()

            # Build session filter clause
            session_filter = "WHERE ep.session_id = ?" if session_id else ""
            params = [session_id] if session_id else []

            # Build exchanges from message pairs
            query = f"""
                INSERT INTO exchanges (
                    id, session_id, exchange_number,
                    user_message_id, assistant_message_id,
                    prompt_input, prompt_output,
                    started_at, ended_at, duration_ms,
                    tokens_in, tokens_out, tokens_reasoning, cost,
                    tool_count, reasoning_count,
                    agent, model_id
                )
                WITH user_messages AS (
                    SELECT
                        m.id,
                        m.session_id,
                        m.created_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY m.session_id ORDER BY m.created_at
                        ) as msg_num
                    FROM messages m
                    WHERE m.role = 'user'
                ),
                assistant_messages AS (
                    SELECT
                        m.id,
                        m.session_id,
                        m.created_at,
                        m.agent,
                        m.model_id,
                        ROW_NUMBER() OVER (
                            PARTITION BY m.session_id ORDER BY m.created_at
                        ) as msg_num
                    FROM messages m
                    WHERE m.role = 'assistant'
                ),
                exchange_pairs AS (
                    SELECT
                        u.id as user_msg_id,
                        u.session_id,
                        u.msg_num as exchange_num,
                        u.created_at as user_time,
                        a.id as assistant_msg_id,
                        a.created_at as assistant_time,
                        a.agent,
                        a.model_id
                    FROM user_messages u
                    LEFT JOIN assistant_messages a
                        ON u.session_id = a.session_id AND u.msg_num = a.msg_num
                ),
                user_prompts AS (
                    SELECT DISTINCT ON (p.message_id) p.message_id, p.content as prompt_input
                    FROM parts p
                    WHERE p.part_type = 'text'
                      AND p.message_id IN (SELECT user_msg_id FROM exchange_pairs)
                    ORDER BY p.message_id, p.created_at
                ),
                assistant_responses AS (
                    SELECT DISTINCT ON (p.message_id) p.message_id, p.content as prompt_output
                    FROM parts p
                    WHERE p.part_type = 'text'
                      AND p.message_id IN (
                          SELECT assistant_msg_id FROM exchange_pairs
                          WHERE assistant_msg_id IS NOT NULL
                      )
                    ORDER BY p.message_id, p.created_at DESC
                ),
                step_totals AS (
                    SELECT
                        se.message_id,
                        SUM(se.tokens_input) as tokens_in,
                        SUM(se.tokens_output) as tokens_out,
                        SUM(se.tokens_reasoning) as tokens_reasoning,
                        SUM(se.cost) as cost
                    FROM step_events se
                    WHERE se.event_type = 'finish'
                    GROUP BY se.message_id
                ),
                tool_counts AS (
                    SELECT message_id, COUNT(*) as tool_count
                    FROM parts
                    WHERE part_type = 'tool'
                    GROUP BY message_id
                ),
                reasoning_counts AS (
                    SELECT message_id, COUNT(*) as reasoning_count
                    FROM parts
                    WHERE part_type = 'reasoning'
                    GROUP BY message_id
                )
                SELECT
                    'exc_' || ep.session_id || '_' || CAST(ep.exchange_num AS VARCHAR) as id,
                    ep.session_id,
                    ep.exchange_num as exchange_number,
                    ep.user_msg_id,
                    ep.assistant_msg_id,
                    up.prompt_input,
                    ar.prompt_output,
                    ep.user_time as started_at,
                    ep.assistant_time as ended_at,
                    CASE
                        WHEN ep.assistant_time IS NOT NULL AND ep.user_time IS NOT NULL
                        THEN CAST(
                            EXTRACT(EPOCH FROM (ep.assistant_time - ep.user_time)) * 1000
                            AS INTEGER
                        )
                        ELSE NULL
                    END as duration_ms,
                    COALESCE(st.tokens_in, 0) as tokens_in,
                    COALESCE(st.tokens_out, 0) as tokens_out,
                    COALESCE(st.tokens_reasoning, 0) as tokens_reasoning,
                    COALESCE(st.cost, 0) as cost,
                    COALESCE(tc.tool_count, 0) + COALESCE(atc.tool_count, 0) as tool_count,
                    COALESCE(rc.reasoning_count, 0) as reasoning_count,
                    ep.agent,
                    ep.model_id
                FROM exchange_pairs ep
                LEFT JOIN user_prompts up ON up.message_id = ep.user_msg_id
                LEFT JOIN assistant_responses ar ON ar.message_id = ep.assistant_msg_id
                LEFT JOIN step_totals st ON st.message_id = ep.assistant_msg_id
                LEFT JOIN tool_counts tc ON tc.message_id = ep.user_msg_id
                LEFT JOIN tool_counts atc ON atc.message_id = ep.assistant_msg_id
                LEFT JOIN reasoning_counts rc ON rc.message_id = ep.assistant_msg_id
                {session_filter}
                ORDER BY ep.session_id, ep.exchange_num
                ON CONFLICT (id) DO UPDATE SET
                    session_id = EXCLUDED.session_id,
                    exchange_number = EXCLUDED.exchange_number,
                    user_message_id = EXCLUDED.user_message_id,
                    assistant_message_id = EXCLUDED.assistant_message_id,
                    prompt_input = EXCLUDED.prompt_input,
                    prompt_output = EXCLUDED.prompt_output,
                    started_at = EXCLUDED.started_at,
                    ended_at = EXCLUDED.ended_at,
                    duration_ms = EXCLUDED.duration_ms,
                    tokens_in = EXCLUDED.tokens_in,
                    tokens_out = EXCLUDED.tokens_out,
                    tokens_reasoning = EXCLUDED.tokens_reasoning,
                    cost = EXCLUDED.cost,
                    tool_count = EXCLUDED.tool_count,
                    reasoning_count = EXCLUDED.reasoning_count,
                    agent = EXCLUDED.agent,
                    model_id = EXCLUDED.model_id
            """

            conn.execute(query, params)

            # Get count of inserted rows
            if session_id:
                result = conn.execute(
                    "SELECT COUNT(*) FROM exchanges WHERE session_id = ?",
                    [session_id],
                ).fetchone()
            else:
                result = conn.execute("SELECT COUNT(*) FROM exchanges").fetchone()

            count = result[0] if result else 0
            debug(f"[TraceBuilder] Built {count} exchanges")
            return count

        except Exception as e:
            debug(f"[TraceBuilder] Failed to build exchanges: {e}")
            return 0

    def build_exchange_traces(self, session_id: Optional[str] = None) -> int:
        """Build chronological event timeline for each exchange.

        Orders all events (text, reasoning, tools, steps) by timestamp
        and creates exchange_traces records with:
        - event_type (user_prompt, reasoning, tool_call, step_finish, patch, assistant_response)
        - event_order (sequence within exchange)
        - event_data (JSON with type-specific details)

        Args:
            session_id: Optional session ID filter. If None, builds for all sessions.

        Returns:
            Number of exchange trace events created.
        """
        conn = self._db.connect()

        try:
            # Delete existing exchange_traces for the session(s) and commit immediately
            if session_id:
                conn.execute(
                    "DELETE FROM exchange_traces WHERE session_id = ?", [session_id]
                )
            else:
                conn.execute("DELETE FROM exchange_traces")

            # Commit the DELETE to ensure it's persisted before INSERT
            conn.commit()

            # Build session filter clause
            session_filter = "WHERE all_events.session_id = ?" if session_id else ""
            params = [session_id] if session_id else []

            query = f"""
                INSERT INTO exchange_traces (
                    id, session_id, exchange_id, event_type, event_order,
                    event_data, timestamp, duration_ms, tokens_in, tokens_out
                )
                WITH all_events AS (
                    -- User prompts
                    SELECT
                        p.id,
                        p.session_id,
                        e.id as exchange_id,
                        'user_prompt' as event_type,
                        p.created_at as timestamp,
                        NULL::INTEGER as duration_ms,
                        0 as tokens_in,
                        0 as tokens_out,
                        json_object(
                            'content', p.content,
                            'message_id', p.message_id
                        ) as event_data
                    FROM parts p
                    JOIN exchanges e ON e.user_message_id = p.message_id
                    WHERE p.part_type = 'text'

                    UNION ALL

                    -- Reasoning
                    SELECT
                        p.id,
                        p.session_id,
                        e.id as exchange_id,
                        'reasoning' as event_type,
                        p.created_at as timestamp,
                        p.duration_ms,
                        0 as tokens_in,
                        0 as tokens_out,
                        json_object(
                            'text', p.reasoning_text,
                            'has_signature', CASE WHEN p.anthropic_signature IS NOT NULL THEN true ELSE false END,
                            'signature', p.anthropic_signature
                        ) as event_data
                    FROM parts p
                    JOIN exchanges e ON e.assistant_message_id = p.message_id
                    WHERE p.part_type = 'reasoning'

                    UNION ALL

                    -- Tool calls
                    SELECT
                        p.id,
                        p.session_id,
                        e.id as exchange_id,
                        'tool_call' as event_type,
                        p.created_at as timestamp,
                        p.duration_ms,
                        0 as tokens_in,
                        0 as tokens_out,
                        json_object(
                            'tool_name', p.tool_name,
                            'status', p.tool_status,
                            'arguments', p.arguments,
                            'result_summary', LEFT(COALESCE(p.result_summary, ''), 500),
                            'error', p.error_message,
                            'child_session_id', p.child_session_id
                        ) as event_data
                    FROM parts p
                    JOIN exchanges e ON e.assistant_message_id = p.message_id
                    WHERE p.part_type = 'tool'

                    UNION ALL

                    -- Step finish events
                    SELECT
                        se.id,
                        se.session_id,
                        e.id as exchange_id,
                        'step_finish' as event_type,
                        se.created_at as timestamp,
                        NULL::INTEGER as duration_ms,
                        se.tokens_input as tokens_in,
                        se.tokens_output as tokens_out,
                        json_object(
                            'reason', se.reason,
                            'snapshot', se.snapshot_hash,
                            'cost', se.cost,
                            'tokens_reasoning', se.tokens_reasoning,
                            'tokens_cache_read', se.tokens_cache_read,
                            'tokens_cache_write', se.tokens_cache_write
                        ) as event_data
                    FROM step_events se
                    JOIN exchanges e ON e.assistant_message_id = se.message_id
                    WHERE se.event_type = 'finish'

                    UNION ALL

                    -- Patches
                    SELECT
                        pa.id,
                        pa.session_id,
                        e.id as exchange_id,
                        'patch' as event_type,
                        pa.created_at as timestamp,
                        NULL::INTEGER as duration_ms,
                        0 as tokens_in,
                        0 as tokens_out,
                        json_object(
                            'git_hash', pa.git_hash,
                            'files', pa.files,
                            'file_count', array_length(pa.files, 1)
                        ) as event_data
                    FROM patches pa
                    JOIN exchanges e ON e.assistant_message_id = pa.message_id

                    UNION ALL

                    -- Assistant responses (last text part only)
                    SELECT
                        p.id,
                        p.session_id,
                        e.id as exchange_id,
                        'assistant_response' as event_type,
                        p.created_at as timestamp,
                        NULL::INTEGER as duration_ms,
                        0 as tokens_in,
                        0 as tokens_out,
                        json_object(
                            'content', p.content,
                            'message_id', p.message_id
                        ) as event_data
                    FROM parts p
                    JOIN exchanges e ON e.assistant_message_id = p.message_id
                    WHERE p.part_type = 'text'
                      AND p.id = (
                          SELECT p2.id FROM parts p2
                          WHERE p2.message_id = e.assistant_message_id
                            AND p2.part_type = 'text'
                          ORDER BY p2.created_at DESC
                          LIMIT 1
                      )
                )
                SELECT
                    all_events.id || '_evt' as id,
                    all_events.session_id,
                    all_events.exchange_id,
                    all_events.event_type,
                    ROW_NUMBER() OVER (
                        PARTITION BY all_events.exchange_id ORDER BY all_events.timestamp
                    ) as event_order,
                    all_events.event_data,
                    all_events.timestamp,
                    all_events.duration_ms,
                    all_events.tokens_in,
                    all_events.tokens_out
                FROM all_events
                {session_filter}
                ORDER BY all_events.exchange_id, all_events.timestamp
                ON CONFLICT (id) DO UPDATE SET
                    session_id = EXCLUDED.session_id,
                    exchange_id = EXCLUDED.exchange_id,
                    event_type = EXCLUDED.event_type,
                    event_order = EXCLUDED.event_order,
                    event_data = EXCLUDED.event_data,
                    timestamp = EXCLUDED.timestamp,
                    duration_ms = EXCLUDED.duration_ms,
                    tokens_in = EXCLUDED.tokens_in,
                    tokens_out = EXCLUDED.tokens_out
            """

            conn.execute(query, params)

            # Get count of inserted rows
            if session_id:
                result = conn.execute(
                    "SELECT COUNT(*) FROM exchange_traces WHERE session_id = ?",
                    [session_id],
                ).fetchone()
            else:
                result = conn.execute("SELECT COUNT(*) FROM exchange_traces").fetchone()

            count = result[0] if result else 0
            debug(f"[TraceBuilder] Built {count} exchange traces")
            return count

        except Exception as e:
            debug(f"[TraceBuilder] Failed to build exchange traces: {e}")
            return 0

    def _calculate_delegation_depth(self, session_id: str) -> int:
        """Calculate depth in delegation tree (0 = root, 1 = first child, etc.).

        Uses delegations table to trace parent chain recursively.
        Walks up the tree from child to root, counting hops.

        Args:
            session_id: The session ID to calculate depth for

        Returns:
            Depth in the delegation tree (0 for root sessions)
        """
        conn = self._db.connect()
        depth = 0
        current_session = session_id
        visited = set()  # Prevent infinite loops from circular references

        try:
            while current_session and current_session not in visited:
                visited.add(current_session)

                # Find parent session via delegations table
                result = conn.execute(
                    """
                    SELECT session_id FROM delegations
                    WHERE child_session_id = ?
                    LIMIT 1
                    """,
                    [current_session],
                ).fetchone()

                if result and result[0]:
                    depth += 1
                    current_session = result[0]
                else:
                    break

            return depth

        except Exception as e:
            debug(f"[TraceBuilder] Failed to calculate depth for {session_id}: {e}")
            return 0

    def _build_delegation_depths(self) -> dict[str, int]:
        """Build depth map for all sessions using recursive CTE.

        Returns:
            Dict mapping session_id to depth (0 = root)
        """
        conn = self._db.connect()

        try:
            # Use recursive CTE to calculate depths efficiently
            results = conn.execute(
                """
                WITH RECURSIVE delegation_tree AS (
                    -- Base case: root sessions (not child of any delegation)
                    SELECT
                        s.id as session_id,
                        0 as depth
                    FROM sessions s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM delegations d
                        WHERE d.child_session_id = s.id
                    )

                    UNION ALL

                    -- Recursive case: child sessions
                    SELECT
                        d.child_session_id as session_id,
                        dt.depth + 1 as depth
                    FROM delegations d
                    JOIN delegation_tree dt ON dt.session_id = d.session_id
                    WHERE d.child_session_id IS NOT NULL
                )
                SELECT session_id, depth FROM delegation_tree
                """
            ).fetchall()

            return {row[0]: row[1] for row in results}

        except Exception as e:
            debug(f"[TraceBuilder] Failed to build depth map: {e}")
            return {}

    def build_session_traces(self, session_id: Optional[str] = None) -> int:
        """Build high-level session trace records.

        Aggregates from exchanges and handles delegation hierarchy:
        - Parent-child session links via delegations table
        - Recursive depth calculation (0 = root, 1 = first child, etc.)
        - Total metrics aggregation

        Args:
            session_id: Optional session ID filter. If None, builds for all sessions.

        Returns:
            Number of session traces created.
        """
        conn = self._db.connect()

        try:
            # Delete existing session_traces for the session(s) and commit immediately
            if session_id:
                conn.execute(
                    "DELETE FROM session_traces WHERE session_id = ?", [session_id]
                )
            else:
                conn.execute("DELETE FROM session_traces")

            # Commit the DELETE to ensure it's persisted before INSERT
            conn.commit()

            # Build session filter clause
            session_filter = "WHERE s.id = ?" if session_id else ""
            params = [session_id] if session_id else []

            # Use recursive CTE for proper depth calculation
            query = f"""
                INSERT INTO session_traces (
                    id, session_id, title, directory,
                    parent_session_id, parent_trace_id, depth,
                    total_exchanges, total_tool_calls,
                    total_file_reads, total_file_writes,
                    total_tokens, total_cost, total_delegations,
                    started_at, ended_at, duration_ms, status
                )
                WITH RECURSIVE delegation_tree AS (
                    -- Base case: root sessions (not child of any delegation)
                    SELECT
                        s.id as session_id,
                        CAST(NULL AS VARCHAR) as parent_session_id,
                        0 as depth
                    FROM sessions s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM delegations d
                        WHERE d.child_session_id = s.id
                    )

                    UNION ALL

                    -- Recursive case: child sessions
                    SELECT
                        d.child_session_id as session_id,
                        d.session_id as parent_session_id,
                        dt.depth + 1 as depth
                    FROM delegations d
                    JOIN delegation_tree dt ON dt.session_id = d.session_id
                    WHERE d.child_session_id IS NOT NULL
                ),
                exchange_stats AS (
                    SELECT
                        session_id,
                        COUNT(*) as total_exchanges,
                        SUM(tool_count) as total_tool_calls,
                        SUM(tokens_in + tokens_out + tokens_reasoning) as total_tokens,
                        SUM(cost) as total_cost,
                        MIN(started_at) as first_exchange,
                        MAX(ended_at) as last_exchange
                    FROM exchanges
                    GROUP BY session_id
                ),
                file_stats AS (
                    SELECT
                        session_id,
                        SUM(CASE WHEN operation = 'read' THEN 1 ELSE 0 END) as total_reads,
                        SUM(CASE WHEN operation IN ('write', 'edit') THEN 1 ELSE 0 END) as total_writes
                    FROM file_operations
                    GROUP BY session_id
                ),
                delegation_stats AS (
                    SELECT
                        session_id,
                        COUNT(*) as total_delegations
                    FROM delegations
                    GROUP BY session_id
                ),
                parent_traces AS (
                    -- Find the trace that created each child session
                    SELECT
                        d.child_session_id as session_id,
                        COALESCE(
                            -- First try agent_traces (delegation traces)
                            atr.trace_id,
                            -- Fallback: construct delegation trace ID from part
                            'del_' || p.id
                        ) as parent_trace_id
                    FROM delegations d
                    LEFT JOIN agent_traces atr ON atr.child_session_id = d.child_session_id
                    LEFT JOIN parts p ON p.id = d.id
                )
                SELECT
                    'st_' || s.id as id,
                    s.id as session_id,
                    s.title,
                    s.directory,
                    dt.parent_session_id,
                    pt.parent_trace_id,
                    COALESCE(dt.depth, 0) as depth,
                    COALESCE(es.total_exchanges, 0) as total_exchanges,
                    COALESCE(es.total_tool_calls, 0) as total_tool_calls,
                    COALESCE(fs.total_reads, 0) as total_file_reads,
                    COALESCE(fs.total_writes, 0) as total_file_writes,
                    COALESCE(es.total_tokens, 0) as total_tokens,
                    COALESCE(es.total_cost, 0) as total_cost,
                    COALESCE(ds.total_delegations, 0) as total_delegations,
                    COALESCE(es.first_exchange, s.created_at) as started_at,
                    COALESCE(es.last_exchange, s.updated_at) as ended_at,
                    s.duration_ms,
                    CASE
                        WHEN s.ended_at IS NOT NULL THEN 'completed'
                        ELSE 'running'
                    END as status
                FROM sessions s
                LEFT JOIN delegation_tree dt ON dt.session_id = s.id
                LEFT JOIN exchange_stats es ON es.session_id = s.id
                LEFT JOIN file_stats fs ON fs.session_id = s.id
                LEFT JOIN delegation_stats ds ON ds.session_id = s.id
                LEFT JOIN parent_traces pt ON pt.session_id = s.id
                {session_filter}
                ON CONFLICT (id) DO UPDATE SET
                    session_id = EXCLUDED.session_id,
                    title = EXCLUDED.title,
                    directory = EXCLUDED.directory,
                    parent_session_id = EXCLUDED.parent_session_id,
                    parent_trace_id = EXCLUDED.parent_trace_id,
                    depth = EXCLUDED.depth,
                    total_exchanges = EXCLUDED.total_exchanges,
                    total_tool_calls = EXCLUDED.total_tool_calls,
                    total_file_reads = EXCLUDED.total_file_reads,
                    total_file_writes = EXCLUDED.total_file_writes,
                    total_tokens = EXCLUDED.total_tokens,
                    total_cost = EXCLUDED.total_cost,
                    total_delegations = EXCLUDED.total_delegations,
                    started_at = EXCLUDED.started_at,
                    ended_at = EXCLUDED.ended_at,
                    duration_ms = EXCLUDED.duration_ms,
                    status = EXCLUDED.status
            """

            conn.execute(query, params)

            # Get count of inserted rows
            if session_id:
                result = conn.execute(
                    "SELECT COUNT(*) FROM session_traces WHERE session_id = ?",
                    [session_id],
                ).fetchone()
            else:
                result = conn.execute("SELECT COUNT(*) FROM session_traces").fetchone()

            count = result[0] if result else 0
            debug(f"[TraceBuilder] Built {count} session traces")
            return count

        except Exception as e:
            debug(f"[TraceBuilder] Failed to build session traces: {e}")
            return 0
