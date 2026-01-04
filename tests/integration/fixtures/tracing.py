"""
Tracing-specific mock responses.

Provides pre-built tracing data with session hierarchies for testing.
"""

from datetime import datetime, timedelta
from typing import Any

from .constants import FIXED_TEST_DATE


def _create_session_hierarchy(base_date: datetime) -> list[dict[str, Any]]:
    """Create hierarchical session structure for tracing tests."""
    return [
        {
            "session_id": "sess-root-001",
            "node_type": "session",
            "title": "Implement feature X",
            "directory": "/home/dev/my-project",
            "created_at": base_date.isoformat(),
            "status": "completed",
            "duration_ms": 125000,
            "tokens_in": 5000,
            "tokens_out": 8000,
            "trace_count": 5,
            "agent_type": None,
            "parent_agent": None,
            "children": [
                {
                    "session_id": "sess-child-001",
                    "node_type": "delegation",
                    "title": "Execute implementation",
                    "agent_type": "executor",
                    "parent_agent": "user",
                    "created_at": (base_date - timedelta(minutes=5)).isoformat(),
                    "status": "completed",
                    "duration_ms": 45000,
                    "tokens_in": 2000,
                    "tokens_out": 3000,
                    "trace_count": 2,
                    "children": [],
                },
                {
                    "session_id": "sess-child-002",
                    "node_type": "delegation",
                    "title": "Run tests",
                    "agent_type": "tester",
                    "parent_agent": "executor",
                    "created_at": (base_date - timedelta(minutes=3)).isoformat(),
                    "status": "completed",
                    "duration_ms": 30000,
                    "tokens_in": 1500,
                    "tokens_out": 2500,
                    "trace_count": 1,
                    "children": [],
                },
            ],
        },
    ]


def _create_sessions_list(base_date: datetime) -> list[dict[str, Any]]:
    """Create flat sessions list for tracing tests."""
    return [
        {
            "id": "sess-root-001",
            "title": "Implement feature X",
            "directory": "/home/dev/my-project",
            "created_at": base_date.isoformat(),
            "tokens_in": 5000,
            "tokens_out": 8000,
        },
        {
            "id": "sess-child-001",
            "title": "Execute implementation",
            "directory": "/home/dev/my-project",
            "created_at": (base_date - timedelta(minutes=5)).isoformat(),
            "tokens_in": 2000,
            "tokens_out": 3000,
        },
        {
            "id": "sess-child-002",
            "title": "Run tests",
            "directory": "/home/dev/my-project",
            "created_at": (base_date - timedelta(minutes=3)).isoformat(),
            "tokens_in": 1500,
            "tokens_out": 2500,
        },
    ]


def _create_session_details(base_date: datetime) -> dict[str, Any]:
    """Create detailed session data (tokens, tools, files, agents, timeline)."""
    return {
        "session_tokens": {
            "sess-root-001": {
                "input": 5000,
                "output": 8000,
                "cache_read": 1000,
                "cache_write": 500,
            },
            "sess-child-001": {
                "input": 2000,
                "output": 3000,
                "cache_read": 400,
                "cache_write": 200,
            },
            "sess-child-002": {
                "input": 1500,
                "output": 2500,
                "cache_read": 300,
                "cache_write": 150,
            },
        },
        "session_tools": {
            "sess-root-001": [
                {"tool_name": "read", "count": 15, "duration_ms": 500},
                {"tool_name": "edit", "count": 8, "duration_ms": 1200},
                {"tool_name": "bash", "count": 5, "duration_ms": 3000},
            ],
            "sess-child-001": [
                {"tool_name": "read", "count": 10, "duration_ms": 300},
                {"tool_name": "edit", "count": 5, "duration_ms": 800},
            ],
            "sess-child-002": [
                {"tool_name": "bash", "count": 3, "duration_ms": 2000},
            ],
        },
        "session_files": {
            "sess-root-001": [
                {"path": "src/main.py", "reads": 10, "writes": 3},
                {"path": "tests/test_main.py", "reads": 5, "writes": 2},
            ],
            "sess-child-001": [
                {"path": "src/auth/login.py", "reads": 8, "writes": 4},
            ],
            "sess-child-002": [
                {"path": "tests/test_auth.py", "reads": 3, "writes": 1},
            ],
        },
        "session_agents": {
            "sess-root-001": [
                {"agent": "executor", "messages": 50, "tokens": 5000},
                {"agent": "tester", "messages": 30, "tokens": 3000},
            ],
            "sess-child-001": [
                {"agent": "executor", "messages": 25, "tokens": 2500},
            ],
            "sess-child-002": [
                {"agent": "tester", "messages": 15, "tokens": 1500},
            ],
        },
        "session_timeline": {
            "sess-root-001": [
                {"timestamp": base_date.isoformat(), "event": "session_start"},
                {
                    "timestamp": (base_date + timedelta(seconds=10)).isoformat(),
                    "event": "agent_spawn",
                    "agent": "executor",
                },
                {
                    "timestamp": (base_date + timedelta(minutes=2)).isoformat(),
                    "event": "agent_spawn",
                    "agent": "tester",
                },
                {
                    "timestamp": (base_date + timedelta(minutes=5)).isoformat(),
                    "event": "session_end",
                },
            ],
            "sess-child-001": [
                {
                    "timestamp": (base_date - timedelta(minutes=5)).isoformat(),
                    "event": "session_start",
                },
                {
                    "timestamp": (base_date - timedelta(minutes=4)).isoformat(),
                    "event": "session_end",
                },
            ],
            "sess-child-002": [
                {
                    "timestamp": (base_date - timedelta(minutes=3)).isoformat(),
                    "event": "session_start",
                },
                {
                    "timestamp": (base_date - timedelta(minutes=2)).isoformat(),
                    "event": "session_end",
                },
            ],
        },
    }


def realistic_tracing() -> dict[str, Any]:
    """Create realistic tracing data with session hierarchy.

    Uses FIXED_TEST_DATE for reproducible tests.
    Data structure matches EXPECTED_TRACING constants for assertions.
    """
    base_date = FIXED_TEST_DATE

    hierarchy = _create_session_hierarchy(base_date)
    sessions = _create_sessions_list(base_date)
    details = _create_session_details(base_date)

    return {
        "sessions": sessions,
        "session_hierarchy": hierarchy,
        "total_traces": 3,
        "unique_agents": 3,
        "total_duration_ms": 200000,
        **details,
    }
