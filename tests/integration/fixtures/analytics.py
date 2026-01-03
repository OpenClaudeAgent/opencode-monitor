"""
Analytics-specific mock responses.

Provides pre-built analytics data for various test scenarios.
"""

from typing import Any


def realistic_analytics() -> dict[str, Any]:
    """Create realistic analytics data with agents, tools, and skills."""
    return {
        "sessions": 42,
        "messages": 1337,
        "tokens": "2.5M",
        "cache_hit": "73%",
        "agents": [
            {"agent": "coordinator", "messages": 500, "tokens": 1200000},
            {"agent": "executor", "messages": 400, "tokens": 800000},
            {"agent": "tester", "messages": 250, "tokens": 400000},
            {"agent": "quality", "messages": 187, "tokens": 100000},
        ],
        "tools": [
            {"tool_name": "read", "invocations": 450, "failures": 5},
            {"tool_name": "edit", "invocations": 320, "failures": 12},
            {"tool_name": "bash", "invocations": 180, "failures": 8},
            {"tool_name": "grep", "invocations": 95, "failures": 0},
        ],
        "skills": [
            {"skill_name": "agentic-flow", "load_count": 15},
            {"skill_name": "swarm-orchestration", "load_count": 8},
            {"skill_name": "reporting-executor", "load_count": 12},
        ],
    }
