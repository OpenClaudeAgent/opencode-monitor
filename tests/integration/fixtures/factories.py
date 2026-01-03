"""
Factory functions for creating test data.

Provides functions to create individual data objects with
sensible defaults that can be overridden.
"""

from datetime import datetime
from typing import Any

from .constants import FIXED_TEST_DATE


def create_session_data(
    session_id: str = "sess-001",
    title: str = "Test Session",
    created_at: datetime | None = None,
    tokens_in: int = 1000,
    tokens_out: int = 500,
) -> dict[str, Any]:
    """Create a mock session data dict.

    Args:
        session_id: Unique session identifier
        title: Session title/description
        created_at: Session creation timestamp
        tokens_in: Input tokens count
        tokens_out: Output tokens count

    Returns:
        Session data dict matching API response format
    """
    if created_at is None:
        created_at = FIXED_TEST_DATE

    return {
        "id": session_id,
        "title": title,
        "created_at": created_at.isoformat(),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "directory": "/home/user/project",
    }


def create_trace_data(
    trace_id: str = "trace-001",
    session_id: str = "sess-001",
    parent_trace_id: str = "root_sess-001",
    subagent_type: str = "executor",
    status: str = "completed",
    duration_ms: int = 5000,
    tokens_in: int = 500,
    tokens_out: int = 250,
    started_at: datetime | None = None,
) -> dict[str, Any]:
    """Create a mock trace data dict.

    Args:
        trace_id: Unique trace identifier
        session_id: Parent session ID
        parent_trace_id: Parent trace (root_xxx for root sessions)
        subagent_type: Type of agent (user, executor, tester, etc.)
        status: Trace status (running, completed, error)
        duration_ms: Trace duration in milliseconds
        tokens_in: Input tokens
        tokens_out: Output tokens
        started_at: Trace start timestamp

    Returns:
        Trace data dict matching API response format
    """
    if started_at is None:
        started_at = FIXED_TEST_DATE

    return {
        "trace_id": trace_id,
        "session_id": session_id,
        "parent_trace_id": parent_trace_id,
        "subagent_type": subagent_type,
        "status": status,
        "duration_ms": duration_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "started_at": started_at.isoformat(),
        "parent_agent": "user" if subagent_type == "user" else "coordinator",
    }


def create_global_stats(
    total_sessions: int = 10,
    total_traces: int = 50,
    total_messages: int = 200,
    total_tokens: int = 50000,
    unique_agents: int = 5,
) -> dict[str, Any]:
    """Create mock global statistics.

    Args:
        total_sessions: Number of sessions
        total_traces: Number of traces
        total_messages: Number of messages
        total_tokens: Total tokens used
        unique_agents: Number of unique agents

    Returns:
        Global stats dict matching API response format
    """
    input_tokens = int(total_tokens * 0.6)
    output_tokens = int(total_tokens * 0.3)
    cache_tokens = int(total_tokens * 0.1)

    return {
        "summary": {
            "total_sessions": total_sessions,
            "total_traces": total_traces,
            "total_messages": total_messages,
            "total_tokens": total_tokens,
            "unique_agents": unique_agents,
            "total_duration_ms": total_traces * 5000,
        },
        "details": {
            "tokens": {
                "input": input_tokens,
                "output": output_tokens,
                "cache_read": cache_tokens,
            }
        },
    }


def create_monitoring_data(
    num_agents: int = 2,
    num_busy: int = 1,
    num_waiting: int = 0,
) -> dict[str, Any]:
    """Create mock monitoring data.

    Args:
        num_agents: Total number of agents
        num_busy: Number of busy agents
        num_waiting: Number of agents waiting for user

    Returns:
        Monitoring data dict for UI update
    """
    agents_data = []
    for i in range(num_agents):
        is_busy = i < num_busy
        agents_data.append(
            {
                "agent_id": f"agent-{i:03d}",
                "title": f"Agent {i}",
                "dir": f"project-{i}",
                "status": "busy" if is_busy else "idle",
                "tools": [],
                "todos_total": 3 if is_busy else 0,
            }
        )

    waiting_data = []
    for i in range(num_waiting):
        waiting_data.append(
            {
                "agent_id": f"agent-waiting-{i:03d}",
                "title": f"Waiting Agent {i}",
                "question": "Please confirm action",
                "options": "Yes | No",
                "context": "test @ main",
            }
        )

    return {
        "instances": max(1, num_agents // 2),
        "agents": num_agents,
        "busy": num_busy,
        "waiting": num_waiting,
        "idle": max(0, (num_agents // 2) - num_busy),
        "todos": sum(a.get("todos_total", 0) for a in agents_data),
        "agents_data": agents_data,
        "tools_data": [],
        "waiting_data": waiting_data,
    }


def create_security_data(
    total_commands: int = 10,
    critical_count: int = 1,
    high_count: int = 2,
) -> dict[str, Any]:
    """Create mock security data.

    Args:
        total_commands: Total commands scanned
        critical_count: Number of critical commands
        high_count: Number of high risk commands

    Returns:
        Security data dict for UI update
    """
    commands = []
    for i in range(total_commands):
        if i < critical_count:
            risk = "critical"
            score = 90
        elif i < critical_count + high_count:
            risk = "high"
            score = 70
        else:
            risk = "low"
            score = 20

        commands.append(
            {
                "command": f"command-{i}",
                "risk": risk,
                "score": score,
                "reason": f"Test reason {i}",
            }
        )

    return {
        "stats": {
            "total_scanned": total_commands,
            "total_commands": total_commands,
            "critical": critical_count,
            "high": high_count,
            "medium": 0,
            "low": total_commands - critical_count - high_count,
        },
        "commands": commands,
        "files": [],
        "critical_items": [c for c in commands if c["risk"] in ("critical", "high")],
    }
