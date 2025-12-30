"""
Dashboard sections: Monitoring, Security, Analytics.

Each section fetches and displays data from the existing modules.
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QLabel,
    QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from .widgets import Card, MetricsRow, DataTable, SectionHeader, Separator
from .styles import COLORS, SPACING


class MonitoringSection(QWidget):
    """Monitoring section - displays active sessions, agents, tools, todos."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["lg"])

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(
            0, 0, SPACING["md"], 0
        )  # Right margin for scrollbar
        content_layout.setSpacing(SPACING["xl"])

        # Summary metrics
        content_layout.addWidget(
            SectionHeader("Overview", "Real-time monitoring status")
        )

        self._metrics = MetricsRow()
        self._metrics.add_metric("instances", "0", "Instances")
        self._metrics.add_metric("agents", "0", "Agents")
        self._metrics.add_metric("busy", "0", "Busy", COLORS["accent_success"])
        self._metrics.add_metric("idle", "0", "Idle", COLORS["text_muted"])
        self._metrics.add_metric("todos", "0", "Todos", COLORS["accent_warning"])
        self._metrics.add_stretch()
        content_layout.addWidget(self._metrics)

        content_layout.addWidget(Separator())

        # Agents table
        content_layout.addWidget(
            SectionHeader("Active Agents", "Currently running sessions")
        )

        self._agents_table = DataTable(
            ["Agent", "Directory", "Status", "Tools", "Todos"]
        )
        # Set default column widths (user can resize)
        self._agents_table.setColumnWidth(0, 300)  # Agent
        self._agents_table.setColumnWidth(1, 220)  # Directory
        self._agents_table.setColumnWidth(2, 80)  # Status
        self._agents_table.setColumnWidth(3, 60)  # Tools
        # Todos is last - stretches to fill
        content_layout.addWidget(self._agents_table)

        content_layout.addWidget(Separator())

        # Tools table
        content_layout.addWidget(
            SectionHeader("Running Tools", "Tools currently executing")
        )

        self._tools_table = DataTable(["Tool", "Agent", "Arguments", "Duration"])
        # Set default column widths (user can resize)
        self._tools_table.setColumnWidth(0, 100)  # Tool
        self._tools_table.setColumnWidth(1, 200)  # Agent
        self._tools_table.setColumnWidth(2, 350)  # Arguments
        # Duration is last - stretches to fill
        content_layout.addWidget(self._tools_table)

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def update_data(
        self,
        instances: int,
        agents: int,
        busy: int,
        idle: int,
        todos: int,
        agents_data: list[dict],
        tools_data: list[dict],
    ) -> None:
        """Update the monitoring data."""
        # Update metrics
        self._metrics.update_metric("instances", str(instances))
        self._metrics.update_metric("agents", str(agents))
        self._metrics.update_metric("busy", str(busy))
        self._metrics.update_metric("idle", str(idle))
        self._metrics.update_metric("todos", str(todos))

        # Update agents table
        self._agents_table.clear_data()
        for agent in agents_data:
            status_class = (
                "status-busy" if agent.get("status") == "busy" else "status-idle"
            )
            title = agent.get("title", "Unknown")
            directory = agent.get("dir", "")
            self._agents_table.add_row(
                [
                    title,
                    directory,
                    (agent.get("status", "").upper(), status_class),
                    str(len(agent.get("tools", []))),
                    str(agent.get("todos_total", 0)),
                ],
                full_values=[title, directory, "", "", ""],
            )

        # Update tools table
        self._tools_table.clear_data()
        for tool in tools_data:
            elapsed = tool.get("elapsed_ms", 0)
            duration = f"{elapsed // 1000}s" if elapsed >= 1000 else f"{elapsed}ms"
            arg = tool.get("arg", "")
            self._tools_table.add_row(
                [
                    tool.get("name", ""),
                    tool.get("agent", ""),
                    arg,
                    duration,
                ],
                full_values=[
                    tool.get("name", ""),
                    tool.get("agent", ""),
                    arg,
                    duration,
                ],
            )


