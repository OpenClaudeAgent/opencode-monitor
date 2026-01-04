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

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING

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
ROOT_LABEL = f"🌳 {SESSION_PROJECT_NAME}"
UT1_LABEL = f'💬 user → {UT1_AGENT}: "{UT1_PROMPT}"'
UT2_LABEL = f'💬 user → {UT2_AGENT}: "{UT2_PROMPT}"'
UT3_LABEL = f'💬 user → {UT3_AGENT}: "{UT3_PROMPT}"'
UT4_LABEL = f'💬 user → {UT4_AGENT}: "{UT4_PROMPT}"'
UT5_LABEL = f'💬 user → {UT5_AGENT}: "{UT5_PROMPT}"'
# Note: depth=2 (root→ut5→delegation), so icon is └─ not 🔗
DELEG_LABEL = f"└─ {DELEG_PARENT_AGENT} → {DELEG_AGENT_TYPE}"

# Tool labels (EXACT)
UT2_TOOL1_LABEL = f"{UT2_TOOL1_ICON} {UT2_TOOL1_NAME}: {UT2_TOOL1_DISPLAY}"
UT2_TOOL2_LABEL = f"{UT2_TOOL2_ICON} {UT2_TOOL2_NAME}: {UT2_TOOL2_DISPLAY}"
UT3_TOOL1_LABEL = f"{UT3_TOOL1_ICON} {UT3_TOOL1_NAME}: {UT3_TOOL1_DISPLAY}"
UT4_TOOL1_LABEL = f"{UT4_TOOL1_ICON} {UT4_TOOL1_NAME}: {UT4_TOOL1_DISPLAY}"
DELEG_TOOL1_LABEL = f"{DELEG_TOOL1_ICON} {DELEG_TOOL1_NAME}: {DELEG_TOOL1_DISPLAY}"
DELEG_TOOL2_LABEL = f"{DELEG_TOOL2_ICON} {DELEG_TOOL2_NAME}: {DELEG_TOOL2_DISPLAY}"


# =============================================================================
# Fixture: Complete Quick Check-in Mock Data
# =============================================================================


