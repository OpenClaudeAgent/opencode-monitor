"""
Integration tests for dashboard robustness.

Tests verify that the dashboard:
- Handles rapid navigation without crashes
- Gracefully manages null/missing data fields
- Handles extreme values without freezing
- Correctly displays unicode/emoji content
- Maintains independent state across parallel tests
"""

import pytest

from .conftest import (
    SIGNAL_WAIT_MS,
    SECTION_MONITORING,
    SECTION_SECURITY,
    SECTION_ANALYTICS,
    SECTION_TRACING,
)
from .fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


# =============================================================================
# Data During Navigation Tests
# =============================================================================


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


# =============================================================================
# Null/Missing Data Tests
# =============================================================================


class TestRobustnessNullData:
    """Test dashboard handles null/missing fields gracefully."""

    def test_null_data_fields_no_crash(self, dashboard_window, qtbot):
        """Dashboard handles null/missing fields gracefully."""
        # Monitoring with null fields
        data_with_nulls = {
            "instances": None,
            "agents": 0,
            "busy": None,
            "waiting": 0,
            "idle": None,
            "todos": None,
            "agents_data": [
                {
                    "agent_id": "agent-x",
                    "title": None,
                    "dir": None,
                    "status": "idle",
                    "tools": None,
                    "todos_total": None,
                }
            ],
            "tools_data": None,
            "waiting_data": None,
        }

        # Should not crash
        dashboard_window._signals.monitoring_updated.emit(data_with_nulls)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert dashboard_window.isVisible()

    def test_partial_data_no_crash(self, dashboard_window, qtbot, click_nav):
        """Dashboard handles partial data (from MockAPIResponses)."""
        data = MockAPIResponses.partial_data()

        # Navigate to tracing and emit partial data
        click_nav(dashboard_window, SECTION_TRACING)
        dashboard_window._signals.tracing_updated.emit(
            {
                "traces": [],
                "sessions": data.get("sessions", []),
                "session_hierarchy": [],
                "total_traces": 0,
                "unique_agents": 0,
                "total_duration_ms": 0,
            }
        )
        qtbot.wait(SIGNAL_WAIT_MS)

        assert dashboard_window.isVisible()

    def test_empty_lists_vs_none(self, dashboard_window, qtbot):
        """Dashboard distinguishes between empty lists and None."""
        # Empty lists = no data, valid state
        empty_list_data = {
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

        dashboard_window._signals.monitoring_updated.emit(empty_list_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        monitoring = dashboard_window._monitoring
        # Empty state should show for agents
        assert (
            monitoring._agents_empty.isVisible()
            or not monitoring._agents_table.isVisible()
        )


# =============================================================================
# Extreme Values Tests
# =============================================================================


class TestRobustnessExtremeValues:
    """Test dashboard handles extreme values without freezing."""

    def test_extreme_values_no_freeze(self, dashboard_window, qtbot):
        """Dashboard handles very large numbers without freezing."""
        data = MockAPIResponses.realistic_monitoring()
        data["agents"] = 999_999
        data["todos"] = 999_999_999

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Should display (possibly formatted as "999K" or "999M")
        metrics = dashboard_window._monitoring._metrics
        agents_text = metrics._cards["agents"]._value_label.text()
        assert agents_text  # Not empty

    def test_extreme_data_fixture(self, dashboard_window, qtbot, click_nav):
        """Dashboard handles extreme_data fixture without crash."""
        data = MockAPIResponses.extreme_data()

        # Navigate to tracing
        click_nav(dashboard_window, SECTION_TRACING)

        tracing_data = {
            "traces": data.get("traces", [])[:10],  # Limit for test speed
            "sessions": data.get("sessions", []),
            "session_hierarchy": [],
            "total_traces": len(data.get("traces", [])),
            "unique_agents": 4,
            "total_duration_ms": 1_000_000,
        }

        dashboard_window._signals.tracing_updated.emit(tracing_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert dashboard_window.isVisible()

    def test_very_long_strings(self, dashboard_window, qtbot):
        """Dashboard handles very long strings without crash."""
        data = MockAPIResponses.realistic_monitoring()
        # Agent with very long title
        data["agents_data"][0]["title"] = "A" * 1000

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Table should have exactly 3 agents from mock data (possibly with truncated title)
        table = dashboard_window._monitoring._agents_table
        assert table.rowCount() == 3, (
            f"Expected 3 agents from mock data, got {table.rowCount()}"
        )


# =============================================================================
# Unicode/Emoji Tests
# =============================================================================


class TestRobustnessUnicode:
    """Test dashboard handles unicode/emoji correctly."""

    def test_unicode_in_agent_title(self, dashboard_window, qtbot):
        """Dashboard handles unicode in agent titles."""
        data = MockAPIResponses.realistic_monitoring()
        data["agents_data"][0]["title"] = "🚀 Deploy émojis & spëcial çhars"

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        table = dashboard_window._monitoring._agents_table
        title = table.item(0, 0).text()
        # Should contain either the emoji or the text
        assert "🚀" in title or "Deploy" in title

    def test_unicode_in_directory_path(self, dashboard_window, qtbot):
        """Dashboard handles unicode in directory paths."""
        data = MockAPIResponses.realistic_monitoring()
        data["agents_data"][0]["dir"] = "/home/用户/项目"

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        table = dashboard_window._monitoring._agents_table
        # Should not crash, path should be displayed
        assert table.rowCount() >= 1

    def test_unicode_in_question_text(self, dashboard_window, qtbot):
        """Dashboard handles unicode in waiting questions."""
        data = MockAPIResponses.realistic_monitoring()
        data["waiting_data"][0]["question"] = "¿Está seguro? 日本語テスト 🎉"

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        table = dashboard_window._monitoring._waiting_table
        # Should not crash
        assert table.rowCount() >= 1


# =============================================================================
# Parallel Safety Tests
# =============================================================================


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


# =============================================================================
# Monitoring State Variants Tests
# =============================================================================


class TestMonitoringStateVariants:
    """Test monitoring section with different data states."""

    def test_all_idle_state(self, dashboard_window, qtbot):
        """All agents idle displays correctly."""
        data = MockAPIResponses.realistic_monitoring_all_idle()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        monitoring = dashboard_window._monitoring

        # Metrics should show 0 busy, 4 idle
        assert monitoring._metrics._cards["busy"]._value_label.text() == "0"
        assert monitoring._metrics._cards["idle"]._value_label.text() == "4"

        # All agents in table should have IDLE status
        table = monitoring._agents_table
        for row in range(table.rowCount()):
            badge = table.cellWidget(row, 2)
            if badge:
                assert "IDLE" in badge.text()

    def test_all_waiting_state(self, dashboard_window, qtbot):
        """All agents waiting displays correctly."""
        data = MockAPIResponses.realistic_monitoring_all_waiting()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        monitoring = dashboard_window._monitoring

        # Metrics should show 3 waiting
        assert monitoring._metrics._cards["waiting"]._value_label.text() == "3"

        # Waiting table should have 3 rows
        waiting_table = monitoring._waiting_table
        assert waiting_table.rowCount() == 3

    def test_error_state_agents(self, dashboard_window, qtbot):
        """Agents in error state are handled gracefully."""
        data = MockAPIResponses.realistic_monitoring_error()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Should not crash
        assert dashboard_window.isVisible()

        # Table should still display
        table = dashboard_window._monitoring._agents_table
        assert table.rowCount() >= 1


# =============================================================================
# API Error Handling Tests
# =============================================================================


class TestAPIErrorHandling:
    """Test dashboard handles API errors gracefully."""

    def test_api_unavailable_shows_graceful_state(
        self, dashboard_window, qtbot, click_nav
    ):
        """Dashboard handles API unavailable without crash."""
        click_nav(dashboard_window, SECTION_MONITORING)

        # Emit empty data (simulates API error/unavailable)
        # Note: Signal is typed dict, so we use empty dict instead of None
        dashboard_window._signals.monitoring_updated.emit({})
        qtbot.wait(SIGNAL_WAIT_MS)

        # Should not crash, window still visible
        assert dashboard_window.isVisible(), "Window should remain visible on API error"

    def test_malformed_data_no_crash(self, dashboard_window, qtbot, click_nav):
        """Dashboard handles malformed data without crash."""
        click_nav(dashboard_window, SECTION_TRACING)

        malformed = {
            "sessions": [{"id": 123}],  # Wrong type, missing fields
            "traces": None,
            "session_hierarchy": [],
        }
        dashboard_window._signals.tracing_updated.emit(malformed)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert dashboard_window.isVisible()

    def test_signal_after_close_no_crash(self, dashboard_window, qtbot):
        """Signal emitted after close() doesn't crash."""
        dashboard_window.close()
        qtbot.wait(100)

        # Should not raise exception
        try:
            dashboard_window._signals.monitoring_updated.emit({})
            dashboard_window._signals.analytics_updated.emit({})
            dashboard_window._signals.tracing_updated.emit({})
        except Exception as e:
            pytest.fail(f"Signal after close raised: {e}")


# =============================================================================
# Complex Sequences Tests
# =============================================================================


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
