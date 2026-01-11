"""Integration tests for API error handling and monitoring state variants."""

import pytest

from ..conftest import SECTION_MONITORING, SECTION_TRACING
from ..fixtures import MockAPIResponses, process_qt_events

pytestmark = pytest.mark.integration


def wait_for_metric(qtbot, label, expected: str, timeout: int = 1000):
    qtbot.waitUntil(lambda: label.text() == expected, timeout=timeout)


def wait_for_table(qtbot, table, expected_rows: int, timeout: int = 1000):
    qtbot.waitUntil(lambda: table.rowCount() == expected_rows, timeout=timeout)


class TestAPIErrorHandling:
    @pytest.mark.parametrize(
        "section,signal_name,malformed_data",
        [
            pytest.param(
                SECTION_MONITORING,
                "monitoring_updated",
                {},
                id="api_unavailable_empty_dict",
            ),
            pytest.param(
                SECTION_TRACING,
                "tracing_updated",
                {"session_hierarchy": []},
                id="malformed_types_and_nulls",
            ),
            pytest.param(
                SECTION_MONITORING,
                "monitoring_updated",
                {
                    "instances": "not_an_int",
                    "agents_data": None,
                },
                id="malformed_monitoring_types",
            ),
        ],
    )
    def test_malformed_data_resilience(
        self, dashboard_window, qtbot, click_nav, section, signal_name, malformed_data
    ):
        click_nav(dashboard_window, section)

        signal = getattr(dashboard_window._signals, signal_name)
        signal.emit(malformed_data)
        process_qt_events()

        assert dashboard_window.isVisible()
        assert dashboard_window.isEnabled()
        assert dashboard_window.isActiveWindow() or not dashboard_window.isMinimized()

    def test_signals_after_close_are_safe(self, dashboard_window, qtbot):
        was_visible = dashboard_window.isVisible()
        assert was_visible

        dashboard_window.close()
        qtbot.waitUntil(lambda: not dashboard_window.isVisible(), timeout=1000)

        dashboard_window._signals.monitoring_updated.emit({})
        dashboard_window._signals.analytics_updated.emit({})
        dashboard_window._signals.tracing_updated.emit({})

        assert not dashboard_window.isVisible()


class TestMonitoringStateVariants:
    def test_all_idle_state(self, dashboard_window, qtbot):
        data = MockAPIResponses.realistic_monitoring_all_idle()
        dashboard_window._signals.monitoring_updated.emit(data)

        monitoring = dashboard_window._monitoring
        wait_for_metric(qtbot, monitoring._metric_cards["idle"]._value_label, "4")

        assert monitoring._metric_cards["busy"]._value_label.text() == "0"

        table = monitoring._agents_table
        for row in range(table.rowCount()):
            badge = table.cellWidget(row, 2)
            if badge:
                assert "IDLE" in badge.text()

    def test_all_waiting_state(self, dashboard_window, qtbot):
        data = MockAPIResponses.realistic_monitoring_all_waiting()
        dashboard_window._signals.monitoring_updated.emit(data)

        monitoring = dashboard_window._monitoring
        wait_for_metric(qtbot, monitoring._metric_cards["waiting"]._value_label, "3")

        waiting_table = monitoring._waiting_table
        wait_for_table(qtbot, waiting_table, 3)

    def test_error_state_agents(self, dashboard_window, qtbot):
        data = MockAPIResponses.realistic_monitoring_error()
        dashboard_window._signals.monitoring_updated.emit(data)

        monitoring = dashboard_window._monitoring
        wait_for_metric(qtbot, monitoring._metric_cards["busy"]._value_label, "1")

        assert dashboard_window.isVisible()
        assert monitoring._metric_cards["idle"]._value_label.text() == "1"

        table = monitoring._agents_table
        wait_for_table(qtbot, table, 4)
