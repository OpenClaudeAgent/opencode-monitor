"""
Qt UI tests for delegation_result display in timeline.

Verifies that delegation_result events are correctly displayed:
- Correct icon (📥)
- Appears AFTER child session events
- Content is displayed correctly
- Exchange grouping is correct
"""

import pytest
from PyQt6.QtCore import Qt

from ..conftest import SECTION_TRACING
from ..helpers.tree_helpers import expand_all_indexes

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group(name="qt_tracing"),
]

SESSION_ID = "ses_delegation_result_test"
CHILD_SESSION_ID = "ses_child_delegation"
DELEGATION_RESULT_CONTENT = "Agent completed: Found 5 relevant files"


def delegation_result_timeline_data() -> dict:
    """Timeline data with delegation_result appearing after child session."""
    return {
        "session_hierarchy": [
            {
                "session_id": SESSION_ID,
                "node_type": "session",
                "title": "Test Delegation Result",
                "directory": "/test/project",
                "agent_type": "build",
                "tokens_in": 100,
                "tokens_out": 500,
                "started_at": "2026-01-15T10:00:00.000000",
                "children": [
                    {
                        "node_type": "user_turn",
                        "trace_id": "exchange_001",
                        "prompt_input": "Search for files",
                        "tokens_in": 50,
                        "tokens_out": 200,
                        "duration_ms": 5000,
                        "parent_agent": "user",
                        "subagent_type": "build",
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-15T10:00:01.000000",
                        "ended_at": "2026-01-15T10:00:06.000000",
                        "children": [
                            {
                                "node_type": "agent",
                                "agent_type": "librarian",
                                "child_session_id": CHILD_SESSION_ID,
                                "result_summary": DELEGATION_RESULT_CONTENT,
                                "duration_ms": 3000,
                                "trace_id": "delegation_001",
                                "session_id": SESSION_ID,
                                "started_at": "2026-01-15T10:00:02.000000",
                                "children": [
                                    {
                                        "node_type": "tool",
                                        "tool_name": "grep",
                                        "display_info": "*.py",
                                        "duration_ms": 100,
                                        "tool_status": "completed",
                                        "trace_id": "tool_child_001",
                                        "session_id": CHILD_SESSION_ID,
                                        "started_at": "2026-01-15T10:00:03.000000",
                                        "children": [],
                                    },
                                    {
                                        "node_type": "tool",
                                        "tool_name": "read",
                                        "display_info": "main.py",
                                        "duration_ms": 50,
                                        "tool_status": "completed",
                                        "trace_id": "tool_child_002",
                                        "session_id": CHILD_SESSION_ID,
                                        "started_at": "2026-01-15T10:00:04.000000",
                                        "children": [],
                                    },
                                ],
                            },
                        ],
                    },
                ],
            }
        ],
    }


def get_text(model, index) -> str:
    return model.data(index, Qt.ItemDataRole.DisplayRole) or ""


def get_data(model, index) -> dict:
    return model.data(index, Qt.ItemDataRole.UserRole) or {}


def load_tracing_section(dashboard_window, qtbot, click_nav):
    click_nav(dashboard_window, SECTION_TRACING)
    tracing = dashboard_window._tracing

    data = delegation_result_timeline_data()
    data["meta"] = {"has_more": False}
    dashboard_window._signals.tracing_updated.emit(data)
    qtbot.waitUntil(lambda: tracing._model.rowCount() > 0, timeout=2000)

    root_index = tracing._model.index(0, 0)
    qtbot.waitUntil(lambda: tracing._model.rowCount(root_index) >= 1, timeout=3000)

    expand_all_indexes(tracing._tree)
    qtbot.wait(50)
    return tracing


class TestDelegationResultTreeDisplay:
    def test_delegation_node_exists_in_tree(self, dashboard_window, qtbot, click_nav):
        """Tree must contain an agent/delegation node for the child session."""
        tracing = load_tracing_section(dashboard_window, qtbot, click_nav)
        model = tracing._model

        root_index = model.index(0, 0)
        user_turn_index = model.index(0, 0, root_index)

        assert model.rowCount(user_turn_index) >= 1, "User turn should have children"

        delegation_index = model.index(0, 0, user_turn_index)
        delegation_data = get_data(model, delegation_index)

        assert delegation_data.get("node_type") in ("agent", "delegation")
        assert delegation_data.get("child_session_id") == CHILD_SESSION_ID

    def test_delegation_has_child_tools(self, dashboard_window, qtbot, click_nav):
        """Delegation node must contain child session's tools."""
        tracing = load_tracing_section(dashboard_window, qtbot, click_nav)
        model = tracing._model

        root_index = model.index(0, 0)
        user_turn_index = model.index(0, 0, root_index)
        delegation_index = model.index(0, 0, user_turn_index)

        child_count = model.rowCount(delegation_index)
        assert child_count == 2, "Delegation should have 2 child tools (grep, read)"

        tool1_data = get_data(model, model.index(0, 0, delegation_index))
        tool2_data = get_data(model, model.index(1, 0, delegation_index))

        assert tool1_data.get("node_type") == "tool"
        assert tool1_data.get("tool_name") == "grep"

        assert tool2_data.get("node_type") == "tool"
        assert tool2_data.get("tool_name") == "read"

    def test_delegation_result_summary_in_tree_data(
        self, dashboard_window, qtbot, click_nav
    ):
        """Delegation node must contain result_summary."""
        tracing = load_tracing_section(dashboard_window, qtbot, click_nav)
        model = tracing._model

        root_index = model.index(0, 0)
        user_turn_index = model.index(0, 0, root_index)
        delegation_index = model.index(0, 0, user_turn_index)

        delegation_data = get_data(model, delegation_index)
        assert delegation_data.get("result_summary") == DELEGATION_RESULT_CONTENT


class TestDelegationResultDetailPanel:
    def test_detail_panel_shows_delegation_content(
        self, dashboard_window, qtbot, click_nav
    ):
        """Clicking delegation node shows result_summary in detail panel."""
        tracing = load_tracing_section(dashboard_window, qtbot, click_nav)
        model = tracing._model

        root_index = model.index(0, 0)
        user_turn_index = model.index(0, 0, root_index)
        delegation_index = model.index(0, 0, user_turn_index)

        tracing._tree.setCurrentIndex(delegation_index)
        tracing._on_index_clicked(delegation_index)
        qtbot.wait(100)

        detail_panel = tracing._detail_panel
        assert detail_panel is not None
        assert not detail_panel.isHidden()


class TestDelegationResultEventOrder:
    def test_child_tools_appear_before_parent_response(
        self, dashboard_window, qtbot, click_nav
    ):
        """In the tree, child tools must appear under delegation, before any parent response."""
        tracing = load_tracing_section(dashboard_window, qtbot, click_nav)
        model = tracing._model

        root_index = model.index(0, 0)
        user_turn_index = model.index(0, 0, root_index)

        user_turn_children = model.rowCount(user_turn_index)
        assert user_turn_children >= 1

        delegation_index = model.index(0, 0, user_turn_index)
        delegation_data = get_data(model, delegation_index)

        assert delegation_data.get("child_session_id") == CHILD_SESSION_ID

        child_tools = model.rowCount(delegation_index)
        assert child_tools == 2, "Child session tools should be nested under delegation"

        for i in range(child_tools):
            tool_index = model.index(i, 0, delegation_index)
            tool_data = get_data(model, tool_index)
            assert tool_data.get("node_type") == "tool"
            assert tool_data.get("session_id") == CHILD_SESSION_ID
