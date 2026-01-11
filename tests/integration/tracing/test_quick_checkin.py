"""
Integration tests for Tracing section with "Quick check-in" session data.

EXHAUSTIVE TESTS with STRICT EQUALITY ASSERTIONS:
- Exact number of items at each level
- Exact labels for every node
- Exact hierarchy (parent-child relationships)
- Exact tool names and display_info
- Exact node_type for every item
- Exact order of items

Session Reference: "Quick check-in"
- 5 user turns total (EXACT)
- 6 tools: 2 webfetch + 1 bash + 1 read + 2 read in delegation (EXACT)
- 1 delegation to "roadmap" agent with 2 nested tools (EXACT)

NO >= or <= assertions - ALL STRICT EQUALITY (==)
"""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItem

from ..fixtures import process_qt_events
from ..conftest import SECTION_TRACING

pytestmark = pytest.mark.integration


# =============================================================================
# Quick Check-in Session Constants - EXACT VALUES (IMMUTABLE)
# =============================================================================

# Session-level
SESSION_ID = "ses_quick_checkin_001"
SESSION_TITLE = "Quick check-in"
SESSION_DIRECTORY = "/Users/test/project"
SESSION_PROJECT_NAME = "project"  # Extracted from directory
SESSION_TOKENS_IN = 129
SESSION_TOKENS_OUT = 9101
SESSION_CACHE_READ = 417959

# User Turn 1 - Simple greeting (NO tools)
UT1_TRACE_ID = "exchange_msg_001"
UT1_PROMPT = "Salut, est-ce que ça va ?"
UT1_AGENT = "plan"
UT1_TOKENS_IN = 8
UT1_TOKENS_OUT = 305
UT1_DURATION_MS = 14708
UT1_TOOL_COUNT = 0

# User Turn 2 - Weather API (2 webfetch tools)
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

# User Turn 3 - Create file (1 bash tool)
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

# User Turn 4 - Read README (1 read tool)
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

# User Turn 5 - Delegation (1 agent with 2 tools)
UT5_TRACE_ID = "exchange_msg_005"
UT5_PROMPT = "Lance l'agent roadmap"
UT5_AGENT = "plan"
UT5_TOKENS_IN = 15
UT5_TOKENS_OUT = 500
UT5_DURATION_MS = 165000
UT5_DELEGATION_COUNT = 1
UT5_DIRECT_TOOL_COUNT = 0  # Tools are inside the delegation, not direct children

# Delegation details
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

# Total counts (EXACT)
TOTAL_USER_TURNS = 5
TOTAL_TOOLS = 6  # 2 + 1 + 1 + 2 (in delegation)
TOTAL_DELEGATIONS = 1
TOTAL_ROOT_CHILDREN = 5  # 5 user turns directly under root

# Expected labels (EXACT)
ROOT_LABEL = f"🌳 {SESSION_PROJECT_NAME}: {SESSION_TITLE}"
UT1_LABEL = f'💬 user → {UT1_AGENT}: "{UT1_PROMPT}"'
UT2_LABEL = f'💬 user → {UT2_AGENT}: "{UT2_PROMPT}"'
UT3_LABEL = f'💬 user → {UT3_AGENT}: "{UT3_PROMPT}"'
UT4_LABEL = f'💬 user → {UT4_AGENT}: "{UT4_PROMPT}"'
UT5_LABEL = f'💬 user → {UT5_AGENT}: "{UT5_PROMPT}"'
# Note: depth=2 (root→ut5→delegation), so icon is └─ not 🔗
DELEG_LABEL = f"└─ {DELEG_PARENT_AGENT} → {DELEG_AGENT_TYPE}"

# Tool labels (EXACT) - Note: tool names are now capitalized in UI
UT2_TOOL1_LABEL = f"{UT2_TOOL1_ICON} {UT2_TOOL1_NAME.capitalize()}: {UT2_TOOL1_DISPLAY}"
UT2_TOOL2_LABEL = f"{UT2_TOOL2_ICON} {UT2_TOOL2_NAME.capitalize()}: {UT2_TOOL2_DISPLAY}"
UT3_TOOL1_LABEL = f"{UT3_TOOL1_ICON} {UT3_TOOL1_NAME.capitalize()}: {UT3_TOOL1_DISPLAY}"
UT4_TOOL1_LABEL = f"{UT4_TOOL1_ICON} {UT4_TOOL1_NAME.capitalize()}: {UT4_TOOL1_DISPLAY}"
DELEG_TOOL1_LABEL = (
    f"{DELEG_TOOL1_ICON} {DELEG_TOOL1_NAME.capitalize()}: {DELEG_TOOL1_DISPLAY}"
)
DELEG_TOOL2_LABEL = (
    f"{DELEG_TOOL2_ICON} {DELEG_TOOL2_NAME.capitalize()}: {DELEG_TOOL2_DISPLAY}"
)


# =============================================================================
# Fixture: Complete Quick Check-in Mock Data
# =============================================================================


