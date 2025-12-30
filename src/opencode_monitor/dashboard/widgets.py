"""
Dashboard widgets - Modern, minimal design.

Design principles:
- Soft rounded corners
- Clear visual hierarchy
- Generous spacing
- Strong typography
- Semantic colors
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
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from .styles import COLORS, SPACING, FONTS, RADIUS, ICONS, UI


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
        self.setMinimumHeight(UI["nav_item_height"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], 0, SPACING["lg"], 0)
        layout.setSpacing(SPACING["md"])

        # Icon
        self._icon = QLabel(icon)
        self._icon.setFixedWidth(24)
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
                    border-left: 3px solid {COLORS["sidebar_active_border"]};
                    border-radius: 0;
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
                    border-left: 3px solid transparent;
                    border-radius: 0;
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
        self.setFixedWidth(UI["sidebar_width"])

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
        logo_icon.setStyleSheet(f"font-size: 24px; color: {COLORS['accent_primary']};")
        logo_layout.addWidget(logo_icon)

        logo_text = QLabel("OpenCode")
        logo_text.setStyleSheet(f"""
            font-size: {FONTS["size_xl"]}px;
            font-weight: {FONTS["weight_bold"]};
            color: {COLORS["text_primary"]};
            letter-spacing: -0.5px;
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
        self._status_dot.setStyleSheet(f"font-size: 10px; color: {COLORS['success']};")
        status_layout.addWidget(self._status_dot)

        self._status_text = QLabel("Live")
        self._status_text.setStyleSheet(f"""
            font-size: {FONTS["size_sm"]}px;
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
        self._status_dot.setStyleSheet(f"font-size: 10px; color: {color};")
        if text:
            self._status_text.setText(text)


# ============================================================
# PAGE HEADER
# ============================================================


class PageHeader(QWidget):
    """Page header with title, subtitle and actions."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, SPACING["lg"])
        layout.setSpacing(SPACING["xs"])

        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(SPACING["lg"])

        self._title = QLabel(title)
        self._title.setStyleSheet(f"""
            font-size: {FONTS["size_xl"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
            letter-spacing: -0.3px;
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
                font-size: {FONTS["size_base"]}px;
                color: {COLORS["text_muted"]};
            """)
            layout.addWidget(self._subtitle)

    def add_action(self, widget: QWidget) -> None:
        self._actions_layout.addWidget(widget)


# ============================================================
# METRIC CARDS (Centered, with shadow)
# ============================================================


class MetricCard(QFrame):
    """Centered metric card with subtle shadow."""

    ACCENT_MAP = {
        "primary": COLORS["accent_primary"],
        "success": COLORS["accent_success"],
        "warning": COLORS["accent_warning"],
        "error": COLORS["accent_error"],
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
        self._accent_color = self.ACCENT_MAP.get(accent, COLORS["text_muted"])

        # Card styling - no border, just shadow for elevation
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: none;
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        # Dimensions - generous sizing for large numbers
        self.setMinimumWidth(UI["card_min_width"])
        self.setMinimumHeight(UI["card_min_height"])
        self.setMaximumWidth(UI["card_max_width"])

        # Shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        # Layout - truly centered with generous padding
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["sm"])
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Value (large, colored if accent) - NO border
        self._value_label = QLabel(value)
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_color = (
            self._accent_color if accent != "muted" else COLORS["text_primary"]
        )
        self._value_label.setStyleSheet(f"""
            font-size: {FONTS["size_2xl"]}px;
            font-weight: {FONTS["weight_bold"]};
            color: {value_color};
            letter-spacing: -0.5px;
            border: none;
            background: transparent;
        """)
        layout.addWidget(self._value_label)

        # Label (uppercase, muted) - NO border
        self._label = QLabel(label.upper())
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
            letter-spacing: 0.5px;
            border: none;
            background: transparent;
        """)
        layout.addWidget(self._label)

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)


class MetricsRow(QWidget):
    """Row of metric cards with proper spacing."""

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
# BADGES (Risk and Type)
# ============================================================


class Badge(QLabel):
    """Base badge with pill style."""

    def __init__(
        self,
        text: str,
        bg_color: str,
        text_color: str,
        parent: QWidget | None = None,
    ):
        super().__init__(text.upper(), parent)
        self.setStyleSheet(f"""
            padding: {SPACING["xs"]}px {SPACING["sm"] + 4}px;
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_bold"]};
            background-color: {bg_color};
            color: {text_color};
            border-radius: {RADIUS["sm"]}px;
            letter-spacing: 0.3px;
        """)


class RiskBadge(Badge):
    """Badge for risk levels."""

    VARIANTS = {
        "critical": (COLORS["risk_critical_bg"], COLORS["risk_critical"]),
        "high": (COLORS["risk_high_bg"], COLORS["risk_high"]),
        "medium": (COLORS["risk_medium_bg"], COLORS["risk_medium"]),
        "low": (COLORS["risk_low_bg"], COLORS["risk_low"]),
    }

    def __init__(
        self,
        level: str,
        parent: QWidget | None = None,
    ):
        level_lower = level.lower()
        bg, fg = self.VARIANTS.get(
            level_lower, (COLORS["bg_elevated"], COLORS["text_secondary"])
        )
        super().__init__(level, bg, fg, parent)


class TypeBadge(Badge):
    """Badge for operation types."""

    TYPE_MAP = {
        "command": ("type_command_bg", "type_command"),
        "bash": ("type_bash_bg", "type_bash"),
        "read": ("type_read_bg", "type_read"),
        "write": ("type_write_bg", "type_write"),
        "edit": ("type_edit_bg", "type_edit"),
        "webfetch": ("type_webfetch_bg", "type_webfetch"),
        "web_fetch": ("type_webfetch_bg", "type_webfetch"),
        "glob": ("type_glob_bg", "type_glob"),
        "grep": ("type_grep_bg", "type_grep"),
        "skill": ("type_skill_bg", "type_skill"),
    }

    def __init__(
        self,
        op_type: str,
        parent: QWidget | None = None,
    ):
        type_lower = op_type.lower()
        bg_key, fg_key = self.TYPE_MAP.get(
            type_lower, ("bg_elevated", "text_secondary")
        )
        bg = COLORS.get(bg_key, COLORS["bg_elevated"])
        fg = COLORS.get(fg_key, COLORS["text_secondary"])
        super().__init__(op_type, bg, fg, parent)


class StatusBadge(QLabel):
    """Status badge (busy/idle)."""

    VARIANTS = {
        "success": (COLORS["success_muted"], COLORS["success"]),
        "warning": (COLORS["warning_muted"], COLORS["warning"]),
        "error": (COLORS["error_muted"], COLORS["error"]),
        "info": (COLORS["info_muted"], COLORS["info"]),
        "neutral": (COLORS["bg_elevated"], COLORS["text_secondary"]),
        "critical": (COLORS["risk_critical_bg"], COLORS["risk_critical"]),
        "high": (COLORS["risk_high_bg"], COLORS["risk_high"]),
        "medium": (COLORS["risk_medium_bg"], COLORS["risk_medium"]),
        "low": (COLORS["risk_low_bg"], COLORS["risk_low"]),
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
            padding: {SPACING["xs"]}px {SPACING["sm"] + 4}px;
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_bold"]};
            background-color: {bg};
            color: {fg};
            border-radius: {RADIUS["sm"]}px;
        """)


