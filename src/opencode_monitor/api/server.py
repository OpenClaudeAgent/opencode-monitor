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
from .config import API_HOST, API_PORT


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
            """Get session prompts (first user prompt + last response)."""
            try:
                with self._db_lock:
                    service = self._get_service()
                    data = service.get_session_prompts(session_id)
                return jsonify({"success": True, "data": data})
            except Exception as e:
                error(f"[API] Error getting session prompts: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self._app.route("/api/session/<session_id>/messages", methods=["GET"])
        def get_session_messages(session_id: str):
            """Get all messages with content for a session."""
            try:
                with self._db_lock:
                    service = self._get_service()
                    data = service.get_session_messages(session_id)
                return jsonify({"success": True, "data": data})
            except Exception as e:
                error(f"[API] Error getting session messages: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self._app.route("/api/session/<session_id>/operations", methods=["GET"])
        def get_session_operations(session_id: str):
            """Get tool operations for a session (for tree display)."""
            try:
                with self._db_lock:
                    service = self._get_service()
                    data = service.get_session_tool_operations(session_id)
                return jsonify({"success": True, "data": data})
            except Exception as e:
                error(f"[API] Error getting session operations: {e}")
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
            """Get flat list of agent traces (legacy endpoint)."""
            try:
                days = request.args.get("days", 30, type=int)
                limit = request.args.get("limit", 500, type=int)

                with self._db_lock:
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

        @self._app.route("/api/tracing/tree", methods=["GET"])
        def get_tracing_tree():
            """Get hierarchical tracing tree for dashboard display.

            Returns sessions with their child traces and tools in a tree structure.
            All hierarchy logic is done in SQL, no client-side aggregation needed.

            Structure:
            - Session (user → agent)
              - Agent trace (agent → subagent)
                - Tool (bash, read, edit, etc.)
                - Tool ...
              - Agent trace ...
            """
            try:
                days = request.args.get("days", 30, type=int)
                include_tools = (
                    request.args.get("include_tools", "true").lower() == "true"
                )

                with self._db_lock:
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
                    if include_tools:
                        # Collect all session IDs (child_session_id from traces)
                        all_session_ids = set()
                        for row in root_rows:
                            if row[13]:  # child_session_id
                                all_session_ids.add(row[13])
                        for row in child_rows:
                            if row[13]:  # child_session_id
                                all_session_ids.add(row[13])

                        if all_session_ids:
                            # Get tools for these sessions
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

                                # Parse arguments to extract display info
                                args = row[4]
                                display_info = ""
                                if args:
                                    try:
                                        import json

                                        args_dict = json.loads(args)
                                        tool_name = row[2]
                                        if tool_name == "bash":
                                            cmd = args_dict.get("command", "")
                                            display_info = (
                                                cmd[:100] + "..."
                                                if len(cmd) > 100
                                                else cmd
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
                                            display_info = args_dict.get(
                                                "subagent_type", ""
                                            )
                                    except:
                                        pass

                                tools_by_session[session_id].append(
                                    {
                                        "id": row[0],
                                        "node_type": "tool",
                                        "tool_name": row[2],
                                        "status": row[3],
                                        "display_info": display_info,
                                        "created_at": row[5].isoformat()
                                        if row[5]
                                        else None,
                                        "duration_ms": row[6],
                                    }
                                )

                    # Build children lookup by parent_trace_id
                    children_by_parent: dict = {}
                    for row in child_rows:
                        parent_id = row[2]  # parent_trace_id
                        if parent_id not in children_by_parent:
                            children_by_parent[parent_id] = []

                        child_session_id = row[13]
                        child_tools = (
                            tools_by_session.get(child_session_id, [])
                            if include_tools
                            else []
                        )

                        children_by_parent[parent_id].append(
                            {
                                "trace_id": row[0],
                                "session_id": row[1],
                                "node_type": "agent",
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
                                # Tools are included in children (3rd level)
                                "children": child_tools.copy(),  # Start with tools
                            }
                        )

                    # Build recursive tree
                    def build_children(parent_trace_id: str, depth: int = 0) -> list:
                        if depth > 10:  # Prevent infinite recursion
                            return []
                        children = children_by_parent.get(parent_trace_id, [])
                        for child in children:
                            # Get nested agents and add them after tools
                            nested_agents = build_children(child["trace_id"], depth + 1)
                            child["children"].extend(nested_agents)
                        return children

                    # Build final tree
                    sessions = []
                    for row in root_rows:
                        trace_id = row[0]
                        child_session_id = row[13]
                        agent_type = row[3]

                        # Get agent delegations (2nd level) - tools are inside each agent
                        agent_children = build_children(trace_id)

                        # If no agent delegations but has tools, create a virtual agent node
                        # This ensures 3-level hierarchy: Session → Agent → Tools
                        if not agent_children and include_tools:
                            root_tools = tools_by_session.get(child_session_id, [])
                            if root_tools:
                                # Create virtual "primary agent" node to hold tools
                                agent_children = [
                                    {
                                        "trace_id": f"{trace_id}_primary",
                                        "session_id": row[1],
                                        "node_type": "agent",
                                        "parent_agent": "user",
                                        "subagent_type": agent_type or "agent",
                                        "started_at": row[4].isoformat()
                                        if row[4]
                                        else None,
                                        "ended_at": row[5].isoformat()
                                        if row[5]
                                        else None,
                                        "duration_ms": row[6],
                                        "tokens_in": row[7],
                                        "tokens_out": row[8],
                                        "status": row[9],
                                        "prompt_input": row[10],
                                        "children": root_tools,
                                    }
                                ]

                        session = {
                            "session_id": row[1],
                            "trace_id": trace_id,
                            "node_type": "session",
                            "parent_agent": row[2] or "user",
                            "agent_type": agent_type,
                            "started_at": row[4].isoformat() if row[4] else None,
                            "ended_at": row[5].isoformat() if row[5] else None,
                            "duration_ms": row[6],
                            "tokens_in": row[7],
                            "tokens_out": row[8],
                            "status": row[9],
                            "prompt_input": row[10],
                            "title": row[11] or "",
                            "directory": row[12] or "",
                            # Agents at level 2, tools at level 3 inside agents
                            "children": agent_children,
                        }

                        # Count total traces in subtree
                        def count_traces(node: dict) -> int:
                            return 1 + sum(
                                count_traces(c) for c in node.get("children", [])
                            )

                        session["trace_count"] = (
                            count_traces(session) - 1
                        )  # Exclude root
                        sessions.append(session)

                return jsonify({"success": True, "data": sessions})
            except Exception as e:
                error(f"[API] Error getting tracing tree: {e}")
                import traceback

                error(traceback.format_exc())
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
