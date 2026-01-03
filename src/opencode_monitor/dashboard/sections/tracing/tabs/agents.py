"""
Agents tab - Agent hierarchy with delegation info.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem

from opencode_monitor.dashboard.styles import COLORS, SPACING, FONTS, RADIUS
from ..helpers import format_tokens_short


class AgentsTab(QWidget):
    """Tab displaying agent hierarchy with delegation info."""

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

        # Agents list
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
                color: {COLORS["text_secondary"]};
            }}
            QListWidget::item:selected {{
                background-color: {COLORS["sidebar_active"]};
            }}
            QListWidget::item:hover {{
                background-color: {COLORS["bg_hover"]};
            }}
        """)
        layout.addWidget(self._list)

    def load_data(self, agents: list[dict]) -> None:
        """Load agents data from TracingDataService response."""
        self._loaded = True

        self._list.clear()

        if not agents:
            self._summary.setText("No agent data available")
            return

        # Update summary
        total_agents = len(agents)
        total_tokens = sum(a.get("tokens", 0) for a in agents)
        self._summary.setText(
            f"Agents: {total_agents}  •  "
            f"Total tokens: {format_tokens_short(total_tokens)}"
        )

        # Add agents to list
        for agent in agents:
            name = agent.get("agent", "unknown")
            tokens = agent.get("tokens", 0)
            msg_count = agent.get("message_count", 0)

            item = QListWidgetItem(
                f"🤖 {name}  •  {format_tokens_short(tokens)} tokens  •  {msg_count} messages"
            )
            self._list.addItem(item)

    def is_loaded(self) -> bool:
        return self._loaded

    def clear(self) -> None:
        self._loaded = False
        self._summary.setText("")
        self._list.clear()
