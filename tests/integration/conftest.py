"""
Pytest configuration and fixtures for integration tests.

Provides:
- Mock API client that replaces the real HTTP client
- QApplication fixture for PyQt tests
- Dashboard fixtures with mocked dependencies
- Helper utilities for UI interaction testing

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
def dashboard_window_hidden(
    qtbot, patched_api_client, patched_monitoring, patched_security
):
    """Create a dashboard window without showing it."""
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
def select_first_session(qtbot):
    """Helper to select first session in tracing tree.

    Eliminates duplication of session selection pattern across tests.
    Returns the selected root item for further assertions.

    Usage:
        def test_with_session(tracing_with_data, select_first_session):
            tracing, _ = tracing_with_data
            root_item = select_first_session(tracing)
            # Now session is selected, detail panel is updated
    """

    def _select(tracing):
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, "Expected at least one session in tree"
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)
        return root_item

    return _select


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


@pytest.fixture
def assert_table_content():
    """Helper fixture for table content assertions.

    Provides a function to assert table cell content with options
    for contains/exact matching and case sensitivity.

    Usage:
        def test_table(assert_table_content, dashboard_window):
            table = dashboard_window._monitoring._agents_table
            assert_table_content(table, 0, 0, "Agent Name")
            assert_table_content(table, 0, 1, "path", contains=True)
    """

    def _assert(
        table,
        row: int,
        col: int,
        expected: str,
        contains: bool = False,
        ignore_case: bool = False,
    ):
        item = table.item(row, col)
        assert item is not None, f"No item at ({row}, {col})"

        actual = item.text()
        expected_cmp = expected
        actual_cmp = actual

        if ignore_case:
            actual_cmp = actual.lower()
            expected_cmp = expected.lower()

        if contains:
            assert expected_cmp in actual_cmp, (
                f"Expected '{expected}' in '{actual}' at ({row}, {col})"
            )
        else:
            assert actual_cmp == expected_cmp, (
                f"Expected '{expected}', got '{actual}' at ({row}, {col})"
            )

    return _assert


@pytest.fixture
def assert_widget_content():
    """Helper fixture for cell widget assertions.

    Similar to assert_table_content but for cell widgets (like badges).
    """

    def _assert(
        table,
        row: int,
        col: int,
        expected: str,
        contains: bool = True,
        ignore_case: bool = True,
    ):
        widget = table.cellWidget(row, col)
        assert widget is not None, f"No widget at ({row}, {col})"

        actual = widget.text()
        expected_cmp = expected
        actual_cmp = actual

        if ignore_case:
            actual_cmp = actual.lower()
            expected_cmp = expected.lower()

        if contains:
            assert expected_cmp in actual_cmp, (
                f"Expected '{expected}' in widget text '{actual}' at ({row}, {col})"
            )
        else:
            assert actual_cmp == expected_cmp, (
                f"Expected '{expected}', got '{actual}' in widget at ({row}, {col})"
            )

    return _assert


# =============================================================================
# Constants
# =============================================================================

SIGNAL_WAIT_MS = (
    200  # Standard wait time for signal processing (increased for CI stability)
)

# Section indices (order in sidebar and pages)
SECTION_MONITORING = 0
SECTION_SECURITY = 1
SECTION_ANALYTICS = 2
SECTION_TRACING = 3


@pytest.fixture
def wait_for_signal():
    """Fixture to wait for Qt signals with timeout."""

    def waiter(qtbot, signal, timeout: int = 1000) -> bool:
        try:
            with qtbot.waitSignal(signal, timeout=timeout):
                return True
        except TimeoutError:
            # Signal was not emitted within timeout
            return False
        # Let other exceptions propagate for debugging

    return waiter


@pytest.fixture
def click_nav(qtbot):
    """Helper to click sidebar navigation buttons.

    This simulates real user interaction by clicking on sidebar nav items
    instead of directly manipulating internal state.

    Usage:
        click_nav(dashboard_window, SECTION_MONITORING)
        click_nav(dashboard_window, SECTION_TRACING)
    """
    from PyQt6.QtCore import Qt

    def _click(dashboard_window, section_index: int) -> None:
        """Click on sidebar nav item to navigate to section.

        Args:
            dashboard_window: The dashboard window
            section_index: 0=Monitoring, 1=Security, 2=Analytics, 3=Tracing
        """
        sidebar = dashboard_window._sidebar
        nav_items = sidebar._nav_items
        if 0 <= section_index < len(nav_items):
            qtbot.mouseClick(nav_items[section_index], Qt.MouseButton.LeftButton)
            qtbot.wait(SIGNAL_WAIT_MS)

    return _click


@pytest.fixture
def click_tab(qtbot):
    """Helper to click on QTabWidget tabs.

    This simulates real user interaction by clicking on tab bar
    instead of directly calling setCurrentIndex().

    Usage:
        click_tab(detail._tabs, 0)  # Click first tab
        click_tab(detail._tabs, 1)  # Click second tab
    """
    from PyQt6.QtCore import Qt

    def _click(tab_widget, tab_index: int) -> None:
        """Click on a tab by index.

        Args:
            tab_widget: QTabWidget instance
            tab_index: Index of the tab to click
        """
        tab_bar = tab_widget.tabBar()
        tab_rect = tab_bar.tabRect(tab_index)
        qtbot.mouseClick(tab_bar, Qt.MouseButton.LeftButton, pos=tab_rect.center())
        qtbot.wait(SIGNAL_WAIT_MS)

    return _click


# =============================================================================
# Markers
# =============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "slow: marks tests as slow running")
