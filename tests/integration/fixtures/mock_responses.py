"""
MockAPIResponses class with pre-built API responses.

Provides a unified interface for accessing mock responses for
different test scenarios (empty, basic, complex, edge cases).
"""

from datetime import timedelta
from typing import Any

from .constants import FIXED_TEST_DATE
from .factories import create_global_stats, create_session_data
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


class MockAPIResponses:
    """Pre-built API responses for common test scenarios."""

    # Re-export domain-specific functions as static methods
    empty_monitoring = staticmethod(empty_monitoring)
    realistic_monitoring = staticmethod(realistic_monitoring)
    realistic_monitoring_all_idle = staticmethod(realistic_monitoring_all_idle)
    realistic_monitoring_all_waiting = staticmethod(realistic_monitoring_all_waiting)
    realistic_monitoring_error = staticmethod(realistic_monitoring_error)
    realistic_security = staticmethod(realistic_security)
    realistic_analytics = staticmethod(realistic_analytics)
    realistic_tracing = staticmethod(realistic_tracing)

    @staticmethod
    def empty() -> dict[str, Any]:
        """Empty responses for testing initial state."""
        return {
            "health": True,
            "stats": {"sessions": 0, "traces": 0, "messages": 0},
            "global_stats": create_global_stats(0, 0, 0, 0, 0),
            "sessions": [],
            "delegations": [],
        }

    @staticmethod
    def api_error() -> dict[str, Any]:
        """Responses simulating API errors/unavailable.

        Use None to indicate errors (vs [] for empty but successful).
        """
        return {
            "health": False,
            "stats": None,
            "global_stats": None,
            "sessions": None,  # None = error, [] = empty
            "delegations": None,
        }

    @staticmethod
    def partial_data() -> dict[str, Any]:
        """Responses with missing/null fields (edge case testing).

        Tests dashboard resilience when API returns incomplete data.
        """
        return {
            "health": True,
            "stats": {"sessions": 5},  # Missing traces, messages
            "global_stats": None,  # Missing entirely
            "sessions": [
                {
                    "id": "sess-partial-001",
                    "title": None,  # Missing title
                    "created_at": FIXED_TEST_DATE.isoformat(),
                    "tokens_in": None,  # Missing tokens
                    "tokens_out": 0,
                    "directory": None,
                }
            ],
            "delegations": [],
        }

    @staticmethod
    def extreme_data() -> dict[str, Any]:
        """Responses with extreme values (stress test).

        Tests dashboard handling of very large numbers and long strings.
        """
        base_date = FIXED_TEST_DATE

        # Create session with extreme values
        session = create_session_data(
            "sess-extreme",
            "A" * 500,  # Very long title (500 chars)
            base_date,
            tokens_in=999_999_999,  # Very large number
            tokens_out=999_999_999,
        )

        return {
            "health": True,
            "stats": {"sessions": 999_999, "traces": 999_999, "messages": 999_999_999},
            "global_stats": create_global_stats(
                999_999,  # sessions
                999_999,  # traces
                999_999_999,  # messages
                999_999_999_999,  # tokens
                100,  # unique agents
            ),
            "sessions": [session],
            "delegations": [],
        }

    @staticmethod
    def malformed_types() -> dict[str, Any]:
        """Responses with incorrect types for resilience testing.

        Tests dashboard handling of type mismatches from malformed API responses.
        """
        return {
            "health": True,
            "sessions": [
                {
                    "id": 12345,  # int instead of string
                    "title": None,  # null
                    "created_at": "not-a-date",  # invalid format
                    "tokens_in": "not_a_number",  # string instead of int
                    "tokens_out": -100,  # negative
                }
            ],
            "global_stats": None,
        }

    @staticmethod
    def missing_required_fields() -> dict[str, Any]:
        """Responses with missing required fields.

        Tests dashboard resilience when required fields are absent.
        """
        return {
            "health": True,
            "sessions": [
                {"id": "sess-001"}  # Missing title, tokens, etc.
            ],
        }

    @staticmethod
    def api_becomes_unavailable() -> dict[str, Any]:
        """Simulates API that was working then fails.

        Tests dashboard handling when API becomes unavailable mid-session.
        Use this after initial successful responses to simulate connection loss.
        """
        return {
            "health": False,
            "stats": None,
            "global_stats": None,
            "sessions": None,  # None = error, [] = empty
            "error": "Connection refused",
        }

    @staticmethod
    def basic() -> dict[str, Any]:
        """Basic responses with minimal data for simple tests."""
        base_date = FIXED_TEST_DATE
        session = create_session_data("sess-001", "Test Session", base_date)

        # Minimal session hierarchy for tracing tree (matches realistic_tracing structure)
        session_hierarchy = [
            {
                "session_id": "sess-001",
                "node_type": "session",
                "title": "Test Session",
                "directory": "/home/dev/my-project",
                "created_at": base_date.isoformat(),
                "status": "completed",
                "duration_ms": 10000,
                "tokens_in": 100,
                "tokens_out": 200,
                "children": [],
            }
        ]

        return {
            "health": True,
            "stats": {"sessions": 1, "traces": 1, "messages": 10},
            "global_stats": create_global_stats(1, 1, 10, 1000, 1),
            "sessions": [session],
            "delegations": [],
            "session_hierarchy": session_hierarchy,
            "session_messages": {
                "sess-001": [
                    {
                        "type": "text",
                        "role": "user",
                        "content": "Hello, test prompt",
                        "timestamp": base_date.isoformat(),
                        "tokens_in": 10,
                    },
                    {
                        "type": "text",
                        "role": "assistant",
                        "content": "Test response",
                        "timestamp": (base_date + timedelta(seconds=1)).isoformat(),
                        "tokens_out": 20,
                    },
                ]
            },
            "session_operations": {"sess-001": []},
        }

    @staticmethod
    def complex() -> dict[str, Any]:
        """Complex responses with multiple sessions and agents."""
        base_date = FIXED_TEST_DATE

        sessions = [
            create_session_data(
                f"sess-{i:03d}", f"Session {i}", base_date - timedelta(hours=i)
            )
            for i in range(3)
        ]

        return {
            "health": True,
            "stats": {"sessions": 3, "traces": 4, "messages": 100},
            "global_stats": create_global_stats(3, 4, 100, 25000, 4),
            "sessions": sessions,
            "delegations": [
                {"parent_session_id": "sess-000", "child_session_id": "sess-001"},
                {"parent_session_id": "sess-000", "child_session_id": "sess-002"},
            ],
            "session_messages": {
                "sess-000": [
                    {
                        "type": "text",
                        "role": "user",
                        "content": "Complex task prompt",
                        "timestamp": base_date.isoformat(),
                        "tokens_in": 100,
                    },
                    {
                        "type": "text",
                        "role": "assistant",
                        "content": "Starting complex task...",
                        "timestamp": (base_date + timedelta(seconds=5)).isoformat(),
                        "tokens_out": 200,
                        "agent": "coordinator",
                    },
                ]
            },
            "session_operations": {
                "sess-001": [
                    {
                        "tool_name": "read",
                        "display_info": "src/main.py",
                        "status": "completed",
                        "timestamp": base_date.isoformat(),
                        "duration_ms": 50,
                    },
                    {
                        "tool_name": "edit",
                        "display_info": "src/main.py",
                        "status": "completed",
                        "timestamp": (base_date + timedelta(seconds=1)).isoformat(),
                        "duration_ms": 100,
                    },
                ]
            },
        }
