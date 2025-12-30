"""
OpenCode Monitor Dashboard - PyQt6 visualization interface.

A modern dashboard with sidebar navigation featuring:
- Monitoring: Real-time agents, tools, and todos status
- Security: Risk analysis and command history
- Analytics: Usage statistics and trends
"""

from .window import DashboardWindow, show_dashboard
from .styles import COLORS, SPACING, RADIUS, FONTS, ICONS, get_stylesheet
from .widgets import (
    # Navigation
    Sidebar,
    NavItem,
    # Layout
    PageHeader,
    SectionHeader,
    Separator,
    Card,
    # Metrics
    MetricCard,
    MetricsRow,
    # Tables
    DataTable,
    # Status
    StatusBadge,
    EmptyState,
)
from .sections import MonitoringSection, SecuritySection, AnalyticsSection

__all__ = [
    # Main entry points
    "DashboardWindow",
    "show_dashboard",
    # Styles
    "COLORS",
    "SPACING",
    "RADIUS",
    "FONTS",
    "ICONS",
    "get_stylesheet",
    # Navigation
    "Sidebar",
    "NavItem",
    # Layout
    "PageHeader",
    "SectionHeader",
    "Separator",
    "Card",
    # Metrics
    "MetricCard",
    "MetricsRow",
    # Tables
    "DataTable",
    # Status
    "StatusBadge",
    "EmptyState",
    # Sections
    "MonitoringSection",
    "SecuritySection",
    "AnalyticsSection",
]
