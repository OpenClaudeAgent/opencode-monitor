"""
Timeline tab - Chronological timeline of events.
"""

from PyQt6.QtCore import pyqtSignal

from opencode_monitor.dashboard.sections.tracing.views import TimelineView
from .base import BaseTab


class TimelineTab(BaseTab):
    """Tab displaying chronological timeline of events."""

    event_selected = pyqtSignal(dict)  # Emitted when user clicks an event

    def __init__(self, parent=None):
        super().__init__(parent)
        self._add_summary_label()

        # Use rich TimelineView instead of basic list
        self._timeline_view = TimelineView()
        self._timeline_view.event_clicked.connect(self._on_event_clicked)
        self._layout.addWidget(self._timeline_view)

    def load_data(self, events: list[dict]) -> None:
        """Load timeline data from TracingDataService response."""
        self._loaded = True
        self._timeline_view.set_timeline(events)
        self._update_summary(events)

    def _update_summary(self, events: list[dict]) -> None:
        """Update the summary label with event statistics."""
        if not self._summary:
            return
        total = len(events)
        tools = len([e for e in events if e.get("type") == "tool_call"])
        reasoning = len([e for e in events if e.get("type") == "reasoning"])
        self._summary.setText(
            f"Events: {total}  •  Tools: {tools}  •  Reasoning: {reasoning}"
        )

    def _on_event_clicked(self, event: dict) -> None:
        """Handle event click from TimelineView."""
        self.event_selected.emit(event)

    def clear(self) -> None:
        """Clear the tab."""
        super().clear()
        self._timeline_view.set_timeline([])
