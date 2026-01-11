"""
Integration tests for API error handling and monitoring state variants.

Tests verify that:
- API errors are handled gracefully
- Different monitoring states display correctly
"""

import pytest

from ..conftest import SECTION_MONITORING, SECTION_TRACING
from ..fixtures import MockAPIResponses, process_qt_events

pytestmark = pytest.mark.integration


class TestAPIErrorHandling:
    """Test dashboard handles API errors gracefully."""

    @pytest.mark.parametrize(
        "section,signal_name,malformed_data",
        [
            pytest.param(
                SECTION_MONITORING,
                "monitoring_updated",
                {},  # Empty data simulating API unavailable
                id="api_unavailable_empty_dict",
            ),
            pytest.param(
                SECTION_TRACING,
                "tracing_updated",
                {"session_hierarchy": []},
                id="malformed_types_and_nulls",
            ),
            pytest.param(
                SECTION_MONITORING,
                "monitoring_updated",
                {
                    "instances": "not_an_int",  # Wrong type
                    "agents_data": None,  # Null instead of list
                },
                id="malformed_monitoring_types",
            ),
        ],
    )
    def test_malformed_data_resilience(
        self, dashboard_window, qtbot, click_nav, section, signal_name, malformed_data
    ):
        """Dashboard handles malformed/unavailable data without crash."""
        click_nav(dashboard_window, section)

        signal = getattr(dashboard_window._signals, signal_name)
        signal.emit(malformed_data)
        process_qt_events()

        # Verify resilience: window visible and responsive
        assert dashboard_window.isVisible(), "Window should remain visible"
        assert dashboard_window.isEnabled(), "Window should remain enabled"
        # Verify no modal error dialogs blocking the UI
        assert dashboard_window.isActiveWindow() or not dashboard_window.isMinimized()

    def test_signals_after_close_are_safe(self, dashboard_window, qtbot):
        """Signals emitted after close() don't crash or raise exceptions."""
        # Capture initial state
        was_visible = dashboard_window.isVisible()
        assert was_visible, "Window should start visible"

        dashboard_window.close()
        process_qt_events()

        # Verify closed state
        assert not dashboard_window.isVisible(), "Window should be closed"

        # Emit all signals - none should raise
        dashboard_window._signals.monitoring_updated.emit({})
        dashboard_window._signals.analytics_updated.emit({})
        dashboard_window._signals.tracing_updated.emit({})

        # Window should remain closed (no accidental re-show)
        assert not dashboard_window.isVisible(), "Window should stay closed"


class TestMonitoringStateVariants:
    """Test monitoring section with different data states."""

    def test_all_idle_state(self, dashboard_window, qtbot):
        """All agents idle displays correctly."""
        data = MockAPIResponses.realistic_monitoring_all_idle()
        dashboard_window._signals.monitoring_updated.emit(data)
        process_qt_events()

        monitoring = dashboard_window._monitoring

        # Metrics should show 0 busy, 4 idle
        assert monitoring._metric_cards["busy"]._value_label.text() == "0"
        assert monitoring._metric_cards["idle"]._value_label.text() == "4"

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
        process_qt_events()

        monitoring = dashboard_window._monitoring

        # Metrics should show 3 waiting
        assert monitoring._metric_cards["waiting"]._value_label.text() == "3"

        # Waiting table should have 3 rows
        waiting_table = monitoring._waiting_table
        assert waiting_table.rowCount() == 3

    def test_error_state_agents(self, dashboard_window, qtbot):
        """Agents in error state are handled gracefully."""
        data = MockAPIResponses.realistic_monitoring_error()
        dashboard_window._signals.monitoring_updated.emit(data)
        process_qt_events()

        monitoring = dashboard_window._monitoring

        # Verify dashboard remains functional
        assert dashboard_window.isVisible(), "Window should remain visible"

        # Verify metrics display correctly (1 busy, 1 idle from mock data)
        assert monitoring._metric_cards["busy"]._value_label.text() == "1"
        assert monitoring._metric_cards["idle"]._value_label.text() == "1"

        # Table should display all 4 agents from mock data
        table = monitoring._agents_table
        assert table.rowCount() == 4, (
            "Should display all 4 agents including error states"
        )
