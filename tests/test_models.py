"""
Tests for opencode_monitor.core.models

Coverage target: 100% for all model classes
Uses parametrized tests for enum values and edge cases.
"""

import pytest
from opencode_monitor.core.models import (
    SessionStatus,
    TodoStatus,
    Tool,
    AgentTodos,
    Agent,
    Instance,
    Todos,
    State,
    UsagePeriod,
    Usage,
)


# =============================================================================
# Enum Tests (Parametrized)
# =============================================================================


@pytest.mark.parametrize(
    "status,expected",
    [
        (SessionStatus.IDLE, "idle"),
        (SessionStatus.BUSY, "busy"),
    ],
)
def test_session_status_values(status, expected):
    """SessionStatus enum values are correct."""
    assert status.value == expected


@pytest.mark.parametrize(
    "status,expected",
    [
        (TodoStatus.PENDING, "pending"),
        (TodoStatus.IN_PROGRESS, "in_progress"),
        (TodoStatus.COMPLETED, "completed"),
    ],
)
def test_todo_status_values(status, expected):
    """TodoStatus enum values are correct."""
    assert status.value == expected


# =============================================================================
# Tool Tests
# =============================================================================


class TestTool:
    """Tests for Tool dataclass"""

    def test_default_arg(self):
        """Tool default arg is empty string."""
        tool = Tool(name="bash")
        assert tool.name == "bash"
        assert tool.arg == ""

    def test_default_elapsed_ms(self):
        """Tool default elapsed_ms is 0."""
        tool = Tool(name="bash")
        assert tool.elapsed_ms == 0

    def test_with_arg(self):
        """Tool with custom arg."""
        tool = Tool(name="read", arg="/path/to/file.py")
        assert tool.name == "read"
        assert tool.arg == "/path/to/file.py"

    def test_with_elapsed_ms(self):
        """Tool with custom elapsed_ms."""
        tool = Tool(name="bash", arg="ls", elapsed_ms=5000)
        assert tool.elapsed_ms == 5000

    @pytest.mark.parametrize(
        "name,arg,elapsed_ms,expected",
        [
            (
                "write",
                "content.txt",
                0,
                {
                    "name": "write",
                    "arg": "content.txt",
                    "elapsed_ms": 0,
                    "may_need_permission": False,
                },
            ),
            (
                "bash",
                "",
                0,
                {
                    "name": "bash",
                    "arg": "",
                    "elapsed_ms": 0,
                    "may_need_permission": False,
                },
            ),
            (
                "read",
                "/file.py",
                10000,
                {
                    "name": "read",
                    "arg": "/file.py",
                    "elapsed_ms": 10000,
                    "may_need_permission": True,
                },
            ),
        ],
    )
    def test_to_dict(self, name, arg, elapsed_ms, expected):
        """Tool to_dict returns correct structure with elapsed_ms and may_need_permission."""
        tool = Tool(name=name, arg=arg, elapsed_ms=elapsed_ms)
        assert tool.to_dict() == expected

    def test_excluded_tools_contains_task(self):
        """EXCLUDED_TOOLS contains 'task' for sub-agents."""
        assert "task" in Tool.EXCLUDED_TOOLS

    @pytest.mark.parametrize(
        "tool_name,elapsed_ms,expected",
        [
            # Below threshold (5s = 5000ms) - should be False
            ("bash", 0, False),
            ("bash", 4999, False),
            ("read", 5000, False),  # Exactly at threshold, not above
            # Above threshold - should be True
            ("bash", 5001, True),
            ("read", 10000, True),
            ("write", 6000, True),
            # Excluded tools - always False regardless of elapsed_ms
            ("task", 0, False),
            ("task", 5001, False),
            ("task", 100000, False),
            ("Task", 10000, False),  # Case-insensitive check
        ],
    )
    def test_may_need_permission(self, tool_name, elapsed_ms, expected):
        """may_need_permission property based on elapsed_ms and exclusions."""
        tool = Tool(name=tool_name, elapsed_ms=elapsed_ms)
        assert tool.may_need_permission is expected


# =============================================================================
# AgentTodos Tests
# =============================================================================


