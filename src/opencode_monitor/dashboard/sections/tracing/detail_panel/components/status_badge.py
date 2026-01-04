"""StatusBadge - Visual status indicator with different states."""

from PyQt6.QtWidgets import QLabel, QWidget

from opencode_monitor.dashboard.styles import COLORS, SPACING, FONTS, RADIUS


class StatusBadge(QLabel):
    """Visual badge showing status (completed, running, error, etc.)."""

    # Status configuration: (text, bg_color_key, text_color_key)
    STATUS_STYLES = {
        "completed": ("Completed", "success_muted", "success"),
        "running": ("Running", "warning_muted", "warning"),
        "error": ("Error", "error_muted", "error"),
        "session": ("Session", "info_muted", "info"),
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.hide()  # Hidden by default

    def _apply_style(self, bg_color: str, text_color: str) -> None:
        """Apply style with specific colors."""
        self.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            padding: {SPACING["xs"]}px {SPACING["sm"]}px;
            border-radius: {RADIUS["sm"]}px;
            background-color: {bg_color};
            color: {text_color};
        """)

    def set_status(self, status: str) -> None:
        """Set the badge status.

        Args:
            status: One of 'completed', 'running', 'error', 'session' or any custom status
        """
        status_lower = status.lower() if status else "unknown"

        if status_lower == "completed":
            self.setText("Completed")
            self._apply_style(COLORS["success_muted"], COLORS["success"])
        elif status_lower == "running":
            self.setText("Running")
            self._apply_style(COLORS["warning_muted"], COLORS["warning"])
        elif status_lower == "error":
            self.setText("Error")
            self._apply_style(COLORS["error_muted"], COLORS["error"])
        elif status_lower == "session":
            self.setText("Session")
            self._apply_style(COLORS["info_muted"], COLORS["info"])
        else:
            # Unknown status - capitalize and show with info style
            display_text = status.capitalize() if status else "Unknown"
            self.setText(f"{display_text}")
            self._apply_style(COLORS["info_muted"], COLORS["info"])

        self.show()

    def set_custom(self, text: str, style: str = "info") -> None:
        """Set custom text with a predefined style.

        Args:
            text: Text to display
            style: One of 'success', 'warning', 'error', 'info'
        """
        self.setText(text)

        style_map = {
            "success": (COLORS["success_muted"], COLORS["success"]),
            "warning": (COLORS["warning_muted"], COLORS["warning"]),
            "error": (COLORS["error_muted"], COLORS["error"]),
            "info": (COLORS["info_muted"], COLORS["info"]),
        }

        bg_color, text_color = style_map.get(
            style, (COLORS["info_muted"], COLORS["info"])
        )
        self._apply_style(bg_color, text_color)
        self.show()

    def clear(self) -> None:
        """Hide the badge."""
        self.hide()
