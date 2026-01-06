"""
Card widgets for metrics and content display.
"""

from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ..styles import COLORS, SPACING, FONTS, RADIUS, UI


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

        # Card styling - IMPROVED BORDERS
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["md"]}px;
            }}
            QFrame:hover {{
                border: 1px solid {COLORS["border_strong"]};
                background-color: {COLORS["bg_elevated"]};
            }}
        """)

        # Dimensions - MORE COMPACT
        self.setMinimumWidth(UI["card_min_width"])
        self.setMinimumHeight(UI["card_min_height"])
        self.setMaximumWidth(UI["card_max_width"])

        # Shadow effect - MORE SUBTLE
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)  # Reduced from 16
        shadow.setXOffset(0)
        shadow.setYOffset(2)  # Reduced from 4
        shadow.setColor(QColor(0, 0, 0, 60))  # More subtle (was 80)
        self.setGraphicsEffect(shadow)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"]
        )
        layout.setSpacing(SPACING["xs"])
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Value - BIGGER, BOLDER
        self._value_label = QLabel(value)
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_color = (
            self._accent_color if accent != "muted" else COLORS["text_primary"]
        )
        self._value_label.setStyleSheet(f"""
            font-size: {FONTS["size_3xl"]}px;
            font-weight: {FONTS["weight_extrabold"]};
            color: {value_color};
            letter-spacing: {FONTS["tracking_tighter"]}px;
            border: none;
            background: transparent;
        """)
        layout.addWidget(self._value_label)

        # Label - IMPROVED LETTER SPACING
        self._label = QLabel(label.upper())
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_bold"]};
            color: {COLORS["text_muted"]};
            letter-spacing: {FONTS["tracking_wider"]}px;
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
