"""
Test fixtures and mock data for integration tests.

Provides realistic API responses and test data for dashboard testing.
"""

from .api_responses import (
    # Constants for reproducible tests
    FIXED_TEST_DATE,
    EXPECTED_TRACING,
    # Factory functions
    MockAPIResponses,
    create_session_data,
    create_trace_data,
    create_global_stats,
    create_monitoring_data,
    create_security_data,
)

__all__ = [
    # Constants
    "FIXED_TEST_DATE",
    "EXPECTED_TRACING",
    # Factory class and functions
    "MockAPIResponses",
    "create_session_data",
    "create_trace_data",
    "create_global_stats",
    "create_monitoring_data",
    "create_security_data",
    # Convenience re-exports
    "realistic_monitoring",
    "realistic_analytics",
    "realistic_security",
    "realistic_tracing",
    "api_error",
    "partial_data",
    "extreme_data",
    "malformed_types",
    "missing_required_fields",
    "api_becomes_unavailable",
    "monitoring_all_idle",
    "monitoring_all_waiting",
    "monitoring_error",
]

# Convenience re-exports for realistic data (from MockAPIResponses)
realistic_monitoring = MockAPIResponses.realistic_monitoring
realistic_analytics = MockAPIResponses.realistic_analytics
realistic_security = MockAPIResponses.realistic_security
realistic_tracing = MockAPIResponses.realistic_tracing

# Additional states for robustness testing
api_error = MockAPIResponses.api_error
partial_data = MockAPIResponses.partial_data
extreme_data = MockAPIResponses.extreme_data
malformed_types = MockAPIResponses.malformed_types
missing_required_fields = MockAPIResponses.missing_required_fields
api_becomes_unavailable = MockAPIResponses.api_becomes_unavailable
monitoring_all_idle = MockAPIResponses.realistic_monitoring_all_idle
monitoring_all_waiting = MockAPIResponses.realistic_monitoring_all_waiting
monitoring_error = MockAPIResponses.realistic_monitoring_error
