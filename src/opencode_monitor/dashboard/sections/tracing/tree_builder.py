"""
Tree builder for tracing section.

Handles populating the session tree with hierarchical data.
"""

from typing import Optional

from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from opencode_monitor.dashboard.styles import COLORS

from .helpers import format_duration, format_tokens_short, AGENT_SUFFIX_PATTERN
from .enriched_helpers import get_tool_display_label, build_tool_tooltip
from .tree_utils import (
    format_time,
    get_project_name,
    extract_agent_from_title,
    get_delegation_icon,
    TREE_TOOL_ICONS,
)


def build_session_tree(
    tree: QTreeWidget,
    sessions: list[dict],
) -> None:
    """Populate tree widget with session hierarchy.

    Args:
        tree: QTreeWidget to populate
        sessions: List of session dictionaries with hierarchy
    """
    tree.clear()

    if not sessions:
        return

    def add_session_item(
        parent_item: Optional[QTreeWidgetItem],
        session: dict,
        is_root: bool = False,
        depth: int = 0,
    ) -> QTreeWidgetItem:
        if parent_item:
            item = QTreeWidgetItem(parent_item)
        else:
            item = QTreeWidgetItem(tree)

        node_type = session.get("node_type", "session")
        agent_type = session.get("agent_type")
        subagent_type = session.get("subagent_type")
        parent_agent = session.get("parent_agent")
        title = session.get("title") or ""
        directory = session.get("directory")
        created_at = session.get("created_at") or session.get("started_at")

        if is_root:
            project = get_project_name(directory)
            if title:
                # Show both project and session title
                item.setText(0, f"🌳 {project}: {title}")
            else:
                # Fallback to project only if no title
                item.setText(0, f"🌳 {project}")
            item.setForeground(0, QColor(COLORS["tree_root"]))
        elif node_type in ("user_turn", "conversation"):
            # Unified format from /api/tracing/tree
            responding_agent = session.get("agent") or subagent_type or "assistant"

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

            icon = TREE_TOOL_ICONS.get(tool_name, "⚙️")

            # Use enriched title if available, fallback to tool_name
            display_label = get_tool_display_label(session)

            # Build label
            if display_info:
                label = f"{icon} {display_label}: {display_info}"
            else:
                label = f"{icon} {display_label}"

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

            # Enriched tooltip with result_summary, cost, tokens
            tooltip = build_tool_tooltip(session)
            if tooltip:
                item.setToolTip(0, tooltip)

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
                    clean_title[:35] + "..." if len(clean_title) > 35 else clean_title
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

        # Store session data with root flag for reliable detection
        if is_root:
            session = {**session, "_is_tree_root": True}
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

    tree.collapseAll()
