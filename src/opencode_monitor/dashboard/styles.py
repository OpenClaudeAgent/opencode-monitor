"""
Dashboard styles - Clean, minimal design system.

Design Philosophy:
- Dark theme with refined neutral palette
- Sharp edges, no rounded corners
- Minimal decoration, maximum clarity
- Strong typography hierarchy
- Subtle borders, no heavy shadows
"""

# ============================================================
# COLOR PALETTE - Neutral & Clean
# ============================================================

COLORS = {
    # Background layers (neutral grays)
    "bg_base": "#0c0c0c",  # Near black
    "bg_surface": "#161616",  # Card/panel background
    "bg_elevated": "#1e1e1e",  # Elevated elements
    "bg_hover": "#262626",  # Hover states
    "bg_active": "#2e2e2e",  # Active/pressed states
    # Text hierarchy (high contrast)
    "text_primary": "#f4f4f4",  # Primary text
    "text_secondary": "#8c8c8c",  # Secondary text
    "text_muted": "#5c5c5c",  # Muted/disabled text
    "text_inverse": "#0c0c0c",  # Text on light backgrounds
    # Accent (single blue tone)
    "accent_primary": "#2563eb",  # Blue 600
    "accent_primary_hover": "#3b82f6",  # Blue 500
    "accent_primary_muted": "rgba(37, 99, 235, 0.15)",
    # Semantic colors (clear, distinct)
    "success": "#22c55e",  # Green 500
    "success_muted": "rgba(34, 197, 94, 0.15)",
    "warning": "#eab308",  # Yellow 500
    "warning_muted": "rgba(234, 179, 8, 0.15)",
    "error": "#ef4444",  # Red 500
    "error_muted": "rgba(239, 68, 68, 0.15)",
    "info": "#3b82f6",  # Blue 500
    "info_muted": "rgba(59, 130, 246, 0.15)",
    # Risk levels
    "risk_critical": "#dc2626",  # Red 600
    "risk_high": "#ea580c",  # Orange 600
    "risk_medium": "#ca8a04",  # Yellow 600
    "risk_low": "#16a34a",  # Green 600
    # Operation types (colorful distinction)
    "type_command": "#a855f7",  # Purple 500 - Shell commands
    "type_command_bg": "rgba(168, 85, 247, 0.15)",
    "type_read": "#3b82f6",  # Blue 500 - Read operations
    "type_read_bg": "rgba(59, 130, 246, 0.15)",
    "type_write": "#f97316",  # Orange 500 - Write operations
    "type_write_bg": "rgba(249, 115, 22, 0.15)",
    "type_edit": "#eab308",  # Yellow 500 - Edit operations
    "type_edit_bg": "rgba(234, 179, 8, 0.15)",
    "type_webfetch": "#06b6d4",  # Cyan 500 - Web fetch
    "type_webfetch_bg": "rgba(6, 182, 212, 0.15)",
    "type_glob": "#ec4899",  # Pink 500 - Glob search
    "type_glob_bg": "rgba(236, 72, 153, 0.15)",
    "type_grep": "#10b981",  # Emerald 500 - Grep search
    "type_grep_bg": "rgba(16, 185, 129, 0.15)",
    # Borders (minimal)
    "border_subtle": "#1e1e1e",
    "border_default": "#2a2a2a",
    "border_strong": "#3a3a3a",
    # Sidebar
    "sidebar_bg": "#111111",
    "sidebar_hover": "rgba(255, 255, 255, 0.04)",
    "sidebar_active": "rgba(37, 99, 235, 0.12)",
    "sidebar_active_border": "#2563eb",
}

# ============================================================
# SPACING SYSTEM (4px base)
# ============================================================

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "2xl": 32,
    "3xl": 48,
    "4xl": 64,
}

# ============================================================
# BORDER RADIUS - Minimal (mostly 0)
# ============================================================

RADIUS = {
    "none": 0,
    "xs": 2,
    "sm": 3,
    "md": 4,
    "lg": 6,
}

# ============================================================
# TYPOGRAPHY
# ============================================================

FONTS = {
    "family": "'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    "mono": "Menlo, Monaco, 'Courier New', monospace",
    "size_xs": 11,
    "size_sm": 12,
    "size_base": 13,
    "size_md": 14,
    "size_lg": 15,
    "size_xl": 18,
    "size_2xl": 20,
    "size_3xl": 26,
    "weight_normal": 400,
    "weight_medium": 500,
    "weight_semibold": 600,
    "weight_bold": 700,
}