def quick_checkin_tracing_data() -> dict:
    """Create complete mock tracing data for Quick check-in session.

    This data structure matches exactly what the API returns and what
    the dashboard expects. Every value is from the real session.
    """
    return {
        "traces": [],
        "sessions": [
            {
                "id": SESSION_ID,
                "title": SESSION_TITLE,
                "directory": SESSION_DIRECTORY,
                "created_at": "2026-01-04T15:44:31.235000",
                "tokens_in": SESSION_TOKENS_IN,
                "tokens_out": SESSION_TOKENS_OUT,
            }
        ],
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
        "total_traces": TOTAL_USER_TURNS,
        "unique_agents": 2,
        "total_duration_ms": 193351,
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


def expand_all_items(tree_widget, qtbot):
    """Expand all items in the tree."""
    for item in get_all_tree_items(tree_widget):
        if item.childCount() > 0:
            item.setExpanded(True)
    qtbot.wait(SIGNAL_WAIT_MS // 2)


def load_and_expand(dashboard_window, qtbot, click_nav):
    """Load data and expand all items. Returns tracing section."""
    click_nav(dashboard_window, SECTION_TRACING)
    tracing = dashboard_window._tracing

    data = quick_checkin_tracing_data()
    dashboard_window._signals.tracing_updated.emit(data)
    qtbot.wait(SIGNAL_WAIT_MS)

    expand_all_items(tracing._tree, qtbot)
    return tracing


# =============================================================================
# TEST CLASS: Root Structure
# =============================================================================


class TestRootStructure:
    """Tests for root node structure - STRICT EQUALITY."""

    def test_exactly_one_root_item(self, dashboard_window, qtbot, click_nav):
        """Tree must have exactly 1 root item."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        count = tracing._tree.topLevelItemCount()
        assert count == 1, f"Expected exactly 1 root, got {count}"

    def test_root_label_exact(self, dashboard_window, qtbot, click_nav):
        """Root label must be exactly '🌳 project'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        label = root.text(0)
        assert label == ROOT_LABEL, f"Expected '{ROOT_LABEL}', got '{label}'"

    def test_root_has_exactly_5_children(self, dashboard_window, qtbot, click_nav):
        """Root must have exactly 5 children (5 user turns)."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        count = root.childCount()
        assert count == TOTAL_ROOT_CHILDREN, (
            f"Expected {TOTAL_ROOT_CHILDREN} children, got {count}"
        )

    def test_root_node_type_is_session(self, dashboard_window, qtbot, click_nav):
        """Root node_type must be 'session'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        data = get_item_data(root)
        node_type = data.get("node_type")
        assert node_type == "session", f"Expected 'session', got '{node_type}'"


# =============================================================================
# TEST CLASS: User Turn Count and Labels
# =============================================================================


class TestUserTurnsExact:
    """Tests for user turns - STRICT EQUALITY."""

    def test_exactly_5_user_turns(self, dashboard_window, qtbot, click_nav):
        """Must have exactly 5 user_turn items."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        user_turns = find_items_by_node_type(tracing._tree, "user_turn")
        count = len(user_turns)
        assert count == TOTAL_USER_TURNS, (
            f"Expected {TOTAL_USER_TURNS} user turns, got {count}"
        )

    def test_user_turn_1_label_exact(self, dashboard_window, qtbot, click_nav):
        """User Turn 1 label must match exactly."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut1 = root.child(0)
        label = ut1.text(0)
        assert label == UT1_LABEL, (
            f"UT1 label mismatch:\nExpected: {UT1_LABEL}\nGot: {label}"
        )

    def test_user_turn_2_label_exact(self, dashboard_window, qtbot, click_nav):
        """User Turn 2 label must match exactly."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut2 = root.child(1)
        label = ut2.text(0)
        assert label == UT2_LABEL, (
            f"UT2 label mismatch:\nExpected: {UT2_LABEL}\nGot: {label}"
        )

    def test_user_turn_3_label_exact(self, dashboard_window, qtbot, click_nav):
        """User Turn 3 label must match exactly."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut3 = root.child(2)
        label = ut3.text(0)
        assert label == UT3_LABEL, (
            f"UT3 label mismatch:\nExpected: {UT3_LABEL}\nGot: {label}"
        )

    def test_user_turn_4_label_exact(self, dashboard_window, qtbot, click_nav):
        """User Turn 4 label must match exactly."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut4 = root.child(3)
        label = ut4.text(0)
        assert label == UT4_LABEL, (
            f"UT4 label mismatch:\nExpected: {UT4_LABEL}\nGot: {label}"
        )

    def test_user_turn_5_label_exact(self, dashboard_window, qtbot, click_nav):
        """User Turn 5 label must match exactly."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        label = ut5.text(0)
        assert label == UT5_LABEL, (
            f"UT5 label mismatch:\nExpected: {UT5_LABEL}\nGot: {label}"
        )

    def test_all_user_turns_have_node_type_user_turn(
        self, dashboard_window, qtbot, click_nav
    ):
        """All 5 children of root must have node_type 'user_turn'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        for i in range(TOTAL_USER_TURNS):
            child = root.child(i)
            data = get_item_data(child)
            node_type = data.get("node_type")
            assert node_type == "user_turn", (
                f"Child {i} node_type: expected 'user_turn', got '{node_type}'"
            )


# =============================================================================
# TEST CLASS: User Turn Children Count
# =============================================================================


class TestUserTurnChildrenCount:
    """Tests for exact children count per user turn."""

    def test_ut1_has_0_children(self, dashboard_window, qtbot, click_nav):
        """User Turn 1 must have exactly 0 children."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut1 = root.child(0)
        count = ut1.childCount()
        assert count == UT1_TOOL_COUNT, (
            f"UT1 children: expected {UT1_TOOL_COUNT}, got {count}"
        )

    def test_ut2_has_2_children(self, dashboard_window, qtbot, click_nav):
        """User Turn 2 must have exactly 2 children (2 webfetch tools)."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut2 = root.child(1)
        count = ut2.childCount()
        assert count == UT2_TOOL_COUNT, (
            f"UT2 children: expected {UT2_TOOL_COUNT}, got {count}"
        )

    def test_ut3_has_1_child(self, dashboard_window, qtbot, click_nav):
        """User Turn 3 must have exactly 1 child (1 bash tool)."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut3 = root.child(2)
        count = ut3.childCount()
        assert count == UT3_TOOL_COUNT, (
            f"UT3 children: expected {UT3_TOOL_COUNT}, got {count}"
        )

    def test_ut4_has_1_child(self, dashboard_window, qtbot, click_nav):
        """User Turn 4 must have exactly 1 child (1 read tool)."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut4 = root.child(3)
        count = ut4.childCount()
        assert count == UT4_TOOL_COUNT, (
            f"UT4 children: expected {UT4_TOOL_COUNT}, got {count}"
        )

    def test_ut5_has_1_child(self, dashboard_window, qtbot, click_nav):
        """User Turn 5 must have exactly 1 child (1 delegation)."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        count = ut5.childCount()
        assert count == UT5_DELEGATION_COUNT, (
            f"UT5 children: expected {UT5_DELEGATION_COUNT}, got {count}"
        )


# =============================================================================
# TEST CLASS: Tools in User Turn 2
# =============================================================================


class TestUT2Tools:
    """Tests for tools in User Turn 2 - STRICT EQUALITY."""

    def test_ut2_tool1_label_exact(self, dashboard_window, qtbot, click_nav):
        """UT2 Tool 1 label must be exactly '🌐 webfetch: https://www.weatherapi.com/'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut2 = root.child(1)
        tool1 = ut2.child(0)
        label = tool1.text(0)
        assert label == UT2_TOOL1_LABEL, (
            f"UT2 Tool1 label:\nExpected: {UT2_TOOL1_LABEL}\nGot: {label}"
        )

    def test_ut2_tool2_label_exact(self, dashboard_window, qtbot, click_nav):
        """UT2 Tool 2 label must be exactly '🌐 webfetch: https://openweathermap.org/api'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut2 = root.child(1)
        tool2 = ut2.child(1)
        label = tool2.text(0)
        assert label == UT2_TOOL2_LABEL, (
            f"UT2 Tool2 label:\nExpected: {UT2_TOOL2_LABEL}\nGot: {label}"
        )

    def test_ut2_tool1_node_type_is_tool(self, dashboard_window, qtbot, click_nav):
        """UT2 Tool 1 node_type must be 'tool'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut2 = root.child(1)
        tool1 = ut2.child(0)
        data = get_item_data(tool1)
        assert data.get("node_type") == "tool"

    def test_ut2_tool1_tool_name_is_webfetch(self, dashboard_window, qtbot, click_nav):
        """UT2 Tool 1 tool_name must be 'webfetch'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut2 = root.child(1)
        tool1 = ut2.child(0)
        data = get_item_data(tool1)
        assert data.get("tool_name") == UT2_TOOL1_NAME

    def test_ut2_tool1_display_info_exact(self, dashboard_window, qtbot, click_nav):
        """UT2 Tool 1 display_info must be exactly 'https://www.weatherapi.com/'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut2 = root.child(1)
        tool1 = ut2.child(0)
        data = get_item_data(tool1)
        assert data.get("display_info") == UT2_TOOL1_DISPLAY

    def test_ut2_tool2_tool_name_is_webfetch(self, dashboard_window, qtbot, click_nav):
        """UT2 Tool 2 tool_name must be 'webfetch'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut2 = root.child(1)
        tool2 = ut2.child(1)
        data = get_item_data(tool2)
        assert data.get("tool_name") == UT2_TOOL2_NAME

    def test_ut2_tool2_display_info_exact(self, dashboard_window, qtbot, click_nav):
        """UT2 Tool 2 display_info must be exactly 'https://openweathermap.org/api'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut2 = root.child(1)
        tool2 = ut2.child(1)
        data = get_item_data(tool2)
        assert data.get("display_info") == UT2_TOOL2_DISPLAY


# =============================================================================
# TEST CLASS: Tool in User Turn 3
# =============================================================================


class TestUT3Tool:
    """Tests for tool in User Turn 3 - STRICT EQUALITY."""

    def test_ut3_tool1_label_exact(self, dashboard_window, qtbot, click_nav):
        """UT3 Tool 1 label must be exactly '🔧 bash: touch /tmp/test.txt'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut3 = root.child(2)
        tool1 = ut3.child(0)
        label = tool1.text(0)
        assert label == UT3_TOOL1_LABEL, (
            f"UT3 Tool1 label:\nExpected: {UT3_TOOL1_LABEL}\nGot: {label}"
        )

    def test_ut3_tool1_node_type_is_tool(self, dashboard_window, qtbot, click_nav):
        """UT3 Tool 1 node_type must be 'tool'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut3 = root.child(2)
        tool1 = ut3.child(0)
        data = get_item_data(tool1)
        assert data.get("node_type") == "tool"

    def test_ut3_tool1_tool_name_is_bash(self, dashboard_window, qtbot, click_nav):
        """UT3 Tool 1 tool_name must be 'bash'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut3 = root.child(2)
        tool1 = ut3.child(0)
        data = get_item_data(tool1)
        assert data.get("tool_name") == UT3_TOOL1_NAME

    def test_ut3_tool1_display_info_exact(self, dashboard_window, qtbot, click_nav):
        """UT3 Tool 1 display_info must be exactly 'touch /tmp/test.txt'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut3 = root.child(2)
        tool1 = ut3.child(0)
        data = get_item_data(tool1)
        assert data.get("display_info") == UT3_TOOL1_DISPLAY


# =============================================================================
# TEST CLASS: Tool in User Turn 4
# =============================================================================


class TestUT4Tool:
    """Tests for tool in User Turn 4 - STRICT EQUALITY."""

    def test_ut4_tool1_label_exact(self, dashboard_window, qtbot, click_nav):
        """UT4 Tool 1 label must be exactly '📖 read: /path/to/README.md'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut4 = root.child(3)
        tool1 = ut4.child(0)
        label = tool1.text(0)
        assert label == UT4_TOOL1_LABEL, (
            f"UT4 Tool1 label:\nExpected: {UT4_TOOL1_LABEL}\nGot: {label}"
        )

    def test_ut4_tool1_node_type_is_tool(self, dashboard_window, qtbot, click_nav):
        """UT4 Tool 1 node_type must be 'tool'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut4 = root.child(3)
        tool1 = ut4.child(0)
        data = get_item_data(tool1)
        assert data.get("node_type") == "tool"

    def test_ut4_tool1_tool_name_is_read(self, dashboard_window, qtbot, click_nav):
        """UT4 Tool 1 tool_name must be 'read'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut4 = root.child(3)
        tool1 = ut4.child(0)
        data = get_item_data(tool1)
        assert data.get("tool_name") == UT4_TOOL1_NAME

    def test_ut4_tool1_display_info_exact(self, dashboard_window, qtbot, click_nav):
        """UT4 Tool 1 display_info must be exactly '/path/to/README.md'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut4 = root.child(3)
        tool1 = ut4.child(0)
        data = get_item_data(tool1)
        assert data.get("display_info") == UT4_TOOL1_DISPLAY


# =============================================================================
# TEST CLASS: Delegation in User Turn 5
# =============================================================================


class TestUT5Delegation:
    """Tests for delegation in User Turn 5 - STRICT EQUALITY."""

    def test_ut5_child_is_agent(self, dashboard_window, qtbot, click_nav):
        """UT5 child must have node_type 'agent'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)
        data = get_item_data(delegation)
        assert data.get("node_type") == "agent", (
            f"Expected 'agent', got '{data.get('node_type')}'"
        )

    def test_delegation_label_exact(self, dashboard_window, qtbot, click_nav):
        """Delegation label must be exactly '🔗 plan → roadmap'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)
        label = delegation.text(0)
        assert label == DELEG_LABEL, (
            f"Delegation label:\nExpected: {DELEG_LABEL}\nGot: {label}"
        )

    def test_delegation_subagent_type_exact(self, dashboard_window, qtbot, click_nav):
        """Delegation subagent_type must be 'roadmap'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)
        data = get_item_data(delegation)
        assert data.get("subagent_type") == DELEG_AGENT_TYPE

    def test_delegation_parent_agent_exact(self, dashboard_window, qtbot, click_nav):
        """Delegation parent_agent must be 'plan'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)
        data = get_item_data(delegation)
        assert data.get("parent_agent") == DELEG_PARENT_AGENT

    def test_delegation_has_exactly_2_children(
        self, dashboard_window, qtbot, click_nav
    ):
        """Delegation must have exactly 2 children (2 read tools)."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)
        count = delegation.childCount()
        assert count == DELEG_TOOL_COUNT, (
            f"Delegation children: expected {DELEG_TOOL_COUNT}, got {count}"
        )