# ============================================================
# SEGMENTED CONTROL (Modern tabs)
# ============================================================


class SegmentedControl(QWidget):
    """Modern segmented control for period selection."""

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

        # Container styling
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS["bg_elevated"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["sm"]}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        for i, option in enumerate(options):
            btn = QPushButton(option)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setMinimumHeight(28)
            btn.setMinimumWidth(80)
            btn.clicked.connect(lambda checked, idx=i: self._on_button_clicked(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)
            self._update_button_style(btn, i == 0)

        if self._buttons:
            self._buttons[0].setChecked(True)

    def _on_button_clicked(self, index: int) -> None:
        if index == self._current_index:
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
                    border-radius: {RADIUS["sm"] - 2}px;
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
                    color: {COLORS["text_muted"]};
                    border: none;
                    border-radius: {RADIUS["sm"] - 2}px;
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
# DATA TABLE (Enhanced)
# ============================================================


class DataTable(QTableWidget):
    """Enhanced data table with better styling."""

    ROW_HEIGHT = UI["row_height"]
    HEADER_HEIGHT = UI["header_height"]

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

        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        self.setSortingEnabled(True)

        # Alternating row colors
        palette = self.palette()
        palette.setColor(palette.ColorRole.Base, QColor(COLORS["bg_surface"]))
        palette.setColor(palette.ColorRole.AlternateBase, QColor(COLORS["bg_elevated"]))
        self.setPalette(palette)

        # Hide row numbers
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
            header.setMinimumSectionSize(80)
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
        # Disable sorting while adding rows to prevent data corruption
        self.setSortingEnabled(False)

        row = self.rowCount()
        self.insertRow(row)

        for col, item_data in enumerate(data):
            if isinstance(item_data, tuple):
                value, variant = item_data
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Color mapping for variants
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
                    "type-bash": COLORS["type_bash"],
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
                item.setForeground(QColor(COLORS["text_secondary"]))

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

        # Re-enable sorting after adding row
        self.setSortingEnabled(True)

    def clear_data(self) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(0)
        self._update_height()
        self.setSortingEnabled(True)

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
    """Section header with title and optional subtitle."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, SPACING["md"], 0, SPACING["lg"])
        layout.setSpacing(0)

        # Left side: title and subtitle
        left_layout = QVBoxLayout()
        left_layout.setSpacing(SPACING["xs"])

        self._title = QLabel(title)
        self._title.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)
        left_layout.addWidget(self._title)

        if subtitle:
            self._subtitle = QLabel(subtitle)
            self._subtitle.setStyleSheet(f"""
                font-size: {FONTS["size_base"]}px;
                color: {COLORS["text_muted"]};
            """)
            left_layout.addWidget(self._subtitle)

        layout.addLayout(left_layout)
        layout.addStretch()

        # Right side: for actions
        self._actions_layout = QHBoxLayout()
        self._actions_layout.setSpacing(SPACING["sm"])
        layout.addLayout(self._actions_layout)

    def add_action(self, widget: QWidget) -> None:
        self._actions_layout.addWidget(widget)


class Separator(QFrame):
    """Horizontal separator with generous margin."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"""
            background-color: {COLORS["border_subtle"]};
            margin: {SPACING["lg"]}px 0;
        """)


class Card(QFrame):
    """Card container with rounded corners."""

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
                border-radius: {RADIUS["md"]}px;
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
# EMPTY STATE
# ============================================================


class EmptyState(QWidget):
    """Empty state placeholder with icon."""

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
            SPACING["2xl"], SPACING["xl"], SPACING["2xl"], SPACING["xl"]
        )
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(SPACING["sm"])

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"""
            font-size: 36px;
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
                font-size: {FONTS["size_base"]}px;
                color: {COLORS["text_muted"]};
            """)
            subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(subtitle_label)
