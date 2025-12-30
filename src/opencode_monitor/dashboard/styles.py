"""
Dashboard styles - QSS stylesheet based on UI Design Principles.

Design System:
- 8px spacing scale (xs:4, sm:8, md:16, lg:24, xl:32)
- Dark theme with blue tint
- Tinted grays (never pure gray)
- Consistent border radius (sm:6, md:10, lg:14)
"""

# Color palette
COLORS = {
    # Background surfaces
    "bg_base": "#12121a",
    "bg_surface": "#1a1a2e",
    "bg_elevated": "#1e2140",
    "bg_hover": "#252850",
    # Text
    "text_primary": "#f0f0f5",
    "text_secondary": "#a8a8c0",  # Improved contrast ratio ~5:1
    "text_muted": "#707088",
    # Accents
    "accent_primary": "#636EFA",
    "accent_success": "#00CC96",
    "accent_warning": "#FFA15A",
    "accent_error": "#EF553B",
    # Borders
    "border_subtle": "rgba(100, 110, 250, 0.15)",
    "border_default": "rgba(100, 110, 250, 0.25)",
}

# Spacing scale (8px base)
SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 16,
    "lg": 24,
    "xl": 32,
    "2xl": 48,
}

# Border radius
RADIUS = {
    "sm": 6,
    "md": 10,
    "lg": 14,
}


