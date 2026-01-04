"""
Tracing Tree Builder - Constructs hierarchical trace trees for the dashboard.

This module extracts the tree-building logic from server.py into a dedicated class
for better separation of concerns and testability.
"""

import re
from datetime import datetime, timedelta
from threading import Lock
from typing import Any

from ..analytics import get_analytics_db
from ..analytics.tracing.helpers import extract_tool_display_info


# Minimum timestamp for sorting items without timestamps
MIN_TIMESTAMP = "0000-01-01T00:00:00"


class TracingTreeBuilder:
    """Builds hierarchical tracing trees from database data.

    The tree structure is:
    - Session (user → agent)
      - Exchange (user turn with tools)
        - Tool (bash, read, edit, etc.)
        - Delegation (agent → subagent)
          - Tool ...
    """

    def __init__(self, db_lock: Lock):
        """Initialize the builder.

        Args:
            db_lock: Lock for thread-safe database access.
        """
        self._db_lock = db_lock

    def build_tree(self, days: int = 30, include_tools: bool = True) -> list[dict]:
        """Build the complete tracing tree.

        Args:
            days: Number of days to look back.
            include_tools: Whether to include tool details.

        Returns:
            List of session nodes with nested children.
        """
        with self._db_lock:
            db = get_analytics_db()
            conn = db.connect()
            start_date = datetime.now() - timedelta(days=days)

            # Fetch all data
            root_rows = self._fetch_root_traces(conn, start_date)
            segment_rows = self._fetch_segments(conn, start_date)
            child_rows = self._fetch_child_traces(conn, start_date)

            # Build lookup structures
            segments_by_session = self._group_by_session(segment_rows)
            root_session_ids = {row[1] for row in root_rows}
            all_session_ids = self._collect_session_ids(root_rows, child_rows)

            # Fetch tools if requested
            tools_by_session = {}
            tools_by_message = {}
            if include_tools and all_session_ids:
                tools_by_session = self._fetch_tools_by_session(conn, all_session_ids)
                tools_by_message = self._fetch_tools_by_message(conn, root_session_ids)

            # Find subagent sessions for delegation tokens
            subagent_data = self._fetch_subagent_sessions(conn, start_date)

            # Build children lookup (delegations)
            children_by_parent = self._build_children_lookup(
                child_rows, tools_by_session, subagent_data, include_tools
            )

            # Fetch exchanges (user messages)
            exchanges_by_session = {}
            tokens_by_session = {}
            if root_session_ids:
                exchanges_by_session = self._fetch_exchanges(
                    conn, root_session_ids, tools_by_message, segments_by_session
                )
                tokens_by_session = self._fetch_session_tokens(conn, root_session_ids)

            # Build final tree
            sessions = self._build_sessions(
                root_rows,
                children_by_parent,
                segments_by_session,
                exchanges_by_session,
                tokens_by_session,
            )

            return sessions

    # -------------------------------------------------------------------------
    # Data Fetching Methods
    # -------------------------------------------------------------------------

    def _fetch_root_traces(self, conn: Any, start_date: datetime) -> list:
        """Fetch root traces (user-initiated sessions)."""
        return conn.execute(
            """
            SELECT 
                t.trace_id,
                t.session_id,
                t.parent_agent,
                t.subagent_type,
                t.started_at,
                t.ended_at,
                t.duration_ms,
                t.tokens_in,
                t.tokens_out,
                t.status,
                t.prompt_input,
                s.title,
                s.directory,
                t.child_session_id
            FROM agent_traces t
            LEFT JOIN sessions s ON t.session_id = s.id
            WHERE t.parent_trace_id IS NULL
              AND t.trace_id LIKE 'root_%'
              AND t.trace_id NOT LIKE '%_seg%'
              AND t.started_at >= ?
            ORDER BY t.started_at DESC
            """,
            [start_date],
        ).fetchall()

    def _fetch_segments(self, conn: Any, start_date: datetime) -> list:
        """Fetch segment traces (agent changes within sessions)."""
        return conn.execute(
            """
            SELECT 
                t.trace_id,
                t.session_id,
                t.parent_agent,
                t.subagent_type,
                t.started_at,
                t.ended_at,
                t.duration_ms,
                t.tokens_in,
                t.tokens_out,
                t.status,
                t.prompt_input,
                t.child_session_id
            FROM agent_traces t
            WHERE t.trace_id LIKE 'root_%_seg%'
              AND t.started_at >= ?
            ORDER BY t.started_at ASC
            """,
            [start_date],
        ).fetchall()

    def _fetch_child_traces(self, conn: Any, start_date: datetime) -> list:
        """Fetch child traces (delegations)."""
        return conn.execute(
            """
            SELECT 
                t.trace_id,
                t.session_id,
                t.parent_trace_id,
                t.parent_agent,
                t.subagent_type,
                t.started_at,
                t.ended_at,
                t.duration_ms,
                t.tokens_in,
                t.tokens_out,
                t.status,
                t.prompt_input,
                t.prompt_output,
                t.child_session_id
            FROM agent_traces t
            WHERE t.parent_trace_id IS NOT NULL
              AND t.trace_id NOT LIKE 'root_%'
              AND t.started_at >= ?
            ORDER BY t.started_at ASC
            """,
            [start_date],
        ).fetchall()

    def _fetch_tools_by_session(self, conn: Any, session_ids: set) -> dict:
        """Fetch tools grouped by session."""
        placeholders = ",".join(["?" for _ in session_ids])
        rows = conn.execute(
            f"""
            SELECT 
                id, session_id, tool_name, tool_status,
                arguments, created_at, duration_ms, result_summary
            FROM parts
            WHERE session_id IN ({placeholders})
              AND part_type = 'tool'
              AND tool_name IS NOT NULL
              AND tool_name != 'task'
            ORDER BY created_at ASC
            """,
            list(session_ids),
        ).fetchall()

        tools_by_session: dict = {}
        for row in rows:
            session_id = row[1]
            if session_id not in tools_by_session:
                tools_by_session[session_id] = []

            tool_name = row[2]
            arguments = row[4]
            display_info = extract_tool_display_info(tool_name, arguments)

            tools_by_session[session_id].append(
                {
                    "id": row[0],
                    "node_type": "tool",
                    "tool_name": tool_name,
                    "tool_status": row[3],
                    "display_info": display_info,
                    "created_at": row[5].isoformat() if row[5] else None,
                    "duration_ms": row[6],
                    "children": [],
                }
            )

        return tools_by_session

    def _fetch_tools_by_message(self, conn: Any, session_ids: set) -> dict:
        """Fetch tools grouped by message ID."""
        placeholders = ",".join(["?" for _ in session_ids])
        rows = conn.execute(
            f"""
            SELECT 
                id, session_id, message_id, tool_name, tool_status,
                arguments, created_at, duration_ms, result_summary
            FROM parts
            WHERE session_id IN ({placeholders})
              AND part_type = 'tool'
              AND tool_name IS NOT NULL
              AND tool_name != 'task'
            ORDER BY created_at ASC
            """,
            list(session_ids),
        ).fetchall()

        tools_by_message: dict = {}
        for row in rows:
            msg_id = row[2]
            if msg_id:
                if msg_id not in tools_by_message:
                    tools_by_message[msg_id] = []

                tool_name = row[3]
                arguments = row[5]
                display_info = extract_tool_display_info(tool_name, arguments)

                tools_by_message[msg_id].append(
                    {
                        "trace_id": f"tool_{row[0]}",
                        "session_id": row[1],
                        "node_type": "tool",
                        "tool_name": tool_name,
                        "tool_status": row[4],
                        "arguments": arguments,
                        "display_info": display_info,
                        "started_at": row[6].isoformat() if row[6] else None,
                        "duration_ms": row[7],
                        "result_summary": row[8],
                        "children": [],
                    }
                )

        return tools_by_message

    def _fetch_subagent_sessions(self, conn: Any, start_date: datetime) -> list:
        """Fetch subagent sessions with their tokens."""
        # Find sessions that look like subagent sessions
        sessions = conn.execute(
            """
            SELECT id, title, created_at
            FROM sessions
            WHERE title LIKE '%subagent)%'
              AND created_at >= ?
            ORDER BY created_at ASC
            """,
            [start_date],
        ).fetchall()

        if not sessions:
            return []

        # Get tokens for these sessions
        session_ids = [s[0] for s in sessions]
        placeholders = ",".join(["?" for _ in session_ids])
        token_rows = conn.execute(
            f"""
            SELECT 
                session_id,
                COALESCE(SUM(tokens_input), 0) as tokens_in,
                COALESCE(SUM(tokens_output), 0) as tokens_out,
                COALESCE(SUM(tokens_cache_read), 0) as cache_read
            FROM messages
            WHERE session_id IN ({placeholders})
            GROUP BY session_id
            """,
            session_ids,
        ).fetchall()

        tokens_map = {
            row[0]: {"tokens_in": row[1], "tokens_out": row[2], "cache_read": row[3]}
            for row in token_rows
        }

        # Build result with agent type extracted from title
        result = []
        for session_id, title, created_at in sessions:
            match = re.search(r"@(\w+)\s+subagent", title or "")
            if match and created_at:
                result.append(
                    {
                        "session_id": session_id,
                        "agent_type": match.group(1),
                        "created_at": created_at,
                        "tokens": tokens_map.get(session_id, {}),
                    }
                )

        return result

    def _fetch_exchanges(
        self,
        conn: Any,
        session_ids: set,
        tools_by_message: dict,
        segments_by_session: dict,
    ) -> dict:
        """Fetch user messages (exchanges) with their tools."""
        placeholders = ",".join(["?" for _ in session_ids])

        rows = conn.execute(
            f"""
            SELECT 
                m.id,
                m.session_id,
                m.created_at,
                m.role,
                m.agent,
                (SELECT p.content FROM parts p 
                 WHERE p.message_id = m.id AND p.part_type = 'text' 
                 LIMIT 1) as content,
                m.tokens_input,
                m.tokens_output,
                m.tokens_cache_read
            FROM messages m
            WHERE m.session_id IN ({placeholders})
            ORDER BY m.session_id, m.created_at ASC
            """,
            list(session_ids),
        ).fetchall()

        # Build segment timelines for agent type lookup
        segment_timeline = self._build_segment_timeline(segments_by_session)
        initial_agent = self._get_initial_agents(segments_by_session)

        exchanges_by_session: dict = {}
        current_user_msg = None

        for row in rows:
            msg_id, session_id, created_at, role, msg_agent = row[:5]
            content = row[5] or ""
            tokens_input, tokens_output, tokens_cache = row[6:9]

            if role == "user":
                # Determine agent type
                agent_type = msg_agent or self._get_agent_at_time(
                    session_id, created_at, segment_timeline, initial_agent
                )

                current_user_msg = {
                    "trace_id": f"exchange_{msg_id}",
                    "session_id": session_id,
                    "node_type": "user_turn",
                    "parent_agent": "user",
                    "subagent_type": agent_type,
                    "started_at": created_at.isoformat() if created_at else None,
                    "prompt_input": content[:500] if content else "",
                    "children": [],
                    "tokens_in": None,
                    "tokens_out": None,
                    "cache_read": None,
                }

                if session_id not in exchanges_by_session:
                    exchanges_by_session[session_id] = []
                exchanges_by_session[session_id].append(current_user_msg)

            elif role == "assistant" and current_user_msg:
                # Attach tools
                msg_tools = tools_by_message.get(msg_id, [])
                if msg_tools:
                    current_user_msg["children"].extend(msg_tools)

                # Add tokens
                current_user_msg["tokens_in"] = tokens_input
                current_user_msg["tokens_out"] = tokens_output
                current_user_msg["cache_read"] = tokens_cache

                # Update agent type if different (handles compaction)
                if msg_agent and msg_agent != current_user_msg.get("subagent_type"):
                    current_user_msg["subagent_type"] = msg_agent

        return exchanges_by_session

    def _fetch_session_tokens(self, conn: Any, session_ids: set) -> dict:
        """Fetch aggregated tokens per session."""
        placeholders = ",".join(["?" for _ in session_ids])
        rows = conn.execute(
            f"""
            SELECT 
                session_id,
                COALESCE(SUM(tokens_input), 0) as tokens_in,
                COALESCE(SUM(tokens_output), 0) as tokens_out,
                COALESCE(SUM(tokens_cache_read), 0) as cache_read
            FROM messages
            WHERE session_id IN ({placeholders})
            GROUP BY session_id
            """,
            list(session_ids),
        ).fetchall()

        return {
            row[0]: {"tokens_in": row[1], "tokens_out": row[2], "cache_read": row[3]}
            for row in rows
        }

    # -------------------------------------------------------------------------
    # Tree Building Methods
    # -------------------------------------------------------------------------

    def _build_children_lookup(
        self,
        child_rows: list,
        tools_by_session: dict,
        subagent_data: list,
        include_tools: bool,
    ) -> dict:
        """Build lookup of children by parent trace ID."""
        children_by_parent: dict = {}

        for row in child_rows:
            parent_id = row[2]  # parent_trace_id
            if parent_id not in children_by_parent:
                children_by_parent[parent_id] = []

            child_session_id = row[13]
            child_tools = (
                tools_by_session.get(child_session_id, []) if include_tools else []
            )

            # Try to find matching subagent session for tokens
            delegation_start = row[5]
            delegation_agent = row[4]
            delegation_tokens = {"tokens_in": row[8], "tokens_out": row[9]}

            if not delegation_tokens["tokens_in"] and delegation_start:
                for sa in subagent_data:
                    if sa["agent_type"] == delegation_agent:
                        time_diff = abs(
                            (sa["created_at"] - delegation_start).total_seconds()
                        )
                        if time_diff < 5:
                            delegation_tokens = {
                                "tokens_in": sa["tokens"].get("tokens_in"),
                                "tokens_out": sa["tokens"].get("tokens_out"),
                                "cache_read": sa["tokens"].get("cache_read"),
                            }
                            child_session_id = sa["session_id"]
                            break

            children_by_parent[parent_id].append(
                {
                    "trace_id": row[0],
                    "session_id": row[1],
                    "child_session_id": child_session_id,
                    "node_type": "agent",
                    "parent_trace_id": row[2],
                    "parent_agent": row[3],
                    "subagent_type": row[4],
                    "started_at": row[5].isoformat() if row[5] else None,
                    "ended_at": row[6].isoformat() if row[6] else None,
                    "duration_ms": row[7],
                    "tokens_in": delegation_tokens.get("tokens_in"),
                    "tokens_out": delegation_tokens.get("tokens_out"),
                    "cache_read": delegation_tokens.get("cache_read"),
                    "status": row[10],
                    "prompt_input": row[11],
                    "prompt_output": row[12],
                    "children": [t.copy() for t in child_tools],
                }
            )

        return children_by_parent

    def _build_sessions(
        self,
        root_rows: list,
        children_by_parent: dict,
        segments_by_session: dict,
        exchanges_by_session: dict,
        tokens_by_session: dict,
    ) -> list:
        """Build the final session list with all children."""
        sessions = []

        for row in root_rows:
            trace_id = row[0]
            session_id = row[1]
            agent_type = row[3]

            # Get agent delegations
            agent_children = self._build_children_recursive(
                children_by_parent, trace_id
            )

            # Get children from segments
            for seg_row in segments_by_session.get(session_id, []):
                seg_trace_id = seg_row[0]
                seg_children = self._build_children_recursive(
                    children_by_parent, seg_trace_id
                )
                agent_children.extend(seg_children)

            # Add exchanges
            session_exchanges = exchanges_by_session.get(session_id, [])
            if session_exchanges:
                # Link delegations to exchanges
                self._link_delegations_to_exchanges(session_exchanges, agent_children)
                agent_children = []  # Delegations now nested in exchanges

                # Calculate exchange durations
                self._calculate_exchange_durations(session_exchanges, row[5])

                agent_children = session_exchanges + agent_children
                agent_children.sort(key=get_sort_key)

            # Get session tokens
            session_tokens = tokens_by_session.get(session_id, {})

            session = {
                "session_id": session_id,
                "trace_id": trace_id,
                "node_type": "session",
                "parent_agent": row[2] or "user",
                "agent_type": agent_type,
                "started_at": row[4].isoformat() if row[4] else None,
                "ended_at": row[5].isoformat() if row[5] else None,
                "duration_ms": row[6],
                "tokens_in": session_tokens.get("tokens_in") or row[7],
                "tokens_out": session_tokens.get("tokens_out") or row[8],
                "cache_read": session_tokens.get("cache_read"),
                "status": row[9],
                "prompt_input": row[10],
                "title": row[11] or "",
                "directory": row[12] or "",
                "children": agent_children,
            }

            session["trace_count"] = count_traces(session) - 1
            sessions.append(session)

        return sessions

    def _build_children_recursive(
        self, children_by_parent: dict, parent_trace_id: str, depth: int = 0
    ) -> list:
        """Recursively build children for a parent trace."""
        if depth > 10:  # Prevent infinite recursion
            return []

        children = children_by_parent.get(parent_trace_id, [])
        for child in children:
            nested = self._build_children_recursive(
                children_by_parent, child["trace_id"], depth + 1
            )
            child["children"].extend(nested)
            child["children"].sort(key=get_sort_key)

        children.sort(key=get_sort_key)
        return children

    def _link_delegations_to_exchanges(
        self, exchanges: list, delegations: list
    ) -> None:
        """Link delegations to the exchange that triggered them."""
        if not delegations:
            return

        sorted_exchanges = sorted(exchanges, key=lambda x: x.get("started_at") or "")

        for delegation in delegations:
            deleg_start = delegation.get("started_at") or ""

            # Find the exchange that was active when delegation started
            parent_exchange = None
            for ex in sorted_exchanges:
                ex_start = ex.get("started_at") or ""
                if ex_start <= deleg_start:
                    parent_exchange = ex
                else:
                    break

            if parent_exchange:
                parent_exchange["children"].append(delegation)
                parent_exchange["children"].sort(key=get_sort_key)
            else:
                exchanges.append(delegation)

    def _calculate_exchange_durations(self, exchanges: list, session_end: Any) -> None:
        """Calculate duration for each exchange."""
        sorted_exchanges = sorted(exchanges, key=lambda x: x.get("started_at") or "")

        for i, ex in enumerate(sorted_exchanges):
            ex_start_str = ex.get("started_at")
            if not ex_start_str:
                continue

            ended_at_str = None

            # Option 1: Last child's end time
            for child in reversed(ex.get("children", [])):
                child_end = child.get("ended_at")
                if child_end:
                    ended_at_str = child_end
                    break
                child_start = child.get("started_at")
                child_duration = child.get("duration_ms")
                if child_start and child_duration:
                    try:
                        start_dt = datetime.fromisoformat(child_start)
                        end_dt = start_dt + timedelta(milliseconds=child_duration)
                        ended_at_str = end_dt.isoformat()
                        break
                    except (ValueError, TypeError):
                        pass

            # Option 2: Next exchange's start time
            if not ended_at_str and i + 1 < len(sorted_exchanges):
                ended_at_str = sorted_exchanges[i + 1].get("started_at")

            # Option 3: Session end time
            if not ended_at_str and session_end:
                ended_at_str = session_end.isoformat()

            ex["ended_at"] = ended_at_str

            # Calculate duration
            if ex_start_str and ended_at_str:
                try:
                    start_dt = datetime.fromisoformat(ex_start_str)
                    end_dt = datetime.fromisoformat(ended_at_str)
                    ex["duration_ms"] = int((end_dt - start_dt).total_seconds() * 1000)
                except (ValueError, TypeError):
                    pass

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _group_by_session(self, rows: list) -> dict:
        """Group rows by session_id."""
        result: dict = {}
        for row in rows:
            session_id = row[1]
            if session_id not in result:
                result[session_id] = []
            result[session_id].append(row)
        return result

    def _collect_session_ids(self, root_rows: list, child_rows: list) -> set:
        """Collect all session IDs from root and child rows."""
        ids = set()
        for row in root_rows:
            ids.add(row[1])
            if row[13]:  # child_session_id
                ids.add(row[13])
        for row in child_rows:
            if row[13]:
                ids.add(row[13])
        return ids

    def _build_segment_timeline(self, segments_by_session: dict) -> dict:
        """Build timeline of agent changes per session."""
        timeline: dict = {}
        for session_id, segments in segments_by_session.items():
            timeline[session_id] = []
            for seg in segments:
                seg_ts = seg[4]  # started_at
                seg_agent = seg[3]  # subagent_type
                if seg_ts and seg_agent:
                    timeline[session_id].append((seg_ts, seg_agent))
            timeline[session_id].sort(key=lambda x: x[0])
        return timeline

    def _get_initial_agents(self, segments_by_session: dict) -> dict:
        """Get initial agent for each session."""
        result: dict = {}
        for session_id, segments in segments_by_session.items():
            if segments:
                first_seg = min(segments, key=lambda s: s[4] if s[4] else datetime.max)
                result[session_id] = first_seg[3] or "assistant"
        return result

    def _get_agent_at_time(
        self,
        session_id: str,
        timestamp: Any,
        segment_timeline: dict,
        initial_agent: dict,
    ) -> str:
        """Get the active agent at a given timestamp."""
        agent = initial_agent.get(session_id, "assistant")
        for seg_ts, seg_agent in segment_timeline.get(session_id, []):
            if timestamp >= seg_ts:
                agent = seg_agent
            else:
                break
        return agent


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------


def get_sort_key(item: dict) -> str:
    """Get a sortable timestamp from an item."""
    ts = item.get("started_at") or item.get("created_at")
    return ts if ts else MIN_TIMESTAMP


def count_traces(node: dict) -> int:
    """Count total traces in a subtree."""
    return 1 + sum(count_traces(c) for c in node.get("children", []))


# Note: extract_tool_display_info is imported from analytics.tracing.helpers
