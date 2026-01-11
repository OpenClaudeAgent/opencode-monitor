"""
Constants for integration tests.

Provides fixed values for reproducible testing.
"""

from datetime import datetime

FIXED_TEST_DATE = datetime(2024, 1, 15, 10, 30, 0)

EXPECTED_TRACING = {
    "root_session_title": "Implement feature X",
    "root_session_id": "sess-root-001",
    "child_subagent_type": "executor",
    "delegation_subagent_type": "tester",
    "total_sessions": 4,
    "total_traces": 4,
    "root_tokens_in": 5000,
    "root_tokens_out": 8000,
    "root_duration_ms": 125000,
}

SECTION_MONITORING = 0
SECTION_SECURITY = 1
SECTION_ANALYTICS = 2
SECTION_TRACING = 3


def process_qt_events():
    """Process pending Qt events immediately instead of waiting fixed time."""
    from PyQt6.QtWidgets import QApplication

    QApplication.processEvents()
