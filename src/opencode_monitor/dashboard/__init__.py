"""
OpenCode Monitor Dashboard - PyQt6 visualization interface.

Provides a tabbed dashboard with:
- Monitoring: Real-time agents, tools, and todos status
- Security: Risk analysis and command history
- Analytics: Usage statistics and trends
"""

from .window import DashboardWindow, show_dashboard
from .styles import COLORS, SPACING, RADIUS, get_stylesheet
from .widgets import Card, MetricCard, MetricsRow, DataTable, SectionHeader, Separator
from .sections import MonitoringSection, SecuritySection, AnalyticsSection

__all__ = [
    # Main entry points
    "DashboardWindow",
    "show_dashboard",
    # Styles
    "COLORS",
    "SPACING",
    "RADIUS",
    "get_stylesheet",
    # Widgets
    "Card",
    "MetricCard",
    "MetricsRow",
    "DataTable",
    "SectionHeader",
    "Separator",
    # Sections
    "MonitoringSection",
    "SecuritySection",
    "AnalyticsSection",
]
