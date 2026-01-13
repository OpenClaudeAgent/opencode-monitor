from typing import Any, Optional

from PyQt6.QtCore import QAbstractItemModel, QModelIndex, Qt

from .tree_formatters import get_display_text, get_foreground_color, get_tooltip


class TreeNode:
    def __init__(self, data: dict, parent: Optional["TreeNode"] = None):
        self.data = data
        self.parent = parent
        self.children: list[TreeNode] = []

    def add_child(self, child: "TreeNode") -> None:
        child.parent = self
        self.children.append(child)

    def child(self, row: int) -> Optional["TreeNode"]:
        if 0 <= row < len(self.children):
            return self.children[row]
        return None

    def child_count(self) -> int:
        return len(self.children)

    def row(self) -> int:
        if self.parent:
            return self.parent.children.index(self)
        return 0

    def get_data(self, column: int, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.UserRole:
            return self.data
        if role == Qt.ItemDataRole.DisplayRole:
            return get_display_text(self.data, column)
        if role == Qt.ItemDataRole.ForegroundRole:
            return get_foreground_color(self.data, column)
        if role == Qt.ItemDataRole.ToolTipRole:
            return get_tooltip(self.data, column)
        return None


class TracingTreeModel(QAbstractItemModel):
    """Tree model for tracing data with virtualization support.

    Uses QAbstractItemModel to enable efficient rendering of large
    hierarchical datasets with thousands of nodes.
    """

    def __init__(self, parent=None):
        """Initialize the tree model."""
        super().__init__(parent)
        self._root = TreeNode({"node_type": "root"})
        self._column_count = 6
        self._headers = ["Name", "Time", "Duration", "In", "Out", ""]

    def clear(self) -> None:
        """Clear all data from the model."""
        self.beginResetModel()
        self._root = TreeNode({"node_type": "root"})
        self.endResetModel()

    def set_sessions(self, sessions: list[dict]) -> None:
        self.beginResetModel()
        self._root = TreeNode({"node_type": "root"})

        for session_data in sessions:
            root_data = {**session_data, "_is_tree_root": True}
            self._build_session_node(self._root, root_data)

        self.endResetModel()

    def _build_session_node(self, parent: TreeNode, session_data: dict) -> TreeNode:
        """Build a session node and its children recursively.

        Args:
            parent: Parent tree node
            session_data: Session data dictionary

        Returns:
            Created session node
        """
        # Create session node
        node = TreeNode(session_data, parent)
        parent.add_child(node)

        # Add children recursively
        children = session_data.get("children", [])
        for child_data in children:
            child_type = child_data.get("node_type", "")

            if child_type in ("user_turn", "conversation", "exchange"):
                # Exchange node
                exchange_node = TreeNode(child_data, node)
                node.add_child(exchange_node)

                # Add parts/tools as children
                if "parts" in child_data:
                    for part_data in child_data["parts"]:
                        part_node = TreeNode(part_data, exchange_node)
                        exchange_node.add_child(part_node)
                elif "assistant" in child_data:
                    # New format with assistant.parts
                    assistant = child_data.get("assistant", {})
                    for part_data in assistant.get("parts", []):
                        part_node = TreeNode(part_data, exchange_node)
                        exchange_node.add_child(part_node)

            elif child_type == "agent":
                # Agent/delegation node - recurse
                self._build_session_node(node, child_data)

            elif child_type == "part":
                # Direct part (tool) - shouldn't happen at this level but handle it
                part_node = TreeNode(child_data, node)
                node.add_child(part_node)

        return node

    # =========================================================================
    # QAbstractItemModel Interface
    # =========================================================================

    def index(
        self, row: int, column: int, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex:
        """Create an index for the item at row/column under parent."""
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parent_node = self._root
        else:
            parent_node = parent.internalPointer()

        child_node = parent_node.child(row)
        if child_node:
            return self.createIndex(row, column, child_node)
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        """Get the parent index of the given index."""
        if not index.isValid():
            return QModelIndex()

        child_node = index.internalPointer()
        parent_node = child_node.parent

        if parent_node == self._root or parent_node is None:
            return QModelIndex()

        return self.createIndex(parent_node.row(), 0, parent_node)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get number of rows under parent."""
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parent_node = self._root
        else:
            parent_node = parent.internalPointer()

        return parent_node.child_count()

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get number of columns."""
        return self._column_count

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Get data for the given index and role."""
        if not index.isValid():
            return None

        node = index.internalPointer()
        return node.get_data(index.column(), role)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Get header data for the given section."""
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Get flags for the given index."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
