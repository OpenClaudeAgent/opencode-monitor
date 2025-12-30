"""
OpenCode Analytics module.

Provides analytics and reporting for OpenCode session data.

Structure:
- models.py: Data models (dataclasses)
- db.py: DuckDB database management
- collector.py: Background incremental data collection
- loader.py: Bulk data loading (legacy)
- queries.py: SQL queries
- report/: HTML report generation
"""

from .db import AnalyticsDB, get_analytics_db
from .collector import get_collector, start_collector, stop_collector
from .loader import load_opencode_data
from .models import PeriodStats, TokenStats
from .queries import AnalyticsQueries
from .report import AnalyticsReport, generate_report

__all__ = [
    # Database
    "AnalyticsDB",
    # Collector (incremental background loading)
    "get_collector",
    "start_collector",
    "stop_collector",
    # Data loading (legacy bulk)
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
