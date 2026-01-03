"""
Tracing section - Agent execution traces visualization.

Displays hierarchical view of agent delegations with timing and prompts.
Provides detailed session analysis with tabs for different metrics.
"""

from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QComboBox,
    QLabel,
    QProgressBar,
    QFrame,
    QPushButton,
    QHeaderView,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QGridLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

from ..widgets import (
    PageHeader,
    SectionHeader,
    EmptyState,
    MetricsRow,
    Separator,
    RiskBadge,
    StatusBadge,
)
from ..styles import COLORS, SPACING, FONTS, RADIUS, UI

if TYPE_CHECKING:
    from ...analytics import TracingDataService


def format_duration(ms: Optional[int]) -> str:
    """Format duration in milliseconds to human readable."""
    if ms is None:
        return "..."
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    else:
        minutes = ms // 60000
        seconds = (ms % 60000) // 1000
        return f"{minutes}m {seconds}s"


def format_tokens_short(tokens: Optional[int]) -> str:
    """Format tokens to short form like 1.2K."""
    if tokens is None:
        return "-"
    if tokens < 1000:
        return str(tokens)
    elif tokens < 1000000:
        return f"{tokens / 1000:.1f}K"
    else:
        return f"{tokens / 1000000:.1f}M"


class DurationBar(QProgressBar):
    """Custom progress bar for visualizing relative duration."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setFixedHeight(6)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS["border_default"]};
                border: none;
                border-radius: 3px;
                margin: 0 {SPACING["sm"]}px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 {COLORS["accent_primary"]},
                    stop: 1 {COLORS["accent_primary_hover"]}
                );
                border-radius: 3px;
            }}
        """)


class CollapsibleTextEdit(QFrame):
    """Collapsible text section with header."""

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._expanded = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])

        # Header with expand/collapse
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(SPACING["sm"])

        self._arrow = QLabel("▼")
        self._arrow.setStyleSheet(f"""
            color: {COLORS["text_muted"]};
            font-size: 10px;
        """)
        self._arrow.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self._arrow)

        self._title = QLabel(title)
        self._title.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            font-weight: {FONTS["weight_medium"]};
        """)
        self._title.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self._title)
        header_layout.addStretch()

        header.mousePressEvent = lambda a0: self.toggle()
        layout.addWidget(header)

        # Text content
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS["bg_hover"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: 8px;
                padding: {SPACING["sm"]}px;
                color: {COLORS["text_primary"]};
                font-family: "SF Mono", Menlo, monospace;
                font-size: {FONTS["size_sm"]}px;
            }}
        """)
        self._text.setMinimumHeight(100)
        self._text.setMaximumHeight(300)
        layout.addWidget(self._text)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._text.setVisible(self._expanded)
        self._arrow.setText("▼" if self._expanded else "▶")

    def set_title(self, title: str) -> None:
        """Change the section title."""
        self._title.setText(title)

    def set_text(self, text: str) -> None:
        self._text.setPlainText(text)


# =============================================================================
# Tab Widgets for TraceDetailPanel
# =============================================================================


