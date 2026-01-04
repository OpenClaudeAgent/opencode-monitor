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

        # Verify tree structure: 1 session with 2 delegations
        assert tracing._tree.topLevelItemCount() == 1, (
            "Should have exactly 1 root session"
        )

        root_item = tracing._tree.topLevelItem(0)
        assert root_item.text(0) == "🌳 my-project", (
            f"Root should be '🌳 my-project', got '{root_item.text(0)}'"
        )
        assert root_item.childCount() == 2, (
            f"Root should have 2 delegations, got {root_item.childCount()}"
        )

        # Verify delegation children with exact fixture values
        child_1 = root_item.child(0)
        child_2 = root_item.child(1)

        assert child_1.text(0) == "💬 user → executor", (
            f"First child mismatch: {child_1.text(0)}"
        )
        assert child_2.text(0) == "🔗 executor → tester", (
            f"Second child mismatch: {child_2.text(0)}"
        )

        # Verify children have no sub-children (leaf nodes)
        assert child_1.childCount() == 0, (
            f"First delegation should be leaf, got {child_1.childCount()} children"
        )
        assert child_2.childCount() == 0, (
            f"Second delegation should be leaf, got {child_2.childCount()} children"
        )

        # Select root session and verify detail panel updates
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Explore ALL 6 tabs and verify each activates
        tab_names = ["Overview", "Tokens", "Tools", "Files", "Agents", "Timeline"]
        for tab_index in range(6):
            click_tab(detail._tabs, tab_index)
            assert detail._tabs.currentIndex() == tab_index, (
                f"Tab {tab_names[tab_index]} (index {tab_index}) should be active"
            )
            qtbot.wait(50)

        # Navigate away and back
        click_nav(dashboard_window, SECTION_MONITORING)
        qtbot.wait(SIGNAL_WAIT_MS)
        click_nav(dashboard_window, SECTION_TRACING)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Verify we're back on tracing with data intact
        assert dashboard_window._pages.currentIndex() == SECTION_TRACING
        assert tracing._tree.topLevelItemCount() == 1, (
            "Tree should preserve data after navigation"
        )

    def test_navigation_preserves_section_state(
        self, dashboard_window, qtbot, click_nav
    ):
        """Navigation away and back preserves section data."""
        # Setup tracing with data first
        click_nav(dashboard_window, SECTION_TRACING)
        tracing_data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(tracing_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        tracing = dashboard_window._tracing
        initial_tree_count = tracing._tree.topLevelItemCount()
        assert initial_tree_count == 1, "Tracing should have 1 root session"

        # Setup monitoring with data
        click_nav(dashboard_window, SECTION_MONITORING)
        monitoring_data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(monitoring_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Verify monitoring data is there
        metrics = dashboard_window._monitoring._metrics
        initial_agents = metrics._cards["agents"]._value_label.text()
        assert initial_agents == "3", (
            f"Expected 3 agents initially, got {initial_agents}"
        )

        # Navigate to Analytics then back to Monitoring
        click_nav(dashboard_window, SECTION_ANALYTICS)
        qtbot.wait(SIGNAL_WAIT_MS)
        click_nav(dashboard_window, SECTION_MONITORING)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Monitoring data should persist
        final_agents = metrics._cards["agents"]._value_label.text()
        assert final_agents == "3", (
            f"Monitoring data should persist: expected '3', got {final_agents}"
        )

        # Navigate back to Tracing - verify its data persisted too
        click_nav(dashboard_window, SECTION_TRACING)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert tracing._tree.topLevelItemCount() == 1, (
            "Tracing tree should persist after navigation"
        )
        root_item = tracing._tree.topLevelItem(0)
        assert root_item.text(0) == "🌳 my-project", (
            f"Tracing root text should persist, got '{root_item.text(0)}'"
        )

        # Verify complete tree structure persists (children intact)
        assert root_item.childCount() == 2, (
            f"Root should still have 2 delegations, got {root_item.childCount()}"
        )
        assert root_item.child(0).text(0) == "💬 user → executor", (
            f"First delegation should persist: {root_item.child(0).text(0)}"
        )
        assert root_item.child(1).text(0) == "🔗 executor → tester", (
            f"Second delegation should persist: {root_item.child(1).text(0)}"
        )
