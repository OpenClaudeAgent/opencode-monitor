"""
Pytest configuration and shared fixtures for opencode_monitor tests.

This module provides:
- rumps mocking infrastructure for UI tests
- Common fixtures for models, mocks, and test data factories
- Pytest markers and configuration
"""

import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from unittest.mock import MagicMock, patch

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


# =============================================================================
# Rumps Mock Infrastructure (shared by test_app.py and test_menu.py)
# =============================================================================


class MockMenuItem:
    """Mock for rumps.MenuItem with proper menu behavior."""

    def __init__(self, title="", callback=None, **kwargs):
        self.title = title
        self.callback = callback
        self._items = []
        self._items_dict = {}
        self.state = 0
        self._menuitem = MagicMock()
        self.parent = None

    def add(self, item):
        if isinstance(item, MockMenuItem):
            self._items.append(item)
            self._items_dict[item.title] = item
            item.parent = self
        elif item is None:
            # Separator
            self._items.append(None)

    def clear(self):
        self._items = []
        self._items_dict = {}

    def values(self):
        return [item for item in self._items if item is not None]

    def __iter__(self):
        return iter(self._items)

    def __repr__(self):
        return f"MockMenuItem({self.title!r})"


class MockMenu:
    """Mock rumps menu with proper list-like and method behavior."""

    def __init__(self):
        self._items = []
        self._clear_called = False
        self._add_calls = []

    def clear(self):
        self._items = []
        self._clear_called = True

    def add(self, item):
        self._items.append(item)
        self._add_calls.append(item)

    def __setitem__(self, key, value):
        pass

    def __getitem__(self, key):
        return self._items[key] if isinstance(key, int) else None

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class MockApp:
    """Mock rumps.App base class."""

    def __init__(self, name="", title="", quit_button=None, **kwargs):
        self.name = name
        self.title = title
        self._menu = MockMenu()

    @property
    def menu(self):
        return self._menu

    @menu.setter
    def menu(self, value):
        if isinstance(value, list):
            self._menu = MockMenu()
            for item in value:
                self._menu.add(item)
        else:
            self._menu = value

    def run(self):
        pass


@pytest.fixture
def mock_rumps():
    """Provide a mock rumps module for UI tests."""
    rumps_mock = MagicMock()
    rumps_mock.App = MockApp
    rumps_mock.MenuItem = MockMenuItem
    rumps_mock.timer = lambda interval: lambda f: f
    rumps_mock.quit_application = MagicMock()
    return rumps_mock


# =============================================================================
# Security Auditor Mock Infrastructure
# =============================================================================


def create_default_auditor_stats() -> dict:
    """Create default stats dict for auditor mocking."""
    return {
        "total_scanned": 0,
        "total_commands": 0,
        "total_reads": 0,
        "total_writes": 0,
        "total_webfetches": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "reads_critical": 0,
        "reads_high": 0,
        "reads_medium": 0,
        "writes_critical": 0,
        "writes_high": 0,
        "writes_medium": 0,
        "webfetches_critical": 0,
        "webfetches_high": 0,
        "webfetches_medium": 0,
    }


@pytest.fixture
def mock_db():
    """Create a mock SecurityDatabase with default configuration."""
    db = MagicMock()
    db.get_stats.return_value = create_default_auditor_stats()
    db.get_all_scanned_ids.return_value = set()
    db.get_commands_by_level.return_value = []
    db.get_reads_by_level.return_value = []
    db.get_writes_by_level.return_value = []
    db.get_webfetches_by_level.return_value = []
    db.get_all_commands.return_value = []
    db.get_all_reads.return_value = []
    db.get_all_writes.return_value = []
    db.get_all_webfetches.return_value = []
    db.insert_command.return_value = True
    db.insert_read.return_value = True
    db.insert_write.return_value = True
    db.insert_webfetch.return_value = True
    return db