class TestAgentTodos:
    """Tests for AgentTodos dataclass"""

    def test_defaults(self):
        """AgentTodos default values."""
        todos = AgentTodos()
        assert todos.pending == 0
        assert todos.in_progress == 0
        assert todos.current_label == ""
        assert todos.next_label == ""

    def test_with_values(self):
        """AgentTodos with custom values."""
        todos = AgentTodos(
            pending=3,
            in_progress=1,
            current_label="Implementing feature",
            next_label="Write tests",
        )
        assert todos.pending == 3
        assert todos.in_progress == 1
        assert todos.current_label == "Implementing feature"
        assert todos.next_label == "Write tests"

    def test_to_dict(self):
        """AgentTodos to_dict returns correct structure."""
        todos = AgentTodos(
            pending=5,
            in_progress=2,
            current_label="Current task",
            next_label="Next task",
        )
        assert todos.to_dict() == {
            "pending": 5,
            "in_progress": 2,
            "current_label": "Current task",
            "next_label": "Next task",
        }

    @pytest.mark.parametrize(
        "pending,in_progress,expected_total",
        [
            (3, 2, 5),
            (0, 0, 0),
            (10, 0, 10),
            (0, 5, 5),
        ],
    )
    def test_total_property(self, pending, in_progress, expected_total):
        """Total property sums pending and in_progress."""
        todos = AgentTodos(pending=pending, in_progress=in_progress)
        assert todos.total == expected_total


# =============================================================================
# Agent Tests
# =============================================================================


class TestAgent:
    """Tests for Agent dataclass"""

    def test_minimal_agent(self):
        """Agent with required fields only."""
        agent = Agent(
            id="agent-123",
            title="Test Session",
            dir="project",
            full_dir="/home/user/project",
            status=SessionStatus.IDLE,
        )
        assert agent.id == "agent-123"
        assert agent.title == "Test Session"
        assert agent.dir == "project"
        assert agent.full_dir == "/home/user/project"
        assert agent.status == SessionStatus.IDLE
        assert agent.tools == []
        assert isinstance(agent.todos, AgentTodos)
        assert agent.parent_id is None

    @pytest.mark.parametrize(
        "parent_id,expected",
        [
            (None, False),
            ("parent-123", True),
        ],
    )
    def test_is_subagent(self, parent_id, expected):
        """is_subagent property based on parent_id."""
        agent = Agent(
            id="agent-123",
            title="Test",
            dir="project",
            full_dir="/path",
            status=SessionStatus.IDLE,
            parent_id=parent_id,
        )
        assert agent.is_subagent is expected

    def test_to_dict_without_parent(self):
        """to_dict without parent_id."""
        tool = Tool(name="bash", arg="ls -la")
        todos = AgentTodos(pending=2, in_progress=1, current_label="Task")
        agent = Agent(
            id="agent-123",
            title="Test",
            dir="proj",
            full_dir="/full/path/proj",
            status=SessionStatus.BUSY,
            tools=[tool],
            todos=todos,
        )
        result = agent.to_dict()

        assert result["id"] == "agent-123"
        assert result["title"] == "Test"
        assert result["dir"] == "proj"
        assert result["full_dir"] == "/full/path/proj"
        assert result["status"] == "busy"
        assert result["tools"] == [
            {
                "name": "bash",
                "arg": "ls -la",
                "elapsed_ms": 0,
                "may_need_permission": False,
            }
        ]
        assert result["todos"] == {
            "pending": 2,
            "in_progress": 1,
            "current_label": "Task",
            "next_label": "",
        }
        assert "parent_id" not in result

    def test_to_dict_with_parent(self):
        """to_dict includes parent_id when set."""
        agent = Agent(
            id="sub-123",
            title="Sub Agent",
            dir="proj",
            full_dir="/path",
            status=SessionStatus.IDLE,
            parent_id="parent-456",
        )
        result = agent.to_dict()
        assert result["parent_id"] == "parent-456"

    def test_to_dict_with_multiple_tools(self):
        """to_dict with multiple tools."""
        tools = [
            Tool(name="read", arg="file1.py"),
            Tool(name="write", arg="file2.py"),
            Tool(name="bash", arg="pytest"),
        ]
        agent = Agent(
            id="agent-123",
            title="Test",
            dir="proj",
            full_dir="/path",
            status=SessionStatus.BUSY,
            tools=tools,
        )
        result = agent.to_dict()

        assert len(result["tools"]) == 3
        assert result["tools"][0] == {
            "name": "read",
            "arg": "file1.py",
            "elapsed_ms": 0,
            "may_need_permission": False,
        }
        assert result["tools"][1] == {
            "name": "write",
            "arg": "file2.py",
            "elapsed_ms": 0,
            "may_need_permission": False,
        }
        assert result["tools"][2] == {
            "name": "bash",
            "arg": "pytest",
            "elapsed_ms": 0,
            "may_need_permission": False,
        }


