"""
Monitoring-specific mock responses.

Provides pre-built monitoring data for various test scenarios.
"""

from typing import Any


def empty_monitoring() -> dict[str, Any]:
    """Empty monitoring data for testing empty states.

    Use this for tests that need to verify empty state behavior
    in the monitoring section (agents_empty, tools_empty, waiting_empty).
    """
    return {
        "instances": 0,
        "agents": 0,
        "busy": 0,
        "waiting": 0,
        "idle": 0,
        "todos": 0,
        "agents_data": [],
        "tools_data": [],
        "waiting_data": [],
    }


def realistic_monitoring() -> dict[str, Any]:
    """Create realistic monitoring data with agents, tools, and waiting items."""
    return {
        "instances": 2,
        "agents": 3,
        "busy": 2,
        "waiting": 1,
        "idle": 1,
        "todos": 7,
        "agents_data": [
            {
                "agent_id": "agent-abc123",
                "title": "Implement User Auth",
                "dir": "/home/dev/auth-service",
                "status": "busy",
                "tools": [{"name": "edit"}, {"name": "bash"}],
                "todos_total": 4,
            },
            {
                "agent_id": "agent-def456",
                "title": "Fix Database Migration",
                "dir": "/home/dev/db-service",
                "status": "busy",
                "tools": [{"name": "read"}],
                "todos_total": 3,
            },
            {
                "agent_id": "agent-ghi789",
                "title": "Code Review",
                "dir": "/home/dev/frontend",
                "status": "idle",
                "tools": [],
                "todos_total": 0,
            },
        ],
        "tools_data": [
            {
                "name": "edit",
                "agent": "Implement User Auth",
                "arg": "src/auth/login.py",
                "elapsed_ms": 1250,
            },
            {
                "name": "bash",
                "agent": "Implement User Auth",
                "arg": "pytest tests/",
                "elapsed_ms": 5400,
            },
            {
                "name": "read",
                "agent": "Fix Database Migration",
                "arg": "migrations/v2.sql",
                "elapsed_ms": 150,
            },
        ],
        "waiting_data": [
            {
                "agent_id": "agent-wait001",
                "title": "Deploy to Production",
                "question": "Are you sure you want to deploy version 2.5.0 to production? This will affect 10,000 users.",
                "options": "Yes, deploy | No, cancel | Schedule for later",
                "context": "infra-team @ main",
            },
        ],
    }


def realistic_monitoring_all_idle() -> dict[str, Any]:
    """All agents idle, no tools running.

    Tests monitoring section displays correctly when nothing is active.
    """
    return {
        "instances": 2,
        "agents": 4,
        "busy": 0,
        "waiting": 0,
        "idle": 4,
        "todos": 0,
        "agents_data": [
            {
                "agent_id": f"agent-idle-{i:03d}",
                "title": f"Idle Agent {i}",
                "dir": f"/home/dev/project-{i}",
                "status": "idle",
                "tools": [],
                "todos_total": 0,
            }
            for i in range(4)
        ],
        "tools_data": [],
        "waiting_data": [],
    }


def realistic_monitoring_all_waiting() -> dict[str, Any]:
    """Multiple agents waiting for user response.

    Tests monitoring section handles multiple waiting agents.
    """
    return {
        "instances": 3,
        "agents": 3,
        "busy": 0,
        "waiting": 3,
        "idle": 0,
        "todos": 0,
        "agents_data": [
            {
                "agent_id": f"agent-wait-{i:03d}",
                "title": f"Waiting Agent {i}",
                "dir": f"/home/dev/project-{i}",
                "status": "waiting",
                "tools": [],
                "todos_total": 0,
            }
            for i in range(3)
        ],
        "tools_data": [],
        "waiting_data": [
            {
                "agent_id": f"agent-wait-{i:03d}",
                "title": f"Waiting Agent {i}",
                "question": f"Question {i}: Need user confirmation for action {i}",
                "options": "Confirm | Reject | Skip",
                "context": f"project-{i} @ feature-branch",
            }
            for i in range(3)
        ],
    }


def realistic_monitoring_error() -> dict[str, Any]:
    """Monitoring data with some agents in error state.

    Tests monitoring section handles error states gracefully.
    """
    return {
        "instances": 2,
        "agents": 4,
        "busy": 1,
        "waiting": 0,
        "idle": 1,
        "todos": 2,
        "agents_data": [
            {
                "agent_id": "agent-busy-001",
                "title": "Normal Working Agent",
                "dir": "/home/dev/project",
                "status": "busy",
                "tools": [{"name": "read"}],
                "todos_total": 2,
            },
            {
                "agent_id": "agent-error-001",
                "title": "Error: Connection Failed",
                "dir": "/home/dev/broken",
                "status": "error",
                "tools": [],
                "todos_total": 0,
            },
            {
                "agent_id": "agent-error-002",
                "title": None,  # Missing title
                "dir": None,  # Missing directory
                "status": "unknown",
                "tools": None,  # Missing tools
                "todos_total": None,
            },
            {
                "agent_id": "agent-idle-001",
                "title": "Idle Agent",
                "dir": "/home/dev/idle",
                "status": "idle",
                "tools": [],
                "todos_total": 0,
            },
        ],
        "tools_data": [
            {
                "name": "read",
                "agent": "Normal Working Agent",
                "arg": "src/file.py",
                "elapsed_ms": 500,
            },
        ],
        "waiting_data": [],
    }
