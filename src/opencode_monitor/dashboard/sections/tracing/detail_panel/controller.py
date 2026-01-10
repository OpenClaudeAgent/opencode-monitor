"""
Panel controller - Orchestrates panel updates based on tree selection.
"""

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItem

from .strategies import TreeNodeData, get_strategy_factory

if TYPE_CHECKING:
    from .panel import TraceDetailPanel


class PanelController:
    def __init__(self, panel: "TraceDetailPanel") -> None:
        self._panel = panel
        self._factory = get_strategy_factory()

    def handle_selection(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        node = TreeNodeData(raw=data)
        strategy = self._factory.get(node.node_type)
        content = strategy.get_content(node)
        self._panel.render(content)
