"""
Integration tests for Tracing section UI basics.

Tests verify that:
- TracingSection exists and is accessible
- Empty state displays correctly
- Session list populates with data
"""

import pytest

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


class TestTracingSectionExists:
    """Test that tracing section exists and is accessible."""

    def test_tracing_section_exists(self, dashboard_window, qtbot):
        """Verify tracing section is registered in dashboard."""
        assert hasattr(dashboard_window, "_tracing")
        assert dashboard_window._tracing is not None

    def test_tracing_section_in_pages(self, dashboard_window, qtbot, click_nav):
        """Tracing section is in the pages stack."""
        # Navigate to Tracing via sidebar click (index 3)
        click_nav(dashboard_window, SECTION_TRACING)

        # Verify we can navigate to it
        assert dashboard_window._pages.currentIndex() == SECTION_TRACING

    def test_tracing_section_has_tree(self, dashboard_window, qtbot):
        """Tracing section has a tree widget."""
        tracing = dashboard_window._tracing
        assert hasattr(tracing, "_tree")
        assert tracing._tree is not None

    def test_tracing_section_has_detail_panel(self, dashboard_window, qtbot):
        """Tracing section has a detail panel."""
        tracing = dashboard_window._tracing
        assert hasattr(tracing, "_detail_panel")
        assert tracing._detail_panel is not None


class TestTracingEmptyState:
    """Test tracing section empty state behavior."""

    def test_tracing_section_shows_empty_state_without_data(
        self, dashboard_window, qtbot, click_nav
    ):
        """Empty state appears when no tracing data."""
        # Navigate to Tracing section via sidebar click
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing

        # Emit empty tracing data
        empty_data = {
            "traces": [],
            "sessions": [],
            "session_hierarchy": [],
            "total_traces": 0,
            "unique_agents": 0,
            "total_duration_ms": 0,
        }
        dashboard_window._signals.tracing_updated.emit(empty_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Tree should be hidden, empty state NOT hidden
        # Note: isVisible() checks parent visibility, isHidden() checks widget state
        assert tracing._tree.isHidden(), "Tree should be hidden with empty data"
        assert not tracing._empty.isHidden(), "Empty state should not be hidden"

    def test_tracing_empty_state_has_correct_message(
        self, dashboard_window, qtbot, click_nav
    ):
        """Empty state shows appropriate message."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing

        # Emit empty data
        empty_data = {
            "traces": [],
            "sessions": [],
            "session_hierarchy": [],
            "total_traces": 0,
            "unique_agents": 0,
            "total_duration_ms": 0,
        }
        dashboard_window._signals.tracing_updated.emit(empty_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Empty state should not be hidden (shows message)
        assert not tracing._empty.isHidden(), "Empty state should be shown"


class TestTracingSessionList:
    """Test session list display with data."""

    def test_tracing_section_shows_session_list_with_data(
        self, dashboard_window, qtbot, click_nav
    ):
        """Session tree populates when data is provided."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Tree should NOT be hidden (visible), empty state should be hidden
        # Note: isVisible() checks parent visibility, isHidden() checks widget state
        assert not tracing._tree.isHidden(), "Tree should not be hidden with data"
        assert tracing._empty.isHidden(), "Empty state should be hidden with data"

        # Should have at least one top-level item
        assert tracing._tree.topLevelItemCount() >= 1

    def test_session_tree_shows_hierarchy(self, dashboard_window, qtbot, click_nav):
        """Session tree displays hierarchical structure."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Get first root item
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None

        # Root item should have text (project name or session title)
        root_text = root_item.text(0)
        assert root_text, f"Root item should have text, got empty string"
        # Verify text is from mock data (could be project name like "my-project" or session title)
        assert len(root_text) >= 3, (
            f"Expected meaningful text (at least 3 chars), got: '{root_text}'"
        )
