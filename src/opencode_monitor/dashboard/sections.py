"""
Dashboard sections - Modern, minimal design.

Each section features:
- Clear page header with actions
- Metric cards with centered values
- Enhanced data tables
- Generous spacing (8px based)
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
    StatusBadge,
)
from .styles import COLORS, SPACING, COL_WIDTH, UI, format_tokens, format_duration_ms


# ============================================================
# COLOR MAPS FOR VISUAL DISTINCTION
# ============================================================

# Map operation types to color variants
OPERATION_TYPE_COLORS = {
    # Commands
    "command": "type-command",
    "bash": "type-bash",
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
    "skill": "type-skill",
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

    # Signal emitted when user double-clicks to open terminal
    open_terminal_requested = pyqtSignal(str)  # agent_id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_table_signals()

    def _connect_table_signals(self) -> None:
        """Connect double-click signals for opening terminal."""
        self._agents_table.cellDoubleClicked.connect(self._on_agents_double_click)
        self._waiting_table.cellDoubleClicked.connect(self._on_waiting_double_click)

        # Set pointing hand cursor to indicate clickable rows
        self._agents_table.setCursor(Qt.CursorShape.PointingHandCursor)
        self._waiting_table.setCursor(Qt.CursorShape.PointingHandCursor)

    def _on_agents_double_click(self, row: int, _col: int) -> None:
        """Handle double-click on agents table."""
        item = self._agents_table.item(row, 0)
        if item:
            agent_id = item.data(Qt.ItemDataRole.UserRole)
            if agent_id:
                self.open_terminal_requested.emit(agent_id)

    def _on_waiting_double_click(self, row: int, _col: int) -> None:
        """Handle double-click on waiting table."""
        item = self._waiting_table.item(row, 0)
        if item:
            agent_id = item.data(Qt.ItemDataRole.UserRole)
            if agent_id:
                self.open_terminal_requested.emit(agent_id)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"]
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
        content_layout.setContentsMargins(0, 0, SPACING["md"], 0)
        content_layout.setSpacing(SPACING["xl"])

        # Metrics Row (6 cards)
        self._metrics = MetricsRow()
        self._metrics.add_metric("instances", "0", "Instances", "primary")
        self._metrics.add_metric("agents", "0", "Agents", "primary")
        self._metrics.add_metric("busy", "0", "Busy", "success")
        self._metrics.add_metric("waiting", "0", "Waiting", "warning")
        self._metrics.add_metric("idle", "0", "Idle", "muted")
        self._metrics.add_metric("todos", "0", "Todos", "warning")
        self._metrics.add_stretch()
        content_layout.addWidget(self._metrics)

        content_layout.addWidget(Separator())

        # Active Agents Section
        content_layout.addWidget(
            SectionHeader("Active Agents", "Currently running sessions")
        )

        self._agents_table = DataTable(
            ["Agent", "Directory", "Status", "Tools", "Todos"]
        )
        self._agents_table.setColumnWidth(0, COL_WIDTH["name_long"])  # Agent name
        self._agents_table.setColumnWidth(1, COL_WIDTH["path"])  # Directory
        self._agents_table.setColumnWidth(2, COL_WIDTH["status"])  # Status (BUSY/IDLE)
        self._agents_table.setColumnWidth(3, COL_WIDTH["number_tiny"])  # Tools count
        content_layout.addWidget(self._agents_table)

        self._agents_empty = EmptyState(
            icon="○",
            title="No active agents",
            subtitle="Start a Claude session to see it here",
        )
        self._agents_empty.hide()
        content_layout.addWidget(self._agents_empty)

        content_layout.addWidget(Separator())

        # Running Tools Section
        content_layout.addWidget(
            SectionHeader("Running Tools", "Tools currently executing")
        )

        self._tools_table = DataTable(["Tool", "Agent", "Arguments", "Duration"])
        self._tools_table.setColumnWidth(0, COL_WIDTH["type"])  # Tool type
        self._tools_table.setColumnWidth(1, COL_WIDTH["name_short"])  # Agent name
        self._tools_table.setColumnWidth(2, COL_WIDTH["path"])  # Arguments
        content_layout.addWidget(self._tools_table)

        self._tools_empty = EmptyState(
            icon="○",
            title="No tools currently running",
            subtitle="Tools will appear here when executing",
        )
        self._tools_empty.hide()
        content_layout.addWidget(self._tools_empty)

        content_layout.addWidget(Separator())

        # Waiting for Response Section
        content_layout.addWidget(
            SectionHeader("Waiting for Response", "Agents waiting for user input")
        )

        self._waiting_table = DataTable(["Title", "Question", "Options", "Context"])
        self._waiting_table.setColumnWidth(0, COL_WIDTH["name_short"])  # Title
        self._waiting_table.setColumnWidth(1, COL_WIDTH["path"])  # Question (truncated)
        self._waiting_table.setColumnWidth(2, COL_WIDTH["name_short"])  # Options
        self._waiting_table.setColumnWidth(
            3, COL_WIDTH["name_short"]
        )  # Context (repo @ branch)
        content_layout.addWidget(self._waiting_table)

        self._waiting_empty = EmptyState(
            icon="✓",
            title="No agents waiting",
            subtitle="Agents will appear here when asking for user input",
        )
        self._waiting_empty.hide()
        content_layout.addWidget(self._waiting_empty)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def update_data(
        self,
        instances: int,
        agents: int,
        busy: int,
        waiting: int,
        idle: int,
        todos: int,
        agents_data: list[dict],
        tools_data: list[dict],
        waiting_data: list[dict] | None = None,
    ) -> None:
        """Update monitoring data."""
        self._metrics.update_metric("instances", str(instances))
        self._metrics.update_metric("agents", str(agents))
        self._metrics.update_metric("busy", str(busy))
        self._metrics.update_metric("waiting", str(waiting))
        self._metrics.update_metric("idle", str(idle))
        self._metrics.update_metric("todos", str(todos))

        # Agents table
        self._agents_table.clear_data()

        if agents_data:
            self._agents_table.show()
            self._agents_empty.hide()

            for agent in agents_data:
                status = agent.get("status", "idle")
                title = agent.get("title", "Unknown")
                directory = agent.get("dir", "")
                agent_id = agent.get("agent_id", "")

                # Add row with placeholder for status (will be replaced by widget)
                self._agents_table.add_row(
                    [
                        title,
                        directory,
                        "",  # Placeholder for status badge
                        str(len(agent.get("tools", []))),
                        str(agent.get("todos_total", 0)),
                    ],
                    full_values=[title, directory, "", "", ""],
                )

                # Replace status cell with StatusBadge widget
                row = self._agents_table.rowCount() - 1
                status_badge = StatusBadge(
                    "BUSY" if status == "busy" else "IDLE",
                    "success" if status == "busy" else "neutral",
                )
                self._agents_table.setCellWidget(row, 2, status_badge)

                # Store agent_id for double-click handling
                first_item = self._agents_table.item(row, 0)
                if first_item:
                    first_item.setData(Qt.ItemDataRole.UserRole, agent_id)
        else:
            self._agents_table.hide()
            self._agents_empty.show()

        # Tools table
        self._tools_table.clear_data()

        if tools_data:
            self._tools_table.show()
            self._tools_empty.hide()

            for tool in tools_data:
                duration = format_duration_ms(tool.get("elapsed_ms", 0))
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

        # Waiting for Response table
        self._waiting_table.clear_data()

        if waiting_data:
            self._waiting_table.show()
            self._waiting_empty.hide()

            for agent in waiting_data:
                title = agent.get("title", "Unknown")
                question = agent.get("question", "")
                options = agent.get("options", "")
                context = agent.get("context", "")
                agent_id = agent.get("agent_id", "")

                # Truncate question to 80 chars for display
                question_display = (
                    question[:80] + "..." if len(question) > 80 else question
                )

                self._waiting_table.add_row(
                    [title, question_display, options, context],
                    full_values=[title, question, options, context],
                )

                # Store agent_id for double-click handling
                row = self._waiting_table.rowCount() - 1
                first_item = self._waiting_table.item(row, 0)
                if first_item:
                    first_item.setData(Qt.ItemDataRole.UserRole, agent_id)
        else:
            self._waiting_table.hide()
            self._waiting_empty.show()


class SecuritySection(QWidget):
    """Security section - risk analysis."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"]
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
        content_layout.setContentsMargins(0, 0, SPACING["md"], 0)
        content_layout.setSpacing(SPACING["xl"])

        # Security Metrics (5 cards with risk colors)
        self._metrics = MetricsRow()
        self._metrics.add_metric("total", "0", "Analyzed", "primary")
        self._metrics.add_metric("critical", "0", "Critical", "error")
        self._metrics.add_metric("high", "0", "High", "warning")
        self._metrics.add_metric("medium", "0", "Medium", "warning")
        self._metrics.add_metric("low", "0", "Low", "success")
        self._metrics.add_stretch()
        content_layout.addWidget(self._metrics)

        content_layout.addWidget(Separator())

        # Critical Alerts Section
        content_layout.addWidget(
            SectionHeader("Critical Alerts", "High-risk operations requiring attention")
        )

        self._critical_table = DataTable(["Type", "Details", "Risk", "Reason"])
        self._critical_table.setColumnWidth(0, COL_WIDTH["type"])  # Operation type
        self._critical_table.setColumnWidth(1, COL_WIDTH["path"])  # Details/path
        self._critical_table.setColumnWidth(2, COL_WIDTH["risk"])  # Risk level
        content_layout.addWidget(self._critical_table)

        self._critical_empty = EmptyState(
            icon="✓",
            title="No critical alerts",
            subtitle="All operations within normal risk levels",
        )
        self._critical_empty.hide()
        content_layout.addWidget(self._critical_empty)

        content_layout.addWidget(Separator())

        # Recent Commands Section
        content_layout.addWidget(
            SectionHeader("Recent Commands", "Last analyzed shell commands")
        )

        self._commands_table = DataTable(["Command", "Risk", "Score", "Reason"])
        self._commands_table.setColumnWidth(0, COL_WIDTH["path"])  # Command (long text)
        self._commands_table.setColumnWidth(1, COL_WIDTH["risk"])  # Risk level
        self._commands_table.setColumnWidth(2, COL_WIDTH["number_tiny"])  # Score
        self._commands_table.setColumnWidth(2, 80)
        content_layout.addWidget(self._commands_table)

        content_layout.addWidget(Separator())

        # File Operations Section
        content_layout.addWidget(
            SectionHeader("File Operations", "Recent file reads and writes")
        )

        self._files_table = DataTable(["Operation", "Path", "Risk", "Score"])
        self._files_table.setColumnWidth(0, COL_WIDTH["type"])  # Operation type
        self._files_table.setColumnWidth(1, COL_WIDTH["path"])  # File path
        self._files_table.setColumnWidth(2, COL_WIDTH["risk"])  # Risk level
        self._files_table.setColumnWidth(3, COL_WIDTH["number_tiny"])  # Score
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

                for item in sorted_items[: UI["table_row_limit"]]:
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
        for cmd in commands[: UI["table_row_limit"]]:
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
        for f in files[: UI["table_row_limit"]]:
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
        ("24h", 1),
        ("7d", 7),
        ("30d", 30),
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_days = 7
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"]
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
        content_layout.setContentsMargins(0, 0, SPACING["md"], 0)
        content_layout.setSpacing(SPACING["xl"])

        # Usage Metrics (4 cards)
        self._metrics = MetricsRow()
        self._metrics.add_metric("sessions", "0", "Sessions", "primary")
        self._metrics.add_metric("messages", "0", "Messages", "primary")
        self._metrics.add_metric("tokens", "0", "Tokens", "warning")
        self._metrics.add_metric("cache_hit", "0%", "Cache Hit", "success")
        self._metrics.add_stretch()
        content_layout.addWidget(self._metrics)

        content_layout.addWidget(Separator())

        # Agent Usage Section
        content_layout.addWidget(
            SectionHeader("Agent Usage", "Token consumption by agent")
        )

        self._agents_table = DataTable(["Agent", "Messages", "Tokens", "Share"])
        self._agents_table.setColumnWidth(0, COL_WIDTH["path"])  # Agent name (long)
        self._agents_table.setColumnWidth(
            1, COL_WIDTH["number_small"]
        )  # Messages count
        self._agents_table.setColumnWidth(
            2, COL_WIDTH["number_medium"]
        )  # Tokens (formatted)
        self._agents_table.setColumnWidth(3, COL_WIDTH["percentage"])  # Share %
        content_layout.addWidget(self._agents_table)

        self._agents_empty = EmptyState(
            icon="○",
            title="No usage data",
            subtitle="Analytics will appear after some activity",
        )
        self._agents_empty.hide()
        content_layout.addWidget(self._agents_empty)

        content_layout.addWidget(Separator())

        # Top Tools Section
        content_layout.addWidget(
            SectionHeader("Top Tools", "Most frequently used tools")
        )

        self._tools_table = DataTable(
            ["Tool", "Invocations", "Failures", "Failure Rate"]
        )
        self._tools_table.setColumnWidth(0, COL_WIDTH["name_short"])  # Tool name
        self._tools_table.setColumnWidth(1, COL_WIDTH["number_small"])  # Invocations
        self._tools_table.setColumnWidth(2, COL_WIDTH["number_tiny"])  # Failures
        self._tools_table.setColumnWidth(3, COL_WIDTH["percentage"])  # Failure rate
        content_layout.addWidget(self._tools_table)

        content_layout.addWidget(Separator())

        # Skills Section
        content_layout.addWidget(SectionHeader("Skills Loaded", "Custom skills used"))

        self._skills_table = DataTable(["Skill", "Load Count"])
        self._skills_table.setColumnWidth(0, COL_WIDTH["path"])  # Skill name
        self._skills_table.setColumnWidth(1, COL_WIDTH["number_small"])  # Load count
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
            for agent in agents[: UI["top_items_limit"]]:
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
                        format_tokens(tokens_val),
                        share,
                    ]
                )
        else:
            self._agents_table.hide()
            self._agents_empty.show()

        # Tools with type badges
        self._tools_table.clear_data()
        for tool in tools[: UI["top_items_limit"]]:
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
        for skill in skills[: UI["top_items_limit"]]:
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
        """Get the currently selected period in days."""
        return self._current_days