class HorizontalBar(QFrame):
    """Horizontal bar chart for simple value visualization."""

    def __init__(
        self,
        value: int,
        max_value: int,
        label: str = "",
        color: str = COLORS["accent_primary"],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._value = value
        self._max_value = max_value
        self._label = label
        self._color = color

        self.setMinimumHeight(28)
        self.setMaximumHeight(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(SPACING["sm"])

        # Label
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            min-width: 80px;
        """)
        layout.addWidget(label_widget)

        # Bar container
        bar_container = QFrame()
        bar_container.setStyleSheet(f"""
            background-color: {COLORS["bg_hover"]};
            border-radius: 4px;
        """)
        bar_container.setFixedHeight(16)

        bar_layout = QHBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)

        # Bar fill
        percentage = min(100, int((value / max_value) * 100)) if max_value > 0 else 0
        bar_fill = QFrame()
        bar_fill.setStyleSheet(f"""
            background-color: {color};
            border-radius: 4px;
        """)
        bar_fill.setFixedHeight(16)
        bar_fill.setMinimumWidth(max(2, percentage * 2))
        bar_layout.addWidget(bar_fill)
        bar_layout.addStretch()

        layout.addWidget(bar_container, stretch=1)

        # Value
        value_widget = QLabel(format_tokens_short(value))
        value_widget.setStyleSheet(f"""
            color: {COLORS["text_primary"]};
            font-size: {FONTS["size_sm"]}px;
            font-weight: {FONTS["weight_medium"]};
            min-width: 50px;
            text-align: right;
        """)
        value_widget.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(value_widget)


class PromptsTab(QWidget):
    """Tab displaying user prompt and final output."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING["md"], 0, 0)
        layout.setSpacing(SPACING["md"])

        # User prompt section
        self._input_section = CollapsibleTextEdit("💬 User Prompt")
        layout.addWidget(self._input_section)

        # Final output section
        self._output_section = CollapsibleTextEdit("📤 Final Output")
        layout.addWidget(self._output_section)

        layout.addStretch()

    def load_data(self, data: dict) -> None:
        """Load prompts data from TracingDataService response."""
        self._loaded = True
        prompt_input = data.get("prompt_input", "")
        prompt_output = data.get("prompt_output", "")

        self._input_section.set_text(prompt_input or "(No user prompt)")
        self._output_section.set_text(prompt_output or "(No output yet)")

    def is_loaded(self) -> bool:
        return self._loaded

    def clear(self) -> None:
        self._loaded = False
        self._input_section.set_text("")
        self._output_section.set_text("")


class TokensTab(QWidget):
    """Tab displaying token usage breakdown with mini-charts."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING["md"], 0, 0)
        layout.setSpacing(SPACING["lg"])

        # Summary row
        self._summary = QLabel("")
        self._summary.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            padding: {SPACING["sm"]}px;
            background-color: {COLORS["bg_hover"]};
            border-radius: {RADIUS["sm"]}px;
        """)
        layout.addWidget(self._summary)

        # Token breakdown section
        breakdown_label = QLabel("Token Breakdown")
        breakdown_label.setStyleSheet(f"""
            color: {COLORS["text_primary"]};
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_semibold"]};
        """)
        layout.addWidget(breakdown_label)

        # Bars container
        self._bars_container = QWidget()
        self._bars_layout = QVBoxLayout(self._bars_container)
        self._bars_layout.setContentsMargins(0, 0, 0, 0)
        self._bars_layout.setSpacing(SPACING["xs"])
        layout.addWidget(self._bars_container)

        # By agent section
        agent_label = QLabel("By Agent")
        agent_label.setStyleSheet(f"""
            color: {COLORS["text_primary"]};
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_semibold"]};
            margin-top: {SPACING["md"]}px;
        """)
        layout.addWidget(agent_label)

        self._agent_container = QWidget()
        self._agent_layout = QVBoxLayout(self._agent_container)
        self._agent_layout.setContentsMargins(0, 0, 0, 0)
        self._agent_layout.setSpacing(SPACING["xs"])
        layout.addWidget(self._agent_container)

        layout.addStretch()

    def load_data(self, data: dict) -> None:
        """Load tokens data from TracingDataService response."""
        self._loaded = True

        details = data.get("details", {})
        summary = data.get("summary", {})

        # Update summary
        total = summary.get("total", 0)
        cache_ratio = summary.get("cache_hit_ratio", 0)
        self._summary.setText(
            f"Total: {format_tokens_short(total)}  •  Cache hit: {cache_ratio:.1f}%"
        )

        # Clear old bars
        while self._bars_layout.count():
            child = self._bars_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add token bars
        input_tokens = details.get("input", 0)
        output_tokens = details.get("output", 0)
        cache_tokens = details.get("cache_read", 0)
        max_tokens = max(input_tokens, output_tokens, cache_tokens, 1)

        self._bars_layout.addWidget(
            HorizontalBar(input_tokens, max_tokens, "Input", COLORS["info"])
        )
        self._bars_layout.addWidget(
            HorizontalBar(output_tokens, max_tokens, "Output", COLORS["success"])
        )
        self._bars_layout.addWidget(
            HorizontalBar(cache_tokens, max_tokens, "Cache", COLORS["type_skill"])
        )

        # Clear old agent bars
        while self._agent_layout.count():
            child = self._agent_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add agent bars
        by_agent = details.get("by_agent", [])
        if by_agent:
            max_agent_tokens = max((a.get("tokens", 0) for a in by_agent), default=1)
            for agent_data in by_agent[:5]:  # Top 5 agents
                agent_name = agent_data.get("agent", "unknown")
                tokens = agent_data.get("tokens", 0)
                self._agent_layout.addWidget(
                    HorizontalBar(
                        tokens, max_agent_tokens, agent_name, COLORS["accent_primary"]
                    )
                )
        else:
            no_data = QLabel("No agent breakdown available")
            no_data.setStyleSheet(
                f"color: {COLORS['text_muted']}; font-size: {FONTS['size_sm']}px;"
            )
            self._agent_layout.addWidget(no_data)

    def is_loaded(self) -> bool:
        return self._loaded

    def clear(self) -> None:
        self._loaded = False
        self._summary.setText("")
        while self._bars_layout.count():
            child = self._bars_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        while self._agent_layout.count():
            child = self._agent_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()


class ToolsTab(QWidget):
    """Tab displaying tool usage statistics."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING["md"], 0, 0)
        layout.setSpacing(SPACING["md"])

        # Summary
        self._summary = QLabel("")
        self._summary.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            padding: {SPACING["sm"]}px;
            background-color: {COLORS["bg_hover"]};
            border-radius: {RADIUS["sm"]}px;
        """)
        layout.addWidget(self._summary)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(
            ["Tool", "Count", "Avg Duration", "Errors"]
        )
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)

        # Style
        palette = self._table.palette()
        palette.setColor(palette.ColorRole.Base, QColor(COLORS["bg_surface"]))
        palette.setColor(palette.ColorRole.AlternateBase, QColor(COLORS["bg_elevated"]))
        self._table.setPalette(palette)

        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["md"]}px;
            }}
            QTableWidget::item {{
                padding: {SPACING["sm"]}px;
                color: {COLORS["text_secondary"]};
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS["sidebar_active"]};
            }}
            QHeaderView::section {{
                background-color: {COLORS["bg_elevated"]};
                color: {COLORS["text_muted"]};
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["sm"]}px;
                border: none;
                border-bottom: 1px solid {COLORS["border_default"]};
            }}
        """)

        header = self._table.horizontalHeader()
        if header:
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self._table)
        layout.addStretch()

    def load_data(self, data: dict) -> None:
        """Load tools data from TracingDataService response."""
        self._loaded = True

        summary = data.get("summary", {})
        details = data.get("details", {})

        # Update summary
        total = summary.get("total_calls", 0)
        unique = summary.get("unique_tools", 0)
        success_rate = summary.get("success_rate", 0)
        avg_duration = summary.get("avg_duration_ms", 0)

        self._summary.setText(
            f"Total: {total} calls  •  "
            f"Unique: {unique} tools  •  "
            f"Success: {success_rate:.1f}%  •  "
            f"Avg: {format_duration(avg_duration)}"
        )

        # Populate table
        self._table.setRowCount(0)
        top_tools = details.get("top_tools", [])

        for tool in top_tools:
            row = self._table.rowCount()
            self._table.insertRow(row)

            name_item = QTableWidgetItem(tool.get("name", ""))
            name_item.setForeground(QColor(COLORS["text_primary"]))
            self._table.setItem(row, 0, name_item)

            count_item = QTableWidgetItem(str(tool.get("count", 0)))
            self._table.setItem(row, 1, count_item)

            duration_item = QTableWidgetItem(
                format_duration(tool.get("avg_duration_ms"))
            )
            self._table.setItem(row, 2, duration_item)

            errors = tool.get("error_count", 0)
            error_item = QTableWidgetItem(str(errors))
            if errors > 0:
                error_item.setForeground(QColor(COLORS["error"]))
            self._table.setItem(row, 3, error_item)

    def is_loaded(self) -> bool:
        return self._loaded

    def clear(self) -> None:
        self._loaded = False
        self._summary.setText("")
        self._table.setRowCount(0)


class FilesTab(QWidget):
    """Tab displaying file operations with risk indicators."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING["md"], 0, 0)
        layout.setSpacing(SPACING["md"])

        # Summary
        self._summary = QLabel("")
        self._summary.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            padding: {SPACING["sm"]}px;
            background-color: {COLORS["bg_hover"]};
            border-radius: {RADIUS["sm"]}px;
        """)
        layout.addWidget(self._summary)

        # Operations breakdown
        self._operations_container = QWidget()
        ops_layout = QGridLayout(self._operations_container)
        ops_layout.setContentsMargins(0, SPACING["sm"], 0, 0)
        ops_layout.setSpacing(SPACING["md"])

        # Create operation cards
        self._reads_card = self._create_op_card("📖 Reads", "0", COLORS["type_read"])
        self._writes_card = self._create_op_card("✏️ Writes", "0", COLORS["type_write"])
        self._edits_card = self._create_op_card("📝 Edits", "0", COLORS["type_edit"])
        self._risk_card = self._create_op_card("⚠️ High Risk", "0", COLORS["error"])

        ops_layout.addWidget(self._reads_card, 0, 0)
        ops_layout.addWidget(self._writes_card, 0, 1)
        ops_layout.addWidget(self._edits_card, 1, 0)
        ops_layout.addWidget(self._risk_card, 1, 1)

        layout.addWidget(self._operations_container)
        layout.addStretch()

    def _create_op_card(self, label: str, value: str, color: str) -> QFrame:
        """Create a small operation card."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_hover"]};
                border-radius: {RADIUS["md"]}px;
                padding: {SPACING["md"]}px;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"]
        )
        card_layout.setSpacing(SPACING["xs"])

        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet(f"""
            font-size: {FONTS["size_xl"]}px;
            font-weight: {FONTS["weight_bold"]};
            color: {color};
        """)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(value_label)

        text_label = QLabel(label)
        text_label.setStyleSheet(f"""
            font-size: {FONTS["size_sm"]}px;
            color: {COLORS["text_muted"]};
        """)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(text_label)

        return card

    def _update_card_value(self, card: QFrame, value: str) -> None:
        """Update the value in an operation card."""
        value_label = card.findChild(QLabel, "value")
        if value_label:
            value_label.setText(value)

    def load_data(self, data: dict) -> None:
        """Load files data from TracingDataService response."""
        self._loaded = True

        summary = data.get("summary", {})

        reads = summary.get("total_reads", 0)
        writes = summary.get("total_writes", 0)
        edits = summary.get("total_edits", 0)
        high_risk = summary.get("high_risk_count", 0)

        self._summary.setText(
            f"Total operations: {reads + writes + edits}  •  High risk: {high_risk}"
        )

        self._update_card_value(self._reads_card, str(reads))
        self._update_card_value(self._writes_card, str(writes))
        self._update_card_value(self._edits_card, str(edits))
        self._update_card_value(self._risk_card, str(high_risk))

    def is_loaded(self) -> bool:
        return self._loaded

    def clear(self) -> None:
        self._loaded = False
        self._summary.setText("")
        self._update_card_value(self._reads_card, "0")
        self._update_card_value(self._writes_card, "0")
        self._update_card_value(self._edits_card, "0")
        self._update_card_value(self._risk_card, "0")


