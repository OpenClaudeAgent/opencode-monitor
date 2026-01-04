"""
TracingSection - Main tracing section widget.

Agent execution traces visualization with hierarchical view of agent delegations.
"""

import os
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from opencode_monitor.dashboard.widgets import EmptyState
from opencode_monitor.dashboard.styles import COLORS, SPACING, FONTS, RADIUS

from .helpers import (
    format_duration,
    format_tokens_short,
    AGENT_PATTERN,
    AGENT_SUFFIX_PATTERN,
)
from .widgets import DurationBar
from .detail_panel import TraceDetailPanel


class TracingSection(QWidget):
    """Tracing section - agent execution traces visualization.

    Simplified UI with two panels:
    - Top: Session/trace tree with hierarchy
    - Bottom: Detail panel with tabs
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
        self._splitter.setHandleWidth(8)
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

        # Top panel: Tree view
        top_panel = QWidget()
        top_panel.setMinimumHeight(200)
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        # Tree widget
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(
            ["Session / Agent", "Created", "Agents", "Traces", ""]
        )
        self._tree.setColumnWidth(0, 320)
        self._tree.setColumnWidth(1, 130)
        self._tree.setColumnWidth(2, 70)
        self._tree.setColumnWidth(3, 70)
        self._tree.setColumnWidth(4, 40)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(20)
        self._tree.setUniformRowHeights(True)

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
        self._detail_panel.setMinimumHeight(250)
        self._splitter.addWidget(self._detail_panel)

        # Set splitter proportions (50% tree, 50% details)
        self._splitter.setSizes([500, 500])

        layout.addWidget(self._splitter, stretch=1)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)

    def _on_item_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        """Handle click on tree item - show details."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if self._view_mode == "sessions":
            node_type = data.get("node_type", "session")
            session_id = data.get("session_id")

            if node_type == "tool":
                # Show tool details
                self._detail_panel.show_tool(
                    tool_name=data.get("tool_name", ""),
                    display_info=data.get("display_info", ""),
                    status=data.get("status", "completed"),
                    duration_ms=data.get("duration_ms", 0),
                    timestamp=data.get("created_at"),
                )
            elif node_type == "turn":
                self._detail_panel.show_turn(
                    user_content=data.get("user_content", ""),
                    assistant_content=data.get("assistant_content"),
                    tokens_in=data.get("tokens_in", 0),
                    tokens_out=data.get("tokens_out", 0),
                    timestamp=data.get("created_at"),
                )
            elif node_type == "message":
                self._detail_panel.show_message(
                    role=data.get("role", ""),
                    content=data.get("content", data.get("title", "")),
                    tokens_in=data.get("tokens_in", 0),
                    tokens_out=data.get("tokens_out", 0),
                    timestamp=data.get("created_at"),
                )
            elif session_id:
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
                    "prompt_input": data.get("prompt_input"),
                    "prompt_output": data.get("prompt_output"),
                    "session_id": session_id,
                }
                self._detail_panel.show_session_summary(session_id, tree_data=tree_data)
            else:
                self._detail_panel.show_session(
                    title=data.get("title", ""),
                    agent_type=data.get("agent_type"),
                    parent_agent=data.get("parent_agent"),
                    directory=data.get("directory", ""),
                    created_at=data.get("created_at"),
                    trace_count=data.get("trace_count", 0),
                    children_count=len(data.get("children", [])),
                    prompt_input=data.get("prompt_input"),
                    node_type=data.get("node_type"),
                )
        else:
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

    def _populate_sessions_tree(self, sessions: list[dict]) -> None:
        """Populate tree widget with session hierarchy."""
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
                if not dt:
                    return "-"
                if isinstance(dt, str):
                    return dt[:16].replace("T", " ")
                return dt.strftime("%Y-%m-%d %H:%M")

            def get_project_name(directory: Optional[str]) -> str:
                if not directory:
                    return "Unknown"
                return os.path.basename(directory.rstrip("/"))

            def extract_agent_from_title(title: Optional[str]) -> Optional[str]:
                if not title:
                    return None
                match = AGENT_PATTERN.search(title)
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
                created_at = session.get("created_at") or session.get("started_at")
                trace_count = session.get("trace_count", 0)
                children_count = len(session.get("children", []))

                if is_root:
                    project = get_project_name(directory)
                    item.setText(0, f"🌳 {project}")
                    item.setForeground(0, QColor(COLORS["tree_root"]))
                elif node_type == "turn":
                    icon = "💬"
                    color = COLORS.get("text_primary", "#E5E7EB")
                    responding_agent = session.get("agent", "assistant")
                    label = f"{icon} user → {responding_agent}"
                    item.setText(0, label)
                    item.setForeground(0, QColor(color))

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
                elif node_type == "user_turn":
                    # User initiated conversation with agent
                    effective_agent = agent_type or extract_agent_from_title(title)
                    icon = "💬"
                    if effective_agent and parent_agent:
                        label = f"{icon} {parent_agent} → {effective_agent}"
                    elif effective_agent:
                        label = f"{icon} {effective_agent}"
                    else:
                        label = f"{icon} agent"
                    item.setText(0, label)
                    item.setForeground(0, QColor(COLORS["tree_child"]))
                elif node_type == "delegation":
                    # Agent delegating to sub-agent
                    effective_agent = agent_type or extract_agent_from_title(title)
                    icon = "🔗"
                    if effective_agent and parent_agent:
                        label = f"{icon} {parent_agent} → {effective_agent}"
                    elif effective_agent:
                        label = f"{icon} {effective_agent}"
                    else:
                        label = f"{icon} subagent"
                    item.setText(0, label)
                    item.setForeground(0, QColor(COLORS["tree_child"]))
                elif node_type == "tool":
                    tool_name = session.get("tool_name", "")
                    display_info = session.get("display_info", "")
                    tool_status = session.get("status", "completed")

                    # Choose icon based on tool type
                    tool_icons = {
                        "read": "📖",
                        "edit": "✏️",
                        "write": "📝",
                        "bash": "🔧",
                        "glob": "🔍",
                        "grep": "🔎",
                        "task": "🤖",
                        "webfetch": "🌐",
                        "web_fetch": "🌐",
                        "todowrite": "📋",
                        "todoread": "📋",
                    }
                    icon = tool_icons.get(tool_name, "⚙️")

                    # Build label
                    if display_info:
                        label = f"{icon} {tool_name}: {display_info}"
                    else:
                        label = f"{icon} {tool_name}"

                    # Truncate if too long
                    if len(label) > 60:
                        label = label[:57] + "..."

                    item.setText(0, label)

                    # Color based on status
                    if tool_status == "error":
                        item.setForeground(0, QColor(COLORS["error"]))
                    else:
                        item.setForeground(0, QColor(COLORS["text_muted"]))

                    # Show duration in column 1
                    duration_ms = session.get("duration_ms", 0)
                    if duration_ms:
                        item.setText(1, format_duration(duration_ms))
                    else:
                        item.setText(1, "-")
                    item.setForeground(1, QColor(COLORS["text_muted"]))

                    # Empty columns 2 and 3
                    item.setText(2, "-")
                    item.setForeground(2, QColor(COLORS["text_muted"]))
                    item.setText(3, "-")
                    item.setForeground(3, QColor(COLORS["text_muted"]))

                    item.setData(0, Qt.ItemDataRole.UserRole, session)
                    return item  # Tools don't have children
                else:
                    # Unknown node_type - display with generic icon
                    effective_agent = agent_type or extract_agent_from_title(title)
                    icon = "○"
                    if effective_agent and parent_agent:
                        label = f"{icon} {parent_agent} → {effective_agent}"
                    elif effective_agent:
                        label = f"{icon} {effective_agent}"
                    elif title:
                        label = f"{icon} {title[:40]}"
                    else:
                        label = f"{icon} {node_type or 'unknown'}"

                    item.setText(0, label)
                    item.setForeground(0, QColor(COLORS["tree_child"]))

                # Date
                item.setText(1, format_datetime(created_at))
                item.setForeground(1, QColor(COLORS["text_secondary"]))

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
                    if children_count > 0:
                        item.setText(2, str(children_count))
                        item.setForeground(2, QColor(COLORS["accent_primary"]))
                    else:
                        item.setText(2, "-")
                        item.setForeground(2, QColor(COLORS["text_muted"]))

                    if trace_count > 0:
                        item.setText(3, str(trace_count))
                        item.setForeground(3, QColor(COLORS["text_secondary"]))
                    else:
                        item.setText(3, "-")
                        item.setForeground(3, QColor(COLORS["text_muted"]))

                item.setData(0, Qt.ItemDataRole.UserRole, session)

                if directory:
                    item.setToolTip(0, directory)

                # Add all children (agents and tools are now both in children)
                # Order is determined by API - dashboard just displays
                for child in session.get("children", []):
                    add_session_item(item, child, is_root=False, depth=depth + 1)

                return item

            for session in sessions:
                add_session_item(None, session, is_root=True, depth=0)

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

        if status == "completed":
            status_icon = "●"
            agent_color = QColor(COLORS["success"])
        elif status == "error":
            status_icon = "✕"
            agent_color = QColor(COLORS["error"])
        else:
            status_icon = "◐"
            agent_color = QColor(COLORS["warning"])

        item.setText(0, f"{status_icon} {agent}")
        item.setForeground(0, agent_color)

        item.setText(1, format_duration(duration_ms))
        item.setForeground(1, QColor(COLORS["text_secondary"]))

        item.setText(2, format_tokens_short(tokens_in))
        item.setForeground(2, QColor(COLORS["text_secondary"]))

        status_display = status.capitalize() if status else "-"
        item.setText(3, status_display)

        if status == "completed":
            status_color = QColor(COLORS["success"])
        elif status == "error":
            status_color = QColor(COLORS["error"])
        else:
            status_color = QColor(COLORS["warning"])

        item.setForeground(3, status_color)

        item.setData(0, Qt.ItemDataRole.UserRole, trace)
        item.setToolTip(0, f"Agent: {agent}\nStatus: {status}")

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
        """Update tracing data."""
        self._traces_data = traces
        self._sessions_data = sessions
        self._session_hierarchy = session_hierarchy or []

        # Populate tree with sessions hierarchy (always sessions view)
        self._populate_sessions_tree(self._session_hierarchy)
