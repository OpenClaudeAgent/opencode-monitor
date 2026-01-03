"""
Tokens tab - Token usage breakdown with mini-charts.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from opencode_monitor.dashboard.styles import COLORS, SPACING, FONTS, RADIUS
from ..helpers import format_tokens_short
from ..widgets import HorizontalBar


class TokensTab(QWidget):
    """Tab displaying token usage breakdown with mini-charts."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING["md"], 0, 0)
        layout.setSpacing(SPACING["lg"])

        # Summary row
        self._summary = QLabel("")
        self._summary.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_sm"]}px;
            padding: {SPACING["sm"]}px;
            background-color: {COLORS["bg_hover"]};
            border-radius: {RADIUS["sm"]}px;
        """)
        layout.addWidget(self._summary)

        # Token breakdown section
        breakdown_label = QLabel("Token Breakdown")
        breakdown_label.setStyleSheet(f"""
            color: {COLORS["text_primary"]};
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_semibold"]};
        """)
        layout.addWidget(breakdown_label)

        # Bars container
        self._bars_container = QWidget()
        self._bars_layout = QVBoxLayout(self._bars_container)
        self._bars_layout.setContentsMargins(0, 0, 0, 0)
        self._bars_layout.setSpacing(SPACING["xs"])
        layout.addWidget(self._bars_container)

        # By agent section
        agent_label = QLabel("By Agent")
        agent_label.setStyleSheet(f"""
            color: {COLORS["text_primary"]};
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_semibold"]};
            margin-top: {SPACING["md"]}px;
        """)
        layout.addWidget(agent_label)

        self._agent_container = QWidget()
        self._agent_layout = QVBoxLayout(self._agent_container)
        self._agent_layout.setContentsMargins(0, 0, 0, 0)
        self._agent_layout.setSpacing(SPACING["xs"])
        layout.addWidget(self._agent_container)

        layout.addStretch()

    def load_data(self, data: dict) -> None:
        """Load tokens data from TracingDataService response."""
        self._loaded = True

        details = data.get("details", {})
        summary = data.get("summary", {})

        # Update summary
        total = summary.get("total", 0)
        cache_ratio = summary.get("cache_hit_ratio", 0)
        self._summary.setText(
            f"Total: {format_tokens_short(total)}  •  Cache hit: {cache_ratio:.1f}%"
        )

        # Clear old bars
        while self._bars_layout.count():
            child = self._bars_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add token bars
        input_tokens = details.get("input", 0)
        output_tokens = details.get("output", 0)
        cache_tokens = details.get("cache_read", 0)
        max_tokens = max(input_tokens, output_tokens, cache_tokens, 1)

        self._bars_layout.addWidget(
            HorizontalBar(input_tokens, max_tokens, "Input", COLORS["info"])
        )
        self._bars_layout.addWidget(
            HorizontalBar(output_tokens, max_tokens, "Output", COLORS["success"])
        )
        self._bars_layout.addWidget(
            HorizontalBar(cache_tokens, max_tokens, "Cache", COLORS["type_skill"])
        )

        # Clear old agent bars
        while self._agent_layout.count():
            child = self._agent_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add agent bars
        by_agent = details.get("by_agent", [])
        if by_agent:
            max_agent_tokens = max((a.get("tokens", 0) for a in by_agent), default=1)
            for agent_data in by_agent[:5]:  # Top 5 agents
                agent_name = agent_data.get("agent", "unknown")
                tokens = agent_data.get("tokens", 0)
                self._agent_layout.addWidget(
                    HorizontalBar(
                        tokens, max_agent_tokens, agent_name, COLORS["accent_primary"]
                    )
                )
        else:
            no_data = QLabel("No agent breakdown available")
            no_data.setStyleSheet(
                f"color: {COLORS['text_muted']}; font-size: {FONTS['size_sm']}px;"
            )
            self._agent_layout.addWidget(no_data)

    def is_loaded(self) -> bool:
        return self._loaded

    def clear(self) -> None:
        self._loaded = False
        self._summary.setText("")
        while self._bars_layout.count():
            child = self._bars_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        while self._agent_layout.count():
            child = self._agent_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