# =============================================================================
# Instance Tests
# =============================================================================


class TestInstance:
    """Tests for Instance dataclass"""

    def test_defaults(self):
        """Instance default values."""
        instance = Instance(port=3000)
        assert instance.port == 3000
        assert instance.tty == ""
        assert instance.agents == []

    def test_with_tty(self):
        """Instance with tty."""
        instance = Instance(port=3001, tty="/dev/ttys001")
        assert instance.tty == "/dev/ttys001"

    @pytest.mark.parametrize(
        "agents_count,expected",
        [
            (0, 0),
            (1, 1),
            (3, 3),
        ],
    )
    def test_agent_count(self, agents_count, expected):
        """agent_count property."""
        agents = [
            Agent(
                id=str(i), title="A", dir="d", full_dir="/d", status=SessionStatus.IDLE
            )
            for i in range(agents_count)
        ]
        instance = Instance(port=3000, agents=agents)
        assert instance.agent_count == expected

    @pytest.mark.parametrize(
        "busy,idle,expected",
        [
            (0, 2, 0),  # None busy
            (2, 1, 2),  # Some busy
            (3, 0, 3),  # All busy
        ],
    )
    def test_busy_count(self, busy, idle, expected):
        """busy_count property."""
        agents = [
            Agent(
                id=f"busy-{i}",
                title="A",
                dir="d",
                full_dir="/d",
                status=SessionStatus.BUSY,
            )
            for i in range(busy)
        ] + [
            Agent(
                id=f"idle-{i}",
                title="B",
                dir="d",
                full_dir="/d",
                status=SessionStatus.IDLE,
            )
            for i in range(idle)
        ]
        instance = Instance(port=3000, agents=agents)
        assert instance.busy_count == expected

    @pytest.mark.parametrize(
        "busy,idle,expected",
        [
            (0, 2, 2),  # All idle
            (2, 1, 1),  # Some idle
            (3, 0, 0),  # None idle
        ],
    )
    def test_idle_count(self, busy, idle, expected):
        """idle_count property."""
        agents = [
            Agent(
                id=f"busy-{i}",
                title="A",
                dir="d",
                full_dir="/d",
                status=SessionStatus.BUSY,
            )
            for i in range(busy)
        ] + [
            Agent(
                id=f"idle-{i}",
                title="B",
                dir="d",
                full_dir="/d",
                status=SessionStatus.IDLE,
            )
            for i in range(idle)
        ]
        instance = Instance(port=3000, agents=agents)
        assert instance.idle_count == expected

    def test_to_dict(self):
        """to_dict method."""
        agent = Agent(
            id="agent-1",
            title="Test Agent",
            dir="project",
            full_dir="/home/project",
            status=SessionStatus.BUSY,
        )
        instance = Instance(port=3000, tty="/dev/ttys001", agents=[agent])
        result = instance.to_dict()

        assert result["port"] == 3000
        assert result["tty"] == "/dev/ttys001"
        assert result["agent_count"] == 1
        assert result["busy_count"] == 1
        assert result["idle_count"] == 0
        assert len(result["agents"]) == 1
        assert result["agents"][0]["id"] == "agent-1"

    def test_to_dict_empty_agents(self):
        """to_dict with no agents."""
        instance = Instance(port=3000)
        result = instance.to_dict()

        assert result["port"] == 3000
        assert result["agents"] == []
        assert result["agent_count"] == 0
        assert result["busy_count"] == 0
        assert result["idle_count"] == 0

    def test_to_dict_with_idle_agents(self):
        """to_dict includes idle_count."""
        agents = [
            Agent(
                id="busy-1",
                title="Busy",
                dir="d",
                full_dir="/d",
                status=SessionStatus.BUSY,
            ),
            Agent(
                id="idle-1",
                title="Idle1",
                dir="d",
                full_dir="/d",
                status=SessionStatus.IDLE,
            ),
            Agent(
                id="idle-2",
                title="Idle2",
                dir="d",
                full_dir="/d",
                status=SessionStatus.IDLE,
            ),
        ]
        instance = Instance(port=3000, agents=agents)
        result = instance.to_dict()

        assert result["busy_count"] == 1
        assert result["idle_count"] == 2


