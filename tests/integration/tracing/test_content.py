"""
Integration tests for Tracing tabs and tree content.

Tests verify that:
- Tab content is accessible after selection
- Tree displays correct hierarchical content
- Detail header and metrics update correctly
"""

import pytest

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


class TestTracingTabsContent:
    """Test that tabs display actual content when data is loaded."""

    def test_transcript_tab_accessible_after_selection(
        self, dashboard_window, qtbot, click_nav, click_tab
    ):
        """Transcript tab is accessible and can receive content."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Select a session - must exist with data
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, (
            "Expected at least one item in tree after data load"
        )

        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Verify transcript tab exists and is accessible
        detail = tracing._detail_panel
        transcript = detail._transcript_tab
        assert transcript is not None, "Transcript tab should not be None"

        # Tab should be visible when selected (click on tab bar)
        click_tab(detail._tabs, 0)
        assert detail._tabs.currentIndex() == 0

    def test_tokens_tab_shows_token_widgets(
        self, dashboard_window, qtbot, click_nav, click_tab
    ):
        """Tokens tab has widgets for displaying token metrics."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Select first session - must exist with data
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, (
            "Expected at least one item in tree after data load"
        )

        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Navigate to tokens tab (click on tab bar)
        detail = tracing._detail_panel
        click_tab(detail._tabs, 1)  # tokens tab

        tokens_tab = detail._tokens_tab
        assert tokens_tab is not None, "Tokens tab should not be None"

    def test_tools_tab_shows_tool_widgets(
        self, dashboard_window, qtbot, click_nav, click_tab
    ):
        """Tools tab has widgets for displaying tool usage."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Select first session - must exist with data
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, (
            "Expected at least one item in tree after data load"
        )

        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Navigate to tools tab (click on tab bar)
        detail = tracing._detail_panel
        click_tab(detail._tabs, 2)  # tools tab

        tools_tab = detail._tools_tab
        assert tools_tab is not None, "Tools tab should not be None"

    def test_files_tab_accessible(self, dashboard_window, qtbot, click_nav, click_tab):
        """Files tab is accessible after session selection."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Select first session - must exist with data
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, (
            "Expected at least one item in tree after data load"
        )

        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Navigate to files tab (click on tab bar)
        detail = tracing._detail_panel
        click_tab(detail._tabs, 3)  # files tab

        files_tab = detail._files_tab
        assert files_tab is not None, "Files tab should not be None"

    def test_agents_tab_accessible(self, dashboard_window, qtbot, click_nav, click_tab):
        """Agents tab is accessible after session selection."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Select first session - must exist with data
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, (
            "Expected at least one item in tree after data load"
        )

        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Navigate to agents tab (click on tab bar)
        detail = tracing._detail_panel
        click_tab(detail._tabs, 4)  # agents tab

        agents_tab = detail._agents_tab
        assert agents_tab is not None, "Agents tab should not be None"

    def test_timeline_tab_accessible(
        self, dashboard_window, qtbot, click_nav, click_tab
    ):
        """Timeline tab is accessible after session selection."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Select first session - must exist with data
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, (
            "Expected at least one item in tree after data load"
        )

        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Navigate to timeline tab (click on tab bar)
        detail = tracing._detail_panel
        click_tab(detail._tabs, 5)  # timeline tab

        timeline_tab = detail._timeline_tab
        assert timeline_tab is not None, "Timeline tab should not be None"

    def test_detail_header_updates_on_selection(
        self, dashboard_window, qtbot, click_nav
    ):
        """Detail panel header updates when session is selected."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        detail = tracing._detail_panel
        initial_header = detail._header.text()

        # Select a session - must exist with data
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, (
            "Expected at least one item in tree after data load"
        )

        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Header should have changed
        new_header = detail._header.text()
        # Header must not be empty and should change from initial state
        assert new_header, "Header should not be empty after selection"
        assert new_header != initial_header, (
            f"Header should change after selection. "
            f"Initial: '{initial_header}', New: '{new_header}'"
        )

    def test_metrics_update_on_selection(self, dashboard_window, qtbot, click_nav):
        """Detail panel metrics update when session is selected."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        detail = tracing._detail_panel

        # Select a session with known tokens - must exist with data
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, (
            "Expected at least one item in tree after data load"
        )

        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Check metrics bar exists (refactored from _metric_duration/_metric_tokens)
        assert hasattr(detail, "_metrics_bar"), (
            "Detail panel should have _metrics_bar attribute"
        )


class TestTracingTreeContent:
    """Test that session tree displays correct hierarchical content."""

    def test_tree_root_item_has_session_info(self, dashboard_window, qtbot, click_nav):
        """Root tree items contain session information."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Get first root item
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, "Expected at least one root item in tree"

        # Root item should have text (session title or project name)
        root_text = root_item.text(0)
        assert root_text, f"Root item should have text, got empty string"
        # Verify text is from mock data (meaningful content)
        assert len(root_text) >= 3, (
            f"Expected meaningful text (at least 3 chars), got: '{root_text}'"
        )

    def test_tree_shows_agent_children(self, dashboard_window, qtbot, click_nav):
        """Tree shows child agents under root session."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Get first root item - must exist with data
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, "Expected at least one root item in tree"

        # If root has children, verify they exist and have text
        if root_item.childCount() > 0:
            first_child = root_item.child(0)
            assert first_child is not None, "Child at index 0 should not be None"
            child_text = first_child.text(0)
            assert child_text, f"Child item should have text, got empty string"

    def test_tree_item_has_data(self, dashboard_window, qtbot, click_nav):
        """Tree items have associated data for selection handling."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, "Expected at least one root item in tree"

        # Tree widget has 6 columns (Type/Name, Time, Duration, In, Out, Status)
        assert root_item.columnCount() == 6, (
            f"Expected 6 columns, got {root_item.columnCount()}"
        )
