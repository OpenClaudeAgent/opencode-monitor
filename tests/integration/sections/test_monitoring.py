"""
Integration tests for the Monitoring section.

Tests verify that:
- Metrics cards show correct values
- Agents table displays all agents with correct data
- Tools table shows running tools
- Waiting table shows agents awaiting user response
- Empty states appear when appropriate
"""

import pytest

from ..conftest import SIGNAL_WAIT_MS
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration

# Expected test data values (from MockAPIResponses.realistic_monitoring)
EXPECTED_MONITORING = {
    "instances": 2,
    "agents": 3,
    "busy": 2,
    "waiting": 1,
    "idle": 1,
    "todos": 7,
    "first_agent_title": "Implement User Auth",
    "first_agent_dir": "/home/dev/auth-service",
    "first_agent_tools_count": "2",
    "first_agent_todos": "4",
    "first_tool_name": "edit",
    "first_tool_elapsed_ms": 1250,
    "waiting_title": "Deploy to Production",
    "waiting_context": "infra-team @ main",
}


class TestMonitoringSectionMetrics:
    """Test that monitoring metrics display correct values."""

    def test_metrics_display_correct_values(self, dashboard_window, qtbot):
        """Verify each metric card shows the injected data."""
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        metrics = dashboard_window._monitoring._metrics

        # Check each metric card displays the correct value
        assert metrics._cards["instances"]._value_label.text() == "2", (
            f"Expected instances=2, got {metrics._cards['instances']._value_label.text()}"
        )
        assert metrics._cards["agents"]._value_label.text() == "3", (
            f"Expected agents=3, got {metrics._cards['agents']._value_label.text()}"
        )
        assert metrics._cards["busy"]._value_label.text() == "2", (
            f"Expected busy=2, got {metrics._cards['busy']._value_label.text()}"
        )
        assert metrics._cards["waiting"]._value_label.text() == "1", (
            f"Expected waiting=1, got {metrics._cards['waiting']._value_label.text()}"
        )
        assert metrics._cards["idle"]._value_label.text() == "1", (
            f"Expected idle=1, got {metrics._cards['idle']._value_label.text()}"
        )
        assert metrics._cards["todos"]._value_label.text() == "7", (
            f"Expected todos=7, got {metrics._cards['todos']._value_label.text()}"
        )

    def test_metrics_update_when_data_changes(self, dashboard_window, qtbot):
        """Verify metrics update when new data arrives."""
        # Initial data
        data1 = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data1)
        qtbot.wait(50)

        # Verify initial state
        metrics = dashboard_window._monitoring._metrics
        assert metrics._cards["agents"]._value_label.text() == "3"

        # Updated data with more agents
        data2 = MockAPIResponses.realistic_monitoring()
        data2["agents"] = 10
        data2["busy"] = 8
        dashboard_window._signals.monitoring_updated.emit(data2)
        qtbot.wait(50)

        # Verify updated values
        assert metrics._cards["agents"]._value_label.text() == "10"
        assert metrics._cards["busy"]._value_label.text() == "8"


class TestMonitoringAgentsTable:
    """Test that agents table displays correct content."""

    def test_agents_table_shows_all_agents(self, dashboard_window, qtbot):
        """Verify agents table contains all agents from data."""
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        table = dashboard_window._monitoring._agents_table

        # Table should have 3 rows (3 agents)
        assert table.rowCount() == 3

        # Verify first agent data
        assert table.item(0, 0).text() == "Implement User Auth"
        assert table.item(0, 1).text() == "/home/dev/auth-service"
        assert table.item(0, 3).text() == "2"  # 2 tools
        assert table.item(0, 4).text() == "4"  # 4 todos

    def test_agents_table_shows_status_badges(self, dashboard_window, qtbot):
        """Verify status column contains StatusBadge widgets."""
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        table = dashboard_window._monitoring._agents_table

        # Check first agent has BUSY badge
        badge_widget = table.cellWidget(0, 2)
        assert badge_widget is not None
        assert "BUSY" in badge_widget.text()

        # Check third agent has IDLE badge
        idle_badge = table.cellWidget(2, 2)
        assert idle_badge is not None
        assert "IDLE" in idle_badge.text()

    def test_agents_table_visible_with_data(self, dashboard_window, qtbot):
        """Table is visible when data exists, empty state is hidden."""
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        monitoring = dashboard_window._monitoring
        assert monitoring._agents_table.isVisible()
        assert not monitoring._agents_empty.isVisible()

    def test_agents_empty_state_when_no_agents(self, dashboard_window, qtbot):
        """Empty state appears when no agents."""
        data = MockAPIResponses.empty_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        monitoring = dashboard_window._monitoring
        assert not monitoring._agents_table.isVisible()
        assert monitoring._agents_empty.isVisible()


