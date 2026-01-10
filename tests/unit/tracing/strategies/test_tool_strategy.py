"""Unit tests for ToolStrategy."""

import pytest
from opencode_monitor.dashboard.sections.tracing.detail_panel.strategies import (
    TreeNodeData,
    ToolStrategy,
)


class TestToolStrategy:
    def test_handles_tool_node_type(self):
        """ToolStrategy should handle 'tool' and 'part' node types."""
        assert "tool" in ToolStrategy.handles()
        assert "part" in ToolStrategy.handles()

    def test_get_content_returns_tabs(self):
        """ToolStrategy should return content_type='tabs'."""
        data = {
            "node_type": "tool",
            "tool_name": "mcp_read",
            "display_info": "src/main.py",
            "status": "completed",
        }
        node = TreeNodeData(raw=data)
        content = ToolStrategy().get_content(node)

        assert content["content_type"] == "tabs"

    def test_get_content_header_with_tool_name(self):
        """Header should contain tool name."""
        data = {
            "node_type": "tool",
            "tool_name": "bash",
            "display_info": "make test",
        }
        node = TreeNodeData(raw=data)
        content = ToolStrategy().get_content(node)

        assert "bash" in content["header"]

    def test_get_content_status_completed(self):
        """Status should be set for completed tools."""
        data = {
            "node_type": "tool",
            "tool_name": "mcp_edit",
            "status": "completed",
        }
        node = TreeNodeData(raw=data)
        content = ToolStrategy().get_content(node)

        assert content.get("status") == "completed"

    def test_get_content_status_error(self):
        """Status should be set for error tools."""
        data = {
            "node_type": "tool",
            "tool_name": "mcp_bash",
            "status": "error",
        }
        node = TreeNodeData(raw=data)
        content = ToolStrategy().get_content(node)

        assert content.get("status") == "error"
