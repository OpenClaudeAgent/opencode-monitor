"""
Timeline tab - Chronological timeline of events.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PyQt6.QtGui import QColor

from opencode_monitor.dashboard.styles import COLORS, SPACING, FONTS, RADIUS
from ..helpers import format_duration, format_tokens_short


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
