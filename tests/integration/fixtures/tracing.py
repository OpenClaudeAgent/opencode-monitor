"""
Tracing-specific mock responses.

Provides pre-built tracing data with session hierarchies for testing.
"""

from datetime import datetime, timedelta
from typing import Any

from .constants import FIXED_TEST_DATE


def _create_session_hierarchy(base_date: datetime) -> list[dict[str, Any]]:
    """Create hierarchical session structure for tracing tests.

    Structure matches real API response:
    - session (root)
      - user_turn (user → agent)
        - tool
        - agent (delegation: agent → subagent)
          - tool
      - user_turn (user → agent)
        - tool

    Note: API returns 'subagent_type' for agent name, not 'agent_type'.
    """
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
            "agent_type": "user",
            "parent_agent": None,
            "children": [
                {
                    # user_turn: user initiates conversation with executor
                    "session_id": "sess-child-001",
                    "node_type": "delegation",
                    "title": "Execute implementation",
                    "subagent_type": "executor",  # API uses subagent_type
                    "parent_agent": "user",
                    "created_at": (base_date - timedelta(minutes=5)).isoformat(),
                    "status": "completed",
                    "duration_ms": 45000,
                    "tokens_in": 2000,
                    "tokens_out": 3000,
                    "trace_count": 2,
                    "children": [
                        # Tool used by executor
                        {
                            "node_type": "tool",
                            "tool_name": "read",
                            "display_info": "src/main.py",
                            "status": "completed",
                            "duration_ms": 50,
                            "created_at": (
                                base_date - timedelta(minutes=4, seconds=50)
                            ).isoformat(),
                        },
                        # Delegation: executor → tester
                        {
                            "session_id": "sess-grandchild-001",
                            "node_type": "agent",  # API returns "agent" for delegations
                            "title": "Run tests",
                            "subagent_type": "tester",  # API uses subagent_type
                            "parent_agent": "executor",
                            "created_at": (
                                base_date - timedelta(minutes=4)
                            ).isoformat(),
                            "status": "completed",
                            "duration_ms": 30000,
                            "tokens_in": 1500,
                            "tokens_out": 2500,
                            "trace_count": 1,
                            "children": [
                                # Tool used by tester (3rd level)
                                {
                                    "node_type": "tool",
                                    "tool_name": "bash",
                                    "display_info": "pytest tests/",
                                    "status": "completed",
                                    "duration_ms": 5000,
                                    "created_at": (
                                        base_date - timedelta(minutes=3, seconds=30)
                                    ).isoformat(),
                                },
                            ],
                        },
                        # Another tool used by executor after delegation
                        {
                            "node_type": "tool",
                            "tool_name": "edit",
                            "display_info": "src/main.py",
                            "status": "completed",
                            "duration_ms": 100,
                            "created_at": (
                                base_date - timedelta(minutes=2)
                            ).isoformat(),
                        },
                    ],
                },
                {
                    # Another user_turn
                    "session_id": "sess-child-002",
                    "node_type": "delegation",
                    "title": "Run tests",
                    "agent_type": "tester",
                    "parent_agent": "executor",
                    "created_at": (base_date - timedelta(minutes=3)).isoformat(),
                    "status": "completed",
                    "duration_ms": 15000,
                    "tokens_in": 1000,
                    "tokens_out": 1500,
                    "trace_count": 1,
                    "children": [
                        {
                            "node_type": "tool",
                            "tool_name": "glob",
                            "display_info": "**/*.py",
                            "status": "completed",
                            "duration_ms": 200,
                            "created_at": (
                                base_date - timedelta(seconds=50)
                            ).isoformat(),
                        },
                    ],
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
            "id": "sess-grandchild-001",
            "title": "Run tests",
            "directory": "/home/dev/my-project",
            "created_at": (base_date - timedelta(minutes=4)).isoformat(),
            "tokens_in": 1500,
            "tokens_out": 2500,
        },
        {
            "id": "sess-child-002",
            "title": "Review changes",
            "directory": "/home/dev/my-project",
            "created_at": (base_date - timedelta(minutes=1)).isoformat(),
            "tokens_in": 1000,
            "tokens_out": 1500,
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
            "sess-grandchild-001": {
                "input": 1500,
                "output": 2500,
                "cache_read": 300,
                "cache_write": 150,
            },
            "sess-child-002": {
                "input": 1000,
                "output": 1500,
                "cache_read": 200,
                "cache_write": 100,
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
            "sess-grandchild-001": [
                {"tool_name": "bash", "count": 3, "duration_ms": 5000},
            ],
            "sess-child-002": [
                {"tool_name": "glob", "count": 2, "duration_ms": 200},
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
            "sess-grandchild-001": [
                {"path": "tests/test_auth.py", "reads": 3, "writes": 1},
            ],
            "sess-child-002": [
                {"path": "src/review.py", "reads": 5, "writes": 0},
            ],
        },
        "session_agents": {
            "sess-root-001": [
                {"agent": "executor", "messages": 50, "tokens": 5000},
                {"agent": "tester", "messages": 30, "tokens": 3000},
                {"agent": "quality", "messages": 20, "tokens": 1500},
            ],
            "sess-child-001": [
                {"agent": "executor", "messages": 25, "tokens": 2500},
            ],
            "sess-grandchild-001": [
                {"agent": "tester", "messages": 15, "tokens": 1500},
            ],
            "sess-child-002": [
                {"agent": "quality", "messages": 10, "tokens": 1000},
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
                    "timestamp": (base_date + timedelta(minutes=4)).isoformat(),
                    "event": "agent_spawn",
                    "agent": "quality",
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
                    "timestamp": (base_date - timedelta(minutes=2)).isoformat(),
                    "event": "session_end",
                },
            ],
            "sess-grandchild-001": [
                {
                    "timestamp": (base_date - timedelta(minutes=4)).isoformat(),
                    "event": "session_start",
                },
                {
                    "timestamp": (base_date - timedelta(minutes=3)).isoformat(),
                    "event": "session_end",
                },
            ],
            "sess-child-002": [
                {
                    "timestamp": (base_date - timedelta(minutes=1)).isoformat(),
                    "event": "session_start",
                },
                {
                    "timestamp": (base_date - timedelta(seconds=30)).isoformat(),
                    "event": "session_end",
                },
            ],
        },
    }


def realistic_tracing() -> dict[str, Any]:
    """Create realistic tracing data with session hierarchy.

    Uses FIXED_TEST_DATE for reproducible tests.
    Data structure matches EXPECTED_TRACING constants for assertions.

    Hierarchy structure tested:
    - session (node_type: "session")
      - user_turn (user → executor) with tools
        - agent (executor → tester) delegation with tools  <-- 3rd level
        - tool
      - user_turn (user → quality) with tools
    """
    base_date = FIXED_TEST_DATE

    hierarchy = _create_session_hierarchy(base_date)
    sessions = _create_sessions_list(base_date)
    details = _create_session_details(base_date)

    return {
        "sessions": sessions,
        "session_hierarchy": hierarchy,
        "total_traces": 4,
        "unique_agents": 4,  # user, executor, tester, quality
        "total_duration_ms": 215000,
        **details,
    }
