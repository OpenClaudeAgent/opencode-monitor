"""
Dashboard widgets - Modern, minimal design.

Design principles:
- Soft rounded corners
- Clear visual hierarchy
- Generous spacing
- Strong typography
- Semantic colors

This package provides re-exports for all widget classes to maintain
backwards compatibility with the original widgets.py module.
"""

# Navigation
from .navigation import NavItem, Sidebar

# Cards
from .cards import MetricCard, MetricsRow, Card

# Badges
from .badges import Badge, RiskBadge, TypeBadge, StatusBadge

# Tables
from .tables import DataTable

# Controls
from .controls import (
    PageHeader,
    SectionHeader,
    Separator,
    SegmentedControl,
    EmptyState,
)

__all__ = [
    # Navigation
    "NavItem",
    "Sidebar",
    # Cards
    "MetricCard",
    "MetricsRow",
    "Card",
    # Badges
    "Badge",
    "RiskBadge",
    "TypeBadge",
    "StatusBadge",
    # Tables
    "DataTable",
    # Controls
    "PageHeader",
    "SectionHeader",
    "Separator",
    "SegmentedControl",
    "EmptyState",
]
