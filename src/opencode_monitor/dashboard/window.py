"""
Dashboard main window with sidebar navigation.

Modern design with:
- Sidebar navigation instead of tabs
- Page-based content switching
- Status indicators and header
- Real-time data refresh
"""

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

# Import analytics modules at top level to avoid deadlock in threads
from ..analytics.db import AnalyticsDB
from ..analytics.queries.trace_queries import TraceQueries
from ..analytics.loader import load_opencode_data


@dataclass
class SyncConfig:
    """Configuration for OpenCode data synchronization.

    Extracted as a dataclass for testability - allows injecting
    different configurations in tests without modifying code.

    Attributes:
        clear_first: Whether to clear existing data before sync
        max_days: Maximum number of days to sync
        skip_parts: Skip loading parts (slow with many files)
    """

    clear_first: bool = False
    max_days: int = 30
    skip_parts: bool = True


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
    sync_completed = pyqtSignal(dict)  # OpenCode data sync status


class DashboardWindow(QMainWindow):
    """Main dashboard window with sidebar navigation."""

    def __init__(
        self,
        parent: QWidget | None = None,
        sync_config: SyncConfig | None = None,
    ):
        """Initialize dashboard window.

        Args:
            parent: Parent widget (optional)
            sync_config: Configuration for OpenCode data sync (optional).
                        If not provided, uses default SyncConfig().
                        Inject a custom config for testing.
        """
        super().__init__(parent)

        self._signals = DataSignals()
        self._refresh_timer: Optional[QTimer] = None
        self._agent_tty_map: dict[str, str] = {}  # agent_id -> tty mapping
        self._sync_config = sync_config or SyncConfig()

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
        self._signals.sync_completed.connect(self._on_sync_completed)

        # Connect period change to trigger analytics refresh
        self._analytics.period_changed.connect(self._on_analytics_period_changed)

        # Connect terminal focus signal
        self._monitoring.open_terminal_requested.connect(self._on_open_terminal)
        self._tracing.open_terminal_requested.connect(self._on_open_terminal_session)

    def _on_sync_completed(self, result: dict) -> None:
        """Handle OpenCode data sync completion - refresh all data."""
        # Refresh all sections to pick up new data
        self._refresh_all_data()

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
        """Start periodic data refresh."""
        # Sync OpenCode data first (in background to not block UI)
        threading.Thread(target=self._sync_opencode_data, daemon=True).start()

        # Initial data load (will use whatever is in DB)
        self._refresh_all_data()

        # Periodic refresh
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_all_data)
        self._refresh_timer.start(UI["refresh_interval_ms"])

    def _sync_opencode_data(self) -> None:
        """Sync OpenCode storage data to analytics database.

        This runs on startup to ensure the dashboard shows the latest data.
        Uses configuration from self._sync_config for testability.
        """
        try:
            from ..utils.logger import info, error

            cfg = self._sync_config
            info(f"[Dashboard] Syncing OpenCode data (max_days={cfg.max_days})...")
            result = load_opencode_data(
                clear_first=cfg.clear_first,
                max_days=cfg.max_days,
                skip_parts=cfg.skip_parts,
            )
            info(f"[Dashboard] Sync complete: {result}")

            # Emit signal to trigger data refresh
            self._signals.sync_completed.emit(result)

        except Exception as e:
            from ..utils.logger import error

            error(f"[Dashboard] Sync error: {e}")

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
        """Fetch analytics data from database."""
        try:
            from ..analytics import AnalyticsQueries
            from ..analytics.db import AnalyticsDB

            db = AnalyticsDB()
            queries = AnalyticsQueries(db)

            days = self._analytics.get_current_period()
            stats = queries.get_period_stats(days=days)

            tokens_str = format_tokens(stats.tokens.total)
            cache_hit = f"{stats.tokens.cache_hit_ratio:.0f}%"

            # Convert dataclasses to dicts
            limit = UI["top_items_limit"]
            agents = [
                {
                    "agent": a.agent,
                    "messages": a.message_count,
                    "tokens": a.tokens.total,
                }
                for a in stats.agents[:limit]
            ]

            tools = [
                {
                    "tool_name": t.tool_name,
                    "invocations": t.invocations,
                    "failures": t.failures,
                }
                for t in stats.tools[:limit]
            ]

            skills = [
                {
                    "skill_name": s.skill_name,
                    "load_count": s.load_count,
                }
                for s in stats.skills[:limit]
            ]

            data = {
                "sessions": stats.session_count,
                "messages": stats.message_count,
                "tokens": tokens_str,
                "cache_hit": cache_hit,
                "agents": agents,
                "tools": tools,
                "skills": skills,
            }

            db.close()
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
        """Fetch tracing data from database."""
        try:
            db = AnalyticsDB()
            queries = TraceQueries(db)

            # Get stats for last 30 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            stats = queries.get_trace_stats(start_date, end_date)
            sessions = queries.get_sessions_with_traces(limit=50)
            traces = queries.get_traces_by_date_range(start_date, end_date)
            session_hierarchy = queries.get_session_hierarchy(
                start_date, end_date, limit=50
            )

            # Convert traces to dicts for Qt signal
            traces_data = []
            for trace in traces:
                traces_data.append(
                    {
                        "trace_id": trace.trace_id,
                        "session_id": trace.session_id,
                        "parent_trace_id": trace.parent_trace_id,
                        "parent_agent": trace.parent_agent,
                        "subagent_type": trace.subagent_type,
                        "prompt_input": trace.prompt_input,
                        "prompt_output": trace.prompt_output,
                        "started_at": trace.started_at,
                        "ended_at": trace.ended_at,
                        "duration_ms": trace.duration_ms,
                        "tokens_in": trace.tokens_in,
                        "tokens_out": trace.tokens_out,
                        "status": trace.status,
                        "tools_used": trace.tools_used,
                        "child_session_id": trace.child_session_id,
                    }
                )

            sessions_data = []
            for session in sessions:
                sessions_data.append(
                    {
                        "session_id": session.session_id,
                        "title": session.title,
                        "trace_count": session.trace_count,
                        "first_trace_at": session.first_trace_at,
                        "total_duration_ms": session.total_duration_ms,
                    }
                )

            # Convert session hierarchy to nested dicts
            def session_to_dict(node):
                return {
                    "session_id": node.session_id,
                    "title": node.title,
                    "parent_session_id": node.parent_session_id,
                    "agent_type": node.agent_type,
                    "parent_agent": node.parent_agent,
                    "created_at": node.created_at,
                    "directory": node.directory,
                    "trace_count": node.trace_count,
                    "children": [session_to_dict(c) for c in node.children],
                }

            hierarchy_data = [session_to_dict(s) for s in session_hierarchy]

            data = {
                "traces": traces_data,
                "sessions": sessions_data,
                "session_hierarchy": hierarchy_data,
                "total_traces": stats.get("total_traces", 0),
                "unique_agents": stats.get("unique_agents", 0),
                "total_duration_ms": stats.get("total_duration_ms", 0),
            }

            db.close()
            self._signals.tracing_updated.emit(data)

        except Exception as e:
            from ..utils.logger import error

            error(f"[Dashboard] Tracing fetch error: {e}")

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
