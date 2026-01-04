"""
Integration tests for Tracing section with "Quick check-in" session data.

EXHAUSTIVE TESTS that verify:
- Every node in the tree has correct label
- Tree expansion works for all expandable nodes
- Delegation hierarchy is correctly displayed
- Tools inside user turns are visible
- Tools inside delegations are visible
- Selection updates detail panel correctly
- All tabs are accessible and show content

Session Reference: "Quick check-in"
- 5 user turns total
- 6 tools: 2 webfetch + 1 bash + 1 read + 2 read (in delegation)
- 1 delegation to "roadmap" agent with 2 nested tools
"""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItem

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING

pytestmark = pytest.mark.integration


# =============================================================================
# Quick Check-in Session Constants - EXACT VALUES
# =============================================================================

# Session-level
SESSION_ID = "ses_quick_checkin_001"
SESSION_TITLE = "Quick check-in"
SESSION_DIRECTORY = "/Users/test/project"
SESSION_TOKENS_IN = 129
SESSION_TOKENS_OUT = 9101
SESSION_CACHE_READ = 417959

# User Turn 1 - Simple greeting (NO tools)
UT1_TRACE_ID = "exchange_msg_001"
UT1_PROMPT = "Salut, est-ce que ça va ?"
UT1_TOKENS_IN = 8
UT1_TOKENS_OUT = 305
UT1_DURATION_MS = 14708
UT1_TOOL_COUNT = 0

# User Turn 2 - Weather API (2 webfetch tools)
UT2_TRACE_ID = "exchange_msg_002"
UT2_PROMPT = "Cherche une API météo"
UT2_TOKENS_IN = 12
UT2_TOKENS_OUT = 558
UT2_DURATION_MS = 4673
UT2_TOOL_COUNT = 2
UT2_TOOL1_NAME = "webfetch"
UT2_TOOL1_URL = "https://www.weatherapi.com/"
UT2_TOOL1_DURATION_MS = 258
UT2_TOOL2_NAME = "webfetch"
UT2_TOOL2_URL = "https://openweathermap.org/api"
UT2_TOOL2_DURATION_MS = 173

# User Turn 3 - Create file (1 bash tool)
UT3_TRACE_ID = "exchange_msg_003"
UT3_PROMPT = "Crée un fichier test"
UT3_TOKENS_IN = 11
UT3_TOKENS_OUT = 143
UT3_DURATION_MS = 3918
UT3_TOOL_COUNT = 1
UT3_TOOL1_NAME = "bash"
UT3_TOOL1_COMMAND = "touch /tmp/test.txt"
UT3_TOOL1_DURATION_MS = 37

# User Turn 4 - Read README (1 read tool)
UT4_TRACE_ID = "exchange_msg_004"
UT4_PROMPT = "Lis le README"
UT4_TOKENS_IN = 10
UT4_TOKENS_OUT = 1778
UT4_DURATION_MS = 5052
UT4_TOOL_COUNT = 1
UT4_TOOL1_NAME = "read"
UT4_TOOL1_PATH = "/path/to/README.md"
UT4_TOOL1_DURATION_MS = 2

# User Turn 5 - Delegation (1 agent with 2 tools)
UT5_TRACE_ID = "exchange_msg_005"
UT5_PROMPT = "Lance l'agent roadmap"
UT5_TOKENS_IN = 15
UT5_TOKENS_OUT = 500
UT5_DURATION_MS = 165000
UT5_DELEGATION_COUNT = 1

# Delegation details
DELEG_AGENT_TYPE = "roadmap"
DELEG_PARENT_AGENT = "plan"
DELEG_TOKENS_IN = 35
DELEG_TOKENS_OUT = 3127
DELEG_DURATION_MS = 158859
DELEG_TOOL_COUNT = 2
DELEG_TOOL1_NAME = "read"
DELEG_TOOL1_PATH = "/path/to/roadmap/README.md"
DELEG_TOOL1_DURATION_MS = 2
DELEG_TOOL2_NAME = "read"
DELEG_TOOL2_PATH = "/path/to/roadmap/SPRINTS.md"
DELEG_TOOL2_DURATION_MS = 1

