"""SessionOverviewPanel - Compact overview panel for root sessions."""

from typing import Any

from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QWidget,
)
from PyQt6.QtCore import Qt

from opencode_monitor.dashboard.styles import COLORS, SPACING, FONTS, RADIUS
from ...helpers import format_duration, format_tokens_short


class SessionOverviewPanel(QFrame):
    """Displays aggregated stats for a root session and all its children."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {COLORS["bg_surface"]};
                width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS["border_default"]};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)

        self._content = QWidget()
        self._content.setStyleSheet("background-color: transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(
            SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"]
        )
        self._content_layout.setSpacing(0)

        self._setup_header_section()
        self._setup_duration_tokens_row()
        self._setup_counts_row()
        self._setup_cost_row()
        self._setup_errors_row()

        self._content_layout.addStretch()
        scroll.setWidget(self._content)
        main_layout.addWidget(scroll)

    def _setup_header_section(self) -> None:
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, SPACING["xs"])
        header_layout.setSpacing(2)

        self._title_label = QLabel()
        self._title_label.setStyleSheet(f"""
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)
        self._title_label.setWordWrap(True)
        header_layout.addWidget(self._title_label)

        self._path_label = QLabel()
        self._path_label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            color: {COLORS["text_muted"]};
        """)
        self._path_label.setWordWrap(True)
        header_layout.addWidget(self._path_label)

        self._content_layout.addWidget(header)
        self._add_separator()

    def _setup_duration_tokens_row(self) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, SPACING["xs"], 0, SPACING["xs"])
        row_layout.setSpacing(SPACING["md"])

        self._duration_label = self._create_metric_label("⏱", "0s")
        row_layout.addWidget(self._duration_label)

        sep = QLabel("│")
        sep.setStyleSheet(f"color: {COLORS['border_default']};")
        row_layout.addWidget(sep)

        self._tokens_label = self._create_metric_label("🎫", "0 in / 0 out / 0 cache")
        row_layout.addWidget(self._tokens_label)
        row_layout.addStretch()

        self._content_layout.addWidget(row)
        self._add_separator()

    def _setup_counts_row(self) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, SPACING["xs"], 0, SPACING["xs"])
        row_layout.setSpacing(SPACING["md"])

        self._exchanges_label = self._create_metric_label("💬", "0 exchanges")
        row_layout.addWidget(self._exchanges_label)

        sep1 = QLabel("│")
        sep1.setStyleSheet(f"color: {COLORS['border_default']};")
        row_layout.addWidget(sep1)

        self._tools_label = self._create_metric_label("🔧", "0 tools")
        row_layout.addWidget(self._tools_label)

        sep2 = QLabel("│")
        sep2.setStyleSheet(f"color: {COLORS['border_default']};")
        row_layout.addWidget(sep2)

        self._delegations_label = self._create_metric_label("🔗", "0 delegations")
        row_layout.addWidget(self._delegations_label)
        row_layout.addStretch()

        self._content_layout.addWidget(row)
        self._add_separator()

    def _setup_cost_row(self) -> None:
        self._cost_widget = QWidget()
        cost_layout = QHBoxLayout(self._cost_widget)
        cost_layout.setContentsMargins(0, SPACING["xs"], 0, SPACING["xs"])
        cost_layout.setSpacing(0)

        self._cost_label = self._create_metric_label("💰", "$0.00 estimated")
        cost_layout.addWidget(self._cost_label)
        cost_layout.addStretch()

        self._content_layout.addWidget(self._cost_widget)

    def _setup_errors_row(self) -> None:
        self._errors_widget = QWidget()
        errors_layout = QHBoxLayout(self._errors_widget)
        errors_layout.setContentsMargins(0, SPACING["xs"], 0, SPACING["xs"])
        errors_layout.setSpacing(0)

        self._errors_label = QLabel()
        self._errors_label.setStyleSheet(f"""
            font-size: {FONTS["size_sm"]}px;
            font-weight: {FONTS["weight_medium"]};
            color: {COLORS["error"]};
        """)
        errors_layout.addWidget(self._errors_label)
        errors_layout.addStretch()

        self._content_layout.addWidget(self._errors_widget)
        self._errors_widget.hide()

    def _create_metric_label(self, icon: str, text: str) -> QLabel:
        label = QLabel(f"{icon} {text}")
        label.setStyleSheet(f"""
            font-size: {FONTS["size_sm"]}px;
            font-weight: {FONTS["weight_medium"]};
            color: {COLORS["text_secondary"]};
        """)
        return label

    def _add_separator(self) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['border_subtle']};")
        sep.setFixedHeight(1)
        self._content_layout.addWidget(sep)

    def load_session(self, tree_data: dict) -> None:
        """Load session data and aggregate stats from children."""
        title = tree_data.get("title", "")
        project = tree_data.get("project", "")
        directory = tree_data.get("directory", "")

        if project and title:
            self._title_label.setText(f"🌳 {project}: {title}")
        elif project:
            self._title_label.setText(f"🌳 {project}")
        elif title:
            self._title_label.setText(f"🌳 {title}")
        else:
            self._title_label.setText("🌳 Session")

        if directory:
            self._path_label.setText(directory)
            self._path_label.show()
        else:
            self._path_label.hide()

        stats = self._aggregate_stats(tree_data)

        duration_ms = stats.get("duration_ms") or tree_data.get("duration_ms") or 0
        self._duration_label.setText(f"⏱ {format_duration(duration_ms)}")

        tokens_in = stats.get("tokens_in", 0)
        tokens_out = stats.get("tokens_out", 0)
        cache_read = stats.get("cache_read", 0)
        self._tokens_label.setText(
            f"🎫 {format_tokens_short(tokens_in)} in / "
            f"{format_tokens_short(tokens_out)} out / "
            f"{format_tokens_short(cache_read)} cache"
        )

        exchanges = stats.get("exchanges", 0)
        tools = stats.get("tools", 0)
        delegations = stats.get("delegations", 0)
        self._exchanges_label.setText(f"💬 {exchanges} exchanges")
        self._tools_label.setText(f"🔧 {tools} tools")
        self._delegations_label.setText(f"🔗 {delegations} delegations")

        cost = stats.get("cost", 0.0)
        if cost > 0:
            self._cost_label.setText(f"💰 ${cost:.4f} estimated")
            self._cost_widget.show()
        else:
            self._cost_widget.hide()

        errors = stats.get("errors", 0)
        if errors > 0:
            self._errors_label.setText(f"⚠️ {errors} errors")
            self._errors_widget.show()
        else:
            self._errors_widget.hide()

    def _aggregate_stats(self, node: dict) -> dict[str, Any]:
        """Recursively aggregate stats from all children."""
        stats: dict[str, Any] = {
            "tokens_in": 0,
            "tokens_out": 0,
            "cache_read": 0,
            "exchanges": 0,
            "tools": 0,
            "delegations": 0,
            "errors": 0,
            "cost": 0.0,
            "duration_ms": 0,
        }

        self._aggregate_node(node, stats)
        return stats

    def _aggregate_node(self, node: dict, stats: dict[str, Any]) -> None:
        """Process a single node and its children."""
        stats["tokens_in"] += node.get("tokens_in") or 0
        stats["tokens_out"] += node.get("tokens_out") or 0
        stats["cache_read"] += node.get("cache_read") or node.get("cache_creation") or 0
        stats["cost"] += node.get("cost") or 0.0

        duration = node.get("duration_ms") or 0
        if duration > stats["duration_ms"]:
            stats["duration_ms"] = duration

        node_type = node.get("node_type", "")
        if node_type in ("user_turn", "conversation", "exchange"):
            stats["exchanges"] += 1
        elif node_type == "tool":
            stats["tools"] += 1
        elif node_type in ("delegation", "agent"):
            stats["delegations"] += 1

        status = node.get("status", "")
        if status == "error":
            stats["errors"] += 1

        children = node.get("children", [])
        for child in children:
            self._aggregate_node(child, stats)

    def clear(self) -> None:
        """Reset the panel to empty state."""
        self._title_label.setText("🌳 Session")
        self._path_label.setText("")
        self._path_label.hide()
        self._duration_label.setText("⏱ 0s")
        self._tokens_label.setText("🎫 0 in / 0 out / 0 cache")
        self._exchanges_label.setText("💬 0 exchanges")
        self._tools_label.setText("🔧 0 tools")
        self._delegations_label.setText("🔗 0 delegations")
        self._cost_label.setText("💰 $0.00 estimated")
        self._cost_widget.hide()
        self._errors_widget.hide()
