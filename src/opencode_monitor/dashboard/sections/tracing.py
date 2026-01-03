"""
Tracing section - Agent execution traces visualization.

Displays hierarchical view of agent delegations with timing and prompts.
Provides detailed session analysis with tabs for different metrics.
"""

import os
import re
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING

# Pre-compiled regex patterns
_AGENT_PATTERN = re.compile(r"\(@(\w+)")  # Extract agent type from title
_AGENT_SUFFIX_PATTERN = re.compile(r"\s*\(@\w+.*\)$")  # Remove agent suffix from title

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QLabel,
    QProgressBar,
    QFrame,
    QHeaderView,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QGridLayout,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from ..widgets import EmptyState
from ..styles import COLORS, SPACING, FONTS, RADIUS, UI
from ...utils.logger import debug

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


class TranscriptTab(QWidget):
    """Tab displaying full conversation transcript."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING["md"], 0, 0)
        layout.setSpacing(SPACING["md"])

        # Scroll area for long transcripts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {COLORS["bg_surface"]};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS["border_default"]};
                border-radius: 4px;
                min-height: 30px;
            }}
        """)

        # Content widget
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(
            SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"]
        )
        self._content_layout.setSpacing(SPACING["lg"])

        scroll.setWidget(self._content)
        layout.addWidget(scroll)

    def load_data(self, data: dict) -> None:
        """Load transcript data.

        Args:
            data: Dict with user_content and assistant_content
        """
        self._loaded = True

        # Clear existing content
        while self._content_layout.count():
            child = self._content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        user_content = data.get("user_content", "")
        assistant_content = data.get("assistant_content", "")

        # User section
        if user_content:
            user_header = QLabel("💬 User Prompt")
            user_header.setStyleSheet(f"""
                color: {COLORS.get("info", "#60A5FA")};
                font-size: {FONTS["size_md"]}px;
                font-weight: {FONTS["weight_semibold"]};
            """)
            self._content_layout.addWidget(user_header)

            user_text = QTextEdit()
            user_text.setPlainText(user_content)
            user_text.setReadOnly(True)
            user_text.setMinimumHeight(100)
            user_text.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {COLORS["bg_hover"]};
                    color: {COLORS["text_primary"]};
                    border: 1px solid {COLORS["border_default"]};
                    border-radius: {RADIUS["md"]}px;
                    padding: {SPACING["md"]}px;
                    font-family: {FONTS["family"]};
                    font-size: {FONTS["size_sm"]}px;
                }}
            """)
            self._content_layout.addWidget(user_text)

        # Assistant section
        if assistant_content:
            assistant_header = QLabel("🤖 Assistant Response")
            assistant_header.setStyleSheet(f"""
                color: {COLORS.get("success", "#34D399")};
                font-size: {FONTS["size_md"]}px;
                font-weight: {FONTS["weight_semibold"]};
                margin-top: {SPACING["md"]}px;
            """)
            self._content_layout.addWidget(assistant_header)

            assistant_text = QTextEdit()
            assistant_text.setPlainText(assistant_content)
            assistant_text.setReadOnly(True)
            assistant_text.setMinimumHeight(150)
            assistant_text.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {COLORS["bg_hover"]};
                    color: {COLORS["text_primary"]};
                    border: 1px solid {COLORS["border_default"]};
                    border-radius: {RADIUS["md"]}px;
                    padding: {SPACING["md"]}px;
                    font-family: {FONTS["family"]};
                    font-size: {FONTS["size_sm"]}px;
                }}
            """)
            self._content_layout.addWidget(assistant_text)

        self._content_layout.addStretch()

    def is_loaded(self) -> bool:
        return self._loaded

    def clear(self) -> None:
        self._loaded = False
        while self._content_layout.count():
            child = self._content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()


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
    - Scrollable content for overflow handling
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

        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {COLORS["bg_surface"]};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS["border_default"]};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {COLORS["text_muted"]};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        # Content widget inside scroll area
        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(content)
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

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

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
                padding: {SPACING["md"]}px {SPACING["lg"]}px;
                margin-right: 4px;
                border-top-left-radius: {RADIUS["sm"]}px;
                border-top-right-radius: {RADIUS["sm"]}px;
                font-size: 16px;
                min-width: 32px;
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
        self._transcript_tab = TranscriptTab()
        self._tokens_tab = TokensTab()
        self._tools_tab = ToolsTab()
        self._files_tab = FilesTab()
        self._agents_tab = AgentsTab()
        self._timeline_tab = TimelineTab()

        # Short tab labels to avoid truncation
        self._tabs.addTab(self._transcript_tab, "📜")
        self._tabs.addTab(self._tokens_tab, "📊")
        self._tabs.addTab(self._tools_tab, "🔧")
        self._tabs.addTab(self._files_tab, "📁")
        self._tabs.addTab(self._agents_tab, "🤖")
        self._tabs.addTab(self._timeline_tab, "⏱")

        # Add tooltips for clarity
        self._tabs.setTabToolTip(0, "Transcript - Full conversation")
        self._tabs.setTabToolTip(1, "Tokens - Usage breakdown")
        self._tabs.setTabToolTip(2, "Tools - Tool calls")
        self._tabs.setTabToolTip(3, "Files - File operations")
        self._tabs.setTabToolTip(4, "Agents - Agent hierarchy")
        self._tabs.setTabToolTip(5, "Timeline - Event timeline")

        # Connect tab change for lazy loading
        self._tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self._tabs)

    def _get_api_client(self):
        """Get the API client for data access."""
        from ...api import get_api_client

        return get_api_client()

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change - load data for new tab if needed."""
        if not self._current_session_id:
            return

        # Load data for the selected tab
        self._load_tab_data(index)

    def _load_tab_data(self, tab_index: int) -> None:
        """Load data for a specific tab via API."""
        if not self._current_session_id:
            debug("[TraceDetailPanel] _load_tab_data: no session_id")
            return

        client = self._get_api_client()

        if not client.is_available:
            debug("[TraceDetailPanel] _load_tab_data: API not available")
            return

        try:
            # Tab indices after removing PromptsTab:
            # 0 = Transcript, 1 = Tokens, 2 = Tools, 3 = Files, 4 = Agents, 5 = Timeline
            if tab_index == 0:  # Transcript
                if not self._transcript_tab.is_loaded():
                    debug(
                        f"[TraceDetailPanel] Loading prompts for transcript {self._current_session_id}"
                    )
                    prompts_data = client.get_session_prompts(self._current_session_id)
                    debug(
                        f"[TraceDetailPanel] Prompts data: {prompts_data is not None}"
                    )
                    if prompts_data:
                        # Convert prompts data to transcript format
                        self._transcript_tab.load_data(
                            {
                                "user_content": prompts_data.get("prompt_input", ""),
                                "assistant_content": prompts_data.get(
                                    "prompt_output", ""
                                ),
                            }
                        )
                    else:
                        self._transcript_tab.load_data(
                            {
                                "user_content": "(No prompt data available)",
                                "assistant_content": "(Session may be empty or API unavailable)",
                            }
                        )
            elif tab_index == 1:  # Tokens
                if not self._tokens_tab.is_loaded():
                    data = client.get_session_tokens(self._current_session_id)
                    if data:
                        self._tokens_tab.load_data(data)
            elif tab_index == 2:  # Tools
                if not self._tools_tab.is_loaded():
                    data = client.get_session_tools(self._current_session_id)
                    if data:
                        self._tools_tab.load_data(data)
            elif tab_index == 3:  # Files
                if not self._files_tab.is_loaded():
                    data = client.get_session_files(self._current_session_id)
                    if data:
                        self._files_tab.load_data(data)
            elif tab_index == 4:  # Agents
                if not self._agents_tab.is_loaded():
                    agents = client.get_session_agents(self._current_session_id)
                    if agents:
                        self._agents_tab.load_data(agents)
            elif tab_index == 5:  # Timeline
                if not self._timeline_tab.is_loaded():
                    events = client.get_session_timeline(self._current_session_id)
                    if events:
                        self._timeline_tab.load_data(events)
        except Exception as e:
            debug(f"Failed to load tab data: {e}")

    def show_session_summary(
        self, session_id: str, tree_data: dict | None = None
    ) -> None:
        """Show session summary with data from TracingDataService.

        This is the main entry point for displaying session details.
        Loads summary data and updates all metrics. Tab data is lazy loaded.

        For root sessions: fetches data from API
        For child sessions (sub-agents): uses tree_data directly

        Args:
            session_id: The session ID to display
            tree_data: Optional data from tree item for consistent metrics
                       (children_count, trace_count, tokens, duration, agent_type)
        """
        debug(f"[TraceDetailPanel] show_session_summary called for: {session_id}")
        self._current_session_id = session_id
        self._tree_data = tree_data or {}

        # Clear all tabs
        self._clear_tabs()

        # Check if this is a child session (sub-agent trace)
        # Child sessions have agent_type != None and != "user"
        agent_type = self._tree_data.get("agent_type")
        is_child = agent_type is not None and agent_type != "user"

        if is_child:
            # For child sessions, use tree_data directly (more accurate for specific trace)
            self._show_child_session(tree_data or {})
            return

        # For root sessions, get summary from API
        client = self._get_api_client()

        if not client.is_available:
            debug("[TraceDetailPanel] API not available, using fallback")
            self._header.setText("API not available")
            self._header.setStyleSheet(f"""
                font-size: {FONTS["size_lg"]}px;
                font-weight: {FONTS["weight_semibold"]};
                color: {COLORS["text_muted"]};
            """)
            return

        summary = client.get_session_summary(session_id)
        debug(f"[TraceDetailPanel] Got summary: {summary is not None}")

        if summary is None:
            summary = {"meta": {}, "summary": {}, "details": {}}

        self._current_data = summary
        meta = summary.get("meta", {})
        s = summary.get("summary", {})
        details = summary.get("details", {})

        # Update header
        title = meta.get("title", "")
        directory = meta.get("directory", "")
        project_name = os.path.basename(directory) if directory else "Session"

        header_text = f"🌳 {project_name}"
        self._header.setText(header_text)
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Update status badge
        status = s.get("status", "completed")
        self._update_status_badge(status)

        # Update metrics - prefer tree_data for consistency with tree display
        duration_ms = self._tree_data.get("duration_ms") or s.get("duration_ms", 0)
        total_tokens = s.get("total_tokens", 0)
        total_tools = s.get("total_tool_calls", 0)
        total_files = s.get("total_files", 0)
        agents_count = self._tree_data.get("children_count", s.get("unique_agents", 0))

        self._update_metric(self._metric_duration, "⏱", format_duration(duration_ms))
        self._update_metric(
            self._metric_tokens, "🎫", format_tokens_short(total_tokens)
        )
        self._update_metric(self._metric_tools, "🔧", str(total_tools))
        self._update_metric(self._metric_files, "📁", str(total_files))
        self._update_metric(self._metric_agents, "🤖", str(agents_count))

        # Load data for current tab
        self._load_tab_data(self._tabs.currentIndex())

    def _show_child_session(self, tree_data: dict) -> None:
        """Show details for a child session (sub-agent trace).

        Child sessions are individual agent invocations within a parent session.
        We display their specific metrics from tree_data.
        """
        agent_type = tree_data.get("agent_type", "agent")
        parent_agent = tree_data.get("parent_agent", "user")
        title = tree_data.get("title", "")
        status = tree_data.get("status", "completed")
        session_id = tree_data.get("session_id")

        # Update header - show delegation chain
        if parent_agent:
            header_text = f"🔗 {parent_agent} → {agent_type}"
        else:
            header_text = f"🤖 {agent_type}"

        self._header.setText(header_text)
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Update status badge
        self._update_status_badge(status)

        # Update metrics from tree_data (use 'or 0' to handle None values)
        duration_ms = tree_data.get("duration_ms") or 0
        tokens_in = tree_data.get("tokens_in") or 0
        tokens_out = tree_data.get("tokens_out") or 0
        total_tokens = tokens_in + tokens_out
        children_count = tree_data.get("children_count") or 0

        self._update_metric(self._metric_duration, "⏱", format_duration(duration_ms))
        self._update_metric(
            self._metric_tokens, "🎫", format_tokens_short(total_tokens)
        )
        self._update_metric(self._metric_tools, "🔧", "-")  # Not available for child
        self._update_metric(self._metric_files, "📁", "-")  # Not available for child
        self._update_metric(self._metric_agents, "🤖", str(children_count))

        # Get prompts directly from tree_data (loaded from agent_traces table)
        prompt_input = tree_data.get("prompt_input")
        prompt_output = tree_data.get("prompt_output")

        # Fallback if no prompts found
        if not prompt_input:
            prompt_input = title if title else f"Task delegated to {agent_type}"
        if not prompt_output:
            prompt_output = (
                f"Agent: {agent_type}\n"
                f"Duration: {format_duration(duration_ms)}\n"
                f"Tokens: {format_tokens_short(tokens_in)} in / {format_tokens_short(tokens_out)} out\n"
                f"Status: {status}"
            )

        # Store data for transcript tab
        self._current_data = {
            "user_content": prompt_input,
            "assistant_content": prompt_output,
        }

        # Load transcript tab with local data
        self._transcript_tab.load_data(self._current_data)
        self._tabs.setCurrentIndex(0)

    def _update_status_badge(self, status: str) -> None:
        """Update the status badge appearance."""
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
            self._status_badge.setText(
                f"● {status.capitalize() if status else 'Unknown'}"
            )
            self._status_badge.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
                background-color: {COLORS["info_muted"]};
                color: {COLORS["info"]};
            """)
        self._status_badge.show()

    def show_turn(
        self,
        user_content: str,
        assistant_content: Optional[str],
        tokens_in: int = 0,
        tokens_out: int = 0,
        timestamp: Optional[str] = None,
    ) -> None:
        """Display a conversation turn (user prompt + assistant response).

        Args:
            user_content: User's prompt
            assistant_content: Assistant's response (can be None if pending)
            tokens_in: Input tokens
            tokens_out: Output tokens
            timestamp: Turn timestamp (ISO format)
        """
        self._current_session_id = None
        self._clear_tabs()

        # Update header
        self._header.setText("💬 Conversation Turn")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Hide status badge
        self._status_badge.hide()

        # Update metrics
        total_tokens = (tokens_in or 0) + (tokens_out or 0)
        self._update_metric(self._metric_duration, "⏱", "-")
        self._update_metric(
            self._metric_tokens, "🎫", format_tokens_short(total_tokens)
        )
        self._update_metric(self._metric_tools, "🔧", "-")
        self._update_metric(self._metric_files, "📁", "-")
        self._update_metric(self._metric_agents, "🤖", "-")

        # Store data for reference
        self._current_data = {
            "user_content": user_content,
            "assistant_content": assistant_content or "(Waiting for response...)",
        }

        # Load full content into transcript tab
        self._transcript_tab.load_data(self._current_data)

        # Show transcript tab by default for turns (index 0 now)
        self._tabs.setCurrentIndex(0)

    def show_message(
        self,
        role: str,
        content: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        timestamp: Optional[str] = None,
    ) -> None:
        """Display message content (user prompt or assistant response).

        Args:
            role: "user" or "assistant"
            content: Full message content
            tokens_in: Input tokens for this message
            tokens_out: Output tokens for this message
            timestamp: Message timestamp (ISO format)
        """
        self._current_session_id = None
        self._clear_tabs()

        # Update header based on role
        if role == "user":
            self._header.setText("💬 User Message")
            header_color = COLORS.get("info", "#60A5FA")
        else:
            self._header.setText("🤖 Assistant Response")
            header_color = COLORS.get("success", "#34D399")

        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {header_color};
        """)

        # Hide status badge for messages
        self._status_badge.hide()

        # Update metrics
        total_tokens = (tokens_in or 0) + (tokens_out or 0)
        self._update_metric(self._metric_duration, "⏱", "-")
        self._update_metric(
            self._metric_tokens, "🎫", format_tokens_short(total_tokens)
        )
        self._update_metric(self._metric_tools, "🔧", "-")
        self._update_metric(self._metric_files, "📁", "-")
        self._update_metric(self._metric_agents, "🤖", "-")

        # Load content into transcript tab
        self._current_data = {
            "user_content": content if role == "user" else "",
            "assistant_content": content if role == "assistant" else "",
        }
        self._transcript_tab.load_data(self._current_data)
        self._tabs.setCurrentIndex(0)

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

        # Store for transcript tab
        self._current_data = {
            "user_content": prompt_input,
            "assistant_content": prompt_output or "",
        }

        # Load transcript tab (default)
        self._transcript_tab.load_data(self._current_data)
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

        # Store for transcript tab
        output_text = f"Directory: {directory}\n"
        if is_root:
            output_text += "Type: Direct user conversation\n"
        output_text += f"Traces: {trace_count}\n"
        output_text += f"Sub-agents: {children_count}"

        self._current_data = {
            "user_content": prompt_input or title or "(No prompt)",
            "assistant_content": output_text,
        }

        # Load transcript tab
        self._transcript_tab.load_data(self._current_data)
        self._tabs.setCurrentIndex(0)

    def _clear_tabs(self) -> None:
        """Clear all tab data."""
        self._transcript_tab.clear()
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
    """Tracing section - agent execution traces visualization.

    Simplified UI with two panels:
    - Left: Session/trace tree with hierarchy
    - Right: Detail panel with tabs
    """

    # Signal when double-click to open terminal
    open_terminal_requested = pyqtSignal(str)  # session_id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._traces_data: list[dict] = []
        self._sessions_data: list[dict] = []
        self._session_hierarchy: list[dict] = []
        self._max_duration_ms: int = 1  # Avoid division by zero
        self._view_mode: str = "sessions"  # Always sessions view
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["sm"])

        # Simple header with just title
        title = QLabel("Traces")
        title.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
            padding-bottom: {SPACING["xs"]}px;
        """)
        layout.addWidget(title)

        # Main content with vertical splitter (tree on top, details below)
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(8)  # Make handle easier to grab
        self._splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {COLORS["border_default"]};
                margin: 4px 40px;
                border-radius: 2px;
            }}
            QSplitter::handle:hover {{
                background-color: {COLORS["accent_primary"]};
            }}
        """)

        # Top panel: Tree view (gets more space)
        top_panel = QWidget()
        top_panel.setMinimumHeight(200)  # Ensure tree gets adequate space
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
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
        if header:
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

        # Bottom panel: Detail panel
        self._detail_panel = TraceDetailPanel()
        self._detail_panel.setMinimumHeight(250)  # Ensure details panel is visible
        self._splitter.addWidget(self._detail_panel)

        # Set splitter proportions (50% tree, 50% details)
        self._splitter.setSizes([500, 500])

        layout.addWidget(self._splitter, stretch=1)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)

    def _on_item_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        """Handle click on tree item - show details.

        In sessions view: Uses TracingDataService for rich session summary
        In traces view: Shows trace details with prompts
        """
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if self._view_mode == "sessions":
            node_type = data.get("node_type", "session")
            session_id = data.get("session_id")

            if node_type == "turn":
                # Turn clicked - show conversation exchange in detail panel
                self._detail_panel.show_turn(
                    user_content=data.get("user_content", ""),
                    assistant_content=data.get("assistant_content"),
                    tokens_in=data.get("tokens_in", 0),
                    tokens_out=data.get("tokens_out", 0),
                    timestamp=data.get("created_at"),
                )
            elif node_type == "message":
                # Single message clicked (legacy)
                self._detail_panel.show_message(
                    role=data.get("role", ""),
                    content=data.get("content", data.get("title", "")),
                    tokens_in=data.get("tokens_in", 0),
                    tokens_out=data.get("tokens_out", 0),
                    timestamp=data.get("created_at"),
                )
            elif session_id:
                # Session/Agent clicked - use TracingDataService for full summary
                duration = data.get("duration_ms") or data.get("total_duration_ms", 0)
                tree_data = {
                    "node_type": node_type,
                    "children_count": len(data.get("children", [])),
                    "trace_count": data.get("trace_count", 0),
                    "tokens_in": data.get("tokens_in", 0),
                    "tokens_out": data.get("tokens_out", 0),
                    "duration_ms": duration,
                    "agent_type": data.get("agent_type"),
                    "parent_agent": data.get("parent_agent"),
                    "title": data.get("title", ""),
                    "status": data.get("status"),
                    "prompt_input": data.get(
                        "prompt_input"
                    ),  # Real prompt from Task tool
                    "prompt_output": data.get("prompt_output"),  # Agent's response
                    "session_id": session_id,
                }
                self._detail_panel.show_session_summary(session_id, tree_data=tree_data)
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

            def format_datetime(dt) -> str:
                """Format datetime for display. Handles both datetime and string."""
                if not dt:
                    return "-"
                if isinstance(dt, str):
                    # ISO format string from API - extract date/time part
                    return dt[:16].replace("T", " ")
                return dt.strftime("%Y-%m-%d %H:%M")

            def get_project_name(directory: Optional[str]) -> str:
                """Extract project name from full path."""
                if not directory:
                    return "Unknown"
                # Get the last folder name
                return os.path.basename(directory.rstrip("/"))

            def extract_agent_from_title(title: Optional[str]) -> Optional[str]:
                """Extract agent type from title like 'Task (@agent_type'."""
                if not title:
                    return None
                # Look for pattern (@agent_type) or (@agent_type subagent)
                match = _AGENT_PATTERN.search(title)
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

                node_type = session.get("node_type", "session")
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
                    item.setForeground(0, QColor(COLORS["tree_root"]))
                elif node_type == "turn":
                    # Conversation turn: show delegation (user → agent)
                    icon = "💬"
                    color = COLORS.get("text_primary", "#E5E7EB")
                    # Show user → agent_name (coordinateur, executeur, etc.)
                    responding_agent = session.get("agent", "assistant")
                    label = f"{icon} user → {responding_agent}"
                    item.setText(0, label)
                    item.setForeground(0, QColor(color))

                    # Tooltip with full conversation
                    user_content = session.get("user_content", "")
                    assistant_content = session.get("assistant_content", "")
                    tooltip = f"User:\n{user_content[:400]}"
                    if len(user_content) > 400:
                        tooltip += "..."
                    if assistant_content:
                        tooltip += f"\n\nAssistant:\n{assistant_content[:400]}"
                        if len(assistant_content) > 400:
                            tooltip += "..."
                    item.setToolTip(0, tooltip)
                elif node_type == "message":
                    # Single message node (legacy)
                    role = session.get("role", "")
                    if role == "user":
                        icon = "💬"
                        color = COLORS.get("info", "#60A5FA")
                    else:
                        icon = "🤖"
                        color = COLORS.get("success", "#34D399")

                    label = f"{icon} {title}"
                    item.setText(0, label)
                    item.setForeground(0, QColor(color))

                    full_content = session.get("content", title)
                    if full_content:
                        item.setToolTip(
                            0,
                            full_content[:500] + "..."
                            if len(full_content) > 500
                            else full_content,
                        )
                elif node_type == "agent":
                    # Agent delegation node
                    effective_agent = agent_type or extract_agent_from_title(title)
                    icon = "🔗" if depth == 1 else "└─"

                    if effective_agent and parent_agent:
                        label = f"{icon} {parent_agent} → {effective_agent}"
                    elif effective_agent:
                        label = f"{icon} {effective_agent}"
                    else:
                        label = f"{icon} subagent"

                    item.setText(0, label)
                    item.setForeground(0, QColor(COLORS["tree_child"]))
                else:
                    # Fallback for other node types
                    effective_agent = agent_type or extract_agent_from_title(title)
                    icon = "🔗" if depth == 1 else "└─"

                    if effective_agent and parent_agent:
                        label = f"{icon} {parent_agent} → {effective_agent}"
                    elif effective_agent:
                        label = f"{icon} {effective_agent}"
                    else:
                        label = f"{icon} subagent"

                    if title:
                        clean_title = _AGENT_SUFFIX_PATTERN.sub("", title)
                        short_title = (
                            clean_title[:35] + "..."
                            if len(clean_title) > 35
                            else clean_title
                        )
                        if short_title.strip():
                            label = f"{label}: {short_title}"

                    item.setText(0, label)
                    item.setForeground(0, QColor(COLORS["tree_child"]))

                # Date - secondary color
                item.setText(1, format_datetime(created_at))
                item.setForeground(1, QColor(COLORS["text_secondary"]))

                # For messages, show tokens instead of children count
                if node_type == "message":
                    tokens_in = session.get("tokens_in") or 0
                    tokens_out = session.get("tokens_out") or 0
                    if tokens_in or tokens_out:
                        item.setText(2, f"{tokens_in}→{tokens_out}")
                        item.setForeground(2, QColor(COLORS["text_muted"]))
                    else:
                        item.setText(2, "-")
                        item.setForeground(2, QColor(COLORS["text_muted"]))
                    item.setText(3, "-")
                    item.setForeground(3, QColor(COLORS["text_muted"]))
                else:
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

                # Tooltip with full path for sessions
                if directory:
                    item.setToolTip(0, directory)

                # Add children recursively (children are already sorted chronologically)
                for child in session.get("children", []):
                    add_session_item(item, child, is_root=False, depth=depth + 1)

                return item

            # Add root sessions (they are sorted DESC - most recent first)
            for session in sessions:
                add_session_item(None, session, is_root=True, depth=0)

            # Collapse all by default - user can expand manually
            self._tree.collapseAll()

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

        # Populate tree with sessions hierarchy (always sessions view)
        self._populate_sessions_tree(self._session_hierarchy)
