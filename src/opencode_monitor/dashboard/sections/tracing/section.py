"""
TracingSection - Main tracing section widget.

Agent execution traces visualization with hierarchical view of agent delegations.
"""

import os
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
        """Add an exchange (user → assistant) item to the tree."""
        item = QTreeWidgetItem(parent)

        user_msg = exchange.get("user", {})
        assistant_msg = exchange.get("assistant", {})

        # Format user content preview
        user_content = (user_msg.get("content") or "") if user_msg else ""
        user_preview = (
            user_content[:60] + "..." if len(user_content) > 60 else user_content
        )
        user_preview = user_preview.replace("\n", " ")

        # Get assistant info
        agent = (
            assistant_msg.get("agent", "assistant") if assistant_msg else "assistant"
        )
        tokens_in = assistant_msg.get("tokens_in", 0) if assistant_msg else 0
        tokens_out = assistant_msg.get("tokens_out", 0) if assistant_msg else 0

        # Label: 💬 user → agent: "preview..."
        if user_preview:
            label = f'💬 user → {agent}: "{user_preview}"'
        else:
            label = f"💬 user → {agent}"

        item.setText(0, label)
        item.setForeground(0, QColor(COLORS["text_primary"]))

        # Time column - format: MM-DD HH:MM
        created = user_msg.get("created_at", "") if user_msg else ""
        if created:
            # "2026-01-04T08:21:30" -> "01-04 08:21"
            if "T" in created:
                time_str = f"{created[5:10]} {created[11:16]}"
            elif len(created) > 15:
                time_str = f"{created[5:10]} {created[11:16]}"
            else:
                time_str = created
            item.setText(1, time_str)
        item.setForeground(1, QColor(COLORS["text_secondary"]))

        # Duration - from assistant response
        duration_ms = 0
        if assistant_msg:
            started = assistant_msg.get("created_at")
            ended = assistant_msg.get("completed_at")
            if started and ended:
                # Calculate duration from timestamps
                try:
                    from datetime import datetime as dt_module

                    start_dt = dt_module.fromisoformat(started.replace("Z", "+00:00"))
                    end_dt = dt_module.fromisoformat(ended.replace("Z", "+00:00"))
                    duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
                except (ValueError, TypeError):
                    pass
        item.setText(2, format_duration(duration_ms) if duration_ms else "-")
        item.setForeground(2, QColor(COLORS["text_muted"]))

        # Tokens In
        item.setText(3, format_tokens_short(tokens_in) if tokens_in else "-")
        item.setForeground(3, QColor(COLORS["text_muted"]))

        # Tokens Out
        item.setText(4, format_tokens_short(tokens_out) if tokens_out else "-")
        item.setForeground(4, QColor(COLORS["text_muted"]))

        # Store data for detail panel
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            {
                "node_type": "exchange",
                "index": index,
                "user": user_msg,
                "assistant": assistant_msg,
            },
        )

        # Add parts as children
        if assistant_msg:
            parts = assistant_msg.get("parts", [])
            for part in parts:
                self._add_part_item(item, part)

        return item

    def _add_part_item(self, parent: QTreeWidgetItem, part: dict) -> QTreeWidgetItem:
        """Add a part (tool, text, delegation) item to the tree."""
        item = QTreeWidgetItem(parent)

        part_type = part.get("type", "")
        tool_name = part.get("tool_name", "")
        display_info = part.get("display_info", "")
        status = part.get("status", "completed")
        duration_ms = part.get("duration_ms", 0)
        content = part.get("content", "")

        # Choose icon based on type
        tool_icons = {
            "bash": "🔧",
            "read": "📖",
            "write": "📝",
            "edit": "✏️",
            "glob": "🔍",
            "grep": "🔎",
            "task": "📨",
            "webfetch": "🌐",
            "web_fetch": "🌐",
            "todowrite": "📋",
            "todoread": "📋",
            "skill": "📚",
            "notify_ask_user": "❓",
            "notify_notify_commit": "📦",
            "notify_notify_merge": "🔀",
        }

        if tool_name:
            icon = tool_icons.get(tool_name, "⚙️")
            # Build label with display info
            if display_info:
                info_preview = (
                    display_info[:50] + "..."
                    if len(display_info) > 50
                    else display_info
                )
                info_preview = info_preview.replace("\n", " ")
                label = f"  {icon} {tool_name}: {info_preview}"
            else:
                label = f"  {icon} {tool_name}"
        elif part_type == "text":
            icon = "💭"
            text_preview = content[:60] + "..." if len(content) > 60 else content
            text_preview = text_preview.replace("\n", " ")
            label = f"  {icon} {text_preview}" if text_preview else f"  {icon} (text)"
        else:
            icon = "○"
            label = f"  {icon} {part_type}"

        item.setText(0, label)

        # Color based on status
        if status == "error":
            item.setForeground(0, QColor(COLORS["error"]))
        elif tool_name:
            item.setForeground(0, QColor(COLORS["text_secondary"]))
        else:
            item.setForeground(0, QColor(COLORS["text_muted"]))

        # Time column - from part created_at
        created = part.get("created_at", "")
        if created:
            time_str = created[11:19] if len(created) > 19 else created
            item.setText(1, time_str)
        item.setForeground(1, QColor(COLORS["text_muted"]))

        # Duration
        if duration_ms:
            item.setText(2, format_duration(duration_ms))
        else:
            item.setText(2, "-")
        item.setForeground(2, QColor(COLORS["text_muted"]))

        # Tokens In/Out - empty for parts
        item.setText(3, "-")
        item.setForeground(3, QColor(COLORS["text_muted"]))
        item.setText(4, "-")
        item.setForeground(4, QColor(COLORS["text_muted"]))

        # Status icon in last column (5)
        if status == "completed":
            item.setText(5, "✓")
            item.setForeground(5, QColor(COLORS["success"]))
        elif status == "error":
            item.setText(5, "✗")
            item.setForeground(5, QColor(COLORS["error"]))
        elif status == "running":
            item.setText(5, "◐")
            item.setForeground(5, QColor(COLORS["warning"]))

        # Store data for detail panel
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            {
                "node_type": "part",
                **part,
            },
        )

        return item

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

            def format_time(dt) -> str:
                """Format datetime to MM-DD HH:MM for consistent Time column."""
                if not dt:
                    return "-"
                if isinstance(dt, str):
                    # Extract MM-DD HH:MM from ISO string (e.g., "2026-01-04T08:21:30")
                    if "T" in dt:
                        # "2026-01-04T08:21:30" -> "01-04 08:21"
                        date_part = dt[5:10]  # MM-DD
                        time_part = dt.split("T")[1][:5]  # HH:MM
                        return f"{date_part} {time_part}"
                    elif len(dt) > 10:
                        # "2026-01-04 08:21:30" -> "01-04 08:21"
                        return f"{dt[5:10]} {dt[11:16]}"
                    return dt
                return dt.strftime("%m-%d %H:%M")

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

            def get_delegation_icon(depth: int, parent_agent: Optional[str]) -> str:
                """Get icon for delegation based on depth and parent.

                Returns:
                    💬 for user-initiated (depth 1, parent is user)
                    🔗 for agent delegations (depth 1, parent is agent)
                    └─ for nested delegations (depth > 1)
                """
                if depth == 1:
                    return "💬" if parent_agent == "user" else "🔗"
                return "└─"

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
                subagent_type = session.get("subagent_type")
                parent_agent = session.get("parent_agent")
                title = session.get("title") or ""
                directory = session.get("directory")
                created_at = session.get("created_at") or session.get("started_at")

                if is_root:
                    project = get_project_name(directory)
                    item.setText(0, f"🌳 {project}")
                    item.setForeground(0, QColor(COLORS["tree_root"]))
                elif node_type in ("user_turn", "conversation"):
                    # Unified format from /api/tracing/tree
                    responding_agent = (
                        session.get("agent") or subagent_type or "assistant"
                    )

                    # Choose icon based on agent type
                    if responding_agent == "compaction":
                        icon = "📦"  # Compaction/compression icon
                        color = COLORS.get("text_secondary", "#9CA3AF")
                    else:
                        icon = "💬"
                        color = COLORS.get("text_primary", "#E5E7EB")

                    # Build label with prompt preview
                    prompt_input = session.get("prompt_input") or session.get(
                        "message_preview", ""
                    )
                    if prompt_input:
                        preview = prompt_input[:60].replace("\n", " ")
                        if len(prompt_input) > 60:
                            preview += "..."
                        label = f'{icon} user → {responding_agent}: "{preview}"'
                    else:
                        label = f"{icon} user → {responding_agent}"

                    item.setText(0, label)
                    item.setForeground(0, QColor(color))

                    # Full prompt as tooltip
                    if prompt_input:
                        tooltip = f"User:\n{prompt_input[:500]}"
                        if len(prompt_input) > 500:
                            tooltip += "..."
                        item.setToolTip(0, tooltip)
                elif node_type == "turn":
                    # Legacy format
                    responding_agent = session.get("agent", "assistant")

                    # Choose icon based on agent type
                    if responding_agent == "compaction":
                        icon = "📦"
                        color = COLORS.get("text_secondary", "#9CA3AF")
                    else:
                        icon = "💬"
                        color = COLORS.get("text_primary", "#E5E7EB")

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
                elif node_type in ("agent", "delegation"):
                    # Get effective agent from agent_type, subagent_type, or title
                    effective_agent = (
                        agent_type
                        or subagent_type
                        or session.get("subagent_type")
                        or extract_agent_from_title(title)
                    )
                    icon = get_delegation_icon(depth, parent_agent)

                    # Use label from API if available (e.g., "plan -> roadmap")
                    api_label = session.get("label", "")
                    if api_label and " -> " in api_label:
                        label = f"{icon} {api_label.replace(' -> ', ' → ')}"
                    elif effective_agent and parent_agent:
                        label = f"{icon} {parent_agent} → {effective_agent}"
                    elif effective_agent:
                        label = f"{icon} {effective_agent}"
                    elif parent_agent:
                        label = f"{icon} {parent_agent} → agent"
                    else:
                        label = f"{icon} agent"

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

                    # Column 1: Time
                    item.setText(1, format_time(created_at))
                    item.setForeground(1, QColor(COLORS["text_muted"]))

                    # Column 2: Duration
                    duration_ms = session.get("duration_ms", 0)
                    if duration_ms:
                        item.setText(2, format_duration(duration_ms))
                    else:
                        item.setText(2, "-")
                    item.setForeground(2, QColor(COLORS["text_muted"]))

                    # Columns 3, 4: In/Out tokens (empty for tools)
                    item.setText(3, "-")
                    item.setForeground(3, QColor(COLORS["text_muted"]))
                    item.setText(4, "-")
                    item.setForeground(4, QColor(COLORS["text_muted"]))

                    # Column 5: Status
                    if tool_status == "completed":
                        item.setText(5, "✓")
                        item.setForeground(5, QColor(COLORS["success"]))
                    elif tool_status == "error":
                        item.setText(5, "✗")
                        item.setForeground(5, QColor(COLORS["error"]))
                    else:
                        item.setText(5, "◐")
                        item.setForeground(5, QColor(COLORS["warning"]))

                    item.setData(0, Qt.ItemDataRole.UserRole, session)
                    return item  # Tools don't have children
                else:
                    # Get agent name from agent_type, subagent_type, or extract from title
                    effective_agent = (
                        agent_type or subagent_type or extract_agent_from_title(title)
                    )
                    icon = get_delegation_icon(depth, parent_agent)

                    if effective_agent and parent_agent:
                        label = f"{icon} {parent_agent} → {effective_agent}"
                    elif effective_agent:
                        label = f"{icon} {effective_agent}"
                    elif parent_agent:
                        label = f"{icon} {parent_agent} → agent"
                    else:
                        # Fallback: use node_type or generic label
                        label = f"{icon} {node_type}" if node_type else f"{icon} agent"

                    if title:
                        clean_title = AGENT_SUFFIX_PATTERN.sub("", title)
                        short_title = (
                            clean_title[:35] + "..."
                            if len(clean_title) > 35
                            else clean_title
                        )
                        if short_title.strip():
                            label = f"{label}: {short_title}"

                    item.setText(0, label)
                    item.setForeground(0, QColor(COLORS["tree_child"]))

                # Column 1: Time
                item.setText(1, format_time(created_at))
                item.setForeground(1, QColor(COLORS["text_secondary"]))

                # Column 2: Duration
                duration_ms = session.get("duration_ms", 0)
                if duration_ms:
                    item.setText(2, format_duration(duration_ms))
                else:
                    item.setText(2, "-")
                item.setForeground(2, QColor(COLORS["text_muted"]))

                # Columns 3, 4: Tokens In/Out
                tokens_in = session.get("tokens_in") or 0
                tokens_out = session.get("tokens_out") or 0

                if tokens_in:
                    item.setText(3, format_tokens_short(tokens_in))
                    item.setForeground(3, QColor(COLORS["text_muted"]))
                else:
                    item.setText(3, "-")
                    item.setForeground(3, QColor(COLORS["text_muted"]))

                if tokens_out:
                    item.setText(4, format_tokens_short(tokens_out))
                    item.setForeground(4, QColor(COLORS["text_muted"]))
                else:
                    item.setText(4, "-")
                    item.setForeground(4, QColor(COLORS["text_muted"]))

                # Column 5: Status (if available)
                status = session.get("status", "")
                if status == "completed":
                    item.setText(5, "✓")
                    item.setForeground(5, QColor(COLORS["success"]))
                elif status == "error":
                    item.setText(5, "✗")
                    item.setForeground(5, QColor(COLORS["error"]))
                elif status == "running":
                    item.setText(5, "◐")
                    item.setForeground(5, QColor(COLORS["warning"]))

                item.setData(0, Qt.ItemDataRole.UserRole, session)

                if directory:
                    item.setToolTip(0, directory)

                # Add all children sorted by started_at ASC (timeline order)
                children = session.get("children", [])
                sorted_children = sorted(
                    children,
                    key=lambda c: c.get("started_at") or c.get("created_at") or "",
                )
                for child in sorted_children:
                    add_session_item(item, child, is_root=False, depth=depth + 1)

                return item

            for session in sessions:
                add_session_item(None, session, is_root=True, depth=0)

            self._tree.collapseAll()

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