class AgentsTab(QWidget):
    """Tab displaying agent hierarchy with delegation info."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING["md"], 0, 0)
        layout.setSpacing(SPACING["md"])

        # Summary
        self._summary = QLabel("")
        self._summary.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            padding: {SPACING["sm"]}px;
            background-color: {COLORS["bg_hover"]};
            border-radius: {RADIUS["sm"]}px;
        """)
        layout.addWidget(self._summary)

        # Agents list
        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["md"]}px;
            }}
            QListWidget::item {{
                padding: {SPACING["sm"]}px {SPACING["md"]}px;
                border-bottom: 1px solid {COLORS["border_subtle"]};
                color: {COLORS["text_secondary"]};
            }}
            QListWidget::item:selected {{
                background-color: {COLORS["sidebar_active"]};
            }}
            QListWidget::item:hover {{
                background-color: {COLORS["bg_hover"]};
            }}
        """)
        layout.addWidget(self._list)

    def load_data(self, agents: list[dict]) -> None:
        """Load agents data from TracingDataService response."""
        self._loaded = True

        self._list.clear()

        if not agents:
            self._summary.setText("No agent data available")
            return

        # Update summary
        total_agents = len(agents)
        total_tokens = sum(a.get("tokens", 0) for a in agents)
        self._summary.setText(
            f"Agents: {total_agents}  •  "
            f"Total tokens: {format_tokens_short(total_tokens)}"
        )

        # Add agents to list
        for agent in agents:
            name = agent.get("agent", "unknown")
            tokens = agent.get("tokens", 0)
            msg_count = agent.get("message_count", 0)

            item = QListWidgetItem(
                f"🤖 {name}  •  {format_tokens_short(tokens)} tokens  •  {msg_count} messages"
            )
            self._list.addItem(item)

    def is_loaded(self) -> bool:
        return self._loaded

    def clear(self) -> None:
        self._loaded = False
        self._summary.setText("")
        self._list.clear()


class TimelineTab(QWidget):
    """Tab displaying chronological timeline of events."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING["md"], 0, 0)
        layout.setSpacing(SPACING["md"])

        # Summary
        self._summary = QLabel("")
        self._summary.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            padding: {SPACING["sm"]}px;
            background-color: {COLORS["bg_hover"]};
            border-radius: {RADIUS["sm"]}px;
        """)
        layout.addWidget(self._summary)

        # Timeline list
        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["md"]}px;
            }}
            QListWidget::item {{
                padding: {SPACING["sm"]}px {SPACING["md"]}px;
                border-bottom: 1px solid {COLORS["border_subtle"]};
                font-family: {FONTS["mono"]};
                font-size: {FONTS["size_sm"]}px;
            }}
            QListWidget::item:selected {{
                background-color: {COLORS["sidebar_active"]};
            }}
        """)
        layout.addWidget(self._list)

    def load_data(self, events: list[dict]) -> None:
        """Load timeline data from TracingDataService response."""
        self._loaded = True

        self._list.clear()

        if not events:
            self._summary.setText("No events recorded")
            return

        # Update summary
        total_events = len(events)
        tool_events = len([e for e in events if e.get("type") == "tool"])
        msg_events = len([e for e in events if e.get("type") == "message"])

        self._summary.setText(
            f"Events: {total_events}  •  "
            f"Messages: {msg_events}  •  "
            f"Tools: {tool_events}"
        )

        # Add events to list
        for event in events[:50]:  # Limit to 50 events
            event_type = event.get("type", "")
            timestamp = event.get("timestamp", "")

            if event_type == "message":
                role = event.get("role", "")
                tokens = event.get("tokens_in", 0) + event.get("tokens_out", 0)
                icon = "💬" if role == "user" else "🤖"
                text = f"{timestamp[:19]}  {icon} {role}  ({format_tokens_short(tokens)} tokens)"
            elif event_type == "tool":
                tool_name = event.get("tool_name", "")
                status = event.get("status", "")
                duration = event.get("duration_ms", 0)
                icon = (
                    "✅"
                    if status == "completed"
                    else "❌"
                    if status == "error"
                    else "⏳"
                )
                text = f"{timestamp[:19]}  🔧 {tool_name} {icon} ({format_duration(duration)})"
            else:
                text = f"{timestamp[:19]}  {event_type}"

            item = QListWidgetItem(text)
            if event_type == "tool" and event.get("status") == "error":
                item.setForeground(QColor(COLORS["error"]))
            else:
                item.setForeground(QColor(COLORS["text_secondary"]))
            self._list.addItem(item)

    def is_loaded(self) -> bool:
        return self._loaded

    def clear(self) -> None:
        self._loaded = False
        self._summary.setText("")
        self._list.clear()


# =============================================================================
# Main TraceDetailPanel with Tabs
# =============================================================================