# =============================================================================
# TEST CLASS: Tools in Delegation
# =============================================================================


class TestDelegationTools:
    """Tests for tools inside the delegation - STRICT EQUALITY."""

    def test_deleg_tool1_label_exact(self, dashboard_window, qtbot, click_nav):
        """Delegation Tool 1 label must be exactly '📖 read: /path/to/roadmap/README.md'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)
        tool1 = delegation.child(0)
        label = tool1.text(0)
        assert label == DELEG_TOOL1_LABEL, (
            f"Deleg Tool1 label:\nExpected: {DELEG_TOOL1_LABEL}\nGot: {label}"
        )

    def test_deleg_tool2_label_exact(self, dashboard_window, qtbot, click_nav):
        """Delegation Tool 2 label must be exactly '📖 read: /path/to/roadmap/SPRINTS.md'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)
        tool2 = delegation.child(1)
        label = tool2.text(0)
        assert label == DELEG_TOOL2_LABEL, (
            f"Deleg Tool2 label:\nExpected: {DELEG_TOOL2_LABEL}\nGot: {label}"
        )

    def test_deleg_tool1_node_type_is_tool(self, dashboard_window, qtbot, click_nav):
        """Delegation Tool 1 node_type must be 'tool'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)
        tool1 = delegation.child(0)
        data = get_item_data(tool1)
        assert data.get("node_type") == "tool"

    def test_deleg_tool1_tool_name_is_read(self, dashboard_window, qtbot, click_nav):
        """Delegation Tool 1 tool_name must be 'read'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)
        tool1 = delegation.child(0)
        data = get_item_data(tool1)
        assert data.get("tool_name") == DELEG_TOOL1_NAME

    def test_deleg_tool1_display_info_exact(self, dashboard_window, qtbot, click_nav):
        """Delegation Tool 1 display_info must be exactly '/path/to/roadmap/README.md'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)
        tool1 = delegation.child(0)
        data = get_item_data(tool1)
        assert data.get("display_info") == DELEG_TOOL1_DISPLAY

    def test_deleg_tool2_node_type_is_tool(self, dashboard_window, qtbot, click_nav):
        """Delegation Tool 2 node_type must be 'tool'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)
        tool2 = delegation.child(1)
        data = get_item_data(tool2)
        assert data.get("node_type") == "tool"

    def test_deleg_tool2_tool_name_is_read(self, dashboard_window, qtbot, click_nav):
        """Delegation Tool 2 tool_name must be 'read'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)
        tool2 = delegation.child(1)
        data = get_item_data(tool2)
        assert data.get("tool_name") == DELEG_TOOL2_NAME

    def test_deleg_tool2_display_info_exact(self, dashboard_window, qtbot, click_nav):
        """Delegation Tool 2 display_info must be exactly '/path/to/roadmap/SPRINTS.md'."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)
        tool2 = delegation.child(1)
        data = get_item_data(tool2)
        assert data.get("display_info") == DELEG_TOOL2_DISPLAY


