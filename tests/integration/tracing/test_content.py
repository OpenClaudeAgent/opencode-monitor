"""
Integration tests for Tracing tabs and tree content.

Tests verify that:
- Tab content is accessible after selection
- Tree displays correct hierarchical content
- Detail header and metrics update correctly
"""

import pytest
from PyQt6.QtWidgets import QWidget

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration

# Expected tree columns
TREE_COLUMNS = ["Type / Name", "Time", "Duration", "In", "Out", ""]
TREE_COLUMN_COUNT = 6

# Expected values from fixture (tracing.py)
ROOT_SESSION_LABEL = "🌳 my-project"
CHILD_COUNT = 2  # executor + tester delegations

# Detail panel header (fallback when session_summaries not mocked)
DETAIL_HEADER_FALLBACK = "🌳 Session"


class TestTracingTabsContent:
    """Test that tabs display actual content when data is loaded."""

    @pytest.mark.parametrize(
        "tab_index,tab_attr",
        [
            (0, "_transcript_tab"),
            (1, "_tokens_tab"),
            (2, "_tools_tab"),
            (3, "_files_tab"),
            (4, "_agents_tab"),
            (5, "_timeline_tab"),
        ],
        ids=[
            "transcript",
            "tokens",
            "tools",
            "files",
            "agents",
            "timeline",
        ],
    )
    def test_tab_accessible_after_selection(
        self, dashboard_window, qtbot, click_nav, click_tab, tab_index, tab_attr
    ):
        """Each tab is accessible and selectable after session selection."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Select root session
        root_item = tracing._tree.topLevelItem(0)
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Navigate to tab and verify accessibility
        detail = tracing._detail_panel
        click_tab(detail._tabs, tab_index)

        assert detail._tabs.currentIndex() == tab_index
        tab_widget = getattr(detail, tab_attr)
        assert isinstance(tab_widget, QWidget)

    def test_detail_panel_updates_on_selection(
        self, dashboard_window, qtbot, click_nav
    ):
        """Detail panel header and metrics update when session is selected."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        detail = tracing._detail_panel
        initial_header = detail._header.text()

        # Select root session
        root_item = tracing._tree.topLevelItem(0)
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Header should change to session info
        new_header = detail._header.text()
        assert new_header != initial_header, (
            f"Header should change after selection. "
            f"Initial: '{initial_header}', New: '{new_header}'"
        )
        assert new_header == DETAIL_HEADER_FALLBACK, (
            f"Expected header '{DETAIL_HEADER_FALLBACK}', got '{new_header}'"
        )

        # Metrics bar should exist
        assert isinstance(detail._metrics_bar, QWidget)


class TestTracingTreeContent:
    """Test that session tree displays correct hierarchical content."""

    def test_tree_structure(self, dashboard_window, qtbot, click_nav):
        """Tree displays correct root session with children and proper columns."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Verify tree has expected column count
        tree = tracing._tree
        assert tree.columnCount() == TREE_COLUMN_COUNT

        # Get root item and verify session info
        root_item = tree.topLevelItem(0)
        root_text = root_item.text(0)
        assert root_text == ROOT_SESSION_LABEL, (
            f"Expected root label '{ROOT_SESSION_LABEL}', got '{root_text}'"
        )

        # Verify children count and structure
        assert root_item.childCount() == CHILD_COUNT, (
            f"Expected {CHILD_COUNT} children, got {root_item.childCount()}"
        )

        # Verify first child (executor delegation)
        first_child = root_item.child(0)
        first_child_text = first_child.text(0)
        assert "executor" in first_child_text.lower() or "Execute" in first_child_text

        # Verify second child (tester delegation)
        second_child = root_item.child(1)
        second_child_text = second_child.text(0)
        assert "tester" in second_child_text.lower() or "Run tests" in second_child_text

        # All items should have proper column count
        assert root_item.columnCount() == TREE_COLUMN_COUNT
        assert first_child.columnCount() == TREE_COLUMN_COUNT
        assert second_child.columnCount() == TREE_COLUMN_COUNT
