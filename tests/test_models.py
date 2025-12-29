"""
Tests for opencode_monitor.core.models

Coverage target: 100% for all model classes
"""

import pytest
import time
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


class TestSessionStatus:
    """Tests for SessionStatus enum"""

    def test_idle_value(self):
        assert SessionStatus.IDLE.value == "idle"

    def test_busy_value(self):
        assert SessionStatus.BUSY.value == "busy"


class TestTodoStatus:
    """Tests for TodoStatus enum"""

    def test_pending_value(self):
        assert TodoStatus.PENDING.value == "pending"

    def test_in_progress_value(self):
        assert TodoStatus.IN_PROGRESS.value == "in_progress"

    def test_completed_value(self):
        assert TodoStatus.COMPLETED.value == "completed"


class TestTool:
    """Tests for Tool dataclass"""

    def test_default_arg(self):
        """Test that default arg is empty string"""
        tool = Tool(name="bash")
        assert tool.name == "bash"
        assert tool.arg == ""

    def test_with_arg(self):
        """Test tool with custom arg"""
        tool = Tool(name="read", arg="/path/to/file.py")
        assert tool.name == "read"
        assert tool.arg == "/path/to/file.py"

    def test_to_dict(self):
        """Test to_dict method returns correct structure"""
        tool = Tool(name="write", arg="content.txt")
        result = tool.to_dict()

        assert result == {"name": "write", "arg": "content.txt"}

    def test_to_dict_empty_arg(self):
        """Test to_dict with default empty arg"""
        tool = Tool(name="bash")
        result = tool.to_dict()

        assert result == {"name": "bash", "arg": ""}


class TestAgentTodos:
    """Tests for AgentTodos dataclass"""

    def test_defaults(self):
        """Test default values"""
        todos = AgentTodos()
        assert todos.pending == 0
        assert todos.in_progress == 0
        assert todos.current_label == ""
        assert todos.next_label == ""

    def test_with_values(self):
        """Test with custom values"""
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
        """Test to_dict method returns correct structure"""
        todos = AgentTodos(
            pending=5,
            in_progress=2,
            current_label="Current task",
            next_label="Next task",
        )
        result = todos.to_dict()

        assert result == {
            "pending": 5,
            "in_progress": 2,
            "current_label": "Current task",
            "next_label": "Next task",
        }

    def test_total_property(self):
        """Test total property sums pending and in_progress"""
        todos = AgentTodos(pending=3, in_progress=2)
        assert todos.total == 5

    def test_total_property_zeros(self):
        """Test total property with zero values"""
        todos = AgentTodos()
        assert todos.total == 0


class TestAgent:
    """Tests for Agent dataclass"""

    def test_minimal_agent(self):
        """Test agent with required fields only"""
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

    def test_is_subagent_false(self):
        """Test is_subagent returns False when no parent"""
        agent = Agent(
            id="agent-123",
            title="Main Session",
            dir="project",
            full_dir="/path",
            status=SessionStatus.IDLE,
        )
        assert agent.is_subagent is False

    def test_is_subagent_true(self):
        """Test is_subagent returns True when parent_id is set"""
        agent = Agent(
            id="sub-agent-456",
            title="Sub Agent",
            dir="project",
            full_dir="/path",
            status=SessionStatus.BUSY,
            parent_id="agent-123",
        )
        assert agent.is_subagent is True

    def test_to_dict_without_parent(self):
        """Test to_dict without parent_id"""
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
        assert result["tools"] == [{"name": "bash", "arg": "ls -la"}]
        assert result["todos"] == {
            "pending": 2,
            "in_progress": 1,
            "current_label": "Task",
            "next_label": "",
        }
        assert "parent_id" not in result

    def test_to_dict_with_parent(self):
        """Test to_dict includes parent_id when set"""
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
        """Test to_dict with multiple tools"""
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
        assert result["tools"][0] == {"name": "read", "arg": "file1.py"}
        assert result["tools"][1] == {"name": "write", "arg": "file2.py"}
        assert result["tools"][2] == {"name": "bash", "arg": "pytest"}


class TestInstance:
    """Tests for Instance dataclass"""

    def test_defaults(self):
        """Test default values"""
        instance = Instance(port=3000)
        assert instance.port == 3000
        assert instance.tty == ""
        assert instance.agents == []

    def test_with_tty(self):
        """Test instance with tty"""
        instance = Instance(port=3001, tty="/dev/ttys001")
        assert instance.tty == "/dev/ttys001"

    def test_agent_count_empty(self):
        """Test agent_count with no agents"""
        instance = Instance(port=3000)
        assert instance.agent_count == 0

    def test_agent_count_with_agents(self):
        """Test agent_count with multiple agents"""
        agents = [
            Agent(id="1", title="A", dir="d", full_dir="/d", status=SessionStatus.IDLE),
            Agent(id="2", title="B", dir="d", full_dir="/d", status=SessionStatus.BUSY),
            Agent(id="3", title="C", dir="d", full_dir="/d", status=SessionStatus.IDLE),
        ]
        instance = Instance(port=3000, agents=agents)
        assert instance.agent_count == 3

    def test_busy_count_none_busy(self):
        """Test busy_count when no agents are busy"""
        agents = [
            Agent(id="1", title="A", dir="d", full_dir="/d", status=SessionStatus.IDLE),
            Agent(id="2", title="B", dir="d", full_dir="/d", status=SessionStatus.IDLE),
        ]
        instance = Instance(port=3000, agents=agents)
        assert instance.busy_count == 0

    def test_busy_count_some_busy(self):
        """Test busy_count with some busy agents"""
        agents = [
            Agent(id="1", title="A", dir="d", full_dir="/d", status=SessionStatus.BUSY),
            Agent(id="2", title="B", dir="d", full_dir="/d", status=SessionStatus.IDLE),
            Agent(id="3", title="C", dir="d", full_dir="/d", status=SessionStatus.BUSY),
        ]
        instance = Instance(port=3000, agents=agents)
        assert instance.busy_count == 2

    def test_busy_count_all_busy(self):
        """Test busy_count when all agents are busy"""
        agents = [
            Agent(id="1", title="A", dir="d", full_dir="/d", status=SessionStatus.BUSY),
            Agent(id="2", title="B", dir="d", full_dir="/d", status=SessionStatus.BUSY),
        ]
        instance = Instance(port=3000, agents=agents)
        assert instance.busy_count == 2

    def test_to_dict(self):
        """Test to_dict method"""
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
        assert len(result["agents"]) == 1
        assert result["agents"][0]["id"] == "agent-1"

    def test_to_dict_empty_agents(self):
        """Test to_dict with no agents"""
        instance = Instance(port=3000)
        result = instance.to_dict()

        assert result["port"] == 3000
        assert result["agents"] == []
        assert result["agent_count"] == 0
        assert result["busy_count"] == 0


