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
    QPushButton,
    QHeaderView,
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
from ..styles import COLORS, SPACING, FONTS, RADIUS, UI


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


class TraceDetailPanel(QFrame):
    """Panel showing detailed trace information."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("trace-detail")
        self.setMinimumWidth(350)
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

        # Header
        self._header = QLabel("Select a trace")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
        """)
        layout.addWidget(self._header)

        # Metrics line
        self._metrics_line = QLabel("")
        self._metrics_line.setStyleSheet(f"""
            font-size: {FONTS["size_sm"]}px;
            color: {COLORS["text_secondary"]};
        """)
        self._metrics_line.setWordWrap(True)
        layout.addWidget(self._metrics_line)

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
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Metrics
        duration_str = format_duration(duration_ms)
        tokens_str = f"{format_tokens_short(tokens_in)} in / {format_tokens_short(tokens_out)} out"
        self._metrics_line.setText(
            f"Duration: {duration_str}  •  Tokens: {tokens_str}  •  Status: {status}"
        )

        # Reset section titles for trace view
        self._input_section.set_title("Prompt Input")
        self._output_section.set_title("Prompt Output")

        # Prompts
        self._input_section.set_text(prompt_input or "(No input)")
        self._output_section.set_text(prompt_output or "(No output)")

        # Tools
        if tools_used:
            self._tools_text.setText(", ".join(tools_used))
        else:
            self._tools_text.setText("-")

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
        """Display session details.

        Args:
            title: Session title
            agent_type: Type of agent running in this session
            parent_agent: Agent that delegated to this session
            directory: Working directory
            created_at: Creation timestamp
            trace_count: Number of traces in session
            children_count: Number of child sessions
            prompt_input: First user message (for ROOT sessions)
        """
        import os

        # Determine if this is a ROOT session (no parent)
        is_root = parent_agent is None and agent_type is None

        # Header with session info
        if agent_type and parent_agent:
            header_text = f"🔗 {agent_type} ← {parent_agent}"
        elif agent_type:
            header_text = f"Agent: {agent_type}"
        else:
            # Root session - show project name with tree icon
            project_name = os.path.basename(directory) if directory else "Session"
            header_text = f"🌳 {project_name}"

        self._header.setText(header_text)
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Metrics line with session info
        parts = []
        if created_at:
            parts.append(f"📅 {created_at.strftime('%Y-%m-%d %H:%M')}")
        if parent_agent:
            parts.append(f"⬅ Appelé par {parent_agent}")
        if is_root:
            parts.append("🌳 ROOT session")
        if trace_count > 0:
            parts.append(f"📊 {trace_count} traces")
        if children_count > 0:
            parts.append(f"🔗 {children_count} sous-agents")

        self._metrics_line.setText("  •  ".join(parts) if parts else "")

        # Adapt section titles based on session type
        if is_root:
            self._input_section.set_title("💬 User Prompt")
            self._output_section.set_title("📁 Project Info")
        else:
            self._input_section.set_title("📝 Task Description")
            self._output_section.set_title("📁 Project Info")

        # Show prompt/title in first section
        if prompt_input:
            # For ROOT sessions, show the actual user prompt
            self._input_section.set_text(prompt_input)
        elif title:
            # Clean up title - remove (@agent) suffix if present
            import re

            clean_title = re.sub(r"\s*\(@\w+.*\)$", "", title)
            self._input_section.set_text(
                clean_title if clean_title else "(No description)"
            )
        else:
            self._input_section.set_text("(No prompt)")

        # Show project info in second section
        project_info_parts = []
        if directory:
            project_info_parts.append(f"Directory: {directory}")
        if is_root:
            project_info_parts.append("Type: Direct user conversation")
        project_info_parts.append(f"Traces in session: {trace_count}")
        project_info_parts.append(f"Delegated sub-agents: {children_count}")

        self._output_section.set_text("\n".join(project_info_parts))

        # Clear tools
        self._tools_text.setText("-")

    def clear(self) -> None:
        """Clear all trace details."""
        self._header.setText("Select a trace")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
        """)
        self._metrics_line.setText("")
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
        """Handle click on tree item - show details."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if self._view_mode == "sessions":
            # Session clicked - find associated trace to show prompts
            session_id = data.get("session_id")

            # Search for a trace where child_session_id matches this session
            # (the trace that CREATED this session via delegation)
            matching_trace = None
            for trace in self._traces_data:
                if trace.get("child_session_id") == session_id:
                    matching_trace = trace
                    break

            # Also check if this session directly contains traces
            if not matching_trace:
                for trace in self._traces_data:
                    if trace.get("session_id") == session_id:
                        matching_trace = trace
                        break

            if matching_trace:
                # Found a trace - show its prompts
                self._detail_panel.show_trace(
                    agent=matching_trace.get(
                        "subagent_type", data.get("agent_type", "unknown")
                    ),
                    duration_ms=matching_trace.get("duration_ms"),
                    tokens_in=matching_trace.get("tokens_in"),
                    tokens_out=matching_trace.get("tokens_out"),
                    status=matching_trace.get("status", ""),
                    prompt_input=matching_trace.get("prompt_input", ""),
                    prompt_output=matching_trace.get("prompt_output"),
                    tools_used=matching_trace.get("tools_used", []),
                )
            else:
                # No trace found - show session info as fallback
                # For ROOT sessions, prompt_input may be stored in data
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
