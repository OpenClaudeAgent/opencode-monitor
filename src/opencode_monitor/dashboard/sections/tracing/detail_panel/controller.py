"""
Panel controller - Orchestrates panel updates based on tree selection.
"""

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItem

from opencode_monitor.utils.logger import debug

from .strategies import TreeNodeData, get_strategy_factory

if TYPE_CHECKING:
    from .panel import TraceDetailPanel


class PanelController:
    def __init__(self, panel: "TraceDetailPanel") -> None:
        self._panel = panel
        self._factory = get_strategy_factory()

    def handle_selection(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        debug("[CONTROLLER] handle_selection called")
        if not data:
            debug("[CONTROLLER] No data in item, returning")
            return

        node = TreeNodeData(raw=data)
        debug(f"[CONTROLLER] node_type={node.node_type}, is_root={node.is_root}")

        strategy = self._factory.get(node.node_type)
        debug(f"[CONTROLLER] Got strategy: {type(strategy).__name__}")

        content = strategy.get_content(node)
        debug(f"[CONTROLLER] content_type={content.get('content_type')}")
        debug("[CONTROLLER] Calling panel.render()...")

        self._panel.render(content)
