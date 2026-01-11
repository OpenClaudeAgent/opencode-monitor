"""
Test fixtures for integration tests.

Provides:
- Factory functions for creating test data
- Pre-built mock responses for common scenarios
- Constants for reproducible testing
"""

from .constants import (
    EXPECTED_TRACING,
    FIXED_TEST_DATE,
    SECTION_ANALYTICS,
    SECTION_MONITORING,
    SECTION_SECURITY,
    SECTION_TRACING,
    process_qt_events,
)

# Factory functions
from .factories import (
    create_global_stats,
    create_monitoring_data,
    create_security_data,
    create_session_data,
    create_trace_data,
)

# Domain-specific responses
from .monitoring import (
    empty_monitoring,
    realistic_monitoring,
    realistic_monitoring_all_idle,
    realistic_monitoring_all_waiting,
    realistic_monitoring_error,
)
from .security import realistic_security
from .analytics import realistic_analytics
from .tracing import realistic_tracing

# Main mock responses class
from .mock_responses import MockAPIResponses

__all__ = [
    "FIXED_TEST_DATE",
    "EXPECTED_TRACING",
    "SECTION_MONITORING",
    "SECTION_SECURITY",
    "SECTION_ANALYTICS",
    "SECTION_TRACING",
    "process_qt_events",
    # Factories
    "create_session_data",
    "create_trace_data",
    "create_global_stats",
    "create_monitoring_data",
    "create_security_data",
    # Domain responses
    "empty_monitoring",
    "realistic_monitoring",
    "realistic_monitoring_all_idle",
    "realistic_monitoring_all_waiting",
    "realistic_monitoring_error",
    "realistic_security",
    "realistic_analytics",
    "realistic_tracing",
    # Main class
    "MockAPIResponses",
    # Legacy aliases for backward compatibility
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

# Legacy aliases for backward compatibility
api_error = MockAPIResponses.api_error
partial_data = MockAPIResponses.partial_data
extreme_data = MockAPIResponses.extreme_data
malformed_types = MockAPIResponses.malformed_types
missing_required_fields = MockAPIResponses.missing_required_fields
api_becomes_unavailable = MockAPIResponses.api_becomes_unavailable
monitoring_all_idle = realistic_monitoring_all_idle
monitoring_all_waiting = realistic_monitoring_all_waiting
monitoring_error = realistic_monitoring_error