@pytest.fixture
def mock_auditor(mock_db):
    """Create a mock SecurityAuditor with default configuration."""
    auditor = MagicMock()
    auditor.get_stats.return_value = create_default_auditor_stats()
    auditor.get_critical_commands.return_value = []
    auditor.get_sensitive_reads.return_value = []
    auditor.get_sensitive_writes.return_value = []
    auditor.get_risky_webfetches.return_value = []
    auditor.get_all_commands.return_value = []
    auditor.get_all_reads.return_value = []
    auditor.get_all_writes.return_value = []
    auditor.get_all_webfetches.return_value = []
    auditor.generate_report.return_value = "Security Report"
    auditor._db = mock_db
    return auditor


# =============================================================================
# Tool File Content Factory (for auditor tests)
# =============================================================================


def create_tool_file_content(
    tool: str,
    session_id: str = "sess-001",
    timestamp: int = 1703001000000,
    **input_args,
) -> dict:
    """
    Factory to create tool file content for auditor tests.

    Args:
        tool: Tool name (bash, read, write, edit, webfetch)
        session_id: Session ID
        timestamp: Timestamp in milliseconds
        **input_args: Additional input arguments for the tool

    Examples:
        >>> create_tool_file_content("bash", command="ls -la")
        >>> create_tool_file_content("read", filePath="/etc/passwd")
        >>> create_tool_file_content("webfetch", url="https://example.com")
    """
    return {
        "type": "tool",
        "tool": tool,
        "sessionID": session_id,
        "state": {
            "input": input_args,
            "time": {"start": timestamp},
        },
    }


@pytest.fixture
def tool_content_factory():
    """Fixture providing the tool content factory function."""
    return create_tool_file_content


# =============================================================================
# Model Fixtures
# =============================================================================


@pytest.fixture
def sample_agent():
    """Create a sample Agent for testing."""
    from opencode_monitor.core.models import Agent, SessionStatus

    return Agent(
        id="agent-test-1",
        title="Test Agent",
        dir="project",
        full_dir="/home/user/project",
        status=SessionStatus.BUSY,
    )


@pytest.fixture
def sample_idle_agent():
    """Create a sample idle Agent for testing."""
    from opencode_monitor.core.models import Agent, SessionStatus

    return Agent(
        id="agent-idle-1",
        title="Idle Agent",
        dir="project",
        full_dir="/home/user/project",
        status=SessionStatus.IDLE,
    )


@pytest.fixture
def sample_instance(sample_agent):
    """Create a sample Instance with one agent."""
    from opencode_monitor.core.models import Instance

    return Instance(
        port=8080,
        tty="/dev/ttys001",
        agents=[sample_agent],
    )


@pytest.fixture
def sample_state(sample_instance):
    """Create a sample State with one instance."""
    from opencode_monitor.core.models import State, Todos

    return State(
        instances=[sample_instance],
        todos=Todos(pending=3, in_progress=1),
        connected=True,
    )


# =============================================================================
# Async Test Helpers
# =============================================================================


def run_async(coro):
    """Helper to run async coroutines in sync tests."""
    import asyncio

    return asyncio.run(coro)


@pytest.fixture
def async_runner():
    """Fixture providing the async runner function."""
    return run_async


# =============================================================================
# Temporary Storage Helpers
# =============================================================================


@pytest.fixture
def mock_storage(tmp_path):
    """Create a mock OpenCode storage directory structure."""
    storage = tmp_path / "opencode_storage"
    storage.mkdir(parents=True)
    return storage


def create_prt_file(storage: Path, msg_id: str, file_id: str, content: dict) -> Path:
    """Helper to create a prt_*.json file in storage."""
    msg_dir = storage / msg_id
    msg_dir.mkdir(parents=True, exist_ok=True)
    file_path = msg_dir / f"prt_{file_id}.json"
    file_path.write_text(json.dumps(content))
    return file_path


@pytest.fixture
def prt_file_factory(mock_storage):
    """Fixture providing a factory to create prt files in mock storage."""

    def factory(msg_id: str, file_id: str, content: dict) -> Path:
        return create_prt_file(mock_storage, msg_id, file_id, content)

    return factory
