"""
Integration tests for data robustness.

Tests verify that:
- Dashboard handles null/missing fields gracefully
- Extreme values don't freeze the UI
- Unicode/emoji content displays correctly
"""

import pytest

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


class TestRobustnessNullData:
    """Test dashboard handles null/missing fields gracefully."""

    def test_null_data_fields_no_crash(self, dashboard_window, qtbot):
        """Dashboard handles null/missing fields gracefully."""
        # Monitoring with null fields
        data_with_nulls = {
            "instances": None,
            "agents": 0,
            "busy": None,
            "waiting": 0,
            "idle": None,
            "todos": None,
            "agents_data": [
                {
                    "agent_id": "agent-x",
                    "title": None,
                    "dir": None,
                    "status": "idle",
                    "tools": None,
                    "todos_total": None,
                }
            ],
            "tools_data": None,
            "waiting_data": None,
        }

        # Should not crash
        dashboard_window._signals.monitoring_updated.emit(data_with_nulls)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert dashboard_window.isVisible()

    def test_partial_data_no_crash(self, dashboard_window, qtbot, click_nav):
        """Dashboard handles partial data (from MockAPIResponses)."""
        data = MockAPIResponses.partial_data()

        # Navigate to tracing and emit partial data
        click_nav(dashboard_window, SECTION_TRACING)
        dashboard_window._signals.tracing_updated.emit(
            {
                "traces": [],
                "sessions": data.get("sessions", []),
                "session_hierarchy": [],
                "total_traces": 0,
                "unique_agents": 0,
                "total_duration_ms": 0,
            }
        )
        qtbot.wait(SIGNAL_WAIT_MS)

        assert dashboard_window.isVisible()

    def test_empty_lists_vs_none(self, dashboard_window, qtbot):
        """Dashboard distinguishes between empty lists and None."""
        # Empty lists = no data, valid state
        empty_list_data = {
            "instances": 0,
            "agents": 0,
            "busy": 0,
            "waiting": 0,
            "idle": 0,
            "todos": 0,
            "agents_data": [],
            "tools_data": [],
            "waiting_data": [],
        }

        dashboard_window._signals.monitoring_updated.emit(empty_list_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        monitoring = dashboard_window._monitoring
        # Empty state should show for agents
        assert (
            monitoring._agents_empty.isVisible()
            or not monitoring._agents_table.isVisible()
        )


class TestRobustnessExtremeValues:
    """Test dashboard handles extreme values without freezing."""

    def test_extreme_values_no_freeze(self, dashboard_window, qtbot):
        """Dashboard handles very large numbers without freezing."""
        data = MockAPIResponses.realistic_monitoring()
        data["agents"] = 999_999
        data["todos"] = 999_999_999

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Should display (possibly formatted as "999K" or "999M")
        metrics = dashboard_window._monitoring._metrics
        agents_text = metrics._cards["agents"]._value_label.text()
        assert agents_text  # Not empty

    def test_extreme_data_fixture(self, dashboard_window, qtbot, click_nav):
        """Dashboard handles extreme_data fixture without crash."""
        data = MockAPIResponses.extreme_data()

        # Navigate to tracing
        click_nav(dashboard_window, SECTION_TRACING)

        tracing_data = {
            "traces": data.get("traces", [])[:10],  # Limit for test speed
            "sessions": data.get("sessions", []),
            "session_hierarchy": [],
            "total_traces": len(data.get("traces", [])),
            "unique_agents": 4,
            "total_duration_ms": 1_000_000,
        }

        dashboard_window._signals.tracing_updated.emit(tracing_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert dashboard_window.isVisible()

    def test_very_long_strings(self, dashboard_window, qtbot):
        """Dashboard handles very long strings without crash."""
        data = MockAPIResponses.realistic_monitoring()
        # Agent with very long title
        data["agents_data"][0]["title"] = "A" * 1000

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Table should have exactly 3 agents from mock data (possibly with truncated title)
        table = dashboard_window._monitoring._agents_table
        assert table.rowCount() == 3, (
            f"Expected 3 agents from mock data, got {table.rowCount()}"
        )


class TestRobustnessUnicode:
    """Test dashboard handles unicode/emoji correctly."""

    def test_unicode_in_agent_title(self, dashboard_window, qtbot):
        """Dashboard handles unicode in agent titles."""
        data = MockAPIResponses.realistic_monitoring()
        data["agents_data"][0]["title"] = "🚀 Deploy émojis & spëcial çhars"

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        table = dashboard_window._monitoring._agents_table
        title = table.item(0, 0).text()
        # Should contain either the emoji or the text
        assert "🚀" in title or "Deploy" in title

    def test_unicode_in_directory_path(self, dashboard_window, qtbot):
        """Dashboard handles unicode in directory paths."""
        data = MockAPIResponses.realistic_monitoring()
        data["agents_data"][0]["dir"] = "/home/用户/项目"

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        table = dashboard_window._monitoring._agents_table
        # Should not crash, path should be displayed
        assert table.rowCount() >= 1

    def test_unicode_in_question_text(self, dashboard_window, qtbot):
        """Dashboard handles unicode in waiting questions."""
        data = MockAPIResponses.realistic_monitoring()
        data["waiting_data"][0]["question"] = "¿Está seguro? 日本語テスト 🎉"

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        table = dashboard_window._monitoring._waiting_table
        # Should not crash
        assert table.rowCount() >= 1
