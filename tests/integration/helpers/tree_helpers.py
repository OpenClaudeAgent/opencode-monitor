"""
Tree traversal helpers for Tracing section integration tests.

Provides reusable functions for:
- Traversing QTreeWidget items
- Extracting item data
- Finding items by node_type or tool_name
- Expanding all items
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem


def get_all_tree_items(tree_widget: QTreeWidget) -> list[QTreeWidgetItem]:
    """Get all items in tree (flattened).

    Args:
        tree_widget: The QTreeWidget to traverse

    Returns:
        List of all QTreeWidgetItem in the tree (depth-first)
    """
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
    """Get the data stored in a tree item.

    Args:
        item: The tree item to extract data from

    Returns:
        Dict of item data (node_type, tool_name, etc.)
    """
    return item.data(0, Qt.ItemDataRole.UserRole) or {}


def find_items_by_node_type(
    tree_widget: QTreeWidget, node_type: str
) -> list[QTreeWidgetItem]:
    """Find all items with a specific node_type.

    Args:
        tree_widget: The QTreeWidget to search
        node_type: The node_type to match (e.g., "session", "user_turn", "tool")

    Returns:
        List of matching QTreeWidgetItems
    """
    result = []
    for item in get_all_tree_items(tree_widget):
        data = get_item_data(item)
        if data.get("node_type") == node_type:
            result.append(item)
    return result


def find_items_by_tool_name(
    tree_widget: QTreeWidget, tool_name: str
) -> list[QTreeWidgetItem]:
    """Find all tool items with a specific tool_name.

    Args:
        tree_widget: The QTreeWidget to search
        tool_name: The tool_name to match (e.g., "webfetch", "bash", "read")

    Returns:
        List of matching QTreeWidgetItems (node_type == "tool")
    """
    result = []
    for item in get_all_tree_items(tree_widget):
        data = get_item_data(item)
        if data.get("node_type") == "tool" and data.get("tool_name") == tool_name:
            result.append(item)
    return result


def expand_all_items(tree_widget: QTreeWidget, qtbot, wait_ms: int = 50) -> None:
    """Expand all items in the tree.

    Args:
        tree_widget: The QTreeWidget to expand
        qtbot: pytest-qt's qtbot fixture
        wait_ms: Time to wait after expanding (default 50ms)
    """
    for item in get_all_tree_items(tree_widget):
        if item.childCount() > 0:
            item.setExpanded(True)
    qtbot.wait(wait_ms)
