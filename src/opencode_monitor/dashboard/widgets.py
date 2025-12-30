"""
Dashboard widgets - Clean, minimal design.

Design principles:
- Sharp edges, no rounded corners
- Clear visual hierarchy
- Minimal decoration
- Strong typography
"""

from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QWidget,
    QPushButton,
    QSizePolicy,
    QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from .styles import COLORS, SPACING, FONTS, ICONS


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================


class NavItem(QPushButton):
    """Sidebar navigation item."""

    def __init__(
        self,
        icon: str,
        text: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], 0, SPACING["lg"], 0)
        layout.setSpacing(SPACING["md"])

        # Icon
        self._icon = QLabel(icon)
        self._icon.setFixedWidth(20)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon)

        # Text
        self._text = QLabel(text)
        layout.addWidget(self._text)
        layout.addStretch()

        self._update_style()
        self.toggled.connect(self._update_style)

    def _update_style(self) -> None:
        """Update style based on state."""
        if self.isChecked():
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS["sidebar_active"]};
                    border: none;
                    border-left: 2px solid {COLORS["sidebar_active_border"]};
                    text-align: left;
                }}
            """)
            self._icon.setStyleSheet(
                f"color: {COLORS['accent_primary']}; font-size: 14px;"
            )
            self._text.setStyleSheet(f"""
                color: {COLORS["text_primary"]};
                font-size: {FONTS["size_md"]}px;
                font-weight: {FONTS["weight_medium"]};
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-left: 2px solid transparent;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {COLORS["sidebar_hover"]};
                }}
            """)
            self._icon.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 14px;")
            self._text.setStyleSheet(f"""
                color: {COLORS["text_secondary"]};
                font-size: {FONTS["size_md"]}px;
                font-weight: {FONTS["weight_normal"]};
            """)


class Sidebar(QFrame):
    """Sidebar navigation panel."""

    section_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(200)

        self.setStyleSheet(f"""
            QFrame#sidebar {{
                background-color: {COLORS["sidebar_bg"]};
                border-right: 1px solid {COLORS["border_default"]};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING["xl"], 0, SPACING["lg"])
        layout.setSpacing(0)

        # Logo
        logo_container = QWidget()
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.setContentsMargins(SPACING["lg"], 0, SPACING["lg"], SPACING["2xl"])
        logo_layout.setSpacing(SPACING["sm"])

        logo_icon = QLabel("⬡")
        logo_icon.setStyleSheet(f"font-size: 20px; color: {COLORS['accent_primary']};")
        logo_layout.addWidget(logo_icon)

        logo_text = QLabel("OpenCode")
        logo_text.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_bold"]};
            color: {COLORS["text_primary"]};
        """)
        logo_layout.addWidget(logo_text)
        logo_layout.addStretch()
        layout.addWidget(logo_container)

        # Section label
        section_label = QLabel("NAVIGATION")
        section_label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
            padding: 0 {SPACING["lg"]}px {SPACING["sm"]}px;
            letter-spacing: 1px;
        """)
        layout.addWidget(section_label)

        # Nav items
        self._nav_items: list[NavItem] = []
        nav_data = [
            (ICONS["monitoring"], "Monitoring"),
            (ICONS["security"], "Security"),
            (ICONS["analytics"], "Analytics"),
        ]

        for i, (icon, text) in enumerate(nav_data):
            item = NavItem(icon, text)
            item.clicked.connect(lambda checked, idx=i: self._on_item_clicked(idx))
            self._nav_items.append(item)
            layout.addWidget(item)

        layout.addStretch()

        # Status
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], 0)
        status_layout.setSpacing(SPACING["sm"])

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"font-size: 8px; color: {COLORS['success']};")
        status_layout.addWidget(self._status_dot)

        self._status_text = QLabel("Live")
        self._status_text.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            color: {COLORS["text_muted"]};
        """)
        status_layout.addWidget(self._status_text)
        status_layout.addStretch()
        layout.addWidget(status_container)

        # Select first by default
        if self._nav_items:
            self._nav_items[0].setChecked(True)

    def _on_item_clicked(self, index: int) -> None:
        for i, item in enumerate(self._nav_items):
            item.setChecked(i == index)
        self.section_changed.emit(index)

    def set_status(self, active: bool, text: str = "") -> None:
        color = COLORS["success"] if active else COLORS["text_muted"]
        self._status_dot.setStyleSheet(f"font-size: 8px; color: {color};")
        if text:
            self._status_text.setText(text)


# ============================================================
# PAGE HEADER
# ============================================================


class PageHeader(QWidget):
    """Page header with title and actions."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, SPACING["xl"])
        layout.setSpacing(SPACING["xs"])

        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(SPACING["lg"])

        self._title = QLabel(title)
        self._title.setStyleSheet(f"""
            font-size: {FONTS["size_2xl"]}px;
            font-weight: {FONTS["weight_bold"]};
            color: {COLORS["text_primary"]};
            letter-spacing: -0.5px;
        """)
        title_row.addWidget(self._title)
        title_row.addStretch()

        self._actions_layout = QHBoxLayout()
        self._actions_layout.setSpacing(SPACING["sm"])
        title_row.addLayout(self._actions_layout)

        layout.addLayout(title_row)

        if subtitle:
            self._subtitle = QLabel(subtitle)
            self._subtitle.setStyleSheet(f"""
                font-size: {FONTS["size_sm"]}px;
                color: {COLORS["text_muted"]};
            """)
            layout.addWidget(self._subtitle)

    def add_action(self, widget: QWidget) -> None:
        self._actions_layout.addWidget(widget)