class TestTodos:
    """Tests for Todos dataclass"""

    def test_defaults(self):
        """Test default values"""
        todos = Todos()
        assert todos.pending == 0
        assert todos.in_progress == 0

    def test_with_values(self):
        """Test with custom values"""
        todos = Todos(pending=10, in_progress=3)
        assert todos.pending == 10
        assert todos.in_progress == 3

    def test_to_dict(self):
        """Test to_dict method"""
        todos = Todos(pending=5, in_progress=2)
        result = todos.to_dict()

        assert result == {"pending": 5, "in_progress": 2}


class TestState:
    """Tests for State dataclass"""

    def test_defaults(self):
        """Test default values"""
        state = State()
        assert state.instances == []
        assert isinstance(state.todos, Todos)
        assert isinstance(state.updated, int)
        assert state.connected is False

    def test_connected_true(self):
        """Test state with connected=True"""
        state = State(connected=True)
        assert state.connected is True

    def test_instance_count_empty(self):
        """Test instance_count with no instances"""
        state = State()
        assert state.instance_count == 0

    def test_instance_count_multiple(self):
        """Test instance_count with multiple instances"""
        instances = [
            Instance(port=3000),
            Instance(port=3001),
            Instance(port=3002),
        ]
        state = State(instances=instances)
        assert state.instance_count == 3

    def test_agent_count_empty(self):
        """Test agent_count with no instances"""
        state = State()
        assert state.agent_count == 0

    def test_agent_count_sums_all_instances(self):
        """Test agent_count sums agents across all instances"""
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

    def test_busy_count_empty(self):
        """Test busy_count with no instances"""
        state = State()
        assert state.busy_count == 0

    def test_busy_count_sums_all_instances(self):
        """Test busy_count sums busy agents across all instances"""
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

    def test_to_dict(self):
        """Test to_dict method returns complete structure"""
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
        assert result["todos"] == {"pending": 5, "in_progress": 2}
        assert result["updated"] == 1234567890
        assert result["connected"] is True
        assert len(result["instances"]) == 1
        assert result["instances"][0]["port"] == 3000


class TestUsagePeriod:
    """Tests for UsagePeriod dataclass"""

    def test_defaults(self):
        """Test default values"""
        period = UsagePeriod()
        assert period.utilization == 0
        assert period.resets_at is None

    def test_with_values(self):
        """Test with custom values"""
        period = UsagePeriod(utilization=75, resets_at="2024-01-15T10:00:00Z")
        assert period.utilization == 75
        assert period.resets_at == "2024-01-15T10:00:00Z"

    def test_to_dict(self):
        """Test to_dict method"""
        period = UsagePeriod(utilization=50, resets_at="2024-01-15T12:00:00Z")
        result = period.to_dict()

        assert result == {
            "utilization": 50,
            "resets_at": "2024-01-15T12:00:00Z",
        }

    def test_to_dict_none_resets_at(self):
        """Test to_dict with None resets_at"""
        period = UsagePeriod(utilization=25)
        result = period.to_dict()

        assert result == {"utilization": 25, "resets_at": None}


class TestUsage:
    """Tests for Usage dataclass"""

    def test_defaults(self):
        """Test default values"""
        usage = Usage()
        assert isinstance(usage.five_hour, UsagePeriod)
        assert isinstance(usage.seven_day, UsagePeriod)
        assert usage.error is None
        assert isinstance(usage.updated, int)

    def test_with_periods(self):
        """Test with custom periods"""
        five_hour = UsagePeriod(utilization=30, resets_at="2024-01-15T15:00:00Z")
        seven_day = UsagePeriod(utilization=60, resets_at="2024-01-20T00:00:00Z")
        usage = Usage(five_hour=five_hour, seven_day=seven_day)

        assert usage.five_hour.utilization == 30
        assert usage.seven_day.utilization == 60

    def test_with_error(self):
        """Test with error message"""
        usage = Usage(error="API rate limited")
        assert usage.error == "API rate limited"

    def test_to_dict_without_error(self):
        """Test to_dict without error"""
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
        """Test to_dict includes error when set"""
        usage = Usage(error="Connection failed", updated=1234567890)
        result = usage.to_dict()

        assert result["error"] == "Connection failed"
        assert result["updated"] == 1234567890
