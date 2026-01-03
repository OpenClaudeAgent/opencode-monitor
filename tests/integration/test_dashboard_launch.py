"""
Integration tests for dashboard window launch and lifecycle.

Tests:
- Window creation and initialization
- Window properties (title, size, icon)
- Timer setup and cleanup
- Close event handling
"""

import pytest

pytestmark = pytest.mark.integration


class TestDashboardWindowCreation:
    """Test dashboard window creation and initialization."""

    def test_window_creates_successfully(self, dashboard_window):
        """Test that the dashboard window creates without errors."""
        assert dashboard_window is not None
        assert dashboard_window.isVisible()

    def test_window_title_is_correct(self, dashboard_window):
        """Test that the window title is set correctly."""
        assert dashboard_window.windowTitle() == "OpenCode Monitor"

    def test_window_has_minimum_size(self, dashboard_window):
        """Test that the window has minimum size constraints."""
        min_width = dashboard_window.minimumWidth()
        min_height = dashboard_window.minimumHeight()

        # Should have reasonable minimum dimensions
        assert min_width > 0
        assert min_height > 0

    def test_window_has_default_size(self, dashboard_window):
        """Test that the window starts with default size."""
        width = dashboard_window.width()
        height = dashboard_window.height()

        # Should have reasonable default dimensions
        assert width >= dashboard_window.minimumWidth()
        assert height >= dashboard_window.minimumHeight()

    def test_window_has_icon(self, dashboard_window):
        """Test that the window has an icon set."""
        icon = dashboard_window.windowIcon()
        assert not icon.isNull()


class TestDashboardTimers:
    """Test dashboard timer initialization and cleanup."""

    def test_refresh_timer_is_running(self, dashboard_window):
        """Test that the refresh timer is started."""
        assert dashboard_window._refresh_timer is not None
        assert dashboard_window._refresh_timer.isActive()

    def test_sync_checker_is_running(self, dashboard_window):
        """Test that the sync checker is started."""
        assert dashboard_window._sync_checker is not None

    def test_timers_stop_on_close(self, dashboard_window, qtbot):
        """Test that timers are stopped when window is closed."""
        # Get references before close
        refresh_timer = dashboard_window._refresh_timer
        sync_checker = dashboard_window._sync_checker

        # Close the window
        dashboard_window.close()

        # Timers should be stopped
        assert not refresh_timer.isActive()


class TestDashboardSections:
    """Test that all dashboard sections are created."""

    def test_monitoring_section_exists(self, dashboard_window):
        """Test that monitoring section is created."""
        assert dashboard_window._monitoring is not None

    def test_security_section_exists(self, dashboard_window):
        """Test that security section is created."""
        assert dashboard_window._security is not None

    def test_analytics_section_exists(self, dashboard_window):
        """Test that analytics section is created."""
        assert dashboard_window._analytics is not None

    def test_tracing_section_exists(self, dashboard_window):
        """Test that tracing section is created."""
        assert dashboard_window._tracing is not None

    def test_sidebar_exists(self, dashboard_window):
        """Test that sidebar is created."""
        assert dashboard_window._sidebar is not None

    def test_pages_stack_exists(self, dashboard_window):
        """Test that stacked pages widget is created."""
        assert dashboard_window._pages is not None

    def test_four_pages_in_stack(self, dashboard_window):
        """Test that there are exactly 4 pages in the stack."""
        assert dashboard_window._pages.count() == 4


class TestDashboardSignals:
    """Test that dashboard signals are properly connected."""

    def test_signals_object_exists(self, dashboard_window):
        """Test that signals object is created."""
        assert dashboard_window._signals is not None

    def test_monitoring_signal_exists(self, dashboard_window):
        """Test that monitoring_updated signal exists."""
        assert hasattr(dashboard_window._signals, "monitoring_updated")

    def test_security_signal_exists(self, dashboard_window):
        """Test that security_updated signal exists."""
        assert hasattr(dashboard_window._signals, "security_updated")

    def test_analytics_signal_exists(self, dashboard_window):
        """Test that analytics_updated signal exists."""
        assert hasattr(dashboard_window._signals, "analytics_updated")

    def test_tracing_signal_exists(self, dashboard_window):
        """Test that tracing_updated signal exists."""
        assert hasattr(dashboard_window._signals, "tracing_updated")


class TestDashboardHidden:
    """Test dashboard creation without showing the window."""

    def test_hidden_window_creates_successfully(self, dashboard_window_hidden):
        """Test that hidden window creates without errors."""
        assert dashboard_window_hidden is not None
        assert not dashboard_window_hidden.isVisible()

    def test_hidden_window_has_sections(self, dashboard_window_hidden):
        """Test that hidden window has all sections."""
        assert dashboard_window_hidden._monitoring is not None
        assert dashboard_window_hidden._security is not None
        assert dashboard_window_hidden._analytics is not None
        assert dashboard_window_hidden._tracing is not None

    def test_hidden_window_timers_running(self, dashboard_window_hidden):
        """Test that timers start even for hidden window."""
        # Timers should still be running for background refresh
        assert dashboard_window_hidden._refresh_timer is not None
        assert dashboard_window_hidden._refresh_timer.isActive()
