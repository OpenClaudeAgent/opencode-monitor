"""
Dashboard styles - Modern, minimal design system.

Design Philosophy:
- Dark theme with refined neutral palette
- Soft rounded corners (not sharp)
- Maximum clarity with generous spacing
- Strong typography hierarchy
- Subtle shadows for depth
"""

# ============================================================
# COLOR PALETTE - Modern Dark Theme
# ============================================================

COLORS = {
    # Backgrounds (layered depth)
    "bg_base": "#0f0f0f",  # Deepest background
    "bg_surface": "#1a1a1a",  # Cards, panels
    "bg_elevated": "#252525",  # Elevated elements
    "bg_hover": "#2a2a2a",  # Hover states
    "bg_active": "#303030",  # Active/pressed states
    # Text hierarchy
    "text_primary": "#ffffff",  # Primary text
    "text_secondary": "#a0a0a0",  # Secondary text
    "text_muted": "#666666",  # Muted/disabled text
    "text_inverse": "#0f0f0f",  # Text on light backgrounds
    # Accent colors
    "accent_primary": "#3b82f6",  # Blue 500
    "accent_primary_hover": "#60a5fa",  # Blue 400
    "accent_primary_muted": "rgba(59, 130, 246, 0.15)",
    "accent_success": "#22c55e",  # Green 500
    "accent_warning": "#f59e0b",  # Amber 500
    "accent_error": "#ef4444",  # Red 500
    # Semantic colors with muted backgrounds
    "success": "#22c55e",
    "success_muted": "rgba(34, 197, 94, 0.20)",
    "warning": "#f59e0b",
    "warning_muted": "rgba(245, 158, 11, 0.20)",
    "error": "#ef4444",
    "error_muted": "rgba(239, 68, 68, 0.20)",
    "info": "#3b82f6",
    "info_muted": "rgba(59, 130, 246, 0.20)",
    # Risk levels (semantic)
    "risk_critical": "#ef4444",  # Red 500
    "risk_critical_bg": "rgba(239, 68, 68, 0.20)",
    "risk_high": "#f97316",  # Orange 500
    "risk_high_bg": "rgba(249, 115, 22, 0.20)",
    "risk_medium": "#eab308",  # Yellow 500
    "risk_medium_bg": "rgba(234, 179, 8, 0.20)",
    "risk_low": "#22c55e",  # Green 500
    "risk_low_bg": "rgba(34, 197, 94, 0.20)",
    # Operation type colors (for badges)
    "type_command": "#a855f7",  # Violet 500
    "type_command_bg": "rgba(168, 85, 247, 0.20)",
    "type_bash": "#a855f7",
    "type_bash_bg": "rgba(168, 85, 247, 0.20)",
    "type_read": "#3b82f6",  # Blue 500
    "type_read_bg": "rgba(59, 130, 246, 0.20)",
    "type_write": "#f97316",  # Orange 500
    "type_write_bg": "rgba(249, 115, 22, 0.20)",
    "type_edit": "#eab308",  # Yellow 500
    "type_edit_bg": "rgba(234, 179, 8, 0.20)",
    "type_webfetch": "#06b6d4",  # Cyan 500
    "type_webfetch_bg": "rgba(6, 182, 212, 0.20)",
    "type_glob": "#ec4899",  # Pink 500
    "type_glob_bg": "rgba(236, 72, 153, 0.20)",
    "type_grep": "#10b981",  # Emerald 500
    "type_grep_bg": "rgba(16, 185, 129, 0.20)",
    "type_skill": "#8b5cf6",  # Violet 500
    "type_skill_bg": "rgba(139, 92, 246, 0.20)",
    # Borders (subtle)
    "border_subtle": "rgba(255, 255, 255, 0.06)",
    "border_default": "rgba(255, 255, 255, 0.10)",
    "border_strong": "rgba(255, 255, 255, 0.15)",
    # Sidebar
    "sidebar_bg": "#111111",
    "sidebar_hover": "rgba(255, 255, 255, 0.04)",
    "sidebar_active": "rgba(59, 130, 246, 0.12)",
    "sidebar_active_border": "#3b82f6",
    # Shadows
    "shadow_sm": "rgba(0, 0, 0, 0.3)",
    "shadow_md": "rgba(0, 0, 0, 0.4)",
}

# ============================================================
# SPACING SYSTEM (8px base)
# ============================================================

SPACING = {
    "xs": 4,  # Tight spacing
    "sm": 8,  # Small spacing (base)
    "md": 16,  # Medium spacing (2x)
    "lg": 24,  # Large spacing (3x)
    "xl": 32,  # Extra large (4x)
    "2xl": 48,  # 2x extra large (6x)
    "3xl": 64,  # 3x extra large (8x)
}

# ============================================================
# BORDER RADIUS (soft, not sharp)
# ============================================================

RADIUS = {
    "sm": 6,  # Small radius (badges, buttons)
    "md": 8,  # Medium radius (cards, inputs)
    "lg": 12,  # Large radius (containers)
    "xl": 16,  # Extra large (modals)
    "full": 9999,  # Fully rounded (pills)
}

# ============================================================
# TYPOGRAPHY
# ============================================================

