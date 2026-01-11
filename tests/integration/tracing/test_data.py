"""
Integration tests for Tracing data persistence and signals.

Tests verify that:
- Tracing data persists across navigation
- Signals work correctly
"""

import pytest

from ..fixtures import process_qt_events
from ..conftest import SECTION_TRACING, SECTION_MONITORING
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


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
        process_qt_events()

        initial_count = tracing._tree.topLevelItemCount()
        # Fixture realistic_tracing() creates exactly 1 root session
        assert initial_count == 1

        # Navigate away to Monitoring
        click_nav(dashboard_window, SECTION_MONITORING)

        # Navigate back to Tracing
        click_nav(dashboard_window, SECTION_TRACING)

        # Data should still be there
        assert tracing._tree.topLevelItemCount() == initial_count


class TestTracingSignals:
    """Test tracing signal handling."""

    def test_double_click_emits_open_terminal_signal(
        self, dashboard_window, qtbot, click_nav
    ):
        """Double-clicking item with session_id emits open_terminal_requested signal."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing

        # Verify signal exists by connecting a slot (fails if signal doesn't exist)
        signals_received = []
        tracing.open_terminal_requested.connect(
            lambda sid: signals_received.append(sid)
        )

        # Load data
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        process_qt_events()

        # Get first item and double-click
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, "Expected root item in tree after data load"

        tracing._on_item_double_clicked(root_item, 0)
        process_qt_events()

        # Signal must be emitted with the expected session_id
        assert len(signals_received) == 1, "Expected exactly one signal emission"
        assert signals_received[0] == "sess-root-001"
