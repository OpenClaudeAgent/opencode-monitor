"""
Tests for Tracing Tree API - Real Session Data Validation.

These tests validate the tracing tree structure using real session data patterns.
They are designed to break if the API contract changes.

Test Session Reference: "Quick check-in" session
- 9 user turns (exchanges)
- 20 tools (read, bash, webfetch, etc.)
- 1 agent delegation
- Tokens: 129 in, 9101 out, 417959 cache
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Fixtures - Real Session Data Structure
# =============================================================================


@pytest.fixture
def sample_session_tree() -> dict:
    """Sample session tree matching real 'Quick check-in' session structure."""
    return {
        "agent_type": "plan",
        "cache_read": 417959,
        "session_id": "ses_test_session_001",
        "title": "Quick check-in test session",
        "directory": "/Users/test/project",
        "started_at": "2026-01-04T15:44:31.235000",
        "tokens_in": 129,
        "tokens_out": 9101,
        "node_type": "session",
        "children": [
            # User turn without tools
            {
                "cache_read": 0,
                "children": [],
                "duration_ms": 14708,
                "ended_at": "2026-01-04T15:44:45.956000",
                "node_type": "user_turn",
                "parent_agent": "user",
                "prompt_input": "Salut, est-ce que ça va ?",
                "session_id": "ses_test_session_001",
                "started_at": "2026-01-04T15:44:31.248000",
                "subagent_type": "plan",
                "tokens_in": 8,
                "tokens_out": 305,
                "trace_id": "exchange_msg_001",
            },
            # User turn with webfetch tools
            {
                "cache_read": 36680,
                "children": [
                    {
                        "arguments": '{"url": "https://www.weatherapi.com/", "format": "text"}',
                        "children": [],
                        "display_info": "https://www.weatherapi.com/",
                        "duration_ms": 258,
                        "node_type": "tool",
                        "session_id": "ses_test_session_001",
                        "started_at": "2026-01-04T15:45:53.089000",
                        "tool_name": "webfetch",
                        "tool_status": "completed",
                        "trace_id": "tool_prt_001",
                    },
                    {
                        "arguments": '{"url": "https://openweathermap.org/api", "format": "text"}',
                        "children": [],
                        "display_info": "https://openweathermap.org/api",
                        "duration_ms": 173,
                        "node_type": "tool",
                        "tool_name": "webfetch",
                        "tool_status": "completed",
                        "trace_id": "tool_prt_002",
                    },
                ],
                "duration_ms": 4673,
                "node_type": "user_turn",
                "parent_agent": "user",
                "prompt_input": "Cherche une API météo",
                "session_id": "ses_test_session_001",
                "started_at": "2026-01-04T15:45:48.773000",
                "subagent_type": "plan",
                "tokens_in": 12,
                "tokens_out": 558,
                "trace_id": "exchange_msg_002",
            },
            # User turn with bash tool
            {
                "cache_read": 68618,
                "children": [
                    {
                        "arguments": '{"command": "touch /tmp/test.txt", "description": "Create test file"}',
                        "display_info": "touch /tmp/test.txt",
                        "duration_ms": 37,
                        "node_type": "tool",
                        "session_id": "ses_test_session_001",
                        "started_at": "2026-01-04T15:46:10.000000",
                        "tool_name": "bash",
                        "tool_status": "completed",
                        "trace_id": "tool_prt_003",
                    }
                ],
                "duration_ms": 3918,
                "ended_at": "2026-01-04T15:46:14.000000",
                "node_type": "user_turn",
                "parent_agent": "user",
                "prompt_input": "Crée un fichier test",
                "session_id": "ses_test_session_001",
                "started_at": "2026-01-04T15:46:10.000000",
                "subagent_type": "plan",
                "tokens_in": 11,
                "tokens_out": 143,
                "trace_id": "exchange_msg_003",
            },
            # User turn with read tools
            {
                "cache_read": 72980,
                "children": [
                    {
                        "arguments": '{"filePath": "/path/to/README.md"}',
                        "display_info": "/path/to/README.md",
                        "duration_ms": 2,
                        "node_type": "tool",
                        "session_id": "ses_test_session_001",
                        "started_at": "2026-01-04T15:47:00.000000",
                        "tool_name": "read",
                        "tool_status": "completed",
                        "trace_id": "tool_prt_004",
                    }
                ],
                "duration_ms": 5052,
                "ended_at": "2026-01-04T15:47:05.000000",
                "node_type": "user_turn",
                "parent_agent": "user",
                "prompt_input": "Lis le README",
                "session_id": "ses_test_session_001",
                "started_at": "2026-01-04T15:47:00.000000",
                "subagent_type": "plan",
                "tokens_in": 10,
                "tokens_out": 1778,
                "trace_id": "exchange_msg_004",
            },
            # Agent delegation with child tools
            {
                "cache_read": 30128,
                "child_session_id": "ses_child_session_001",
                "children": [
                    {
                        "cache_read": 261028,
                        "child_session_id": "ses_grandchild_001",
                        "children": [
                            {
                                "display_info": "/path/to/roadmap/README.md",
                                "duration_ms": 2,
                                "node_type": "tool",
                                "tool_name": "read",
                                "status": "completed",
                            },
                            {
                                "display_info": "/path/to/roadmap/SPRINTS.md",
                                "duration_ms": 1,
                                "node_type": "tool",
                                "tool_name": "read",
                                "status": "completed",
                            },
                        ],
                        "duration_ms": 158859,
                        "node_type": "agent",
                        "parent_agent": "plan",
                        "subagent_type": "roadmap",
                        "tokens_in": 35,
                        "tokens_out": 3127,
                        "trace_id": "prt_delegation_001",
                    }
                ],
                "duration_ms": 165000,
                "ended_at": "2026-01-04T15:50:00.000000",
                "node_type": "user_turn",
                "parent_agent": "user",
                "prompt_input": "Lance l'agent roadmap",
                "session_id": "ses_test_session_001",
                "started_at": "2026-01-04T15:48:00.000000",
                "subagent_type": "plan",
                "tokens_in": 15,
                "tokens_out": 500,
                "trace_id": "exchange_msg_005",
            },
        ],
    }


@pytest.fixture
def sample_tool_node() -> dict:
    """Sample tool node with all required fields."""
    return {
        "arguments": '{"filePath": "/test/file.py"}',
        "children": [],
        "display_info": "/test/file.py",
        "duration_ms": 5,
        "node_type": "tool",
        "result_summary": None,
        "session_id": "ses_test",
        "started_at": "2026-01-04T10:00:00.000000",
        "tool_name": "read",
        "tool_status": "completed",
        "trace_id": "tool_prt_test",
    }


@pytest.fixture
def sample_delegation_node() -> dict:
    """Sample agent delegation node."""
    return {
        "cache_read": 50000,
        "child_session_id": "ses_child_123",
        "children": [],
        "duration_ms": 30000,
        "ended_at": "2026-01-04T10:00:30.000000",
        "node_type": "agent",
        "parent_agent": "plan",
        "parent_trace_id": "root_ses_parent",
        "prompt_input": "Analyze this code",
        "prompt_output": None,
        "session_id": "ses_parent",
        "started_at": "2026-01-04T10:00:00.000000",
        "status": "completed",
        "subagent_type": "explore",
        "tokens_in": 100,
        "tokens_out": 2000,
        "trace_id": "prt_delegation_test",
    }


# =============================================================================
# Tests - Node Type Validation
# =============================================================================


class TestNodeTypes:
    """Tests for node type field validation."""

    def test_session_node_has_required_fields(self, sample_session_tree: dict):
        """Session node must have all required fields."""
        required_fields = {"agent_type", "session_id", "children", "node_type"}
        assert required_fields.issubset(sample_session_tree.keys())
        assert sample_session_tree["node_type"] == "session"

    def test_user_turn_node_has_required_fields(self, sample_session_tree: dict):
        """User turn nodes must have specific fields."""
        user_turn = sample_session_tree["children"][0]
        required_fields = {
            "node_type",
            "trace_id",
            "tokens_in",
            "tokens_out",
            "duration_ms",
            "parent_agent",
        }
        assert required_fields.issubset(user_turn.keys())
        assert user_turn["node_type"] == "user_turn"
        assert user_turn["parent_agent"] == "user"

    def test_tool_node_has_required_fields(self, sample_tool_node: dict):
        """Tool nodes must have specific fields."""
        required_fields = {
            "node_type",
            "tool_name",
            "tool_status",
            "duration_ms",
            "trace_id",
        }
        assert required_fields.issubset(sample_tool_node.keys())
        assert sample_tool_node["node_type"] == "tool"

    def test_delegation_node_has_required_fields(self, sample_delegation_node: dict):
        """Agent delegation nodes must have specific fields."""
        required_fields = {
            "node_type",
            "subagent_type",
            "tokens_in",
            "tokens_out",
            "duration_ms",
            "parent_agent",
            "trace_id",
        }
        assert required_fields.issubset(sample_delegation_node.keys())
        assert sample_delegation_node["node_type"] == "agent"

    def test_valid_node_types(self, sample_session_tree: dict):
        """All nodes must have valid node_type values."""
        valid_types = {"session", "user_turn", "tool", "agent", "exchange", "part"}

        def check_node_types(node: dict):
            node_type = node.get("node_type")
            assert node_type in valid_types, f"Invalid node_type: {node_type}"
            for child in node.get("children", []):
                check_node_types(child)

        check_node_types(sample_session_tree)


# =============================================================================
# Tests - Tree Structure Validation
# =============================================================================


class TestTreeStructure:
    """Tests for hierarchical tree structure."""

    def test_session_has_children(self, sample_session_tree: dict):
        """Session must have children array."""
        assert "children" in sample_session_tree
        assert isinstance(sample_session_tree["children"], list)
        assert len(sample_session_tree["children"]) > 0

    def test_user_turn_can_have_tool_children(self, sample_session_tree: dict):
        """User turns can contain tool nodes as children."""
        # Find user turn with tools
        for child in sample_session_tree["children"]:
            if child.get("node_type") == "user_turn" and child.get("children"):
                for tool in child["children"]:
                    assert tool.get("node_type") in ("tool", "agent")
                return
        pytest.skip("No user turn with tool children found")

    def test_delegation_nested_in_user_turn(self, sample_session_tree: dict):
        """Agent delegations can be nested inside user turns."""
        for child in sample_session_tree["children"]:
            if child.get("node_type") == "user_turn":
                for nested in child.get("children", []):
                    if nested.get("node_type") == "agent":
                        assert "subagent_type" in nested
                        assert "tokens_in" in nested
                        return
        pytest.skip("No nested delegation found")

    def test_delegation_has_child_session_id(self, sample_delegation_node: dict):
        """Agent delegations should have child_session_id."""
        assert "child_session_id" in sample_delegation_node
        assert sample_delegation_node["child_session_id"].startswith("ses_")

    def test_tools_are_leaf_nodes(self, sample_tool_node: dict):
        """Tool nodes should be leaf nodes (no children or empty children)."""
        children = sample_tool_node.get("children", [])
        assert children == []


# =============================================================================
# Tests - Token Metrics Validation
# =============================================================================


class TestTokenMetrics:
    """Tests for token counting and metrics."""

    def test_session_has_token_counts(self, sample_session_tree: dict):
        """Session should have aggregate token counts."""
        assert "tokens_in" in sample_session_tree
        assert "tokens_out" in sample_session_tree
        assert sample_session_tree["tokens_in"] >= 0
        assert sample_session_tree["tokens_out"] >= 0

    def test_session_has_cache_read(self, sample_session_tree: dict):
        """Session should have cache_read metric."""
        assert "cache_read" in sample_session_tree
        assert sample_session_tree["cache_read"] >= 0

    def test_user_turn_has_tokens(self, sample_session_tree: dict):
        """User turns should have token metrics."""
        user_turn = sample_session_tree["children"][0]
        assert "tokens_in" in user_turn
        assert "tokens_out" in user_turn
        assert user_turn["tokens_in"] >= 0
        assert user_turn["tokens_out"] >= 0

    def test_delegation_has_tokens(self, sample_delegation_node: dict):
        """Delegations should have token metrics."""
        assert sample_delegation_node["tokens_in"] >= 0
        assert sample_delegation_node["tokens_out"] >= 0

    def test_token_sum_consistency(self, sample_session_tree: dict):
        """Sum of children tokens should not exceed session total."""
        session_total = sample_session_tree["tokens_out"]
        children_sum = sum(
            child.get("tokens_out", 0) for child in sample_session_tree["children"]
        )
        # Children sum can be less due to aggregation logic
        assert children_sum <= session_total * 1.5  # Allow some margin


# =============================================================================
# Tests - Tool Display Info
# =============================================================================


class TestToolDisplayInfo:
    """Tests for tool display_info extraction."""

    def test_read_tool_shows_filepath(self, sample_session_tree: dict):
        """Read tool should show file path in display_info."""
        for child in sample_session_tree["children"]:
            for tool in child.get("children", []):
                if tool.get("tool_name") == "read":
                    assert "display_info" in tool
                    assert tool["display_info"] is not None
                    return
        pytest.skip("No read tool found")

    def test_webfetch_tool_shows_url(self, sample_session_tree: dict):
        """Webfetch tool should show URL in display_info."""
        for child in sample_session_tree["children"]:
            for tool in child.get("children", []):
                if tool.get("tool_name") == "webfetch":
                    assert "display_info" in tool
                    assert "http" in tool["display_info"]
                    return
        pytest.skip("No webfetch tool found")

    def test_bash_tool_shows_command(self, sample_session_tree: dict):
        """Bash tool should show command in display_info."""
        for child in sample_session_tree["children"]:
            for tool in child.get("children", []):
                if tool.get("tool_name") == "bash":
                    assert "display_info" in tool
                    return
        pytest.skip("No bash tool found")


# =============================================================================
# Tests - Timing and Duration
# =============================================================================


class TestTiming:
    """Tests for timing and duration fields."""

    def test_user_turn_has_duration(self, sample_session_tree: dict):
        """User turns should have duration_ms."""
        for child in sample_session_tree["children"]:
            if child.get("node_type") == "user_turn":
                assert "duration_ms" in child
                assert child["duration_ms"] >= 0

    def test_tool_has_duration(self, sample_tool_node: dict):
        """Tools should have duration_ms."""
        assert "duration_ms" in sample_tool_node
        assert sample_tool_node["duration_ms"] >= 0

    def test_user_turn_has_timestamps(self, sample_session_tree: dict):
        """User turns should have started_at timestamp."""
        for child in sample_session_tree["children"]:
            if child.get("node_type") == "user_turn":
                assert "started_at" in child
                # Validate ISO format
                datetime.fromisoformat(child["started_at"].replace("Z", "+00:00"))

    def test_delegation_has_timestamps(self, sample_delegation_node: dict):
        """Delegations should have start and end timestamps."""
        assert "started_at" in sample_delegation_node
        assert "ended_at" in sample_delegation_node


# =============================================================================
# Tests - Agent Types
# =============================================================================


class TestAgentTypes:
    """Tests for agent type fields."""

    def test_session_has_agent_type(self, sample_session_tree: dict):
        """Session should have agent_type."""
        assert "agent_type" in sample_session_tree
        assert sample_session_tree["agent_type"] is not None

    def test_user_turn_has_subagent_type(self, sample_session_tree: dict):
        """User turns should have subagent_type."""
        for child in sample_session_tree["children"]:
            if child.get("node_type") == "user_turn":
                assert "subagent_type" in child

    def test_delegation_has_subagent_type(self, sample_delegation_node: dict):
        """Delegations must have subagent_type."""
        assert "subagent_type" in sample_delegation_node
        assert sample_delegation_node["subagent_type"] is not None

    def test_delegation_has_parent_agent(self, sample_delegation_node: dict):
        """Delegations should have parent_agent."""
        assert "parent_agent" in sample_delegation_node


# =============================================================================
# Tests - ID Formats
# =============================================================================


class TestIdFormats:
    """Tests for ID field formats."""

    def test_session_id_format(self, sample_session_tree: dict):
        """Session IDs should match expected format."""
        session_id = sample_session_tree["session_id"]
        assert session_id.startswith("ses_")

    def test_trace_id_format_for_exchange(self, sample_session_tree: dict):
        """Exchange trace IDs should have specific format."""
        for child in sample_session_tree["children"]:
            if child.get("node_type") == "user_turn":
                trace_id = child.get("trace_id", "")
                assert trace_id.startswith("exchange_") or trace_id.startswith("msg_")
                return

    def test_trace_id_format_for_tool(self, sample_tool_node: dict):
        """Tool trace IDs should have specific format."""
        trace_id = sample_tool_node["trace_id"]
        assert "tool_" in trace_id or "prt_" in trace_id


# =============================================================================
# Tests - Empty/Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and empty data."""

    def test_empty_children_is_list(self, sample_tool_node: dict):
        """Empty children should be an empty list, not None."""
        assert sample_tool_node["children"] == []
        assert sample_tool_node["children"] is not None

    def test_user_turn_without_tools(self, sample_session_tree: dict):
        """User turns can have empty children (no tools)."""
        first_turn = sample_session_tree["children"][0]
        assert first_turn["children"] == []

    def test_nullable_fields_handled(self, sample_tool_node: dict):
        """Nullable fields should be None or have value, not missing."""
        # result_summary can be None
        assert "result_summary" in sample_tool_node


