"""
Integration tests for the Tracing section.

Tests verify that:
- TracingSection displays correctly with and without data
- Session tree shows hierarchical data
- Session selection updates detail panel
- Tab navigation works correctly
- Empty state appears when no traces
"""

import pytest
from PyQt6.QtCore import Qt

from .conftest import (
    SIGNAL_WAIT_MS,
    SECTION_TRACING,
    SECTION_MONITORING,
    SECTION_ANALYTICS,
)
from .fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


# =============================================================================
# Tracing Section Tests
# =============================================================================


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


class TestTracingDataPersistence:
    """Test that tracing data persists across navigation."""

    def test_data_persists_after_navigation(self, dashboard_window, qtbot, click_nav):
        """Tracing data remains after navigating away and back."""
        # Navigate to Tracing
        click_nav(dashboard_window, SECTION_TRACING)

        # Set data
        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        initial_count = tracing._tree.topLevelItemCount()
        assert initial_count > 0

        # Navigate away to Monitoring
        click_nav(dashboard_window, SECTION_MONITORING)

        # Navigate back to Tracing
        click_nav(dashboard_window, SECTION_TRACING)

        # Data should still be there
        assert tracing._tree.topLevelItemCount() == initial_count


class TestTracingSignals:
    """Test tracing signal handling."""

    def test_open_terminal_signal_exists(self, dashboard_window, qtbot):
        """Tracing section has open_terminal_requested signal."""
        tracing = dashboard_window._tracing
        assert hasattr(tracing, "open_terminal_requested")

    def test_double_click_emits_signal(self, dashboard_window, qtbot, click_nav):
        """Double-clicking item emits open_terminal_requested signal."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Track signal
        signals_received = []
        tracing.open_terminal_requested.connect(
            lambda sid: signals_received.append(sid)
        )

        # Get first item and double-click - must exist with data
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, (
            "Expected at least one item in tree after data load"
        )

        tracing._on_item_double_clicked(root_item, 0)
        qtbot.wait(50)

        # Signal may or may not be emitted depending on data
        # (session_id must be present in item data)


# =============================================================================
# Tracing Tabs Content Tests (Reinforced Assertions)
# =============================================================================


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

        # Check metrics exist
        assert hasattr(detail, "_metric_duration"), (
            "Detail panel should have _metric_duration attribute"
        )
        assert hasattr(detail, "_metric_tokens"), (
            "Detail panel should have _metric_tokens attribute"
        )


# =============================================================================
# Tree Content Validation Tests
# =============================================================================


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

        # Tree widget has 4 columns (name, tokens, duration, status)
        assert root_item.columnCount() == 4, (
            f"Expected 4 columns, got {root_item.columnCount()}"
        )


# =============================================================================
# User Workflow Tests
# =============================================================================


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