class TraceDetailPanel(QFrame):
    """Panel showing detailed trace/session information with tabbed sections.

    Features:
    - Header with key metrics (duration, tokens, tools, files, agents, status)
    - 6 tabs: Prompts, Tokens, Tools, Files, Agents, Timeline
    - Lazy loading: only loads data for the active tab
    - TracingDataService integration
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("trace-detail")
        self.setMinimumWidth(400)

        # TracingDataService instance (lazy loaded)
        self._service: Optional["TracingDataService"] = None
        self._current_session_id: Optional[str] = None
        self._current_data: dict = {}

        self.setStyleSheet(f"""
            QFrame#trace-detail {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["lg"]}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["md"])

        # === Header Section ===
        self._setup_header(layout)

        # === Metrics Row ===
        self._setup_metrics(layout)

        # === Separator ===
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['border_default']};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # === Tab Widget ===
        self._setup_tabs(layout)

    def _setup_header(self, layout: QVBoxLayout) -> None:
        """Setup header with title and status."""
        header_row = QHBoxLayout()
        header_row.setSpacing(SPACING["sm"])

        self._header = QLabel("Select a session")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
        """)
        header_row.addWidget(self._header)
        header_row.addStretch()

        self._status_badge = QLabel("")
        self._status_badge.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            padding: {SPACING["xs"]}px {SPACING["sm"]}px;
            border-radius: {RADIUS["sm"]}px;
            background-color: {COLORS["success_muted"]};
            color: {COLORS["success"]};
        """)
        self._status_badge.hide()
        header_row.addWidget(self._status_badge)

        layout.addLayout(header_row)

    def _setup_metrics(self, layout: QVBoxLayout) -> None:
        """Setup metrics row with key KPIs."""
        metrics_container = QFrame()
        metrics_container.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_hover"]};
                border-radius: {RADIUS["md"]}px;
                padding: {SPACING["sm"]}px;
            }}
        """)

        metrics_layout = QHBoxLayout(metrics_container)
        metrics_layout.setContentsMargins(
            SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"]
        )
        metrics_layout.setSpacing(SPACING["lg"])

        # Create metrics labels
        self._metric_duration = self._create_metric("⏱", "0s", "Duration")
        self._metric_tokens = self._create_metric("🎫", "0", "Tokens")
        self._metric_tools = self._create_metric("🔧", "0", "Tools")
        self._metric_files = self._create_metric("📁", "0", "Files")
        self._metric_agents = self._create_metric("🤖", "0", "Agents")

        metrics_layout.addWidget(self._metric_duration)
        metrics_layout.addWidget(self._metric_tokens)
        metrics_layout.addWidget(self._metric_tools)
        metrics_layout.addWidget(self._metric_files)
        metrics_layout.addWidget(self._metric_agents)
        metrics_layout.addStretch()

        layout.addWidget(metrics_container)

    def _create_metric(self, icon: str, value: str, label: str) -> QWidget:
        """Create a single metric widget."""
        widget = QWidget()
        widget_layout = QVBoxLayout(widget)
        widget_layout.setContentsMargins(0, 0, 0, 0)
        widget_layout.setSpacing(2)

        # Value with icon
        value_label = QLabel(f"{icon} {value}")
        value_label.setObjectName("metric_value")
        value_label.setStyleSheet(f"""
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)
        widget_layout.addWidget(value_label)

        # Label
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            color: {COLORS["text_muted"]};
        """)
        widget_layout.addWidget(label_widget)

        return widget

    def _update_metric(self, metric_widget: QWidget, icon: str, value: str) -> None:
        """Update a metric widget's value."""
        value_label = metric_widget.findChild(QLabel, "metric_value")
        if value_label:
            value_label.setText(f"{icon} {value}")

    def _setup_tabs(self, layout: QVBoxLayout) -> None:
        """Setup tab widget with 6 sections."""
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["md"]}px;
                background-color: {COLORS["bg_surface"]};
                padding: {SPACING["sm"]}px;
            }}
            QTabBar::tab {{
                background-color: {COLORS["bg_elevated"]};
                color: {COLORS["text_secondary"]};
                padding: {SPACING["sm"]}px {SPACING["md"]}px;
                margin-right: 2px;
                border-top-left-radius: {RADIUS["sm"]}px;
                border-top-right-radius: {RADIUS["sm"]}px;
                font-size: {FONTS["size_sm"]}px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS["accent_primary_muted"]};
                color: {COLORS["accent_primary"]};
                font-weight: {FONTS["weight_semibold"]};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {COLORS["bg_hover"]};
                color: {COLORS["text_primary"]};
            }}
        """)

        # Create tabs
        self._prompts_tab = PromptsTab()
        self._tokens_tab = TokensTab()
        self._tools_tab = ToolsTab()
        self._files_tab = FilesTab()
        self._agents_tab = AgentsTab()
        self._timeline_tab = TimelineTab()

        self._tabs.addTab(self._prompts_tab, "💬 Prompts")
        self._tabs.addTab(self._tokens_tab, "📊 Tokens")
        self._tabs.addTab(self._tools_tab, "🔧 Tools")
        self._tabs.addTab(self._files_tab, "📁 Files")
        self._tabs.addTab(self._agents_tab, "🤖 Agents")
        self._tabs.addTab(self._timeline_tab, "⏱ Timeline")

        # Connect tab change for lazy loading
        self._tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self._tabs)

    def _get_service(self) -> "TracingDataService":
        """Lazy load TracingDataService."""
        if self._service is None:
            from ...analytics import TracingDataService

            self._service = TracingDataService()
        return self._service

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change - load data for new tab if needed."""
        if not self._current_session_id:
            return

        # Load data for the selected tab
        self._load_tab_data(index)

    def _load_tab_data(self, tab_index: int) -> None:
        """Load data for a specific tab."""
        if not self._current_session_id:
            return

        service = self._get_service()

        try:
            if tab_index == 0:  # Prompts
                if not self._prompts_tab.is_loaded():
                    self._prompts_tab.load_data(self._current_data)
            elif tab_index == 1:  # Tokens
                if not self._tokens_tab.is_loaded():
                    data = service.get_session_tokens(self._current_session_id)
                    self._tokens_tab.load_data(data)
            elif tab_index == 2:  # Tools
                if not self._tools_tab.is_loaded():
                    data = service.get_session_tools(self._current_session_id)
                    self._tools_tab.load_data(data)
            elif tab_index == 3:  # Files
                if not self._files_tab.is_loaded():
                    data = service.get_session_files(self._current_session_id)
                    self._files_tab.load_data(data)
            elif tab_index == 4:  # Agents
                if not self._agents_tab.is_loaded():
                    agents = service.get_session_agents(self._current_session_id)
                    self._agents_tab.load_data(agents)
            elif tab_index == 5:  # Timeline
                if not self._timeline_tab.is_loaded():
                    events = service.get_session_timeline(self._current_session_id)
                    self._timeline_tab.load_data(events)
        except Exception as e:
            from ...utils.logger import debug

            debug(f"Failed to load tab data: {e}")

    def show_session_summary(self, session_id: str) -> None:
        """Display complete session summary using TracingDataService.

        This is the main entry point for displaying session details.
        Loads summary data and updates all metrics. Tab data is lazy loaded.
        """
        import os

        self._current_session_id = session_id

        # Clear all tabs
        self._clear_tabs()

        # Get summary from service
        service = self._get_service()
        summary = service.get_session_summary(session_id)

        self._current_data = summary
        meta = summary.get("meta", {})
        s = summary.get("summary", {})
        details = summary.get("details", {})

        # Update header
        title = meta.get("title", "")
        directory = meta.get("directory", "")
        project_name = os.path.basename(directory) if directory else "Session"

        if title:
            header_text = f"🌳 {project_name}"
        else:
            header_text = f"🌳 {project_name}"

        self._header.setText(header_text)
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Update status badge
        status = s.get("status", "completed")
        if status == "completed":
            self._status_badge.setText("✅ Completed")
            self._status_badge.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
                background-color: {COLORS["success_muted"]};
                color: {COLORS["success"]};
            """)
        elif status == "running":
            self._status_badge.setText("⏳ Running")
            self._status_badge.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
                background-color: {COLORS["warning_muted"]};
                color: {COLORS["warning"]};
            """)
        else:
            self._status_badge.setText(f"● {status.capitalize()}")
            self._status_badge.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
                background-color: {COLORS["info_muted"]};
                color: {COLORS["info"]};
            """)
        self._status_badge.show()

        # Update metrics
        duration_ms = s.get("duration_ms", 0)
        total_tokens = s.get("total_tokens", 0)
        total_tools = s.get("total_tool_calls", 0)
        total_files = s.get("total_files", 0)
        unique_agents = s.get("unique_agents", 0)

        self._update_metric(self._metric_duration, "⏱", format_duration(duration_ms))
        self._update_metric(
            self._metric_tokens, "🎫", format_tokens_short(total_tokens)
        )
        self._update_metric(self._metric_tools, "🔧", str(total_tools))
        self._update_metric(self._metric_files, "📁", str(total_files))
        self._update_metric(self._metric_agents, "🤖", str(unique_agents))

        # Load data for current tab
        self._load_tab_data(self._tabs.currentIndex())

    def show_trace(
        self,
        agent: str,
        duration_ms: Optional[int],
        tokens_in: Optional[int],
        tokens_out: Optional[int],
        status: str,
        prompt_input: str,
        prompt_output: Optional[str],
        tools_used: list[str],
    ) -> None:
        """Display trace details (legacy method for compatibility)."""
        self._current_session_id = None
        self._clear_tabs()

        # Update header
        self._header.setText(f"Agent: {agent}")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Update status badge
        if status == "completed":
            self._status_badge.setText("✅ Completed")
            self._status_badge.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
                background-color: {COLORS["success_muted"]};
                color: {COLORS["success"]};
            """)
        elif status == "error":
            self._status_badge.setText("❌ Error")
            self._status_badge.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
                background-color: {COLORS["error_muted"]};
                color: {COLORS["error"]};
            """)
        else:
            self._status_badge.setText("⏳ Running")
            self._status_badge.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
                background-color: {COLORS["warning_muted"]};
                color: {COLORS["warning"]};
            """)
        self._status_badge.show()

        # Update metrics
        total_tokens = (tokens_in or 0) + (tokens_out or 0)
        self._update_metric(self._metric_duration, "⏱", format_duration(duration_ms))
        self._update_metric(
            self._metric_tokens, "🎫", format_tokens_short(total_tokens)
        )
        self._update_metric(self._metric_tools, "🔧", str(len(tools_used)))
        self._update_metric(self._metric_files, "📁", "-")
        self._update_metric(self._metric_agents, "🤖", "1")

        # Store for prompts tab
        self._current_data = {
            "prompt_input": prompt_input,
            "prompt_output": prompt_output,
        }

        # Load prompts tab (default)
        self._prompts_tab.load_data(self._current_data)
        self._tabs.setCurrentIndex(0)

    def show_session(
        self,
        title: str,
        agent_type: Optional[str],
        parent_agent: Optional[str],
        directory: str,
        created_at: Optional[datetime],
        trace_count: int,
        children_count: int,
        prompt_input: Optional[str] = None,
    ) -> None:
        """Display session details (legacy method for compatibility)."""
        import os

        self._current_session_id = None
        self._clear_tabs()

        # Determine if this is a ROOT session
        is_root = parent_agent is None and agent_type is None

        # Update header
        if agent_type and parent_agent:
            header_text = f"🔗 {agent_type} ← {parent_agent}"
        elif agent_type:
            header_text = f"Agent: {agent_type}"
        else:
            project_name = os.path.basename(directory) if directory else "Session"
            header_text = f"🌳 {project_name}"

        self._header.setText(header_text)
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Status badge
        self._status_badge.setText("📁 Session")
        self._status_badge.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            padding: {SPACING["xs"]}px {SPACING["sm"]}px;
            border-radius: {RADIUS["sm"]}px;
            background-color: {COLORS["info_muted"]};
            color: {COLORS["info"]};
        """)
        self._status_badge.show()

        # Update metrics
        self._update_metric(self._metric_duration, "⏱", "-")
        self._update_metric(self._metric_tokens, "🎫", "-")
        self._update_metric(self._metric_tools, "🔧", "-")
        self._update_metric(self._metric_files, "📁", str(trace_count))
        self._update_metric(self._metric_agents, "🤖", str(children_count))

        # Store for prompts tab
        output_text = f"Directory: {directory}\n"
        if is_root:
            output_text += "Type: Direct user conversation\n"
        output_text += f"Traces: {trace_count}\n"
        output_text += f"Sub-agents: {children_count}"

        self._current_data = {
            "prompt_input": prompt_input or title or "(No prompt)",
            "prompt_output": output_text,
        }

        # Load prompts tab
        self._prompts_tab.load_data(self._current_data)
        self._tabs.setCurrentIndex(0)

    def _clear_tabs(self) -> None:
        """Clear all tab data."""
        self._prompts_tab.clear()
        self._tokens_tab.clear()
        self._tools_tab.clear()
        self._files_tab.clear()
        self._agents_tab.clear()
        self._timeline_tab.clear()

    def clear(self) -> None:
        """Clear all trace details."""
        self._current_session_id = None
        self._current_data = {}

        self._header.setText("Select a session")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
        """)

        self._status_badge.hide()

        # Reset metrics
        self._update_metric(self._metric_duration, "⏱", "0s")
        self._update_metric(self._metric_tokens, "🎫", "0")
        self._update_metric(self._metric_tools, "🔧", "0")
        self._update_metric(self._metric_files, "📁", "0")
        self._update_metric(self._metric_agents, "🤖", "0")

        # Clear tabs
        self._clear_tabs()