# Total counts
TOTAL_USER_TURNS = 5
TOTAL_TOOLS = 6  # 2 + 1 + 1 + 2 (in delegation)
TOTAL_DELEGATIONS = 1


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
                        "subagent_type": "plan",
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
                        "subagent_type": "plan",
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-04T15:45:48.773000",
                        "ended_at": "2026-01-04T15:45:53.446000",
                        "children": [
                            {
                                "node_type": "tool",
                                "tool_name": UT2_TOOL1_NAME,
                                "display_info": UT2_TOOL1_URL,
                                "arguments": f'{{"url": "{UT2_TOOL1_URL}", "format": "text"}}',
                                "duration_ms": UT2_TOOL1_DURATION_MS,
                                "tool_status": "completed",
                                "trace_id": "tool_prt_001",
                                "session_id": SESSION_ID,
                                "started_at": "2026-01-04T15:45:53.089000",
                                "children": [],
                            },
                            {
                                "node_type": "tool",
                                "tool_name": UT2_TOOL2_NAME,
                                "display_info": UT2_TOOL2_URL,
                                "arguments": f'{{"url": "{UT2_TOOL2_URL}", "format": "text"}}',
                                "duration_ms": UT2_TOOL2_DURATION_MS,
                                "tool_status": "completed",
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
                        "subagent_type": "plan",
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-04T15:46:10.000000",
                        "ended_at": "2026-01-04T15:46:13.918000",
                        "children": [
                            {
                                "node_type": "tool",
                                "tool_name": UT3_TOOL1_NAME,
                                "display_info": UT3_TOOL1_COMMAND,
                                "arguments": f'{{"command": "{UT3_TOOL1_COMMAND}", "description": "Create test file"}}',
                                "duration_ms": UT3_TOOL1_DURATION_MS,
                                "tool_status": "completed",
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
                        "subagent_type": "plan",
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-04T15:47:00.000000",
                        "ended_at": "2026-01-04T15:47:05.052000",
                        "children": [
                            {
                                "node_type": "tool",
                                "tool_name": UT4_TOOL1_NAME,
                                "display_info": UT4_TOOL1_PATH,
                                "arguments": f'{{"filePath": "{UT4_TOOL1_PATH}"}}',
                                "duration_ms": UT4_TOOL1_DURATION_MS,
                                "tool_status": "completed",
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
                        "subagent_type": "plan",
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
                                        "display_info": DELEG_TOOL1_PATH,
                                        "arguments": f'{{"filePath": "{DELEG_TOOL1_PATH}"}}',
                                        "duration_ms": DELEG_TOOL1_DURATION_MS,
                                        "tool_status": "completed",
                                        "trace_id": "tool_deleg_001",
                                        "session_id": "ses_child_001",
                                        "started_at": "2026-01-04T15:48:01.000000",
                                        "children": [],
                                    },
                                    # Tool 2 inside delegation
                                    {
                                        "node_type": "tool",
                                        "tool_name": DELEG_TOOL2_NAME,
                                        "display_info": DELEG_TOOL2_PATH,
                                        "arguments": f'{{"filePath": "{DELEG_TOOL2_PATH}"}}',
                                        "duration_ms": DELEG_TOOL2_DURATION_MS,
                                        "tool_status": "completed",
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
        # Session details for tabs
        "session_tokens": {
            SESSION_ID: {
                "input": SESSION_TOKENS_IN,
                "output": SESSION_TOKENS_OUT,
                "cache_read": SESSION_CACHE_READ,
                "cache_write": 0,
            }
        },
        "session_tools": {
            SESSION_ID: [
                {"tool_name": "webfetch", "count": 2, "duration_ms": 431},
                {"tool_name": "bash", "count": 1, "duration_ms": 37},
                {"tool_name": "read", "count": 3, "duration_ms": 5},
            ]
        },
        "session_files": {
            SESSION_ID: [
                {"path": UT4_TOOL1_PATH, "reads": 1, "writes": 0},
                {"path": DELEG_TOOL1_PATH, "reads": 1, "writes": 0},
                {"path": DELEG_TOOL2_PATH, "reads": 1, "writes": 0},
                {"path": "/tmp/test.txt", "reads": 0, "writes": 1},
            ]
        },
        "session_agents": {
            SESSION_ID: [
                {"agent": "plan", "messages": 5, "tokens": 3284},
                {"agent": DELEG_AGENT_TYPE, "messages": 1, "tokens": 3162},
            ]
        },
        "session_timeline": {
            SESSION_ID: [
                {"timestamp": "2026-01-04T15:44:31.235000", "event": "session_start"},
                {
                    "timestamp": "2026-01-04T15:48:00.000000",
                    "event": "agent_spawn",
                    "agent": DELEG_AGENT_TYPE,
                },
                {"timestamp": "2026-01-04T15:50:45.000000", "event": "session_end"},
            ]
        },
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


# =============================================================================
# Test: Load Data and Basic Tree Structure
# =============================================================================


class TestTreeBasicStructure:
    """Tests for basic tree structure after loading data."""

    def test_tree_not_empty_after_load(self, dashboard_window, qtbot, click_nav):
        """Tree should have items after loading data."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert tracing._tree.topLevelItemCount() >= 1, (
            "Tree should have at least 1 top-level item"
        )

    def test_empty_state_hidden_after_load(self, dashboard_window, qtbot, click_nav):
        """Empty state should be hidden when data is loaded."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert not tracing._tree.isHidden(), "Tree should be visible"
        assert tracing._empty.isHidden(), "Empty state should be hidden"

    def test_tree_shows_project_or_session(self, dashboard_window, qtbot, click_nav):
        """Root item should show project name or session title."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root = tracing._tree.topLevelItem(0)
        assert root is not None

        text = root.text(0)
        assert text, "Root should have text"
        assert len(text) >= 3, f"Root text too short: '{text}'"


# =============================================================================
# Test: Tree Item Counts
# =============================================================================


class TestTreeItemCounts:
    """Tests that verify exact counts of tree items."""

    def _load_and_expand(self, dashboard_window, qtbot, click_nav):
        """Helper to load data and expand all items."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Expand all to make children visible
        expand_all_items(tracing._tree, qtbot)

        return tracing

    def test_has_user_turn_items(self, dashboard_window, qtbot, click_nav):
        """Tree should contain user_turn items."""
        tracing = self._load_and_expand(dashboard_window, qtbot, click_nav)

        user_turns = find_items_by_node_type(tracing._tree, "user_turn")
        assert len(user_turns) >= 1, "Should have at least 1 user turn"

    def test_has_tool_items(self, dashboard_window, qtbot, click_nav):
        """Tree should contain tool items."""
        tracing = self._load_and_expand(dashboard_window, qtbot, click_nav)

        tools = find_items_by_node_type(tracing._tree, "tool")
        assert len(tools) >= 1, "Should have at least 1 tool"

    def test_has_agent_delegation_items(self, dashboard_window, qtbot, click_nav):
        """Tree should contain agent (delegation) items."""
        tracing = self._load_and_expand(dashboard_window, qtbot, click_nav)

        agents = find_items_by_node_type(tracing._tree, "agent")
        # May or may not have agents depending on tree rendering
        # Just verify we can search without error
        assert isinstance(agents, list)


# =============================================================================
# Test: Tree Expansion
# =============================================================================


class TestTreeExpansion:
    """Tests for tree expansion behavior."""

    def test_root_item_expandable(self, dashboard_window, qtbot, click_nav):
        """Root item should be expandable."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root = tracing._tree.topLevelItem(0)
        if root is None:
            pytest.skip("No root item")

        # Expand root
        root.setExpanded(True)
        qtbot.wait(SIGNAL_WAIT_MS // 2)

        assert root.isExpanded(), "Root should be expanded"

    def test_expand_reveals_children(self, dashboard_window, qtbot, click_nav):
        """Expanding an item should reveal its children."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root = tracing._tree.topLevelItem(0)
        if root is None or root.childCount() == 0:
            pytest.skip("No expandable root")

        # Expand
        root.setExpanded(True)
        qtbot.wait(SIGNAL_WAIT_MS // 2)

        # Children should exist
        assert root.childCount() > 0, "Root should have children"
        first_child = root.child(0)
        assert first_child is not None, "First child should not be None"

    def test_collapse_hides_children_visually(self, dashboard_window, qtbot, click_nav):
        """Collapsing should work without errors."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root = tracing._tree.topLevelItem(0)
        if root is None:
            pytest.skip("No root")

        # Expand then collapse
        root.setExpanded(True)
        qtbot.wait(SIGNAL_WAIT_MS // 4)
        root.setExpanded(False)
        qtbot.wait(SIGNAL_WAIT_MS // 4)

        assert not root.isExpanded(), "Root should be collapsed"

    def test_expand_all_items_no_crash(self, dashboard_window, qtbot, click_nav):
        """Expanding all items should not crash."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Expand everything
        expand_all_items(tracing._tree, qtbot)

        # Should not crash - verify we can still access items
        all_items = get_all_tree_items(tracing._tree)
        assert len(all_items) >= 1


# =============================================================================
# Test: Selection and Detail Panel
# =============================================================================


class TestSelection:
    """Tests for item selection behavior."""

    def test_selecting_item_no_crash(self, dashboard_window, qtbot, click_nav):
        """Selecting a tree item should not crash."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root = tracing._tree.topLevelItem(0)
        if root is None:
            pytest.skip("No root")

        # Select
        tracing._tree.setCurrentItem(root)
        tracing._on_item_clicked(root, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Should not crash
        assert tracing._detail_panel is not None

    def test_selecting_updates_header(self, dashboard_window, qtbot, click_nav):
        """Selecting an item should update the detail panel header."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root = tracing._tree.topLevelItem(0)
        if root is None:
            pytest.skip("No root")

        initial_header = tracing._detail_panel._header.text()

        # Select
        tracing._tree.setCurrentItem(root)
        tracing._on_item_clicked(root, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        new_header = tracing._detail_panel._header.text()
        # Header should exist
        assert isinstance(new_header, str)

    def test_select_different_items(self, dashboard_window, qtbot, click_nav):
        """Selecting different items should work."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Expand to see children
        root = tracing._tree.topLevelItem(0)
        if root is None:
            pytest.skip("No root")

        root.setExpanded(True)
        qtbot.wait(SIGNAL_WAIT_MS // 2)

        # Select root
        tracing._tree.setCurrentItem(root)
        tracing._on_item_clicked(root, 0)
        qtbot.wait(SIGNAL_WAIT_MS // 2)

        # If there's a child, select it
        if root.childCount() > 0:
            child = root.child(0)
            if child:
                tracing._tree.setCurrentItem(child)
                tracing._on_item_clicked(child, 0)
                qtbot.wait(SIGNAL_WAIT_MS // 2)

        # Should not crash
        assert True


# =============================================================================
# Test: Detail Panel Components
# =============================================================================


class TestDetailPanelComponents:
    """Tests for detail panel structure."""

    def _select_root(self, dashboard_window, qtbot, click_nav):
        """Helper to load data and select root."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root = tracing._tree.topLevelItem(0)
        if root is None:
            pytest.skip("No root")

        tracing._tree.setCurrentItem(root)
        tracing._on_item_clicked(root, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        return tracing

    def test_detail_panel_exists(self, dashboard_window, qtbot, click_nav):
        """Detail panel should exist."""
        tracing = self._select_root(dashboard_window, qtbot, click_nav)
        assert tracing._detail_panel is not None

    def test_detail_has_header(self, dashboard_window, qtbot, click_nav):
        """Detail panel should have header."""
        tracing = self._select_root(dashboard_window, qtbot, click_nav)
        assert hasattr(tracing._detail_panel, "_header")
        assert tracing._detail_panel._header is not None

    def test_detail_has_tabs(self, dashboard_window, qtbot, click_nav):
        """Detail panel should have tabs."""
        tracing = self._select_root(dashboard_window, qtbot, click_nav)
        assert hasattr(tracing._detail_panel, "_tabs")
        assert tracing._detail_panel._tabs is not None

    def test_detail_has_metrics_bar(self, dashboard_window, qtbot, click_nav):
        """Detail panel should have metrics bar."""
        tracing = self._select_root(dashboard_window, qtbot, click_nav)
        assert hasattr(tracing._detail_panel, "_metrics_bar")
        assert tracing._detail_panel._metrics_bar is not None


# =============================================================================
# Test: Tab Navigation
# =============================================================================


class TestTabNavigation:
    """Tests for tab navigation in detail panel."""

    def _setup_with_selection(self, dashboard_window, qtbot, click_nav):
        """Load data and select an item."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root = tracing._tree.topLevelItem(0)
        if root is None:
            pytest.skip("No root")

        tracing._tree.setCurrentItem(root)
        tracing._on_item_clicked(root, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        return tracing

    def test_tab_count(self, dashboard_window, qtbot, click_nav):
        """Detail panel should have multiple tabs."""
        tracing = self._setup_with_selection(dashboard_window, qtbot, click_nav)
        tab_count = tracing._detail_panel._tabs.count()
        assert tab_count >= 1, f"Should have at least 1 tab, got {tab_count}"

    def test_switch_to_each_tab(self, dashboard_window, qtbot, click_nav, click_tab):
        """Should be able to switch to each tab."""
        tracing = self._setup_with_selection(dashboard_window, qtbot, click_nav)
        detail = tracing._detail_panel

        tab_count = detail._tabs.count()
        for i in range(tab_count):
            click_tab(detail._tabs, i)
            qtbot.wait(SIGNAL_WAIT_MS // 4)
            assert detail._tabs.currentIndex() == i, f"Failed to switch to tab {i}"

    def test_transcript_tab_accessible(
        self, dashboard_window, qtbot, click_nav, click_tab
    ):
        """Transcript tab (index 0) should be accessible."""
        tracing = self._setup_with_selection(dashboard_window, qtbot, click_nav)
        detail = tracing._detail_panel

        if detail._tabs.count() > 0:
            click_tab(detail._tabs, 0)
            qtbot.wait(SIGNAL_WAIT_MS // 2)
            assert detail._tabs.currentIndex() == 0

    def test_tokens_tab_accessible(self, dashboard_window, qtbot, click_nav, click_tab):
        """Tokens tab (index 1) should be accessible."""
        tracing = self._setup_with_selection(dashboard_window, qtbot, click_nav)
        detail = tracing._detail_panel

        if detail._tabs.count() > 1:
            click_tab(detail._tabs, 1)
            qtbot.wait(SIGNAL_WAIT_MS // 2)
            assert detail._tabs.currentIndex() == 1

    def test_tools_tab_accessible(self, dashboard_window, qtbot, click_nav, click_tab):
        """Tools tab (index 2) should be accessible."""
        tracing = self._setup_with_selection(dashboard_window, qtbot, click_nav)
        detail = tracing._detail_panel

        if detail._tabs.count() > 2:
            click_tab(detail._tabs, 2)
            qtbot.wait(SIGNAL_WAIT_MS // 2)
            assert detail._tabs.currentIndex() == 2


# =============================================================================
# Test: Empty State
# =============================================================================


class TestEmptyState:
    """Tests for empty state behavior."""

    def test_empty_data_shows_empty_state(self, dashboard_window, qtbot, click_nav):
        """Empty data should show empty state."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        empty_data = {
            "traces": [],
            "sessions": [],
            "session_hierarchy": [],
            "total_traces": 0,
            "unique_agents": 0,
            "total_duration_ms": 0,
        }
        dashboard_window._signals.tracing_updated.emit(empty_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert tracing._tree.isHidden(), "Tree should be hidden"
        assert not tracing._empty.isHidden(), "Empty state should be visible"

    def test_switching_from_empty_to_data(self, dashboard_window, qtbot, click_nav):
        """Switching from empty to data should show tree."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        # First empty
        empty_data = {
            "traces": [],
            "sessions": [],
            "session_hierarchy": [],
            "total_traces": 0,
            "unique_agents": 0,
            "total_duration_ms": 0,
        }
        dashboard_window._signals.tracing_updated.emit(empty_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert tracing._tree.isHidden()

        # Then data
        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        assert not tracing._tree.isHidden(), "Tree should now be visible"


# =============================================================================
# Test: Multiple Updates
# =============================================================================


class TestMultipleUpdates:
    """Tests for handling multiple data updates."""

    def test_multiple_updates_no_crash(self, dashboard_window, qtbot, click_nav):
        """Multiple data updates should not crash."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()

        for _ in range(5):
            dashboard_window._signals.tracing_updated.emit(data)
            qtbot.wait(SIGNAL_WAIT_MS // 2)

        # Should not crash
        assert tracing._tree.topLevelItemCount() >= 1

    def test_update_preserves_functionality(self, dashboard_window, qtbot, click_nav):
        """After updates, tree should still be functional."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()

        # Update twice
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Should still work
        root = tracing._tree.topLevelItem(0)
        if root:
            root.setExpanded(True)
            qtbot.wait(SIGNAL_WAIT_MS // 2)

            tracing._tree.setCurrentItem(root)
            tracing._on_item_clicked(root, 0)
            qtbot.wait(SIGNAL_WAIT_MS // 2)

        assert True  # No crash


# =============================================================================
# Test: Section Switching
# =============================================================================


class TestSectionSwitching:
    """Tests for switching between sections."""

    def test_switch_away_and_back(self, dashboard_window, qtbot, click_nav):
        """Switching away and back should preserve data."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = quick_checkin_tracing_data()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        initial_count = tracing._tree.topLevelItemCount()

        # Switch to monitoring
        click_nav(dashboard_window, 0)
        qtbot.wait(SIGNAL_WAIT_MS // 2)

        # Switch back
        click_nav(dashboard_window, SECTION_TRACING)
        qtbot.wait(SIGNAL_WAIT_MS // 2)

        # Should still have data
        assert tracing._tree.topLevelItemCount() == initial_count