# =============================================================================
# Todos Tests
# =============================================================================


class TestTodos:
    """Tests for Todos dataclass"""

    def test_defaults(self):
        """Todos default values."""
        todos = Todos()
        assert todos.pending == 0
        assert todos.in_progress == 0

    def test_with_values(self):
        """Todos with custom values."""
        todos = Todos(pending=10, in_progress=3)
        assert todos.pending == 10
        assert todos.in_progress == 3

    def test_to_dict(self):
        """to_dict method."""
        todos = Todos(pending=5, in_progress=2)
        assert todos.to_dict() == {"pending": 5, "in_progress": 2}


# =============================================================================
# State Tests
# =============================================================================


class TestState:
    """Tests for State dataclass"""

    def test_defaults(self):
        """State default values."""
        state = State()
        assert state.instances == []
        assert isinstance(state.todos, Todos)
        assert isinstance(state.updated, int)
        assert state.connected is False

    def test_connected_true(self):
        """State with connected=True."""
        state = State(connected=True)
        assert state.connected is True

    @pytest.mark.parametrize(
        "instance_count,expected",
        [
            (0, 0),
            (3, 3),
        ],
    )
    def test_instance_count(self, instance_count, expected):
        """instance_count property."""
        instances = [Instance(port=3000 + i) for i in range(instance_count)]
        state = State(instances=instances)
        assert state.instance_count == expected

    def test_agent_count_sums_all_instances(self):
        """agent_count sums agents across all instances."""
        agents1 = [
            Agent(id="1", title="A", dir="d", full_dir="/d", status=SessionStatus.IDLE),
            Agent(id="2", title="B", dir="d", full_dir="/d", status=SessionStatus.BUSY),
        ]
        agents2 = [
            Agent(id="3", title="C", dir="d", full_dir="/d", status=SessionStatus.IDLE),
        ]
        instances = [
            Instance(port=3000, agents=agents1),
            Instance(port=3001, agents=agents2),
        ]
        state = State(instances=instances)
        assert state.agent_count == 3

    def test_busy_count_sums_all_instances(self):
        """busy_count sums busy agents across all instances."""
        agents1 = [
            Agent(id="1", title="A", dir="d", full_dir="/d", status=SessionStatus.BUSY),
            Agent(id="2", title="B", dir="d", full_dir="/d", status=SessionStatus.BUSY),
        ]
        agents2 = [
            Agent(id="3", title="C", dir="d", full_dir="/d", status=SessionStatus.BUSY),
            Agent(id="4", title="D", dir="d", full_dir="/d", status=SessionStatus.IDLE),
        ]
        instances = [
            Instance(port=3000, agents=agents1),
            Instance(port=3001, agents=agents2),
        ]
        state = State(instances=instances)
        assert state.busy_count == 3

    def test_idle_count_sums_all_instances(self):
        """idle_count sums idle agents across all instances."""
        agents1 = [
            Agent(id="1", title="A", dir="d", full_dir="/d", status=SessionStatus.BUSY),
            Agent(id="2", title="B", dir="d", full_dir="/d", status=SessionStatus.IDLE),
        ]
        agents2 = [
            Agent(id="3", title="C", dir="d", full_dir="/d", status=SessionStatus.IDLE),
            Agent(id="4", title="D", dir="d", full_dir="/d", status=SessionStatus.IDLE),
        ]
        instances = [
            Instance(port=3000, agents=agents1),
            Instance(port=3001, agents=agents2),
        ]
        state = State(instances=instances)
        assert state.idle_count == 3

    @pytest.mark.parametrize(
        "instances,expected_agent,expected_busy,expected_idle",
        [
            ([], 0, 0, 0),  # Empty
        ],
    )
    def test_empty_state_counts(
        self, instances, expected_agent, expected_busy, expected_idle
    ):
        """Empty state has zero counts."""
        state = State(instances=instances)
        assert state.agent_count == expected_agent
        assert state.busy_count == expected_busy
        assert state.idle_count == expected_idle

    def test_to_dict(self):
        """to_dict returns complete structure."""
        agent = Agent(
            id="agent-1",
            title="Test",
            dir="proj",
            full_dir="/path/proj",
            status=SessionStatus.BUSY,
        )
        instance = Instance(port=3000, tty="/dev/tty", agents=[agent])
        todos = Todos(pending=5, in_progress=2)
        state = State(
            instances=[instance],
            todos=todos,
            updated=1234567890,
            connected=True,
        )
        result = state.to_dict()

        assert result["instance_count"] == 1
        assert result["agent_count"] == 1
        assert result["busy_count"] == 1
        assert result["idle_count"] == 0
        assert result["todos"] == {"pending": 5, "in_progress": 2}
        assert result["updated"] == 1234567890
        assert result["connected"] is True
        assert len(result["instances"]) == 1
        assert result["instances"][0]["port"] == 3000

    def test_to_dict_with_idle_agents(self):
        """to_dict includes correct idle_count."""
        busy_agent = Agent(
            id="busy-1",
            title="Busy",
            dir="proj",
            full_dir="/path/proj",
            status=SessionStatus.BUSY,
        )
        idle_agent = Agent(
            id="idle-1",
            title="Idle",
            dir="proj",
            full_dir="/path/proj",
            status=SessionStatus.IDLE,
        )
        instance = Instance(port=3000, agents=[busy_agent, idle_agent])
        state = State(instances=[instance], connected=True)
        result = state.to_dict()

        assert result["busy_count"] == 1
        assert result["idle_count"] == 1


