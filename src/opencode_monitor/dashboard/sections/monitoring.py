"""
Monitoring section - real-time agents and tools.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..widgets import (
    MetricsRow,
    DataTable,
    SectionHeader,
    Separator,
    PageHeader,
    EmptyState,
    StatusBadge,
)
from ..styles import COLORS, SPACING, COL_WIDTH, UI, format_duration_ms
from .colors import get_operation_variant


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
