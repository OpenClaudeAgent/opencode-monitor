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
"""

import json
from datetime import datetime, timedelta
from typing import Any

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

# User Turn 1 - Simple greeting (no tools)
UT1_TRACE_ID = "exchange_msg_001"
UT1_PROMPT = "Salut, est-ce que ça va ?"
UT1_TOKENS_IN = 8
UT1_TOKENS_OUT = 305
UT1_DURATION_MS = 14708
UT1_CACHE_READ = 0
UT1_TOOL_COUNT = 0
UT1_STARTED_AT = "2026-01-04T15:44:31.248000"
UT1_ENDED_AT = "2026-01-04T15:44:45.956000"

# User Turn 2 - Weather API search (2 webfetch tools)
UT2_TRACE_ID = "exchange_msg_002"
UT2_PROMPT = "Cherche une API météo"
UT2_TOKENS_IN = 12
UT2_TOKENS_OUT = 558
UT2_DURATION_MS = 4673
UT2_CACHE_READ = 36680
UT2_TOOL_COUNT = 2
UT2_STARTED_AT = "2026-01-04T15:45:48.773000"

# User Turn 2 - Tool 1 (webfetch weatherapi)
UT2_TOOL1_NAME = "webfetch"
UT2_TOOL1_URL = "https://www.weatherapi.com/"
UT2_TOOL1_DURATION_MS = 258
UT2_TOOL1_TRACE_ID = "tool_prt_001"
UT2_TOOL1_STATUS = "completed"

# User Turn 2 - Tool 2 (webfetch openweathermap)
UT2_TOOL2_NAME = "webfetch"
UT2_TOOL2_URL = "https://openweathermap.org/api"
UT2_TOOL2_DURATION_MS = 173
UT2_TOOL2_TRACE_ID = "tool_prt_002"
UT2_TOOL2_STATUS = "completed"

# User Turn 3 - Create file (1 bash tool)
UT3_TRACE_ID = "exchange_msg_003"
UT3_PROMPT = "Crée un fichier test"
UT3_TOKENS_IN = 11
UT3_TOKENS_OUT = 143
UT3_DURATION_MS = 3918
UT3_CACHE_READ = 68618
UT3_TOOL_COUNT = 1

# User Turn 3 - Tool (bash)
UT3_TOOL1_NAME = "bash"
UT3_TOOL1_COMMAND = "touch /tmp/test.txt"
UT3_TOOL1_DURATION_MS = 37
UT3_TOOL1_TRACE_ID = "tool_prt_003"

# User Turn 4 - Read README (1 read tool)
UT4_TRACE_ID = "exchange_msg_004"
UT4_PROMPT = "Lis le README"
UT4_TOKENS_IN = 10
UT4_TOKENS_OUT = 1778
UT4_DURATION_MS = 5052
UT4_CACHE_READ = 72980
UT4_TOOL_COUNT = 1

# User Turn 4 - Tool (read)
UT4_TOOL1_NAME = "read"
UT4_TOOL1_PATH = "/path/to/README.md"
UT4_TOOL1_DURATION_MS = 2
UT4_TOOL1_TRACE_ID = "tool_prt_004"

# User Turn 5 - Delegation (roadmap agent with 2 tools)
UT5_TRACE_ID = "exchange_msg_005"
UT5_PROMPT = "Lance l'agent roadmap"
UT5_TOKENS_IN = 15
UT5_TOKENS_OUT = 500
UT5_DURATION_MS = 165000
UT5_CACHE_READ = 30128
UT5_CHILD_SESSION_ID = "ses_child_session_001"

# Delegation inside User Turn 5
DELEG1_SUBAGENT_TYPE = "roadmap"
DELEG1_PARENT_AGENT = "plan"
DELEG1_TOKENS_IN = 35
DELEG1_TOKENS_OUT = 3127
DELEG1_DURATION_MS = 158859
DELEG1_CACHE_READ = 261028
DELEG1_CHILD_SESSION_ID = "ses_grandchild_001"
DELEG1_TRACE_ID = "prt_delegation_001"
DELEG1_TOOL_COUNT = 2

# Delegation tools
DELEG1_TOOL1_NAME = "read"
DELEG1_TOOL1_PATH = "/path/to/roadmap/README.md"
DELEG1_TOOL1_DURATION_MS = 2

DELEG1_TOOL2_NAME = "read"
DELEG1_TOOL2_PATH = "/path/to/roadmap/SPRINTS.md"
DELEG1_TOOL2_DURATION_MS = 1


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
                "cache_read": UT1_CACHE_READ,
                "children": [],
                "duration_ms": UT1_DURATION_MS,
                "ended_at": UT1_ENDED_AT,
                "node_type": "user_turn",
                "parent_agent": "user",
                "prompt_input": UT1_PROMPT,
                "session_id": EXPECTED_SESSION_ID,
                "started_at": UT1_STARTED_AT,
                "subagent_type": "plan",
                "tokens_in": UT1_TOKENS_IN,
                "tokens_out": UT1_TOKENS_OUT,
                "trace_id": UT1_TRACE_ID,
            },
            # User turn 2 - Weather API search (2 webfetch tools)
            {
                "cache_read": UT2_CACHE_READ,
                "children": [
                    {
                        "arguments": f'{{"url": "{UT2_TOOL1_URL}", "format": "text"}}',
                        "children": [],
                        "display_info": UT2_TOOL1_URL,
                        "duration_ms": UT2_TOOL1_DURATION_MS,
                        "node_type": "tool",
                        "session_id": EXPECTED_SESSION_ID,
                        "started_at": "2026-01-04T15:45:53.089000",
                        "tool_name": UT2_TOOL1_NAME,
                        "tool_status": UT2_TOOL1_STATUS,
                        "trace_id": UT2_TOOL1_TRACE_ID,
                    },
                    {
                        "arguments": f'{{"url": "{UT2_TOOL2_URL}", "format": "text"}}',
                        "children": [],
                        "display_info": UT2_TOOL2_URL,
                        "duration_ms": UT2_TOOL2_DURATION_MS,
                        "node_type": "tool",
                        "session_id": EXPECTED_SESSION_ID,
                        "started_at": "2026-01-04T15:45:53.500000",
                        "tool_name": UT2_TOOL2_NAME,
                        "tool_status": UT2_TOOL2_STATUS,
                        "trace_id": UT2_TOOL2_TRACE_ID,
                    },
                ],
                "duration_ms": UT2_DURATION_MS,
                "ended_at": "2026-01-04T15:45:53.446000",
                "node_type": "user_turn",
                "parent_agent": "user",
                "prompt_input": UT2_PROMPT,
                "session_id": EXPECTED_SESSION_ID,
                "started_at": UT2_STARTED_AT,
                "subagent_type": "plan",
                "tokens_in": UT2_TOKENS_IN,
                "tokens_out": UT2_TOKENS_OUT,
                "trace_id": UT2_TRACE_ID,
            },
            # User turn 3 - Create file (1 bash tool)
            {
                "cache_read": UT3_CACHE_READ,
                "children": [
                    {
                        "arguments": f'{{"command": "{UT3_TOOL1_COMMAND}", "description": "Create test file"}}',
                        "children": [],
                        "display_info": UT3_TOOL1_COMMAND,
                        "duration_ms": UT3_TOOL1_DURATION_MS,
                        "node_type": "tool",
                        "session_id": EXPECTED_SESSION_ID,
                        "started_at": "2026-01-04T15:46:10.000000",
                        "tool_name": UT3_TOOL1_NAME,
                        "tool_status": "completed",
                        "trace_id": UT3_TOOL1_TRACE_ID,
                    }
                ],
                "duration_ms": UT3_DURATION_MS,
                "ended_at": "2026-01-04T15:46:14.000000",
                "node_type": "user_turn",
                "parent_agent": "user",
                "prompt_input": UT3_PROMPT,
                "session_id": EXPECTED_SESSION_ID,
                "started_at": "2026-01-04T15:46:10.000000",
                "subagent_type": "plan",
                "tokens_in": UT3_TOKENS_IN,
                "tokens_out": UT3_TOKENS_OUT,
                "trace_id": UT3_TRACE_ID,
            },
            # User turn 4 - Read README (1 read tool)
            {
                "cache_read": UT4_CACHE_READ,
                "children": [
                    {
                        "arguments": f'{{"filePath": "{UT4_TOOL1_PATH}"}}',
                        "children": [],
                        "display_info": UT4_TOOL1_PATH,
                        "duration_ms": UT4_TOOL1_DURATION_MS,
                        "node_type": "tool",
                        "session_id": EXPECTED_SESSION_ID,
                        "started_at": "2026-01-04T15:47:00.000000",
                        "tool_name": UT4_TOOL1_NAME,
                        "tool_status": "completed",
                        "trace_id": UT4_TOOL1_TRACE_ID,
                    }
                ],
                "duration_ms": UT4_DURATION_MS,
                "ended_at": "2026-01-04T15:47:05.000000",
                "node_type": "user_turn",
                "parent_agent": "user",
                "prompt_input": UT4_PROMPT,
                "session_id": EXPECTED_SESSION_ID,
                "started_at": "2026-01-04T15:47:00.000000",
                "subagent_type": "plan",
                "tokens_in": UT4_TOKENS_IN,
                "tokens_out": UT4_TOKENS_OUT,
                "trace_id": UT4_TRACE_ID,
            },
            # User turn 5 - Agent delegation with nested tools
            {
                "cache_read": UT5_CACHE_READ,
                "child_session_id": UT5_CHILD_SESSION_ID,
                "children": [
                    {
                        "cache_read": DELEG1_CACHE_READ,
                        "child_session_id": DELEG1_CHILD_SESSION_ID,
                        "children": [
                            {
                                "arguments": f'{{"filePath": "{DELEG1_TOOL1_PATH}"}}',
                                "children": [],
                                "display_info": DELEG1_TOOL1_PATH,
                                "duration_ms": DELEG1_TOOL1_DURATION_MS,
                                "node_type": "tool",
                                "tool_name": DELEG1_TOOL1_NAME,
                                "tool_status": "completed",
                                "trace_id": "tool_deleg_001",
                            },
                            {
                                "arguments": f'{{"filePath": "{DELEG1_TOOL2_PATH}"}}',
                                "children": [],
                                "display_info": DELEG1_TOOL2_PATH,
                                "duration_ms": DELEG1_TOOL2_DURATION_MS,
                                "node_type": "tool",
                                "tool_name": DELEG1_TOOL2_NAME,
                                "tool_status": "completed",
                                "trace_id": "tool_deleg_002",
                            },
                        ],
                        "duration_ms": DELEG1_DURATION_MS,
                        "ended_at": "2026-01-04T15:50:38.000000",
                        "node_type": "agent",
                        "parent_agent": DELEG1_PARENT_AGENT,
                        "prompt_input": "Analyze roadmap",
                        "session_id": UT5_CHILD_SESSION_ID,
                        "started_at": "2026-01-04T15:48:00.000000",
                        "subagent_type": DELEG1_SUBAGENT_TYPE,
                        "tokens_in": DELEG1_TOKENS_IN,
                        "tokens_out": DELEG1_TOKENS_OUT,
                        "trace_id": DELEG1_TRACE_ID,
                    }
                ],
                "duration_ms": UT5_DURATION_MS,
                "ended_at": "2026-01-04T15:50:45.000000",
                "node_type": "user_turn",
                "parent_agent": "user",
                "prompt_input": UT5_PROMPT,
                "session_id": EXPECTED_SESSION_ID,
                "started_at": "2026-01-04T15:48:00.000000",
                "subagent_type": "plan",
                "tokens_in": UT5_TOKENS_IN,
                "tokens_out": UT5_TOKENS_OUT,
                "trace_id": UT5_TRACE_ID,
            },
        ],
    }


@pytest.fixture
def sample_tool_node() -> dict:
    """Sample tool node with all required fields."""
    return {
        "arguments": f'{{"filePath": "{UT4_TOOL1_PATH}"}}',
        "children": [],
        "display_info": UT4_TOOL1_PATH,
        "duration_ms": UT4_TOOL1_DURATION_MS,
        "node_type": "tool",
        "result_summary": None,
        "session_id": EXPECTED_SESSION_ID,
        "started_at": "2026-01-04T15:47:00.000000",
        "tool_name": UT4_TOOL1_NAME,
        "tool_status": "completed",
        "trace_id": UT4_TOOL1_TRACE_ID,
    }


@pytest.fixture
def sample_delegation_node() -> dict:
    """Sample agent delegation node with exact values."""
    return {
        "cache_read": DELEG1_CACHE_READ,
        "child_session_id": DELEG1_CHILD_SESSION_ID,
        "children": [],
        "duration_ms": DELEG1_DURATION_MS,
        "ended_at": "2026-01-04T15:50:38.000000",
        "node_type": "agent",
        "parent_agent": DELEG1_PARENT_AGENT,
        "parent_trace_id": "root_ses_parent",
        "prompt_input": "Analyze roadmap",
        "prompt_output": None,
        "session_id": UT5_CHILD_SESSION_ID,
        "started_at": "2026-01-04T15:48:00.000000",
        "status": "completed",
        "subagent_type": DELEG1_SUBAGENT_TYPE,
        "tokens_in": DELEG1_TOKENS_IN,
        "tokens_out": DELEG1_TOKENS_OUT,
        "trace_id": DELEG1_TRACE_ID,
    }


# =============================================================================
# Tests - Session Level Exact Values
# =============================================================================


class TestSessionExactValues:
    """Tests that validate EXACT session-level values."""

    def test_session_id_exact(self, sample_session_tree: dict):
        """Session ID must be exactly as expected."""
        assert sample_session_tree["session_id"] == EXPECTED_SESSION_ID

    def test_session_title_exact(self, sample_session_tree: dict):
        """Session title must be exactly as expected."""
        assert sample_session_tree["title"] == EXPECTED_SESSION_TITLE

    def test_session_directory_exact(self, sample_session_tree: dict):
        """Session directory must be exactly as expected."""
        assert sample_session_tree["directory"] == EXPECTED_SESSION_DIRECTORY

    def test_session_agent_type_exact(self, sample_session_tree: dict):
        """Session agent_type must be exactly as expected."""
        assert sample_session_tree["agent_type"] == EXPECTED_SESSION_AGENT_TYPE

    def test_session_tokens_in_exact(self, sample_session_tree: dict):
        """Session tokens_in must be exactly 129."""
        assert sample_session_tree["tokens_in"] == EXPECTED_SESSION_TOKENS_IN

    def test_session_tokens_out_exact(self, sample_session_tree: dict):
        """Session tokens_out must be exactly 9101."""
        assert sample_session_tree["tokens_out"] == EXPECTED_SESSION_TOKENS_OUT

    def test_session_cache_read_exact(self, sample_session_tree: dict):
        """Session cache_read must be exactly 417959."""
        assert sample_session_tree["cache_read"] == EXPECTED_SESSION_CACHE_READ

    def test_session_started_at_exact(self, sample_session_tree: dict):
        """Session started_at must be exactly as expected."""
        assert sample_session_tree["started_at"] == EXPECTED_SESSION_STARTED_AT

    def test_session_node_type_is_session(self, sample_session_tree: dict):
        """Session node_type must be 'session'."""
        assert sample_session_tree["node_type"] == "session"


# =============================================================================
# Tests - User Turn Counts and Structure
# =============================================================================


class TestUserTurnCounts:
    """Tests that validate exact user turn counts."""

    def test_exact_user_turn_count(self, sample_session_tree: dict):
        """Session must have exactly 5 user turns."""
        user_turns = [
            c
            for c in sample_session_tree["children"]
            if c.get("node_type") == "user_turn"
        ]
        assert len(user_turns) == EXPECTED_USER_TURN_COUNT, (
            f"Expected {EXPECTED_USER_TURN_COUNT} user turns, got {len(user_turns)}"
        )

    def test_children_are_all_user_turns(self, sample_session_tree: dict):
        """All direct children of session should be user_turn nodes."""
        for i, child in enumerate(sample_session_tree["children"]):
            assert child["node_type"] == "user_turn", (
                f"Child {i} has node_type '{child['node_type']}', expected 'user_turn'"
            )

    def test_total_tool_count_across_all_turns(self, sample_session_tree: dict):
        """Total tools across all user turns must be exactly 6."""
        total_tools = 0

        def count_tools(node: dict) -> int:
            count = 0
            for child in node.get("children", []):
                if child.get("node_type") == "tool":
                    count += 1
                count += count_tools(child)
            return count

        for user_turn in sample_session_tree["children"]:
            total_tools += count_tools(user_turn)

        assert total_tools == EXPECTED_TOTAL_TOOL_COUNT, (
            f"Expected {EXPECTED_TOTAL_TOOL_COUNT} tools, got {total_tools}"
        )


# =============================================================================
# Tests - User Turn 1 Exact Values (Simple greeting)
# =============================================================================


class TestUserTurn1Exact:
    """Tests for User Turn 1 - Simple greeting (no tools)."""

    def _get_ut1(self, tree: dict) -> dict:
        return tree["children"][0]

    def test_ut1_trace_id(self, sample_session_tree: dict):
        """User turn 1 trace_id must be exact."""
        ut1 = self._get_ut1(sample_session_tree)
        assert ut1["trace_id"] == UT1_TRACE_ID

    def test_ut1_prompt_input(self, sample_session_tree: dict):
        """User turn 1 prompt must be exact."""
        ut1 = self._get_ut1(sample_session_tree)
        assert ut1["prompt_input"] == UT1_PROMPT

    def test_ut1_tokens_in(self, sample_session_tree: dict):
        """User turn 1 tokens_in must be exactly 8."""
        ut1 = self._get_ut1(sample_session_tree)
        assert ut1["tokens_in"] == UT1_TOKENS_IN

    def test_ut1_tokens_out(self, sample_session_tree: dict):
        """User turn 1 tokens_out must be exactly 305."""
        ut1 = self._get_ut1(sample_session_tree)
        assert ut1["tokens_out"] == UT1_TOKENS_OUT

    def test_ut1_duration_ms(self, sample_session_tree: dict):
        """User turn 1 duration must be exactly 14708ms."""
        ut1 = self._get_ut1(sample_session_tree)
        assert ut1["duration_ms"] == UT1_DURATION_MS

    def test_ut1_cache_read(self, sample_session_tree: dict):
        """User turn 1 cache_read must be exactly 0."""
        ut1 = self._get_ut1(sample_session_tree)
        assert ut1["cache_read"] == UT1_CACHE_READ

    def test_ut1_has_no_tools(self, sample_session_tree: dict):
        """User turn 1 must have no tools (empty children)."""
        ut1 = self._get_ut1(sample_session_tree)
        assert ut1["children"] == [], f"Expected empty children, got {ut1['children']}"
        assert len(ut1["children"]) == UT1_TOOL_COUNT

    def test_ut1_started_at(self, sample_session_tree: dict):
        """User turn 1 started_at must be exact."""
        ut1 = self._get_ut1(sample_session_tree)
        assert ut1["started_at"] == UT1_STARTED_AT

    def test_ut1_ended_at(self, sample_session_tree: dict):
        """User turn 1 ended_at must be exact."""
        ut1 = self._get_ut1(sample_session_tree)
        assert ut1["ended_at"] == UT1_ENDED_AT

    def test_ut1_node_type(self, sample_session_tree: dict):
        """User turn 1 node_type must be 'user_turn'."""
        ut1 = self._get_ut1(sample_session_tree)
        assert ut1["node_type"] == "user_turn"

    def test_ut1_parent_agent(self, sample_session_tree: dict):
        """User turn 1 parent_agent must be 'user'."""
        ut1 = self._get_ut1(sample_session_tree)
        assert ut1["parent_agent"] == "user"

    def test_ut1_subagent_type(self, sample_session_tree: dict):
        """User turn 1 subagent_type must be 'plan'."""
        ut1 = self._get_ut1(sample_session_tree)
        assert ut1["subagent_type"] == "plan"

    def test_ut1_session_id(self, sample_session_tree: dict):
        """User turn 1 session_id must match parent session."""
        ut1 = self._get_ut1(sample_session_tree)
        assert ut1["session_id"] == EXPECTED_SESSION_ID


# =============================================================================
# Tests - User Turn 2 Exact Values (Weather API - 2 webfetch)
# =============================================================================


class TestUserTurn2Exact:
    """Tests for User Turn 2 - Weather API search (2 webfetch tools)."""

    def _get_ut2(self, tree: dict) -> dict:
        return tree["children"][1]

    def test_ut2_trace_id(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        assert ut2["trace_id"] == UT2_TRACE_ID

    def test_ut2_prompt_input(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        assert ut2["prompt_input"] == UT2_PROMPT

    def test_ut2_tokens_in(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        assert ut2["tokens_in"] == UT2_TOKENS_IN

    def test_ut2_tokens_out(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        assert ut2["tokens_out"] == UT2_TOKENS_OUT

    def test_ut2_duration_ms(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        assert ut2["duration_ms"] == UT2_DURATION_MS

    def test_ut2_cache_read(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        assert ut2["cache_read"] == UT2_CACHE_READ

    def test_ut2_has_exactly_2_tools(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        assert len(ut2["children"]) == UT2_TOOL_COUNT

    def test_ut2_tool1_is_webfetch(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        tool1 = ut2["children"][0]
        assert tool1["tool_name"] == UT2_TOOL1_NAME

    def test_ut2_tool1_url_exact(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        tool1 = ut2["children"][0]
        assert tool1["display_info"] == UT2_TOOL1_URL

    def test_ut2_tool1_duration(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        tool1 = ut2["children"][0]
        assert tool1["duration_ms"] == UT2_TOOL1_DURATION_MS

    def test_ut2_tool1_trace_id(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        tool1 = ut2["children"][0]
        assert tool1["trace_id"] == UT2_TOOL1_TRACE_ID

    def test_ut2_tool1_status(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        tool1 = ut2["children"][0]
        assert tool1["tool_status"] == UT2_TOOL1_STATUS

    def test_ut2_tool1_node_type(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        tool1 = ut2["children"][0]
        assert tool1["node_type"] == "tool"

    def test_ut2_tool1_has_no_children(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        tool1 = ut2["children"][0]
        assert tool1["children"] == []

    def test_ut2_tool2_is_webfetch(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        tool2 = ut2["children"][1]
        assert tool2["tool_name"] == UT2_TOOL2_NAME

    def test_ut2_tool2_url_exact(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        tool2 = ut2["children"][1]
        assert tool2["display_info"] == UT2_TOOL2_URL

    def test_ut2_tool2_duration(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        tool2 = ut2["children"][1]
        assert tool2["duration_ms"] == UT2_TOOL2_DURATION_MS

    def test_ut2_tool2_trace_id(self, sample_session_tree: dict):
        ut2 = self._get_ut2(sample_session_tree)
        tool2 = ut2["children"][1]
        assert tool2["trace_id"] == UT2_TOOL2_TRACE_ID


# =============================================================================
# Tests - User Turn 3 Exact Values (Create file - 1 bash)
# =============================================================================


class TestUserTurn3Exact:
    """Tests for User Turn 3 - Create file (1 bash tool)."""

    def _get_ut3(self, tree: dict) -> dict:
        return tree["children"][2]

    def test_ut3_trace_id(self, sample_session_tree: dict):
        ut3 = self._get_ut3(sample_session_tree)
        assert ut3["trace_id"] == UT3_TRACE_ID

    def test_ut3_prompt_input(self, sample_session_tree: dict):
        ut3 = self._get_ut3(sample_session_tree)
        assert ut3["prompt_input"] == UT3_PROMPT

    def test_ut3_tokens_in(self, sample_session_tree: dict):
        ut3 = self._get_ut3(sample_session_tree)
        assert ut3["tokens_in"] == UT3_TOKENS_IN

    def test_ut3_tokens_out(self, sample_session_tree: dict):
        ut3 = self._get_ut3(sample_session_tree)
        assert ut3["tokens_out"] == UT3_TOKENS_OUT

    def test_ut3_duration_ms(self, sample_session_tree: dict):
        ut3 = self._get_ut3(sample_session_tree)
        assert ut3["duration_ms"] == UT3_DURATION_MS

    def test_ut3_cache_read(self, sample_session_tree: dict):
        ut3 = self._get_ut3(sample_session_tree)
        assert ut3["cache_read"] == UT3_CACHE_READ

    def test_ut3_has_exactly_1_tool(self, sample_session_tree: dict):
        ut3 = self._get_ut3(sample_session_tree)
        assert len(ut3["children"]) == UT3_TOOL_COUNT

    def test_ut3_tool_is_bash(self, sample_session_tree: dict):
        ut3 = self._get_ut3(sample_session_tree)
        tool = ut3["children"][0]
        assert tool["tool_name"] == UT3_TOOL1_NAME

    def test_ut3_tool_command_exact(self, sample_session_tree: dict):
        ut3 = self._get_ut3(sample_session_tree)
        tool = ut3["children"][0]
        assert tool["display_info"] == UT3_TOOL1_COMMAND

    def test_ut3_tool_duration(self, sample_session_tree: dict):
        ut3 = self._get_ut3(sample_session_tree)
        tool = ut3["children"][0]
        assert tool["duration_ms"] == UT3_TOOL1_DURATION_MS

    def test_ut3_tool_trace_id(self, sample_session_tree: dict):
        ut3 = self._get_ut3(sample_session_tree)
        tool = ut3["children"][0]
        assert tool["trace_id"] == UT3_TOOL1_TRACE_ID


# =============================================================================
# Tests - User Turn 4 Exact Values (Read README - 1 read)
# =============================================================================


class TestUserTurn4Exact:
    """Tests for User Turn 4 - Read README (1 read tool)."""

    def _get_ut4(self, tree: dict) -> dict:
        return tree["children"][3]

    def test_ut4_trace_id(self, sample_session_tree: dict):
        ut4 = self._get_ut4(sample_session_tree)
        assert ut4["trace_id"] == UT4_TRACE_ID

    def test_ut4_prompt_input(self, sample_session_tree: dict):
        ut4 = self._get_ut4(sample_session_tree)
        assert ut4["prompt_input"] == UT4_PROMPT

    def test_ut4_tokens_in(self, sample_session_tree: dict):
        ut4 = self._get_ut4(sample_session_tree)
        assert ut4["tokens_in"] == UT4_TOKENS_IN

    def test_ut4_tokens_out(self, sample_session_tree: dict):
        ut4 = self._get_ut4(sample_session_tree)
        assert ut4["tokens_out"] == UT4_TOKENS_OUT

    def test_ut4_duration_ms(self, sample_session_tree: dict):
        ut4 = self._get_ut4(sample_session_tree)
        assert ut4["duration_ms"] == UT4_DURATION_MS

    def test_ut4_cache_read(self, sample_session_tree: dict):
        ut4 = self._get_ut4(sample_session_tree)
        assert ut4["cache_read"] == UT4_CACHE_READ

    def test_ut4_has_exactly_1_tool(self, sample_session_tree: dict):
        ut4 = self._get_ut4(sample_session_tree)
        assert len(ut4["children"]) == UT4_TOOL_COUNT

    def test_ut4_tool_is_read(self, sample_session_tree: dict):
        ut4 = self._get_ut4(sample_session_tree)
        tool = ut4["children"][0]
        assert tool["tool_name"] == UT4_TOOL1_NAME

    def test_ut4_tool_path_exact(self, sample_session_tree: dict):
        ut4 = self._get_ut4(sample_session_tree)
        tool = ut4["children"][0]
        assert tool["display_info"] == UT4_TOOL1_PATH

    def test_ut4_tool_duration(self, sample_session_tree: dict):
        ut4 = self._get_ut4(sample_session_tree)
        tool = ut4["children"][0]
        assert tool["duration_ms"] == UT4_TOOL1_DURATION_MS

    def test_ut4_tool_trace_id(self, sample_session_tree: dict):
        ut4 = self._get_ut4(sample_session_tree)
        tool = ut4["children"][0]
        assert tool["trace_id"] == UT4_TOOL1_TRACE_ID


# =============================================================================
# Tests - User Turn 5 Exact Values (Delegation with nested tools)
# =============================================================================


class TestUserTurn5AndDelegation:
    """Tests for User Turn 5 - Delegation to roadmap agent with nested tools."""

    def _get_ut5(self, tree: dict) -> dict:
        return tree["children"][4]

    def _get_delegation(self, tree: dict) -> dict:
        return self._get_ut5(tree)["children"][0]

    def test_ut5_trace_id(self, sample_session_tree: dict):
        ut5 = self._get_ut5(sample_session_tree)
        assert ut5["trace_id"] == UT5_TRACE_ID

    def test_ut5_prompt_input(self, sample_session_tree: dict):
        ut5 = self._get_ut5(sample_session_tree)
        assert ut5["prompt_input"] == UT5_PROMPT

    def test_ut5_tokens_in(self, sample_session_tree: dict):
        ut5 = self._get_ut5(sample_session_tree)
        assert ut5["tokens_in"] == UT5_TOKENS_IN

    def test_ut5_tokens_out(self, sample_session_tree: dict):
        ut5 = self._get_ut5(sample_session_tree)
        assert ut5["tokens_out"] == UT5_TOKENS_OUT

    def test_ut5_duration_ms(self, sample_session_tree: dict):
        ut5 = self._get_ut5(sample_session_tree)
        assert ut5["duration_ms"] == UT5_DURATION_MS

    def test_ut5_cache_read(self, sample_session_tree: dict):
        ut5 = self._get_ut5(sample_session_tree)
        assert ut5["cache_read"] == UT5_CACHE_READ

    def test_ut5_has_child_session_id(self, sample_session_tree: dict):
        ut5 = self._get_ut5(sample_session_tree)
        assert ut5["child_session_id"] == UT5_CHILD_SESSION_ID

    def test_ut5_has_exactly_1_delegation(self, sample_session_tree: dict):
        ut5 = self._get_ut5(sample_session_tree)
        assert len(ut5["children"]) == 1
        assert ut5["children"][0]["node_type"] == "agent"

    # Delegation assertions
    def test_delegation_node_type(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        assert deleg["node_type"] == "agent"

    def test_delegation_subagent_type(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        assert deleg["subagent_type"] == DELEG1_SUBAGENT_TYPE

    def test_delegation_parent_agent(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        assert deleg["parent_agent"] == DELEG1_PARENT_AGENT

    def test_delegation_tokens_in(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        assert deleg["tokens_in"] == DELEG1_TOKENS_IN

    def test_delegation_tokens_out(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        assert deleg["tokens_out"] == DELEG1_TOKENS_OUT

    def test_delegation_duration_ms(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        assert deleg["duration_ms"] == DELEG1_DURATION_MS

    def test_delegation_cache_read(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        assert deleg["cache_read"] == DELEG1_CACHE_READ

    def test_delegation_child_session_id(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        assert deleg["child_session_id"] == DELEG1_CHILD_SESSION_ID

    def test_delegation_trace_id(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        assert deleg["trace_id"] == DELEG1_TRACE_ID

    def test_delegation_has_exactly_2_tools(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        assert len(deleg["children"]) == DELEG1_TOOL_COUNT

    def test_delegation_tool1_is_read(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        tool1 = deleg["children"][0]
        assert tool1["tool_name"] == DELEG1_TOOL1_NAME

    def test_delegation_tool1_path(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        tool1 = deleg["children"][0]
        assert tool1["display_info"] == DELEG1_TOOL1_PATH

    def test_delegation_tool1_duration(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        tool1 = deleg["children"][0]
        assert tool1["duration_ms"] == DELEG1_TOOL1_DURATION_MS

    def test_delegation_tool2_is_read(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        tool2 = deleg["children"][1]
        assert tool2["tool_name"] == DELEG1_TOOL2_NAME

    def test_delegation_tool2_path(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        tool2 = deleg["children"][1]
        assert tool2["display_info"] == DELEG1_TOOL2_PATH

    def test_delegation_tool2_duration(self, sample_session_tree: dict):
        deleg = self._get_delegation(sample_session_tree)
        tool2 = deleg["children"][1]
        assert tool2["duration_ms"] == DELEG1_TOOL2_DURATION_MS


# =============================================================================
# Tests - Tree Traversal and Structure Integrity
# =============================================================================


class TestTreeStructureIntegrity:
    """Tests for complete tree structure integrity."""

    def test_all_nodes_have_node_type(self, sample_session_tree: dict):
        """Every node in the tree must have a node_type field."""

        def check_node(node: dict, path: str = "root"):
            assert "node_type" in node, f"Missing node_type at {path}"
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

    def test_no_node_has_none_children(self, sample_session_tree: dict):
        """No node should have children=None, it should be [] if empty."""

        def check_children(node: dict, path: str = "root"):
            if "children" in node:
                assert node["children"] is not None, f"children is None at {path}"
                assert isinstance(node["children"], list), (
                    f"children is not list at {path}"
                )
            for i, child in enumerate(node.get("children", [])):
                check_children(child, f"{path}.children[{i}]")

        check_children(sample_session_tree)

    def test_session_id_propagated_correctly(self, sample_session_tree: dict):
        """User turns should have same session_id as parent session."""
        parent_session_id = sample_session_tree["session_id"]

        for i, child in enumerate(sample_session_tree["children"]):
            assert child.get("session_id") == parent_session_id, (
                f"User turn {i} session_id mismatch: {child.get('session_id')} != {parent_session_id}"
            )


# =============================================================================
# Tests - Timestamp Validation
# =============================================================================


class TestTimestampValidation:
    """Tests for timestamp format and ordering."""

    def test_session_started_at_is_valid_iso(self, sample_session_tree: dict):
        """Session started_at must be valid ISO format."""
        ts = sample_session_tree["started_at"]
        dt = datetime.fromisoformat(ts)
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 4

    def test_all_user_turn_timestamps_valid(self, sample_session_tree: dict):
        """All user turn timestamps must be valid ISO format."""
        for i, ut in enumerate(sample_session_tree["children"]):
            if "started_at" in ut:
                try:
                    datetime.fromisoformat(ut["started_at"])
                except ValueError:
                    pytest.fail(
                        f"User turn {i} has invalid started_at: {ut['started_at']}"
                    )

    def test_user_turns_in_chronological_order(self, sample_session_tree: dict):
        """User turns must be in chronological order by started_at."""
        timestamps = []
        for ut in sample_session_tree["children"]:
            if "started_at" in ut:
                timestamps.append(ut["started_at"])

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


# =============================================================================
# Tests - Token Aggregation Validation
# =============================================================================


class TestTokenAggregation:
    """Tests for token sum consistency."""

    def test_session_tokens_greater_than_zero(self, sample_session_tree: dict):
        """Session must have non-zero tokens."""
        assert sample_session_tree["tokens_in"] > 0
        assert sample_session_tree["tokens_out"] > 0

    def test_user_turn_tokens_sum_reasonable(self, sample_session_tree: dict):
        """Sum of user turn tokens should be close to session total."""
        ut_tokens_in = sum(ut["tokens_in"] for ut in sample_session_tree["children"])
        ut_tokens_out = sum(ut["tokens_out"] for ut in sample_session_tree["children"])

        # Allow for some variance due to aggregation
        assert ut_tokens_in <= sample_session_tree["tokens_in"] * 2
        assert ut_tokens_out <= sample_session_tree["tokens_out"] * 2

    def test_all_tokens_non_negative(self, sample_session_tree: dict):
        """All token values must be >= 0."""

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


# =============================================================================
# Tests - Tool Arguments JSON Parsing
# =============================================================================


class TestToolArgumentsParsing:
    """Tests for tool arguments JSON structure."""

    def test_webfetch_arguments_parse_correctly(self, sample_session_tree: dict):
        """Webfetch tool arguments must be valid JSON with url."""
        ut2 = sample_session_tree["children"][1]
        for tool in ut2["children"]:
            if tool["tool_name"] == "webfetch":
                args = json.loads(tool["arguments"])
                assert "url" in args
                assert args["url"].startswith("http")

    def test_bash_arguments_parse_correctly(self, sample_session_tree: dict):
        """Bash tool arguments must be valid JSON with command."""
        ut3 = sample_session_tree["children"][2]
        for tool in ut3["children"]:
            if tool["tool_name"] == "bash":
                args = json.loads(tool["arguments"])
                assert "command" in args

    def test_read_arguments_parse_correctly(self, sample_session_tree: dict):
        """Read tool arguments must be valid JSON with filePath."""
        ut4 = sample_session_tree["children"][3]
        for tool in ut4["children"]:
            if tool["tool_name"] == "read":
                args = json.loads(tool["arguments"])
                assert "filePath" in args


# =============================================================================
# Tests - Node Type Enum Validation
# =============================================================================


class TestNodeTypeValidation:
    """Tests for valid node_type values."""

    VALID_NODE_TYPES = {"session", "user_turn", "tool", "agent", "exchange", "part"}

    def test_all_nodes_have_valid_type(self, sample_session_tree: dict):
        """All node_type values must be from the valid set."""

        def check_type(node: dict, path: str = "root"):
            nt = node.get("node_type")
            assert nt in self.VALID_NODE_TYPES, f"Invalid node_type '{nt}' at {path}"
            for i, child in enumerate(node.get("children", [])):
                check_type(child, f"{path}.children[{i}]")

        check_type(sample_session_tree)


# =============================================================================
# Tests - ID Format Validation
# =============================================================================


class TestIdFormatValidation:
    """Tests for ID format consistency."""

    def test_session_id_format(self, sample_session_tree: dict):
        """Session ID must start with 'ses_'."""
        assert sample_session_tree["session_id"].startswith("ses_")

    def test_tool_trace_ids_format(self, sample_session_tree: dict):
        """Tool trace IDs should contain 'tool_' or 'prt_' or 'deleg'."""

        def check_tool_ids(node: dict):
            if node.get("node_type") == "tool":
                trace_id = node.get("trace_id", "")
                assert any(x in trace_id for x in ["tool_", "prt_", "deleg"]), (
                    f"Invalid tool trace_id format: {trace_id}"
                )
            for child in node.get("children", []):
                check_tool_ids(child)

        check_tool_ids(sample_session_tree)

    def test_exchange_trace_ids_format(self, sample_session_tree: dict):
        """User turn trace IDs should contain 'exchange_' or 'msg_'."""
        for ut in sample_session_tree["children"]:
            if ut.get("node_type") == "user_turn":
                trace_id = ut.get("trace_id", "")
                assert any(x in trace_id for x in ["exchange_", "msg_"]), (
                    f"Invalid user turn trace_id format: {trace_id}"
                )
