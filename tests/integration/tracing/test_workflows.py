"""
Integration tests for Tracing user workflows.

Tests verify that:
- Complete session exploration works end-to-end
- Navigation preserves section state
"""

import pytest

from ..conftest import SECTION_TRACING, SECTION_MONITORING, SECTION_ANALYTICS
from ..fixtures import MockAPIResponses, process_qt_events

pytestmark = pytest.mark.integration


class TestUserWorkflows:
    """Test realistic user workflows end-to-end."""

    def test_complete_session_exploration(
        self, dashboard_window, qtbot, click_nav, click_tab
    ):
        """User explores a session through all tabs."""
        click_nav(dashboard_window, SECTION_TRACING)

        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        process_qt_events()

        tracing = dashboard_window._tracing
        detail = tracing._detail_panel

        assert tracing._tree.topLevelItemCount() == 1

        root_item = tracing._tree.topLevelItem(0)
        assert root_item.text(0) == "🌳 my-project: Implement feature X"

        expected_child_count = 2
        root_has_all_children = lambda: root_item.childCount() == expected_child_count
        qtbot.waitUntil(root_has_all_children, timeout=3000)

        child_1 = root_item.child(0)
        child_2 = root_item.child(1)

        assert child_1.text(0) == "💬 user → executor"
        assert child_2.text(0) == "🔗 executor → tester"

        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)

        click_tab(detail._tabs, 0)
        assert detail._tabs.currentIndex() == 0
        click_tab(detail._tabs, 5)
        assert detail._tabs.currentIndex() == 5

        click_nav(dashboard_window, SECTION_MONITORING)
        click_nav(dashboard_window, SECTION_TRACING)

        assert dashboard_window._pages.currentIndex() == SECTION_TRACING
        assert tracing._tree.topLevelItemCount() == 1

    def test_navigation_preserves_section_state(
        self, dashboard_window, qtbot, click_nav
    ):
        """Navigation away and back preserves section data."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing_data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(tracing_data)
        process_qt_events()

        tracing = dashboard_window._tracing
        assert tracing._tree.topLevelItemCount() == 1

        click_nav(dashboard_window, SECTION_MONITORING)
        monitoring_data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(monitoring_data)
        process_qt_events()

        metric_cards = dashboard_window._monitoring._metric_cards
        initial_agents = metric_cards["agents"]._value_label.text()
        assert initial_agents == "3"

        click_nav(dashboard_window, SECTION_ANALYTICS)
        click_nav(dashboard_window, SECTION_MONITORING)

        final_agents = metric_cards["agents"]._value_label.text()
        assert final_agents == "3"

        click_nav(dashboard_window, SECTION_TRACING)

        assert tracing._tree.topLevelItemCount() == 1
        root_item = tracing._tree.topLevelItem(0)
        assert root_item.text(0).startswith("🌳 my-project")
