"""
Tracing Routes - Agent trace tree and hierarchy endpoints.

This module contains the complex tracing tree endpoints that build
hierarchical views of agent traces, conversations, and tool usage.
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any

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
# Routes
# =============================================================================


@tracing_bp.route("/api/traces", methods=["GET"])
def get_traces():
    """Get flat list of agent traces (legacy endpoint)."""
    try:
        days = request.args.get("days", 30, type=int)
        limit = request.args.get("limit", 500, type=int)

        with get_db_lock():
            db = get_analytics_db()
            conn = db.connect()
            start_date = datetime.now() - timedelta(days=days)

            rows = conn.execute(
                """
                SELECT 
                    t.trace_id, t.session_id, t.parent_trace_id,
                    t.parent_agent, t.subagent_type,
                    t.started_at, t.ended_at, t.duration_ms,
                    t.tokens_in, t.tokens_out, t.status,
                    t.prompt_input, t.prompt_output
                FROM agent_traces t
                WHERE t.started_at >= ?
                ORDER BY t.started_at DESC
                LIMIT ?
                """,
                [start_date, limit],
            ).fetchall()

            traces = [
                {
                    "trace_id": row[0],
                    "session_id": row[1],
                    "parent_trace_id": row[2],
                    "parent_agent": row[3],
                    "subagent_type": row[4],
                    "started_at": row[5].isoformat() if row[5] else None,
                    "ended_at": row[6].isoformat() if row[6] else None,
                    "duration_ms": row[7],
                    "tokens_in": row[8],
                    "tokens_out": row[9],
                    "status": row[10],
                    "prompt_input": row[11],
                    "prompt_output": row[12],
                }
                for row in rows
            ]

        return jsonify({"success": True, "data": traces})
    except Exception as e:
        error(f"[API] Error getting traces: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


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

            # Step 1: Get root traces (user-initiated sessions)
            root_rows = conn.execute(
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

            # Step 1b: Get segment traces
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

            # Group segments by session_id
            segments_by_session: dict = {}
            for row in segment_rows:
                session_id = row[1]
                if session_id not in segments_by_session:
                    segments_by_session[session_id] = []
                segments_by_session[session_id].append(row)

            # Step 2: Get all child traces (delegations)
            child_rows = conn.execute(
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

            # Step 3: Get tools for all sessions (if requested)
            tools_by_session: dict = {}
            all_session_ids = set()
            root_session_ids = set()

            for row in root_rows:
                root_session_ids.add(row[1])
                all_session_ids.add(row[1])
                if row[13]:  # child_session_id
                    all_session_ids.add(row[13])

            for row in child_rows:
                if row[13]:
                    all_session_ids.add(row[13])

            if include_tools and all_session_ids:
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

                    args = row[4]
                    display_info = ""
                    if args:
                        try:
                            args_dict = json.loads(args)
                            tool_name = row[2]
                            if tool_name == "bash":
                                cmd = args_dict.get("command", "")
                                display_info = (
                                    cmd[:100] + "..." if len(cmd) > 100 else cmd
                                )
                            elif tool_name in ("read", "write", "edit"):
                                display_info = args_dict.get(
                                    "filePath", args_dict.get("path", "")
                                )
                            elif tool_name == "glob":
                                display_info = args_dict.get("pattern", "")
                            elif tool_name == "grep":
                                display_info = args_dict.get("pattern", "")
                            elif tool_name == "task":
                                display_info = args_dict.get("subagent_type", "")
                        except (json.JSONDecodeError, TypeError, AttributeError):
                            pass

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

            # Step 3b: Find subagent sessions to get tokens for delegations
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

            # Build children lookup
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

                if not delegation_tokens["tokens_in"] and delegation_start:
                    for sa in subagent_by_time:
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
                        "children": child_tools.copy(),
                    }
                )

            # Step 4: Get user messages (exchanges) for root sessions
            exchanges_by_session: dict = {}
            if root_session_ids:
                placeholders = ",".join(["?" for _ in root_session_ids])

                all_msg_rows = conn.execute(
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

                tools_by_message: dict = {}
                if include_tools:
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
                                    "started_at": trow[6].isoformat()
                                    if trow[6]
                                    else None,
                                    "duration_ms": trow[7],
                                    "result_summary": trow[8],
                                    "children": [],
                                }
                            )

                # Build segment timeline per session
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

                # Get initial agent from root trace
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

                # Build exchanges
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
                        agent_type = msg_agent or (
                            get_agent_at_time(session_id, created_at)
                            if created_at
                            else "assistant"
                        )
                        prompt_preview = content[:500] if content else ""

                        current_user_msg = {
                            "trace_id": f"exchange_{msg_id}",
                            "session_id": session_id,
                            "node_type": "user_turn",
                            "parent_agent": "user",
                            "subagent_type": agent_type,
                            "started_at": created_at.isoformat()
                            if created_at
                            else None,
                            "prompt_input": prompt_preview,
                            "children": [],
                            "tokens_in": None,
                            "tokens_out": None,
                            "cache_read": None,
                        }

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

                        if msg_agent and msg_agent != current_user_msg.get(
                            "subagent_type"
                        ):
                            current_user_msg["subagent_type"] = msg_agent

                # Get token aggregation per session
                tokens_by_session: dict = {}
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
                for trow in token_rows:
                    tokens_by_session[trow[0]] = {
                        "tokens_in": trow[1],
                        "tokens_out": trow[2],
                        "cache_read": trow[3],
                    }

            # Build recursive tree
            def build_children(parent_trace_id: str, depth: int = 0) -> list:
                if depth > 10:
                    return []
                children = children_by_parent.get(parent_trace_id, [])
                for child in children:
                    nested_agents = build_children(child["trace_id"], depth + 1)
                    child["children"].extend(nested_agents)
                    child["children"].sort(key=get_sort_key)
                children.sort(key=get_sort_key)
                return children

            # Build final tree
            sessions = []
            for row in root_rows:
                trace_id = row[0]
                agent_type = row[3]

                agent_children = build_children(trace_id)

                session_segments = segments_by_session.get(row[1], [])
                for seg_row in session_segments:
                    seg_trace_id = seg_row[0]
                    seg_children = build_children(seg_trace_id)
                    agent_children.extend(seg_children)

                session_id = row[1]
                session_exchanges = exchanges_by_session.get(session_id, [])

                if session_exchanges:
                    if agent_children:
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

                        agent_children = []

                    # Calculate duration for each exchange
                    sorted_for_duration = sorted(
                        session_exchanges,
                        key=lambda x: x.get("started_at") or "",
                    )
                    session_end = row[5]

                    for i, ex in enumerate(sorted_for_duration):
                        ex_start_str = ex.get("started_at")
                        if not ex_start_str:
                            continue

                        ended_at_str = None
                        children = ex.get("children", [])
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
                                        end_dt = start_dt + timedelta(
                                            milliseconds=child_duration
                                        )
                                        ended_at_str = end_dt.isoformat()
                                        break
                                    except (ValueError, TypeError):
                                        pass

                        if not ended_at_str and i + 1 < len(sorted_for_duration):
                            next_start = sorted_for_duration[i + 1].get("started_at")
                            if next_start:
                                ended_at_str = next_start

                        if not ended_at_str and session_end:
                            ended_at_str = session_end.isoformat()

                        ex["ended_at"] = ended_at_str

                        if ex_start_str and ended_at_str:
                            try:
                                start_dt = datetime.fromisoformat(ex_start_str)
                                end_dt = datetime.fromisoformat(ended_at_str)
                                duration = int(
                                    (end_dt - start_dt).total_seconds() * 1000
                                )
                                ex["duration_ms"] = duration
                            except (ValueError, TypeError):
                                pass

                    agent_children = session_exchanges + agent_children
                    agent_children.sort(key=get_sort_key)

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

                def count_traces(node: dict) -> int:
                    return 1 + sum(count_traces(c) for c in node.get("children", []))

                session["trace_count"] = count_traces(session) - 1
                sessions.append(session)

        return jsonify({"success": True, "data": sessions})
    except Exception as e:
        error(f"[API] Error getting tracing tree: {e}")
        import traceback

        error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@tracing_bp.route("/api/tracing/tree/v2", methods=["GET"])
def get_tracing_tree_v2():
    """Get hierarchical tracing tree based on conversations.

    This endpoint builds the tree from messages (conversations)
    as the primary source, not agent_traces.

    Structure:
    - Session (project root)
      - Conversation (user -> agent: "message preview")
        - Tool (bash, read, edit, etc.)
        - Delegation (agent -> subagent)
          - [recursive: subagent's conversations]

    Query params:
    - days: int (default: 30)
    - include_tools: bool (default: true)
    - max_depth: int (default: 5)
    """
    try:
        days = request.args.get("days", 30, type=int)
        include_tools = request.args.get("include_tools", "true").lower() == "true"
        max_depth = min(request.args.get("max_depth", 5, type=int), 10)

        with get_db_lock():
            db = get_analytics_db()
            conn = db.connect()
            start_date = datetime.now() - timedelta(days=days)

            # Step 1: Get root sessions (no parent_id)
            root_sessions = conn.execute(
                """
                SELECT 
                    s.id,
                    s.title,
                    s.directory,
                    s.created_at,
                    s.updated_at,
                    s.duration_ms,
                    s.project_name
                FROM sessions s
                WHERE s.parent_id IS NULL
                  AND s.created_at >= ?
                ORDER BY s.created_at DESC
                """,
                [start_date],
            ).fetchall()

            def build_session_tree(session_id: str, depth: int = 0) -> dict | None:
                """Build tree for a session recursively."""
                if depth > max_depth:
                    return None

                session_row = conn.execute(
                    """
                    SELECT id, title, directory, created_at, 
                           updated_at, duration_ms, project_name
                    FROM sessions WHERE id = ?
                    """,
                    [session_id],
                ).fetchone()

                if not session_row:
                    return None

                messages = conn.execute(
                    """
                    SELECT 
                        m.id,
                        m.role,
                        m.agent,
                        m.created_at,
                        m.completed_at,
                        m.tokens_input,
                        m.tokens_output
                    FROM messages m
                    WHERE m.session_id = ?
                    ORDER BY m.created_at ASC
                    """,
                    [session_id],
                ).fetchall()

                conversations = []
                current_user_msg = None
                conv_num = 0

                for msg in messages:
                    msg_id, role, agent, created, completed, tok_in, tok_out = msg

                    if role == "user":
                        current_user_msg = {
                            "id": msg_id,
                            "created_at": created,
                            "agent": agent,
                        }
                    elif role == "assistant" and current_user_msg:
                        conv_num += 1
                        conv = {
                            "id": f"conv_{session_id}_{conv_num}",
                            "node_type": "conversation",
                            "user_message_id": current_user_msg["id"],
                            "assistant_message_id": msg_id,
                            "agent": agent or "assistant",
                            "started_at": current_user_msg["created_at"].isoformat()
                            if current_user_msg["created_at"]
                            else None,
                            "ended_at": completed.isoformat() if completed else None,
                            "tokens_in": tok_in or 0,
                            "tokens_out": tok_out or 0,
                            "children": [],
                        }

                        preview_row = conn.execute(
                            """
                            SELECT content FROM parts
                            WHERE message_id = ? AND part_type = 'text'
                            LIMIT 1
                            """,
                            [current_user_msg["id"]],
                        ).fetchone()

                        preview = ""
                        if preview_row and preview_row[0]:
                            preview = preview_row[0][:80]
                            if len(preview_row[0]) > 80:
                                preview += "..."

                        conv["label"] = f"user -> {agent or 'assistant'}"
                        if preview:
                            conv["label"] += f': "{preview}"'
                        conv["message_preview"] = preview

                        # Get tools for this assistant message
                        if include_tools:
                            tools = conn.execute(
                                """
                                SELECT 
                                    p.id,
                                    p.tool_name,
                                    p.tool_status,
                                    p.created_at,
                                    p.ended_at,
                                    p.duration_ms,
                                    p.arguments
                                FROM parts p
                                WHERE p.message_id = ?
                                  AND p.part_type = 'tool'
                                  AND p.tool_name IS NOT NULL
                                  AND p.tool_name != 'task'
                                ORDER BY p.created_at ASC
                                """,
                                [msg_id],
                            ).fetchall()

                            for tool in tools:
                                (
                                    t_id,
                                    t_name,
                                    t_status,
                                    t_created,
                                    t_ended,
                                    t_dur,
                                    t_args,
                                ) = tool

                                display_info = ""
                                if t_args:
                                    try:
                                        args = (
                                            json.loads(t_args)
                                            if isinstance(t_args, str)
                                            else t_args
                                        )
                                        if t_name in ("read", "edit", "write"):
                                            display_info = args.get("filePath", "")
                                            if display_info and len(display_info) > 40:
                                                display_info = (
                                                    "..." + display_info[-37:]
                                                )
                                        elif t_name == "bash":
                                            cmd = args.get("command", "")
                                            display_info = (
                                                cmd[:50] + "..."
                                                if len(cmd) > 50
                                                else cmd
                                            )
                                        elif t_name in ("glob", "grep"):
                                            display_info = args.get("pattern", "")
                                    except (json.JSONDecodeError, TypeError):
                                        pass

                                conv["children"].append(
                                    {
                                        "id": t_id,
                                        "node_type": "tool",
                                        "tool_name": t_name,
                                        "label": f"{t_name}: {display_info}"
                                        if display_info
                                        else t_name,
                                        "status": t_status or "completed",
                                        "started_at": t_created.isoformat()
                                        if t_created
                                        else None,
                                        "ended_at": t_ended.isoformat()
                                        if t_ended
                                        else None,
                                        "duration_ms": t_dur or 0,
                                    }
                                )

                        # Get delegations (task tool)
                        delegations = conn.execute(
                            """
                            SELECT 
                                p.id,
                                p.tool_status,
                                p.created_at,
                                p.ended_at,
                                p.duration_ms,
                                p.arguments
                            FROM parts p
                            WHERE p.message_id = ?
                              AND p.tool_name = 'task'
                            ORDER BY p.created_at ASC
                            """,
                            [msg_id],
                        ).fetchall()

                        for deleg in delegations:
                            d_id, d_status, d_created, d_ended, d_dur, d_args = deleg

                            subagent_type = ""
                            prompt_preview = ""

                            if d_args:
                                try:
                                    args = (
                                        json.loads(d_args)
                                        if isinstance(d_args, str)
                                        else d_args
                                    )
                                    subagent_type = args.get("subagent_type", "agent")
                                    prompt_preview = args.get("prompt", "")[:80]
                                    if len(args.get("prompt", "")) > 80:
                                        prompt_preview += "..."
                                except (json.JSONDecodeError, TypeError):
                                    pass

                            trace_row = conn.execute(
                                """
                                SELECT child_session_id, tokens_in, tokens_out, status
                                FROM agent_traces
                                WHERE trace_id = ? OR (
                                    session_id = ? 
                                    AND subagent_type = ?
                                    AND started_at >= ?
                                )
                                ORDER BY started_at ASC
                                LIMIT 1
                                """,
                                [d_id, session_id, subagent_type, d_created],
                            ).fetchone()

                            deleg_node = {
                                "id": d_id,
                                "node_type": "delegation",
                                "label": f"{agent or 'assistant'} -> {subagent_type}",
                                "subagent_type": subagent_type,
                                "prompt_preview": prompt_preview,
                                "status": d_status or "completed",
                                "started_at": d_created.isoformat()
                                if d_created
                                else None,
                                "ended_at": d_ended.isoformat() if d_ended else None,
                                "duration_ms": d_dur or 0,
                                "tokens_in": trace_row[1] if trace_row else 0,
                                "tokens_out": trace_row[2] if trace_row else 0,
                                "children": [],
                            }

                            if trace_row and trace_row[0]:
                                child_session_id = trace_row[0]
                                child_tree = build_session_tree(
                                    child_session_id, depth + 1
                                )
                                if child_tree:
                                    deleg_node["children"] = child_tree.get(
                                        "children", []
                                    )

                            conv["children"].append(deleg_node)

                        conversations.append(conv)
                        current_user_msg = None

                total_tokens_in = sum(c.get("tokens_in", 0) for c in conversations)
                total_tokens_out = sum(c.get("tokens_out", 0) for c in conversations)

                return {
                    "id": session_row[0],
                    "node_type": "session",
                    "label": session_row[6] or session_row[1] or "Session",
                    "title": session_row[1],
                    "directory": session_row[2],
                    "started_at": session_row[3].isoformat()
                    if session_row[3]
                    else None,
                    "ended_at": session_row[4].isoformat() if session_row[4] else None,
                    "duration_ms": session_row[5] or 0,
                    "tokens_in": total_tokens_in,
                    "tokens_out": total_tokens_out,
                    "status": "completed",
                    "children": conversations,
                }

            tree = []
            for session in root_sessions:
                session_tree = build_session_tree(session[0])
                if session_tree:
                    tree.append(session_tree)

        return jsonify(
            {
                "success": True,
                "data": tree,
                "meta": {
                    "version": "v2",
                    "root_count": len(tree),
                    "days": days,
                    "include_tools": include_tools,
                    "max_depth": max_depth,
                },
            }
        )

    except Exception as e:
        import traceback

        error(f"[API] Error in tracing tree v2: {e}")
        error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500