# ============================================================
# METRIC CARDS
# ============================================================


class MetricCard(QFrame):
    """Compact metric display."""

    ACCENT_MAP = {
        "primary": COLORS["accent_primary"],
        "success": COLORS["success"],
        "warning": COLORS["warning"],
        "error": COLORS["error"],
        "muted": COLORS["text_muted"],
    }

    def __init__(
        self,
        value: str,
        label: str,
        accent: str = "primary",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._accent = accent
        accent_color = self.ACCENT_MAP.get(accent, COLORS["text_muted"])

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-top: 2px solid {accent_color};
            }}
        """)

        self.setMinimumWidth(120)
        self.setMaximumWidth(160)
        self.setFixedHeight(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"]
        )
        layout.setSpacing(SPACING["xs"])
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Value
        self._value_label = QLabel(value)
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_label.setStyleSheet(f"""
            font-size: {FONTS["size_2xl"]}px;
            font-weight: {FONTS["weight_bold"]};
            color: {COLORS["text_primary"]};
        """)
        layout.addWidget(self._value_label)

        # Label
        self._label = QLabel(label.upper())
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_medium"]};
            color: {COLORS["text_muted"]};
            letter-spacing: 0.5px;
        """)
        layout.addWidget(self._label)

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)


class MetricsRow(QWidget):
    """Row of metric cards."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, SPACING["sm"], 0, SPACING["sm"])
        self._layout.setSpacing(SPACING["md"])
        self._cards: dict[str, MetricCard] = {}

    def add_metric(
        self,
        key: str,
        value: str,
        label: str,
        accent: str = "primary",
    ) -> MetricCard:
        card = MetricCard(value, label, accent)
        self._cards[key] = card
        self._layout.addWidget(card)
        return card

    def update_metric(self, key: str, value: str) -> None:
        if key in self._cards:
            self._cards[key].set_value(value)

    def add_stretch(self) -> None:
        self._layout.addStretch()


# ============================================================
# STATUS BADGE
# ============================================================


class StatusBadge(QLabel):
    """Minimal status badge."""

    VARIANTS = {
        "success": (COLORS["success_muted"], COLORS["success"]),
        "warning": (COLORS["warning_muted"], COLORS["warning"]),
        "error": (COLORS["error_muted"], COLORS["error"]),
        "info": (COLORS["info_muted"], COLORS["info"]),
        "neutral": (COLORS["bg_elevated"], COLORS["text_secondary"]),
        "critical": (COLORS["error_muted"], COLORS["risk_critical"]),
        "high": (COLORS["warning_muted"], COLORS["risk_high"]),
        "medium": (COLORS["warning_muted"], COLORS["risk_medium"]),
        "low": (COLORS["success_muted"], COLORS["risk_low"]),
    }

    def __init__(
        self,
        text: str,
        variant: str = "neutral",
        parent: QWidget | None = None,
    ):
        super().__init__(text, parent)
        self.set_variant(variant)

    def set_variant(self, variant: str) -> None:
        bg, fg = self.VARIANTS.get(variant, self.VARIANTS["neutral"])
        self.setStyleSheet(f"""
            padding: {SPACING["xs"]}px {SPACING["sm"]}px;
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            background-color: {bg};
            color: {fg};
        """)


# ============================================================
# DATA TABLE
# ============================================================


class DataTable(QTableWidget):
    """Clean data table."""

    ROW_HEIGHT = 44
    HEADER_HEIGHT = 44

    def __init__(
        self,
        headers: list[str],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self._original_headers = headers.copy()
        self._current_sort_column = -1
        self._current_sort_order = Qt.SortOrder.AscendingOrder

        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        self.setSortingEnabled(True)

        # Hide row numbers and configure vertical header
        v_header = self.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(self.ROW_HEIGHT)

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        header = self.horizontalHeader()
        if header:
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setDefaultSectionSize(150)
            header.setMinimumSectionSize(60)
            header.setFixedHeight(self.HEADER_HEIGHT)
            header.setSortIndicatorShown(False)
            header.sortIndicatorChanged.connect(self._on_sort_changed)

        self.setFixedHeight(self.HEADER_HEIGHT + 2)

    def _on_sort_changed(self, column: int, order: Qt.SortOrder) -> None:
        for i, text in enumerate(self._original_headers):
            item = self.horizontalHeaderItem(i)
            if item:
                item.setText(text)

        if 0 <= column < len(self._original_headers):
            arrow = " ↑" if order == Qt.SortOrder.AscendingOrder else " ↓"
            item = self.horizontalHeaderItem(column)
            if item:
                item.setText(f"{self._original_headers[column]}{arrow}")

        self._current_sort_column = column
        self._current_sort_order = order

    def add_row(
        self,
        data: list[str | tuple[str, str]],
        full_values: list[str] | None = None,
    ) -> None:
        row = self.rowCount()
        self.insertRow(row)

        for col, item_data in enumerate(data):
            if isinstance(item_data, tuple):
                value, variant = item_data
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                color_map = {
                    # Status colors
                    "status-busy": COLORS["success"],
                    "status-idle": COLORS["text_muted"],
                    # Risk levels
                    "risk-critical": COLORS["risk_critical"],
                    "risk-high": COLORS["risk_high"],
                    "risk-medium": COLORS["risk_medium"],
                    "risk-low": COLORS["risk_low"],
                    # Operation types
                    "type-command": COLORS["type_command"],
                    "type-read": COLORS["type_read"],
                    "type-write": COLORS["type_write"],
                    "type-edit": COLORS["type_edit"],
                    "type-webfetch": COLORS["type_webfetch"],
                    "type-glob": COLORS["type_glob"],
                    "type-grep": COLORS["type_grep"],
                }
                if variant in color_map:
                    item.setForeground(QColor(color_map[variant]))
                    font = item.font()
                    font.setWeight(QFont.Weight.DemiBold)
                    item.setFont(font)
            else:
                value = item_data
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Tooltip
            if full_values and col < len(full_values):
                tooltip = full_values[col]
            else:
                tooltip = (
                    value
                    if isinstance(item_data, str)
                    else item_data[0]
                    if isinstance(item_data, tuple)
                    else ""
                )
            if tooltip and len(tooltip) > 30:
                item.setToolTip(tooltip)

            self.setItem(row, col, item)

        self._update_height()

    def clear_data(self) -> None:
        self.setRowCount(0)
        self._update_height()

    def _update_height(self) -> None:
        row_count = self.rowCount()
        header = self.horizontalHeader()
        header_height = header.height() if header else self.HEADER_HEIGHT
        content_height = row_count * self.ROW_HEIGHT
        self.setFixedHeight(header_height + content_height + 2)


# ============================================================
# SECTION COMPONENTS
# ============================================================


class SectionHeader(QWidget):
    """Section header with title."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING["sm"], 0, SPACING["lg"])
        layout.setSpacing(SPACING["xs"])

        self._title = QLabel(title)
        self._title.setStyleSheet(f"""
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)
        layout.addWidget(self._title)

        if subtitle:
            self._subtitle = QLabel(subtitle)
            self._subtitle.setStyleSheet(f"""
                font-size: {FONTS["size_sm"]}px;
                color: {COLORS["text_muted"]};
            """)
            layout.addWidget(self._subtitle)


class Separator(QFrame):
    """Horizontal separator."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background-color: {COLORS['border_subtle']};")


