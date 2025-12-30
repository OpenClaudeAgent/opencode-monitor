"""
Report generation module for OpenCode analytics.

This module provides HTML report generation with:
- CSS Design System (styles.py)
- Plotly charts (charts.py)
- HTML sections (sections.py)
- Main generator (generator.py)
"""

from .generator import AnalyticsReport, generate_html_report, generate_report
from .sections import format_tokens
from .styles import get_full_css

__all__ = [
    "AnalyticsReport",
    "generate_html_report",
    "generate_report",
    "format_tokens",
    "get_full_css",
]