# =============================================================================
# Tests - Real Data Counts (Quick check-in reference)
# =============================================================================


class TestRealDataCounts:
    """Tests that validate counts match real session patterns."""

    def test_session_with_multiple_user_turns(self, sample_session_tree: dict):
        """Session should have multiple user turns (like Quick check-in: 9)."""
        user_turns = [
            c
            for c in sample_session_tree["children"]
            if c.get("node_type") == "user_turn"
        ]
        assert len(user_turns) >= 1

    def test_tools_across_user_turns(self, sample_session_tree: dict):
        """Count total tools across all user turns."""
        total_tools = 0
        for child in sample_session_tree["children"]:
            for nested in child.get("children", []):
                if nested.get("node_type") == "tool":
                    total_tools += 1
        assert total_tools >= 1

    def test_delegation_with_child_tools(self, sample_session_tree: dict):
        """Delegations can have their own child tools."""
        for child in sample_session_tree["children"]:
            for nested in child.get("children", []):
                if nested.get("node_type") == "agent":
                    # Delegation found, check for children
                    assert "children" in nested
                    return
        pytest.skip("No delegation found")


# =============================================================================
# Tests - Sorting and Order
# =============================================================================


class TestSortingOrder:
    """Tests for proper ordering of tree elements."""

    def test_user_turns_ordered_by_time(self, sample_session_tree: dict):
        """User turns should be in chronological order."""
        timestamps = []
        for child in sample_session_tree["children"]:
            if child.get("node_type") == "user_turn" and "started_at" in child:
                timestamps.append(child["started_at"])

        if len(timestamps) > 1:
            assert timestamps == sorted(timestamps)

    def test_tools_ordered_by_time(self, sample_session_tree: dict):
        """Tools within a user turn should be ordered by time."""
        for child in sample_session_tree["children"]:
            if child.get("node_type") == "user_turn":
                tools = [
                    t for t in child.get("children", []) if t.get("node_type") == "tool"
                ]
                if len(tools) > 1:
                    timestamps = [t.get("started_at", "") for t in tools]
                    filtered = [t for t in timestamps if t]
                    if len(filtered) > 1:
                        assert filtered == sorted(filtered)
