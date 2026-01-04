"""
Tracing Routes - Agent trace tree and hierarchy endpoints.

This module contains the complex tracing tree endpoints that build
hierarchical views of agent traces, conversations, and tool usage.
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any, Callable

from flask import Blueprint, jsonify, request

from ...analytics import get_analytics_db
from ...utils.logger import error
from ._context import get_db_lock

tracing_bp = Blueprint("tracing", __name__)


# =============================================================================
# Helper Functions
# =============================================================================

MIN_TIMESTAMP = "0000-01-01T00:00:00"


def get_sort_key(item: dict) -> str:
    """Get a sortable timestamp from an item."""
    ts = item.get("started_at") or item.get("created_at")
    return ts if ts else MIN_TIMESTAMP


def extract_display_info(tool_name: str, arguments: str | None) -> str | None:
    """Extract human-readable display info from tool arguments."""
    if not arguments:
        return None
    try:
        args = json.loads(arguments)

        # URL-based tools
        if tool_name in ("webfetch", "context7_query-docs"):
            url = args.get("url") or args.get("libraryId", "")
            return url[:80] if url else None

        # File-based tools
        if tool_name in ("read", "write", "edit", "glob"):
            path = args.get("filePath") or args.get("path", "")
            return path[:80] if path else None

        # Command-based tools
        if tool_name == "bash":
            cmd = args.get("command", "")
            return cmd[:60] if cmd else None

        # Search tools
        if tool_name == "grep":
            pattern = args.get("pattern", "")
            return f"/{pattern}/"[:40] if pattern else None

        # Task/delegation tools
        if tool_name == "task":
            desc = args.get("description", "")
            return desc[:50] if desc else None

    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return None


# =============================================================================
# Private Helper Functions for Tracing Tree
# =============================================================================


def _fetch_root_traces(conn: Any, start_date: Any) -> list:
    """Fetch root traces (user-initiated sessions) from database.

    Args:
        conn: Database connection
        start_date: Start date filter for traces

    Returns:
        List of root trace rows
    """
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


def _fetch_segment_traces(conn: Any, start_date: Any) -> dict:
    """Fetch segment traces and group them by session_id.

    Args:
        conn: Database connection
        start_date: Start date filter for traces

    Returns:
        Dictionary mapping session_id to list of segment rows
    """
    segment_rows = conn.execute(
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

    segments_by_session: dict = {}
    for row in segment_rows:
        session_id = row[1]
        if session_id not in segments_by_session:
            segments_by_session[session_id] = []
        segments_by_session[session_id].append(row)

    return segments_by_session


def _fetch_child_traces(conn: Any, start_date: Any) -> list:
    """Fetch child traces (delegations) from database.

    Args:
        conn: Database connection
        start_date: Start date filter for traces

    Returns:
        List of child trace rows
    """
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


def _collect_session_ids(root_rows: list, child_rows: list) -> tuple[set, set]:
    """Collect all session IDs from root and child traces.

    Args:
        root_rows: List of root trace rows
        child_rows: List of child trace rows

    Returns:
        Tuple of (all_session_ids, root_session_ids)
    """
    all_session_ids: set = set()
    root_session_ids: set = set()

    for row in root_rows:
        root_session_ids.add(row[1])
        all_session_ids.add(row[1])
        if row[13]:  # child_session_id
            all_session_ids.add(row[13])

    for row in child_rows:
        if row[13]:
            all_session_ids.add(row[13])

    return all_session_ids, root_session_ids


def _extract_tool_display_info(tool_name: str, args: str | None) -> str:
    """Extract display info from tool arguments for inline display.

    Args:
        tool_name: Name of the tool
        args: JSON string of tool arguments

    Returns:
        Human-readable display info string
    """
    if not args:
        return ""

    try:
        args_dict = json.loads(args)
        if tool_name == "bash":
            cmd = args_dict.get("command", "")
            return cmd[:100] + "..." if len(cmd) > 100 else cmd
        elif tool_name in ("read", "write", "edit"):
            return args_dict.get("filePath", args_dict.get("path", ""))
        elif tool_name == "glob":
            return args_dict.get("pattern", "")
        elif tool_name == "grep":
            return args_dict.get("pattern", "")
        elif tool_name == "task":
            return args_dict.get("subagent_type", "")
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    return ""


def _build_tools_by_session(
    conn: Any, all_session_ids: set, include_tools: bool
) -> dict:
    """Build dictionary of tools grouped by session_id.

    Args:
        conn: Database connection
        all_session_ids: Set of session IDs to fetch tools for
        include_tools: Whether to include tools in output

    Returns:
        Dictionary mapping session_id to list of tool dicts
    """
    tools_by_session: dict = {}

    if not include_tools or not all_session_ids:
        return tools_by_session

    placeholders = ",".join(["?" for _ in all_session_ids])
    tool_rows = conn.execute(
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
        list(all_session_ids),
    ).fetchall()

    for row in tool_rows:
        session_id = row[1]
        if session_id not in tools_by_session:
            tools_by_session[session_id] = []

        display_info = _extract_tool_display_info(row[2], row[4])

        tools_by_session[session_id].append(
            {
                "id": row[0],
                "node_type": "tool",
                "tool_name": row[2],
                "status": row[3],
                "display_info": display_info,
                "created_at": row[5].isoformat() if row[5] else None,
                "duration_ms": row[6],
            }
        )

    return tools_by_session


def _fetch_subagent_tokens(conn: Any, start_date: Any) -> tuple[dict, list]:
    """Fetch subagent sessions and their token counts.

    Args:
        conn: Database connection
        start_date: Start date filter

    Returns:
        Tuple of (subagent_tokens dict, subagent_by_time list)
    """
    subagent_sessions = conn.execute(
        """
        SELECT 
            id,
            title,
            created_at
        FROM sessions
        WHERE title LIKE '%subagent)%'
          AND created_at >= ?
        ORDER BY created_at ASC
        """,
        [start_date],
    ).fetchall()

    subagent_tokens: dict = {}
    if subagent_sessions:
        subagent_ids = [s[0] for s in subagent_sessions]
        sa_placeholders = ",".join(["?" for _ in subagent_ids])
        token_rows = conn.execute(
            f"""
            SELECT 
                session_id,
                COALESCE(SUM(tokens_input), 0) as tokens_in,
                COALESCE(SUM(tokens_output), 0) as tokens_out,
                COALESCE(SUM(tokens_cache_read), 0) as cache_read
            FROM messages
            WHERE session_id IN ({sa_placeholders})
            GROUP BY session_id
            """,
            subagent_ids,
        ).fetchall()
        for trow in token_rows:
            subagent_tokens[trow[0]] = {
                "tokens_in": trow[1],
                "tokens_out": trow[2],
                "cache_read": trow[3],
            }

    # Build index of subagent sessions by (timestamp, agent_type)
    subagent_by_time: list = []
    for sa_row in subagent_sessions:
        sa_id, sa_title, sa_created = sa_row
        match = re.search(r"@(\w+)\s+subagent", sa_title or "")
        if match and sa_created:
            agent_type = match.group(1)
            subagent_by_time.append(
                {
                    "session_id": sa_id,
                    "agent_type": agent_type,
                    "created_at": sa_created,
                    "tokens": subagent_tokens.get(sa_id, {}),
                }
            )

    return subagent_tokens, subagent_by_time


def _match_delegation_tokens(
    delegation_start: Any,
    delegation_agent: str,
    delegation_tokens: dict,
    subagent_by_time: list,
) -> tuple[dict, str | None]:
    """Match delegation with subagent session to get tokens.

    Args:
        delegation_start: Start timestamp of delegation
        delegation_agent: Agent type of delegation
        delegation_tokens: Current token dict
        subagent_by_time: List of subagent sessions with timestamps

    Returns:
        Tuple of (updated tokens dict, matched session_id or None)
    """
    if delegation_tokens.get("tokens_in") or not delegation_start:
        return delegation_tokens, None

    for sa in subagent_by_time:
        if sa["agent_type"] == delegation_agent:
            time_diff = abs((sa["created_at"] - delegation_start).total_seconds())
            if time_diff < 5:
                return {
                    "tokens_in": sa["tokens"].get("tokens_in"),
                    "tokens_out": sa["tokens"].get("tokens_out"),
                    "cache_read": sa["tokens"].get("cache_read"),
                }, sa["session_id"]

    return delegation_tokens, None


def _build_children_by_parent(
    child_rows: list,
    tools_by_session: dict,
    subagent_by_time: list,
    include_tools: bool,
) -> dict:
    """Build dictionary mapping parent trace IDs to their children.

    Args:
        child_rows: List of child trace rows
        tools_by_session: Dictionary of tools by session
        subagent_by_time: List of subagent sessions with timestamps
        include_tools: Whether to include tools

    Returns:
        Dictionary mapping parent_trace_id to list of child dicts
    """
    children_by_parent: dict = {}

    for row in child_rows:
        parent_id = row[2]
        if parent_id not in children_by_parent:
            children_by_parent[parent_id] = []

        child_session_id = row[13]
        child_tools = (
            tools_by_session.get(child_session_id, []) if include_tools else []
        )

        delegation_start = row[5]
        delegation_agent = row[4]
        delegation_tokens = {"tokens_in": row[8], "tokens_out": row[9]}

        matched_tokens, matched_session = _match_delegation_tokens(
            delegation_start, delegation_agent, delegation_tokens, subagent_by_time
        )
        if matched_session:
            child_session_id = matched_session
            delegation_tokens = matched_tokens

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
                "children": child_tools.copy(),
            }
        )

    return children_by_parent


def _fetch_messages_for_exchanges(conn: Any, root_session_ids: set) -> list:
    """Fetch all messages for root sessions to build exchanges.

    Args:
        conn: Database connection
        root_session_ids: Set of root session IDs

    Returns:
        List of message rows
    """
    if not root_session_ids:
        return []

    placeholders = ",".join(["?" for _ in root_session_ids])
    return conn.execute(
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
        list(root_session_ids),
    ).fetchall()


def _build_tools_by_message(
    conn: Any, root_session_ids: set, include_tools: bool
) -> dict:
    """Build dictionary of tools grouped by message_id.

    Args:
        conn: Database connection
        root_session_ids: Set of root session IDs
        include_tools: Whether to include tools

    Returns:
        Dictionary mapping message_id to list of tool dicts
    """
    tools_by_message: dict = {}

    if not include_tools or not root_session_ids:
        return tools_by_message

    placeholders = ",".join(["?" for _ in root_session_ids])
    tool_rows = conn.execute(
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
        list(root_session_ids),
    ).fetchall()

    for trow in tool_rows:
        msg_id = trow[2]
        if msg_id:
            if msg_id not in tools_by_message:
                tools_by_message[msg_id] = []

            tool_name = trow[3]
            arguments = trow[5]
            display_info = extract_display_info(tool_name, arguments)

            tools_by_message[msg_id].append(
                {
                    "trace_id": f"tool_{trow[0]}",
                    "session_id": trow[1],
                    "node_type": "tool",
                    "tool_name": tool_name,
                    "tool_status": trow[4],
                    "arguments": arguments,
                    "display_info": display_info,
                    "started_at": trow[6].isoformat() if trow[6] else None,
                    "duration_ms": trow[7],
                    "result_summary": trow[8],
                    "children": [],
                }
            )

    return tools_by_message


def _build_segment_timeline(segments_by_session: dict) -> dict:
    """Build segment timeline per session for agent detection.

    Args:
        segments_by_session: Dictionary of segments by session

    Returns:
        Dictionary mapping session_id to sorted list of (timestamp, agent) tuples
    """
    segment_timeline: dict = {}
    for session_id, seg_list in segments_by_session.items():
        timeline = []
        for seg_row in seg_list:
            seg_ts = seg_row[4]
            seg_agent = seg_row[3]
            if seg_ts and seg_agent:
                timeline.append((seg_ts, seg_agent))
        timeline.sort(key=lambda x: x[0])
        segment_timeline[session_id] = timeline
    return segment_timeline


def _get_initial_agents(conn: Any, root_session_ids: set) -> dict:
    """Get initial agent type from root traces.

    Args:
        conn: Database connection
        root_session_ids: Set of root session IDs

    Returns:
        Dictionary mapping session_id to initial agent type
    """
    if not root_session_ids:
        return {}

    placeholders = ",".join(["?" for _ in root_session_ids])
    root_agent_rows = conn.execute(
        f"""
        SELECT session_id, subagent_type, started_at
        FROM agent_traces
        WHERE session_id IN ({placeholders})
          AND trace_id LIKE 'root_%'
          AND trace_id NOT LIKE '%_seg%'
        """,
        list(root_session_ids),
    ).fetchall()

    initial_agent: dict = {}
    for arow in root_agent_rows:
        initial_agent[arow[0]] = arow[1]

    return initial_agent


def _create_agent_at_time_getter(
    initial_agent: dict, segment_timeline: dict
) -> Callable[[str, Any], str]:
    """Create a closure function to get active agent at a given timestamp.

    Args:
        initial_agent: Dictionary of initial agents by session
        segment_timeline: Dictionary of segment timelines by session

    Returns:
        Function that returns agent type for a session at a given time
    """

    def get_agent_at_time(session_id: str, timestamp: Any) -> str:
        """Get the active agent type at a given timestamp."""
        agent = initial_agent.get(session_id, "assistant")
        timeline = segment_timeline.get(session_id, [])
        for seg_ts, seg_agent in timeline:
            if timestamp >= seg_ts:
                agent = seg_agent
            else:
                break
        return agent

    return get_agent_at_time


def _build_user_exchange(
    msg_id: str,
    session_id: str,
    created_at: Any,
    content: str,
    msg_agent: str | None,
    get_agent_at_time: Callable[[str, Any], str],
) -> dict:
    """Build a user exchange node.

    Args:
        msg_id: Message ID
        session_id: Session ID
        created_at: Created timestamp
        content: Message content
        msg_agent: Agent from message
        get_agent_at_time: Function to get agent at timestamp

    Returns:
        User exchange dictionary
    """
    agent_type = msg_agent or (
        get_agent_at_time(session_id, created_at) if created_at else "assistant"
    )
    prompt_preview = content[:500] if content else ""

    return {
        "trace_id": f"exchange_{msg_id}",
        "session_id": session_id,
        "node_type": "user_turn",
        "parent_agent": "user",
        "subagent_type": agent_type,
        "started_at": created_at.isoformat() if created_at else None,
        "prompt_input": prompt_preview,
        "children": [],
        "tokens_in": None,
        "tokens_out": None,
        "cache_read": None,
    }


def _build_exchanges_from_messages(
    all_msg_rows: list,
    tools_by_message: dict,
    get_agent_at_time: Callable[[str, Any], str],
) -> dict:
    """Build exchanges dictionary from message rows.

    Args:
        all_msg_rows: List of message rows
        tools_by_message: Dictionary of tools by message
        get_agent_at_time: Function to get agent at timestamp

    Returns:
        Dictionary mapping session_id to list of exchange dicts
    """
    exchanges_by_session: dict = {}
    current_user_msg = None

    for row in all_msg_rows:
        msg_id = row[0]
        session_id = row[1]
        created_at = row[2]
        role = row[3]
        msg_agent = row[4]
        content = row[5] or ""
        tokens_input = row[6]
        tokens_output = row[7]
        tokens_cache = row[8]

        if role == "user":
            current_user_msg = _build_user_exchange(
                msg_id, session_id, created_at, content, msg_agent, get_agent_at_time
            )

            if session_id not in exchanges_by_session:
                exchanges_by_session[session_id] = []
            exchanges_by_session[session_id].append(current_user_msg)

        elif role == "assistant" and current_user_msg:
            msg_tools = tools_by_message.get(msg_id, [])
            if msg_tools:
                current_user_msg["children"].extend(msg_tools)

            current_user_msg["tokens_in"] = tokens_input
            current_user_msg["tokens_out"] = tokens_output
            current_user_msg["cache_read"] = tokens_cache

            if msg_agent and msg_agent != current_user_msg.get("subagent_type"):
                current_user_msg["subagent_type"] = msg_agent

    return exchanges_by_session


def _fetch_tokens_by_session(conn: Any, root_session_ids: set) -> dict:
    """Fetch aggregated tokens per session.

    Args:
        conn: Database connection
        root_session_ids: Set of root session IDs

    Returns:
        Dictionary mapping session_id to token counts
    """
    if not root_session_ids:
        return {}

    placeholders = ",".join(["?" for _ in root_session_ids])
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
        list(root_session_ids),
    ).fetchall()

    tokens_by_session: dict = {}
    for trow in token_rows:
        tokens_by_session[trow[0]] = {
            "tokens_in": trow[1],
            "tokens_out": trow[2],
            "cache_read": trow[3],
        }

    return tokens_by_session


def _attach_delegations_to_exchanges(
    session_exchanges: list, agent_children: list
) -> list:
    """Attach delegation children to their parent exchanges.

    Args:
        session_exchanges: List of exchanges for a session
        agent_children: List of delegation children

    Returns:
        Updated agent_children list (empty if all attached to exchanges)
    """
    if not agent_children:
        return agent_children

    sorted_exchanges = sorted(
        session_exchanges,
        key=lambda x: x.get("started_at") or "",
    )

    for delegation in agent_children:
        deleg_start = delegation.get("started_at") or ""

        parent_exchange = None
        for ex in sorted_exchanges:
            ex_start = ex.get("started_at") or ""
            if ex_start <= deleg_start:
                parent_exchange = ex
            else:
                break

        if parent_exchange:
            if "children" not in parent_exchange:
                parent_exchange["children"] = []
            parent_exchange["children"].append(delegation)
            parent_exchange["children"].sort(key=get_sort_key)
        else:
            session_exchanges.append(delegation)

    return []  # All delegations attached


def _calculate_exchange_durations(session_exchanges: list, session_end: Any) -> None:
    """Calculate duration for each exchange based on next exchange start.

    Args:
        session_exchanges: List of exchanges to update (modified in place)
        session_end: Session end timestamp
    """
    sorted_for_duration = sorted(
        session_exchanges,
        key=lambda x: x.get("started_at") or "",
    )

    for i, ex in enumerate(sorted_for_duration):
        ex_start_str = ex.get("started_at")
        if not ex_start_str:
            continue

        ended_at_str = _calculate_exchange_end_time(
            ex, sorted_for_duration, i, session_end
        )

        ex["ended_at"] = ended_at_str

        if ex_start_str and ended_at_str:
            try:
                start_dt = datetime.fromisoformat(ex_start_str)
                end_dt = datetime.fromisoformat(ended_at_str)
                duration = int((end_dt - start_dt).total_seconds() * 1000)
                ex["duration_ms"] = duration
            except (ValueError, TypeError):
                pass


def _calculate_exchange_end_time(
    ex: dict, sorted_exchanges: list, index: int, session_end: Any
) -> str | None:
    """Calculate end time for a single exchange.

    Args:
        ex: Exchange dictionary
        sorted_exchanges: Sorted list of exchanges
        index: Index of current exchange
        session_end: Session end timestamp

    Returns:
        End time as ISO string or None
    """
    ended_at_str = None
    children = ex.get("children", [])

    # Try to get end time from children
    if children:
        for child in reversed(children):
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

    # Fall back to next exchange start
    if not ended_at_str and index + 1 < len(sorted_exchanges):
        next_start = sorted_exchanges[index + 1].get("started_at")
        if next_start:
            ended_at_str = next_start

    # Fall back to session end
    if not ended_at_str and session_end:
        ended_at_str = session_end.isoformat()

    return ended_at_str


def _build_recursive_children(
    children_by_parent: dict, parent_trace_id: str, depth: int = 0
) -> list:
    """Build recursive tree of children for a parent trace.

    Args:
        children_by_parent: Dictionary mapping parent ID to children
        parent_trace_id: Parent trace ID to get children for
        depth: Current recursion depth

    Returns:
        Sorted list of children with nested children
    """
    if depth > 10:
        return []
    children = children_by_parent.get(parent_trace_id, [])
    for child in children:
        nested_agents = _build_recursive_children(
            children_by_parent, child["trace_id"], depth + 1
        )
        child["children"].extend(nested_agents)
        child["children"].sort(key=get_sort_key)
    children.sort(key=get_sort_key)
    return children


def _build_session_node(
    row: tuple,
    agent_children: list,
    session_tokens: dict,
) -> dict:
    """Build a single session node for the tree.

    Args:
        row: Root trace row tuple
        agent_children: List of children (exchanges + delegations)
        session_tokens: Token counts for session

    Returns:
        Session node dictionary
    """
    session_id = row[1]
    trace_id = row[0]
    agent_type = row[3]

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

    def count_traces(node: dict) -> int:
        return 1 + sum(count_traces(c) for c in node.get("children", []))

    session["trace_count"] = count_traces(session) - 1

    return session


# =============================================================================
# Routes
# =============================================================================


@tracing_bp.route("/api/tracing/tree", methods=["GET"])
def get_tracing_tree():
    """Get hierarchical tracing tree for dashboard display.

    Returns sessions with their child traces and tools in a tree structure.
    All hierarchy logic is done in SQL, no client-side aggregation needed.

    Structure:
    - Session (user -> agent)
      - Agent trace (agent -> subagent)
        - Tool (bash, read, edit, etc.)
        - Tool ...
      - Agent trace ...
    """
    try:
        days = request.args.get("days", 30, type=int)
        include_tools = request.args.get("include_tools", "true").lower() == "true"

        with get_db_lock():
            db = get_analytics_db()
            conn = db.connect()
            start_date = datetime.now() - timedelta(days=days)

            # Step 1: Fetch all trace data
            root_rows = _fetch_root_traces(conn, start_date)
            segments_by_session = _fetch_segment_traces(conn, start_date)
            child_rows = _fetch_child_traces(conn, start_date)

            # Step 2: Collect session IDs and build tools
            all_session_ids, root_session_ids = _collect_session_ids(
                root_rows, child_rows
            )
            tools_by_session = _build_tools_by_session(
                conn, all_session_ids, include_tools
            )

            # Step 3: Fetch subagent tokens for delegations
            _, subagent_by_time = _fetch_subagent_tokens(conn, start_date)

            # Step 4: Build children lookup
            children_by_parent = _build_children_by_parent(
                child_rows, tools_by_session, subagent_by_time, include_tools
            )

            # Step 5: Build exchanges for root sessions
            exchanges_by_session: dict = {}
            tokens_by_session: dict = {}

            if root_session_ids:
                # Fetch messages and build tools by message
                all_msg_rows = _fetch_messages_for_exchanges(conn, root_session_ids)
                tools_by_message = _build_tools_by_message(
                    conn, root_session_ids, include_tools
                )

                # Build timeline and agent detection
                segment_timeline = _build_segment_timeline(segments_by_session)
                initial_agent = _get_initial_agents(conn, root_session_ids)
                get_agent_at_time = _create_agent_at_time_getter(
                    initial_agent, segment_timeline
                )

                # Build exchanges
                exchanges_by_session = _build_exchanges_from_messages(
                    all_msg_rows, tools_by_message, get_agent_at_time
                )

                # Fetch token aggregation
                tokens_by_session = _fetch_tokens_by_session(conn, root_session_ids)

            # Step 6: Build final session tree
            sessions = []
            for row in root_rows:
                trace_id = row[0]
                session_id = row[1]

                # Build recursive children from delegations
                agent_children = _build_recursive_children(children_by_parent, trace_id)

                # Add children from segments
                session_segments = segments_by_session.get(session_id, [])
                for seg_row in session_segments:
                    seg_trace_id = seg_row[0]
                    seg_children = _build_recursive_children(
                        children_by_parent, seg_trace_id
                    )
                    agent_children.extend(seg_children)

                # Get exchanges for this session
                session_exchanges = exchanges_by_session.get(session_id, [])

                if session_exchanges:
                    # Attach delegations to their parent exchanges
                    agent_children = _attach_delegations_to_exchanges(
                        session_exchanges, agent_children
                    )

                    # Calculate duration for each exchange
                    _calculate_exchange_durations(session_exchanges, row[5])

                    # Merge exchanges into children
                    agent_children = session_exchanges + agent_children
                    agent_children.sort(key=get_sort_key)

                # Build session node
                session_tokens = tokens_by_session.get(session_id, {})
                session = _build_session_node(row, agent_children, session_tokens)
                sessions.append(session)

        return jsonify({"success": True, "data": sessions})
    except Exception as e:
        error(f"[API] Error getting tracing tree: {e}")
        import traceback

        error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500
