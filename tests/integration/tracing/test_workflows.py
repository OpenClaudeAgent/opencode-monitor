"""
Integration tests for cross-section data persistence.

Tests verify that navigation between sections preserves data state.
"""

import pytest

from ..conftest import (
    SIGNAL_WAIT_MS,
    SECTION_TRACING,
    SECTION_MONITORING,
    SECTION_ANALYTICS,
)
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


class TestCrossSectionPersistence:
    """Test that data persists when navigating between sections."""

    def test_data_persists_after_navigation_cycle(
        self, dashboard_window, qtbot, click_nav
    ):
        """Data persists after navigation cycle: Tracing -> Monitoring -> Analytics -> Monitoring -> Tracing."""
        # Setup tracing with data
        click_nav(dashboard_window, SECTION_TRACING)
        tracing_data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(tracing_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        tracing = dashboard_window._tracing
        assert tracing._tree.topLevelItemCount() == 1

        # Setup monitoring with data
        click_nav(dashboard_window, SECTION_MONITORING)
        monitoring_data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(monitoring_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        metrics = dashboard_window._monitoring._metrics
        assert metrics._cards["agents"]._value_label.text() == "3"

        # Navigation cycle: Analytics -> Monitoring -> Tracing
        click_nav(dashboard_window, SECTION_ANALYTICS)
        qtbot.wait(SIGNAL_WAIT_MS)
        click_nav(dashboard_window, SECTION_MONITORING)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Monitoring data should persist
        assert metrics._cards["agents"]._value_label.text() == "3"

        # Navigate back to Tracing
        click_nav(dashboard_window, SECTION_TRACING)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Tracing data should persist
        assert tracing._tree.topLevelItemCount() == 1
        root_item = tracing._tree.topLevelItem(0)
        assert root_item.text(0) == "🌳 my-project"
