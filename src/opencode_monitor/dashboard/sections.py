"""
Dashboard sections - Clean, minimal design.

Each section features:
- Clear page header
- Metric cards with accent colors
- Clean data tables
- Generous spacing
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal

from .widgets import (
    MetricsRow,
    DataTable,
    SectionHeader,
    Separator,
    PageHeader,
    EmptyState,
    SegmentedControl,
)
from .styles import COLORS, SPACING


# ============================================================
# COLOR MAPS FOR VISUAL DISTINCTION
# ============================================================

# Map operation types to color variants
OPERATION_TYPE_COLORS = {
    # Commands
    "command": "type-command",
    "bash": "type-command",
    "shell": "type-command",
    # File operations
    "read": "type-read",
    "write": "type-write",
    "edit": "type-edit",
    # Search & fetch
    "webfetch": "type-webfetch",
    "web_fetch": "type-webfetch",
    "glob": "type-glob",
    "grep": "type-grep",
    # Skills
    "skill": "type-webfetch",
    # Task management
    "todoread": "type-read",
    "todowrite": "type-write",
}


def get_operation_variant(operation: str) -> str:
    """Get the color variant for an operation type."""
    op_lower = operation.lower()
    return OPERATION_TYPE_COLORS.get(op_lower, "")


class MonitoringSection(QWidget):
    """Monitoring section - real-time agents and tools."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["3xl"], SPACING["2xl"], SPACING["3xl"], SPACING["2xl"]
        )
        layout.setSpacing(0)

        # Header
        header = PageHeader("Monitoring", "Real-time view of active agents and tools")
        layout.addWidget(header)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, SPACING["lg"], 0)
        content_layout.setSpacing(SPACING["2xl"])

        # Metrics
        self._metrics = MetricsRow()
        self._metrics.add_metric("instances", "0", "Instances", "primary")
        self._metrics.add_metric("agents", "0", "Agents", "primary")
        self._metrics.add_metric("busy", "0", "Busy", "success")
        self._metrics.add_metric("idle", "0", "Idle", "muted")
        self._metrics.add_metric("todos", "0", "Todos", "warning")
        self._metrics.add_stretch()
        content_layout.addWidget(self._metrics)

        content_layout.addWidget(Separator())

        # Active Agents
        content_layout.addWidget(
            SectionHeader("Active Agents", "Currently running sessions")
        )

        self._agents_table = DataTable(
            ["Agent", "Directory", "Status", "Tools", "Todos"]
        )
        self._agents_table.setColumnWidth(0, 260)
        self._agents_table.setColumnWidth(1, 220)
        self._agents_table.setColumnWidth(2, 100)
        self._agents_table.setColumnWidth(3, 80)
        content_layout.addWidget(self._agents_table)

        self._agents_empty = EmptyState(
            icon="○",
            title="No active agents",
            subtitle="Start a Claude session to see it here",
        )
        self._agents_empty.hide()
        content_layout.addWidget(self._agents_empty)

        content_layout.addWidget(Separator())

        # Running Tools
        content_layout.addWidget(
            SectionHeader("Running Tools", "Tools currently executing")
        )

        self._tools_table = DataTable(["Tool", "Agent", "Arguments", "Duration"])
        self._tools_table.setColumnWidth(0, 120)
        self._tools_table.setColumnWidth(1, 180)
        self._tools_table.setColumnWidth(2, 360)
        content_layout.addWidget(self._tools_table)

        self._tools_empty = EmptyState(
            icon="○",
            title="No running tools",
            subtitle="Tools will appear here when executing",
        )
        self._tools_empty.hide()
        content_layout.addWidget(self._tools_empty)

        content_layout.addStretch()
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
        """Update monitoring data."""
        self._metrics.update_metric("instances", str(instances))
        self._metrics.update_metric("agents", str(agents))
        self._metrics.update_metric("busy", str(busy))
        self._metrics.update_metric("idle", str(idle))
        self._metrics.update_metric("todos", str(todos))

        # Agents table
        self._agents_table.clear_data()

        if agents_data:
            self._agents_table.show()
            self._agents_empty.hide()

            for agent in agents_data:
                status = agent.get("status", "idle")
                status_class = "status-busy" if status == "busy" else "status-idle"
                status_text = "● BUSY" if status == "busy" else "○ IDLE"

                title = agent.get("title", "Unknown")
                directory = agent.get("dir", "")

                self._agents_table.add_row(
                    [
                        title,
                        directory,
                        (status_text, status_class),
                        str(len(agent.get("tools", []))),
                        str(agent.get("todos_total", 0)),
                    ],
                    full_values=[title, directory, "", "", ""],
                )
        else:
            self._agents_table.hide()
            self._agents_empty.show()

        # Tools table
        self._tools_table.clear_data()

        if tools_data:
            self._tools_table.show()
            self._tools_empty.hide()

            for tool in tools_data:
                elapsed = tool.get("elapsed_ms", 0)
                if elapsed >= 60000:
                    duration = f"{elapsed // 60000}m {(elapsed % 60000) // 1000}s"
                elif elapsed >= 1000:
                    duration = f"{elapsed // 1000}s"
                else:
                    duration = f"{elapsed}ms"

                tool_name = tool.get("name", "")
                tool_variant = get_operation_variant(tool_name)
                arg = tool.get("arg", "")

                self._tools_table.add_row(
                    [
                        (tool_name.upper(), tool_variant)
                        if tool_variant
                        else tool_name,
                        tool.get("agent", ""),
                        arg,
                        duration,
                    ],
                    full_values=[
                        tool_name,
                        tool.get("agent", ""),
                        arg,
                        duration,
                    ],
                )
        else:
            self._tools_table.hide()
            self._tools_empty.show()


