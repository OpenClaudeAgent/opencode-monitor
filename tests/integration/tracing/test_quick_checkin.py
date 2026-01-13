import pytest
from PyQt6.QtCore import Qt, QModelIndex

from ..conftest import SECTION_TRACING
from ..helpers.tree_helpers import (
    get_all_tree_indexes,
    get_index_data,
    find_indexes_by_node_type,
    find_indexes_by_tool_name,
    expand_all_indexes,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group(name="qt_tracing"),
]


SESSION_ID = "ses_quick_checkin_001"
SESSION_TITLE = "Quick check-in"
SESSION_DIRECTORY = "/Users/test/project"
SESSION_PROJECT_NAME = "project"
SESSION_TOKENS_IN = 129
SESSION_TOKENS_OUT = 9101
SESSION_CACHE_READ = 417959

UT1_TRACE_ID = "exchange_msg_001"
UT1_PROMPT = "Salut, est-ce que ça va ?"
UT1_AGENT = "plan"
UT1_TOKENS_IN = 8
UT1_TOKENS_OUT = 305
UT1_DURATION_MS = 14708
UT1_TOOL_COUNT = 0

UT2_TRACE_ID = "exchange_msg_002"
UT2_PROMPT = "Cherche une API météo"
UT2_AGENT = "plan"
UT2_TOKENS_IN = 12
UT2_TOKENS_OUT = 558
UT2_DURATION_MS = 4673
UT2_TOOL_COUNT = 2
UT2_TOOL1_NAME = "webfetch"
UT2_TOOL1_DISPLAY = "https://www.weatherapi.com/"
UT2_TOOL1_ICON = "🌐"
UT2_TOOL1_DURATION_MS = 258
UT2_TOOL2_NAME = "webfetch"
UT2_TOOL2_DISPLAY = "https://openweathermap.org/api"
UT2_TOOL2_ICON = "🌐"
UT2_TOOL2_DURATION_MS = 173

UT3_TRACE_ID = "exchange_msg_003"
UT3_PROMPT = "Crée un fichier test"
UT3_AGENT = "plan"
UT3_TOKENS_IN = 11
UT3_TOKENS_OUT = 143
UT3_DURATION_MS = 3918
UT3_TOOL_COUNT = 1
UT3_TOOL1_NAME = "bash"
UT3_TOOL1_DISPLAY = "touch /tmp/test.txt"
UT3_TOOL1_ICON = "🔧"
UT3_TOOL1_DURATION_MS = 37

UT4_TRACE_ID = "exchange_msg_004"
UT4_PROMPT = "Lis le README"
UT4_AGENT = "plan"
UT4_TOKENS_IN = 10
UT4_TOKENS_OUT = 1778
UT4_DURATION_MS = 5052
UT4_TOOL_COUNT = 1
UT4_TOOL1_NAME = "read"
UT4_TOOL1_DISPLAY = "/path/to/README.md"
UT4_TOOL1_ICON = "📖"
UT4_TOOL1_DURATION_MS = 2

UT5_TRACE_ID = "exchange_msg_005"
UT5_PROMPT = "Lance l'agent roadmap"
UT5_AGENT = "plan"
UT5_TOKENS_IN = 15
UT5_TOKENS_OUT = 500
UT5_DURATION_MS = 165000
UT5_DELEGATION_COUNT = 1
UT5_DIRECT_TOOL_COUNT = 0

DELEG_AGENT_TYPE = "roadmap"
DELEG_PARENT_AGENT = "plan"
DELEG_TOKENS_IN = 35
DELEG_TOKENS_OUT = 3127
DELEG_DURATION_MS = 158859
DELEG_TOOL_COUNT = 2
DELEG_TOOL1_NAME = "read"
DELEG_TOOL1_DISPLAY = "/path/to/roadmap/README.md"
DELEG_TOOL1_ICON = "📖"
DELEG_TOOL1_DURATION_MS = 2
DELEG_TOOL2_NAME = "read"
DELEG_TOOL2_DISPLAY = "/path/to/roadmap/SPRINTS.md"
DELEG_TOOL2_ICON = "📖"
DELEG_TOOL2_DURATION_MS = 1

TOTAL_USER_TURNS = 5
TOTAL_TOOLS = 6
TOTAL_DELEGATIONS = 1
TOTAL_ROOT_CHILDREN = 5