class SecuritySection(QWidget):
    """Security section - displays risks, commands, file operations."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["lg"])

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(
            0, 0, SPACING["md"], 0
        )  # Right margin for scrollbar
        content_layout.setSpacing(SPACING["xl"])

        # Summary metrics
        content_layout.addWidget(
            SectionHeader("Security Overview", "Risk analysis summary")
        )

        self._metrics = MetricsRow()
        self._metrics.add_metric("total", "0", "Total Analyzed")
        self._metrics.add_metric("critical", "0", "Critical", COLORS["accent_error"])
        self._metrics.add_metric("high", "0", "High", COLORS["accent_warning"])
        self._metrics.add_metric("medium", "0", "Medium", "#e6b800")
        self._metrics.add_metric("low", "0", "Low", COLORS["accent_success"])
        self._metrics.add_stretch()
        content_layout.addWidget(self._metrics)

        content_layout.addWidget(Separator())

        # Critical alerts table
        content_layout.addWidget(
            SectionHeader("Critical Alerts", "High-risk operations requiring attention")
        )

        self._critical_table = DataTable(["Type", "Details", "Risk", "Reason"])
        # Set default column widths (user can resize)
        self._critical_table.setColumnWidth(0, 100)  # Type
        self._critical_table.setColumnWidth(1, 350)  # Details
        self._critical_table.setColumnWidth(2, 80)  # Risk
        # Reason is last - stretches to fill
        content_layout.addWidget(self._critical_table)

        content_layout.addWidget(Separator())

        # Recent commands
        content_layout.addWidget(
            SectionHeader("Recent Commands", "Last analyzed bash commands")
        )

        self._commands_table = DataTable(["Command", "Risk", "Score", "Reason"])
        # Set default column widths (user can resize)
        self._commands_table.setColumnWidth(0, 400)  # Command
        self._commands_table.setColumnWidth(1, 80)  # Risk
        self._commands_table.setColumnWidth(2, 60)  # Score
        # Reason is last - stretches to fill
        content_layout.addWidget(self._commands_table)

        content_layout.addWidget(Separator())

        # File operations
        content_layout.addWidget(
            SectionHeader("File Operations", "Recent reads and writes")
        )

        self._files_table = DataTable(["Operation", "Path", "Risk", "Score"])
        # Set default column widths (user can resize)
        self._files_table.setColumnWidth(0, 100)  # Operation
        self._files_table.setColumnWidth(1, 450)  # Path
        self._files_table.setColumnWidth(2, 80)  # Risk
        # Score is last - stretches to fill
        content_layout.addWidget(self._files_table)

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def update_data(
        self,
        stats: dict,
        commands: list[dict],
        files: list[dict],
        critical_items: list[dict] | None = None,
    ) -> None:
        """Update the security data."""
        # Update metrics
        total = stats.get("total", 0)
        self._metrics.update_metric("total", str(total))
        self._metrics.update_metric("critical", str(stats.get("critical", 0)))
        self._metrics.update_metric("high", str(stats.get("high", 0)))
        self._metrics.update_metric("medium", str(stats.get("medium", 0)))
        self._metrics.update_metric("low", str(stats.get("low", 0)))

        # Update critical alerts table
        self._critical_table.clear_data()
        if critical_items:
            # Sort by score desc
            sorted_items = sorted(
                critical_items,
                key=lambda x: x.get("score", 0),
                reverse=True,
            )
            for item in sorted_items[:20]:
                risk = item.get("risk", "low").lower()
                risk_class = f"risk-{risk}"
                details = item.get("details", "")
                reason = item.get("reason", "")
                self._critical_table.add_row(
                    [
                        item.get("type", ""),
                        details,
                        (risk.upper(), risk_class),
                        reason,
                    ],
                    full_values=[item.get("type", ""), details, risk.upper(), reason],
                )

        # Update commands table
        self._commands_table.clear_data()
        for cmd in commands[:20]:
            risk = cmd.get("risk", "low").lower()
            risk_class = f"risk-{risk}"
            command = cmd.get("command", "")
            reason = cmd.get("reason", "")
            self._commands_table.add_row(
                [
                    command,
                    (risk.upper(), risk_class),
                    str(cmd.get("score", 0)),
                    reason,
                ],
                full_values=[command, risk.upper(), str(cmd.get("score", 0)), reason],
            )

        # Update files table
        self._files_table.clear_data()
        for f in files[:20]:
            risk = f.get("risk", "low").lower()
            risk_class = f"risk-{risk}"
            path = f.get("path", "")
            self._files_table.add_row(
                [
                    f.get("operation", ""),
                    path,
                    (risk.upper(), risk_class),
                    str(f.get("score", 0)),
                ],
                full_values=[
                    f.get("operation", ""),
                    path,
                    risk.upper(),
                    str(f.get("score", 0)),
                ],
            )


class AnalyticsSection(QWidget):
    """Analytics section - displays usage statistics and trends."""

    # Signal emitted when period changes (days: int)
    period_changed = pyqtSignal(int)

    # Period options: (label, days)
    PERIODS = [
        ("Last 24 hours", 1),
        ("Last 7 days", 7),
        ("Last 30 days", 30),
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_days = 7  # Default period
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["lg"])

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(
            0, 0, SPACING["md"], 0
        )  # Right margin for scrollbar
        content_layout.setSpacing(SPACING["xl"])

        # Header with period selector
        header_row = QHBoxLayout()
        header_row.setSpacing(SPACING["lg"])

        self._header = SectionHeader("Analytics Overview")
        header_row.addWidget(self._header)
        header_row.addStretch()

        # Period dropdown
        self._period_combo = QComboBox()
        for label, _ in self.PERIODS:
            self._period_combo.addItem(label)
        self._period_combo.setCurrentIndex(1)  # Default: Last 7 days
        self._period_combo.currentIndexChanged.connect(self._on_period_changed)
        header_row.addWidget(self._period_combo)

        content_layout.addLayout(header_row)

        self._metrics = MetricsRow()
        self._metrics.add_metric("sessions", "0", "Sessions")
        self._metrics.add_metric("messages", "0", "Messages")
        self._metrics.add_metric("tokens", "0", "Tokens")
        self._metrics.add_metric(
            "cache_hit", "0%", "Cache Hit", COLORS["accent_success"]
        )
        self._metrics.add_stretch()
        content_layout.addWidget(self._metrics)

        content_layout.addWidget(Separator())

        # Agents usage
        content_layout.addWidget(
            SectionHeader("Agent Usage", "Token consumption by agent")
        )

        self._agents_table = DataTable(["Agent", "Messages", "Tokens", "Share"])
        # Set default column widths (user can resize)
        self._agents_table.setColumnWidth(0, 350)  # Agent
        self._agents_table.setColumnWidth(1, 100)  # Messages
        self._agents_table.setColumnWidth(2, 100)  # Tokens
        # Share is last - stretches to fill
        content_layout.addWidget(self._agents_table)

        content_layout.addWidget(Separator())

        # Top tools
        content_layout.addWidget(SectionHeader("Top Tools", "Most used tools"))

        self._tools_table = DataTable(
            ["Tool", "Invocations", "Failures", "Failure Rate"]
        )
        # Set default column widths (user can resize)
        self._tools_table.setColumnWidth(0, 200)  # Tool
        self._tools_table.setColumnWidth(1, 120)  # Invocations
        self._tools_table.setColumnWidth(2, 100)  # Failures
        # Failure Rate is last - stretches to fill
        content_layout.addWidget(self._tools_table)

        content_layout.addWidget(Separator())

        # Skills usage
        content_layout.addWidget(SectionHeader("Skills Used", "Loaded skills"))

        self._skills_table = DataTable(["Skill", "Load Count"])
        # Set default column widths (user can resize)
        self._skills_table.setColumnWidth(0, 300)  # Skill
        # Load Count is last - stretches to fill
        content_layout.addWidget(self._skills_table)

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def update_data(
        self,
        sessions: int,
        messages: int,
        tokens: str,
        cache_hit: str,
        agents: list[dict],
        tools: list[dict],
        skills: list[dict],
    ) -> None:
        """Update the analytics data."""
        # Update metrics
        self._metrics.update_metric("sessions", str(sessions))
        self._metrics.update_metric("messages", str(messages))
        self._metrics.update_metric("tokens", tokens)
        self._metrics.update_metric("cache_hit", cache_hit)

        # Update agents table
        self._agents_table.clear_data()
        total_tokens = sum(a.get("tokens", 0) for a in agents)
        for agent in agents[:10]:
            tokens_val = agent.get("tokens", 0)
            share = (
                f"{tokens_val / total_tokens * 100:.1f}%" if total_tokens > 0 else "0%"
            )
            self._agents_table.add_row(
                [
                    agent.get("agent", ""),
                    str(agent.get("messages", 0)),
                    self._format_tokens(tokens_val),
                    share,
                ]
            )

        # Update tools table
        self._tools_table.clear_data()
        for tool in tools[:10]:
            invocations = tool.get("invocations", 0)
            failures = tool.get("failures", 0)
            rate = f"{failures / invocations * 100:.1f}%" if invocations > 0 else "0%"
            self._tools_table.add_row(
                [
                    tool.get("tool_name", ""),
                    str(invocations),
                    str(failures),
                    rate,
                ]
            )

        # Update skills table
        self._skills_table.clear_data()
        for skill in skills[:10]:
            self._skills_table.add_row(
                [
                    skill.get("skill_name", ""),
                    str(skill.get("load_count", 0)),
                ]
            )

    def _on_period_changed(self, index: int) -> None:
        """Handle period selection change."""
        if 0 <= index < len(self.PERIODS):
            _, days = self.PERIODS[index]
            self._current_days = days
            # Emit signal for window to refresh data
            self.period_changed.emit(days)

    def get_current_period(self) -> int:
        """Get the currently selected period in days."""
        return self._current_days

    @staticmethod
    def _format_tokens(count: int) -> str:
        """Format token count for display."""
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        elif count >= 1_000:
            return f"{count / 1_000:.0f}K"
        return str(count)