# ============================================================
# ICONS (Simple Unicode)
# ============================================================

ICONS = {
    "monitoring": "●",
    "security": "◆",
    "analytics": "■",
    "status_active": "●",
    "status_idle": "○",
    "arrow_up": "↑",
    "arrow_down": "↓",
    "check": "✓",
    "warning": "!",
    "error": "×",
}


def get_stylesheet() -> str:
    """Get the complete QSS stylesheet for the dashboard."""
    return f"""
/* ========================================
   Global Reset & Base
   ======================================== */

* {{
    outline: none;
}}

QWidget {{
    font-family: {FONTS["family"]};
    font-size: {FONTS["size_base"]}px;
    color: {COLORS["text_primary"]};
    background-color: transparent;
}}

/* ========================================
   Main Window
   ======================================== */

QMainWindow {{
    background-color: {COLORS["bg_base"]};
}}

/* ========================================
   Sidebar
   ======================================== */

QFrame#sidebar {{
    background-color: {COLORS["sidebar_bg"]};
    border-right: 1px solid {COLORS["border_default"]};
}}

/* ========================================
   Scroll Areas
   ======================================== */

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS["border_strong"]};
    min-height: 40px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS["text_muted"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS["border_strong"]};
    min-width: 40px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLORS["text_muted"]};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ========================================
   Tables
   ======================================== */

QTableWidget {{
    background-color: {COLORS["bg_surface"]};
    border: 1px solid {COLORS["border_default"]};
    gridline-color: transparent;
    selection-background-color: {COLORS["bg_hover"]};
    outline: none;
}}

QTableWidget QTableCornerButton::section {{
    background-color: {COLORS["bg_elevated"]};
    border: none;
}}

QTableWidget::item {{
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    border: none;
    border-bottom: 1px solid {COLORS["border_subtle"]};
}}

QTableWidget::item:selected {{
    background-color: {COLORS["sidebar_active"]};
    color: {COLORS["text_primary"]};
}}

QHeaderView {{
    background-color: transparent;
}}

QHeaderView::section {{
    background-color: {COLORS["bg_elevated"]};
    color: {COLORS["text_muted"]};
    padding: {SPACING["md"]}px {SPACING["lg"]}px;
    border: none;
    border-bottom: 1px solid {COLORS["border_default"]};
    font-weight: {FONTS["weight_semibold"]};
    font-size: {FONTS["size_xs"]}px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QHeaderView::section:hover {{
    background-color: {COLORS["bg_hover"]};
    color: {COLORS["text_secondary"]};
}}

/* ========================================
   Buttons
   ======================================== */

QPushButton {{
    background-color: {COLORS["accent_primary"]};
    color: white;
    border: none;
    padding: {SPACING["sm"]}px {SPACING["lg"]}px;
    font-weight: {FONTS["weight_medium"]};
    font-size: {FONTS["size_sm"]}px;
    min-height: 32px;
}}

QPushButton:hover {{
    background-color: {COLORS["accent_primary_hover"]};
}}

QPushButton:pressed {{
    background-color: #1d4ed8;
}}

QPushButton:disabled {{
    background-color: {COLORS["bg_elevated"]};
    color: {COLORS["text_muted"]};
}}

/* ========================================
   ComboBox
   ======================================== */

QComboBox {{
    background-color: {COLORS["bg_elevated"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border_default"]};
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    padding-right: 28px;
    min-width: 140px;
    min-height: 32px;
    font-size: {FONTS["size_sm"]}px;
}}

QComboBox:hover {{
    border-color: {COLORS["border_strong"]};
}}

QComboBox:focus {{
    border-color: {COLORS["accent_primary"]};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border: none;
}}

QComboBox::down-arrow {{
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLORS["text_muted"]};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS["bg_surface"]};
    border: 1px solid {COLORS["border_default"]};
    selection-background-color: {COLORS["bg_hover"]};
    selection-color: {COLORS["text_primary"]};
    outline: none;
    padding: {SPACING["xs"]}px;
}}

QComboBox QAbstractItemView::item {{
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    min-height: 32px;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {COLORS["bg_hover"]};
}}

/* ========================================
   Tooltips
   ======================================== */

QToolTip {{
    background-color: {COLORS["bg_elevated"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border_default"]};
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    font-size: {FONTS["size_sm"]}px;
}}
"""
