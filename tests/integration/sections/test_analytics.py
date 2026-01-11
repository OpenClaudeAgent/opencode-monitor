"""
Integration tests for the Analytics section.

Tests verify that:
- Metrics cards show correct values (sessions, messages, tokens, cache)
- Agents table displays token usage per agent
- Tools table shows invocation statistics
- Period selector works correctly
"""

import pytest

from ..fixtures import process_qt_events
from ..conftest import SECTION_ANALYTICS
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration

# Expected test data values (from MockAPIResponses.realistic_analytics)
EXPECTED_ANALYTICS = {
    "sessions": "42",
    "messages": "1337",
    "tokens": "2.5M",
    "cache_hit": "73%",
    "first_agent": "coordinator",
    "first_agent_messages": "500",
}


class TestAnalyticsSectionMetrics:
    """Test that analytics metrics display correct values."""

    def test_metrics_display_correct_values(self, dashboard_window, qtbot):
        """Verify each analytics metric card shows the injected data."""
        data = MockAPIResponses.realistic_analytics()
        dashboard_window._signals.analytics_updated.emit(data)
        process_qt_events()

        metrics = dashboard_window._analytics._metrics

        assert metrics._cards["sessions"]._value_label.text() == "42"
        assert metrics._cards["messages"]._value_label.text() == "1337"
        assert metrics._cards["tokens"]._value_label.text() == "2.5M"
        assert metrics._cards["cache_hit"]._value_label.text() == "73%"


class TestAnalyticsAgentsTable:
    """Test analytics agent usage table."""

    def test_agents_table_shows_usage_by_agent(self, dashboard_window, qtbot):
        """Verify agents table shows token usage per agent."""
        data = MockAPIResponses.realistic_analytics()
        dashboard_window._signals.analytics_updated.emit(data)
        process_qt_events()

        table = dashboard_window._analytics._agents_table

        # Should have 4 agents
        assert table.rowCount() == 4

        # Check first agent (coordinator)
        assert table.item(0, 0).text() == "coordinator"
        assert table.item(0, 1).text() == "500"  # messages

        # Tokens should be formatted (1200000 -> 1.2M or 1200K)
        tokens_text = table.item(0, 2).text()
        assert "1" in tokens_text and ("M" in tokens_text or "K" in tokens_text)

    def test_agents_table_empty_state(self, dashboard_window, qtbot, click_nav):
        """Empty state when no agent data - table hidden, empty state shown."""
        # Navigate to Analytics section first
        click_nav(dashboard_window, SECTION_ANALYTICS)

        data = MockAPIResponses.realistic_analytics()
        data["agents"] = []
        dashboard_window._signals.analytics_updated.emit(data)
        process_qt_events()

        analytics = dashboard_window._analytics
        # Table should be hidden (not visible in hierarchy)
        assert analytics._agents_table.isHidden()
        # Empty state should NOT be hidden
        assert not analytics._agents_empty.isHidden()


class TestAnalyticsToolsTable:
    """Test analytics tools table."""

    def test_tools_table_shows_tool_usage(self, dashboard_window, qtbot):
        """Verify tools table shows invocation stats."""
        data = MockAPIResponses.realistic_analytics()
        dashboard_window._signals.analytics_updated.emit(data)
        process_qt_events()

        table = dashboard_window._analytics._tools_table

        # Should have 4 tools
        assert table.rowCount() == 4

        # Check first tool (read)
        first_tool_text = table.item(0, 0).text()
        assert "read" in first_tool_text.lower()
        assert table.item(0, 1).text() == "450"  # invocations
        assert table.item(0, 2).text() == "5"  # failures


class TestAnalyticsPeriodSelector:
    """Test period selector interactions."""

    def test_period_selector_exists_with_default_7d(
        self, dashboard_window, qtbot, click_nav
    ):
        """Period selector widget exists with 3 options, default is 7 days."""
        click_nav(dashboard_window, SECTION_ANALYTICS)

        analytics = dashboard_window._analytics

        # Access directly - will fail if missing
        period_control = analytics._period_control
        assert len(period_control._buttons) == 3
        assert analytics.get_current_period() == 7

    def test_period_selector_emits_signal_on_change(self, dashboard_window, qtbot):
        """Changing period emits period_changed signal."""
        analytics = dashboard_window._analytics

        # Wait for signal emission when changing period
        with qtbot.waitSignal(analytics.period_changed, timeout=1000) as blocker:
            analytics._period_control.set_current_index(2)
            process_qt_events()

        assert blocker.args[0] == 30
        assert analytics.get_current_period() == 30
