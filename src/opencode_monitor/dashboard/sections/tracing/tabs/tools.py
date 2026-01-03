"""
Tools tab - Tool usage statistics.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PyQt6.QtGui import QColor

from opencode_monitor.dashboard.styles import COLORS, SPACING, FONTS, RADIUS
from ..helpers import format_duration


class ToolsTab(QWidget):
    """Tab displaying tool usage statistics."""

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

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(
            ["Tool", "Count", "Avg Duration", "Errors"]
        )
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)

        # Style
        palette = self._table.palette()
        palette.setColor(palette.ColorRole.Base, QColor(COLORS["bg_surface"]))
        palette.setColor(palette.ColorRole.AlternateBase, QColor(COLORS["bg_elevated"]))
        self._table.setPalette(palette)

        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["md"]}px;
            }}
            QTableWidget::item {{
                padding: {SPACING["sm"]}px;
                color: {COLORS["text_secondary"]};
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS["sidebar_active"]};
            }}
            QHeaderView::section {{
                background-color: {COLORS["bg_elevated"]};
                color: {COLORS["text_muted"]};
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["sm"]}px;
                border: none;
                border-bottom: 1px solid {COLORS["border_default"]};
            }}
        """)

        header = self._table.horizontalHeader()
        if header:
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self._table)
        layout.addStretch()

    def load_data(self, data: dict) -> None:
        """Load tools data from TracingDataService response."""
        self._loaded = True

        summary = data.get("summary", {})
        details = data.get("details", {})

        # Update summary
        total = summary.get("total_calls", 0)
        unique = summary.get("unique_tools", 0)
        success_rate = summary.get("success_rate", 0)
        avg_duration = summary.get("avg_duration_ms", 0)

        self._summary.setText(
            f"Total: {total} calls  •  "
            f"Unique: {unique} tools  •  "
            f"Success: {success_rate:.1f}%  •  "
            f"Avg: {format_duration(avg_duration)}"
        )

        # Populate table
        self._table.setRowCount(0)
        top_tools = details.get("top_tools", [])

        for tool in top_tools:
            row = self._table.rowCount()
            self._table.insertRow(row)

            name_item = QTableWidgetItem(tool.get("name", ""))
            name_item.setForeground(QColor(COLORS["text_primary"]))
            self._table.setItem(row, 0, name_item)

            count_item = QTableWidgetItem(str(tool.get("count", 0)))
            self._table.setItem(row, 1, count_item)

            duration_item = QTableWidgetItem(
                format_duration(tool.get("avg_duration_ms"))
            )
            self._table.setItem(row, 2, duration_item)

            errors = tool.get("error_count", 0)
            error_item = QTableWidgetItem(str(errors))
            if errors > 0:
                error_item.setForeground(QColor(COLORS["error"]))
            self._table.setItem(row, 3, error_item)

    def is_loaded(self) -> bool:
        return self._loaded

    def clear(self) -> None:
        self._loaded = False
        self._summary.setText("")
        self._table.setRowCount(0)
