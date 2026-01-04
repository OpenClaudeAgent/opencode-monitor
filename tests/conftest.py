"""
Pytest configuration and shared fixtures for opencode_monitor tests.

This module provides:
- rumps mocking infrastructure for UI tests
- Common fixtures for models, mocks, and test data factories
- Analytics DB and tracing service fixtures
- Qt application fixture (session scope)
- Pytest markers and configuration
"""

import sys
import json
import time
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


# Store original rumps module state at conftest import time
_original_rumps = sys.modules.get("rumps")
_rumps_was_real = _original_rumps is not None and hasattr(_original_rumps, "__file__")


def pytest_runtest_setup(item):
    """Reset rumps module before tests that need real/fresh imports.

    test_menu.py modifies sys.modules["rumps"] at import time with a mock.
    This pollutes subsequent tests. We reset it for affected test files.
    """
    # List of test files that need fresh rumps imports (not the mock from test_menu.py)
    needs_fresh_rumps = ["test_tooltips", "test_db_concurrency"]

    if any(name in str(item.fspath) for name in needs_fresh_rumps):
        # Remove any mock rumps before these tests
        if "rumps" in sys.modules:
            current = sys.modules["rumps"]
            if not hasattr(current, "__file__"):  # It's a mock
                del sys.modules["rumps"]
                # Only clear modules that actually import rumps (not all ui/app modules)
                # This prevents breaking unrelated tests like test_terminal
                rumps_dependent_modules = [
                    "opencode_monitor.ui.menu",
                    "opencode_monitor.app",
                    "opencode_monitor.app.core",
                    "opencode_monitor.app.menu",
                ]
                for mod in rumps_dependent_modules:
                    if mod in sys.modules:
                        del sys.modules[mod]


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


# =============================================================================
# Analytics Database Fixtures
# =============================================================================


@pytest.fixture
def analytics_db(tmp_path: Path):
    """Create a fresh AnalyticsDB (DuckDB) for each test.

    This fixture is shared across all tests needing AnalyticsDB.
    Uses a unique path per test to ensure isolation.
    """
    from opencode_monitor.analytics.db import AnalyticsDB

    db_path = tmp_path / "test_analytics.duckdb"
    db = AnalyticsDB(db_path)
    db.connect()
    return db


# Alias for backward compatibility - tests can use either name
@pytest.fixture
def db(analytics_db):
    """Alias for analytics_db - backward compatible fixture name."""
    return analytics_db


# =============================================================================
# Tracing Data Service Fixtures
# =============================================================================


@pytest.fixture
def tracing_service(analytics_db):
    """Create a TracingDataService instance with analytics_db."""
    from opencode_monitor.analytics.tracing import TracingDataService

    return TracingDataService(db=analytics_db)


# =============================================================================
# Security Analyzer Fixtures
# =============================================================================


@pytest.fixture
def risk_analyzer():
    """Create a fresh RiskAnalyzer for security tests."""
    from opencode_monitor.security.analyzer import RiskAnalyzer

    return RiskAnalyzer()


# =============================================================================
# Time-based Test Fixtures
# =============================================================================


@pytest.fixture
def base_time() -> float:
    """Base timestamp for event-based tests (correlator, sequences, etc.)."""
    return time.time()


# =============================================================================
# Qt Application Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for the test session.

    Session-scoped to avoid multiple QApplication instances.
    Works for both unit tests and integration tests.
    """
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    yield app
