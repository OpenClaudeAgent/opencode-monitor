"""
Data models for OpenCode Monitor
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import time


class SessionStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"


class TodoStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class Tool:
    """A tool being executed by an agent"""

    name: str
    arg: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "arg": self.arg}


@dataclass
class AgentTodos:
    """Todo counters and labels for a single agent"""

    pending: int = 0
    in_progress: int = 0
    current_label: str = ""  # Label of in_progress todo
    next_label: str = ""  # Label of first pending todo

    def to_dict(self) -> dict:
        return {
            "pending": self.pending,
            "in_progress": self.in_progress,
            "current_label": self.current_label,
            "next_label": self.next_label,
        }

    @property
    def total(self) -> int:
        return self.pending + self.in_progress


@dataclass
class Agent:
    """A session/agent within an OpenCode instance"""

    id: str
    title: str
    dir: str  # Short directory name
    full_dir: str  # Full path
    status: SessionStatus
    permission_pending: bool = False
    tools: list[Tool] = field(default_factory=list)
    todos: AgentTodos = field(default_factory=AgentTodos)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "dir": self.dir,
            "full_dir": self.full_dir,
            "status": self.status.value,
            "permission_pending": self.permission_pending,
            "tools": [t.to_dict() for t in self.tools],
            "todos": self.todos.to_dict(),
        }


@dataclass
class Instance:
    """An OpenCode instance running on a specific port"""

    port: int
    tty: str = ""
    agents: list[Agent] = field(default_factory=list)

    @property
    def agent_count(self) -> int:
        return len(self.agents)

    @property
    def busy_count(self) -> int:
        return sum(1 for a in self.agents if a.status == SessionStatus.BUSY)

    def to_dict(self) -> dict:
        return {
            "port": self.port,
            "tty": self.tty,
            "agents": [a.to_dict() for a in self.agents],
            "agent_count": self.agent_count,
            "busy_count": self.busy_count,
        }


@dataclass
class Todos:
    """Todo counters"""

    pending: int = 0
    in_progress: int = 0

    def to_dict(self) -> dict:
        return {"pending": self.pending, "in_progress": self.in_progress}


@dataclass
class State:
    """Complete state for SwiftBar consumption"""

    instances: list[Instance] = field(default_factory=list)
    todos: Todos = field(default_factory=Todos)
    permissions_pending: int = 0
    updated: int = field(default_factory=lambda: int(time.time()))
    connected: bool = False

    @property
    def instance_count(self) -> int:
        return len(self.instances)

    @property
    def agent_count(self) -> int:
        return sum(i.agent_count for i in self.instances)

    @property
    def busy_count(self) -> int:
        return sum(i.busy_count for i in self.instances)

    def to_dict(self) -> dict:
        return {
            "instances": [i.to_dict() for i in self.instances],
            "instance_count": self.instance_count,
            "agent_count": self.agent_count,
            "busy_count": self.busy_count,
            "todos": self.todos.to_dict(),
            "permissions_pending": self.permissions_pending,
            "updated": self.updated,
            "connected": self.connected,
        }


@dataclass
class UsagePeriod:
    """Usage data for a time period"""

    utilization: int = 0  # Percentage 0-100
    resets_at: Optional[str] = None  # ISO datetime

    def to_dict(self) -> dict:
        return {"utilization": self.utilization, "resets_at": self.resets_at}


@dataclass
class Usage:
    """Anthropic API usage data"""

    five_hour: UsagePeriod = field(default_factory=UsagePeriod)
    seven_day: UsagePeriod = field(default_factory=UsagePeriod)
    error: Optional[str] = None
    updated: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> dict:
        result = {
            "five_hour": self.five_hour.to_dict(),
            "seven_day": self.seven_day.to_dict(),
            "updated": self.updated,
        }
        if self.error:
            result["error"] = self.error
        return result