# =============================================================================
# TEST CLASS: Total Counts
# =============================================================================


class TestTotalCounts:
    """Tests for total counts across the entire tree - STRICT EQUALITY."""

    def test_exactly_6_tools_total(self, dashboard_window, qtbot, click_nav):
        """Must have exactly 6 tool items in total."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        tools = find_items_by_node_type(tracing._tree, "tool")
        count = len(tools)
        assert count == TOTAL_TOOLS, f"Total tools: expected {TOTAL_TOOLS}, got {count}"

    def test_exactly_1_delegation_total(self, dashboard_window, qtbot, click_nav):
        """Must have exactly 1 agent (delegation) item."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        agents = find_items_by_node_type(tracing._tree, "agent")
        count = len(agents)
        assert count == TOTAL_DELEGATIONS, (
            f"Total delegations: expected {TOTAL_DELEGATIONS}, got {count}"
        )

    def test_exactly_2_webfetch_tools(self, dashboard_window, qtbot, click_nav):
        """Must have exactly 2 webfetch tools."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        webfetch_tools = find_items_by_tool_name(tracing._tree, "webfetch")
        count = len(webfetch_tools)
        assert count == 2, f"webfetch tools: expected 2, got {count}"

    def test_exactly_1_bash_tool(self, dashboard_window, qtbot, click_nav):
        """Must have exactly 1 bash tool."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        bash_tools = find_items_by_tool_name(tracing._tree, "bash")
        count = len(bash_tools)
        assert count == 1, f"bash tools: expected 1, got {count}"

    def test_exactly_3_read_tools(self, dashboard_window, qtbot, click_nav):
        """Must have exactly 3 read tools (1 in UT4 + 2 in delegation)."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        read_tools = find_items_by_tool_name(tracing._tree, "read")
        count = len(read_tools)
        assert count == 3, f"read tools: expected 3, got {count}"

    def test_total_items_in_tree(self, dashboard_window, qtbot, click_nav):
        """Total items must be exactly 13 (1 root + 5 UT + 6 tools + 1 delegation)."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        all_items = get_all_tree_items(tracing._tree)
        expected = 1 + TOTAL_USER_TURNS + TOTAL_TOOLS + TOTAL_DELEGATIONS  # 13
        count = len(all_items)
        assert count == expected, f"Total items: expected {expected}, got {count}"