ROOT_LABEL = f"🌳 {SESSION_PROJECT_NAME}: {SESSION_TITLE}"
UT1_LABEL = f'💬 user → {UT1_AGENT}: "{UT1_PROMPT}"'
UT2_LABEL = f'💬 user → {UT2_AGENT}: "{UT2_PROMPT}"'
UT3_LABEL = f'💬 user → {UT3_AGENT}: "{UT3_PROMPT}"'
UT4_LABEL = f'💬 user → {UT4_AGENT}: "{UT4_PROMPT}"'
UT5_LABEL = f'💬 user → {UT5_AGENT}: "{UT5_PROMPT}"'
DELEG_LABEL = f"└─ {DELEG_PARENT_AGENT} → {DELEG_AGENT_TYPE}"

UT2_TOOL1_LABEL = (
    f"  {UT2_TOOL1_ICON} {UT2_TOOL1_NAME.capitalize()}: {UT2_TOOL1_DISPLAY}"
)
UT2_TOOL2_LABEL = (
    f"  {UT2_TOOL2_ICON} {UT2_TOOL2_NAME.capitalize()}: {UT2_TOOL2_DISPLAY}"
)
UT3_TOOL1_LABEL = (
    f"  {UT3_TOOL1_ICON} {UT3_TOOL1_NAME.capitalize()}: {UT3_TOOL1_DISPLAY}"
)
UT4_TOOL1_LABEL = (
    f"  {UT4_TOOL1_ICON} {UT4_TOOL1_NAME.capitalize()}: {UT4_TOOL1_DISPLAY}"
)
DELEG_TOOL1_LABEL = (
    f"  {DELEG_TOOL1_ICON} {DELEG_TOOL1_NAME.capitalize()}: {DELEG_TOOL1_DISPLAY}"
)
DELEG_TOOL2_LABEL = (
    f"  {DELEG_TOOL2_ICON} {DELEG_TOOL2_NAME.capitalize()}: {DELEG_TOOL2_DISPLAY}"
)


