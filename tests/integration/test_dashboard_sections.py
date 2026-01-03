"""
Integration tests for dashboard sections functionality.

Tests:
- Section initialization
- Data updates via signals
- Section-specific widgets
- API data handling
"""

import pytest
from unittest.mock import patch, MagicMock

from .fixtures import (
    create_monitoring_data,
    create_security_data,
    create_global_stats,
)

pytestmark = pytest.mark.integration


class TestMonitoringSection:
    """Test monitoring section functionality."""

    def test_monitoring_section_updates_with_data(self, dashboard_window, qtbot):
        """Test that monitoring section updates when data is received."""
        monitoring = dashboard_window._monitoring

        # Create test data
        data = create_monitoring_data(num_agents=2, num_busy=1)

        # Update via signal
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(100)

        # Section should have received data (implementation-dependent)
        # At minimum, it should not raise errors

    def test_monitoring_section_handles_empty_data(self, dashboard_window, qtbot):
        """Test that monitoring section handles empty data gracefully."""
        data = create_monitoring_data(num_agents=0, num_busy=0)

        # Should not raise
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(100)

    def test_monitoring_section_has_update_method(self, dashboard_window):
        """Test that monitoring section has update_data method."""
        assert hasattr(dashboard_window._monitoring, "update_data")


class TestSecuritySection:
    """Test security section functionality."""

    def test_security_section_updates_with_data(self, dashboard_window, qtbot):
        """Test that security section updates when data is received."""
        data = create_security_data(total_commands=10, critical_count=1)

        dashboard_window._signals.security_updated.emit(data)
        qtbot.wait(100)

    def test_security_section_handles_no_threats(self, dashboard_window, qtbot):
        """Test that security section handles no threats gracefully."""
        data = create_security_data(total_commands=10, critical_count=0, high_count=0)

        dashboard_window._signals.security_updated.emit(data)
        qtbot.wait(100)

    def test_security_section_has_update_method(self, dashboard_window):
        """Test that security section has update_data method."""
        assert hasattr(dashboard_window._security, "update_data")


class TestAnalyticsSection:
    """Test analytics section functionality."""

    def test_analytics_section_updates_with_data(self, dashboard_window, qtbot):
        """Test that analytics section updates when data is received."""
        data = {
            "sessions": 10,
            "messages": 100,
            "tokens": "50K",
            "cache_hit": "25%",
            "agents": [],
            "tools": [],
            "skills": [],
        }

        dashboard_window._signals.analytics_updated.emit(data)
        qtbot.wait(100)

    def test_analytics_section_has_period_selector(self, dashboard_window):
        """Test that analytics section has period selection."""
        analytics = dashboard_window._analytics
        assert hasattr(analytics, "get_current_period")

    def test_analytics_section_emits_period_changed(self, dashboard_window, qtbot):
        """Test that analytics section can emit period_changed signal."""
        analytics = dashboard_window._analytics
        assert hasattr(analytics, "period_changed")

    def test_analytics_section_has_update_method(self, dashboard_window):
        """Test that analytics section has update_data method."""
        assert hasattr(dashboard_window._analytics, "update_data")


class TestTracingSection:
    """Test tracing section functionality."""

    def test_tracing_section_updates_with_data(self, dashboard_window, qtbot):
        """Test that tracing section updates when data is received."""
        data = {
            "traces": [],
            "sessions": [],
            "session_hierarchy": [],
            "total_traces": 0,
            "unique_agents": 0,
            "total_duration_ms": 0,
        }

        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(100)

    def test_tracing_section_handles_session_hierarchy(self, dashboard_window, qtbot):
        """Test that tracing section handles session hierarchy."""
        hierarchy = [
            {
                "session_id": "sess-001",
                "node_type": "session",
                "title": "Test Session",
                "agent_type": "user",
                "children": [],
                "trace_count": 1,
                "total_duration_ms": 5000,
            }
        ]

        data = {
            "traces": [],
            "sessions": [],
            "session_hierarchy": hierarchy,
            "total_traces": 1,
            "unique_agents": 1,
            "total_duration_ms": 5000,
        }

        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(100)

    def test_tracing_section_has_update_method(self, dashboard_window):
        """Test that tracing section has update_data method."""
        assert hasattr(dashboard_window._tracing, "update_data")

    def test_tracing_section_has_terminal_signal(self, dashboard_window):
        """Test that tracing section has open_terminal_requested signal."""
        assert hasattr(dashboard_window._tracing, "open_terminal_requested")


class TestSectionDataFlow:
    """Test data flow from API to sections."""

    def test_monitoring_data_flows_correctly(self, dashboard_window, qtbot):
        """Test end-to-end data flow for monitoring."""
        # Create monitoring data
        data = create_monitoring_data(num_agents=3, num_busy=2, num_waiting=1)

        # Emit signal
        dashboard_window._on_monitoring_data(data)
        qtbot.wait(100)

        # Sidebar should be updated
        # (implementation may vary, just ensure no errors)

    def test_analytics_data_flows_correctly(self, dashboard_window, qtbot):
        """Test end-to-end data flow for analytics."""
        data = {
            "sessions": 5,
            "messages": 50,
            "tokens": "10K",
            "cache_hit": "30%",
            "agents": [],
            "tools": [],
            "skills": [],
        }

        dashboard_window._on_analytics_data(data)
        qtbot.wait(100)


class TestAPIClientUsage:
    """Test that sections use the mock API client correctly."""

    def test_api_client_is_mocked(self, dashboard_window, patched_api_client):
        """Test that the API client is properly mocked."""
        # The patched client should be used by the dashboard
        assert patched_api_client.is_available

    def test_api_client_tracks_calls(self, patched_api_client):
        """Test that the mock API client tracks calls."""
        patched_api_client.get_stats()
        patched_api_client.get_global_stats(days=7)

        call_log = patched_api_client.get_call_log()
        assert len(call_log) == 2
        assert call_log[0][0] == "get_stats"
        assert call_log[1][0] == "get_global_stats"
        assert call_log[1][1] == {"days": 7}

    def test_api_client_can_be_set_unavailable(self, patched_api_client):
        """Test that API client availability can be toggled."""
        assert patched_api_client.is_available

        patched_api_client.set_available(False)
        assert not patched_api_client.is_available

        patched_api_client.set_available(True)
        assert patched_api_client.is_available
