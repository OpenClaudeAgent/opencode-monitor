"""
Tests for Plan 45 Timeline API endpoints.

Covers:
- GET /api/session/{id}/timeline/full
- GET /api/session/{id}/exchanges
- GET /api/session/{id}/delegations
- Service layer methods: get_session_timeline_full, get_session_exchanges, get_delegation_tree
"""

from datetime import datetime, timedelta

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.tracing import TracingDataService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def service(tracing_service: TracingDataService) -> TracingDataService:
    """Alias for tracing_service from conftest."""
    return tracing_service


@pytest.fixture
def timeline_db(db: AnalyticsDB) -> AnalyticsDB:
    """Populate database with test data for timeline tests."""
    conn = db.connect()
    now = datetime.now()

    # Insert test session
    conn.execute(
        """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "ses_timeline_001",
            "proj_001",
            "/projects/test",
            "Timeline Test Session",
            now - timedelta(hours=2),
            now,
        ],
    )

    # Insert parent session for delegation tests
    conn.execute(
        """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "ses_parent_001",
            "proj_001",
            "/projects/parent",
            "Parent Session",
            now - timedelta(hours=3),
            now - timedelta(hours=1),
        ],
    )

    # Insert child session for delegation tests
    conn.execute(
        """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "ses_child_001",
            "proj_001",
            "/projects/child",
            "Child Session",
            now - timedelta(hours=2),
            now - timedelta(hours=1, minutes=30),
        ],
    )

    # Insert messages for timeline test
    # User message
    conn.execute(
        """INSERT INTO messages 
           (id, session_id, role, agent, model_id, provider_id,
            tokens_input, tokens_output, tokens_reasoning,
            created_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "msg_user_001",
            "ses_timeline_001",
            "user",
            None,
            None,
            None,
            0,
            0,
            0,
            now - timedelta(hours=2),
            now - timedelta(hours=2),
        ],
    )

    # Assistant message
    conn.execute(
        """INSERT INTO messages 
           (id, session_id, role, agent, model_id, provider_id,
            tokens_input, tokens_output, tokens_reasoning,
            created_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "msg_asst_001",
            "ses_timeline_001",
            "assistant",
            "dev",
            "claude-3",
            "anthropic",
            1000,
            500,
            100,
            now - timedelta(hours=1, minutes=55),
            now - timedelta(hours=1, minutes=50),
        ],
    )

    # Insert parts for timeline test
    # User text part
    conn.execute(
        """INSERT INTO parts 
           (id, session_id, message_id, part_type, content, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "prt_text_001",
            "ses_timeline_001",
            "msg_user_001",
            "text",
            "This is the user prompt content",
            now - timedelta(hours=2),
        ],
    )

    # Reasoning part
    conn.execute(
        """INSERT INTO parts 
           (id, session_id, message_id, part_type, reasoning_text, anthropic_signature,
            created_at, ended_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "prt_reason_001",
            "ses_timeline_001",
            "msg_asst_001",
            "reasoning",
            "Let me analyze this request...",
            "signature_abc123",
            now - timedelta(hours=1, minutes=55),
            now - timedelta(hours=1, minutes=54),
        ],
    )

    # Tool call part
    conn.execute(
        """INSERT INTO parts 
           (id, session_id, message_id, part_type, tool_name, tool_status,
            arguments, result_summary, duration_ms, created_at, ended_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "prt_tool_001",
            "ses_timeline_001",
            "msg_asst_001",
            "tool",
            "read",
            "completed",
            '{"filePath": "/src/main.py"}',
            "File content here...",
            150,
            now - timedelta(hours=1, minutes=53),
            now - timedelta(hours=1, minutes=52),
        ],
    )

    # Assistant response text part
    conn.execute(
        """INSERT INTO parts 
           (id, session_id, message_id, part_type, content, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "prt_text_002",
            "ses_timeline_001",
            "msg_asst_001",
            "text",
            "This is the assistant response content",
            now - timedelta(hours=1, minutes=50),
        ],
    )

    # Insert exchanges table data
    conn.execute(
        """INSERT INTO exchanges 
           (id, session_id, exchange_number, user_message_id, assistant_message_id,
            prompt_input, prompt_output, started_at, ended_at, duration_ms,
            tokens_in, tokens_out, tokens_reasoning, cost,
            tool_count, reasoning_count, agent, model_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "exc_001",
            "ses_timeline_001",
            1,
            "msg_user_001",
            "msg_asst_001",
            "This is the user prompt content",
            "This is the assistant response content",
            now - timedelta(hours=2),
            now - timedelta(hours=1, minutes=50),
            600000,  # 10 minutes
            1000,
            500,
            100,
            0.015,
            1,
            1,
            "dev",
            "claude-3",
        ],
    )

    # Insert exchange traces
    conn.execute(
        """INSERT INTO exchange_traces 
           (id, session_id, exchange_id, event_type, event_order, event_data,
            timestamp, duration_ms, tokens_in, tokens_out)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "evt_001",
            "ses_timeline_001",
            "exc_001",
            "reasoning",
            1,
            '{"text": "Let me analyze...", "has_signature": true, "signature": "sig123"}',
            now - timedelta(hours=1, minutes=55),
            60000,
            0,
            0,
        ],
    )

    conn.execute(
        """INSERT INTO exchange_traces 
           (id, session_id, exchange_id, event_type, event_order, event_data,
            timestamp, duration_ms, tokens_in, tokens_out)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "evt_002",
            "ses_timeline_001",
            "exc_001",
            "tool_call",
            2,
            '{"tool_name": "read", "status": "completed", "arguments": {"filePath": "/src/main.py"}}',
            now - timedelta(hours=1, minutes=53),
            150,
            0,
            0,
        ],
    )

    # Insert delegation for parent session
    conn.execute(
        """INSERT INTO delegations 
           (id, session_id, parent_agent, child_agent, child_session_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "del_001",
            "ses_parent_001",
            "coordinator",
            "dev",
            "ses_child_001",
            now - timedelta(hours=2),
        ],
    )

    # Insert messages for parent session
    conn.execute(
        """INSERT INTO messages 
           (id, session_id, role, agent, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        [
            "msg_parent_001",
            "ses_parent_001",
            "assistant",
            "coordinator",
            now - timedelta(hours=3),
        ],
    )

    # Insert messages for child session
    conn.execute(
        """INSERT INTO messages 
           (id, session_id, role, agent, created_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "msg_child_001",
            "ses_child_001",
            "assistant",
            "dev",
            now - timedelta(hours=2),
            now - timedelta(hours=1, minutes=30),
        ],
    )

    return db


@pytest.fixture
def timeline_service(timeline_db: AnalyticsDB) -> TracingDataService:
    """Create service with timeline test database."""
    return TracingDataService(db=timeline_db)


# =============================================================================
# Tests for get_session_timeline_full
# =============================================================================


class TestGetSessionTimelineFull:
    """Tests for get_session_timeline_full method."""

    def test_timeline_returns_success(self, timeline_service: TracingDataService):
        """Test timeline endpoint returns success for existing session."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        assert result["success"] is True
        assert "data" in result
        assert result["data"] is not None

    def test_timeline_returns_meta(self, timeline_service: TracingDataService):
        """Test timeline includes meta information."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        assert "meta" in result["data"]
        meta = result["data"]["meta"]
        assert meta["session_id"] == "ses_timeline_001"
        assert "generated_at" in meta
        assert "title" in meta
        assert "directory" in meta

    def test_timeline_returns_session_info(self, timeline_service: TracingDataService):
        """Test timeline includes session information."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        assert "session" in result["data"]
        session = result["data"]["session"]
        assert session["id"] == "ses_timeline_001"
        assert "title" in session
        assert "directory" in session
        assert "started_at" in session
        assert "ended_at" in session

    def test_timeline_returns_events(self, timeline_service: TracingDataService):
        """Test timeline includes chronological events."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        assert "timeline" in result["data"]
        timeline = result["data"]["timeline"]
        assert isinstance(timeline, list)
        assert len(timeline) > 0

        for event in timeline:
            assert "timestamp" in event, f"Event {event.get('type')} missing timestamp"
            assert event["timestamp"] is not None, (
                f"Event {event.get('type')} has null timestamp"
            )
            assert "exchange_number" in event
            assert event["exchange_number"] > 0, "Exchange number must be positive"

        timestamps = [e["timestamp"] for e in timeline if e.get("timestamp")]
        if len(timestamps) > 1:
            for i in range(len(timestamps) - 1):
                assert timestamps[i] <= timestamps[i + 1], (
                    "Timeline events not chronologically sorted"
                )

    def test_timeline_events_have_type(self, timeline_service: TracingDataService):
        """Test each timeline event has a type."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        timeline = result["data"]["timeline"]
        for event in timeline:
            assert "type" in event
            assert event["type"] in [
                "user_prompt",
                "reasoning",
                "tool_call",
                "step_finish",
                "patch",
                "assistant_response",
            ]

    def test_timeline_events_have_exchange_number(
        self, timeline_service: TracingDataService
    ):
        """Test each timeline event has exchange_number."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        timeline = result["data"]["timeline"]
        for event in timeline:
            assert "exchange_number" in event
            assert isinstance(event["exchange_number"], int)

    def test_timeline_returns_summary(self, timeline_service: TracingDataService):
        """Test timeline includes summary statistics."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        assert "summary" in result["data"]
        summary = result["data"]["summary"]
        assert "total_exchanges" in summary
        assert "total_tokens" in summary
        assert "total_cost_usd" in summary
        assert "total_tool_calls" in summary
        assert "total_reasoning_entries" in summary

    def test_timeline_not_found(self, timeline_service: TracingDataService):
        """Test timeline returns error for non-existing session."""
        result = timeline_service.get_session_timeline_full("nonexistent_session")

        assert result["success"] is False
        assert "error" in result

    def test_timeline_user_prompt_content(self, timeline_service: TracingDataService):
        """Test user prompt events have full content."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        user_prompts = [
            e for e in result["data"]["timeline"] if e["type"] == "user_prompt"
        ]
        assert len(user_prompts) > 0

        for prompt in user_prompts:
            assert "content" in prompt
            assert prompt["content"] is not None, "User prompt content must not be null"
            assert len(prompt["content"]) > 0, "User prompt content must not be empty"
            assert "message_id" in prompt
            assert prompt["message_id"] is not None, (
                "User prompt message_id must not be null"
            )
            assert "timestamp" in prompt
            assert prompt["timestamp"] is not None, (
                "User prompt timestamp must not be null"
            )

    def test_timeline_reasoning_text_complete(
        self, timeline_service: TracingDataService
    ):
        """Test reasoning events have non-empty text."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        reasoning_events = [
            e for e in result["data"]["timeline"] if e["type"] == "reasoning"
        ]

        if len(reasoning_events) > 0:
            for reasoning in reasoning_events:
                assert "entries" in reasoning, "Reasoning event missing entries field"
                assert reasoning["entries"] is not None, (
                    "Reasoning entries must not be null"
                )
                assert len(reasoning["entries"]) > 0, (
                    "Reasoning entries must not be empty"
                )

                for entry in reasoning["entries"]:
                    assert "text" in entry, "Reasoning entry missing text field"
                    assert entry["text"] is not None, "Reasoning text must not be null"
                    assert len(entry["text"]) > 0, "Reasoning text must not be empty"

    def test_timeline_tool_call_has_details(self, timeline_service: TracingDataService):
        """Test tool call events have necessary details."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        tool_calls = [e for e in result["data"]["timeline"] if e["type"] == "tool_call"]
        if len(tool_calls) > 0:
            for tool in tool_calls:
                assert "tool_name" in tool, "Tool call missing tool_name"
                assert tool["tool_name"] is not None, "Tool name must not be null"
                assert len(tool["tool_name"]) > 0, "Tool name must not be empty"

                assert "status" in tool, "Tool call missing status"
                assert tool["status"] is not None, "Tool status must not be null"
                assert tool["status"] in ["completed", "failed", "pending"], (
                    f"Invalid tool status: {tool['status']}"
                )

                if "arguments" in tool and tool["arguments"]:
                    assert isinstance(tool["arguments"], dict), (
                        "Tool arguments must be dict"
                    )

                if "duration_ms" in tool and tool["duration_ms"] is not None:
                    assert tool["duration_ms"] >= 0, "Duration must be non-negative"


# =============================================================================
# Tests for get_session_exchanges
# =============================================================================


class TestGetSessionExchanges:
    """Tests for get_session_exchanges method."""

    def test_exchanges_returns_meta(self, timeline_service: TracingDataService):
        """Test exchanges endpoint returns meta information."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        assert "meta" in result
        assert result["meta"]["session_id"] == "ses_timeline_001"
        assert "count" in result["meta"]
        assert "generated_at" in result["meta"]

    def test_exchanges_returns_list(self, timeline_service: TracingDataService):
        """Test exchanges endpoint returns list of exchanges."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        assert "exchanges" in result
        assert isinstance(result["exchanges"], list)
        assert len(result["exchanges"]) > 0

    def test_exchange_has_number(self, timeline_service: TracingDataService):
        """Test each exchange has a number."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "number" in exchange
            assert isinstance(exchange["number"], int)
            assert exchange["number"] >= 1

    def test_exchange_has_user_prompt(self, timeline_service: TracingDataService):
        """Test each exchange has user prompt content."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "user_prompt" in exchange
            assert isinstance(exchange["user_prompt"], str)

    def test_exchange_has_assistant_response(
        self, timeline_service: TracingDataService
    ):
        """Test each exchange has assistant response content."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "assistant_response" in exchange
            assert isinstance(exchange["assistant_response"], str)

    def test_exchange_has_tokens(self, timeline_service: TracingDataService):
        """Test each exchange has token counts."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "tokens" in exchange
            tokens = exchange["tokens"]
            assert "input" in tokens
            assert "output" in tokens
            assert "reasoning" in tokens

    def test_exchange_has_timing(self, timeline_service: TracingDataService):
        """Test each exchange has timing information."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "started_at" in exchange
            assert "ended_at" in exchange
            assert "duration_ms" in exchange

    def test_exchange_has_tool_count(self, timeline_service: TracingDataService):
        """Test each exchange has tool_count."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "tool_count" in exchange
            assert isinstance(exchange["tool_count"], int)

    def test_exchange_has_reasoning_count(self, timeline_service: TracingDataService):
        """Test each exchange has reasoning_count."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        for exchange in result["exchanges"]:
            assert "reasoning_count" in exchange
            assert isinstance(exchange["reasoning_count"], int)

    def test_exchanges_empty_session(self, timeline_service: TracingDataService):
        """Test exchanges returns empty for session without messages."""
        result = timeline_service.get_session_exchanges("nonexistent_session")

        assert "exchanges" in result
        assert result["exchanges"] == []


# =============================================================================
# Tests for get_delegation_tree
# =============================================================================


class TestGetDelegationTree:
    """Tests for get_delegation_tree method."""

    def test_delegation_tree_returns_meta(self, timeline_service: TracingDataService):
        """Test delegation tree returns meta information."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        assert "meta" in result
        assert result["meta"]["session_id"] == "ses_parent_001"
        assert "generated_at" in result["meta"]

    def test_delegation_tree_returns_summary(
        self, timeline_service: TracingDataService
    ):
        """Test delegation tree returns summary statistics."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        assert "summary" in result
        summary = result["summary"]
        assert "total_delegations" in summary
        assert "max_depth" in summary
        assert "agents_involved" in summary

    def test_delegation_tree_returns_tree(self, timeline_service: TracingDataService):
        """Test delegation tree returns tree structure."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        assert "tree" in result
        tree = result["tree"]
        assert tree is not None
        assert "session_id" in tree
        assert "agent" in tree
        assert "children" in tree

    def test_delegation_tree_has_children(self, timeline_service: TracingDataService):
        """Test delegation tree includes children."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        tree = result["tree"]
        assert isinstance(tree["children"], list)
        assert len(tree["children"]) > 0

    def test_delegation_child_has_session_id(
        self, timeline_service: TracingDataService
    ):
        """Test child nodes have session_id."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        if len(result["tree"]["children"]) > 0:
            child = result["tree"]["children"][0]
            assert "session_id" in child
            assert child["session_id"] == "ses_child_001"

    def test_delegation_child_has_agent(self, timeline_service: TracingDataService):
        """Test child nodes have agent."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        if len(result["tree"]["children"]) > 0:
            child = result["tree"]["children"][0]
            assert "agent" in child

    def test_delegation_child_has_status(self, timeline_service: TracingDataService):
        """Test child nodes have status."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        if len(result["tree"]["children"]) > 0:
            child = result["tree"]["children"][0]
            assert "status" in child

    def test_delegation_tree_agents_involved(
        self, timeline_service: TracingDataService
    ):
        """Test agents_involved list in summary."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        agents = result["summary"]["agents_involved"]
        assert isinstance(agents, list)
        assert len(agents) > 0

    def test_delegation_tree_session_not_found(
        self, timeline_service: TracingDataService
    ):
        """Test delegation tree handles missing session."""
        result = timeline_service.get_delegation_tree("nonexistent_session")

        assert "tree" in result
        assert result["tree"] is None
        assert "error" in result["meta"]

    def test_delegation_tree_no_delegations(self, timeline_service: TracingDataService):
        """Test delegation tree for session without delegations."""
        result = timeline_service.get_delegation_tree("ses_timeline_001")

        assert "tree" in result
        if result["tree"]:
            assert result["tree"]["children"] == []


# =============================================================================
# Tests for fallback methods (when exchanges table is empty)
# =============================================================================


class TestFallbackMethods:
    """Tests for fallback timeline building from parts."""

    def test_build_timeline_from_parts(self, timeline_service: TracingDataService):
        """Test _build_timeline_from_parts returns events."""
        timeline = timeline_service._build_timeline_from_parts("ses_timeline_001")

        assert isinstance(timeline, list)
        # Should have user_prompt, reasoning, tool_call, assistant_response
        types = [e["type"] for e in timeline]
        assert "user_prompt" in types or len(timeline) == 0

    def test_calculate_timeline_stats(self, timeline_service: TracingDataService):
        """Test _calculate_timeline_stats returns stats dict."""
        stats = timeline_service._calculate_timeline_stats("ses_timeline_001")

        assert "total_tokens" in stats
        assert "total_cost" in stats
        assert "total_tool_calls" in stats
        assert "total_reasoning" in stats

    def test_build_exchanges_from_messages(self, timeline_service: TracingDataService):
        """Test _build_exchanges_from_messages returns exchange list."""
        exchanges = timeline_service._build_exchanges_from_messages("ses_timeline_001")

        assert isinstance(exchanges, list)
        if len(exchanges) > 0:
            ex = exchanges[0]
            assert "number" in ex
            assert "user_prompt" in ex
            assert "assistant_response" in ex


# =============================================================================
# Tests for response format compliance
# =============================================================================


class TestResponseFormat:
    """Tests for API response format compliance."""

    def test_timeline_response_format(self, timeline_service: TracingDataService):
        """Test timeline response matches Plan 45 spec."""
        result = timeline_service.get_session_timeline_full("ses_timeline_001")

        # Check top-level structure
        assert "success" in result
        assert "data" in result

        data = result["data"]
        assert "meta" in data
        assert "session" in data
        assert "timeline" in data
        assert "summary" in data

    def test_exchanges_response_format(self, timeline_service: TracingDataService):
        """Test exchanges response format."""
        result = timeline_service.get_session_exchanges("ses_timeline_001")

        assert "meta" in result
        assert "exchanges" in result

    def test_delegations_response_format(self, timeline_service: TracingDataService):
        """Test delegations response format."""
        result = timeline_service.get_delegation_tree("ses_parent_001")

        assert "meta" in result
        assert "summary" in result
        assert "tree" in result
