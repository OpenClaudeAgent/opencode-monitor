"""
Analytics API Server - Flask server for dashboard data access.

Runs in the menubar process (the only DuckDB writer) and serves
data to the dashboard via HTTP on localhost.

This architecture solves DuckDB's multi-process concurrency limitations.
"""

import threading
from datetime import datetime, timedelta
from typing import Optional
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from ..analytics import TracingDataService, get_analytics_db
from ..utils.logger import info, error, debug

# API Configuration
API_HOST = "127.0.0.1"
API_PORT = 19876  # High port, unlikely to conflict


class AnalyticsAPIServer:
    """Flask server for analytics API.

    Runs in a background thread within the menubar process.
    Provides HTTP endpoints for the dashboard to fetch data.

    Uses a lock to serialize DuckDB access since DuckDB doesn't
    handle concurrent access well from multiple threads.
    """

    def __init__(self, host: str = API_HOST, port: int = API_PORT):
        """Initialize the API server.

        Args:
            host: Host to bind to (default: localhost only)
            port: Port to listen on
        """
        self._host = host
        self._port = port
        self._app = Flask(__name__)
        self._server: Optional[make_server] = None
        self._thread: Optional[threading.Thread] = None
        self._service: Optional[TracingDataService] = None
        self._db_lock = threading.Lock()  # Lock for DuckDB access

        # Register routes
        self._register_routes()

    def _get_service(self) -> TracingDataService:
        """Lazy load the tracing service (uses singleton DB)."""
        if self._service is None:
            self._service = TracingDataService()
        return self._service

    def _with_db_lock(self, func):
        """Execute a function with the DB lock held."""
        with self._db_lock:
            return func()

    def _register_routes(self) -> None:
        """Register all API routes."""

        @self._app.route("/api/health", methods=["GET"])
        def health():
            """Health check endpoint."""
            return jsonify(
                {"success": True, "data": {"status": "ok", "service": "analytics-api"}}
            )

        @self._app.route("/api/stats", methods=["GET"])
        def get_stats():
            """Get database statistics."""
            try:
                with self._db_lock:
                    db = get_analytics_db()
                    stats = db.get_stats()
                return jsonify({"success": True, "data": stats})
            except Exception as e:
                error(f"[API] Error getting stats: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self._app.route("/api/global-stats", methods=["GET"])
        def get_global_stats():
            """Get global statistics from TracingDataService."""
            try:
                days = request.args.get("days", 30, type=int)
                end = datetime.now()
                start = end - timedelta(days=days)

                with self._db_lock:
                    service = self._get_service()
                    data = service.get_global_stats(start=start, end=end)
                return jsonify({"success": True, "data": data})
            except Exception as e:
                error(f"[API] Error getting global stats: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self._app.route("/api/session/<session_id>/summary", methods=["GET"])
        def get_session_summary(session_id: str):
            """Get session summary."""
            try:
                with self._db_lock:
                    service = self._get_service()
                    data = service.get_session_summary(session_id)
                return jsonify({"success": True, "data": data})
            except Exception as e:
                error(f"[API] Error getting session summary: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self._app.route("/api/session/<session_id>/tokens", methods=["GET"])
        def get_session_tokens(session_id: str):
            """Get session token details."""
            try:
                with self._db_lock:
                    service = self._get_service()
                    data = service.get_session_tokens(session_id)
                return jsonify({"success": True, "data": data})
            except Exception as e:
                error(f"[API] Error getting session tokens: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self._app.route("/api/session/<session_id>/tools", methods=["GET"])
        def get_session_tools(session_id: str):
            """Get session tool details."""
            try:
                with self._db_lock:
                    service = self._get_service()
                    data = service.get_session_tools(session_id)
                return jsonify({"success": True, "data": data})
            except Exception as e:
                error(f"[API] Error getting session tools: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self._app.route("/api/session/<session_id>/files", methods=["GET"])
        def get_session_files(session_id: str):
            """Get session file operations."""
            try:
                with self._db_lock:
                    service = self._get_service()
                    data = service.get_session_files(session_id)
                return jsonify({"success": True, "data": data})
            except Exception as e:
                error(f"[API] Error getting session files: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self._app.route("/api/session/<session_id>/agents", methods=["GET"])
        def get_session_agents(session_id: str):
            """Get session agents."""
            try:
                with self._db_lock:
                    service = self._get_service()
                    data = service.get_session_agents(session_id)
                return jsonify({"success": True, "data": data})
            except Exception as e:
                error(f"[API] Error getting session agents: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self._app.route("/api/session/<session_id>/timeline", methods=["GET"])
        def get_session_timeline(session_id: str):
            """Get session timeline events."""
            try:
                with self._db_lock:
                    service = self._get_service()
                    data = service.get_session_timeline(session_id)
                return jsonify({"success": True, "data": data})
            except Exception as e:
                error(f"[API] Error getting session timeline: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self._app.route("/api/session/<session_id>/prompts", methods=["GET"])
        def get_session_prompts(session_id: str):
            """Get session prompts."""
            try:
                with self._db_lock:
                    service = self._get_service()
                    data = service.get_session_prompts(session_id)
                return jsonify({"success": True, "data": data})
            except Exception as e:
                error(f"[API] Error getting session prompts: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self._app.route("/api/sessions", methods=["GET"])
        def get_sessions():
            """Get list of sessions for tree view."""
            try:
                days = request.args.get("days", 30, type=int)
                limit = request.args.get("limit", 100, type=int)

                with self._db_lock:
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

        @self._app.route("/api/traces", methods=["GET"])
        def get_traces():
            """Get agent traces for tree view."""
            try:
                days = request.args.get("days", 30, type=int)
                limit = request.args.get("limit", 500, type=int)

                with self._db_lock:
                    db = get_analytics_db()
                    conn = db.connect()

                    # Calculate start date (DuckDB doesn't support ? in INTERVAL)
                    start_date = datetime.now() - timedelta(days=days)

                    rows = conn.execute(
                        """
                        SELECT 
                            trace_id,
                            session_id,
                            parent_trace_id,
                            parent_agent,
                            subagent_type,
                            started_at,
                            ended_at,
                            duration_ms,
                            tokens_in,
                            tokens_out,
                            status
                        FROM agent_traces
                        WHERE started_at >= ?
                        ORDER BY started_at DESC
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
                        }
                        for row in rows
                    ]

                return jsonify({"success": True, "data": traces})
            except Exception as e:
                error(f"[API] Error getting traces: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self._app.route("/api/delegations", methods=["GET"])
        def get_delegations():
            """Get agent delegations (parent-child session relationships)."""
            try:
                days = request.args.get("days", 30, type=int)
                limit = request.args.get("limit", 1000, type=int)

                with self._db_lock:
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

    def start(self) -> None:
        """Start the API server in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            debug("[API] Server already running")
            return

        def run_server():
            # Disable Flask logging (too verbose)
            import logging

            log = logging.getLogger("werkzeug")
            log.setLevel(logging.ERROR)

            # Use threaded=False to avoid DuckDB concurrency issues
            # Requests will be serialized but that's safer
            self._server = make_server(
                self._host, self._port, self._app, threaded=False
            )
            info(f"[API] Server started on http://{self._host}:{self._port}")
            self._server.serve_forever()

        self._thread = threading.Thread(target=run_server, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the API server."""
        if self._server:
            self._server.shutdown()
            info("[API] Server stopped")
        self._server = None
        self._thread = None

    @property
    def url(self) -> str:
        """Get the base URL of the API server."""
        return f"http://{self._host}:{self._port}"

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._thread is not None and self._thread.is_alive()


# Global server instance
_api_server: Optional[AnalyticsAPIServer] = None


def get_api_server() -> AnalyticsAPIServer:
    """Get or create the global API server instance."""
    global _api_server
    if _api_server is None:
        _api_server = AnalyticsAPIServer()
    return _api_server


def start_api_server() -> None:
    """Start the global API server."""
    server = get_api_server()
    server.start()


def stop_api_server() -> None:
    """Stop the global API server."""
    global _api_server
    if _api_server:
        _api_server.stop()
        _api_server = None
