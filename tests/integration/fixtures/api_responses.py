"""
Mock API responses for integration tests.

Provides factory functions and pre-built responses that mimic
the real Analytics API responses for dashboard testing.
"""

from datetime import datetime, timedelta
from typing import Any


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
        created_at = datetime.now()

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
        started_at = datetime.now()

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


class MockAPIResponses:
    """Pre-built API responses for common test scenarios."""

    @staticmethod
    def empty() -> dict[str, Any]:
        """Empty responses for testing initial state."""
        return {
            "health": True,
            "stats": {"sessions": 0, "traces": 0, "messages": 0},
            "global_stats": create_global_stats(0, 0, 0, 0, 0),
            "sessions": [],
            "traces": [],
            "delegations": [],
        }

    @staticmethod
    def basic() -> dict[str, Any]:
        """Basic responses with minimal data for simple tests."""
        now = datetime.now()
        session = create_session_data("sess-001", "Test Session", now)
        trace = create_trace_data(
            "trace-001", "sess-001", "root_sess-001", "user", started_at=now
        )

        return {
            "health": True,
            "stats": {"sessions": 1, "traces": 1, "messages": 10},
            "global_stats": create_global_stats(1, 1, 10, 1000, 1),
            "sessions": [session],
            "traces": [trace],
            "delegations": [],
            "session_messages": {
                "sess-001": [
                    {
                        "type": "text",
                        "role": "user",
                        "content": "Hello, test prompt",
                        "timestamp": now.isoformat(),
                        "tokens_in": 10,
                    },
                    {
                        "type": "text",
                        "role": "assistant",
                        "content": "Test response",
                        "timestamp": (now + timedelta(seconds=1)).isoformat(),
                        "tokens_out": 20,
                    },
                ]
            },
            "session_operations": {"sess-001": []},
        }

    @staticmethod
    def complex() -> dict[str, Any]:
        """Complex responses with multiple sessions and agents."""
        now = datetime.now()

        sessions = [
            create_session_data(
                f"sess-{i:03d}", f"Session {i}", now - timedelta(hours=i)
            )
            for i in range(3)
        ]

        traces = []
        # Root session with user trace
        traces.append(
            create_trace_data(
                "trace-001", "sess-000", "root_sess-000", "user", started_at=now
            )
        )
        # Sub-agents
        for i, agent_type in enumerate(["executor", "tester", "quality"]):
            traces.append(
                create_trace_data(
                    f"trace-{i + 2:03d}",
                    f"sess-{i + 1:03d}",
                    "root_sess-000",
                    agent_type,
                    started_at=now - timedelta(minutes=i * 5),
                )
            )

        return {
            "health": True,
            "stats": {"sessions": 3, "traces": 4, "messages": 100},
            "global_stats": create_global_stats(3, 4, 100, 25000, 4),
            "sessions": sessions,
            "traces": traces,
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
                        "timestamp": now.isoformat(),
                        "tokens_in": 100,
                    },
                    {
                        "type": "text",
                        "role": "assistant",
                        "content": "Starting complex task...",
                        "timestamp": (now + timedelta(seconds=5)).isoformat(),
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
                        "timestamp": now.isoformat(),
                        "duration_ms": 50,
                    },
                    {
                        "tool_name": "edit",
                        "display_info": "src/main.py",
                        "status": "completed",
                        "timestamp": (now + timedelta(seconds=1)).isoformat(),
                        "duration_ms": 100,
                    },
                ]
            },
        }
