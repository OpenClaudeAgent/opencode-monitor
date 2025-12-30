"""
Reusable dashboard widgets.

Design principles applied:
- Consistent spacing (8px scale)
- Cards with subtle borders and shadows
- Clear visual hierarchy
"""

from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QWidget,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from .styles import COLORS, SPACING, RADIUS


class Card(QFrame):
    """A card container with title and content."""

    def __init__(
        self,
        title: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setProperty("class", "card")

        # Add drop shadow for elevation
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(shadow)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        self._layout.setSpacing(SPACING["md"])

        if title:
            title_label = QLabel(title)
            title_label.setProperty("class", "section-title")
            self._layout.addWidget(title_label)

    def add_widget(self, widget: QWidget) -> None:
        """Add a widget to the card content."""
        self._layout.addWidget(widget)

    def add_layout(self, layout: QVBoxLayout | QHBoxLayout | QGridLayout) -> None:
        """Add a layout to the card content."""
        self._layout.addLayout(layout)


class MetricCard(QFrame):
    """A card displaying a single metric with value and label."""

    def __init__(
        self,
        value: str,
        label: str,
        color: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setMinimumWidth(160)  # Wider to prevent text cutoff

        # Add drop shadow for elevation
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["md"])  # More breathing room
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Value
        self._value_label = QLabel(value)
        self._value_label.setProperty("class", "card-value")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if color:
            self._value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(self._value_label)

        # Label
        self._label = QLabel(label)
        self._label.setProperty("class", "card-label")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

    def set_value(self, value: str) -> None:
        """Update the metric value."""
        self._value_label.setText(value)


class MetricsRow(QWidget):
    """A row of metric cards."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACING["md"])
        self._cards: dict[str, MetricCard] = {}

    def add_metric(
        self,
        key: str,
        value: str,
        label: str,
        color: str | None = None,
    ) -> MetricCard:
        """Add a metric card to the row."""
        card = MetricCard(value, label, color)
        self._cards[key] = card
        self._layout.addWidget(card)
        return card

    def update_metric(self, key: str, value: str) -> None:
        """Update a metric value by key."""
        if key in self._cards:
            self._cards[key].set_value(value)

    def add_stretch(self) -> None:
        """Add stretch to push cards to the left."""
        self._layout.addStretch()


class DataTable(QTableWidget):
    """A styled data table with consistent visual appearance.

    Height calculation follows the 8px spacing system:
    - Header: 40px (aligned to 8px grid)
    - Rows: 40px (aligned to 8px grid)
    - Border: 4px (xs spacing for borders)

    All tables display a minimum of MIN_VISIBLE_ROWS rows for visual consistency.
    """

    # Heights aligned to 8px spacing system
    ROW_HEIGHT = 40
    HEADER_HEIGHT = 40
    TABLE_BORDER = SPACING["xs"]  # 4px for borders

    # Minimum visible rows for visual consistency across all tables
    MIN_VISIBLE_ROWS = 5

    def __init__(
        self,
        headers: list[str],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        # Store original headers for sort indicator
        self._original_headers = headers.copy()
        self._current_sort_column = -1
        self._current_sort_order = Qt.SortOrder.AscendingOrder

        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

        # Style
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.verticalHeader().setVisible(False)

        # Enable sorting by clicking column headers
        self.setSortingEnabled(True)

        # Disable internal scrolling - let parent scroll
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Header - Interactive mode allows user to resize columns
        header = self.horizontalHeader()
        header.setStretchLastSection(True)  # Last column takes remaining space
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setDefaultSectionSize(150)
        header.setMinimumSectionSize(50)  # Minimum column width
        header.setSortIndicatorShown(
            False
        )  # Hide native indicator, use our Unicode arrows

        # Connect sort indicator change to update header text with arrow
        header.sortIndicatorChanged.connect(self._on_sort_changed)

        # Initial height with minimum rows for consistency
        initial_height = (
            self.HEADER_HEIGHT
            + self.MIN_VISIBLE_ROWS * self.ROW_HEIGHT
            + self.TABLE_BORDER
        )
        self.setFixedHeight(initial_height)

    def _on_sort_changed(self, column: int, order: Qt.SortOrder) -> None:
        """Update header text with sort arrow indicator."""
        # Reset all headers to original text
        for i, text in enumerate(self._original_headers):
            self.horizontalHeaderItem(i).setText(text)

        # Add arrow to sorted column
        if column >= 0 and column < len(self._original_headers):
            arrow = " ▲" if order == Qt.SortOrder.AscendingOrder else " ▼"
            original = self._original_headers[column]
            item = self.horizontalHeaderItem(column)
            if item:
                item.setText(f"{original}{arrow}")

        self._current_sort_column = column
        self._current_sort_order = order

    def add_row(
        self, data: list[str | tuple[str, str]], full_values: list[str] | None = None
    ) -> None:
        """Add a row of data with optional tooltips.

        Args:
            data: List of values or tuples of (value, style_class)
            full_values: Optional list of full (non-truncated) values for tooltips
        """
        row = self.rowCount()
        self.insertRow(row)

        for col, item_data in enumerate(data):
            if isinstance(item_data, tuple):
                value, style_class = item_data
            else:
                value, style_class = item_data, None

            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Set tooltip - use full value if provided, otherwise use displayed value
            if full_values and col < len(full_values):
                tooltip = full_values[col]
            else:
                tooltip = value
            # Only set tooltip if content might be truncated
            if tooltip and len(tooltip) > 30:
                item.setToolTip(tooltip)

            if style_class:
                if style_class == "risk-critical":
                    item.setForeground(QColor(COLORS["accent_error"]))
                elif style_class == "risk-high":
                    item.setForeground(QColor(COLORS["accent_warning"]))
                elif style_class == "risk-medium":
                    item.setForeground(QColor("#e6b800"))
                elif style_class == "risk-low":
                    item.setForeground(QColor(COLORS["accent_success"]))
                elif style_class == "status-busy":
                    item.setForeground(QColor(COLORS["accent_success"]))
                elif style_class == "status-idle":
                    item.setForeground(QColor(COLORS["text_muted"]))

            self.setItem(row, col, item)

        # Update table height to fit content
        self._update_height()

    def clear_data(self) -> None:
        """Clear all rows but keep headers."""
        self.setRowCount(0)
        self._update_height()

    def _update_height(self) -> None:
        """Update table height based on row count.

        Follows 8px spacing system:
        - Header: 40px
        - Each row: 40px
        - Border: 4px (TABLE_BORDER)

        Uses MIN_VISIBLE_ROWS to ensure visual consistency across all tables.
        """
        row_count = self.rowCount()
        # Use at least MIN_VISIBLE_ROWS for consistent visual appearance
        visible_rows = max(row_count, self.MIN_VISIBLE_ROWS)
        height = self.HEADER_HEIGHT + visible_rows * self.ROW_HEIGHT + self.TABLE_BORDER
        self.setFixedHeight(height)


class SectionHeader(QWidget):
    """A section header with title and optional subtitle."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, SPACING["md"])
        layout.setSpacing(SPACING["xs"])

        # Title
        title_label = QLabel(title)
        title_label.setProperty("class", "section-title")
        layout.addWidget(title_label)

        # Subtitle (always create, hide if empty)
        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setProperty("class", "subtitle")
        if subtitle:
            layout.addWidget(self._subtitle_label)
        else:
            self._subtitle_label.hide()

    def set_subtitle(self, text: str) -> None:
        """Update the subtitle text."""
        self._subtitle_label.setText(text)
        if text and self._subtitle_label.isHidden():
            self._subtitle_label.show()


class Separator(QFrame):
    """A horizontal separator line."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("class", "separator")
        self.setFixedHeight(1)
