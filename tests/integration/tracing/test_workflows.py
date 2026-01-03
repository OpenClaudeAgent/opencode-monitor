"""
Integration tests for Tracing user workflows.

Tests verify that:
- Complete session exploration works end-to-end
- Navigation preserves section state
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


class TestUserWorkflows:
    """Test realistic user workflows end-to-end."""

    def test_complete_session_exploration(
        self, dashboard_window, qtbot, click_nav, click_tab
    ):
        """User explores a session through all tabs."""
        # Navigate to Tracing
        click_nav(dashboard_window, SECTION_TRACING)

        # Load data
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        tracing = dashboard_window._tracing
        detail = tracing._detail_panel

        # Select first session
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, "Should have sessions"
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Explore ALL 6 tabs
        for tab_index in range(6):
            click_tab(detail._tabs, tab_index)
            assert detail._tabs.currentIndex() == tab_index, (
                f"Should be on tab {tab_index}"
            )
            qtbot.wait(50)

        # Navigate away and back
        click_nav(dashboard_window, SECTION_MONITORING)
        qtbot.wait(SIGNAL_WAIT_MS)
        click_nav(dashboard_window, SECTION_TRACING)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Verify we're back on tracing
        assert dashboard_window._pages.currentIndex() == SECTION_TRACING

    def test_navigation_preserves_section_state(
        self, dashboard_window, qtbot, click_nav
    ):
        """Navigation away and back preserves section data."""
        # Setup monitoring with data
        click_nav(dashboard_window, SECTION_MONITORING)
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Verify data is there
        metrics = dashboard_window._monitoring._metrics
        initial_agents = metrics._cards["agents"]._value_label.text()
        assert initial_agents == "3", (
            f"Expected 3 agents initially, got {initial_agents}"
        )

        # Navigate to Analytics then back
        click_nav(dashboard_window, SECTION_ANALYTICS)
        qtbot.wait(SIGNAL_WAIT_MS)
        click_nav(dashboard_window, SECTION_MONITORING)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Data should persist
        final_agents = metrics._cards["agents"]._value_label.text()
        assert final_agents == initial_agents, (
            f"Data should persist: expected {initial_agents}, got {final_agents}"
        )
