"""
Dashboard dimensions - Spacing, typography, and UI constants.

Design Philosophy:
- 8px base spacing system
- Soft rounded corners (not sharp)
- Strong typography hierarchy
"""

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
