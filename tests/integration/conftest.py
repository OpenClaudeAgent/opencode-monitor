"""
Pytest configuration and fixtures for integration tests.

Provides:
- Mock API client that replaces the real HTTP client
- QApplication fixture for PyQt tests
- Dashboard fixtures with mocked dependencies
- Helper utilities for UI interaction testing
"""

import sys
from pathlib import Path
from typing import Any, Callable, Optional
from unittest.mock import MagicMock, patch

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from .fixtures import MockAPIResponses


# =============================================================================
# Mock API Client
# =============================================================================


class MockAnalyticsAPIClient:
    """Mock API client that returns pre-configured responses.

    Replaces the real AnalyticsAPIClient to avoid HTTP calls during tests.
    All responses are configured via the `responses` parameter.
    """

    def __init__(self, responses: dict[str, Any] | None = None):
        """Initialize with optional pre-configured responses.

        Args:
            responses: Dict of API responses, keyed by method/endpoint
        """
        self._responses = responses or MockAPIResponses.basic()
        self._available = True
        self._call_log: list[tuple[str, dict]] = []

    def _log_call(self, method: str, **kwargs: Any) -> None:
        """Log API call for verification in tests."""
        self._call_log.append((method, kwargs))

    @property
    def is_available(self) -> bool:
        """Return configured availability."""
        return self._available

    def set_available(self, available: bool) -> None:
        """Set API availability for testing offline scenarios."""
        self._available = available

    def health_check(self) -> bool:
        """Return configured health status."""
        self._log_call("health_check")
        return self._responses.get("health", True)

    def get_stats(self) -> Optional[dict]:
        """Return configured stats."""
        self._log_call("get_stats")
        return self._responses.get("stats")

    def get_global_stats(self, days: int = 30) -> Optional[dict]:
        """Return configured global stats."""
        self._log_call("get_global_stats", days=days)
        return self._responses.get("global_stats")

    def get_sessions(self, days: int = 30, limit: int = 100) -> Optional[list]:
        """Return configured sessions list."""
        self._log_call("get_sessions", days=days, limit=limit)
        return self._responses.get("sessions", [])

    def get_traces(self, days: int = 30, limit: int = 500) -> Optional[list]:
        """Return configured traces list."""
        self._log_call("get_traces", days=days, limit=limit)
        return self._responses.get("traces", [])

    def get_delegations(self, days: int = 30, limit: int = 1000) -> Optional[list]:
        """Return configured delegations list."""
        self._log_call("get_delegations", days=days, limit=limit)
        return self._responses.get("delegations", [])

    def get_session_summary(self, session_id: str) -> Optional[dict]:
        """Return configured session summary."""
        self._log_call("get_session_summary", session_id=session_id)
        summaries = self._responses.get("session_summaries", {})
        return summaries.get(session_id)

    def get_session_messages(self, session_id: str) -> Optional[list]:
        """Return configured session messages."""
        self._log_call("get_session_messages", session_id=session_id)
        messages = self._responses.get("session_messages", {})
        return messages.get(session_id, [])

    def get_session_operations(self, session_id: str) -> Optional[list]:
        """Return configured session operations."""
        self._log_call("get_session_operations", session_id=session_id)
        operations = self._responses.get("session_operations", {})
        return operations.get(session_id, [])

    def get_session_tokens(self, session_id: str) -> Optional[dict]:
        """Return configured session tokens."""
        self._log_call("get_session_tokens", session_id=session_id)
        return None

    def get_session_tools(self, session_id: str) -> Optional[dict]:
        """Return configured session tools."""
        self._log_call("get_session_tools", session_id=session_id)
        return None

    def get_session_files(self, session_id: str) -> Optional[dict]:
        """Return configured session files."""
        self._log_call("get_session_files", session_id=session_id)
        return None

    def get_session_agents(self, session_id: str) -> Optional[list]:
        """Return configured session agents."""
        self._log_call("get_session_agents", session_id=session_id)
        return None

    def get_session_timeline(self, session_id: str) -> Optional[list]:
        """Return configured session timeline."""
        self._log_call("get_session_timeline", session_id=session_id)
        return None

    def get_session_prompts(self, session_id: str) -> Optional[dict]:
        """Return configured session prompts."""
        self._log_call("get_session_prompts", session_id=session_id)
        return None

    def get_call_log(self) -> list[tuple[str, dict]]:
        """Return log of all API calls made during test."""
        return self._call_log.copy()

    def clear_call_log(self) -> None:
        """Clear the API call log."""
        self._call_log.clear()


