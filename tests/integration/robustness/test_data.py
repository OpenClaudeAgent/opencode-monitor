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

        # --- Scenario 1: Null fields in monitoring data ---
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

        dashboard_window._signals.monitoring_updated.emit(data_with_nulls)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Should have 1 agent rendered despite null fields
        assert monitoring._agents_table.rowCount() == 1
        # Agent ID should be displayed
        assert monitoring._agents_table.item(0, 0) is not None

        # --- Scenario 2: Partial data from fixture ---
        partial_data = MockAPIResponses.partial_data()
        click_nav(dashboard_window, SECTION_TRACING)

        tracing_data = {"session_hierarchy": []}
        dashboard_window._signals.tracing_updated.emit(tracing_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Tracing section should show empty state (no session hierarchy)
        tracing = dashboard_window._tracing
        assert tracing._empty.isVisible() or len(tracing._session_hierarchy) == 0

        # --- Scenario 3: Empty lists (valid state, not null) ---
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

        # Empty lists should show empty state for agents
        assert monitoring._agents_table.rowCount() == 0
        # Empty state visible OR table hidden (implementation-dependent)
        assert (
            monitoring._agents_empty.isVisible()
            or not monitoring._agents_table.isVisible()
        )

    def test_handles_extreme_values(self, dashboard_window, qtbot, click_nav):
        """Dashboard handles large numbers, extreme data, and long strings."""
        monitoring = dashboard_window._monitoring

        # --- Scenario 1: Very large numbers ---
        data = MockAPIResponses.realistic_monitoring()
        data["agents"] = 999_999
        data["todos"] = 999_999_999

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Metrics should display formatted values (999999 or "999K" or similar)
        metric_cards = monitoring._metric_cards
        agents_text = metric_cards["agents"]._value_label.text()
        todos_text = metric_cards["todos"]._value_label.text()
        assert "999" in agents_text, (
            f"Agents metric should show 999K/999999, got: {agents_text}"
        )
        assert "999" in todos_text, (
            f"Todos metric should show 999M/999999999, got: {todos_text}"
        )

        # --- Scenario 2: Extreme data fixture (stress test) ---
        click_nav(dashboard_window, SECTION_TRACING)

        # Create 10 session hierarchy items for stress test
        session_hierarchy = [
            {
                "session_id": f"sess-extreme-{i:03d}",
                "node_type": "session",
                "title": f"Extreme Session {i}",
                "directory": "/home/dev/my-project",
                "created_at": "2024-01-01T00:00:00",
                "status": "completed",
                "duration_ms": 1_000_000,
                "tokens_in": 999_999,
                "tokens_out": 999_999,
                "children": [],
            }
            for i in range(10)
        ]

        tracing_data = {"session_hierarchy": session_hierarchy}

        dashboard_window._signals.tracing_updated.emit(tracing_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Tracing should render exactly 10 sessions
        tracing = dashboard_window._tracing
        assert len(tracing._session_hierarchy) == 10
        assert tracing._tree.topLevelItemCount() == 10
        # Dashboard should remain responsive
        assert dashboard_window.isVisible()

        # --- Scenario 3: Very long strings ---
        data = MockAPIResponses.realistic_monitoring()
        long_title = "A" * 1000
        data["agents_data"][0]["title"] = long_title

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Table should render 3 agents (long title may be truncated)
        table = monitoring._agents_table
        assert table.rowCount() == 3
        # Cell should contain the long title (possibly truncated but still "A"s)
        cell_text = table.item(0, 0).text()
        assert "A" in cell_text, f"Expected long title with A's, got: {cell_text}"

    def test_handles_unicode_content(self, dashboard_window, qtbot):
        """Dashboard handles unicode and emoji in all text fields."""
        monitoring = dashboard_window._monitoring

        # --- Scenario 1: Emoji in agent title ---
        data = MockAPIResponses.realistic_monitoring()
        data["agents_data"][0]["title"] = "🚀 Deploy émojis & spëcial çhars"

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        table = monitoring._agents_table
        title = table.item(0, 0).text()
        # Should contain either emoji or text (font-dependent)
        assert "🚀" in title or "Deploy" in title
        assert table.rowCount() == 3

        # --- Scenario 2: Unicode in directory path (CJK characters) ---
        data["agents_data"][0]["dir"] = "/home/用户/项目"

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Should render correctly
        assert table.rowCount() == 3
        # Directory column should have the CJK path
        dir_item = table.item(0, 1)
        assert dir_item is not None
        dir_text = dir_item.text()
        assert "/home/用户/项目" in dir_text or "用户" in dir_text, (
            f"Expected CJK path, got: {dir_text}"
        )

        # --- Scenario 3: Unicode in waiting question ---
        data["waiting_data"][0]["question"] = "¿Está seguro? 日本語テスト 🎉"

        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        waiting_table = monitoring._waiting_table
        # Should have exactly 1 waiting item (from realistic_monitoring fixture)
        assert waiting_table.rowCount() == 1
        # Question should be displayed
        question_item = waiting_table.item(0, 1)
        assert question_item is not None
        question_text = question_item.text()
        # Should contain part of unicode text
        assert (
            "¿" in question_text or "日本語" in question_text or "🎉" in question_text
        )
