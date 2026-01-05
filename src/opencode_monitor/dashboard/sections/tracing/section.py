"""
TracingSection - Main tracing section widget.

Agent execution traces visualization with hierarchical view of agent delegations.
"""

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

from .detail_panel import TraceDetailPanel
from .tree_builder import build_session_tree
from .tree_items import add_exchange_item, add_part_item


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

        # Tree widget with columns: Type/Name | Time | Duration | In | Out | Status
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Type / Name", "Time", "Duration", "In", "Out", ""])
        self._tree.setColumnWidth(0, 380)
        self._tree.setColumnWidth(1, 85)
        self._tree.setColumnWidth(2, 70)
        self._tree.setColumnWidth(3, 55)
        self._tree.setColumnWidth(4, 55)
        self._tree.setColumnWidth(5, 30)
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
        self._tree.itemExpanded.connect(self._on_item_expanded)
        # Also handle keyboard navigation (arrow keys)
        self._tree.currentItemChanged.connect(self._on_current_item_changed)

    def _on_current_item_changed(
        self, current: QTreeWidgetItem, _previous: QTreeWidgetItem
    ) -> None:
        """Handle current item change (keyboard navigation)."""
        if current:
            self._on_item_clicked(current, 0)

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        """Handle item expansion.

        Note: Exchanges are now included in the API response (/api/tracing/tree),
        so no separate loading is needed. Children are displayed in the order
        received from the API.
        """
        # No-op: all children are already loaded from the API
        pass

    def _on_item_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        """Handle click on tree item - show details."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        node_type = data.get("node_type", "session")
        session_id = data.get("session_id")

        if node_type in ("user_turn", "conversation"):
            # Show conversation details (user → agent from API)
            prompt_input = data.get("prompt_input") or data.get("message_preview", "")
            agent = data.get("agent") or data.get("subagent_type", "assistant")
            self._detail_panel.show_exchange(
                user_content=prompt_input,
                assistant_content="",  # Not included in conversation
                agent=agent,
                tokens_in=data.get("tokens_in", 0),
                tokens_out=data.get("tokens_out", 0),
                parts=[],
                timestamp=data.get("started_at"),
            )
        elif node_type == "exchange":
            # Legacy: Show exchange details (user → assistant)
            user = data.get("user", {})
            assistant = data.get("assistant", {})
            self._detail_panel.show_exchange(
                user_content=user.get("content", "") if user else "",
                assistant_content=assistant.get("content", "") if assistant else "",
                agent=assistant.get("agent", "assistant") if assistant else "assistant",
                tokens_in=assistant.get("tokens_in", 0) if assistant else 0,
                tokens_out=assistant.get("tokens_out", 0) if assistant else 0,
                parts=assistant.get("parts", []) if assistant else [],
                timestamp=user.get("created_at") if user else None,
            )
        elif node_type == "part":
            # Show part details (tool, text, etc.)
            tool_name = data.get("tool_name", "")
            if tool_name:
                self._detail_panel.show_tool(
                    tool_name=tool_name,
                    display_info=data.get("display_info", ""),
                    status=data.get("status", "completed"),
                    duration_ms=data.get("duration_ms", 0),
                    timestamp=data.get("created_at"),
                )
            else:
                # Text part - show as message
                self._detail_panel.show_message(
                    role="assistant",
                    content=data.get("content", ""),
                    tokens_in=0,
                    tokens_out=0,
                    timestamp=data.get("created_at"),
                )
        elif node_type == "tool":
            self._detail_panel.show_tool(
                tool_name=data.get("tool_name", ""),
                display_info=data.get("display_info", ""),
                status=data.get("status", "completed"),
                duration_ms=data.get("duration_ms", 0),
                timestamp=data.get("created_at"),
            )
        elif node_type in ("session", "agent", "delegation"):
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
                "directory": data.get("directory", ""),
            }
            if session_id:
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
                )
        else:
            # Fallback for unknown types
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

    def _add_exchange_item(
        self, parent: QTreeWidgetItem, exchange: dict, index: int
    ) -> QTreeWidgetItem:
        """Add an exchange (user → assistant) item to the tree.

        Delegates to tree_items.add_exchange_item for implementation.
        """
        return add_exchange_item(parent, exchange, index)

    def _add_part_item(self, parent: QTreeWidgetItem, part: dict) -> QTreeWidgetItem:
        """Add a part (tool, text, delegation) item to the tree.

        Delegates to tree_items.add_part_item for implementation.
        """
        return add_part_item(parent, part)

    def _populate_sessions_tree(self, sessions: list[dict]) -> None:
        """Populate tree widget with session hierarchy."""
        session_ids = {s.get("session_id") for s in sessions}
        if hasattr(self, "_last_session_ids") and self._last_session_ids == session_ids:
            return
        self._last_session_ids = session_ids

        self._tree.setUpdatesEnabled(False)
        try:
            if not sessions:
                self._tree.clear()
                self._tree.hide()
                self._empty.show()
                self._detail_panel.clear()
                return

            self._tree.show()
            self._empty.hide()

            # Delegate to tree_builder module
            build_session_tree(self._tree, sessions)

        finally:
            self._tree.setUpdatesEnabled(True)

    def update_data(
        self,
        session_hierarchy: list[dict] | None = None,
    ) -> None:
        """Update tracing data with session hierarchy.

        Args:
            session_hierarchy: Hierarchical tree of sessions from API
        """
        self._session_hierarchy = session_hierarchy or []

        # Populate tree with sessions hierarchy
        self._populate_sessions_tree(self._session_hierarchy)
