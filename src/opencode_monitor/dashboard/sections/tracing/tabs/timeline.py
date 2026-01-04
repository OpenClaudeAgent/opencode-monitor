"""
Timeline tab - Chronological timeline of events.
"""

from PyQt6.QtWidgets import QListWidgetItem
from PyQt6.QtGui import QColor

from opencode_monitor.dashboard.styles import COLORS, FONTS
from ..helpers import format_duration, format_tokens_short
from .base import BaseTab


class TimelineTab(BaseTab):
    """Tab displaying chronological timeline of events."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Summary label
        self._add_summary_label()

        # Timeline list (with monospace font override)
        self._list = self._add_styled_list()
        # Add mono font for timeline entries
        self._list.setStyleSheet(
            self._list.styleSheet()
            + f"""
            QListWidget::item {{
                font-family: {FONTS["mono"]};
                font-size: {FONTS["size_sm"]}px;
            }}
        """
        )

    def load_data(self, events: list[dict]) -> None:
        """Load timeline data from TracingDataService response."""
        self._loaded = True

        self._list.clear()

        if not events:
            if self._summary:
                self._summary.setText("No events recorded")
            return

        # Update summary
        total_events = len(events)
        tool_events = len([e for e in events if e.get("type") == "tool"])
        msg_events = len([e for e in events if e.get("type") == "message"])

        if self._summary:
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

    def clear(self) -> None:
        super().clear()
        self._list.clear()