# =============================================================================
# TEST CLASS: Hierarchy Validation
# =============================================================================


class TestHierarchy:
    """Tests for parent-child relationships - STRICT EQUALITY."""

    def test_ut2_tools_parent_is_ut2(self, dashboard_window, qtbot, click_nav):
        """UT2 tools must have UT2 as their parent."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut2 = root.child(1)

        for i in range(ut2.childCount()):
            tool = ut2.child(i)
            assert tool.parent() == ut2, f"Tool {i} parent mismatch"

    def test_ut3_tool_parent_is_ut3(self, dashboard_window, qtbot, click_nav):
        """UT3 tool must have UT3 as its parent."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut3 = root.child(2)
        tool = ut3.child(0)

        assert tool.parent() == ut3, "UT3 tool parent mismatch"

    def test_ut4_tool_parent_is_ut4(self, dashboard_window, qtbot, click_nav):
        """UT4 tool must have UT4 as its parent."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut4 = root.child(3)
        tool = ut4.child(0)

        assert tool.parent() == ut4, "UT4 tool parent mismatch"

    def test_delegation_parent_is_ut5(self, dashboard_window, qtbot, click_nav):
        """Delegation must have UT5 as its parent."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)

        assert delegation.parent() == ut5, "Delegation parent mismatch"

    def test_delegation_tools_parent_is_delegation(
        self, dashboard_window, qtbot, click_nav
    ):
        """Delegation tools must have delegation as their parent."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)

        for i in range(delegation.childCount()):
            tool = delegation.child(i)
            assert tool.parent() == delegation, f"Delegation tool {i} parent mismatch"

    def test_all_user_turns_parent_is_root(self, dashboard_window, qtbot, click_nav):
        """All user turns must have root as their parent."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)

        for i in range(TOTAL_USER_TURNS):
            ut = root.child(i)
            assert ut.parent() == root, f"UT{i + 1} parent mismatch"


