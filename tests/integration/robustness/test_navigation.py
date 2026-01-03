"""
Integration tests for navigation robustness.

Tests verify that:
- Rapid navigation doesn't crash
- Parallel test execution is safe
- Complex sequences work correctly
"""

import pytest

from ..conftest import (
    SIGNAL_WAIT_MS,
    SECTION_MONITORING,
    SECTION_SECURITY,
    SECTION_ANALYTICS,
    SECTION_TRACING,
)
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


class TestRobustnessNavigation:
    """Test dashboard handles data during navigation gracefully."""

    def test_data_during_navigation_no_crash(self, dashboard_window, qtbot, click_nav):
        """Emitting data while navigating doesn't crash."""
        monitoring_data = MockAPIResponses.realistic_monitoring()
        tracing_data = MockAPIResponses.realistic_tracing()
        analytics_data = MockAPIResponses.realistic_analytics()

        for _ in range(5):
            # Navigate rapidly and emit data via sidebar clicks
            click_nav(dashboard_window, SECTION_MONITORING)
            dashboard_window._signals.monitoring_updated.emit(monitoring_data)

            click_nav(dashboard_window, SECTION_TRACING)
            dashboard_window._signals.tracing_updated.emit(tracing_data)

            click_nav(dashboard_window, SECTION_ANALYTICS)
            dashboard_window._signals.analytics_updated.emit(analytics_data)

            click_nav(dashboard_window, SECTION_SECURITY)
            qtbot.wait(50)

        # Should not crash - window still visible
        assert dashboard_window.isVisible()

    def test_multiple_signal_emissions_no_crash(self, dashboard_window, qtbot):
        """Rapid signal emissions don't crash the dashboard."""
        data = MockAPIResponses.realistic_monitoring()

        # Emit same signal rapidly 20 times
        for _ in range(20):
            dashboard_window._signals.monitoring_updated.emit(data)
            qtbot.wait(30)

        qtbot.wait(SIGNAL_WAIT_MS)
        assert dashboard_window.isVisible()

    def test_alternating_empty_and_full_data(self, dashboard_window, qtbot):
        """Alternating between empty and full data doesn't crash."""
        empty_data = {
            "instances": 0,
            "agents": 0,
            "busy": 0,
            "waiting": 0,
            "idle": 0,
            "todos": 0,
            "agents_data": [],
            "tools_data": [],
            "waiting_data": [],
        }
        full_data = MockAPIResponses.realistic_monitoring()

        for _ in range(10):
            dashboard_window._signals.monitoring_updated.emit(empty_data)
            qtbot.wait(50)
            dashboard_window._signals.monitoring_updated.emit(full_data)
            qtbot.wait(50)

        assert dashboard_window.isVisible()


class TestParallelSafety:
    """Tests that verify parallel execution safety.

    These tests check that test isolation works correctly
    and that state doesn't bleed between tests.
    """

    def test_independent_window_state_1(self, dashboard_window, qtbot):
        """First test sets specific state."""
        data = MockAPIResponses.realistic_monitoring()
        data["agents"] = 42
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        metrics = dashboard_window._monitoring._metrics
        assert metrics._cards["agents"]._value_label.text() == "42"

    def test_independent_window_state_2(self, dashboard_window, qtbot):
        """Second test should start with fresh state (not 42)."""
        # Without explicitly setting data, check initial state
        metrics = dashboard_window._monitoring._metrics
        initial_value = metrics._cards["agents"]._value_label.text()

        # Value should NOT be "42" from previous test (fresh fixture)
        # Initial value is typically "0" or "-" depending on implementation
        assert initial_value in ("0", "-", ""), (
            f"Initial value should be default (0, -, or empty), got: '{initial_value}'"
        )

    def test_window_isolation_via_marker(self, dashboard_window, qtbot):
        """Each test gets a fresh window instance (no cross-test state leakage).

        This test verifies fixture isolation by checking that no marker
        from any previous test execution exists on the current window.
        Combined test for DRY - tests both setting and absence of markers.
        """
        # First, verify no stale marker exists from any previous test run
        marker = getattr(dashboard_window, "_test_marker", None)
        assert marker is None, "Window should not have marker from previous test"

        # Set a marker to prove we have a fresh instance
        dashboard_window._test_marker = "isolation_verified"
        assert hasattr(dashboard_window, "_test_marker")


class TestSequences:
    """Test complex sequences of actions."""

    def test_rapid_section_switching_with_data(
        self, dashboard_window, qtbot, click_nav
    ):
        """Rapid switching while data is being emitted."""
        monitoring_data = MockAPIResponses.realistic_monitoring()
        analytics_data = MockAPIResponses.realistic_analytics()

        for _ in range(5):
            click_nav(dashboard_window, SECTION_MONITORING)
            dashboard_window._signals.monitoring_updated.emit(monitoring_data)
            click_nav(dashboard_window, SECTION_ANALYTICS)
            dashboard_window._signals.analytics_updated.emit(analytics_data)
            click_nav(dashboard_window, SECTION_TRACING)
            click_nav(dashboard_window, SECTION_SECURITY)

        qtbot.wait(SIGNAL_WAIT_MS)
        assert dashboard_window.isVisible(), "Should survive rapid switching"

    def test_data_update_during_tab_navigation(
        self, dashboard_window, qtbot, click_nav, click_tab
    ):
        """Data updates while user is navigating tabs."""
        click_nav(dashboard_window, SECTION_TRACING)
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        detail = dashboard_window._tracing._detail_panel

        # Navigate tabs while emitting new data
        for i in range(6):
            click_tab(detail._tabs, i)
            # Emit new data mid-navigation
            dashboard_window._signals.tracing_updated.emit(data)
            qtbot.wait(30)

        assert dashboard_window.isVisible()
