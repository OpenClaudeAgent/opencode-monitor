"""MetricsBar - Horizontal bar displaying key metrics."""

from PyQt6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel

from opencode_monitor.dashboard.styles import COLORS, SPACING, FONTS, RADIUS


class MetricsBar(QFrame):
    """Horizontal bar showing key metrics (duration, tokens, tools, files, agents)."""

    # Metric configuration: (key, icon, default_value, label)
    METRICS_CONFIG = [
        ("duration", "⏱", "0s", "Duration"),
        ("tokens", "🎫", "0", "Tokens"),
        ("tools", "🔧", "0", "Tools"),
        ("files", "📁", "0", "Files"),
        ("agents", "🤖", "0", "Agents"),
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._metrics: dict[str, QWidget] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the metrics bar UI."""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_hover"]};
                border-radius: {RADIUS["md"]}px;
                padding: {SPACING["sm"]}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["lg"])

        # Create all metric widgets
        for key, icon, default_value, label in self.METRICS_CONFIG:
            widget = self._create_metric(icon, default_value, label)
            self._metrics[key] = widget
            layout.addWidget(widget)

        layout.addStretch()

    def _create_metric(self, icon: str, value: str, label: str) -> QWidget:
        """Create a single metric widget with icon, value and label."""
        widget = QWidget()
        widget_layout = QVBoxLayout(widget)
        widget_layout.setContentsMargins(0, 0, 0, 0)
        widget_layout.setSpacing(2)

        # Value with icon
        value_label = QLabel(f"{icon} {value}")
        value_label.setObjectName("metric_value")
        value_label.setStyleSheet(f"""
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)
        widget_layout.addWidget(value_label)

        # Label
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            color: {COLORS["text_muted"]};
        """)
        widget_layout.addWidget(label_widget)

        return widget

    def update_metric(self, key: str, value: str) -> None:
        """Update a specific metric value.

        Args:
            key: One of 'duration', 'tokens', 'tools', 'files', 'agents'
            value: The formatted value to display
        """
        if key not in self._metrics:
            return

        widget = self._metrics[key]
        icon = "⚙️"  # Default icon

        # Find icon from config
        for cfg_key, cfg_icon, _, _ in self.METRICS_CONFIG:
            if cfg_key == key:
                icon = cfg_icon
                break

        value_label = widget.findChild(QLabel, "metric_value")
        if value_label:
            value_label.setText(f"{icon} {value}")

    def update_all(
        self,
        duration: str = "0s",
        tokens: str = "0",
        tools: str = "0",
        files: str = "0",
        agents: str = "0",
    ) -> None:
        """Update all metrics at once."""
        self.update_metric("duration", duration)
        self.update_metric("tokens", tokens)
        self.update_metric("tools", tools)
        self.update_metric("files", files)
        self.update_metric("agents", agents)

    def reset(self) -> None:
        """Reset all metrics to default values."""
        self.update_all("0s", "0", "0", "0", "0")