# =============================================================================
# TEST CLASS: Order Validation
# =============================================================================


class TestOrder:
    """Tests for item order - STRICT EQUALITY."""

    def test_user_turns_order(self, dashboard_window, qtbot, click_nav):
        """User turns must be in exact order: UT1, UT2, UT3, UT4, UT5."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)

        expected_labels = [UT1_LABEL, UT2_LABEL, UT3_LABEL, UT4_LABEL, UT5_LABEL]

        for i, expected in enumerate(expected_labels):
            ut = root.child(i)
            actual = ut.text(0)
            assert actual == expected, (
                f"Order mismatch at index {i}:\nExpected: {expected}\nGot: {actual}"
            )

    def test_ut2_tools_order(self, dashboard_window, qtbot, click_nav):
        """UT2 tools must be in order: weatherapi, openweathermap."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut2 = root.child(1)

        tool1_label = ut2.child(0).text(0)
        tool2_label = ut2.child(1).text(0)

        assert tool1_label == UT2_TOOL1_LABEL, f"UT2 Tool1 order mismatch"
        assert tool2_label == UT2_TOOL2_LABEL, f"UT2 Tool2 order mismatch"

    def test_delegation_tools_order(self, dashboard_window, qtbot, click_nav):
        """Delegation tools must be in order: README.md, SPRINTS.md."""
        tracing = load_and_expand(dashboard_window, qtbot, click_nav)

        root = tracing._tree.topLevelItem(0)
        ut5 = root.child(4)
        delegation = ut5.child(0)

        tool1_label = delegation.child(0).text(0)
        tool2_label = delegation.child(1).text(0)

        assert tool1_label == DELEG_TOOL1_LABEL, f"Deleg Tool1 order mismatch"
        assert tool2_label == DELEG_TOOL2_LABEL, f"Deleg Tool2 order mismatch"