class TestMonitoringToolsTable:
    """Test that tools table displays running tools correctly."""

    def test_tools_table_shows_running_tools(self, dashboard_window, qtbot):
        """Verify tools table contains all running tools."""
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        table = dashboard_window._monitoring._tools_table

        # Should have 3 tools
        assert table.rowCount() == 3

        # Check tool data - verify tool name is present
        tool_item = table.item(0, 0)
        tool_widget = table.cellWidget(0, 0)

        if tool_item:
            tool_text = tool_item.text().lower()
            assert "edit" in tool_text or "read" in tool_text, (
                f"Expected tool name (edit/read), got: {tool_text}"
            )
        else:
            # Tool might be displayed as widget instead of text item
            assert tool_widget is not None, (
                "Tool should have either text item or widget"
            )

        assert table.item(0, 1).text() == EXPECTED_MONITORING["first_agent_title"]
        assert table.item(0, 2).text() == "src/auth/login.py"

    def test_tools_table_shows_duration(self, dashboard_window, qtbot):
        """Verify duration column shows formatted time."""
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        table = dashboard_window._monitoring._tools_table

        # Check duration formatting (1250ms = 1s, 5400ms = 5s)
        duration_col = 3
        first_duration = table.item(0, duration_col).text()

        # Duration should not be empty
        assert first_duration, "Duration should not be empty"
        # Duration format: "Xs", "Xms", "Xm Ys", or "running"
        has_time_indicator = (
            any(c.isdigit() for c in first_duration) or first_duration == "running"
        )
        assert has_time_indicator, f"Expected time format, got: {first_duration}"

    def test_tools_empty_state_when_no_tools(self, dashboard_window, qtbot):
        """Empty state appears when no tools running."""
        data = MockAPIResponses.empty_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        monitoring = dashboard_window._monitoring
        assert not monitoring._tools_table.isVisible()
        assert monitoring._tools_empty.isVisible()


class TestMonitoringWaitingTable:
    """Test that waiting table displays agents waiting for response."""

    def test_waiting_table_shows_pending_questions(self, dashboard_window, qtbot):
        """Verify waiting table contains agents waiting for user input."""
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        table = dashboard_window._monitoring._waiting_table

        # Should have 1 waiting agent
        assert table.rowCount() == 1

        # Verify waiting agent data
        title_text = table.item(0, 0).text()
        assert title_text == EXPECTED_MONITORING["waiting_title"], (
            f"Expected '{EXPECTED_MONITORING['waiting_title']}', got: {title_text}"
        )

        # Question is truncated to 80 chars
        question_text = table.item(0, 1).text()
        assert "deploy" in question_text.lower(), (
            f"Expected 'deploy' in question, got: {question_text}"
        )

        # Options should contain response choices
        options_text = table.item(0, 2).text()
        assert options_text, "Options should not be empty"
        # Either has "Yes" or is the options string
        assert "Yes" in options_text or "|" in options_text, (
            f"Expected options text, got: {options_text}"
        )

        # Context
        context_text = table.item(0, 3).text()
        assert EXPECTED_MONITORING["waiting_context"] in context_text, (
            f"Expected '{EXPECTED_MONITORING['waiting_context']}' in context, got: {context_text}"
        )

    def test_waiting_empty_state_when_none_waiting(self, dashboard_window, qtbot):
        """Empty state appears when no agents waiting."""
        data = MockAPIResponses.realistic_monitoring()
        data["waiting_data"] = []
        data["waiting"] = 0
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        monitoring = dashboard_window._monitoring
        assert not monitoring._waiting_table.isVisible()
        assert monitoring._waiting_empty.isVisible()
