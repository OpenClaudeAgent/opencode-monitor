"""
Session strategy - Handle session nodes (root and child).
"""

import os

from ...helpers import format_duration, format_tokens_short
from .types import PanelContent, TreeNodeData, MetricsData, TranscriptData


class SessionStrategy:
    @staticmethod
    def handles() -> list[str]:
        return ["session", "agent", "delegation"]

    def get_content(self, node: TreeNodeData) -> PanelContent:
        if node.is_root:
            return self._get_root_content(node)
        else:
            return self._get_child_content(node)

    def _get_root_content(self, node: TreeNodeData) -> PanelContent:
        directory = node.directory
        project_name = os.path.basename(directory) if directory else "Session"
        tokens_total = node.tokens_in + node.tokens_out
        children_count = len(node.children)

        return PanelContent(
            header=project_name,
            header_icon="🌳",
            header_color=None,
            breadcrumb=[f"🌳 {project_name}"],
            status=node.status,  # type: ignore[typeddict-item]
            status_label=None,
            metrics=MetricsData(
                duration=format_duration(node.duration_ms),
                tokens=format_tokens_short(tokens_total),
                tools="-",
                files="-",
                agents=str(children_count),
            ),
            content_type="overview",
            overview_data={
                "project": project_name,
                "title": node.title,
                "directory": directory,
                "duration_ms": node.duration_ms,
                "tokens": node.get("tokens"),  # Pass complete tokens object from API
                "tokens_in": node.tokens_in,  # Keep for backward compatibility
                "tokens_out": node.tokens_out,
                "cache_read": node.get("cache_read", 0),
                "children": node.children,
            },
            transcript=None,
            available_tabs=[],
            initial_tab=0,
        )

    def _get_child_content(self, node: TreeNodeData) -> PanelContent:
        agent_type = node.agent_type or "agent"
        parent_agent = node.parent_agent or "user"
        tokens_total = node.tokens_in + node.tokens_out
        children_count = len(node.children)

        icon = "💬" if parent_agent == "user" else "🔗"
        header = f"{parent_agent} → {agent_type}" if parent_agent else agent_type

        breadcrumb: list[str] = ["🌳 ROOT"]
        if parent_agent and parent_agent != "user":
            breadcrumb.append(f"🔗 {parent_agent}")
        breadcrumb.append(f"🤖 {agent_type}")

        prompt_input = (
            node.prompt_input or node.title or f"Task delegated to {agent_type}"
        )
        prompt_output = node.prompt_output or (
            f"Agent: {agent_type}\n"
            f"Duration: {format_duration(node.duration_ms)}\n"
            f"Tokens: {format_tokens_short(node.tokens_in)} in / "
            f"{format_tokens_short(node.tokens_out)} out\n"
            f"Status: {node.status}"
        )

        return PanelContent(
            header=header,
            header_icon=icon,
            header_color=None,
            breadcrumb=breadcrumb,
            status=node.status,  # type: ignore[typeddict-item]
            status_label=None,
            metrics=MetricsData(
                duration=format_duration(node.duration_ms),
                tokens=format_tokens_short(tokens_total),
                tools="-",
                files="-",
                agents=str(children_count),
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
