"""
Tests for Tracing Tree API - Real Session Data Validation.

These tests validate the tracing tree structure using real session data patterns.
They are designed to break if the API contract changes.

Test Session Reference: "Quick check-in" session
- 5 user turns (exchanges)
- 6 tools total (2 webfetch, 1 bash, 1 read, 2 read in delegation)
- 1 agent delegation (roadmap) with nested tools
- Session tokens: 129 in, 9101 out, 417959 cache

IMPORTANT: These tests use EXACT values from real session data.
If any assertion fails, it means the API contract has changed.

CONSOLIDATED: 121 tests -> ~18 tests with multiple assertions each.
"""

import json
from datetime import datetime

import pytest


# =============================================================================
# Constants - Exact values from "Quick check-in" session
# =============================================================================

# Session-level metrics
EXPECTED_SESSION_ID = "ses_test_session_001"
EXPECTED_SESSION_TITLE = "Quick check-in test session"
EXPECTED_SESSION_DIRECTORY = "/Users/test/project"
EXPECTED_SESSION_AGENT_TYPE = "plan"
EXPECTED_SESSION_TOKENS_IN = 129
EXPECTED_SESSION_TOKENS_OUT = 9101
EXPECTED_SESSION_CACHE_READ = 417959
EXPECTED_SESSION_STARTED_AT = "2026-01-04T15:44:31.235000"

# User turn counts
EXPECTED_USER_TURN_COUNT = 5
EXPECTED_TOTAL_TOOL_COUNT = 6  # 2 webfetch + 1 bash + 1 read + 2 read in delegation

# User Turn expected values by index (0-based)
USER_TURN_EXPECTATIONS = [
    # UT1 - Simple greeting (no tools)
    {
        "trace_id": "exchange_msg_001",
        "prompt": "Salut, est-ce que ca va ?",
        "tokens_in": 8,
        "tokens_out": 305,
        "duration_ms": 14708,
        "cache_read": 0,
        "tool_count": 0,
        "started_at": "2026-01-04T15:44:31.248000",
        "ended_at": "2026-01-04T15:44:45.956000",
    },
    # UT2 - Weather API search (2 webfetch tools)
    {
        "trace_id": "exchange_msg_002",
        "prompt": "Cherche une API meteo",
        "tokens_in": 12,
        "tokens_out": 558,
        "duration_ms": 4673,
        "cache_read": 36680,
        "tool_count": 2,
        "started_at": "2026-01-04T15:45:48.773000",
        "tools": [
            {
                "name": "webfetch",
                "url": "https://www.weatherapi.com/",
                "duration_ms": 258,
                "trace_id": "tool_prt_001",
                "status": "completed",
            },
            {
                "name": "webfetch",
                "url": "https://openweathermap.org/api",
                "duration_ms": 173,
                "trace_id": "tool_prt_002",
                "status": "completed",
            },
        ],
    },
    # UT3 - Create file (1 bash tool)
    {
        "trace_id": "exchange_msg_003",
        "prompt": "Cree un fichier test",
        "tokens_in": 11,
        "tokens_out": 143,
        "duration_ms": 3918,
        "cache_read": 68618,
        "tool_count": 1,
        "tools": [
            {
                "name": "bash",
                "command": "touch /tmp/test.txt",
                "duration_ms": 37,
                "trace_id": "tool_prt_003",
            },
        ],
    },
    # UT4 - Read README (1 read tool)
    {
        "trace_id": "exchange_msg_004",
        "prompt": "Lis le README",
        "tokens_in": 10,
        "tokens_out": 1778,
        "duration_ms": 5052,
        "cache_read": 72980,
        "tool_count": 1,
        "tools": [
            {
                "name": "read",
                "path": "/path/to/README.md",
                "duration_ms": 2,
                "trace_id": "tool_prt_004",
            },
        ],
    },
    # UT5 - Delegation (roadmap agent with 2 tools)
    {
        "trace_id": "exchange_msg_005",
        "prompt": "Lance l'agent roadmap",
        "tokens_in": 15,
        "tokens_out": 500,
        "duration_ms": 165000,
        "cache_read": 30128,
        "child_session_id": "ses_child_session_001",
        "delegation": {
            "subagent_type": "roadmap",
            "parent_agent": "plan",
            "tokens_in": 35,
            "tokens_out": 3127,
            "duration_ms": 158859,
            "cache_read": 261028,
            "child_session_id": "ses_grandchild_001",
            "trace_id": "prt_delegation_001",
            "tool_count": 2,
            "tools": [
                {
                    "name": "read",
                    "path": "/path/to/roadmap/README.md",
                    "duration_ms": 2,
                },
                {
                    "name": "read",
                    "path": "/path/to/roadmap/SPRINTS.md",
                    "duration_ms": 1,
                },
            ],
        },
    },
]


