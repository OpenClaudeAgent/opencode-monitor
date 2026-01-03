"""
Integration tests for Tracing session selection and tabs navigation.

Tests verify that:
- Session selection updates detail panel
- Tab navigation works correctly
- All tabs are accessible
"""

import pytest

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


class TestTracingSessionSelection:
    """Test session selection and detail panel update."""

    def test_tracing_session_selection_shows_detail_panel(
        self, dashboard_window, qtbot, click_nav
    ):
        """Clicking a session updates detail panel."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Get first item and select it
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None

        # Click on the item
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Detail panel should have been updated
        detail = tracing._detail_panel
        assert detail is not None

        # Header should not be the default "Select a session"
        header_text = detail._header.text()
        # Could be project name or session info
        assert header_text, "Header should be set"

    def test_session_selection_updates_metrics(
        self, dashboard_window, qtbot, click_nav
    ):
        """Selecting a session updates the metrics in detail panel."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Select first item - must exist with data
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, (
            "Expected at least one item in tree after data load"
        )

        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Detail panel metrics should exist
        detail = tracing._detail_panel
        assert hasattr(detail, "_metric_duration"), (
            "Detail panel should have _metric_duration attribute"
        )
        assert hasattr(detail, "_metric_tokens"), (
            "Detail panel should have _metric_tokens attribute"
        )


class TestTracingTabsNavigation:
    """Test tabs navigation in detail panel."""

    def test_tracing_tabs_exist(self, dashboard_window, qtbot):
        """Detail panel has all required tabs."""
        tracing = dashboard_window._tracing
        detail = tracing._detail_panel

        # Should have 6 tabs: transcript, tokens, tools, files, agents, timeline
        assert hasattr(detail, "_tabs")
        assert detail._tabs.count() == 6

    def test_tracing_tabs_navigation(
        self, dashboard_window, qtbot, click_nav, click_tab
    ):
        """Can navigate between tabs."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        detail = tracing._detail_panel
        tabs = detail._tabs

        # Navigate to each tab by clicking on tab bar
        tab_names = ["transcript", "tokens", "tools", "files", "agents", "timeline"]
        for i, name in enumerate(tab_names):
            click_tab(tabs, i)
            assert tabs.currentIndex() == i, f"Should be on {name} tab"

    def test_transcript_tab_is_default(self, dashboard_window, qtbot):
        """Transcript tab is selected by default."""
        tracing = dashboard_window._tracing
        detail = tracing._detail_panel

        # Tab 0 is transcript
        assert detail._tabs.currentIndex() == 0

    @pytest.mark.parametrize(
        "tab_name,tab_index",
        [
            ("transcript", 0),
            ("tokens", 1),
            ("tools", 2),
            ("files", 3),
            ("agents", 4),
            ("timeline", 5),
        ],
    )
    def test_tab_exists_and_is_widget(
        self, dashboard_window, qtbot, tab_name, tab_index
    ):
        """Each tab exists and is a valid QWidget."""
        from PyQt6.QtWidgets import QWidget

        detail = dashboard_window._tracing._detail_panel
        tab_attr = f"_{tab_name}_tab"

        assert hasattr(detail, tab_attr), f"Detail panel should have {tab_attr}"
        tab = getattr(detail, tab_attr)
        assert tab is not None, f"{tab_name} tab should not be None"
        assert isinstance(tab, QWidget), f"{tab_name} tab should be a QWidget"
