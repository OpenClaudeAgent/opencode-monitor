"""
Dashboard main window with tabbed sections.

This window provides a unified view of:
- Monitoring: Real-time agents/tools/todos status
- Security: Risk analysis and command history
- Analytics: Usage statistics and trends
"""

import threading
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QApplication,
)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, Qt, QSize
from PyQt6.QtGui import QCloseEvent, QIcon, QPixmap, QPainter, QFont, QColor

from .styles import get_stylesheet
from .sections import MonitoringSection, SecuritySection, AnalyticsSection


class DataSignals(QObject):
    """Signals for thread-safe data updates."""

    monitoring_updated = pyqtSignal(dict)
    security_updated = pyqtSignal(dict)
    analytics_updated = pyqtSignal(dict)


class DashboardWindow(QMainWindow):
    """Main dashboard window with tabbed sections."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._signals = DataSignals()
        self._refresh_timer: Optional[QTimer] = None

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._start_refresh()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle("OpenCode Monitor")
        self.setMinimumSize(900, 600)
        self.resize(1100, 750)

        # Create app icon programmatically (robot emoji style)
        self._set_app_icon()

        # Apply stylesheet
        self.setStyleSheet(get_stylesheet())

    def _set_app_icon(self) -> None:
        """Create and set a custom app icon."""
        # Create a 128x128 pixmap with the robot emoji
        size = 128
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw robot emoji as text
        font = QFont("Apple Color Emoji", 96)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "🤖")
        painter.end()

        # Set as window and app icon
        icon = QIcon(pixmap)
        self.setWindowIcon(icon)

        # Also set as application icon (for dock)
        app = QApplication.instance()
        if app:
            app.setWindowIcon(icon)

    def _setup_ui(self) -> None:
        """Build the user interface."""
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        # Sections
        self._monitoring = MonitoringSection()
        self._security = SecuritySection()
        self._analytics = AnalyticsSection()

        self._tabs.addTab(self._monitoring, "Monitoring")
        self._tabs.addTab(self._security, "Security")
        self._tabs.addTab(self._analytics, "Analytics")

        layout.addWidget(self._tabs)

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

        # Refresh every 2 seconds
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_all_data)
        self._refresh_timer.start(2000)

    def _refresh_all_data(self) -> None:
        """Refresh all section data in background threads."""
        threading.Thread(target=self._fetch_monitoring_data, daemon=True).start()
        threading.Thread(target=self._fetch_security_data, daemon=True).start()
        threading.Thread(target=self._fetch_analytics_data, daemon=True).start()

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
            busy_count = 0
            idle_count = 0
            total_todos = 0

            for instance in state.instances:
                for agent in instance.agents:
                    is_busy = agent.status == SessionStatus.BUSY
                    if is_busy:
                        busy_count += 1
                    else:
                        idle_count += 1

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

            data = {
                "instances": state.instance_count,
                "agents": len(agents_data),
                "busy": busy_count,
                "idle": idle_count,
                "todos": total_todos,
                "agents_data": agents_data,
                "tools_data": tools_data,
            }

            self._signals.monitoring_updated.emit(data)

        except Exception as e:
            from ..utils.logger import error

            error(f"[Dashboard] Monitoring fetch error: {e}")

    def _fetch_security_data(self) -> None:
        """Fetch security data from auditor."""
        try:
            from ..security.auditor import get_auditor

            auditor = get_auditor()
            stats = auditor.get_stats()
            commands = auditor.get_all_commands(limit=20)
            reads = auditor.get_all_reads(limit=10)
            writes = auditor.get_all_writes(limit=10)

            # Get critical/high items specifically
            critical_cmds = auditor.get_critical_commands(limit=15)
            high_cmds = auditor.get_commands_by_level("high", limit=15)
            sensitive_reads = auditor.get_sensitive_reads(limit=10)
            sensitive_writes = auditor.get_sensitive_writes(limit=10)
            risky_fetches = auditor.get_risky_webfetches(limit=10)

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

            # Combine file operations - use dataclass attributes
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

            # Sort by score desc
            files.sort(key=lambda x: x.get("score", 0), reverse=True)

            # Format commands - use dataclass attributes
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
                "files": files[:20],
                "critical_items": critical_items,
            }

            self._signals.security_updated.emit(data)

        except Exception as e:
            from ..utils.logger import error

            error(f"[Dashboard] Security fetch error: {e}")

    def _fetch_analytics_data(self) -> None:
        """Fetch analytics data from database.

        Collector releases DB lock between batches, so we can connect normally.
        We create a fresh connection each time to avoid stale data.
        """
        try:
            from ..analytics import AnalyticsQueries
            from ..analytics.db import AnalyticsDB

            # Fresh connection each fetch (collector releases lock between batches)
            db = AnalyticsDB()
            queries = AnalyticsQueries(db)

            # Get stats for selected period - returns PeriodStats dataclass
            days = self._analytics.get_current_period()
            stats = queries.get_period_stats(days=days)

            # Format tokens
            total_tokens = stats.tokens.total
            if total_tokens >= 1_000_000:
                tokens_str = f"{total_tokens / 1_000_000:.1f}M"
            elif total_tokens >= 1_000:
                tokens_str = f"{total_tokens / 1_000:.0f}K"
            else:
                tokens_str = str(total_tokens)

            # Cache hit rate from TokenStats
            cache_hit = f"{stats.tokens.cache_hit_ratio:.0f}%"

            # Convert AgentStats dataclasses to dicts
            agents = []
            for a in stats.agents[:10]:
                agents.append(
                    {
                        "agent": a.agent,
                        "messages": a.message_count,
                        "tokens": a.tokens.total,
                    }
                )

            # Convert ToolStats dataclasses to dicts
            tools = []
            for t in stats.tools[:10]:
                tools.append(
                    {
                        "tool_name": t.tool_name,
                        "invocations": t.invocations,
                        "failures": t.failures,
                    }
                )

            # Convert SkillStats dataclasses to dicts
            skills = []
            for s in stats.skills[:10]:
                skills.append(
                    {
                        "skill_name": s.skill_name,
                        "load_count": s.load_count,
                    }
                )

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
            idle=data.get("idle", 0),
            todos=data.get("todos", 0),
            agents_data=data.get("agents_data", []),
            tools_data=data.get("tools_data", []),
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

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close."""
        if self._refresh_timer:
            self._refresh_timer.stop()
        event.accept()


# Global reference to dashboard subprocess
_dashboard_process = None


def show_dashboard() -> None:
    """Show the dashboard window in a separate process.

    Since rumps has its own event loop, we launch the PyQt dashboard
    as a subprocess to avoid conflicts between event loops.

    If dashboard is already running, kill it and open a fresh one.
    """
    import subprocess
    import sys

    global _dashboard_process

    # Kill existing dashboard if running
    if _dashboard_process is not None:
        poll_result = _dashboard_process.poll()
        if poll_result is None:
            # Process still running - terminate it
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