# =============================================================================
# PyQt Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for the test session.

    Uses pytest-qt's built-in qapp fixture internally.
    This ensures proper Qt initialization and cleanup.
    """
    from PyQt6.QtWidgets import QApplication

    # Check if app already exists (pytest-qt may have created one)
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    yield app

    # Don't quit the app here - let pytest-qt handle cleanup


@pytest.fixture
def mock_api_client():
    """Create a mock API client with basic responses."""
    return MockAnalyticsAPIClient(MockAPIResponses.basic())


@pytest.fixture
def mock_api_client_empty():
    """Create a mock API client with empty responses."""
    return MockAnalyticsAPIClient(MockAPIResponses.empty())


@pytest.fixture
def mock_api_client_complex():
    """Create a mock API client with complex multi-session responses."""
    return MockAnalyticsAPIClient(MockAPIResponses.complex())


@pytest.fixture
def mock_api_factory():
    """Factory fixture to create mock API clients with custom responses."""

    def factory(responses: dict[str, Any] | None = None) -> MockAnalyticsAPIClient:
        return MockAnalyticsAPIClient(responses or MockAPIResponses.basic())

    return factory


@pytest.fixture
def patched_api_client(mock_api_client):
    """Patch get_api_client to return the mock client.

    This fixture patches the global get_api_client function so that
    all dashboard code uses the mock client instead of the real one.
    """
    with patch(
        "opencode_monitor.api.client.get_api_client", return_value=mock_api_client
    ):
        # Also patch the api module's __init__ export
        with patch("opencode_monitor.api.get_api_client", return_value=mock_api_client):
            yield mock_api_client


@pytest.fixture
def patched_monitoring():
    """Patch monitoring fetch to avoid real network calls."""
    import asyncio
    from opencode_monitor.core.models import State, Todos

    async def mock_fetch():
        return State(
            instances=[], todos=Todos(pending=0, in_progress=0), connected=False
        )

    # Use side_effect to return a new coroutine each time
    mock = MagicMock(side_effect=lambda: mock_fetch())

    with patch("opencode_monitor.core.monitor.fetch_all_instances", mock):
        yield


@pytest.fixture
def patched_security():
    """Patch security auditor to avoid real file scanning."""
    mock_auditor = MagicMock()
    mock_auditor.get_stats.return_value = {
        "total_scanned": 0,
        "total_commands": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    mock_auditor.get_all_commands.return_value = []
    mock_auditor.get_all_reads.return_value = []
    mock_auditor.get_all_writes.return_value = []
    mock_auditor.get_critical_commands.return_value = []
    mock_auditor.get_commands_by_level.return_value = []
    mock_auditor.get_sensitive_reads.return_value = []
    mock_auditor.get_sensitive_writes.return_value = []
    mock_auditor.get_risky_webfetches.return_value = []

    with patch(
        "opencode_monitor.security.auditor.get_auditor", return_value=mock_auditor
    ):
        yield mock_auditor


@pytest.fixture
def dashboard_window(qtbot, patched_api_client, patched_monitoring, patched_security):
    """Create a dashboard window with all dependencies mocked.

    This is the main fixture for testing dashboard functionality.
    It patches the API client, monitoring, and security modules to
    avoid any real network or file operations.

    Args:
        qtbot: pytest-qt's qtbot fixture for UI interaction
        patched_api_client: Mock API client fixture
        patched_monitoring: Mock monitoring fixture
        patched_security: Mock security fixture

    Yields:
        DashboardWindow: Fully mocked dashboard window
    """
    from opencode_monitor.dashboard.window import DashboardWindow

    # Create window (patches are already active from fixtures)
    window = DashboardWindow()

    # Register with qtbot for proper cleanup
    qtbot.addWidget(window)

    # Show window (needed for some Qt operations)
    window.show()

    # Process events to ensure window is fully initialized
    qtbot.waitExposed(window)

    yield window

    # Cleanup: stop timers before closing
    if window._refresh_timer:
        window._refresh_timer.stop()
    if window._sync_checker:
        window._sync_checker.stop()

    window.close()


@pytest.fixture
def dashboard_window_hidden(
    qtbot, patched_api_client, patched_monitoring, patched_security
):
    """Create a dashboard window without showing it.

    Useful for testing initialization logic without visual display.
    """
    from opencode_monitor.dashboard.window import DashboardWindow

    window = DashboardWindow()
    qtbot.addWidget(window)

    yield window

    if window._refresh_timer:
        window._refresh_timer.stop()
    if window._sync_checker:
        window._sync_checker.stop()

    window.close()


# =============================================================================
# Helper Fixtures
# =============================================================================


@pytest.fixture
def wait_for_signal():
    """Fixture to wait for Qt signals with timeout."""

    def waiter(qtbot, signal, timeout: int = 1000) -> bool:
        """Wait for a signal to be emitted.

        Args:
            qtbot: pytest-qt's qtbot fixture
            signal: Qt signal to wait for
            timeout: Maximum wait time in milliseconds

        Returns:
            True if signal was received, False if timeout
        """
        try:
            with qtbot.waitSignal(signal, timeout=timeout):
                return True
        except Exception:
            return False

    return waiter


@pytest.fixture
def click_sidebar_item():
    """Fixture to click a sidebar navigation item."""

    def clicker(qtbot, sidebar, index: int) -> None:
        """Click a sidebar item by index.

        Args:
            qtbot: pytest-qt's qtbot fixture
            sidebar: Sidebar widget
            index: Item index (0=Monitoring, 1=Security, etc.)
        """
        # Get the button at the specified index
        buttons = sidebar._buttons
        if 0 <= index < len(buttons):
            qtbot.mouseClick(buttons[index], qt_core.Qt.MouseButton.LeftButton)

    from PyQt6 import QtCore as qt_core

    return clicker


# =============================================================================
# Markers
# =============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "slow: marks tests as slow running")
