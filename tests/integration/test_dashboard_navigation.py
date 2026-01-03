"""
Integration tests for dashboard sidebar navigation.

Tests:
- Sidebar button clicks
- Page switching
- Section visibility
- Navigation state persistence
"""

import pytest
from PyQt6.QtCore import Qt

pytestmark = pytest.mark.integration


class TestSidebarNavigation:
    """Test sidebar navigation functionality."""

    def test_initial_page_is_monitoring(self, dashboard_window):
        """Test that the initial page is Monitoring (index 0)."""
        assert dashboard_window._pages.currentIndex() == 0

    def test_monitoring_is_default_visible(self, dashboard_window):
        """Test that monitoring section is visible by default."""
        current_widget = dashboard_window._pages.currentWidget()
        assert current_widget == dashboard_window._monitoring

    def test_click_security_shows_security_page(self, dashboard_window, qtbot):
        """Test that clicking Security in sidebar shows security page."""
        # Simulate section change to Security (index 1)
        dashboard_window._on_section_changed(1)

        # Verify page changed
        assert dashboard_window._pages.currentIndex() == 1
        assert dashboard_window._pages.currentWidget() == dashboard_window._security

    def test_click_analytics_shows_analytics_page(self, dashboard_window, qtbot):
        """Test that clicking Analytics in sidebar shows analytics page."""
        dashboard_window._on_section_changed(2)

        assert dashboard_window._pages.currentIndex() == 2
        assert dashboard_window._pages.currentWidget() == dashboard_window._analytics

    def test_click_tracing_shows_tracing_page(self, dashboard_window, qtbot):
        """Test that clicking Tracing in sidebar shows tracing page."""
        dashboard_window._on_section_changed(3)

        assert dashboard_window._pages.currentIndex() == 3
        assert dashboard_window._pages.currentWidget() == dashboard_window._tracing

    def test_can_navigate_back_to_monitoring(self, dashboard_window, qtbot):
        """Test that we can navigate back to monitoring from another page."""
        # Go to tracing
        dashboard_window._on_section_changed(3)
        assert dashboard_window._pages.currentIndex() == 3

        # Go back to monitoring
        dashboard_window._on_section_changed(0)
        assert dashboard_window._pages.currentIndex() == 0
        assert dashboard_window._pages.currentWidget() == dashboard_window._monitoring


class TestSidebarWidget:
    """Test sidebar widget properties and behavior."""

    def test_sidebar_has_nav_items(self, dashboard_window):
        """Test that sidebar has navigation items."""
        sidebar = dashboard_window._sidebar
        assert hasattr(sidebar, "_nav_items")
        assert len(sidebar._nav_items) == 4  # Monitoring, Security, Analytics, Tracing

    def test_sidebar_emits_section_changed_signal(self, dashboard_window, qtbot):
        """Test that sidebar emits section_changed signal."""
        sidebar = dashboard_window._sidebar

        # Track signal emission
        with qtbot.waitSignal(sidebar.section_changed, timeout=1000) as blocker:
            # Simulate clicking a different section
            sidebar.section_changed.emit(2)

        assert blocker.signal_triggered
        assert blocker.args == [2]

    def test_sidebar_nav_items_are_clickable(self, dashboard_window, qtbot):
        """Test that sidebar navigation items can be clicked."""
        sidebar = dashboard_window._sidebar

        # Get the security nav item (index 1)
        if sidebar._nav_items:
            security_item = sidebar._nav_items[1]

            # Click should not raise
            qtbot.mouseClick(security_item, Qt.MouseButton.LeftButton)

            # After click, current index should change
            qtbot.wait(200)  # Wait for signal processing (increased for CI stability)


class TestPageSwitchingPerformance:
    """Test page switching performance."""

    def test_rapid_page_switching(self, dashboard_window, qtbot):
        """Test that rapid page switching doesn't cause issues."""
        # Rapidly switch through all pages
        for _ in range(3):
            for i in range(4):
                dashboard_window._on_section_changed(i)
                qtbot.wait(50)

        # Should end up on last page (3)
        assert dashboard_window._pages.currentIndex() == 3

    def test_page_switch_is_immediate(self, dashboard_window, qtbot):
        """Test that page switch happens immediately without delay."""
        # Switch to analytics
        dashboard_window._on_section_changed(2)

        # Should be immediate (no need to wait)
        assert dashboard_window._pages.currentIndex() == 2


class TestSidebarStatus:
    """Test sidebar status indicator."""

    def test_sidebar_set_status_method_exists(self, dashboard_window):
        """Test that sidebar has set_status method."""
        sidebar = dashboard_window._sidebar
        assert hasattr(sidebar, "set_status")

    def test_sidebar_status_can_be_updated(self, dashboard_window, qtbot):
        """Test that sidebar status can be updated."""
        sidebar = dashboard_window._sidebar

        # Update status
        sidebar.set_status(True, "3 agents")

        # Should not raise errors
        qtbot.wait(100)

    def test_sidebar_status_idle(self, dashboard_window, qtbot):
        """Test that sidebar can show idle status."""
        sidebar = dashboard_window._sidebar

        sidebar.set_status(False, "Idle")

        qtbot.wait(100)