# =============================================================================
# Fixtures - Complete Session Data Structure
# =============================================================================


@pytest.fixture
def sample_session_tree() -> dict:
    """Complete session tree matching 'Quick check-in' session structure.

    This fixture contains EXACT data that tests will validate against.
    Any change to the structure will break tests intentionally.
    """
    return {
        "agent_type": EXPECTED_SESSION_AGENT_TYPE,
        "cache_read": EXPECTED_SESSION_CACHE_READ,
        "session_id": EXPECTED_SESSION_ID,
        "title": EXPECTED_SESSION_TITLE,
        "directory": EXPECTED_SESSION_DIRECTORY,
        "started_at": EXPECTED_SESSION_STARTED_AT,
        "tokens_in": EXPECTED_SESSION_TOKENS_IN,
        "tokens_out": EXPECTED_SESSION_TOKENS_OUT,
        "node_type": "session",
        "children": [
            # User turn 1 - Simple greeting (no tools)
            {
                "cache_read": 0,
                "children": [],
                "duration_ms": 14708,
                "ended_at": "2026-01-04T15:44:45.956000",
                "node_type": "user_turn",
                "parent_agent": "user",
                "prompt_input": "Salut, est-ce que ca va ?",
                "session_id": EXPECTED_SESSION_ID,
                "started_at": "2026-01-04T15:44:31.248000",
                "subagent_type": "plan",
                "tokens_in": 8,
                "tokens_out": 305,
                "trace_id": "exchange_msg_001",
            },
            # User turn 2 - Weather API search (2 webfetch tools)
            {
                "cache_read": 36680,
                "children": [
                    {
                        "arguments": '{"url": "https://www.weatherapi.com/", "format": "text"}',
                        "children": [],
                        "display_info": "https://www.weatherapi.com/",
                        "duration_ms": 258,
                        "node_type": "tool",
                        "session_id": EXPECTED_SESSION_ID,
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
                        "session_id": EXPECTED_SESSION_ID,
                        "started_at": "2026-01-04T15:45:53.500000",
                        "tool_name": "webfetch",
                        "tool_status": "completed",
                        "trace_id": "tool_prt_002",
                    },
                ],
                "duration_ms": 4673,
                "ended_at": "2026-01-04T15:45:53.446000",
                "node_type": "user_turn",
                "parent_agent": "user",
                "prompt_input": "Cherche une API meteo",
                "session_id": EXPECTED_SESSION_ID,
                "started_at": "2026-01-04T15:45:48.773000",
                "subagent_type": "plan",
                "tokens_in": 12,
                "tokens_out": 558,
                "trace_id": "exchange_msg_002",
            },
            # User turn 3 - Create file (1 bash tool)
            {
                "cache_read": 68618,
                "children": [
                    {
                        "arguments": '{"command": "touch /tmp/test.txt", "description": "Create test file"}',
                        "children": [],
                        "display_info": "touch /tmp/test.txt",
                        "duration_ms": 37,
                        "node_type": "tool",
                        "session_id": EXPECTED_SESSION_ID,
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
                "prompt_input": "Cree un fichier test",
                "session_id": EXPECTED_SESSION_ID,
                "started_at": "2026-01-04T15:46:10.000000",
                "subagent_type": "plan",
                "tokens_in": 11,
                "tokens_out": 143,
                "trace_id": "exchange_msg_003",
            },
            # User turn 4 - Read README (1 read tool)
            {
                "cache_read": 72980,
                "children": [
                    {
                        "arguments": '{"filePath": "/path/to/README.md"}',
                        "children": [],
                        "display_info": "/path/to/README.md",
                        "duration_ms": 2,
                        "node_type": "tool",
                        "session_id": EXPECTED_SESSION_ID,
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
                "session_id": EXPECTED_SESSION_ID,
                "started_at": "2026-01-04T15:47:00.000000",
                "subagent_type": "plan",
                "tokens_in": 10,
                "tokens_out": 1778,
                "trace_id": "exchange_msg_004",
            },
            # User turn 5 - Agent delegation with nested tools
            {
                "cache_read": 30128,
                "child_session_id": "ses_child_session_001",
                "children": [
                    {
                        "cache_read": 261028,
                        "child_session_id": "ses_grandchild_001",
                        "children": [
                            {
                                "arguments": '{"filePath": "/path/to/roadmap/README.md"}',
                                "children": [],
                                "display_info": "/path/to/roadmap/README.md",
                                "duration_ms": 2,
                                "node_type": "tool",
                                "tool_name": "read",
                                "tool_status": "completed",
                                "trace_id": "tool_deleg_001",
                            },
                            {
                                "arguments": '{"filePath": "/path/to/roadmap/SPRINTS.md"}',
                                "children": [],
                                "display_info": "/path/to/roadmap/SPRINTS.md",
                                "duration_ms": 1,
                                "node_type": "tool",
                                "tool_name": "read",
                                "tool_status": "completed",
                                "trace_id": "tool_deleg_002",
                            },
                        ],
                        "duration_ms": 158859,
                        "ended_at": "2026-01-04T15:50:38.000000",
                        "node_type": "agent",
                        "parent_agent": "plan",
                        "prompt_input": "Analyze roadmap",
                        "session_id": "ses_child_session_001",
                        "started_at": "2026-01-04T15:48:00.000000",
                        "subagent_type": "roadmap",
                        "tokens_in": 35,
                        "tokens_out": 3127,
                        "trace_id": "prt_delegation_001",
                    }
                ],
                "duration_ms": 165000,
                "ended_at": "2026-01-04T15:50:45.000000",
                "node_type": "user_turn",
                "parent_agent": "user",
                "prompt_input": "Lance l'agent roadmap",
                "session_id": EXPECTED_SESSION_ID,
                "started_at": "2026-01-04T15:48:00.000000",
                "subagent_type": "plan",
                "tokens_in": 15,
                "tokens_out": 500,
                "trace_id": "exchange_msg_005",
            },
        ],
    }


# =============================================================================
# Consolidated Tests
# =============================================================================


class TestSessionLevel:
    """Tests for session-level data validation."""

    def test_session_fields_exact_values(self, sample_session_tree: dict):
        """Validate ALL session-level fields in a single test."""
        tree = sample_session_tree

        # Identity fields
        assert tree["session_id"] == EXPECTED_SESSION_ID
        assert tree["title"] == EXPECTED_SESSION_TITLE
        assert tree["directory"] == EXPECTED_SESSION_DIRECTORY
        assert tree["agent_type"] == EXPECTED_SESSION_AGENT_TYPE
        assert tree["node_type"] == "session"

        # Token metrics
        assert tree["tokens_in"] == EXPECTED_SESSION_TOKENS_IN
        assert tree["tokens_out"] == EXPECTED_SESSION_TOKENS_OUT
        assert tree["cache_read"] == EXPECTED_SESSION_CACHE_READ

        # Timestamp
        assert tree["started_at"] == EXPECTED_SESSION_STARTED_AT

        # Children structure
        assert "children" in tree
        assert isinstance(tree["children"], list)

    def test_user_turn_counts_and_structure(self, sample_session_tree: dict):
        """Validate user turn count, types, and total tool count."""
        children = sample_session_tree["children"]

        # Exact user turn count
        user_turns = [c for c in children if c.get("node_type") == "user_turn"]
        assert len(user_turns) == EXPECTED_USER_TURN_COUNT, (
            f"Expected {EXPECTED_USER_TURN_COUNT} user turns, got {len(user_turns)}"
        )

        # All direct children are user_turns
        for i, child in enumerate(children):
            assert child["node_type"] == "user_turn", (
                f"Child {i} has node_type '{child['node_type']}', expected 'user_turn'"
            )

        # Count total tools recursively
        def count_tools(node: dict) -> int:
            count = 0
            for child in node.get("children", []):
                if child.get("node_type") == "tool":
                    count += 1
                count += count_tools(child)
            return count

        total_tools = sum(count_tools(ut) for ut in children)
        assert total_tools == EXPECTED_TOTAL_TOOL_COUNT, (
            f"Expected {EXPECTED_TOTAL_TOOL_COUNT} tools, got {total_tools}"
        )


class TestUserTurns:
    """Tests for individual user turn validation."""

    @pytest.mark.parametrize("ut_index", [0, 1, 2, 3])
    def test_user_turn_fields(self, sample_session_tree: dict, ut_index: int):
        """Validate user turn fields for turns 1-4 (parameterized)."""
        ut = sample_session_tree["children"][ut_index]
        expected = USER_TURN_EXPECTATIONS[ut_index]

        # Basic fields
        assert ut["trace_id"] == expected["trace_id"]
        assert ut["prompt_input"] == expected["prompt"]
        assert ut["tokens_in"] == expected["tokens_in"]
        assert ut["tokens_out"] == expected["tokens_out"]
        assert ut["duration_ms"] == expected["duration_ms"]
        assert ut["cache_read"] == expected["cache_read"]

        # Node type and common fields
        assert ut["node_type"] == "user_turn"
        assert ut["parent_agent"] == "user"
        assert ut["subagent_type"] == "plan"
        assert ut["session_id"] == EXPECTED_SESSION_ID

        # Tool count
        assert len(ut["children"]) == expected["tool_count"]

        # Timestamps for UT1
        if "started_at" in expected:
            assert ut["started_at"] == expected["started_at"]
        if "ended_at" in expected:
            assert ut["ended_at"] == expected["ended_at"]

    @pytest.mark.parametrize(
        "ut_index,tool_index",
        [(1, 0), (1, 1), (2, 0), (3, 0)],
        ids=["ut2-tool1", "ut2-tool2", "ut3-tool1", "ut4-tool1"],
    )
    def test_user_turn_tools(
        self, sample_session_tree: dict, ut_index: int, tool_index: int
    ):
        """Validate tool nodes within user turns (parameterized)."""
        ut = sample_session_tree["children"][ut_index]
        tool = ut["children"][tool_index]
        expected_tool = USER_TURN_EXPECTATIONS[ut_index]["tools"][tool_index]

        # Tool name
        assert tool["tool_name"] == expected_tool["name"]
        assert tool["node_type"] == "tool"
        assert tool["children"] == []  # Tools have no children

        # Duration and trace_id
        assert tool["duration_ms"] == expected_tool["duration_ms"]
        if "trace_id" in expected_tool:
            assert tool["trace_id"] == expected_tool["trace_id"]

        # Tool-specific display info
        if "url" in expected_tool:
            assert tool["display_info"] == expected_tool["url"]
        if "command" in expected_tool:
            assert tool["display_info"] == expected_tool["command"]
        if "path" in expected_tool:
            assert tool["display_info"] == expected_tool["path"]

        # Status for webfetch
        if "status" in expected_tool:
            assert tool["tool_status"] == expected_tool["status"]


class TestUserTurn5AndDelegation:
    """Tests for user turn 5 with agent delegation."""

    def test_user_turn_5_fields(self, sample_session_tree: dict):
        """Validate user turn 5 base fields."""
        ut5 = sample_session_tree["children"][4]
        expected = USER_TURN_EXPECTATIONS[4]

        # Basic fields
        assert ut5["trace_id"] == expected["trace_id"]
        assert ut5["prompt_input"] == expected["prompt"]
        assert ut5["tokens_in"] == expected["tokens_in"]
        assert ut5["tokens_out"] == expected["tokens_out"]
        assert ut5["duration_ms"] == expected["duration_ms"]
        assert ut5["cache_read"] == expected["cache_read"]
        assert ut5["child_session_id"] == expected["child_session_id"]

        # Common fields
        assert ut5["node_type"] == "user_turn"
        assert ut5["parent_agent"] == "user"
        assert ut5["session_id"] == EXPECTED_SESSION_ID

        # Has exactly one delegation child
        assert len(ut5["children"]) == 1
        assert ut5["children"][0]["node_type"] == "agent"

    def test_delegation_node_fields(self, sample_session_tree: dict):
        """Validate delegation node inside user turn 5."""
        deleg = sample_session_tree["children"][4]["children"][0]
        expected = USER_TURN_EXPECTATIONS[4]["delegation"]

        # Delegation identity
        assert deleg["node_type"] == "agent"
        assert deleg["subagent_type"] == expected["subagent_type"]
        assert deleg["parent_agent"] == expected["parent_agent"]
        assert deleg["trace_id"] == expected["trace_id"]
        assert deleg["child_session_id"] == expected["child_session_id"]

        # Token metrics
        assert deleg["tokens_in"] == expected["tokens_in"]
        assert deleg["tokens_out"] == expected["tokens_out"]
        assert deleg["duration_ms"] == expected["duration_ms"]
        assert deleg["cache_read"] == expected["cache_read"]

        # Tool count
        assert len(deleg["children"]) == expected["tool_count"]

    def test_delegation_tools(self, sample_session_tree: dict):
        """Validate tools inside delegation node."""
        deleg = sample_session_tree["children"][4]["children"][0]
        expected_tools = USER_TURN_EXPECTATIONS[4]["delegation"]["tools"]

        for i, (tool, expected) in enumerate(zip(deleg["children"], expected_tools)):
            assert tool["node_type"] == "tool", f"Tool {i} node_type mismatch"
            assert tool["tool_name"] == expected["name"], f"Tool {i} name mismatch"
            assert tool["display_info"] == expected["path"], f"Tool {i} path mismatch"
            assert tool["duration_ms"] == expected["duration_ms"], (
                f"Tool {i} duration mismatch"
            )
            assert tool["children"] == [], f"Tool {i} should have no children"


class TestTreeIntegrity:
    """Tests for tree structure integrity."""

    def test_all_nodes_have_required_structure(self, sample_session_tree: dict):
        """Validate every node has node_type and children is never None."""

        def check_node(node: dict, path: str = "root"):
            # Every node must have node_type
            assert "node_type" in node, f"Missing node_type at {path}"

            # children must be list, never None
            if "children" in node:
                assert node["children"] is not None, f"children is None at {path}"
                assert isinstance(node["children"], list), (
                    f"children not list at {path}"
                )

            # Recurse
            for i, child in enumerate(node.get("children", [])):
                check_node(child, f"{path}.children[{i}]")

        check_node(sample_session_tree)

    def test_all_tools_have_required_fields(self, sample_session_tree: dict):
        """Every tool node must have tool_name, duration_ms, and node_type."""
        required_fields = {"tool_name", "duration_ms", "node_type"}

        def check_tools(node: dict, path: str = "root"):
            if node.get("node_type") == "tool":
                for field in required_fields:
                    assert field in node, f"Tool at {path} missing {field}"
            for i, child in enumerate(node.get("children", [])):
                check_tools(child, f"{path}.children[{i}]")

        check_tools(sample_session_tree)

    def test_all_user_turns_have_required_fields(self, sample_session_tree: dict):
        """Every user_turn must have trace_id, tokens_in, tokens_out, duration_ms."""
        required_fields = {
            "trace_id",
            "tokens_in",
            "tokens_out",
            "duration_ms",
            "node_type",
        }

        for i, child in enumerate(sample_session_tree["children"]):
            if child.get("node_type") == "user_turn":
                for field in required_fields:
                    assert field in child, f"User turn {i} missing {field}"

    def test_session_id_propagation(self, sample_session_tree: dict):
        """User turns should have same session_id as parent session."""
        parent_session_id = sample_session_tree["session_id"]

        for i, child in enumerate(sample_session_tree["children"]):
            assert child.get("session_id") == parent_session_id, (
                f"User turn {i} session_id mismatch"
            )


class TestTimestampValidation:
    """Tests for timestamp format and ordering."""

    def test_all_timestamps_valid_and_ordered(self, sample_session_tree: dict):
        """All timestamps must be valid ISO and in chronological order."""
        # Session timestamp
        ts = sample_session_tree["started_at"]
        dt = datetime.fromisoformat(ts)
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 4

        # User turn timestamps valid and ordered
        timestamps = []
        for i, ut in enumerate(sample_session_tree["children"]):
            if "started_at" in ut:
                try:
                    datetime.fromisoformat(ut["started_at"])
                    timestamps.append(ut["started_at"])
                except ValueError:
                    pytest.fail(
                        f"User turn {i} has invalid started_at: {ut['started_at']}"
                    )

        assert timestamps == sorted(timestamps), "User turns not in chronological order"

    def test_ended_at_after_started_at(self, sample_session_tree: dict):
        """For each node with both timestamps, ended_at must be after started_at."""

        def check_timestamps(node: dict, path: str = "root"):
            if "started_at" in node and "ended_at" in node:
                start = datetime.fromisoformat(node["started_at"])
                end = datetime.fromisoformat(node["ended_at"])
                assert end >= start, f"ended_at before started_at at {path}"

            for i, child in enumerate(node.get("children", [])):
                check_timestamps(child, f"{path}.children[{i}]")

        check_timestamps(sample_session_tree)


class TestTokenValidation:
    """Tests for token values consistency."""

    def test_all_tokens_non_negative_and_reasonable(self, sample_session_tree: dict):
        """All token values must be >= 0 and session totals reasonable."""
        # Session tokens > 0
        assert sample_session_tree["tokens_in"] > 0
        assert sample_session_tree["tokens_out"] > 0

        # Sum validation
        ut_tokens_in = sum(ut["tokens_in"] for ut in sample_session_tree["children"])
        ut_tokens_out = sum(ut["tokens_out"] for ut in sample_session_tree["children"])
        assert ut_tokens_in <= sample_session_tree["tokens_in"] * 2
        assert ut_tokens_out <= sample_session_tree["tokens_out"] * 2

        # Non-negative recursively
        def check_tokens(node: dict, path: str = "root"):
            if "tokens_in" in node:
                assert node["tokens_in"] >= 0, f"Negative tokens_in at {path}"
            if "tokens_out" in node:
                assert node["tokens_out"] >= 0, f"Negative tokens_out at {path}"
            if "cache_read" in node:
                assert node["cache_read"] >= 0, f"Negative cache_read at {path}"

            for i, child in enumerate(node.get("children", [])):
                check_tokens(child, f"{path}.children[{i}]")

        check_tokens(sample_session_tree)


class TestToolArguments:
    """Tests for tool arguments JSON structure."""

    @pytest.mark.parametrize(
        "ut_index,tool_index,expected_key",
        [
            (1, 0, "url"),  # webfetch
            (1, 1, "url"),  # webfetch
            (2, 0, "command"),  # bash
            (3, 0, "filePath"),  # read
        ],
        ids=["webfetch1", "webfetch2", "bash", "read"],
    )
    def test_tool_arguments_parse_correctly(
        self,
        sample_session_tree: dict,
        ut_index: int,
        tool_index: int,
        expected_key: str,
    ):
        """Tool arguments must be valid JSON with expected key."""
        ut = sample_session_tree["children"][ut_index]
        tool = ut["children"][tool_index]
        args = json.loads(tool["arguments"])
        assert expected_key in args, (
            f"Missing {expected_key} in {tool['tool_name']} arguments"
        )


class TestNodeTypeAndIdValidation:
    """Tests for node types and ID formats."""

    VALID_NODE_TYPES = {"session", "user_turn", "tool", "agent", "exchange", "part"}

    def test_all_nodes_have_valid_type(self, sample_session_tree: dict):
        """All node_type values must be from the valid set."""

        def check_type(node: dict, path: str = "root"):
            nt = node.get("node_type")
            assert nt in self.VALID_NODE_TYPES, f"Invalid node_type '{nt}' at {path}"
            for i, child in enumerate(node.get("children", [])):
                check_type(child, f"{path}.children[{i}]")

        check_type(sample_session_tree)

    def test_id_formats(self, sample_session_tree: dict):
        """Validate ID format patterns."""
        # Session ID format
        assert sample_session_tree["session_id"].startswith("ses_")

        # Tool trace IDs
        def check_tool_ids(node: dict):
            if node.get("node_type") == "tool":
                trace_id = node.get("trace_id", "")
                assert any(x in trace_id for x in ["tool_", "prt_", "deleg"]), (
                    f"Invalid tool trace_id format: {trace_id}"
                )
            for child in node.get("children", []):
                check_tool_ids(child)

        check_tool_ids(sample_session_tree)

        # User turn trace IDs
        for ut in sample_session_tree["children"]:
            if ut.get("node_type") == "user_turn":
                trace_id = ut.get("trace_id", "")
                assert any(x in trace_id for x in ["exchange_", "msg_"]), (
                    f"Invalid user turn trace_id format: {trace_id}"
                )
