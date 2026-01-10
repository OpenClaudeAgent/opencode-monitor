"""
Text content strategy - Fallback for unknown node types.
"""

from ...helpers import format_duration, format_tokens_short
from .types import PanelContent, TreeNodeData, MetricsData, TranscriptData


class TextContentStrategy:
    @staticmethod
    def handles() -> list[str]:
        return []

    def get_content(self, node: TreeNodeData) -> PanelContent:
        agent = node.get("subagent_type", "")
        duration_ms = node.duration_ms
        tokens_in = node.tokens_in
        tokens_out = node.tokens_out
        tokens_total = tokens_in + tokens_out
        status = node.status
        prompt_input = node.prompt_input or ""
        prompt_output = node.prompt_output or ""
        tools_used = node.get("tools_used", [])

        return PanelContent(
            header=f"Agent: {agent}" if agent else "Trace Details",
            header_icon="🤖" if agent else "📋",
            header_color=None,
            breadcrumb=[],
            status=status if status in ("completed", "error") else None,  # type: ignore[typeddict-item]
            status_label=None,
            metrics=MetricsData(
                duration=format_duration(duration_ms),
                tokens=format_tokens_short(tokens_total),
                tools=str(len(tools_used)),
                files="-",
                agents="1" if agent else "-",
            ),
            content_type="tabs",
            overview_data=None,
            transcript=TranscriptData(
                user_content=prompt_input,
                assistant_content=prompt_output,
            ),
            available_tabs=[0],
            initial_tab=0,
        )
