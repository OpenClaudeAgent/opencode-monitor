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
    "sm": 4,  # Small radius (badges, buttons) - REDUCED (was 6)
    "md": 6,  # Medium radius (cards, inputs) - REDUCED (was 8)
    "lg": 8,  # Large radius (containers) - REDUCED (was 12)
    "xl": 12,  # Extra large (modals) - REDUCED (was 16)
    "full": 9999,  # Fully rounded (pills)
}

# ============================================================
# TYPOGRAPHY
# ============================================================

FONTS = {
    "family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    "mono": "ui-monospace, 'SF Mono', Menlo, Monaco, 'Courier New', monospace",
    # Sizes - IMPROVED HIERARCHY
    "size_xs": 11,  # Labels, badges
    "size_sm": 12,  # Secondary text
    "size_base": 13,  # Body text
    "size_md": 14,  # Emphasized body
    "size_lg": 16,  # Subtitles
    "size_xl": 18,  # Section headers
    "size_2xl": 28,  # Page titles - INCREASED (was 24)
    "size_3xl": 36,  # Large values in cards - INCREASED (was 32)
    "size_4xl": 48,  # Hero numbers - INCREASED (was 40)
    # Weights - MORE VARIATION
    "weight_normal": 400,
    "weight_medium": 500,
    "weight_semibold": 600,
    "weight_bold": 700,
    "weight_extrabold": 800,  # NEW: for important numbers
    # Letter spacing - REFINED
    "tracking_tighter": -0.8,  # NEW: for large numbers
    "tracking_tight": -0.5,
    "tracking_normal": 0,
    "tracking_wide": 0.5,
    "tracking_wider": 1.0,  # NEW: for uppercase labels
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
    # Cards - MORE COMPACT
    "card_min_width": 110,  # REDUCED (was 130)
    "card_min_height": 80,  # REDUCED (was 90)
    "card_max_width": 140,  # REDUCED (was 160)
    # Tables - MORE DENSE
    "row_height": 40,  # REDUCED (was 48)
    "header_height": 36,  # REDUCED (was 44)
    # NEW: Grid layout gaps
    "grid_gap_sm": 12,
    "grid_gap_md": 16,
    "grid_gap_lg": 24,
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
    "tracing": "◎",
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
