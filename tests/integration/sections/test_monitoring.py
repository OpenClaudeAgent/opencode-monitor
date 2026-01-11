"""Integration tests for the Monitoring section."""

import pytest

from ..fixtures import MockAPIResponses, process_qt_events

pytestmark = pytest.mark.integration


def wait_for_table_populated(qtbot, table, expected_rows: int, timeout: int = 1000):
    """Wait until table has expected row count."""
    qtbot.waitUntil(lambda: table.rowCount() == expected_rows, timeout=timeout)


def wait_for_metric(qtbot, label, expected: str, timeout: int = 1000):
    """Wait until metric label shows expected value."""
    qtbot.waitUntil(lambda: label.text() == expected, timeout=timeout)


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
    def test_metrics_display_correct_values(self, dashboard_window, qtbot):
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)

        metric_cards = dashboard_window._monitoring._metric_cards
        wait_for_metric(qtbot, metric_cards["instances"]._value_label, "2")

        assert metric_cards["agents"]._value_label.text() == "3"
        assert metric_cards["busy"]._value_label.text() == "2"
        assert metric_cards["waiting"]._value_label.text() == "1"
        assert metric_cards["idle"]._value_label.text() == "1"
        assert metric_cards["todos"]._value_label.text() == "7"

    def test_metrics_update_when_data_changes(self, dashboard_window, qtbot):
        data1 = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data1)

        metric_cards = dashboard_window._monitoring._metric_cards
        wait_for_metric(qtbot, metric_cards["agents"]._value_label, "3")

        data2 = MockAPIResponses.realistic_monitoring()
        data2["agents"] = 10
        data2["busy"] = 8
        dashboard_window._signals.monitoring_updated.emit(data2)

        wait_for_metric(qtbot, metric_cards["agents"]._value_label, "10")
        assert metric_cards["busy"]._value_label.text() == "8"


class TestMonitoringAgentsTable:
    def test_agents_table_shows_all_agents(self, dashboard_window, qtbot):
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)

        table = dashboard_window._monitoring._agents_table
        wait_for_table_populated(qtbot, table, 3)

        assert table.item(0, 0).text() == "Implement User Auth"
        assert table.item(0, 1).text() == "/home/dev/auth-service"
        assert table.item(0, 3).text() == "2"
        assert table.item(0, 4).text() == "4"

    def test_agents_table_shows_status_badges(self, dashboard_window, qtbot):
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)

        table = dashboard_window._monitoring._agents_table
        wait_for_table_populated(qtbot, table, 3)

        badge_widget = table.cellWidget(0, 2)
        assert badge_widget is not None
        assert "BUSY" in badge_widget.text()

        idle_badge = table.cellWidget(2, 2)
        assert idle_badge is not None
        assert "IDLE" in idle_badge.text()

    def test_agents_table_visible_with_data(self, dashboard_window, qtbot):
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)

        table = dashboard_window._monitoring._agents_table
        wait_for_table_populated(qtbot, table, 3)

        monitoring = dashboard_window._monitoring
        assert monitoring._agents_table.isVisible()
        assert not monitoring._agents_empty.isVisible()

    def test_agents_empty_state_when_no_agents(self, dashboard_window, qtbot):
        data = MockAPIResponses.empty_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)
        process_qt_events()

        monitoring = dashboard_window._monitoring
        qtbot.waitUntil(lambda: monitoring._agents_empty.isVisible(), timeout=1000)
        assert not monitoring._agents_table.isVisible()


class TestMonitoringToolsTable:
    def test_tools_table_shows_running_tools(self, dashboard_window, qtbot):
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)

        table = dashboard_window._monitoring._tools_table
        wait_for_table_populated(qtbot, table, 3)

        tool_item = table.item(0, 0)
        tool_widget = table.cellWidget(0, 0)

        if tool_widget is not None and hasattr(tool_widget, "text"):
            tool_text = tool_widget.text().lower()
            assert "edit" in tool_text or "read" in tool_text
        elif tool_item and tool_item.text():
            tool_text = tool_item.text().lower()
            assert "edit" in tool_text or "read" in tool_text
        else:
            pytest.fail("Tool should have either badge widget or text item")

        assert table.item(0, 1).text() == EXPECTED_MONITORING["first_agent_title"]
        assert table.item(0, 2).text() == "src/auth/login.py"

    def test_tools_table_shows_duration(self, dashboard_window, qtbot):
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)

        table = dashboard_window._monitoring._tools_table
        wait_for_table_populated(qtbot, table, 3)

        duration_col = 3
        first_duration = table.item(0, duration_col).text()

        assert first_duration, "Duration should not be empty"
        has_time_indicator = (
            any(c.isdigit() for c in first_duration) or first_duration == "running"
        )
        assert has_time_indicator

    def test_tools_empty_state_when_no_tools(self, dashboard_window, qtbot):
        data = MockAPIResponses.empty_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)
        process_qt_events()

        monitoring = dashboard_window._monitoring
        qtbot.waitUntil(lambda: monitoring._tools_empty.isVisible(), timeout=1000)
        assert not monitoring._tools_table.isVisible()


class TestMonitoringWaitingTable:
    def test_waiting_table_shows_pending_questions(self, dashboard_window, qtbot):
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)

        table = dashboard_window._monitoring._waiting_table
        wait_for_table_populated(qtbot, table, 1)

        title_text = table.item(0, 0).text()
        assert title_text == EXPECTED_MONITORING["waiting_title"]

        question_text = table.item(0, 1).text()
        assert "deploy" in question_text.lower()

        options_text = table.item(0, 2).text()
        assert options_text
        assert "Yes" in options_text or "|" in options_text

        context_text = table.item(0, 3).text()
        assert EXPECTED_MONITORING["waiting_context"] in context_text

    def test_waiting_empty_state_when_none_waiting(self, dashboard_window, qtbot):
        data = MockAPIResponses.realistic_monitoring()
        data["waiting_data"] = []
        data["waiting"] = 0
        dashboard_window._signals.monitoring_updated.emit(data)
        process_qt_events()

        monitoring = dashboard_window._monitoring
        qtbot.waitUntil(lambda: monitoring._waiting_empty.isVisible(), timeout=1000)
        assert not monitoring._waiting_table.isVisible()
