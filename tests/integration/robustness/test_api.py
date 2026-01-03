"""
Integration tests for API error handling and monitoring state variants.

Tests verify that:
- API errors are handled gracefully
- Different monitoring states display correctly
"""

import pytest

from ..conftest import (
    SIGNAL_WAIT_MS,
    SECTION_MONITORING,
    SECTION_TRACING,
)
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


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
