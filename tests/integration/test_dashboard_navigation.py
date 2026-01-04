"""
Integration tests for dashboard sidebar navigation.

Tests:
- Sidebar structure and signals
- Navigation between sections
- Page switching performance
- Status indicator updates
"""

import pytest
from PyQt6.QtCore import Qt

pytestmark = pytest.mark.integration


class TestSidebarNavigation:
    """Test sidebar navigation functionality."""

    def test_initial_state_shows_monitoring(self, dashboard_window):
        """Test that the dashboard starts on monitoring section."""
        # Page index should be 0 (Monitoring)
        assert dashboard_window._pages.currentIndex() == 0

        # Current widget should be the monitoring section
        current_widget = dashboard_window._pages.currentWidget()
        assert current_widget == dashboard_window._monitoring

    def test_navigation_between_all_sections(self, dashboard_window, qtbot):
        """Test navigation to all sections and back."""
        sections = [
            (1, dashboard_window._security, "Security"),
            (2, dashboard_window._analytics, "Analytics"),
            (3, dashboard_window._tracing, "Tracing"),
            (0, dashboard_window._monitoring, "Monitoring"),
        ]

        for index, expected_widget, name in sections:
            dashboard_window._on_section_changed(index)

            assert dashboard_window._pages.currentIndex() == index, (
                f"Expected {name} (index {index}), got {dashboard_window._pages.currentIndex()}"
            )
            assert dashboard_window._pages.currentWidget() == expected_widget, (
                f"Current widget should be {name} section"
            )


class TestSidebarWidget:
    """Test sidebar widget properties and behavior."""

    def test_sidebar_structure_and_signals(self, dashboard_window, qtbot):
        """Test sidebar has correct structure and emits signals."""
        sidebar = dashboard_window._sidebar

        # Verify nav items structure (4 sections)
        assert len(sidebar._nav_items) == 4

        # Verify set_status method updates status text
        sidebar.set_status(True, "3 agents")
        assert sidebar._status_text.text() == "3 agents"

        sidebar.set_status(False, "Idle")
        assert sidebar._status_text.text() == "Idle"

        # Test signal emission
        with qtbot.waitSignal(sidebar.section_changed, timeout=1000) as blocker:
            sidebar.section_changed.emit(2)

        assert blocker.signal_triggered
        assert blocker.args == [2]

        # Test nav items are clickable
        security_item = sidebar._nav_items[1]
        qtbot.mouseClick(security_item, Qt.MouseButton.LeftButton)
        qtbot.wait(100)


class TestPageSwitchingPerformance:
    """Test page switching performance."""

    def test_page_switching_is_immediate_and_handles_rapid_changes(
        self, dashboard_window, qtbot
    ):
        """Test that page switching is immediate and handles rapid changes."""
        # Test immediate switching
        dashboard_window._on_section_changed(2)
        assert dashboard_window._pages.currentIndex() == 2

        # Test rapid page switching (3 full cycles)
        for _ in range(3):
            for i in range(4):
                dashboard_window._on_section_changed(i)
                qtbot.wait(50)

        # Should end up on last page
        assert dashboard_window._pages.currentIndex() == 3