# =============================================================================
# UsagePeriod Tests
# =============================================================================


class TestUsagePeriod:
    """Tests for UsagePeriod dataclass"""

    def test_defaults(self):
        """UsagePeriod default values."""
        period = UsagePeriod()
        assert period.utilization == 0
        assert period.resets_at is None

    def test_with_values(self):
        """UsagePeriod with custom values."""
        period = UsagePeriod(utilization=75, resets_at="2024-01-15T10:00:00Z")
        assert period.utilization == 75
        assert period.resets_at == "2024-01-15T10:00:00Z"

    @pytest.mark.parametrize(
        "utilization,resets_at",
        [
            (50, "2024-01-15T12:00:00Z"),
            (25, None),
        ],
    )
    def test_to_dict(self, utilization, resets_at):
        """to_dict method."""
        period = UsagePeriod(utilization=utilization, resets_at=resets_at)
        assert period.to_dict() == {"utilization": utilization, "resets_at": resets_at}


# =============================================================================
# Usage Tests
# =============================================================================


class TestUsage:
    """Tests for Usage dataclass"""

    def test_defaults(self):
        """Usage default values."""
        usage = Usage()
        assert isinstance(usage.five_hour, UsagePeriod)
        assert isinstance(usage.seven_day, UsagePeriod)
        assert usage.error is None
        assert isinstance(usage.updated, int)

    def test_with_periods(self):
        """Usage with custom periods."""
        five_hour = UsagePeriod(utilization=30, resets_at="2024-01-15T15:00:00Z")
        seven_day = UsagePeriod(utilization=60, resets_at="2024-01-20T00:00:00Z")
        usage = Usage(five_hour=five_hour, seven_day=seven_day)

        assert usage.five_hour.utilization == 30
        assert usage.seven_day.utilization == 60

    def test_with_error(self):
        """Usage with error message."""
        usage = Usage(error="API rate limited")
        assert usage.error == "API rate limited"

    def test_to_dict_without_error(self):
        """to_dict without error."""
        five_hour = UsagePeriod(utilization=40, resets_at="2024-01-15T15:00:00Z")
        seven_day = UsagePeriod(utilization=80, resets_at="2024-01-20T00:00:00Z")
        usage = Usage(five_hour=five_hour, seven_day=seven_day, updated=1234567890)
        result = usage.to_dict()

        assert result["five_hour"] == {
            "utilization": 40,
            "resets_at": "2024-01-15T15:00:00Z",
        }
        assert result["seven_day"] == {
            "utilization": 80,
            "resets_at": "2024-01-20T00:00:00Z",
        }
        assert result["updated"] == 1234567890
        assert "error" not in result

    def test_to_dict_with_error(self):
        """to_dict includes error when set."""
        usage = Usage(error="Connection failed", updated=1234567890)
        result = usage.to_dict()

        assert result["error"] == "Connection failed"
        assert result["updated"] == 1234567890
