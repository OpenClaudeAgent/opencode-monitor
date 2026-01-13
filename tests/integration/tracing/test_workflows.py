"""
Integration tests for Tracing user workflows.

Tests verify that:
- Complete session exploration works end-to-end
- Navigation preserves section state
"""

import pytest
from PyQt6.QtCore import Qt

from ..conftest import SECTION_TRACING, SECTION_MONITORING, SECTION_ANALYTICS
from ..fixtures import MockAPIResponses, process_qt_events

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group(name="qt_tracing"),  # Force same worker for Qt UI tests
]


class TestUserWorkflows:
    """Test realistic user workflows end-to-end."""

    def test_complete_session_exploration(
        self, dashboard_window, qtbot, click_nav, click_tab
    ):
        """User explores a session through all tabs."""
        click_nav(dashboard_window, SECTION_TRACING)

        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)

        tracing = dashboard_window._tracing
        detail = tracing._detail_panel
        model = tracing._model

        qtbot.waitUntil(lambda: model.rowCount() > 0, timeout=3000)

        root_index = model.index(0, 0)
        root_text = model.data(root_index, Qt.ItemDataRole.DisplayRole)
        assert root_text == "🌳 my-project: Implement feature X"

        expected_child_count = 2
        root_has_all_children = (
            lambda: model.rowCount(root_index) == expected_child_count
        )
        qtbot.waitUntil(root_has_all_children, timeout=3000)

        child_1_index = model.index(0, 0, root_index)
        child_2_index = model.index(1, 0, root_index)

        # Labels format: "└─ parent → child" for delegations
        child_1_text = model.data(child_1_index, Qt.ItemDataRole.DisplayRole)
        child_2_text = model.data(child_2_index, Qt.ItemDataRole.DisplayRole)
        assert "executor" in child_1_text, (
            f"Expected 'executor' in child 1, got: {child_1_text}"
        )
        assert "tester" in child_2_text, (
            f"Expected 'tester' in child 2, got: {child_2_text}"
        )

        tracing._tree.setCurrentIndex(root_index)
        tracing._on_index_clicked(root_index)

        click_tab(detail._tabs, 0)
        assert detail._tabs.currentIndex() == 0
        click_tab(detail._tabs, 5)
        assert detail._tabs.currentIndex() == 5

        click_nav(dashboard_window, SECTION_MONITORING)
        click_nav(dashboard_window, SECTION_TRACING)

        assert dashboard_window._pages.currentIndex() == SECTION_TRACING
        assert model.rowCount() == 1

    def test_navigation_preserves_section_state(
        self, dashboard_window, qtbot, click_nav
    ):
        """Navigation away and back preserves section data."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing_data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(tracing_data)

        tracing = dashboard_window._tracing
        model = tracing._model
        qtbot.waitUntil(lambda: model.rowCount() > 0, timeout=3000)

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

        assert model.rowCount() == 1
        root_index = model.index(0, 0)
        root_text = model.data(root_index, Qt.ItemDataRole.DisplayRole)
        assert root_text.startswith("🌳 my-project")
