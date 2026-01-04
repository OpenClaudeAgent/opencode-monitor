"""
Delegations Routes - Agent delegation and conversation timeline endpoints.
"""

import json
from datetime import datetime, timedelta
from typing import Any

from flask import Blueprint, jsonify, request

from ...analytics import get_analytics_db
from ...utils.logger import error
from ._context import get_db_lock

delegations_bp = Blueprint("delegations", __name__)


# -----------------------------------------------------------------------------
# Private helpers for get_conversation_timeline
# -----------------------------------------------------------------------------


def _extract_tool_display_info(tool_name: str, arguments: str | None) -> dict[str, Any]:
    """Extract display info from tool arguments.

    Args:
        tool_name: Name of the tool (bash, read, write, etc.)
        arguments: JSON string of tool arguments

    Returns:
        Dict with display_info and optionally is_delegation flag
    """
    if not arguments:
        return {}

    try:
        args = json.loads(arguments)
        result: dict[str, Any] = {}

        if tool_name == "bash":
            result["display_info"] = args.get("command", "")[:150]
        elif tool_name in ("read", "write", "edit"):
            result["display_info"] = args.get("filePath", args.get("path", ""))
        elif tool_name == "glob":
            result["display_info"] = args.get("pattern", "")
        elif tool_name == "grep":
            result["display_info"] = args.get("pattern", "")
        elif tool_name == "task":
            result["display_info"] = args.get("subagent_type", "")
            result["is_delegation"] = True

        return result
    except (json.JSONDecodeError, TypeError, KeyError):
        return {}


def _build_part_from_row(row: tuple) -> dict[str, Any]:
    """Build a part dict from a database row.

    Args:
        row: Database row with part data

    Returns:
        Part dict with all fields
    """
    part = {
        "id": row[0],
        "type": row[2],
        "content": row[3][:500] if row[3] else None,
        "tool_name": row[4],
        "status": row[5],
        "arguments": row[6],
        "created_at": row[7].isoformat() if row[7] else None,
        "ended_at": row[8].isoformat() if row[8] else None,
        "duration_ms": row[9],
        "error": row[10],
    }

    # Extract display info for tools
    if part["tool_name"] and part["arguments"]:
        display_info = _extract_tool_display_info(part["tool_name"], part["arguments"])
        part.update(display_info)

    return part


def _build_parts_mapping(
    parts_rows: list[tuple],
) -> tuple[dict[str, list[dict]], list[dict]]:
    """Build message_id -> parts mapping and collect orphan parts.

    Args:
        parts_rows: List of part rows from database

    Returns:
        Tuple of (parts_by_message dict, orphan_parts list)
    """
    parts_by_message: dict[str, list[dict]] = {}
    orphan_parts: list[dict] = []

    for row in parts_rows:
        part = _build_part_from_row(row)
        msg_id = row[1]

        if msg_id:
            if msg_id not in parts_by_message:
                parts_by_message[msg_id] = []
            parts_by_message[msg_id].append(part)
        else:
            orphan_parts.append(part)

    return parts_by_message, orphan_parts


def _build_delegations_mapping(delegation_rows: list[tuple]) -> dict[str, dict]:
    """Build delegation mapping by timestamp.

    Args:
        delegation_rows: List of delegation rows from database

    Returns:
        Dict mapping timestamp -> delegation info
    """
    delegations_by_time: dict[str, dict] = {}

    for row in delegation_rows:
        created = row[3]
        if created:
            key = created.isoformat()[:19]
            delegations_by_time[key] = {
                "id": row[0],
                "child_agent": row[1],
                "child_session_id": row[2],
                "created_at": created.isoformat(),
            }

    return delegations_by_time


def _build_message_dict(
    row: tuple, parts_by_message: dict[str, list[dict]]
) -> dict[str, Any]:
    """Build a message dict from a database row.

    Args:
        row: Database row with message data
        parts_by_message: Mapping of message_id to parts

    Returns:
        Message dict with all fields including parts
    """
    msg_id = row[0]
    role = row[1]
    created_at = row[2]
    completed_at = row[3]
    tokens_in = row[4]
    tokens_out = row[5]
    msg_agent = row[6]

    msg_parts = parts_by_message.get(msg_id, [])

    # Get content from text parts
    text_content = ""
    for p in msg_parts:
        if p["type"] == "text" and p.get("content"):
            text_content += p["content"]

    return {
        "id": msg_id,
        "role": role,
        "agent": msg_agent,
        "content": text_content[:1000] if text_content else None,
        "created_at": created_at.isoformat() if created_at else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "parts": msg_parts,
    }


def _build_exchanges(
    message_rows: list[tuple], parts_by_message: dict[str, list[dict]]
) -> list[dict]:
    """Build exchanges from messages.

    An exchange is a user message paired with an assistant response.

    Args:
        message_rows: List of message rows from database
        parts_by_message: Mapping of message_id to parts

    Returns:
        List of exchange dicts
    """
    exchanges: list[dict] = []
    current_exchange: dict | None = None

    for row in message_rows:
        message = _build_message_dict(row, parts_by_message)
        role = message["role"]

        if role == "user":
            if current_exchange and current_exchange.get("user"):
                exchanges.append(current_exchange)
            current_exchange = {"user": message, "assistant": None}

        elif role == "assistant":
            if current_exchange:
                if current_exchange.get("assistant") is None:
                    current_exchange["assistant"] = message
                else:
                    current_exchange["assistant"]["parts"].extend(message["parts"])
            else:
                current_exchange = {"user": None, "assistant": message}

    if current_exchange:
        exchanges.append(current_exchange)

    return exchanges


