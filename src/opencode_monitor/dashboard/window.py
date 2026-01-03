"""
Dashboard main window with sidebar navigation.

Modern design with:
- Sidebar navigation instead of tabs
- Page-based content switching
- Status indicators and header
- Real-time data refresh

Note: Dashboard operates in read-only mode. Data sync is handled by
the menubar app which has write access to the database. The dashboard
polls sync_meta table to detect when new data is available.
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

# API client is used for all data fetching to avoid DuckDB concurrency issues

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QApplication,
    QFrame,
)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, Qt
from PyQt6.QtGui import QCloseEvent, QIcon, QPixmap, QPainter, QFont

from .styles import get_stylesheet, COLORS, SPACING, UI, format_tokens
from .widgets import Sidebar
from .sections import (
    MonitoringSection,
    SecuritySection,
    AnalyticsSection,
    TracingSection,
)


class DataSignals(QObject):
    """Signals for thread-safe data updates."""

    monitoring_updated = pyqtSignal(dict)
    security_updated = pyqtSignal(dict)
    analytics_updated = pyqtSignal(dict)
    tracing_updated = pyqtSignal(dict)


class SyncChecker:
    """Polls sync_meta to detect when menubar has synced new data.

    The dashboard operates in read-only mode. The menubar updates sync_meta
    when it syncs new data. This class polls that table and triggers a
    refresh when new data is detected.
    """

    POLL_FAST_MS = 2000  # During activity
    POLL_SLOW_MS = 5000  # At rest
    IDLE_THRESHOLD_S = 30  # Switch to slow after 30s without change

    def __init__(self, on_sync_detected: Callable[[], None]):
        """Initialize the sync checker.

        Args:
            on_sync_detected: Callback to invoke when new sync is detected.
        """
        self._on_sync = on_sync_detected
        self._known_sync: Optional[datetime] = None
        self._last_change_time = time.time()

        self._timer = QTimer()
        self._timer.timeout.connect(self._check)
        self._timer.start(self.POLL_FAST_MS)

    def _check(self) -> None:
        """Check if API is available and data has changed."""
        try:
            from ..api import get_api_client

            client = get_api_client()

            # Use API health check instead of direct DB access
            if client.is_available:
                # Get stats to check for changes
                stats = client.get_stats()
                if stats:
                    # Use session count as change indicator
                    current = stats.get("sessions", 0)

                    if current != self._known_sync:
                        self._known_sync = current
                        self._last_change_time = time.time()
                        self._timer.setInterval(self.POLL_FAST_MS)  # Active mode
                        self._on_sync()  # Trigger refresh
                    elif time.time() - self._last_change_time > self.IDLE_THRESHOLD_S:
                        self._timer.setInterval(self.POLL_SLOW_MS)  # Quiet mode
        except Exception:
            pass  # API may not be available

    def stop(self) -> None:
        """Stop the sync checker."""
        self._timer.stop()


class DashboardWindow(QMainWindow):
    """Main dashboard window with sidebar navigation."""

    def __init__(self, parent: QWidget | None = None):
        """Initialize dashboard window.

        Args:
            parent: Parent widget (optional)
        """
        super().__init__(parent)

        self._signals = DataSignals()
        self._refresh_timer: Optional[QTimer] = None
        self._agent_tty_map: dict[str, str] = {}  # agent_id -> tty mapping
        self._sync_checker: Optional[SyncChecker] = None

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._start_refresh()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle("OpenCode Monitor")
        self.setMinimumSize(UI["window_min_width"], UI["window_min_height"])
        self.resize(UI["window_default_width"], UI["window_default_height"])

        # Create app icon
        self._set_app_icon()

        # Apply stylesheet
        self.setStyleSheet(get_stylesheet())

    def _set_app_icon(self) -> None:
        """Create and set a custom app icon."""
        size = UI["app_icon_size"]
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = QFont("Apple Color Emoji", 96)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "🤖")
        painter.end()

        icon = QIcon(pixmap)
        self.setWindowIcon(icon)

        # Set as application icon
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setWindowIcon(icon)

    def _setup_ui(self) -> None:
        """Build the user interface with sidebar layout."""
        central = QWidget()
        self.setCentralWidget(central)

        # Main horizontal layout: sidebar + content
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self._sidebar = Sidebar()
        self._sidebar.section_changed.connect(self._on_section_changed)
        main_layout.addWidget(self._sidebar)

        # Content area
        content_frame = QFrame()
        content_frame.setObjectName("content-area")
        content_frame.setStyleSheet(f"""
            QFrame#content-area {{
                background-color: {COLORS["bg_base"]};
            }}
        """)

        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Stacked widget for page switching
        self._pages = QStackedWidget()

        # Create sections
        self._monitoring = MonitoringSection()
        self._security = SecuritySection()
        self._analytics = AnalyticsSection()
        self._tracing = TracingSection()

        self._pages.addWidget(self._monitoring)
        self._pages.addWidget(self._security)
        self._pages.addWidget(self._analytics)
        self._pages.addWidget(self._tracing)

        content_layout.addWidget(self._pages)
        main_layout.addWidget(content_frame)

    def _on_section_changed(self, index: int) -> None:
        """Handle sidebar navigation."""
        self._pages.setCurrentIndex(index)

    def _connect_signals(self) -> None:
        """Connect data signals to UI updates."""
        self._signals.monitoring_updated.connect(self._on_monitoring_data)
        self._signals.security_updated.connect(self._on_security_data)
        self._signals.analytics_updated.connect(self._on_analytics_data)
        self._signals.tracing_updated.connect(self._on_tracing_data)

        # Connect period change to trigger analytics refresh
        self._analytics.period_changed.connect(self._on_analytics_period_changed)

        # Connect terminal focus signal
        self._monitoring.open_terminal_requested.connect(self._on_open_terminal)
        self._tracing.open_terminal_requested.connect(self._on_open_terminal_session)

    def _on_open_terminal(self, agent_id: str) -> None:
        """Handle request to open terminal for an agent."""
        tty = self._agent_tty_map.get(agent_id)
        if tty:
            from ..ui.terminal import focus_iterm2

            focus_iterm2(tty)

    def _on_open_terminal_session(self, session_id: str) -> None:
        """Handle request to open terminal for a session (from tracing)."""
        # For now, just log - could be extended to find session's terminal
        from ..utils.logger import debug

        debug(f"Open terminal requested for session: {session_id}")

    def _on_analytics_period_changed(self, days: int) -> None:
        """Handle analytics period change - refresh data immediately."""
        threading.Thread(target=self._fetch_analytics_data, daemon=True).start()

    def _start_refresh(self) -> None:
        """Start periodic data refresh.

        Note: Dashboard operates in read-only mode. Data sync is handled by
        the menubar app which has write access to the database.
        """
        # Initial data load from DB (read-only)
        self._refresh_all_data()

        # Periodic refresh
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_all_data)
        self._refresh_timer.start(UI["refresh_interval_ms"])

        # Start sync checker to detect when menubar syncs new data
        self._sync_checker = SyncChecker(on_sync_detected=self._refresh_all_data)

    def _refresh_all_data(self) -> None:
        """Refresh all section data in background threads."""
        threading.Thread(target=self._fetch_monitoring_data, daemon=True).start()
        threading.Thread(target=self._fetch_security_data, daemon=True).start()
        threading.Thread(target=self._fetch_analytics_data, daemon=True).start()
        threading.Thread(target=self._fetch_tracing_data, daemon=True).start()

    def _fetch_monitoring_data(self) -> None:
        """Fetch monitoring data from core module."""
        try:
            import asyncio
            from ..core.monitor import fetch_all_instances
            from ..core.models import SessionStatus

            loop = asyncio.new_event_loop()
            state = loop.run_until_complete(fetch_all_instances())
            loop.close()

            # Build data dict
            agents_data = []
            tools_data = []
            waiting_data = []
            agent_tty_map: dict[str, str] = {}  # Temporary map to update after loop
            busy_count = 0
            waiting_count = 0  # Sessions with pending ask_user
            idle_instances = 0  # Instances with no busy agents
            total_todos = 0

            for instance in state.instances:
                # Count idle instances (instances where no agent is busy)
                if instance.busy_count == 0:
                    idle_instances += 1

                for agent in instance.agents:
                    is_busy = agent.status == SessionStatus.BUSY
                    if is_busy:
                        busy_count += 1

                    # Store TTY mapping for terminal focus
                    if instance.tty:
                        agent_tty_map[agent.id] = instance.tty

                    # Count agents waiting for user response
                    if agent.has_pending_ask_user:
                        waiting_count += 1

                        # Build context string: "agent @ branch" or "repo @ branch" or just "repo"
                        context_parts = []
                        if agent.ask_user_agent:
                            context_parts.append(agent.ask_user_agent)
                        elif agent.ask_user_repo:
                            context_parts.append(agent.ask_user_repo)
                        if agent.ask_user_branch:
                            context_parts.append(agent.ask_user_branch)
                        context = " @ ".join(context_parts) if context_parts else ""

                        waiting_data.append(
                            {
                                "agent_id": agent.id,
                                "title": agent.ask_user_title
                                or agent.title
                                or f"Agent {agent.id[:8]}",
                                "question": agent.ask_user_question
                                or "Waiting for response...",
                                "options": " | ".join(agent.ask_user_options)
                                if agent.ask_user_options
                                else "",
                                "context": context,
                            }
                        )

                    todos_total = agent.todos.pending + agent.todos.in_progress
                    total_todos += todos_total

                    agents_data.append(
                        {
                            "agent_id": agent.id,
                            "title": agent.title or f"Agent {agent.id[:8]}",
                            "dir": agent.dir or "",
                            "status": "busy" if is_busy else "idle",
                            "tools": agent.tools,
                            "todos_total": todos_total,
                        }
                    )

                    for tool in agent.tools:
                        tools_data.append(
                            {
                                "name": tool.name,
                                "agent": agent.title or agent.id[:8],
                                "arg": tool.arg or "",
                                "elapsed_ms": tool.elapsed_ms,
                            }
                        )

            data = {
                "instances": state.instance_count,
                "agents": len(agents_data),
                "busy": busy_count,
                "waiting": waiting_count,
                "idle": idle_instances,
                "todos": total_todos,
                "agents_data": agents_data,
                "tools_data": tools_data,
                "waiting_data": waiting_data,
            }

            # Update TTY mapping (thread-safe assignment)
            self._agent_tty_map = agent_tty_map

            self._signals.monitoring_updated.emit(data)

            # Update sidebar status
            if hasattr(self, "_sidebar"):
                is_active = len(agents_data) > 0 or state.instance_count > 0
                status_text = (
                    f"{len(agents_data)} agents" if agents_data else "No agents"
                )
                # Note: This should be called via signal for thread safety
                # but for simplicity we'll keep it here

        except (
            Exception
        ) as e:  # Intentional catch-all: dashboard fetch errors logged, UI continues
            from ..utils.logger import error

            error(f"[Dashboard] Monitoring fetch error: {e}")

    def _fetch_security_data(self) -> None:
        """Fetch security data from auditor."""
        try:
            from ..security.auditor import get_auditor

            auditor = get_auditor()
            stats = auditor.get_stats()
            row_limit = UI["table_row_limit"]
            top_limit = UI["top_items_limit"]

            commands = auditor.get_all_commands(limit=row_limit)
            reads = auditor.get_all_reads(limit=top_limit)
            writes = auditor.get_all_writes(limit=top_limit)

            # Get critical/high items
            critical_cmds = auditor.get_critical_commands(limit=row_limit)
            high_cmds = auditor.get_commands_by_level("high", limit=row_limit)
            sensitive_reads = auditor.get_sensitive_reads(limit=top_limit)
            sensitive_writes = auditor.get_sensitive_writes(limit=top_limit)
            risky_fetches = auditor.get_risky_webfetches(limit=top_limit)

            # Build critical items list
            critical_items = []
            for c in critical_cmds + high_cmds:
                critical_items.append(
                    {
                        "type": "COMMAND",
                        "details": c.command,
                        "risk": c.risk_level,
                        "reason": c.risk_reason,
                        "score": c.risk_score,
                    }
                )
            for r in sensitive_reads:
                critical_items.append(
                    {
                        "type": "READ",
                        "details": r.file_path,
                        "risk": r.risk_level,
                        "reason": r.risk_reason,
                        "score": r.risk_score,
                    }
                )
            for w in sensitive_writes:
                critical_items.append(
                    {
                        "type": "WRITE",
                        "details": w.file_path,
                        "risk": w.risk_level,
                        "reason": w.risk_reason,
                        "score": w.risk_score,
                    }
                )
            for f in risky_fetches:
                critical_items.append(
                    {
                        "type": "WEBFETCH",
                        "details": f.url,
                        "risk": f.risk_level,
                        "reason": f.risk_reason,
                        "score": f.risk_score,
                    }
                )

            # Combine file operations
            files = []
            for r in reads:
                files.append(
                    {
                        "operation": "READ",
                        "path": r.file_path,
                        "risk": r.risk_level,
                        "score": r.risk_score,
                        "reason": r.risk_reason,
                    }
                )
            for w in writes:
                files.append(
                    {
                        "operation": "WRITE",
                        "path": w.file_path,
                        "risk": w.risk_level,
                        "reason": w.risk_reason,
                        "score": w.risk_score,
                    }
                )

            files.sort(key=lambda x: x.get("score", 0), reverse=True)

            # Format commands
            cmds = []
            for c in commands:
                cmds.append(
                    {
                        "command": c.command,
                        "risk": c.risk_level,
                        "score": c.risk_score,
                        "reason": c.risk_reason,
                    }
                )

            data = {
                "stats": stats,
                "commands": cmds,
                "files": files[:row_limit],
                "critical_items": critical_items,
            }

            self._signals.security_updated.emit(data)

        except (
            Exception
        ) as e:  # Intentional catch-all: dashboard fetch errors logged, UI continues
            from ..utils.logger import error

            error(f"[Dashboard] Security fetch error: {e}")

    def _fetch_analytics_data(self) -> None:
        """Fetch analytics data via API to avoid DuckDB concurrency issues."""
        try:
            from ..api import get_api_client

            client = get_api_client()

            # Check if API is available
            if not client.is_available:
                from ..utils.logger import debug

                debug("[Dashboard] API not available for analytics")
                return

            days = self._analytics.get_current_period()
            global_stats = client.get_global_stats(days=days)

            if not global_stats:
                return

            summary = global_stats.get("summary", {})
            details = global_stats.get("details", {})
            tokens_detail = details.get("tokens", {})

            total_tokens = summary.get("total_tokens", 0)
            input_tokens = tokens_detail.get("input", 0)
            cache_tokens = tokens_detail.get("cache_read", 0)

            # Format tokens
            if total_tokens < 1000:
                tokens_str = str(total_tokens)
            elif total_tokens < 1000000:
                tokens_str = f"{total_tokens / 1000:.1f}K"
            else:
                tokens_str = f"{total_tokens / 1000000:.1f}M"

            # Calculate cache hit ratio
            total_input = input_tokens + cache_tokens
            cache_hit = (
                f"{(cache_tokens / total_input * 100):.0f}%"
                if total_input > 0
                else "0%"
            )

            data = {
                "sessions": summary.get("total_sessions", 0),
                "messages": summary.get("total_messages", 0),
                "tokens": tokens_str,
                "cache_hit": cache_hit,
                "agents": [],  # API doesn't provide detailed agent breakdown yet
                "tools": [],  # API doesn't provide detailed tool breakdown yet
                "skills": [],  # API doesn't provide detailed skill breakdown yet
            }

            self._signals.analytics_updated.emit(data)

        except (
            Exception
        ) as e:  # Intentional catch-all: dashboard fetch errors logged, UI continues
            from ..utils.logger import error

            error(f"[Dashboard] Analytics fetch error: {e}")

    def _on_monitoring_data(self, data: dict) -> None:
        """Handle monitoring data update."""
        self._monitoring.update_data(
            instances=data.get("instances", 0),
            agents=data.get("agents", 0),
            busy=data.get("busy", 0),
            waiting=data.get("waiting", 0),
            idle=data.get("idle", 0),
            todos=data.get("todos", 0),
            agents_data=data.get("agents_data", []),
            tools_data=data.get("tools_data", []),
            waiting_data=data.get("waiting_data", []),
        )

        # Update sidebar status
        agents_count = data.get("agents", 0)
        self._sidebar.set_status(
            agents_count > 0,
            f"{agents_count} agent{'s' if agents_count != 1 else ''}"
            if agents_count > 0
            else "Idle",
        )

    def _on_security_data(self, data: dict) -> None:
        """Handle security data update."""
        self._security.update_data(
            stats=data.get("stats", {}),
            commands=data.get("commands", []),
            files=data.get("files", []),
            critical_items=data.get("critical_items", []),
        )

    def _on_analytics_data(self, data: dict) -> None:
        """Handle analytics data update."""
        self._analytics.update_data(
            sessions=data.get("sessions", 0),
            messages=data.get("messages", 0),
            tokens=data.get("tokens", "0"),
            cache_hit=data.get("cache_hit", "0%"),
            agents=data.get("agents", []),
            tools=data.get("tools", []),
            skills=data.get("skills", []),
        )

    def _fetch_tracing_data(self) -> None:
        """Fetch tracing data from API (menubar serves data).

        Uses the API client instead of direct DB access to avoid
        DuckDB multi-process concurrency issues.
        """
        from ..utils.logger import debug, error

        try:
            from ..api import get_api_client

            client = get_api_client()
            debug("[Dashboard] _fetch_tracing_data: checking API availability...")

            # Check if API is available
            if not client.is_available:
                debug("[Dashboard] API not available, menubar may not be running")
                return

            debug("[Dashboard] API is available, fetching global stats...")

            # Get global stats
            global_stats = client.get_global_stats(days=30)
            if not global_stats:
                debug("[Dashboard] No global stats returned")
                return

            debug(f"[Dashboard] Got global stats: {list(global_stats.keys())}")

            # Get traces, sessions, and delegations from API
            traces_data = client.get_traces(days=30, limit=500) or []
            sessions_data = client.get_sessions(days=30, limit=100) or []
            delegations_data = client.get_delegations(days=30, limit=1000) or []

            debug(
                f"[Dashboard] Got {len(traces_data)} traces, {len(sessions_data)} sessions, {len(delegations_data)} delegations"
            )

            # Convert sessions to expected format
            sessions_formatted = []
            for session in sessions_data:
                sessions_formatted.append(
                    {
                        "session_id": session.get("id"),
                        "title": session.get("title"),
                        "trace_count": 0,  # Will be computed
                        "first_trace_at": session.get("created_at"),
                        "total_duration_ms": 0,
                    }
                )

            # Build session hierarchy using delegations
            session_hierarchy = self._build_session_hierarchy(
                traces_data, sessions_data, delegations_data
            )

            debug(
                f"[Dashboard] Built hierarchy with {len(session_hierarchy)} root sessions"
            )

            # Extract stats
            summary = global_stats.get("summary", {})

            data = {
                "traces": traces_data,
                "sessions": sessions_formatted,
                "session_hierarchy": session_hierarchy,
                "total_traces": summary.get("total_traces", len(traces_data)),
                "unique_agents": summary.get("unique_agents", 0),
                "total_duration_ms": summary.get("total_duration_ms", 0),
            }

            debug(
                f"[Dashboard] Emitting tracing_updated signal with {len(session_hierarchy)} sessions"
            )
            self._signals.tracing_updated.emit(data)

        except Exception as e:
            error(f"[Dashboard] Tracing fetch error: {e}")
            import traceback

            error(traceback.format_exc())

    def _build_session_hierarchy(
        self, traces: list, sessions: list, delegations: list
    ) -> list:
        """Build session hierarchy from traces grouped by root session.

        Creates a tree structure where each root session contains:
        - Messages (user prompts and assistant responses)
        - Sub-agent traces (Task invocations)

        Args:
            traces: List of agent trace dicts
            sessions: List of session dicts
            delegations: List of delegation dicts (for future use)

        Returns:
            List of root session nodes with messages and agents as children
        """
        from ..api import get_api_client

        api_client = get_api_client()

        # Group traces by their root session (extracted from parent_trace_id)
        traces_by_root: dict[str, list] = {}

        for trace in traces:
            parent_trace_id = trace.get("parent_trace_id", "")

            # Extract root session ID from parent_trace_id
            if parent_trace_id.startswith("root_"):
                root_session_id = parent_trace_id[5:]  # Remove "root_" prefix
            else:
                root_session_id = trace.get("session_id", "unknown")

            if root_session_id not in traces_by_root:
                traces_by_root[root_session_id] = []
            traces_by_root[root_session_id].append(trace)

        # Sort traces within each root by time
        for root_id in traces_by_root:
            traces_by_root[root_id].sort(
                key=lambda t: t.get("started_at") or "", reverse=False
            )

        # Build session lookup
        sessions_map = {s.get("id"): s for s in sessions}

        # Build hierarchy
        hierarchy = []

        for root_session_id, root_traces in traces_by_root.items():
            session = sessions_map.get(root_session_id, {})

            # Separate the root trace (user) from sub-agent traces
            user_trace = None
            agent_traces = []

            for t in root_traces:
                if t.get("subagent_type") == "user":
                    user_trace = t
                else:
                    agent_traces.append(t)

            # Use user trace or first trace for metadata
            first_trace = user_trace or (agent_traces[0] if agent_traces else {})

            # Compute totals across all traces
            all_traces = root_traces
            total_duration = sum(t.get("duration_ms", 0) or 0 for t in all_traces)
            total_tokens_in = sum(t.get("tokens_in", 0) or 0 for t in all_traces)
            total_tokens_out = sum(t.get("tokens_out", 0) or 0 for t in all_traces)

            # Build children: agent traces only (messages loaded lazily in TranscriptTab)
            # Note: Loading messages here caused API overload (20+ simultaneous requests
            # to single-threaded Flask server). Messages are now loaded via get_session_summary
            # when user clicks on a session, which is a single request per selection.
            children = []
            messages = []  # Messages loaded lazily via TranscriptTab, not in tree

            # Group messages into conversation turns (user prompt + assistant response)
            # Each turn starts with a user message and includes all following assistant messages
            turns = []
            current_turn = None

            for msg in messages:
                msg_type = msg.get("type", "message")
                role = msg.get("role", "")
                content = msg.get("content", "")
                timestamp = msg.get("timestamp", "")
                agent = msg.get(
                    "agent", ""
                )  # Agent name (coordinateur, executeur, etc.)

                # Skip tool messages and empty content
                if msg_type == "tool" or not content:
                    continue

                if msg_type == "text":
                    if role == "user":
                        # Start a new turn with user message
                        if current_turn:
                            turns.append(current_turn)
                        current_turn = {
                            "user_content": content,
                            "user_timestamp": timestamp,
                            "user_tokens_in": msg.get("tokens_in", 0),
                            "assistant_content": "",  # Will accumulate all responses
                            "assistant_timestamp": None,
                            "assistant_tokens_out": 0,
                            "agent": agent or "assistant",  # Agent who will respond
                        }
                    elif role == "assistant" and current_turn:
                        # Accumulate ALL assistant responses (not just the last one)
                        if current_turn["assistant_content"]:
                            current_turn["assistant_content"] += "\n\n---\n\n" + content
                        else:
                            current_turn["assistant_content"] = content
                        current_turn["assistant_timestamp"] = timestamp
                        current_turn["assistant_tokens_out"] += (
                            msg.get("tokens_out", 0) or 0
                        )
                        # Update agent name from assistant message (more reliable)
                        if agent:
                            current_turn["agent"] = agent

            # Don't forget the last turn
            if current_turn:
                turns.append(current_turn)

            # Add turns as children (conversation exchanges)
            for turn in turns:
                user_content = turn["user_content"] or ""
                assistant_content = turn["assistant_content"]

                # Truncate for display
                user_short = user_content[:80].replace("\n", " ")
                if len(user_content) > 80:
                    user_short += "..."

                if assistant_content:
                    assistant_short = assistant_content[:60].replace("\n", " ")
                    if len(assistant_content) > 60:
                        assistant_short += "..."
                    title = f"{user_short} → {assistant_short}"
                else:
                    title = f"{user_short} → (waiting...)"

                child_node = {
                    "session_id": root_session_id,
                    "node_type": "turn",
                    "title": title,
                    "user_content": user_content,
                    "assistant_content": assistant_content,
                    "created_at": turn["user_timestamp"],
                    "tokens_in": turn["user_tokens_in"],
                    "tokens_out": turn["assistant_tokens_out"],
                    "agent": turn.get("agent", "assistant"),  # Agent who responded
                    "children": [],
                }
                children.append(child_node)

            # Determine session's main agent from turns (for parent_agent correction)
            session_agent = None
            if turns:
                session_agent = turns[0].get("agent")

            # Add agent traces as children
            for agent_trace in agent_traces:
                # Use session's agent as parent if trace says "user" but session has an agent
                trace_parent = agent_trace.get("parent_agent", "user")
                if trace_parent == "user" and session_agent:
                    trace_parent = session_agent

                # Tool operations are displayed in the ToolsTab panel when user
                # clicks on an agent, not in the tree (to avoid API overload)
                tool_children = []

                child_node = {
                    "session_id": agent_trace.get("session_id"),
                    "trace_id": agent_trace.get("trace_id"),
                    "node_type": "agent",
                    "title": agent_trace.get("subagent_type", "agent"),
                    "agent_type": agent_trace.get("subagent_type"),
                    "parent_agent": trace_parent,
                    "created_at": agent_trace.get("started_at"),
                    "duration_ms": agent_trace.get("duration_ms", 0),
                    "tokens_in": agent_trace.get("tokens_in", 0),
                    "tokens_out": agent_trace.get("tokens_out", 0),
                    "status": agent_trace.get("status"),
                    "trace_count": 1,
                    "prompt_input": agent_trace.get(
                        "prompt_input"
                    ),  # Real prompt from Task tool
                    "prompt_output": agent_trace.get(
                        "prompt_output"
                    ),  # Agent's response
                    "children": tool_children,
                }
                children.append(child_node)

            # Sort all children by timestamp
            children.sort(key=lambda c: c.get("created_at") or "", reverse=False)

            # Skip sessions without any children (agents)
            # Note: Messages are loaded lazily via TranscriptTab, not in the tree
            if not children:
                continue

            # Build root node
            node = {
                "session_id": root_session_id,
                "node_type": "session",
                "title": session.get("title") or "Session",
                "agent_type": "user",
                "parent_agent": None,
                "created_at": first_trace.get("started_at")
                or session.get("created_at"),
                "directory": session.get("directory", ""),
                "trace_count": len(all_traces),
                "total_duration_ms": total_duration,
                "tokens_in": total_tokens_in,
                "tokens_out": total_tokens_out,
                "status": first_trace.get("status"),
                "children": children,
            }
            hierarchy.append(node)

        # Sort hierarchy by created_at (most recent first)
        hierarchy.sort(key=lambda n: n.get("created_at") or "", reverse=True)

        return hierarchy

    def _on_tracing_data(self, data: dict) -> None:
        """Handle tracing data update."""
        self._tracing.update_data(
            traces=data.get("traces", []),
            sessions=data.get("sessions", []),
            session_hierarchy=data.get("session_hierarchy", []),
            total_traces=data.get("total_traces", 0),
            unique_agents=data.get("unique_agents", 0),
            total_duration_ms=data.get("total_duration_ms", 0),
        )

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        """Handle window close."""
        if self._refresh_timer:
            self._refresh_timer.stop()
        if self._sync_checker:
            self._sync_checker.stop()
        if a0:
            a0.accept()


# Global reference to dashboard subprocess
_dashboard_process = None


def show_dashboard() -> None:
    """Show the dashboard window in a separate process.

    Since rumps has its own event loop, we launch the PyQt dashboard
    as a subprocess to avoid conflicts between event loops.
    """
    import subprocess
    import sys

    global _dashboard_process

    # Kill existing dashboard if running
    if _dashboard_process is not None:
        poll_result = _dashboard_process.poll()
        if poll_result is None:
            _dashboard_process.terminate()
            try:
                _dashboard_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                _dashboard_process.kill()
        _dashboard_process = None

    # Launch dashboard as a separate process
    _dashboard_process = subprocess.Popen(
        [sys.executable, "-m", "opencode_monitor.dashboard"],
        start_new_session=True,
    )