def quick_checkin_tracing_data() -> dict:
    """Create complete mock tracing data for Quick check-in session.

    This data structure matches exactly what the API returns and what
    the dashboard expects. Every value is from the real session.
    """
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
                    # ========== USER TURN 1 - No tools ==========
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
                    # ========== USER TURN 2 - 2 webfetch tools ==========
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
                    # ========== USER TURN 3 - 1 bash tool ==========
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
                    # ========== USER TURN 4 - 1 read tool ==========
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
                    # ========== USER TURN 5 - Delegation with nested tools ==========
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
                            # DELEGATION to roadmap agent
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
                                    # Tool 1 inside delegation
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
                                    # Tool 2 inside delegation
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


# =============================================================================
# Helper Functions for Tree Traversal
# =============================================================================


def get_all_tree_items(tree_widget) -> list[QTreeWidgetItem]:
    """Get all items in tree (flattened)."""
    items = []

    def collect(item: QTreeWidgetItem):
        items.append(item)
        for i in range(item.childCount()):
            child = item.child(i)
            if child:
                collect(child)

    for i in range(tree_widget.topLevelItemCount()):
        top_item = tree_widget.topLevelItem(i)
        if top_item:
            collect(top_item)

    return items


def get_item_data(item: QTreeWidgetItem) -> dict:
    """Get the data stored in a tree item."""
    return item.data(0, Qt.ItemDataRole.UserRole) or {}


def find_items_by_node_type(tree_widget, node_type: str) -> list[QTreeWidgetItem]:
    """Find all items with a specific node_type."""
    result = []
    for item in get_all_tree_items(tree_widget):
        data = get_item_data(item)
        if data.get("node_type") == node_type:
            result.append(item)
    return result


def find_items_by_tool_name(tree_widget, tool_name: str) -> list[QTreeWidgetItem]:
    """Find all tool items with a specific tool_name."""
    result = []
    for item in get_all_tree_items(tree_widget):
        data = get_item_data(item)
        if data.get("node_type") == "tool" and data.get("tool_name") == tool_name:
            result.append(item)
    return result


def expand_all_items(tree_widget):
    for item in get_all_tree_items(tree_widget):
        if item.childCount() > 0:
            item.setExpanded(True)
    process_qt_events()


def load_and_expand(dashboard_window, qtbot, click_nav):
    """Load data and expand all items. Returns tracing section."""
    click_nav(dashboard_window, SECTION_TRACING)
    tracing = dashboard_window._tracing

    data = quick_checkin_tracing_data()
    dashboard_window._signals.tracing_updated.emit(data)
    process_qt_events()

    expand_all_items(tracing._tree)
    return tracing


# =============================================================================
# TEST CLASS: Root Structure
# =============================================================================


# =============================================================================
# CONSOLIDATED TESTS - Grouped by logical unit
# =============================================================================


