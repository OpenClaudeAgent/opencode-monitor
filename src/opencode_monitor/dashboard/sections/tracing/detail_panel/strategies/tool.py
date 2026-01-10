"""
Tool strategy - Handle tool nodes.
"""

from ...helpers import format_duration
from .types import PanelContent, TreeNodeData, MetricsData, TranscriptData

TOOL_ICONS = {
    "read": "📖",
    "edit": "✏️",
    "write": "📝",
    "bash": "🔧",
    "glob": "🔍",
    "grep": "🔎",
    "task": "🤖",
    "webfetch": "🌐",
    "web_fetch": "🌐",
    "todowrite": "📋",
    "todoread": "📋",
}


class ToolStrategy:
    @staticmethod
    def handles() -> list[str]:
        return ["tool", "part"]

    def get_content(self, node: TreeNodeData) -> PanelContent:
        tool_name = node.tool_name
        if not tool_name:
            return self._get_text_content(node)

        display_info = node.display_info
        status = node.status
        duration_ms = node.duration_ms
        created_at = node.created_at

        icon = TOOL_ICONS.get(tool_name, "⚙️")
        header = f"{tool_name}: {display_info}" if display_info else tool_name

        tool_info = f"Tool: {tool_name}\n"
        if display_info:
            tool_info += f"Target: {display_info}\n"
        tool_info += f"Status: {status}\n"
        if duration_ms:
            tool_info += f"Duration: {format_duration(duration_ms)}\n"
        if created_at:
            tool_info += f"Timestamp: {created_at}\n"

        return PanelContent(
            header=header,
            header_icon=icon,
            header_color=None,
            breadcrumb=[],
            status=status if status in ("completed", "error") else None,  # type: ignore[typeddict-item]
            status_label=None,
            metrics=MetricsData(
                duration=format_duration(duration_ms),
                tokens="-",
                tools="1",
                files="-",
                agents="-",
            ),
            content_type="tabs",
            overview_data=None,
            transcript=TranscriptData(
                user_content=f"Tool: {tool_name}",
                assistant_content=tool_info,
            ),
            available_tabs=[0],
            initial_tab=0,
        )

    def _get_text_content(self, node: TreeNodeData) -> PanelContent:
        content = node.content
        created_at = node.created_at

        return PanelContent(
            header="Assistant Response",
            header_icon="🤖",
            header_color=None,
            breadcrumb=[],
            status=None,
            status_label=None,
            metrics=MetricsData(
                duration="-",
                tokens="-",
                tools="-",
                files="-",
                agents="-",
            ),
            content_type="tabs",
            overview_data=None,
            transcript=TranscriptData(
                user_content="",
                assistant_content=content,
            ),
            available_tabs=[0],
            initial_tab=0,
        )