def quick_checkin_tracing_data() -> dict:
    return {
        "session_hierarchy": [
            {
                "session_id": SESSION_ID,
                "node_type": "session",
                "title": SESSION_TITLE,
                "directory": SESSION_DIRECTORY,
                "agent_type": "plan",
                "tokens_in": SESSION_TOKENS_IN,
                "tokens_out": SESSION_TOKENS_OUT,
                "cache_read": SESSION_CACHE_READ,
                "started_at": "2026-01-04T15:44:31.235000",
                "children": [
                    {
                        "node_type": "user_turn",
                        "trace_id": UT1_TRACE_ID,
                        "prompt_input": UT1_PROMPT,
                        "tokens_in": UT1_TOKENS_IN,
                        "tokens_out": UT1_TOKENS_OUT,
                        "duration_ms": UT1_DURATION_MS,
                        "cache_read": 0,
                        "parent_agent": "user",
                        "subagent_type": UT1_AGENT,
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-04T15:44:31.248000",
                        "ended_at": "2026-01-04T15:44:45.956000",
                        "children": [],
                    },
                    {
                        "node_type": "user_turn",
                        "trace_id": UT2_TRACE_ID,
                        "prompt_input": UT2_PROMPT,
                        "tokens_in": UT2_TOKENS_IN,
                        "tokens_out": UT2_TOKENS_OUT,
                        "duration_ms": UT2_DURATION_MS,
                        "cache_read": 36680,
                        "parent_agent": "user",
                        "subagent_type": UT2_AGENT,
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-04T15:45:48.773000",
                        "ended_at": "2026-01-04T15:45:53.446000",
                        "children": [
                            {
                                "node_type": "tool",
                                "tool_name": UT2_TOOL1_NAME,
                                "display_info": UT2_TOOL1_DISPLAY,
                                "arguments": f'{{"url": "{UT2_TOOL1_DISPLAY}", "format": "text"}}',
                                "duration_ms": UT2_TOOL1_DURATION_MS,
                                "tool_status": "completed",
                                "status": "completed",
                                "trace_id": "tool_prt_001",
                                "session_id": SESSION_ID,
                                "started_at": "2026-01-04T15:45:53.089000",
                                "children": [],
                            },
                            {
                                "node_type": "tool",
                                "tool_name": UT2_TOOL2_NAME,
                                "display_info": UT2_TOOL2_DISPLAY,
                                "arguments": f'{{"url": "{UT2_TOOL2_DISPLAY}", "format": "text"}}',
                                "duration_ms": UT2_TOOL2_DURATION_MS,
                                "tool_status": "completed",
                                "status": "completed",
                                "trace_id": "tool_prt_002",
                                "session_id": SESSION_ID,
                                "started_at": "2026-01-04T15:45:53.262000",
                                "children": [],
                            },
                        ],
                    },
                    {
                        "node_type": "user_turn",
                        "trace_id": UT3_TRACE_ID,
                        "prompt_input": UT3_PROMPT,
                        "tokens_in": UT3_TOKENS_IN,
                        "tokens_out": UT3_TOKENS_OUT,
                        "duration_ms": UT3_DURATION_MS,
                        "cache_read": 68618,
                        "parent_agent": "user",
                        "subagent_type": UT3_AGENT,
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-04T15:46:10.000000",
                        "ended_at": "2026-01-04T15:46:13.918000",
                        "children": [
                            {
                                "node_type": "tool",
                                "tool_name": UT3_TOOL1_NAME,
                                "display_info": UT3_TOOL1_DISPLAY,
                                "arguments": f'{{"command": "{UT3_TOOL1_DISPLAY}", "description": "Create test file"}}',
                                "duration_ms": UT3_TOOL1_DURATION_MS,
                                "tool_status": "completed",
                                "status": "completed",
                                "trace_id": "tool_prt_003",
                                "session_id": SESSION_ID,
                                "started_at": "2026-01-04T15:46:10.500000",
                                "children": [],
                            },
                        ],
                    },
                    {
                        "node_type": "user_turn",
                        "trace_id": UT4_TRACE_ID,
                        "prompt_input": UT4_PROMPT,
                        "tokens_in": UT4_TOKENS_IN,
                        "tokens_out": UT4_TOKENS_OUT,
                        "duration_ms": UT4_DURATION_MS,
                        "cache_read": 72980,
                        "parent_agent": "user",
                        "subagent_type": UT4_AGENT,
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-04T15:47:00.000000",
                        "ended_at": "2026-01-04T15:47:05.052000",
                        "children": [
                            {
                                "node_type": "tool",
                                "tool_name": UT4_TOOL1_NAME,
                                "display_info": UT4_TOOL1_DISPLAY,
                                "arguments": f'{{"filePath": "{UT4_TOOL1_DISPLAY}"}}',
                                "duration_ms": UT4_TOOL1_DURATION_MS,
                                "tool_status": "completed",
                                "status": "completed",
                                "trace_id": "tool_prt_004",
                                "session_id": SESSION_ID,
                                "started_at": "2026-01-04T15:47:00.500000",
                                "children": [],
                            },
                        ],
                    },
                    {
                        "node_type": "user_turn",
                        "trace_id": UT5_TRACE_ID,
                        "prompt_input": UT5_PROMPT,
                        "tokens_in": UT5_TOKENS_IN,
                        "tokens_out": UT5_TOKENS_OUT,
                        "duration_ms": UT5_DURATION_MS,
                        "cache_read": 30128,
                        "parent_agent": "user",
                        "subagent_type": UT5_AGENT,
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-04T15:48:00.000000",
                        "ended_at": "2026-01-04T15:50:45.000000",
                        "child_session_id": "ses_child_001",
                        "children": [
                            {
                                "node_type": "agent",
                                "subagent_type": DELEG_AGENT_TYPE,
                                "parent_agent": DELEG_PARENT_AGENT,
                                "tokens_in": DELEG_TOKENS_IN,
                                "tokens_out": DELEG_TOKENS_OUT,
                                "duration_ms": DELEG_DURATION_MS,
                                "cache_read": 261028,
                                "trace_id": "prt_delegation_001",
                                "session_id": "ses_child_001",
                                "child_session_id": "ses_grandchild_001",
                                "started_at": "2026-01-04T15:48:00.500000",
                                "ended_at": "2026-01-04T15:50:38.859000",
                                "prompt_input": "Analyze roadmap structure",
                                "children": [
                                    {
                                        "node_type": "tool",
                                        "tool_name": DELEG_TOOL1_NAME,
                                        "display_info": DELEG_TOOL1_DISPLAY,
                                        "arguments": f'{{"filePath": "{DELEG_TOOL1_DISPLAY}"}}',
                                        "duration_ms": DELEG_TOOL1_DURATION_MS,
                                        "tool_status": "completed",
                                        "status": "completed",
                                        "trace_id": "tool_deleg_001",
                                        "session_id": "ses_child_001",
                                        "started_at": "2026-01-04T15:48:01.000000",
                                        "children": [],
                                    },
                                    {
                                        "node_type": "tool",
                                        "tool_name": DELEG_TOOL2_NAME,
                                        "display_info": DELEG_TOOL2_DISPLAY,
                                        "arguments": f'{{"filePath": "{DELEG_TOOL2_DISPLAY}"}}',
                                        "duration_ms": DELEG_TOOL2_DURATION_MS,
                                        "tool_status": "completed",
                                        "status": "completed",
                                        "trace_id": "tool_deleg_002",
                                        "session_id": "ses_child_001",
                                        "started_at": "2026-01-04T15:48:01.500000",
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


def get_text(model, index: QModelIndex) -> str:
    return model.data(index, Qt.ItemDataRole.DisplayRole) or ""


def get_data(model, index: QModelIndex) -> dict:
    return model.data(index, Qt.ItemDataRole.UserRole) or {}


def load_and_expand(dashboard_window, qtbot, click_nav):
    click_nav(dashboard_window, SECTION_TRACING)
    tracing = dashboard_window._tracing

    data = quick_checkin_tracing_data()
    data["meta"] = {"has_more": False}
    dashboard_window._signals.tracing_updated.emit(data)
    qtbot.waitUntil(lambda: tracing._model.rowCount() > 0, timeout=2000)

    root_index = tracing._model.index(0, 0)
    root_has_all_children = (
        lambda: tracing._model.rowCount(root_index) == TOTAL_ROOT_CHILDREN
    )
    qtbot.waitUntil(root_has_all_children, timeout=3000)

    expand_all_indexes(tracing._tree)
    qtbot.wait(50)
    return tracing


class TestQuickCheckinSession:
    def test_root_structure(self, dashboard_window, qtbot, click_nav):
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        model = tracing._model

        assert model.rowCount() == 1

        root_index = model.index(0, 0)
        assert get_text(model, root_index) == ROOT_LABEL

        data = get_data(model, root_index)
        assert data.get("node_type") == "session"

        assert model.rowCount(root_index) == TOTAL_ROOT_CHILDREN

    def test_user_turns_labels_and_types(self, dashboard_window, qtbot, click_nav):
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        model = tracing._model
        root_index = model.index(0, 0)

        expected = [
            (UT1_LABEL, UT1_TOOL_COUNT),
            (UT2_LABEL, UT2_TOOL_COUNT),
            (UT3_LABEL, UT3_TOOL_COUNT),
            (UT4_LABEL, UT4_TOOL_COUNT),
            (UT5_LABEL, UT5_DELEGATION_COUNT),
        ]

        for i, (expected_label, expected_children) in enumerate(expected):
            child_index = model.index(i, 0, root_index)
            assert get_text(model, child_index) == expected_label, f"UT{i + 1} label"
            data = get_data(model, child_index)
            assert data.get("node_type") == "user_turn", f"UT{i + 1} node_type"
            assert model.rowCount(child_index) == expected_children, (
                f"UT{i + 1} children"
            )

    def test_ut2_webfetch_tools(self, dashboard_window, qtbot, click_nav):
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        model = tracing._model
        root_index = model.index(0, 0)
        ut2_index = model.index(1, 0, root_index)

        tool1_index = model.index(0, 0, ut2_index)
        assert get_text(model, tool1_index) == UT2_TOOL1_LABEL
        data1 = get_data(model, tool1_index)
        assert data1.get("node_type") == "tool"
        assert data1.get("tool_name") == UT2_TOOL1_NAME
        assert data1.get("display_info") == UT2_TOOL1_DISPLAY

        tool2_index = model.index(1, 0, ut2_index)
        assert get_text(model, tool2_index) == UT2_TOOL2_LABEL
        data2 = get_data(model, tool2_index)
        assert data2.get("node_type") == "tool"
        assert data2.get("tool_name") == UT2_TOOL2_NAME
        assert data2.get("display_info") == UT2_TOOL2_DISPLAY

    def test_ut3_bash_tool(self, dashboard_window, qtbot, click_nav):
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        model = tracing._model
        root_index = model.index(0, 0)
        ut3_index = model.index(2, 0, root_index)

        tool_index = model.index(0, 0, ut3_index)
        assert get_text(model, tool_index) == UT3_TOOL1_LABEL
        data = get_data(model, tool_index)
        assert data.get("node_type") == "tool"
        assert data.get("tool_name") == UT3_TOOL1_NAME
        assert data.get("display_info") == UT3_TOOL1_DISPLAY

    def test_ut4_read_tool(self, dashboard_window, qtbot, click_nav):
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        model = tracing._model
        root_index = model.index(0, 0)
        ut4_index = model.index(3, 0, root_index)

        tool_index = model.index(0, 0, ut4_index)
        assert get_text(model, tool_index) == UT4_TOOL1_LABEL
        data = get_data(model, tool_index)
        assert data.get("node_type") == "tool"
        assert data.get("tool_name") == UT4_TOOL1_NAME
        assert data.get("display_info") == UT4_TOOL1_DISPLAY

    def test_ut5_delegation_and_tools(self, dashboard_window, qtbot, click_nav):
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        model = tracing._model
        root_index = model.index(0, 0)
        ut5_index = model.index(4, 0, root_index)
        deleg_index = model.index(0, 0, ut5_index)

        assert get_text(model, deleg_index) == DELEG_LABEL
        deleg_data = get_data(model, deleg_index)
        assert deleg_data.get("node_type") in ("agent", "delegation")
        assert deleg_data.get("subagent_type") == DELEG_AGENT_TYPE
        assert deleg_data.get("parent_agent") == DELEG_PARENT_AGENT
        assert model.rowCount(deleg_index) == DELEG_TOOL_COUNT

        tool1_index = model.index(0, 0, deleg_index)
        assert get_text(model, tool1_index) == DELEG_TOOL1_LABEL
        data1 = get_data(model, tool1_index)
        assert data1.get("node_type") == "tool"
        assert data1.get("tool_name") == DELEG_TOOL1_NAME
        assert data1.get("display_info") == DELEG_TOOL1_DISPLAY

        tool2_index = model.index(1, 0, deleg_index)
        assert get_text(model, tool2_index) == DELEG_TOOL2_LABEL
        data2 = get_data(model, tool2_index)
        assert data2.get("node_type") == "tool"
        assert data2.get("tool_name") == DELEG_TOOL2_NAME
        assert data2.get("display_info") == DELEG_TOOL2_DISPLAY

    def test_total_counts(self, dashboard_window, qtbot, click_nav):
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        user_turns = find_indexes_by_node_type(tracing._tree, "user_turn")
        assert len(user_turns) == TOTAL_USER_TURNS

        tools = find_indexes_by_node_type(tracing._tree, "tool")
        assert len(tools) == TOTAL_TOOLS

        delegations = find_indexes_by_node_type(tracing._tree, "agent")
        delegations += find_indexes_by_node_type(tracing._tree, "delegation")
        assert len(delegations) == TOTAL_DELEGATIONS

    def test_hierarchy_parent_child_relationships(
        self, dashboard_window, qtbot, click_nav
    ):
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        model = tracing._model
        root_index = model.index(0, 0)

        for i in range(TOTAL_USER_TURNS):
            ut_index = model.index(i, 0, root_index)
            assert model.parent(ut_index) == root_index, f"UT{i + 1} parent"

        ut2_index = model.index(1, 0, root_index)
        assert model.parent(model.index(0, 0, ut2_index)) == ut2_index
        assert model.parent(model.index(1, 0, ut2_index)) == ut2_index

        ut3_index = model.index(2, 0, root_index)
        assert model.parent(model.index(0, 0, ut3_index)) == ut3_index

        ut4_index = model.index(3, 0, root_index)
        assert model.parent(model.index(0, 0, ut4_index)) == ut4_index

        ut5_index = model.index(4, 0, root_index)
        deleg_index = model.index(0, 0, ut5_index)
        assert model.parent(deleg_index) == ut5_index
        assert model.parent(model.index(0, 0, deleg_index)) == deleg_index
        assert model.parent(model.index(1, 0, deleg_index)) == deleg_index

    def test_items_order(self, dashboard_window, qtbot, click_nav):
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        model = tracing._model
        root_index = model.index(0, 0)

        assert get_text(model, model.index(0, 0, root_index)) == UT1_LABEL
        assert get_text(model, model.index(1, 0, root_index)) == UT2_LABEL
        assert get_text(model, model.index(2, 0, root_index)) == UT3_LABEL
        assert get_text(model, model.index(3, 0, root_index)) == UT4_LABEL
        assert get_text(model, model.index(4, 0, root_index)) == UT5_LABEL

        ut2_index = model.index(1, 0, root_index)
        assert get_text(model, model.index(0, 0, ut2_index)) == UT2_TOOL1_LABEL
        assert get_text(model, model.index(1, 0, ut2_index)) == UT2_TOOL2_LABEL

        ut5_index = model.index(4, 0, root_index)
        deleg_index = model.index(0, 0, ut5_index)
        assert get_text(model, model.index(0, 0, deleg_index)) == DELEG_TOOL1_LABEL
        assert get_text(model, model.index(1, 0, deleg_index)) == DELEG_TOOL2_LABEL
