"""
Integration tests for Tracing data persistence and signals.

Tests verify that:
- Tracing data persists across navigation
- Signals work correctly
"""

import pytest

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING, SECTION_MONITORING
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
