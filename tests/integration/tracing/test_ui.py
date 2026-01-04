"""
Integration tests for Tracing section UI basics.

Tests verify that:
- TracingSection structure is complete (tree, detail panel, empty state)
- Navigation works correctly
- Empty state displays with correct message
- Session list populates with data
"""

import pytest
from PyQt6.QtWidgets import QTreeWidget, QLabel

from opencode_monitor.dashboard.widgets import EmptyState
from opencode_monitor.dashboard.sections.tracing import TracingSection
from opencode_monitor.dashboard.sections.tracing.detail_panel import TraceDetailPanel

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


class TestTracingSectionStructure:
    """Test that tracing section has all required components."""

    def test_tracing_section_structure(self, dashboard_window, qtbot, click_nav):
        """Verify tracing section structure: tree widget, detail panel, and navigation."""
        # 1. Tracing section exists and has correct type
        assert isinstance(dashboard_window._tracing, TracingSection), (
            f"_tracing should be TracingSection, got {type(dashboard_window._tracing).__name__}"
        )
        tracing = dashboard_window._tracing

        # 2. Tree widget exists and has correct type
        assert isinstance(tracing._tree, QTreeWidget), (
            f"_tree should be QTreeWidget, got {type(tracing._tree).__name__}"
        )
        assert tracing._tree.headerItem() is not None, "Tree should have headers"
        assert tracing._tree.columnCount() == 6, "Tree should have 6 columns"

        # 3. Detail panel exists and has correct type
        assert isinstance(tracing._detail_panel, TraceDetailPanel), (
            f"_detail_panel should be TraceDetailPanel, got {type(tracing._detail_panel).__name__}"
        )

        # 4. Empty state widget exists and has correct type
        assert isinstance(tracing._empty, EmptyState), (
            f"_empty should be EmptyState, got {type(tracing._empty).__name__}"
        )

        # 5. Navigation to tracing section works
        click_nav(dashboard_window, SECTION_TRACING)
        assert dashboard_window._pages.currentIndex() == SECTION_TRACING, (
            "Should navigate to tracing section"
        )


class TestTracingEmptyState:
    """Test tracing section empty state behavior."""

    def test_empty_state_displays_with_correct_message(
        self, dashboard_window, qtbot, click_nav
    ):
        """Empty state appears with correct message when no tracing data."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        # Emit empty tracing data
        empty_data = {"session_hierarchy": []}
        dashboard_window._signals.tracing_updated.emit(empty_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # 1. Tree should be hidden
        assert tracing._tree.isHidden(), "Tree should be hidden with empty data"

        # 2. Empty state should be visible
        assert not tracing._empty.isHidden(), "Empty state should be visible"
        assert tracing._empty.isVisible(), (
            "Empty state should be visible in widget hierarchy"
        )

        # 3. Verify empty state contains correct message
        labels = tracing._empty.findChildren(QLabel)
        label_texts = [label.text() for label in labels]

        assert "No traces found" in label_texts, (
            f"Empty state should contain 'No traces found', got: {label_texts}"
        )
        assert any("task" in text.lower() for text in label_texts), (
            f"Empty state should mention 'task' tool, got: {label_texts}"
        )


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

        # Tree visible, empty state hidden
        assert tracing._tree.isHidden() is False
        assert tracing._empty.isHidden() is True

        # Fixture has exactly 1 root session
        assert tracing._tree.topLevelItemCount() == 1

    def test_session_tree_shows_hierarchy(self, dashboard_window, qtbot, click_nav):
        """Session tree displays hierarchical structure matching fixture data."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Root: project "my-project" from fixture directory "/home/dev/my-project"
        root_item = tracing._tree.topLevelItem(0)
        assert root_item.text(0) == "🌳 my-project"

        # Fixture has 2 delegation children
        assert root_item.childCount() == 2

        # Verify delegation labels match fixture data exactly
        assert root_item.child(0).text(0) == "💬 user → executor"
        assert root_item.child(1).text(0) == "🔗 executor → tester"