FONTS = {
    "family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    "mono": "ui-monospace, 'SF Mono', Menlo, Monaco, 'Courier New', monospace",
    # Sizes
    "size_xs": 11,  # Labels, badges
    "size_sm": 12,  # Secondary text
    "size_base": 13,  # Body text
    "size_md": 14,  # Emphasized body
    "size_lg": 16,  # Subtitles
    "size_xl": 18,  # Section headers
    "size_2xl": 24,  # Page titles
    "size_3xl": 32,  # Large values in cards
    "size_4xl": 40,  # Hero numbers
    # Weights
    "weight_normal": 400,
    "weight_medium": 500,
    "weight_semibold": 600,
    "weight_bold": 700,
    # Letter spacing
    "tracking_tight": -0.5,
    "tracking_normal": 0,
    "tracking_wide": 0.5,
}

# ============================================================
# UI CONSTANTS
# ============================================================

UI = {
    # Refresh rates (milliseconds)
    "refresh_interval_ms": 2000,
    # Icon sizes
    "app_icon_size": 128,
    # Sidebar
    "sidebar_width": 220,
    "nav_item_height": 48,
    # Cards (compact but visible)
    "card_min_width": 130,
    "card_min_height": 90,
    "card_max_width": 160,
    # Tables
    "row_height": 48,
    "header_height": 44,
    # Limits for data display
    "table_row_limit": 20,
    "top_items_limit": 10,
    # Window
    "window_min_width": 1000,
    "window_min_height": 700,
    "window_default_width": 1200,
    "window_default_height": 800,
}

# ============================================================
# COLUMN WIDTHS (based on data type)
# ============================================================

COL_WIDTH = {
    # Text columns
    "name_short": 180,  # Tool names, short agent names
    "name_long": 280,  # Full agent names, descriptions
    "path": 320,  # File paths, directories
    # Numeric columns
    "number_tiny": 60,  # Single digit or small numbers (0-99)
    "number_small": 80,  # Small numbers (0-9999)
    "number_medium": 100,  # Medium numbers with formatting (10K, 1.2M)
    # Status/Type columns
    "status": 100,  # BUSY, IDLE (badge)
    "risk": 110,  # LOW, MEDIUM, HIGH, CRITICAL (badge)
    "type": 120,  # COMMAND, READ, WRITE, etc. (badge)
    # Other
    "duration": 90,  # 1m 30s, 500ms
    "percentage": 80,  # 48.2%, 100%
    "reason": 200,  # Short explanations
}

# ============================================================
# ICONS (Simple Unicode)
# ============================================================

ICONS = {
    # Navigation
    "monitoring": "●",
    "security": "◆",
    "analytics": "■",
    # Status
    "status_active": "●",
    "status_idle": "○",
    # Actions
    "arrow_up": "↑",
    "arrow_down": "↓",
    "check": "✓",
    "warning": "!",
    "error": "×",
    # Types
    "command": "⌘",
    "read": "◉",
    "write": "✎",
    "edit": "✏",
    "webfetch": "⬡",
    "glob": "⊕",
    "grep": "⊗",
}


# ============================================================
# UTILITY FUNCTIONS
# ============================================================


def format_tokens(count: int) -> str:
    """Format token count for display (e.g., 1500000 -> '1.5M').

    Args:
        count: Raw token count

    Returns:
        Formatted string with K/M suffix
    """
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.0f}K"
    return str(count)


def format_duration_ms(elapsed_ms: int) -> str:
    """Format duration in milliseconds for display.

    Args:
        elapsed_ms: Duration in milliseconds

    Returns:
        Human-readable duration string (e.g., '2m 30s', '5s', '250ms')
    """
    if elapsed_ms >= 60000:
        return f"{elapsed_ms // 60000}m {(elapsed_ms % 60000) // 1000}s"
    elif elapsed_ms >= 1000:
        return f"{elapsed_ms // 1000}s"
    return f"{elapsed_ms}ms"


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
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS["border_strong"]};
    min-height: 40px;
    border-radius: 4px;
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
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS["border_strong"]};
    min-width: 40px;
    border-radius: 4px;
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
    border-radius: {RADIUS["md"]}px;
    gridline-color: transparent;
    selection-background-color: {COLORS["bg_hover"]};
    outline: none;
}}

QTableWidget QTableCornerButton::section {{
    background-color: {COLORS["bg_elevated"]};
    border: none;
    border-top-left-radius: {RADIUS["md"]}px;
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
    padding: {SPACING["md"]}px {SPACING["md"]}px;
    border: none;
    border-bottom: 1px solid {COLORS["border_default"]};
    font-weight: {FONTS["weight_semibold"]};
    font-size: {FONTS["size_xs"]}px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QHeaderView::section:first {{
    border-top-left-radius: {RADIUS["md"]}px;
}}

QHeaderView::section:last {{
    border-top-right-radius: {RADIUS["md"]}px;
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
    border-radius: {RADIUS["sm"]}px;
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
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
    border-radius: {RADIUS["sm"]}px;
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
    border-radius: {RADIUS["sm"]}px;
    selection-background-color: {COLORS["bg_hover"]};
    selection-color: {COLORS["text_primary"]};
    outline: none;
    padding: {SPACING["xs"]}px;
}}

QComboBox QAbstractItemView::item {{
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    min-height: 32px;
    border-radius: {RADIUS["sm"]}px;
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
    border-radius: {RADIUS["sm"]}px;
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    font-size: {FONTS["size_sm"]}px;
}}
"""
