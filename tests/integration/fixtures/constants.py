"""
Constants for integration tests.

Provides fixed values for reproducible testing.
"""

from datetime import datetime

# Fixed test date for reproducible tests (avoids datetime.now() non-determinism)
FIXED_TEST_DATE = datetime(2024, 1, 15, 10, 30, 0)

# Expected values from realistic_tracing() for assertions in tests
EXPECTED_TRACING = {
    "root_session_title": "Implement feature X",
    "root_session_id": "sess-root-001",
    "child_agent_type": "executor",
    "total_sessions": 3,
    "total_traces": 3,
    "root_tokens_in": 5000,
    "root_tokens_out": 8000,
    "root_duration_ms": 125000,
}

# Section indices (order in sidebar and pages)
SECTION_MONITORING = 0
SECTION_SECURITY = 1
SECTION_ANALYTICS = 2
SECTION_TRACING = 3

# Signal wait time for UI updates (increased for CI stability)
SIGNAL_WAIT_MS = 200
