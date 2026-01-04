"""
Integration tests for dashboard window launch and lifecycle.

Tests:
- Window creation and initialization
- Window properties (title, size, icon)
- Timer setup and cleanup
- Section creation and signal configuration
"""

import pytest

from PyQt6.QtWidgets import QStackedWidget
from PyQt6.QtCore import QTimer

from opencode_monitor.dashboard.widgets import Sidebar
from opencode_monitor.dashboard.sections import (
    MonitoringSection,
    SecuritySection,
    AnalyticsSection,
    TracingSection,
)

pytestmark = pytest.mark.integration


class TestDashboardWindowLifecycle:
    """Test dashboard window lifecycle: creation, properties, cleanup."""

    def test_window_properties(self, dashboard_window):
        """Test that the dashboard window has correct properties on creation."""
        assert dashboard_window.isVisible()
        assert dashboard_window.windowTitle() == "OpenCode Monitor"
        assert dashboard_window.minimumWidth() == 1000
        assert dashboard_window.minimumHeight() == 700
        assert dashboard_window.width() >= 1000
        assert dashboard_window.height() >= 700
        assert not dashboard_window.windowIcon().isNull()

    def test_timers_are_running(self, dashboard_window_with_timers):
        """Test that background timers are active after window creation."""
        window = dashboard_window_with_timers

        assert isinstance(window._refresh_timer, QTimer)
        assert window._refresh_timer.isActive()
        assert window._sync_checker is not None
        assert isinstance(window._sync_checker._timer, QTimer)
        assert window._sync_checker._timer.isActive()

    def test_timers_stop_on_close(self, dashboard_window_with_timers, qtbot):
        """Test that timers are properly stopped when window is closed."""
        window = dashboard_window_with_timers
        refresh_timer = window._refresh_timer
        sync_checker = window._sync_checker

        assert refresh_timer.isActive()
        assert sync_checker._timer.isActive()

        window.close()

        assert not refresh_timer.isActive()
        assert not sync_checker._timer.isActive()


class TestDashboardComponents:
    """Test dashboard UI components: sections, pages, signals."""

    @pytest.mark.parametrize(
        "attr,expected_type",
        [
            ("_monitoring", MonitoringSection),
            ("_security", SecuritySection),
            ("_analytics", AnalyticsSection),
            ("_tracing", TracingSection),
            ("_sidebar", Sidebar),
        ],
    )
    def test_component_types(self, dashboard_window, attr, expected_type):
        """Test that all components have correct types."""
        component = getattr(dashboard_window, attr)
        assert isinstance(component, expected_type)

    def test_pages_stack(self, dashboard_window):
        """Test that pages stack exists with exactly 4 pages."""
        pages = dashboard_window._pages
        assert isinstance(pages, QStackedWidget)
        assert pages.count() == 4

    @pytest.mark.parametrize(
        "signal_name",
        [
            "monitoring_updated",
            "security_updated",
            "analytics_updated",
            "tracing_updated",
        ],
    )
    def test_signal_is_connectable(self, dashboard_window, signal_name):
        """Test that data update signals are properly configured."""
        signals = dashboard_window._signals
        assert signals is not None
        signal = getattr(signals, signal_name)
        assert callable(getattr(signal, "connect", None))


class TestDashboardHidden:
    """Test dashboard creation without showing - validates headless init."""

    def test_hidden_window_initializes_fully(self, dashboard_window_hidden_with_timers):
        """Test that hidden window initializes all components correctly."""
        window = dashboard_window_hidden_with_timers

        assert not window.isVisible()

        # Verify all sections exist (types already tested in TestDashboardComponents)
        assert window._monitoring is not None
        assert window._security is not None
        assert window._analytics is not None
        assert window._tracing is not None

        # Verify timers running for background refresh
        assert window._refresh_timer.isActive()
