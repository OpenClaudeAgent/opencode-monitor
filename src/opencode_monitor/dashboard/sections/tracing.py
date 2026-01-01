"""
Tracing section - Agent execution traces visualization.

Displays hierarchical view of agent delegations with timing and prompts.
"""

from datetime import datetime, timedelta
from typing import Optional

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
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from ..widgets import (
    PageHeader,
    SectionHeader,
    EmptyState,
    MetricsRow,
    Separator,
)
from ..styles import COLORS, SPACING, FONTS, UI


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
        self.setFixedHeight(8)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS["bg_hover"]};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS["accent_primary"]};
                border-radius: 4px;
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

    def set_text(self, text: str) -> None:
        self._text.setPlainText(text)


class TraceDetailPanel(QFrame):
    """Panel showing detailed trace information."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("trace-detail")
        self.setStyleSheet(f"""
            QFrame#trace-detail {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["md"])

        # Header
        self._header = QLabel("Select a trace")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)
        layout.addWidget(self._header)

        # Metrics line
        self._metrics = QLabel("")
        self._metrics.setStyleSheet(f"""
            font-size: {FONTS["size_sm"]}px;
            color: {COLORS["text_secondary"]};
        """)
        layout.addWidget(self._metrics)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['border_default']};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # Scroll area for prompts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, SPACING["sm"], 0)
        content_layout.setSpacing(SPACING["md"])

        # Prompt Input
        self._input_section = CollapsibleTextEdit("Prompt Input")
        content_layout.addWidget(self._input_section)

        # Prompt Output
        self._output_section = CollapsibleTextEdit("Prompt Output")
        content_layout.addWidget(self._output_section)

        # Tools Used
        self._tools_label = QLabel("Tools Used")
        self._tools_label.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            font-weight: {FONTS["weight_medium"]};
            margin-top: {SPACING["sm"]}px;
        """)
        content_layout.addWidget(self._tools_label)

        self._tools_text = QLabel("-")
        self._tools_text.setStyleSheet(f"""
            color: {COLORS["text_muted"]};
            font-size: {FONTS["size_sm"]}px;
        """)
        self._tools_text.setWordWrap(True)
        content_layout.addWidget(self._tools_text)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

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
        """Display trace details."""
        self._header.setText(f"Agent: {agent}")

        # Metrics
        duration_str = format_duration(duration_ms)
        tokens_str = f"{format_tokens_short(tokens_in)} in / {format_tokens_short(tokens_out)} out"
        self._metrics.setText(
            f"Duration: {duration_str} | Tokens: {tokens_str} | Status: {status}"
        )

        # Prompts
        self._input_section.set_text(prompt_input or "(No input)")
        self._output_section.set_text(prompt_output or "(No output)")

        # Tools
        if tools_used:
            self._tools_text.setText(", ".join(tools_used))
        else:
            self._tools_text.setText("-")

    def clear(self) -> None:
        """Clear all trace details."""
        self._header.setText("Select a trace")
        self._metrics.setText("")
        self._input_section.set_text("")
        self._output_section.set_text("")
        self._tools_text.setText("-")


class TracingSection(QWidget):
    """Tracing section - agent execution traces visualization."""

    # Signal when double-click to open terminal
    open_terminal_requested = pyqtSignal(str)  # session_id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._traces_data: list[dict] = []
        self._sessions_data: list[dict] = []
        self._max_duration_ms: int = 1  # Avoid division by zero
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"]
        )
        layout.setSpacing(0)

        # Header with session selector
        header = PageHeader("Agent Traces", "Execution traces and delegation hierarchy")

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
        header.add_action(self._session_combo)

        layout.addWidget(header)

        # Main content with splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)

        # Left: Tree view
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, SPACING["md"], 0, 0)
        left_layout.setSpacing(SPACING["sm"])

        # Metrics row
        self._metrics = MetricsRow()
        self._metrics.add_metric("traces", "0", "Traces", "primary")
        self._metrics.add_metric("agents", "0", "Agents", "primary")
        self._metrics.add_metric("duration", "0s", "Total Time", "warning")
        self._metrics.add_stretch()
        left_layout.addWidget(self._metrics)

        left_layout.addWidget(Separator())

        # Tree widget
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(
            ["Agent", "Duration", "Tokens", "Status", "Timeline"]
        )
        self._tree.setColumnWidth(0, 180)  # Agent
        self._tree.setColumnWidth(1, 80)  # Duration
        self._tree.setColumnWidth(2, 70)  # Tokens
        self._tree.setColumnWidth(3, 80)  # Status
        self._tree.setColumnWidth(4, 150)  # Timeline bar
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setAnimated(True)
        self._tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: 8px;
                padding: {SPACING["sm"]}px;
            }}
            QTreeWidget::item {{
                padding: 4px 0;
                border-bottom: 1px solid {COLORS["border_default"]};
            }}
            QTreeWidget::item:selected {{
                background-color: {COLORS["bg_elevated"]};
            }}
            QTreeWidget::item:hover {{
                background-color: {COLORS["bg_hover"]};
            }}
            QHeaderView::section {{
                background-color: {COLORS["bg_hover"]};
                color: {COLORS["text_secondary"]};
                font-size: {FONTS["size_sm"]}px;
                font-weight: {FONTS["weight_medium"]};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {COLORS["border_default"]};
            }}
        """)
        left_layout.addWidget(self._tree)

        # Empty state
        self._empty = EmptyState(
            icon="◯",
            title="No traces found",
            subtitle="Traces will appear after agents are invoked via 'task' tool",
        )
        self._empty.hide()
        left_layout.addWidget(self._empty)

        self._splitter.addWidget(left_panel)

        # Right: Detail panel
        self._detail_panel = TraceDetailPanel()
        self._splitter.addWidget(self._detail_panel)

        # Set splitter proportions
        self._splitter.setSizes([600, 400])

        layout.addWidget(self._splitter)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._session_combo.currentIndexChanged.connect(self._on_session_changed)

    def _on_item_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        """Handle click on tree item - show details."""
        trace_data = item.data(0, Qt.ItemDataRole.UserRole)
        if trace_data:
            self._detail_panel.show_trace(
                agent=trace_data.get("subagent_type", ""),
                duration_ms=trace_data.get("duration_ms"),
                tokens_in=trace_data.get("tokens_in"),
                tokens_out=trace_data.get("tokens_out"),
                status=trace_data.get("status", ""),
                prompt_input=trace_data.get("prompt_input", ""),
                prompt_output=trace_data.get("prompt_output"),
                tools_used=trace_data.get("tools_used", []),
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

        # Group by session for hierarchy
        session_traces: dict[str, list[dict]] = {}
        for trace in traces:
            session = trace.get("session_id", "unknown")
            if session not in session_traces:
                session_traces[session] = []
            session_traces[session].append(trace)

        # Build tree
        for session_id, session_traces_list in session_traces.items():
            # Sort by start time
            session_traces_list.sort(key=lambda t: t.get("started_at") or datetime.min)

            for trace in session_traces_list:
                self._add_trace_item(None, trace)

        # Expand all by default
        self._tree.expandAll()

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

        # Agent name with icon
        status_icon = (
            "●" if status == "completed" else "○" if status == "running" else "✕"
        )
        item.setText(0, f"{status_icon} {agent}")

        # Duration
        item.setText(1, format_duration(duration_ms))

        # Tokens
        item.setText(2, format_tokens_short(tokens_in))

        # Status
        item.setText(3, status)

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

        # Add duration bar as widget (column 4)
        duration_bar = DurationBar()
        if duration_ms and self._max_duration_ms > 0:
            percentage = min(100, int((duration_ms / self._max_duration_ms) * 100))
            duration_bar.setValue(percentage)
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
        total_traces: int = 0,
        unique_agents: int = 0,
        total_duration_ms: int = 0,
    ) -> None:
        """Update tracing data.

        Args:
            traces: List of trace dicts with full details
            sessions: List of sessions with traces for filter combo
            total_traces: Total number of traces
            unique_agents: Number of unique agent types
            total_duration_ms: Total duration of all traces
        """
        self._traces_data = traces
        self._sessions_data = sessions

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

        # Populate tree
        self._populate_tree(traces)
