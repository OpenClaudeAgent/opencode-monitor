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

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING
from ..helpers import (
    expand_all_items,
    find_items_by_node_type,
    get_item_data,
)
from ..fixtures.sessions import (
    # Session constants
    ROOT_LABEL,
    TOTAL_ROOT_CHILDREN,
    TOTAL_USER_TURNS,
    TOTAL_TOOLS,
    TOTAL_DELEGATIONS,
    # User turn labels
    UT1_LABEL,
    UT2_LABEL,
    UT3_LABEL,
    UT4_LABEL,
    UT5_LABEL,
    # Tool counts
    UT1_TOOL_COUNT,
    UT2_TOOL_COUNT,
    UT3_TOOL_COUNT,
    UT4_TOOL_COUNT,
    UT5_DELEGATION_COUNT,
    # UT2 tool constants
    UT2_TOOL1_LABEL,
    UT2_TOOL1_NAME,
    UT2_TOOL1_DISPLAY,
    UT2_TOOL2_LABEL,
    UT2_TOOL2_NAME,
    UT2_TOOL2_DISPLAY,
    # UT3 tool constants
    UT3_TOOL1_LABEL,
    UT3_TOOL1_NAME,
    UT3_TOOL1_DISPLAY,
    # UT4 tool constants
    UT4_TOOL1_LABEL,
    UT4_TOOL1_NAME,
    UT4_TOOL1_DISPLAY,
    # Delegation constants
    DELEG_LABEL,
    DELEG_AGENT_TYPE,
    DELEG_PARENT_AGENT,
    DELEG_TOOL_COUNT,
    DELEG_TOOL1_LABEL,
    DELEG_TOOL1_NAME,
    DELEG_TOOL1_DISPLAY,
    DELEG_TOOL2_LABEL,
    DELEG_TOOL2_NAME,
    DELEG_TOOL2_DISPLAY,
    # Data function
    quick_checkin_tracing_data,
)

pytestmark = pytest.mark.integration


def load_and_expand(dashboard_window, qtbot, click_nav):
    """Load data and expand all items. Returns tracing section."""
    click_nav(dashboard_window, SECTION_TRACING)
    tracing = dashboard_window._tracing

    data = quick_checkin_tracing_data()
    dashboard_window._signals.tracing_updated.emit(data)
    qtbot.wait(SIGNAL_WAIT_MS)

    expand_all_items(tracing._tree, qtbot)
    return tracing


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
