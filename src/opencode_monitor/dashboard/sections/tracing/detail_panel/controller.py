from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItem

from .strategies import TreeNodeData, get_strategy_factory, is_delegation_span
from opencode_monitor.utils.logger import debug, error

if TYPE_CHECKING:
    from .panel import TraceDetailPanel


class PanelController:
    def __init__(self, panel: "TraceDetailPanel") -> None:
        self._panel = panel
        self._factory = get_strategy_factory()

    def handle_selection(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            debug("[Tracing] handle_selection: no data in item")
            return

        node = TreeNodeData(raw=data)

        node_type = node.node_type
        if is_delegation_span(node):
            node_type = "delegation_span"

        debug(
            f"[Tracing] handle_selection: node_type={node_type} session_id={data.get('session_id', 'N/A')}"
        )

        try:
            strategy = self._factory.get(node_type)
            content = strategy.get_content(node)
            debug(
                f"[Tracing] handle_selection: got content type={content.get('type', 'N/A')}"
            )
            self._panel.render(content)
        except Exception as e:
            error(f"[Tracing] handle_selection error: {e}")
            import traceback

            error(traceback.format_exc())
