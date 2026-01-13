from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtWidgets import QTreeView, QTreeWidget, QTreeWidgetItem


def get_all_tree_indexes(tree_view: QTreeView) -> list[QModelIndex]:
    model = tree_view.model()
    if model is None:
        return []

    indexes = []

    def collect(parent: QModelIndex):
        rows = model.rowCount(parent)
        for row in range(rows):
            index = model.index(row, 0, parent)
            if index.isValid():
                indexes.append(index)
                collect(index)

    collect(QModelIndex())
    return indexes


def get_index_data(tree_view: QTreeView, index: QModelIndex) -> dict:
    model = tree_view.model()
    if model is None:
        return {}
    return model.data(index, Qt.ItemDataRole.UserRole) or {}


def find_indexes_by_node_type(
    tree_view: QTreeView, node_type: str
) -> list[QModelIndex]:
    result = []
    for index in get_all_tree_indexes(tree_view):
        data = get_index_data(tree_view, index)
        if data.get("node_type") == node_type:
            result.append(index)
    return result


def find_indexes_by_tool_name(
    tree_view: QTreeView, tool_name: str
) -> list[QModelIndex]:
    result = []
    for index in get_all_tree_indexes(tree_view):
        data = get_index_data(tree_view, index)
        if data.get("node_type") == "tool" and data.get("tool_name") == tool_name:
            result.append(index)
    return result


def expand_all_indexes(tree_view: QTreeView) -> None:
    from PyQt6.QtWidgets import QApplication

    tree_view.expandAll()
    QApplication.processEvents()


# Legacy QTreeWidget support (deprecated - for backward compatibility)


def get_all_tree_items(tree_widget: QTreeWidget) -> list[QTreeWidgetItem]:
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
    return item.data(0, Qt.ItemDataRole.UserRole) or {}


def find_items_by_node_type(
    tree_widget: QTreeWidget, node_type: str
) -> list[QTreeWidgetItem]:
    result = []
    for item in get_all_tree_items(tree_widget):
        data = get_item_data(item)
        if data.get("node_type") == node_type:
            result.append(item)
    return result


def find_items_by_tool_name(
    tree_widget: QTreeWidget, tool_name: str
) -> list[QTreeWidgetItem]:
    result = []
    for item in get_all_tree_items(tree_widget):
        data = get_item_data(item)
        if data.get("node_type") == "tool" and data.get("tool_name") == tool_name:
            result.append(item)
    return result


def expand_all_items(tree_widget: QTreeWidget) -> None:
    from PyQt6.QtWidgets import QApplication

    for item in get_all_tree_items(tree_widget):
        if item.childCount() > 0:
            item.setExpanded(True)
    QApplication.processEvents()
