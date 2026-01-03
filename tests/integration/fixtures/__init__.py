"""
Test fixtures and mock data for integration tests.

Provides realistic API responses and test data for dashboard testing.
"""

from .api_responses import (
    MockAPIResponses,
    create_session_data,
    create_trace_data,
    create_global_stats,
    create_monitoring_data,
    create_security_data,
)

__all__ = [
    "MockAPIResponses",
    "create_session_data",
    "create_trace_data",
    "create_global_stats",
    "create_monitoring_data",
    "create_security_data",
]
