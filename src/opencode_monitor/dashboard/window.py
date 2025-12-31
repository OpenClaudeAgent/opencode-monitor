"""
Dashboard main window with sidebar navigation.

Modern design with:
- Sidebar navigation instead of tabs
- Page-based content switching
- Status indicators and header
- Real-time data refresh
"""

import threading
from typing import Optional

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
from .sections import MonitoringSection, SecuritySection, AnalyticsSection


class DataSignals(QObject):
    """Signals for thread-safe data updates."""

    monitoring_updated = pyqtSignal(dict)
    security_updated = pyqtSignal(dict)
    analytics_updated = pyqtSignal(dict)


class DashboardWindow(QMainWindow):
    """Main dashboard window with sidebar navigation."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._signals = DataSignals()
        self._refresh_timer: Optional[QTimer] = None
        # Track when agents started waiting for ask_user (agent_id -> timestamp_ms)
        self._waiting_since: dict[str, int] = {}

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

        self._pages.addWidget(self._monitoring)
        self._pages.addWidget(self._security)
        self._pages.addWidget(self._analytics)

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

        # Connect period change to trigger analytics refresh
        self._analytics.period_changed.connect(self._on_analytics_period_changed)

    def _on_analytics_period_changed(self, days: int) -> None:
        """Handle analytics period change - refresh data immediately."""
        threading.Thread(target=self._fetch_analytics_data, daemon=True).start()

    def _start_refresh(self) -> None:
        """Start periodic data refresh."""
        # Initial data load
        self._refresh_all_data()

        # Periodic refresh
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_all_data)
        self._refresh_timer.start(UI["refresh_interval_ms"])

    def _refresh_all_data(self) -> None:
        """Refresh all section data in background threads."""
        threading.Thread(target=self._fetch_monitoring_data, daemon=True).start()
        threading.Thread(target=self._fetch_security_data, daemon=True).start()
        threading.Thread(target=self._fetch_analytics_data, daemon=True).start()

    def _fetch_monitoring_data(self) -> None:
        """Fetch monitoring data from core module."""
        try:
            import asyncio
            import time
            from ..core.monitor import fetch_all_instances
            from ..core.models import SessionStatus

            loop = asyncio.new_event_loop()
            state = loop.run_until_complete(fetch_all_instances())
            loop.close()

            current_time_ms = int(time.time() * 1000)

            # Build data dict
            agents_data = []
            tools_data = []
            waiting_data = []
            busy_count = 0
            waiting_count = 0  # Sessions with pending ask_user
            idle_instances = 0  # Instances with no busy agents
            total_todos = 0

            # Track which agents are currently waiting
            current_waiting_ids: set[str] = set()

            for instance in state.instances:
                # Count idle instances (instances where no agent is busy)
                if instance.busy_count == 0:
                    idle_instances += 1

                for agent in instance.agents:
                    is_busy = agent.status == SessionStatus.BUSY
                    if is_busy:
                        busy_count += 1

                    # Count agents waiting for user response
                    if agent.has_pending_ask_user:
                        waiting_count += 1
                        current_waiting_ids.add(agent.id)

                        # Track when agent started waiting
                        if agent.id not in self._waiting_since:
                            self._waiting_since[agent.id] = current_time_ms

                        waiting_ms = current_time_ms - self._waiting_since[agent.id]

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
                                "title": agent.ask_user_title
                                or agent.title
                                or f"Agent {agent.id[:8]}",
                                "question": agent.ask_user_question
                                or "Waiting for response...",
                                "options": " | ".join(agent.ask_user_options)
                                if agent.ask_user_options
                                else "",
                                "context": context,
                                "waiting_ms": waiting_ms,
                                "urgency": agent.ask_user_urgency,
                            }
                        )

                    todos_total = agent.todos.pending + agent.todos.in_progress
                    total_todos += todos_total

                    agents_data.append(
                        {
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

            # Clean up agents that are no longer waiting
            for agent_id in list(self._waiting_since.keys()):
                if agent_id not in current_waiting_ids:
                    del self._waiting_since[agent_id]

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

            self._signals.monitoring_updated.emit(data)

            # Update sidebar status
            if hasattr(self, "_sidebar"):
                is_active = len(agents_data) > 0 or state.instance_count > 0
                status_text = (
                    f"{len(agents_data)} agents" if agents_data else "No agents"
                )
                # Note: This should be called via signal for thread safety
                # but for simplicity we'll keep it here

        except Exception as e:
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

        except Exception as e:
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

        except Exception as e:
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