def get_stylesheet() -> str:
    """Get the complete QSS stylesheet for the dashboard."""
    return f"""
/* ========================================
   Global Styles
   ======================================== */

QWidget {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 14px;
    color: {COLORS["text_primary"]};
    background-color: {COLORS["bg_base"]};
}}

/* ========================================
   Main Window
   ======================================== */

QMainWindow {{
    background-color: {COLORS["bg_base"]};
}}

/* ========================================
   Tab Widget
   ======================================== */

QTabWidget::pane {{
    border: none;
    background-color: {COLORS["bg_base"]};
    margin-top: -1px;
}}

QTabWidget::tab-bar {{
    alignment: left;
}}

QTabBar {{
    background-color: {COLORS["bg_surface"]};
    border-bottom: 1px solid {COLORS["border_default"]};
}}

QTabBar::tab {{
    background-color: transparent;
    color: {COLORS["text_secondary"]};
    padding: {SPACING["md"]}px {SPACING["xl"]}px;
    margin: 0;
    border: none;
    border-bottom: 3px solid transparent;
    font-weight: 500;
    font-size: 14px;
    min-width: 120px;
}}

QTabBar::tab:selected {{
    background-color: transparent;
    color: {COLORS["accent_primary"]};
    border-bottom: 3px solid {COLORS["accent_primary"]};
    font-weight: 600;
}}

QTabBar::tab:hover:!selected {{
    color: {COLORS["text_primary"]};
    background-color: rgba(99, 110, 250, 0.08);
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
    background-color: {COLORS["bg_surface"]};
    width: 10px;
    border-radius: 5px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS["bg_elevated"]};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS["accent_primary"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {COLORS["bg_surface"]};
    height: 10px;
    border-radius: 5px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS["bg_elevated"]};
    border-radius: 5px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLORS["accent_primary"]};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ========================================
   Labels
   ======================================== */

QLabel {{
    color: {COLORS["text_primary"]};
    background-color: transparent;
}}

QLabel[class="title"] {{
    font-size: 24px;
    font-weight: 600;
    color: {COLORS["text_primary"]};
}}

QLabel[class="subtitle"] {{
    font-size: 14px;
    color: {COLORS["text_secondary"]};
}}

QLabel[class="section-title"] {{
    font-size: 20px;
    font-weight: 600;
    color: {COLORS["text_primary"]};
    padding-top: {SPACING["xs"]}px;
    padding-bottom: {SPACING["sm"]}px;
}}

QLabel[class="card-value"] {{
    font-size: 36px;
    font-weight: 700;
    color: {COLORS["accent_primary"]};
    line-height: 1.2;
}}

QLabel[class="card-label"] {{
    font-size: 12px;
    font-weight: 500;
    color: {COLORS["text_secondary"]};
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* ========================================
   Frames / Cards
   ======================================== */

QFrame[class="card"] {{
    background-color: {COLORS["bg_surface"]};
    border-radius: {RADIUS["md"]}px;
    border: 1px solid {COLORS["border_subtle"]};
    padding: {SPACING["lg"]}px;
}}

QFrame[class="card"]:hover {{
    border-color: {COLORS["border_default"]};
}}

QFrame[class="section"] {{
    background-color: transparent;
    border: none;
}}

/* ========================================
   Tables
   ======================================== */

QTableWidget {{
    background-color: {COLORS["bg_surface"]};
    border: 1px solid {COLORS["border_subtle"]};
    border-radius: {RADIUS["md"]}px;
    gridline-color: {COLORS["border_subtle"]};
    selection-background-color: {COLORS["bg_hover"]};
}}

QTableWidget::item {{
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    border-bottom: 1px solid {COLORS["border_subtle"]};
}}

QTableWidget::item:selected {{
    background-color: {COLORS["bg_hover"]};
    color: {COLORS["text_primary"]};
}}

QTableWidget::item:alternate {{
    background-color: rgba(30, 33, 64, 0.5);
}}

QHeaderView {{
    background-color: {COLORS["bg_elevated"]};
}}

QHeaderView::section {{
    background-color: {COLORS["bg_elevated"]};
    color: {COLORS["text_secondary"]};
    padding: 12px {SPACING["md"]}px;
    border: none;
    border-right: 1px solid {COLORS["border_default"]};
    border-bottom: 1px solid {COLORS["border_default"]};
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QHeaderView::section:last {{
    border-right: none;
}}

QHeaderView::section:hover {{
    background-color: {COLORS["bg_hover"]};
    color: {COLORS["text_primary"]};
}}

QHeaderView::section:first {{
    border-top-left-radius: {RADIUS["md"]}px;
}}

QHeaderView::section:last {{
    border-top-right-radius: {RADIUS["md"]}px;
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
    font-weight: 500;
    min-height: 32px;
}}

QPushButton:hover {{
    background-color: #7580fc;
}}

QPushButton:pressed {{
    background-color: #5058d8;
}}

QPushButton:disabled {{
    background-color: {COLORS["bg_elevated"]};
    color: {COLORS["text_muted"]};
}}

QPushButton[class="secondary"] {{
    background-color: transparent;
    color: {COLORS["accent_primary"]};
    border: 1px solid {COLORS["accent_primary"]};
}}

QPushButton[class="secondary"]:hover {{
    background-color: rgba(99, 110, 250, 0.1);
}}

/* ========================================
   Progress Bars
   ======================================== */

QProgressBar {{
    background-color: {COLORS["bg_elevated"]};
    border: none;
    border-radius: {RADIUS["sm"]}px;
    height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {COLORS["accent_primary"]};
    border-radius: {RADIUS["sm"]}px;
}}

/* ========================================
   Separators
   ======================================== */

QFrame[class="separator"] {{
    background-color: {COLORS["border_subtle"]};
    max-height: 1px;
    margin: {SPACING["md"]}px 0px;
}}

/* ========================================
   Status indicators
   ======================================== */

QLabel[class="status-busy"] {{
    color: {COLORS["accent_success"]};
    font-weight: 600;
}}

QLabel[class="status-idle"] {{
    color: {COLORS["text_muted"]};
    font-weight: 600;
}}

QLabel[class="risk-critical"] {{
    color: {COLORS["accent_error"]};
    font-weight: 600;
}}

QLabel[class="risk-high"] {{
    color: {COLORS["accent_warning"]};
    font-weight: 600;
}}

QLabel[class="risk-medium"] {{
    color: #e6b800;
    font-weight: 600;
}}

QLabel[class="risk-low"] {{
    color: {COLORS["accent_success"]};
    font-weight: 600;
}}

/* ========================================
   ComboBox (Dropdowns)
   ======================================== */

QComboBox {{
    background-color: {COLORS["bg_elevated"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border_default"]};
    border-radius: {RADIUS["sm"]}px;
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    padding-right: 32px;
    min-width: 140px;
    min-height: 32px;
    font-size: 13px;
    font-weight: 500;
}}

QComboBox:hover {{
    border-color: {COLORS["accent_primary"]};
    background-color: {COLORS["bg_hover"]};
}}

QComboBox:focus {{
    border-color: {COLORS["accent_primary"]};
    outline: none;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 28px;
    border: none;
    background-color: transparent;
}}

QComboBox::down-arrow {{
    /* Unicode chevron via border trick */
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {COLORS["text_secondary"]};
    margin-right: 8px;
}}

QComboBox:hover::down-arrow {{
    border-top-color: {COLORS["accent_primary"]};
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS["bg_surface"]};
    border: 1px solid {COLORS["border_default"]};
    border-radius: {RADIUS["sm"]}px;
    selection-background-color: {COLORS["bg_hover"]};
    selection-color: {COLORS["text_primary"]};
    outline: none;
    padding: {SPACING["xs"]}px;
    margin-top: 4px;
}}

QComboBox QAbstractItemView::item {{
    padding: {SPACING["sm"]}px {SPACING["md"]}px;
    min-height: 32px;
    border-radius: {RADIUS["sm"]}px;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {COLORS["bg_hover"]};
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: rgba(99, 110, 250, 0.2);
    color: {COLORS["accent_primary"]};
}}
"""
