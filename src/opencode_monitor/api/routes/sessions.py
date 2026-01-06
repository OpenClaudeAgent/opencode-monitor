"""
Sessions Routes - Session listing and detail endpoints.
"""

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from ...analytics import get_analytics_db
from ...utils.logger import error
from ._context import get_db_lock, get_service

sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.route("/api/sessions", methods=["GET"])
def get_sessions():
    """Get list of sessions for tree view."""
    try:
        days = request.args.get("days", 30, type=int)
        limit = request.args.get("limit", 100, type=int)

        with get_db_lock():
            db = get_analytics_db()
            conn = db.connect()

            # Calculate start date
            start_date = datetime.now() - timedelta(days=days)

            rows = conn.execute(
                """
                SELECT 
                    id,
                    title,
                    directory,
                    created_at,
                    updated_at
                FROM sessions
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                [start_date, limit],
            ).fetchall()

            sessions = [
                {
                    "id": row[0],
                    "title": row[1],
                    "directory": row[2],
                    "created_at": row[3].isoformat() if row[3] else None,
                    "updated_at": row[4].isoformat() if row[4] else None,
                }
                for row in rows
            ]

        return jsonify({"success": True, "data": sessions})
    except Exception as e:
        error(f"[API] Error getting sessions: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/summary", methods=["GET"])
def get_session_summary(session_id: str):
    """Get session summary."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_summary(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session summary: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/tokens", methods=["GET"])
def get_session_tokens(session_id: str):
    """Get session token details."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_tokens(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session tokens: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/tools", methods=["GET"])
def get_session_tools(session_id: str):
    """Get session tool details."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_tools(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session tools: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/files", methods=["GET"])
def get_session_files(session_id: str):
    """Get session file operations."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_files(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session files: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/agents", methods=["GET"])
def get_session_agents(session_id: str):
    """Get session agents."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_agents(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session agents: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/timeline", methods=["GET"])
def get_session_timeline(session_id: str):
    """Get session timeline events."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_timeline(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session timeline: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/prompts", methods=["GET"])
def get_session_prompts(session_id: str):
    """Get session prompts (first user prompt + last response)."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_prompts(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session prompts: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/messages", methods=["GET"])
def get_session_messages(session_id: str):
    """Get all messages with content for a session."""
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_messages(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session messages: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ===== Plan 34: Enriched Parts Endpoints =====


@sessions_bp.route("/api/session/<session_id>/reasoning", methods=["GET"])
def get_session_reasoning(session_id: str):
    """Get session reasoning parts (agent thought process).

    Returns the internal reasoning/thinking of the agent with
    Anthropic cryptographic signatures when available.
    """
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_reasoning(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session reasoning: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/steps", methods=["GET"])
def get_session_steps(session_id: str):
    """Get session step events with precise token counts and costs.

    Step events capture the beginning and end of each agent step,
    with accurate token counts and costs from step-finish events.
    """
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_steps(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session steps: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/git-history", methods=["GET"])
def get_session_git_history(session_id: str):
    """Get session git patches history.

    Returns all git commits made during the session with their
    affected files. Useful for understanding code changes.
    """
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_git_history(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session git history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@sessions_bp.route("/api/session/<session_id>/precise-cost", methods=["GET"])
def get_session_precise_cost(session_id: str):
    """Get session cost calculated from step-finish events.

    This provides more accurate cost data than message-level estimates
    by using the actual cost values from step-finish events.
    """
    try:
        with get_db_lock():
            service = get_service()
            data = service.get_session_precise_cost(session_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        error(f"[API] Error getting session precise cost: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
