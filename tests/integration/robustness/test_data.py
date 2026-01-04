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


class TestDataRobustness:
    """Test dashboard handles edge cases in data gracefully."""

    def test_handles_null_and_partial_data(self, dashboard_window, qtbot, click_nav):
        """Dashboard handles null fields, partial data, and empty lists gracefully."""
        monitoring = dashboard_window._monitoring

        # Scenario 1: Null fields in monitoring data
        data_with_nulls = MockAPIResponses.monitoring_with_nulls()
        dashboard_window._signals.monitoring_updated.emit(data_with_nulls)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Should have 1 agent rendered despite null fields
        assert monitoring._agents_table.rowCount() == 1
        assert monitoring._agents_table.item(0, 0) is not None

        # Scenario 2: Empty tracing (partial data)
        click_nav(dashboard_window, SECTION_TRACING)
        dashboard_window._signals.tracing_updated.emit({"session_hierarchy": []})
        qtbot.wait(SIGNAL_WAIT_MS)

        tracing = dashboard_window._tracing
        assert tracing._empty.isVisible() or len(tracing._session_hierarchy) == 0

        # Scenario 3: Empty lists (valid state)
        empty_data = MockAPIResponses.empty_lists_monitoring()
        dashboard_window._signals.monitoring_updated.emit(empty_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert monitoring._agents_table.rowCount() == 0
        assert (
            monitoring._agents_empty.isVisible()
            or not monitoring._agents_table.isVisible()
        )

    @pytest.mark.parametrize(
        "field,extreme_value",
        [
            ("agents", 999_999),
            ("todos", 999_999_999),
        ],
    )
    def test_handles_extreme_numbers(
        self, dashboard_window, qtbot, field, extreme_value
    ):
        """Dashboard handles very large numbers in metrics."""
        monitoring = dashboard_window._monitoring
        data = MockAPIResponses.realistic_monitoring()
        data[field] = extreme_value

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Metric should display formatted value containing "999"
        metric_text = monitoring._metrics._cards[field]._value_label.text()
        assert "999" in metric_text, (
            f"{field} should show 999K/999M, got: {metric_text}"
        )

    def test_handles_extreme_session_count(self, dashboard_window, qtbot, click_nav):
        """Dashboard handles many sessions in tracing tree."""
        click_nav(dashboard_window, SECTION_TRACING)

        # Create 10 sessions for stress test
        session_hierarchy = [
            {
                "session_id": f"sess-extreme-{i:03d}",
                "node_type": "session",
                "title": f"Extreme Session {i}",
                "directory": "/home/dev/my-project",
                "children": [],
            }
            for i in range(10)
        ]

        dashboard_window._signals.tracing_updated.emit(
            {"session_hierarchy": session_hierarchy}
        )
        qtbot.wait(SIGNAL_WAIT_MS)

        tracing = dashboard_window._tracing
        assert len(tracing._session_hierarchy) == 10
        assert tracing._tree.topLevelItemCount() == 10
        assert dashboard_window.isVisible()

    def test_handles_long_strings(self, dashboard_window, qtbot):
        """Dashboard handles very long strings in fields."""
        monitoring = dashboard_window._monitoring
        data = MockAPIResponses.realistic_monitoring()
        long_title = "A" * 1000
        data["agents_data"][0]["title"] = long_title

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert monitoring._agents_table.rowCount() == 3
        cell_text = monitoring._agents_table.item(0, 0).text()
        assert "A" in cell_text

    @pytest.mark.parametrize(
        "field,unicode_value,expected_substr",
        [
            ("title", "🚀 Deploy émojis & spëcial çhars", "🚀"),
            ("dir", "/home/用户/项目", "用户"),
        ],
    )
    def test_handles_unicode_in_agents(
        self, dashboard_window, qtbot, field, unicode_value, expected_substr
    ):
        """Dashboard handles unicode and emoji in agent data fields."""
        monitoring = dashboard_window._monitoring
        data = MockAPIResponses.realistic_monitoring()
        data["agents_data"][0][field] = unicode_value

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert monitoring._agents_table.rowCount() == 3
        # Get the correct column based on field
        col = 0 if field == "title" else 1
        cell_text = monitoring._agents_table.item(0, col).text()
        assert expected_substr in cell_text or unicode_value in cell_text

    def test_handles_unicode_in_waiting(self, dashboard_window, qtbot):
        """Dashboard handles unicode in waiting questions."""
        monitoring = dashboard_window._monitoring
        data = MockAPIResponses.realistic_monitoring()
        data["waiting_data"][0]["question"] = "¿Está seguro? 日本語テスト 🎉"

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert monitoring._waiting_table.rowCount() == 1
        question_text = monitoring._waiting_table.item(0, 1).text()
        assert any(c in question_text for c in ["¿", "日本語", "🎉"])