class TestQuickCheckinSession:
    """Consolidated tests for Quick check-in session hierarchy."""

    def test_root_structure(self, dashboard_window, qtbot, click_nav):
        """Root node: exactly 1 root with correct label, node_type, and 5 children."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        # Exactly 1 root
        assert tracing._tree.topLevelItemCount() == 1

        root = tracing._tree.topLevelItem(0)

        # Root label
        assert root.text(0) == ROOT_LABEL

        # Root node_type
        data = get_item_data(root)
        assert data.get("node_type") == "session"

        # Exactly 5 children (user turns)
        assert root.childCount() == TOTAL_ROOT_CHILDREN

    def test_user_turns_labels_and_types(self, dashboard_window, qtbot, click_nav):
        """All 5 user turns: correct labels, node_types, and child counts."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        root = tracing._tree.topLevelItem(0)

        expected = [
            (UT1_LABEL, UT1_TOOL_COUNT),
            (UT2_LABEL, UT2_TOOL_COUNT),
            (UT3_LABEL, UT3_TOOL_COUNT),
            (UT4_LABEL, UT4_TOOL_COUNT),
            (UT5_LABEL, UT5_DELEGATION_COUNT),
        ]

        for i, (expected_label, expected_children) in enumerate(expected):
            child = root.child(i)
            # Label
            assert child.text(0) == expected_label, f"UT{i + 1} label mismatch"
            # Node type
            data = get_item_data(child)
            assert data.get("node_type") == "user_turn", f"UT{i + 1} node_type mismatch"
            # Child count
            assert child.childCount() == expected_children, (
                f"UT{i + 1} child count mismatch"
            )

    def test_ut2_webfetch_tools(self, dashboard_window, qtbot, click_nav):
        """UT2 tools: 2 webfetch with correct labels, node_types, tool_names."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        root = tracing._tree.topLevelItem(0)
        ut2 = root.child(1)

        # Tool 1
        tool1 = ut2.child(0)
        assert tool1.text(0) == UT2_TOOL1_LABEL
        data1 = get_item_data(tool1)
        assert data1.get("node_type") == "tool"
        assert data1.get("tool_name") == UT2_TOOL1_NAME
        assert data1.get("display_info") == UT2_TOOL1_DISPLAY

        # Tool 2
        tool2 = ut2.child(1)
        assert tool2.text(0) == UT2_TOOL2_LABEL
        data2 = get_item_data(tool2)
        assert data2.get("node_type") == "tool"
        assert data2.get("tool_name") == UT2_TOOL2_NAME
        assert data2.get("display_info") == UT2_TOOL2_DISPLAY

    def test_ut3_bash_tool(self, dashboard_window, qtbot, click_nav):
        """UT3 tool: 1 bash with correct label, node_type, tool_name."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        root = tracing._tree.topLevelItem(0)
        ut3 = root.child(2)

        tool = ut3.child(0)
        assert tool.text(0) == UT3_TOOL1_LABEL
        data = get_item_data(tool)
        assert data.get("node_type") == "tool"
        assert data.get("tool_name") == UT3_TOOL1_NAME
        assert data.get("display_info") == UT3_TOOL1_DISPLAY

    def test_ut4_read_tool(self, dashboard_window, qtbot, click_nav):
        """UT4 tool: 1 read with correct label, node_type, tool_name."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        root = tracing._tree.topLevelItem(0)
        ut4 = root.child(3)

        tool = ut4.child(0)
        assert tool.text(0) == UT4_TOOL1_LABEL
        data = get_item_data(tool)
        assert data.get("node_type") == "tool"
        assert data.get("tool_name") == UT4_TOOL1_NAME
        assert data.get("display_info") == UT4_TOOL1_DISPLAY

    def test_ut5_delegation_and_tools(self, dashboard_window, qtbot, click_nav):
        """UT5 delegation: correct label, node_type, parent, and 2 read tools."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)

        # Delegation node
        assert delegation.text(0) == DELEG_LABEL
        deleg_data = get_item_data(delegation)
        assert deleg_data.get("node_type") in ("agent", "delegation")
        assert deleg_data.get("subagent_type") == DELEG_AGENT_TYPE
        assert deleg_data.get("parent_agent") == DELEG_PARENT_AGENT
        assert delegation.childCount() == DELEG_TOOL_COUNT

        # Delegation Tool 1
        tool1 = delegation.child(0)
        assert tool1.text(0) == DELEG_TOOL1_LABEL
        data1 = get_item_data(tool1)
        assert data1.get("node_type") == "tool"
        assert data1.get("tool_name") == DELEG_TOOL1_NAME
        assert data1.get("display_info") == DELEG_TOOL1_DISPLAY

        # Delegation Tool 2
        tool2 = delegation.child(1)
        assert tool2.text(0) == DELEG_TOOL2_LABEL
        data2 = get_item_data(tool2)
        assert data2.get("node_type") == "tool"
        assert data2.get("tool_name") == DELEG_TOOL2_NAME
        assert data2.get("display_info") == DELEG_TOOL2_DISPLAY

    def test_total_counts(self, dashboard_window, qtbot, click_nav):
        """Total counts: 5 user_turns, 6 tools, 1 delegation."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        user_turns = find_items_by_node_type(tracing._tree, "user_turn")
        assert len(user_turns) == TOTAL_USER_TURNS

        tools = find_items_by_node_type(tracing._tree, "tool")
        assert len(tools) == TOTAL_TOOLS

        delegations = find_items_by_node_type(tracing._tree, "agent")
        delegations += find_items_by_node_type(tracing._tree, "delegation")
        assert len(delegations) == TOTAL_DELEGATIONS

    def test_hierarchy_parent_child_relationships(
        self, dashboard_window, qtbot, click_nav
    ):
        """Verify parent-child relationships in the tree."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        root = tracing._tree.topLevelItem(0)

        # All user turns are children of root
        for i in range(TOTAL_USER_TURNS):
            ut = root.child(i)
            assert ut.parent() == root, f"UT{i + 1} parent should be root"

        # UT2 tools are children of UT2
        ut2 = root.child(1)
        assert ut2.child(0).parent() == ut2
        assert ut2.child(1).parent() == ut2

        # UT3 tool is child of UT3
        ut3 = root.child(2)
        assert ut3.child(0).parent() == ut3

        # UT4 tool is child of UT4
        ut4 = root.child(3)
        assert ut4.child(0).parent() == ut4

        # Delegation is child of UT5, tools are children of delegation
        ut5 = root.child(4)
        delegation = ut5.child(0)
        assert delegation.parent() == ut5
        assert delegation.child(0).parent() == delegation
        assert delegation.child(1).parent() == delegation

    def test_items_order(self, dashboard_window, qtbot, click_nav):
        """Verify items are in correct order."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)
        root = tracing._tree.topLevelItem(0)

        # User turns order
        assert root.child(0).text(0) == UT1_LABEL
        assert root.child(1).text(0) == UT2_LABEL
        assert root.child(2).text(0) == UT3_LABEL
        assert root.child(3).text(0) == UT4_LABEL
        assert root.child(4).text(0) == UT5_LABEL

        # UT2 tools order
        ut2 = root.child(1)
        assert ut2.child(0).text(0) == UT2_TOOL1_LABEL
        assert ut2.child(1).text(0) == UT2_TOOL2_LABEL

        # Delegation tools order
        delegation = root.child(4).child(0)
        assert delegation.child(0).text(0) == DELEG_TOOL1_LABEL
        assert delegation.child(1).text(0) == DELEG_TOOL2_LABEL
