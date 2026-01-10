"""
Integration tests for Tracing session selection and tabs navigation.

Tests verify that:
- Session selection updates detail panel with correct metrics
- Tab structure is correct (6 tabs with proper types)
- Tab navigation works correctly
"""

import pytest
from PyQt6.QtWidgets import QWidget, QTabWidget

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


class TestTracingSessionSelection:
    """Test session selection and detail panel update."""

    def test_session_selection_updates_detail_panel_and_metrics(
        self, tracing_with_data, select_first_session
    ):
        """Selecting a session updates detail panel.

        Consolidated test verifying:
        - Detail panel is updated on session selection
        - SessionOverviewPanel is displayed for root sessions (not tabs)
        """
        tracing, dashboard = tracing_with_data

        # Select first session
        root_item = select_first_session(tracing)
        assert root_item is not None

        # Detail panel should be updated
        detail = tracing._detail_panel
        assert detail is not None, "Detail panel should exist"

        # === CRITICAL: For root session, SessionOverviewPanel should display (NOT tabs) ===
        # Verify _content_stack exists
        assert hasattr(detail, "_content_stack"), (
            "Detail panel should have _content_stack"
        )

        # For root session: page 0 = SessionOverviewPanel, page 1 = tabs
        assert detail._content_stack.currentIndex() == 0, (
            f"Root session should show SessionOverviewPanel (page 0), "
            f"but showing page {detail._content_stack.currentIndex()} (tabs)"
        )

        # Verify SessionOverviewPanel is loaded with data
        assert hasattr(detail, "_session_overview"), (
            "Detail panel should have _session_overview"
        )
        overview = detail._session_overview
        # The title label should have session data loaded, not default
        assert overview._title_label.text() != "", (
            "SessionOverviewPanel should have title loaded"
        )


class TestTracingTabsNavigation:
    """Test tabs structure and navigation in detail panel."""

    def test_tabs_structure_default_and_navigation(
        self, tracing_with_data, select_first_session, click_tab
    ):
        """Verify tabs structure, default selection, and navigation.

        Consolidated test verifying:
        - Exactly 7 tabs exist (transcript, tokens, tools, files, agents, timeline, delegations)
        - Tab widget is correct QTabWidget type
        - Default tab is transcript (index 0)
        - Navigation to each tab works correctly
        """
        tracing, dashboard = tracing_with_data
        detail = tracing._detail_panel

        # Strict type check on tabs widget
        assert isinstance(detail._tabs, QTabWidget), (
            f"Expected QTabWidget, got {type(detail._tabs).__name__}"
        )

        # Verify exact tab count (7 tabs including delegations)
        assert detail._tabs.count() == 7, f"Expected 7 tabs, got {detail._tabs.count()}"

        # Verify default tab is transcript (index 0)
        assert detail._tabs.currentIndex() == 0, (
            f"Default tab should be 0 (transcript), got {detail._tabs.currentIndex()}"
        )

        # Test navigation to each tab
        tab_names = [
            "transcript",
            "tokens",
            "tools",
            "files",
            "agents",
            "timeline",
            "delegations",
        ]
        for i, name in enumerate(tab_names):
            click_tab(detail._tabs, i)
            assert detail._tabs.currentIndex() == i, (
                f"After clicking, should be on tab {i} ({name}), "
                f"got {detail._tabs.currentIndex()}"
            )

    @pytest.mark.parametrize(
        "tab_name,tab_index,expected_tooltip",
        [
            ("transcript", 0, "Transcript - Full conversation"),
            ("tokens", 1, "Tokens - Usage breakdown"),
            ("tools", 2, "Tools - Tool calls"),
            ("files", 3, "Files - File operations"),
            ("agents", 4, "Agents - Agent hierarchy"),
            ("timeline", 5, "Timeline - Event timeline"),
            ("delegations", 6, "Delegations - Agent tree"),
        ],
    )
    def test_tab_widget_type_accessibility_and_tooltip(
        self, dashboard_window, tab_name, tab_index, expected_tooltip
    ):
        """Each tab exists, is accessible, is a valid QWidget, and has tooltip.

        Parametrized test with strict assertions:
        - Tab is accessible via attribute (direct access, raises AttributeError if missing)
        - Tab is not None
        - Tab is a QWidget subclass
        - Tab is the same widget as in QTabWidget at corresponding index
        - Tab has correct tooltip configured
        """
        detail = dashboard_window._tracing._detail_panel
        tab_attr = f"_{tab_name}_tab"

        # Direct attribute access (raises AttributeError if missing)
        tab = getattr(detail, tab_attr)

        # Not None check
        assert tab is not None, f"{tab_name} tab should not be None"

        # Type check - must be QWidget subclass
        assert isinstance(tab, QWidget), (
            f"{tab_name} tab should be QWidget subclass, got {type(tab).__name__}"
        )

        # Verify tab is correctly added to QTabWidget at expected index
        widget_at_index = detail._tabs.widget(tab_index)
        assert widget_at_index is tab, (
            f"Tab at index {tab_index} should be {tab_attr}, "
            f"got {type(widget_at_index).__name__}"
        )

        # Verify tooltip is set correctly
        tooltip = detail._tabs.tabToolTip(tab_index)
        assert tooltip == expected_tooltip, (
            f"Tab {tab_index} tooltip should be '{expected_tooltip}', got '{tooltip}'"
        )
