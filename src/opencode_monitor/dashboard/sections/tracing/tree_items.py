"""
Tree item builders for tracing section.

Functions for creating and populating QTreeWidgetItem objects.
"""

from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from opencode_monitor.dashboard.styles import COLORS

from .helpers import format_duration, format_tokens_short
from .enriched_helpers import get_tool_display_label, build_tool_tooltip
from .tree_utils import TOOL_ICONS


def add_exchange_item(
    parent: QTreeWidgetItem, exchange: dict, index: int
) -> QTreeWidgetItem:
    """Add an exchange (user → assistant) item to the tree.

    Args:
        parent: Parent tree widget item
        exchange: Exchange data dict with 'user' and 'assistant' keys
        index: Index of the exchange in parent

    Returns:
        Created QTreeWidgetItem
    """
    item = QTreeWidgetItem(parent)

    user_msg = exchange.get("user", {})
    assistant_msg = exchange.get("assistant", {})

    # Format user content preview
    user_content = (user_msg.get("content") or "") if user_msg else ""
    user_preview = user_content[:60] + "..." if len(user_content) > 60 else user_content
    user_preview = user_preview.replace("\n", " ")

    # Get assistant info
    agent = assistant_msg.get("agent", "assistant") if assistant_msg else "assistant"
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
            add_part_item(item, part)

    return item


def add_part_item(parent: QTreeWidgetItem, part: dict) -> QTreeWidgetItem:
    """Add a part (tool, text, delegation) item to the tree.

    Args:
        parent: Parent tree widget item
        part: Part data dict

    Returns:
        Created QTreeWidgetItem
    """
    item = QTreeWidgetItem(parent)

    part_type = part.get("type", "")
    tool_name = part.get("tool_name", "")
    display_info = part.get("display_info", "")
    status = part.get("status", "completed")
    duration_ms = part.get("duration_ms", 0)
    content = part.get("content", "")

    if tool_name:
        icon = TOOL_ICONS.get(tool_name, "⚙️")
        # Use enriched title if available, fallback to tool_name
        display_label = get_tool_display_label(part)
        # Build label with display info
        if display_info:
            info_preview = (
                display_info[:50] + "..." if len(display_info) > 50 else display_info
            )
            info_preview = info_preview.replace("\n", " ")
            label = f"  {icon} {display_label}: {info_preview}"
        else:
            label = f"  {icon} {display_label}"
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

    # Enriched tooltip with result_summary, cost, tokens
    if tool_name:
        tooltip = build_tool_tooltip(part)
        if tooltip:
            item.setToolTip(0, tooltip)

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
