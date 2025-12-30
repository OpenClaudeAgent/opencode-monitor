"""
Analytics module for OpenCode Monitor.

Provides usage statistics and insights from OpenCode session data.
"""

from .db import AnalyticsDB
from .loader import load_opencode_data
from .queries import AnalyticsQueries
from .report import AnalyticsReport, generate_report

__all__ = [
    "AnalyticsDB",
    "load_opencode_data",
    "AnalyticsQueries",
    "AnalyticsReport",
    "generate_report",
]