def _associate_orphan_parts(
    exchanges: list[dict], orphan_parts: list[dict]
) -> list[dict]:
    """Associate orphan parts with assistant messages by timestamp.

    Parts without a message_id are matched to assistant messages
    based on their timestamp falling within the message's time range.

    Args:
        exchanges: List of exchanges
        orphan_parts: List of parts without message association

    Returns:
        Remaining orphan parts that couldn't be associated
    """
    if not orphan_parts:
        return orphan_parts

    remaining_orphans = orphan_parts[:]

    for exchange in exchanges:
        assistant = exchange.get("assistant")
        if not assistant:
            continue

        assistant_start = assistant.get("created_at")
        assistant_end = assistant.get("completed_at") or assistant_start

        if not assistant_start:
            continue

        for part in remaining_orphans[:]:
            part_time = part.get("created_at")
            if not part_time:
                continue

            if assistant_start <= part_time:
                if assistant_end is None or part_time <= assistant_end:
                    assistant["parts"].append(part)
                    remaining_orphans.remove(part)

    return remaining_orphans


def _build_session_dict(session_row: tuple, agent_type: str) -> dict[str, Any]:
    """Build session info dict from database row.

    Args:
        session_row: Database row with session data
        agent_type: Type of agent for this session

    Returns:
        Session info dict
    """
    return {
        "id": session_row[0],
        "title": session_row[1],
        "directory": session_row[2],
        "agent_type": agent_type,
        "created_at": session_row[3].isoformat() if session_row[3] else None,
        "updated_at": session_row[4].isoformat() if session_row[4] else None,
    }


@delegations_bp.route("/api/delegations", methods=["GET"])
def get_delegations():
    """Get agent delegations (parent-child session relationships)."""
    try:
        days = request.args.get("days", 30, type=int)
        limit = request.args.get("limit", 1000, type=int)

        with get_db_lock():
            db = get_analytics_db()
            conn = db.connect()

            start_date = datetime.now() - timedelta(days=days)

            rows = conn.execute(
                """
                SELECT 
                    id,
                    session_id,
                    parent_agent,
                    child_agent,
                    child_session_id,
                    created_at
                FROM delegations
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                [start_date, limit],
            ).fetchall()

            delegations = [
                {
                    "id": row[0],
                    "parent_session_id": row[1],
                    "parent_agent": row[2],
                    "child_agent": row[3],
                    "child_session_id": row[4],
                    "created_at": row[5].isoformat() if row[5] else None,
                }
                for row in rows
            ]

        return jsonify({"success": True, "data": delegations})
    except Exception as e:
        error(f"[API] Error getting delegations: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@delegations_bp.route("/api/tracing/conversation/<session_id>", methods=["GET"])
def get_conversation_timeline(session_id: str):
    """Get full conversation timeline for a session.

    Returns a hierarchical view of the conversation:
    - Session info (agent type, title)
    - Exchanges: user message -> assistant response with parts
    - Parts include: tools, text, delegations

    This is the main endpoint for the tracing dashboard.
    """
    try:
        include_delegations = (
            request.args.get("include_delegations", "true").lower() == "true"
        )

        with get_db_lock():
            db = get_analytics_db()
            conn = db.connect()

            # 1. Get session info
            session_row = conn.execute(
                """
                SELECT id, title, directory, created_at, updated_at
                FROM sessions
                WHERE id = ?
                """,
                [session_id],
            ).fetchone()

            if not session_row:
                return jsonify({"success": False, "error": "Session not found"}), 404

            # 2. Get agent type from first assistant message
            agent_row = conn.execute(
                """
                SELECT agent FROM messages
                WHERE session_id = ? AND role = 'assistant' AND agent IS NOT NULL
                ORDER BY created_at ASC
                LIMIT 1
                """,
                [session_id],
            ).fetchone()
            agent_type = agent_row[0] if agent_row else "assistant"

            # 3. Get all messages ordered by time
            message_rows = conn.execute(
                """
                SELECT id, role, created_at, completed_at, 
                       tokens_input, tokens_output, agent
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                [session_id],
            ).fetchall()

            # 4. Get all parts for this session with message association
            parts_rows = conn.execute(
                """
                SELECT id, message_id, part_type, content, tool_name, 
                       tool_status, arguments, created_at, ended_at, 
                       duration_ms, error_message
                FROM parts
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                [session_id],
            ).fetchall()

            # 5. Get delegations (task tool calls)
            delegation_rows: list = []
            if include_delegations:
                delegation_rows = conn.execute(
                    """
                    SELECT id, child_agent, child_session_id, created_at
                    FROM delegations
                    WHERE session_id = ?
                    ORDER BY created_at ASC
                    """,
                    [session_id],
                ).fetchall()

            # Build mappings using helpers
            parts_by_message, orphan_parts = _build_parts_mapping(parts_rows)
            delegations_by_time = _build_delegations_mapping(delegation_rows)

            # Build exchanges and associate orphan parts
            exchanges = _build_exchanges(message_rows, parts_by_message)
            remaining_orphans = _associate_orphan_parts(exchanges, orphan_parts)

            # Build final response
            response = {
                "session": _build_session_dict(session_row, agent_type),
                "exchanges": exchanges,
                "stats": {
                    "total_messages": len(message_rows),
                    "total_parts": len(parts_rows),
                    "total_exchanges": len(exchanges),
                    "orphan_parts": len(remaining_orphans),
                },
                "delegations": list(delegations_by_time.values()),
            }

        return jsonify({"success": True, "data": response})
    except Exception as e:
        import traceback

        error(f"[API] Error getting conversation: {e}")
        error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500