class TracingSection(QWidget):
    """Tracing section - agent execution traces visualization."""

    # Signal when double-click to open terminal
    open_terminal_requested = pyqtSignal(str)  # session_id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._traces_data: list[dict] = []
        self._sessions_data: list[dict] = []
        self._session_hierarchy: list[dict] = []
        self._max_duration_ms: int = 1  # Avoid division by zero
        self._view_mode: str = "sessions"  # "traces" or "sessions"
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"]
        )
        layout.setSpacing(0)

        # Header row with title and metrics
        header_row = QHBoxLayout()
        header_row.setSpacing(SPACING["lg"])

        # Title
        title = QLabel("Agent Traces")
        title.setStyleSheet(f"""
            font-size: {FONTS["size_xl"]}px;
            font-weight: {FONTS["weight_bold"]};
            color: {COLORS["text_primary"]};
        """)
        header_row.addWidget(title)

        # Metrics inline
        self._metrics = MetricsRow()
        self._metrics.add_metric("traces", "0", "Traces", "primary")
        self._metrics.add_metric("agents", "0", "Agents", "primary")
        self._metrics.add_metric("duration", "0s", "Total", "warning")
        header_row.addWidget(self._metrics)

        header_row.addStretch()

        # Use a container for header actions
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, SPACING["sm"])
        header_layout.addLayout(header_row)

        # Session filter combo
        self._session_combo = QComboBox()
        self._session_combo.setMinimumWidth(200)
        self._session_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: 6px;
                padding: 6px 12px;
                color: {COLORS["text_primary"]};
                font-size: {FONTS["size_sm"]}px;
            }}
            QComboBox:hover {{
                border-color: {COLORS["border_strong"]};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: 6px;
                selection-background-color: {COLORS["bg_elevated"]};
            }}
        """)
        self._session_combo.addItem("All Sessions", "")
        header_layout.addWidget(self._session_combo)

        # View mode toggle button
        self._view_toggle = QPushButton("View: Sessions")
        self._view_toggle.setCheckable(True)
        self._view_toggle.setChecked(True)  # Sessions view by default
        self._view_toggle.setMinimumWidth(100)
        self._view_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS["bg_elevated"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["sm"]}px;
                padding: {SPACING["sm"]}px {SPACING["md"]}px;
                color: {COLORS["text_secondary"]};
                font-size: {FONTS["size_sm"]}px;
                font-weight: {FONTS["weight_medium"]};
            }}
            QPushButton:hover {{
                border-color: {COLORS["border_strong"]};
                color: {COLORS["text_primary"]};
            }}
            QPushButton:checked {{
                background-color: {COLORS["accent_primary_muted"]};
                border-color: {COLORS["accent_primary"]};
                color: {COLORS["accent_primary"]};
            }}
        """)
        self._view_toggle.clicked.connect(self._toggle_view_mode)
        header_layout.addWidget(self._view_toggle)

        layout.addWidget(header)

        # Main content with vertical splitter (tree on top, details below)
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setChildrenCollapsible(False)

        # Top: Tree view
        top_panel = QWidget()
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, SPACING["sm"], 0, 0)
        top_layout.setSpacing(0)

        # Tree widget
        self._tree = QTreeWidget()
        # Default to Sessions view headers (matching _view_mode = "sessions")
        self._tree.setHeaderLabels(
            ["Session / Agent", "Created", "Agents", "Traces", ""]
        )
        self._tree.setColumnWidth(0, 320)  # Wide for hierarchy
        self._tree.setColumnWidth(1, 130)  # Date
        self._tree.setColumnWidth(2, 70)  # Agents count
        self._tree.setColumnWidth(3, 70)  # Traces count
        self._tree.setColumnWidth(4, 40)  # Empty spacer
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(20)  # Clear visual indentation
        self._tree.setUniformRowHeights(True)  # Performance optimization

        # Set proper alternating colors via palette
        palette = self._tree.palette()
        palette.setColor(palette.ColorRole.Base, QColor(COLORS["bg_surface"]))
        palette.setColor(palette.ColorRole.AlternateBase, QColor(COLORS["bg_elevated"]))
        self._tree.setPalette(palette)

        self._tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["lg"]}px;
                outline: none;
            }}
            QTreeWidget::item {{
                padding: {SPACING["sm"]}px {SPACING["xs"]}px;
                border: none;
                min-height: 32px;
            }}
            QTreeWidget::item:selected {{
                background-color: {COLORS["sidebar_active"]};
                border-radius: {RADIUS["sm"]}px;
            }}
            QTreeWidget::item:hover:!selected {{
                background-color: {COLORS["bg_hover"]};
            }}
            QTreeWidget::branch {{
                background: transparent;
            }}
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {{
                image: none;
                border-image: none;
            }}
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {{
                image: none;
                border-image: none;
            }}
            QHeaderView {{
                background-color: transparent;
            }}
            QHeaderView::section {{
                background-color: {COLORS["bg_elevated"]};
                color: {COLORS["text_muted"]};
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: {SPACING["sm"]}px {SPACING["md"]}px;
                border: none;
                border-bottom: 1px solid {COLORS["border_default"]};
            }}
            QHeaderView::section:first {{
                border-top-left-radius: {RADIUS["lg"]}px;
            }}
            QHeaderView::section:last {{
                border-top-right-radius: {RADIUS["lg"]}px;
            }}
            QHeaderView::section:hover {{
                background-color: {COLORS["bg_hover"]};
                color: {COLORS["text_secondary"]};
            }}
        """)

        # Make columns resizable
        header = self._tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(50)

        top_layout.addWidget(self._tree)

        # Empty state
        self._empty = EmptyState(
            icon="◯",
            title="No traces found",
            subtitle="Traces will appear after agents are invoked via 'task' tool",
        )
        self._empty.hide()
        top_layout.addWidget(self._empty)

        self._splitter.addWidget(top_panel)

        # Bottom: Detail panel (full width)
        self._detail_panel = TraceDetailPanel()
        self._splitter.addWidget(self._detail_panel)

        # Set splitter proportions (60% tree, 40% details)
        self._splitter.setSizes([500, 300])

        layout.addWidget(self._splitter)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._session_combo.currentIndexChanged.connect(self._on_session_changed)

    def _toggle_view_mode(self) -> None:
        """Toggle between traces and sessions view."""
        if self._view_toggle.isChecked():
            self._view_mode = "sessions"
            self._view_toggle.setText("View: Sessions")
            # Update headers for session view
            self._tree.setHeaderLabels(
                ["Session / Agent", "Created", "Agents", "Traces", ""]
            )
            self._tree.setColumnWidth(0, 320)  # Wide for hierarchy
            self._tree.setColumnWidth(1, 130)
            self._tree.setColumnWidth(2, 70)
            self._tree.setColumnWidth(3, 70)
            self._tree.setColumnWidth(4, 40)
            self._populate_sessions_tree(self._session_hierarchy)
        else:
            self._view_mode = "traces"
            self._view_toggle.setText("View: Traces")
            # Update headers for traces view
            self._tree.setHeaderLabels(
                ["Agent", "Duration", "Tokens", "Status", "Timeline"]
            )
            self._tree.setColumnWidth(0, 200)
            self._tree.setColumnWidth(1, 90)
            self._tree.setColumnWidth(2, 80)
            self._tree.setColumnWidth(3, 90)
            self._tree.setColumnWidth(4, 120)
            self._populate_tree(self._traces_data)

    def _on_item_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        """Handle click on tree item - show details.

        In sessions view: Uses TracingDataService for rich session summary
        In traces view: Shows trace details with prompts
        """
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if self._view_mode == "sessions":
            # Session clicked - use TracingDataService for full summary
            session_id = data.get("session_id")

            if session_id:
                # Use new show_session_summary for rich data
                self._detail_panel.show_session_summary(session_id)
            else:
                # Fallback to legacy method if no session_id
                self._detail_panel.show_session(
                    title=data.get("title", ""),
                    agent_type=data.get("agent_type"),
                    parent_agent=data.get("parent_agent"),
                    directory=data.get("directory", ""),
                    created_at=data.get("created_at"),
                    trace_count=data.get("trace_count", 0),
                    children_count=len(data.get("children", [])),
                    prompt_input=data.get("prompt_input"),
                )
        else:
            # Trace data - show trace details
            self._detail_panel.show_trace(
                agent=data.get("subagent_type", ""),
                duration_ms=data.get("duration_ms"),
                tokens_in=data.get("tokens_in"),
                tokens_out=data.get("tokens_out"),
                status=data.get("status", ""),
                prompt_input=data.get("prompt_input", ""),
                prompt_output=data.get("prompt_output"),
                tools_used=data.get("tools_used", []),
            )

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        """Handle double-click - open terminal."""
        trace_data = item.data(0, Qt.ItemDataRole.UserRole)
        if trace_data:
            session_id = trace_data.get("session_id", "")
            if session_id:
                self.open_terminal_requested.emit(session_id)

    def _on_session_changed(self, _index: int) -> None:
        """Handle session filter change."""
        session_id = self._session_combo.currentData()
        self._filter_traces(session_id)

    def _filter_traces(self, session_id: Optional[str]) -> None:
        """Filter displayed traces by session."""
        if not session_id:
            filtered = self._traces_data
        else:
            filtered = [
                t for t in self._traces_data if t.get("session_id") == session_id
            ]
        self._populate_tree(filtered)

    def _populate_tree(self, traces: list[dict]) -> None:
        """Populate tree widget with traces."""
        # Skip if data hasn't changed (avoid expensive rebuilds)
        trace_ids = {t.get("trace_id") for t in traces}
        if hasattr(self, "_last_trace_ids") and self._last_trace_ids == trace_ids:
            return
        self._last_trace_ids = trace_ids

        # Disable updates during rebuild for performance
        self._tree.setUpdatesEnabled(False)
        try:
            self._tree.clear()

            if not traces:
                self._tree.hide()
                self._empty.show()
                self._detail_panel.clear()
                return

            self._tree.show()
            self._empty.hide()

            # Find max duration for timeline scaling
            self._max_duration_ms = (
                max((t.get("duration_ms") or 0 for t in traces), default=1) or 1
            )

            # Build hierarchy based on parent_trace_id
            traces_by_id: dict[str, dict] = {}
            for t in traces:
                tid = t.get("trace_id")
                if tid:
                    traces_by_id[tid] = t
            children_by_parent: dict[str, list[dict]] = {}
            root_traces: list[dict] = []

            for trace in traces:
                parent_id = trace.get("parent_trace_id")
                if parent_id and parent_id in traces_by_id:
                    # Has a parent in this dataset
                    if parent_id not in children_by_parent:
                        children_by_parent[parent_id] = []
                    children_by_parent[parent_id].append(trace)
                else:
                    # Root trace (no parent or parent not in dataset)
                    root_traces.append(trace)

            # Sort root traces: parents with children first (most recent), then others (most recent)
            def sort_key(t: dict) -> tuple:
                has_children = t.get("trace_id") in children_by_parent
                started = t.get("started_at") or datetime.min
                # Sort by: has_children DESC, started_at DESC
                return (
                    not has_children,
                    -started.timestamp() if started != datetime.min else 0,
                )

            root_traces.sort(key=sort_key)

            # Build tree recursively
            def add_with_children(parent_item: Optional[QTreeWidgetItem], trace: dict):
                item = self._add_trace_item(parent_item, trace)
                trace_id = trace.get("trace_id")
                if trace_id and trace_id in children_by_parent:
                    # Sort children by start time (most recent first)
                    children = sorted(
                        children_by_parent[trace_id],
                        key=lambda t: t.get("started_at") or datetime.min,
                        reverse=True,
                    )
                    for child in children:
                        add_with_children(item, child)

            for trace in root_traces:
                add_with_children(None, trace)

            # Collapse all by default - user can expand manually
            self._tree.collapseAll()
        finally:
            self._tree.setUpdatesEnabled(True)

    def _populate_sessions_tree(self, sessions: list[dict]) -> None:
        """Populate tree widget with session hierarchy.

        Root sessions show: 📁 project_name (from directory)
        Child sessions show: 🔗 agent_type ← parent_agent: title
        """
        # Skip if data hasn't changed
        session_ids = {s.get("session_id") for s in sessions}
        if hasattr(self, "_last_session_ids") and self._last_session_ids == session_ids:
            return
        self._last_session_ids = session_ids

        self._tree.setUpdatesEnabled(False)
        try:
            self._tree.clear()

            if not sessions:
                self._tree.hide()
                self._empty.show()
                self._detail_panel.clear()
                return

            self._tree.show()
            self._empty.hide()

            def format_datetime(dt: Optional[datetime]) -> str:
                """Format datetime for display."""
                if not dt:
                    return "-"
                return dt.strftime("%Y-%m-%d %H:%M")

            def get_project_name(directory: Optional[str]) -> str:
                """Extract project name from full path."""
                if not directory:
                    return "Unknown"
                # Get the last folder name
                import os

                return os.path.basename(directory.rstrip("/"))

            def extract_agent_from_title(title: Optional[str]) -> Optional[str]:
                """Extract agent type from title like 'Task (@agent_type'."""
                if not title:
                    return None
                # Look for pattern (@agent_type) or (@agent_type subagent)
                import re

                match = re.search(r"\(@(\w+)", title)
                if match:
                    return match.group(1)
                return None

            def add_session_item(
                parent_item: Optional[QTreeWidgetItem],
                session: dict,
                is_root: bool = False,
                depth: int = 0,
            ) -> QTreeWidgetItem:
                if parent_item:
                    item = QTreeWidgetItem(parent_item)
                else:
                    item = QTreeWidgetItem(self._tree)

                agent_type = session.get("agent_type")
                parent_agent = session.get("parent_agent")
                title = session.get("title") or ""
                directory = session.get("directory")
                created_at = session.get("created_at")
                trace_count = session.get("trace_count", 0)
                children_count = len(session.get("children", []))

                if is_root:
                    # Root session: show with tree icon (direct user conversation)
                    project = get_project_name(directory)
                    item.setText(0, f"🌳 {project}")
                    # Color root items with primary accent
                    item.setForeground(0, QColor(COLORS["tree_root"]))
                else:
                    # Child session: show agent delegation chain + title
                    # Try to extract agent from title if not in delegation table
                    effective_agent = agent_type or extract_agent_from_title(title)

                    # Use different icons based on depth for visual hierarchy
                    if depth == 1:
                        icon = "🔗"  # Link for first level delegation
                    else:
                        icon = "└─"  # Tree branch for deeper levels

                    if effective_agent and parent_agent:
                        # Show: parent → child (who called who)
                        label = f"{icon} {parent_agent} → {effective_agent}"
                    elif effective_agent:
                        label = f"{icon} {effective_agent}"
                    else:
                        label = f"{icon} subagent"

                    # Add truncated title (remove the (@agent) part for cleaner display)
                    if title:
                        # Remove (@agent...) suffix
                        import re

                        clean_title = re.sub(r"\s*\(@\w+.*\)$", "", title)
                        short_title = (
                            clean_title[:35] + "..."
                            if len(clean_title) > 35
                            else clean_title
                        )
                        if short_title.strip():
                            label = f"{label}: {short_title}"

                    item.setText(0, label)
                    # Color child items with softer purple
                    item.setForeground(0, QColor(COLORS["tree_child"]))

                # Date - secondary color
                item.setText(1, format_datetime(created_at))
                item.setForeground(1, QColor(COLORS["text_secondary"]))

                # Child sessions count
                if children_count > 0:
                    item.setText(2, str(children_count))
                    item.setForeground(2, QColor(COLORS["accent_primary"]))
                else:
                    item.setText(2, "-")
                    item.setForeground(2, QColor(COLORS["text_muted"]))

                # Trace count
                if trace_count > 0:
                    item.setText(3, str(trace_count))
                    item.setForeground(3, QColor(COLORS["text_secondary"]))
                else:
                    item.setText(3, "-")
                    item.setForeground(3, QColor(COLORS["text_muted"]))

                # Store session data for detail panel
                item.setData(0, Qt.ItemDataRole.UserRole, session)

                # Tooltip with full path
                if directory:
                    item.setToolTip(0, directory)

                # Add children recursively (children are already sorted chronologically)
                for child in session.get("children", []):
                    add_session_item(item, child, is_root=False, depth=depth + 1)

                return item

            # Add root sessions (they are sorted DESC - most recent first)
            for session in sessions:
                add_session_item(None, session, is_root=True, depth=0)

            # Expand first level by default to show structure
            self._tree.expandToDepth(0)

        finally:
            self._tree.setUpdatesEnabled(True)

    def _add_trace_item(
        self, parent: Optional[QTreeWidgetItem], trace: dict
    ) -> QTreeWidgetItem:
        """Add a trace item to the tree."""
        if parent:
            item = QTreeWidgetItem(parent)
        else:
            item = QTreeWidgetItem(self._tree)

        agent = trace.get("subagent_type", "unknown")
        duration_ms = trace.get("duration_ms")
        tokens_in = trace.get("tokens_in")
        status = trace.get("status", "running")

        # Status icon with semantic meaning
        if status == "completed":
            status_icon = "●"
            agent_color = QColor(COLORS["success"])
        elif status == "error":
            status_icon = "✕"
            agent_color = QColor(COLORS["error"])
        else:
            status_icon = "◐"  # Half-filled circle for running
            agent_color = QColor(COLORS["warning"])

        item.setText(0, f"{status_icon} {agent}")
        item.setForeground(0, agent_color)

        # Duration - secondary color
        item.setText(1, format_duration(duration_ms))
        item.setForeground(1, QColor(COLORS["text_secondary"]))

        # Tokens
        item.setText(2, format_tokens_short(tokens_in))
        item.setForeground(2, QColor(COLORS["text_secondary"]))

        # Status with capitalized text
        status_display = status.capitalize() if status else "-"
        item.setText(3, status_display)

        # Color by status
        if status == "completed":
            status_color = QColor(COLORS["success"])
        elif status == "error":
            status_color = QColor(COLORS["error"])
        else:
            status_color = QColor(COLORS["warning"])

        item.setForeground(3, status_color)

        # Store trace data for details view
        item.setData(0, Qt.ItemDataRole.UserRole, trace)

        # Tooltip with agent type
        item.setToolTip(0, f"Agent: {agent}\nStatus: {status}")

        # Add duration bar as widget (column 4)
        duration_bar = DurationBar()
        if duration_ms and self._max_duration_ms > 0:
            percentage = min(100, int((duration_ms / self._max_duration_ms) * 100))
            duration_bar.setValue(percentage)
            duration_bar.setToolTip(
                f"{format_duration(duration_ms)} ({percentage}% of max)"
            )
        else:
            duration_bar.setValue(0)
        self._tree.setItemWidget(item, 4, duration_bar)

        # Add children traces if any
        children = trace.get("children", [])
        for child in children:
            self._add_trace_item(item, child)

        return item

    def update_data(
        self,
        traces: list[dict],
        sessions: list[dict],
        session_hierarchy: list[dict] | None = None,
        total_traces: int = 0,
        unique_agents: int = 0,
        total_duration_ms: int = 0,
    ) -> None:
        """Update tracing data.

        Args:
            traces: List of trace dicts with full details
            sessions: List of sessions with traces for filter combo
            session_hierarchy: Hierarchical session tree for delegation view
            total_traces: Total number of traces
            unique_agents: Number of unique agent types
            total_duration_ms: Total duration of all traces
        """
        self._traces_data = traces
        self._sessions_data = sessions
        self._session_hierarchy = session_hierarchy or []

        # Update metrics
        self._metrics.update_metric("traces", str(total_traces))
        self._metrics.update_metric("agents", str(unique_agents))
        self._metrics.update_metric("duration", format_duration(total_duration_ms))

        # Update session combo
        current_session = self._session_combo.currentData()
        self._session_combo.clear()
        self._session_combo.addItem("All Sessions", "")
        for session in sessions:
            title = session.get("title") or session.get("session_id", "")[:12]
            count = session.get("trace_count", 0)
            self._session_combo.addItem(f"{title} ({count})", session.get("session_id"))

        # Restore selection if possible
        if current_session:
            idx = self._session_combo.findData(current_session)
            if idx >= 0:
                self._session_combo.setCurrentIndex(idx)

        # Populate tree based on current view mode
        if hasattr(self, "_view_mode") and self._view_mode == "sessions":
            self._populate_sessions_tree(self._session_hierarchy)
        else:
            self._populate_tree(traces)
