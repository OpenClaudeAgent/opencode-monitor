"""
Pytest configuration and fixtures for integration tests.

Provides:
- Mock API client that replaces the real HTTP client
- QApplication fixture for PyQt tests
- Dashboard fixtures with mocked dependencies

Architecture note:
The dashboard accesses data ONLY via the API client (get_api_client()).
It does NOT access DuckDB directly. The API client is mocked in tests
to provide controlled responses without network calls.
"""

import sys
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import from reorganized fixtures
from .fixtures import (
    MockAPIResponses,
    SIGNAL_WAIT_MS,
    SECTION_MONITORING,
    SECTION_SECURITY,
    SECTION_ANALYTICS,
    SECTION_TRACING,
    EXPECTED_TRACING,
)

# Import helpers (now as fixtures from helpers module)
from .helpers.assertions import assert_table_content, assert_widget_content
from .helpers.navigation import click_nav, click_tab, select_first_session
from .helpers.signals import wait_for_signal


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

    def get_session_tokens(self, session_id: str) -> Optional[dict]:
        """Return configured session tokens."""
        self._log_call("get_session_tokens", session_id=session_id)
        tokens = self._responses.get("session_tokens", {})
        return tokens.get(session_id)

    def get_session_tools(self, session_id: str) -> Optional[list]:
        """Return configured session tools."""
        self._log_call("get_session_tools", session_id=session_id)
        tools = self._responses.get("session_tools", {})
        return tools.get(session_id)

    def get_session_files(self, session_id: str) -> Optional[list]:
        """Return configured session files."""
        self._log_call("get_session_files", session_id=session_id)
        files = self._responses.get("session_files", {})
        return files.get(session_id)

    def get_session_agents(self, session_id: str) -> Optional[list]:
        """Return configured session agents."""
        self._log_call("get_session_agents", session_id=session_id)
        agents = self._responses.get("session_agents", {})
        return agents.get(session_id)

    def get_session_timeline(self, session_id: str) -> Optional[list]:
        """Return configured session timeline."""
        self._log_call("get_session_timeline", session_id=session_id)
        timeline = self._responses.get("session_timeline", {})
        return timeline.get(session_id)

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
    """Create QApplication for the test session."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    yield app


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

    This is the ONLY mock needed for the dashboard - it accesses
    all data through the API client, not directly to DuckDB.
    """
    with patch(
        "opencode_monitor.api.client.get_api_client", return_value=mock_api_client
    ):
        with patch("opencode_monitor.api.get_api_client", return_value=mock_api_client):
            yield mock_api_client


@pytest.fixture
def patched_monitoring():
    """Patch monitoring fetch to avoid real network calls."""
    from opencode_monitor.core.models import State, Todos

    async def mock_fetch():
        return State(
            instances=[], todos=Todos(pending=0, in_progress=0), connected=False
        )

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

    The dashboard accesses data ONLY via the API client, which is mocked
    by patched_api_client. No DuckDB access occurs.

    Args:
        qtbot: pytest-qt's qtbot fixture for UI interaction
        patched_api_client: Mock API client fixture
        patched_monitoring: Mock monitoring fixture
        patched_security: Mock security fixture

    Yields:
        DashboardWindow: Fully mocked dashboard window
    """
    from opencode_monitor.dashboard.window import DashboardWindow

    window = DashboardWindow()
    qtbot.addWidget(window)

    # Stop timers BEFORE yield to avoid interference during tests
    # The 2000ms refresh timer could fire and overwrite manually emitted data
    if window._refresh_timer:
        window._refresh_timer.stop()
    if window._sync_checker:
        window._sync_checker.stop()

    window.show()
    qtbot.waitExposed(window)

    yield window

    # Cleanup
    window.close()


@pytest.fixture
def dashboard_window_hidden(
    qtbot, patched_api_client, patched_monitoring, patched_security
):
    """Create a dashboard window without showing it."""
    from opencode_monitor.dashboard.window import DashboardWindow

    window = DashboardWindow()
    qtbot.addWidget(window)

    # Stop timers BEFORE yield to avoid interference during tests
    # The 2000ms refresh timer could fire and overwrite manually emitted data
    if window._refresh_timer:
        window._refresh_timer.stop()
    if window._sync_checker:
        window._sync_checker.stop()

    yield window

    # Cleanup
    window.close()


@pytest.fixture
def dashboard_window_with_timers(
    qtbot, patched_api_client, patched_monitoring, patched_security
):
    """Create a dashboard window WITH timers running.

    Use this fixture ONLY for tests that specifically verify timer behavior.
    For all other tests, use dashboard_window which stops timers to avoid
    interference with manually emitted data.
    """
    from opencode_monitor.dashboard.window import DashboardWindow

    window = DashboardWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    yield window

    # Cleanup
    if window._refresh_timer:
        window._refresh_timer.stop()
    if window._sync_checker:
        window._sync_checker.stop()
    window.close()


@pytest.fixture
def dashboard_window_hidden_with_timers(
    qtbot, patched_api_client, patched_monitoring, patched_security
):
    """Create a hidden dashboard window WITH timers running.

    Use this fixture ONLY for tests that verify timer behavior on hidden windows.
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


@pytest.fixture
def tracing_with_data(dashboard_window, qtbot, click_nav):
    """Tracing section with realistic data loaded.

    Navigates to tracing section and emits realistic tracing data.
    Returns tuple of (tracing_section, dashboard_window) for flexibility.

    Usage:
        def test_with_tracing(tracing_with_data, select_first_session):
            tracing, dashboard = tracing_with_data
            root_item = select_first_session(tracing)
    """
    click_nav(dashboard_window, SECTION_TRACING)
    data = MockAPIResponses.realistic_tracing()
    dashboard_window._signals.tracing_updated.emit(data)
    qtbot.wait(SIGNAL_WAIT_MS)
    return dashboard_window._tracing, dashboard_window


@pytest.fixture(params=["basic", "empty", "complex", "partial", "extreme"])
def mock_api_client_variants(request):
    """Parametrized fixture for testing multiple data states.

    Useful for testing dashboard behavior with different data shapes:
    - basic: Single session, minimal data
    - empty: No data, tests empty states
    - complex: Multiple sessions with agents
    - partial: Missing/null fields
    - extreme: Very large values, stress testing
    """
    responses_map = {
        "basic": MockAPIResponses.basic(),
        "empty": MockAPIResponses.empty(),
        "complex": MockAPIResponses.complex(),
        "partial": MockAPIResponses.partial_data(),
        "extreme": MockAPIResponses.extreme_data(),
    }
    return MockAnalyticsAPIClient(responses_map[request.param])


# =============================================================================
# Markers
# =============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "slow: marks tests as slow running")