class Card(QFrame):
    """Simple card container."""

    def __init__(
        self,
        title: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
            }}
        """)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        self._layout.setSpacing(SPACING["md"])

        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet(f"""
                font-size: {FONTS["size_md"]}px;
                font-weight: {FONTS["weight_semibold"]};
                color: {COLORS["text_primary"]};
            """)
            self._layout.addWidget(title_label)

    def add_widget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)


# ============================================================
# SEGMENTED CONTROL
# ============================================================


class SegmentedControl(QWidget):
    """Elegant segmented control for period selection."""

    selection_changed = pyqtSignal(int)

    def __init__(
        self,
        options: list[str],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._options = options
        self._current_index = 0
        self._buttons: list[QPushButton] = []

        self.setStyleSheet(f"""
            SegmentedControl {{
                background-color: {COLORS["bg_elevated"]};
                border: 1px solid {COLORS["border_default"]};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xs"], SPACING["xs"], SPACING["xs"], SPACING["xs"]
        )
        layout.setSpacing(0)

        for i, option in enumerate(options):
            btn = QPushButton(option)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setMinimumHeight(28)
            btn.setMinimumWidth(90)
            btn.clicked.connect(lambda checked, idx=i: self._on_button_clicked(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)
            self._update_button_style(btn, i == 0)

        if self._buttons:
            self._buttons[0].setChecked(True)

    def _on_button_clicked(self, index: int) -> None:
        if index == self._current_index:
            # Keep it checked
            self._buttons[index].setChecked(True)
            return

        self._current_index = index
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
            self._update_button_style(btn, i == index)
        self.selection_changed.emit(index)

    def _update_button_style(self, btn: QPushButton, selected: bool) -> None:
        if selected:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS["accent_primary"]};
                    color: white;
                    border: none;
                    font-size: {FONTS["size_sm"]}px;
                    font-weight: {FONTS["weight_medium"]};
                    padding: 0 {SPACING["md"]}px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS["accent_primary_hover"]};
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLORS["text_secondary"]};
                    border: none;
                    font-size: {FONTS["size_sm"]}px;
                    font-weight: {FONTS["weight_normal"]};
                    padding: 0 {SPACING["md"]}px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS["bg_hover"]};
                    color: {COLORS["text_primary"]};
                }}
            """)

    def set_current_index(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._on_button_clicked(index)

    def current_index(self) -> int:
        return self._current_index


# ============================================================
# EMPTY STATE
# ============================================================


class EmptyState(QWidget):
    """Empty state placeholder."""

    def __init__(
        self,
        icon: str = "○",
        title: str = "No data",
        subtitle: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["2xl"], SPACING["2xl"], SPACING["2xl"], SPACING["2xl"]
        )
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"""
            font-size: 32px;
            color: {COLORS["text_muted"]};
        """)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_medium"]};
            color: {COLORS["text_secondary"]};
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setStyleSheet(f"""
                font-size: {FONTS["size_sm"]}px;
                color: {COLORS["text_muted"]};
            """)
            subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(subtitle_label)