class SecuritySection(QWidget):
    """Security section - risk analysis."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["3xl"], SPACING["2xl"], SPACING["3xl"], SPACING["2xl"]
        )
        layout.setSpacing(0)

        header = PageHeader("Security", "Risk analysis of executed operations")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, SPACING["lg"], 0)
        content_layout.setSpacing(SPACING["2xl"])

        # Metrics
        self._metrics = MetricsRow()
        self._metrics.add_metric("total", "0", "Analyzed", "primary")
        self._metrics.add_metric("critical", "0", "Critical", "error")
        self._metrics.add_metric("high", "0", "High", "warning")
        self._metrics.add_metric("medium", "0", "Medium", "warning")
        self._metrics.add_metric("low", "0", "Low", "success")
        self._metrics.add_stretch()
        content_layout.addWidget(self._metrics)

        content_layout.addWidget(Separator())

        # Critical Alerts
        content_layout.addWidget(
            SectionHeader("Critical Alerts", "High-risk operations")
        )

        self._critical_table = DataTable(["Type", "Details", "Risk", "Reason"])
        self._critical_table.setColumnWidth(0, 100)
        self._critical_table.setColumnWidth(1, 360)
        self._critical_table.setColumnWidth(2, 100)
        content_layout.addWidget(self._critical_table)

        self._critical_empty = EmptyState(
            icon="✓",
            title="No critical alerts",
            subtitle="All operations within normal risk levels",
        )
        self._critical_empty.hide()
        content_layout.addWidget(self._critical_empty)

        content_layout.addWidget(Separator())

        # Recent Commands
        content_layout.addWidget(
            SectionHeader("Recent Commands", "Last analyzed commands")
        )

        self._commands_table = DataTable(["Command", "Risk", "Score", "Reason"])
        self._commands_table.setColumnWidth(0, 400)
        self._commands_table.setColumnWidth(1, 100)
        self._commands_table.setColumnWidth(2, 80)
        content_layout.addWidget(self._commands_table)

        content_layout.addWidget(Separator())

        # File Operations
        content_layout.addWidget(
            SectionHeader("File Operations", "Recent reads and writes")
        )

        self._files_table = DataTable(["Operation", "Path", "Risk", "Score"])
        self._files_table.setColumnWidth(0, 100)
        self._files_table.setColumnWidth(1, 420)
        self._files_table.setColumnWidth(2, 100)
        content_layout.addWidget(self._files_table)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def update_data(
        self,
        stats: dict,
        commands: list[dict],
        files: list[dict],
        critical_items: list[dict] | None = None,
    ) -> None:
        """Update security data."""
        self._metrics.update_metric("total", str(stats.get("total", 0)))
        self._metrics.update_metric("critical", str(stats.get("critical", 0)))
        self._metrics.update_metric("high", str(stats.get("high", 0)))
        self._metrics.update_metric("medium", str(stats.get("medium", 0)))
        self._metrics.update_metric("low", str(stats.get("low", 0)))

        # Critical alerts
        self._critical_table.clear_data()

        if critical_items:
            sorted_items = sorted(
                critical_items, key=lambda x: x.get("score", 0), reverse=True
            )

            if sorted_items:
                self._critical_table.show()
                self._critical_empty.hide()

                for item in sorted_items[:20]:
                    risk = item.get("risk", "low").lower()
                    risk_class = f"risk-{risk}"
                    details = item.get("details", "")
                    reason = item.get("reason", "")
                    item_type = item.get("type", "")
                    type_variant = get_operation_variant(item_type)

                    self._critical_table.add_row(
                        [
                            (item_type.upper(), type_variant)
                            if type_variant
                            else item_type.upper(),
                            details,
                            (risk.upper(), risk_class),
                            reason,
                        ],
                        full_values=[
                            item_type.upper(),
                            details,
                            risk.upper(),
                            reason,
                        ],
                    )
            else:
                self._critical_table.hide()
                self._critical_empty.show()
        else:
            self._critical_table.hide()
            self._critical_empty.show()

        # Commands
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

        # Files
        self._files_table.clear_data()
        for f in files[:20]:
            risk = f.get("risk", "low").lower()
            risk_class = f"risk-{risk}"
            path = f.get("path", "")
            operation = f.get("operation", "")
            op_variant = get_operation_variant(operation)

            self._files_table.add_row(
                [
                    (operation.upper(), op_variant)
                    if op_variant
                    else operation.upper(),
                    path,
                    (risk.upper(), risk_class),
                    str(f.get("score", 0)),
                ],
                full_values=[
                    operation.upper(),
                    path,
                    risk.upper(),
                    str(f.get("score", 0)),
                ],
            )


class AnalyticsSection(QWidget):
    """Analytics section - usage statistics."""

    period_changed = pyqtSignal(int)

    PERIODS = [
        ("Last 24 hours", 1),
        ("Last 7 days", 7),
        ("Last 30 days", 30),
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_days = 7
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["3xl"], SPACING["2xl"], SPACING["3xl"], SPACING["2xl"]
        )
        layout.setSpacing(0)

        # Header with period selector
        header = PageHeader("Analytics", "Usage statistics and metrics")

        # Segmented control for period selection
        period_labels = [label for label, _ in self.PERIODS]
        self._period_control = SegmentedControl(period_labels)
        self._period_control.set_current_index(1)  # Default to 7 days
        self._period_control.selection_changed.connect(self._on_period_changed)
        header.add_action(self._period_control)

        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, SPACING["lg"], 0)
        content_layout.setSpacing(SPACING["2xl"])

        # Metrics
        self._metrics = MetricsRow()
        self._metrics.add_metric("sessions", "0", "Sessions", "primary")
        self._metrics.add_metric("messages", "0", "Messages", "primary")
        self._metrics.add_metric("tokens", "0", "Tokens", "warning")
        self._metrics.add_metric("cache_hit", "0%", "Cache Hit", "success")
        self._metrics.add_stretch()
        content_layout.addWidget(self._metrics)

        content_layout.addWidget(Separator())

        # Agent Usage
        content_layout.addWidget(
            SectionHeader("Agent Usage", "Token consumption by agent")
        )

        self._agents_table = DataTable(["Agent", "Messages", "Tokens", "Share"])
        self._agents_table.setColumnWidth(0, 360)
        self._agents_table.setColumnWidth(1, 120)
        self._agents_table.setColumnWidth(2, 120)
        content_layout.addWidget(self._agents_table)

        self._agents_empty = EmptyState(
            icon="○",
            title="No usage data",
            subtitle="Analytics will appear after some activity",
        )
        self._agents_empty.hide()
        content_layout.addWidget(self._agents_empty)

        content_layout.addWidget(Separator())

        # Top Tools
        content_layout.addWidget(
            SectionHeader("Top Tools", "Most frequently used tools")
        )

        self._tools_table = DataTable(
            ["Tool", "Invocations", "Failures", "Failure Rate"]
        )
        self._tools_table.setColumnWidth(0, 200)
        self._tools_table.setColumnWidth(1, 120)
        self._tools_table.setColumnWidth(2, 100)
        content_layout.addWidget(self._tools_table)

        content_layout.addWidget(Separator())

        # Skills
        content_layout.addWidget(SectionHeader("Skills Loaded", "Custom skills used"))

        self._skills_table = DataTable(["Skill", "Load Count"])
        self._skills_table.setColumnWidth(0, 380)
        content_layout.addWidget(self._skills_table)

        content_layout.addStretch()
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
        """Update analytics data."""
        self._metrics.update_metric("sessions", str(sessions))
        self._metrics.update_metric("messages", str(messages))
        self._metrics.update_metric("tokens", tokens)
        self._metrics.update_metric("cache_hit", cache_hit)

        # Agents
        self._agents_table.clear_data()

        if agents:
            self._agents_table.show()
            self._agents_empty.hide()

            total_tokens = sum(a.get("tokens", 0) for a in agents)
            for agent in agents[:10]:
                tokens_val = agent.get("tokens", 0)
                share = (
                    f"{tokens_val / total_tokens * 100:.1f}%"
                    if total_tokens > 0
                    else "0%"
                )

                self._agents_table.add_row(
                    [
                        agent.get("agent", ""),
                        str(agent.get("messages", 0)),
                        self._format_tokens(tokens_val),
                        share,
                    ]
                )
        else:
            self._agents_table.hide()
            self._agents_empty.show()

        # Tools
        self._tools_table.clear_data()
        for tool in tools[:10]:
            invocations = tool.get("invocations", 0)
            failures = tool.get("failures", 0)
            rate = f"{failures / invocations * 100:.1f}%" if invocations > 0 else "0%"
            tool_name = tool.get("tool_name", "")
            tool_variant = get_operation_variant(tool_name)

            self._tools_table.add_row(
                [
                    (tool_name, tool_variant) if tool_variant else tool_name,
                    str(invocations),
                    str(failures),
                    rate,
                ]
            )

        # Skills
        self._skills_table.clear_data()
        for skill in skills[:10]:
            self._skills_table.add_row(
                [
                    skill.get("skill_name", ""),
                    str(skill.get("load_count", 0)),
                ]
            )

    def _on_period_changed(self, index: int) -> None:
        if 0 <= index < len(self.PERIODS):
            _, days = self.PERIODS[index]
            self._current_days = days
            self.period_changed.emit(days)

    def get_current_period(self) -> int:
        return self._current_days

    @staticmethod
    def _format_tokens(count: int) -> str:
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        elif count >= 1_000:
            return f"{count / 1_000:.0f}K"
        return str(count)
