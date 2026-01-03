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

# Convenience re-exports for realistic data (from MockAPIResponses)
realistic_monitoring = MockAPIResponses.realistic_monitoring
realistic_analytics = MockAPIResponses.realistic_analytics
realistic_security = MockAPIResponses.realistic_security
realistic_tracing = MockAPIResponses.realistic_tracing
