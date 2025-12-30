"""
OpenCode Analytics module.

Provides analytics and reporting for OpenCode session data.

Structure:
- models.py: Data models (dataclasses)
- db.py: DuckDB database management
- loader.py: Data loading from OpenCode storage
- queries.py: SQL queries
- report/: HTML report generation
"""

from .db import AnalyticsDB
from .loader import load_opencode_data
from .models import PeriodStats, TokenStats
from .queries import AnalyticsQueries
from .report import AnalyticsReport, generate_report

__all__ = [
    # Database
    "AnalyticsDB",
    # Data loading
    "load_opencode_data",
    # Models
    "PeriodStats",
    "TokenStats",
    # Queries
    "AnalyticsQueries",
    # Report
    "AnalyticsReport",
    "generate_report",
]
