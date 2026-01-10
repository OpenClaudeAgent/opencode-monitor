"""
Tests for test data builders.

Verifies that SessionBuilder, MessageBuilder, and TraceBuilder
produce correct data structures.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from tests.builders import SessionBuilder, MessageBuilder, TraceBuilder


# =============================================================================
# SessionBuilder Tests
# =============================================================================


class TestSessionBuilder:
    """Tests for SessionBuilder."""

    def test_build_returns_dict_with_defaults(self):
        """Build returns dict with sensible defaults."""
        session = SessionBuilder().build()

        assert "id" in session
        assert session["title"] == "Test Session"
        assert session["directory"] == "/home/user/project"
        assert session["tokens_in"] == 1000
        assert session["tokens_out"] == 500
        assert "created_at" in session
        assert "updated_at" in session

    def test_with_id_sets_session_id(self):
        """with_id sets custom session ID."""
        session = SessionBuilder().with_id("sess-custom").build()
        assert session["id"] == "sess-custom"

    def test_with_title_sets_title(self):
        """with_title sets custom title."""
        session = SessionBuilder().with_title("My Session").build()
        assert session["title"] == "My Session"

    def test_with_tokens_sets_all_token_fields(self):
        """with_tokens sets all token counts."""
        session = (
            SessionBuilder()
            .with_tokens(input_tokens=2000, output_tokens=1000, cache_read=500)
            .build()
        )
        assert session["tokens_in"] == 2000
        assert session["tokens_out"] == 1000
        assert session["tokens_cache_read"] == 500

    def test_with_parent_sets_parent_id(self):
        """with_parent sets parent session ID."""
        session = SessionBuilder().with_parent("parent-001").build()
        assert session["parent_id"] == "parent-001"

    def test_as_subsession_configures_parent(self):
        """as_subsession is alias for with_parent."""
        session = SessionBuilder().as_subsession("parent-002").build()
        assert session["parent_id"] == "parent-002"

    def test_with_git_stats_sets_metrics(self):
        """with_git_stats sets git metrics."""
        session = (
            SessionBuilder()
            .with_git_stats(additions=100, deletions=50, files_changed=10)
            .build()
        )
        assert session["additions"] == 100
        assert session["deletions"] == 50
        assert session["files_changed"] == 10

    def test_build_json_returns_opencode_format(self):
        """build_json returns OpenCode storage format."""
        builder = SessionBuilder().with_id("sess-001").with_title("Test")
        json_data = builder.build_json()

        assert json_data["id"] == "sess-001"
        assert json_data["projectID"] is not None
        assert json_data["title"] == "Test"
        assert "time" in json_data
        assert "created" in json_data["time"]
        assert "updated" in json_data["time"]
        # Timestamps should be integers (milliseconds)
        assert isinstance(json_data["time"]["created"], int)

    def test_write_file_creates_json_file(self, tmp_path: Path):
        """write_file creates session JSON in correct location."""
        builder = SessionBuilder().with_id("sess-test")
        file_path = builder.write_file(tmp_path)

        assert file_path.exists()
        assert file_path.name == "sess-test.json"
        assert "session" in str(file_path.parent)  # session/{project_hash}/

        # Verify content
        content = json.loads(file_path.read_text())
        assert content["id"] == "sess-test"

    def test_id_property_returns_session_id(self):
        """id property returns the session ID."""
        builder = SessionBuilder().with_id("sess-prop")
        assert builder.id == "sess-prop"

    def test_fluent_chaining(self):
        """All methods can be chained fluently."""
        session = (
            SessionBuilder()
            .with_id("sess-chain")
            .with_title("Chained Session")
            .with_directory("/project")
            .with_tokens(500, 250)
            .with_git_stats(10, 5, 2)
            .build()
        )

        assert session["id"] == "sess-chain"
        assert session["title"] == "Chained Session"
        assert session["directory"] == "/project"
        assert session["tokens_in"] == 500


# =============================================================================
# MessageBuilder Tests
# =============================================================================


class TestMessageBuilder:
    """Tests for MessageBuilder."""

    def test_build_returns_dict_with_defaults(self):
        """Build returns dict with sensible defaults."""
        message = MessageBuilder().build()

        assert "id" in message
        assert "session_id" in message
        assert message["role"] == "assistant"
        assert message["agent"] == "main"
        assert message["model_id"] == "claude-sonnet"
        assert message["tokens_input"] == 100
        assert message["tokens_output"] == 50

    def test_with_id_sets_message_id(self):
        """with_id sets custom message ID."""
        message = MessageBuilder().with_id("msg-custom").build()
        assert message["id"] == "msg-custom"

    def test_for_session_sets_session_id(self):
        """for_session sets the parent session ID."""
        message = MessageBuilder().for_session("sess-001").build()
        assert message["session_id"] == "sess-001"

    def test_with_agent_sets_agent_type(self):
        """with_agent sets agent type."""
        message = MessageBuilder().with_agent("executor").build()
        assert message["agent"] == "executor"

    def test_with_tokens_sets_all_token_fields(self):
        """with_tokens sets all token counts."""
        message = (
            MessageBuilder()
            .with_tokens(
                input_tokens=200,
                output_tokens=100,
                reasoning_tokens=50,
                cache_read=25,
            )
            .build()
        )
        assert message["tokens_input"] == 200
        assert message["tokens_output"] == 100
        assert message["tokens_reasoning"] == 50
        assert message["tokens_cache_read"] == 25

    def test_as_user_configures_user_message(self):
        """as_user sets role to user."""
        message = MessageBuilder().as_user().build()
        assert message["role"] == "user"

    def test_as_assistant_configures_assistant_message(self):
        """as_assistant sets role and agent."""
        message = MessageBuilder().as_assistant("tester").build()
        assert message["role"] == "assistant"
        assert message["agent"] == "tester"

    def test_build_json_returns_opencode_format(self):
        """build_json returns OpenCode storage format."""
        builder = MessageBuilder().with_id("msg-001").for_session("sess-001")
        json_data = builder.build_json()

        assert json_data["id"] == "msg-001"
        assert json_data["sessionID"] == "sess-001"
        assert "tokens" in json_data
        assert "input" in json_data["tokens"]
        assert "time" in json_data
        # Timestamps should be integers (milliseconds)
        assert isinstance(json_data["time"]["created"], int)

    def test_write_file_creates_json_file(self, tmp_path: Path):
        """write_file creates message JSON in correct location."""
        builder = MessageBuilder().with_id("msg-test").for_session("sess-001")
        file_path = builder.write_file(tmp_path)

        assert file_path.exists()
        assert file_path.name == "msg-test.json"
        assert "sess-001" in str(file_path.parent)

    def test_id_and_session_id_properties(self):
        """id and session_id properties return correct values."""
        builder = MessageBuilder().with_id("msg-prop").for_session("sess-prop")
        assert builder.id == "msg-prop"
        assert builder.session_id == "sess-prop"


# =============================================================================
# TraceBuilder Tests
# =============================================================================


class TestTraceBuilder:
    """Tests for TraceBuilder."""

    def test_with_root_sets_session_info(self):
        """with_root sets root session information."""
        builder = TraceBuilder().with_root("sess-001", "Main Session", "/project")
        assert builder.root_session_id == "sess-001"

    def test_add_delegation_creates_trace(self):
        """add_delegation creates a trace under root."""
        tree = (
            TraceBuilder()
            .with_root("sess-001", "Main")
            .add_delegation("trace-001", "executor")
            .build()
        )

        assert len(tree["traces"]) == 1
        trace = tree["traces"][0]
        assert trace["trace_id"] == "trace-001"
        assert trace["session_id"] == "sess-001"
        assert trace["parent_trace_id"] == "root_sess-001"
        assert trace["subagent_type"] == "executor"

    def test_add_child_delegation_creates_nested_trace(self):
        """add_child_delegation creates nested trace."""
        tree = (
            TraceBuilder()
            .with_root("sess-001", "Main")
            .add_delegation("trace-001", "executor")
            .add_child_delegation("trace-001", "trace-002", "subtask")
            .build()
        )

        assert len(tree["traces"]) == 2
        child = tree["traces"][1]
        assert child["trace_id"] == "trace-002"
        assert child["parent_trace_id"] == "trace-001"
        assert child["parent_agent"] == "executor"

    def test_add_message_creates_message(self):
        """add_message creates a message for a trace."""
        tree = (
            TraceBuilder()
            .with_root("sess-001", "Main")
            .add_delegation("trace-001", "executor")
            .add_message("trace-001", "msg-001")
            .build()
        )

        assert len(tree["messages"]) == 1
        msg = tree["messages"][0]
        assert msg["id"] == "msg-001"
        assert msg["agent"] == "executor"

    def test_build_returns_complete_tree(self):
        """build returns session, traces, and messages."""
        tree = (
            TraceBuilder()
            .with_root("sess-001", "Main Session")
            .add_delegation("trace-001", "executor")
            .build()
        )

        assert "session" in tree
        assert tree["session"]["id"] == "sess-001"
        assert tree["session"]["title"] == "Main Session"
        assert "traces" in tree
        assert "messages" in tree

    def test_build_flat_traces_returns_list(self):
        """build_flat_traces returns just traces as list."""
        traces = (
            TraceBuilder()
            .with_root("sess-001", "Main")
            .add_delegation("trace-001", "executor")
            .add_delegation("trace-002", "tester")
            .build_flat_traces()
        )

        assert len(traces) == 2
        assert traces[0]["trace_id"] == "trace-001"
        assert traces[1]["trace_id"] == "trace-002"

    def test_trace_count_and_message_count_properties(self):
        """Properties return correct counts."""
        builder = (
            TraceBuilder()
            .with_root("sess-001", "Main")
            .add_delegation("trace-001", "executor")
            .add_delegation("trace-002", "tester")
            .add_message("trace-001", "msg-001")
        )

        assert builder.trace_count == 2
        assert builder.message_count == 1

    def test_add_delegation_without_root_raises_error(self):
        """add_delegation raises error if root not set."""
        with pytest.raises(ValueError, match="with_root"):
            TraceBuilder().add_delegation("trace-001", "executor")

    def test_complex_tree_structure(self):
        """Build a complex tree with multiple levels."""
        tree = (
            TraceBuilder()
            .with_root("sess-001", "Complex Session")
            .add_delegation("trace-001", "coordinator", tokens_in=1000, tokens_out=500)
            .add_child_delegation("trace-001", "trace-002", "executor")
            .add_child_delegation("trace-001", "trace-003", "tester")
            .add_child_delegation("trace-002", "trace-004", "subtask")
            .add_message("trace-002", "msg-001", tokens_in=200, tokens_out=100)
            .build()
        )

        assert len(tree["traces"]) == 4
        assert len(tree["messages"]) == 1

        # Verify hierarchy
        trace_map = {t["trace_id"]: t for t in tree["traces"]}
        assert trace_map["trace-001"]["parent_trace_id"] == "root_sess-001"
        assert trace_map["trace-002"]["parent_trace_id"] == "trace-001"
        assert trace_map["trace-004"]["parent_trace_id"] == "trace-002"


# =============================================================================
# Integration Tests
# =============================================================================


class TestBuilderIntegration:
    """Tests for builder integration patterns."""

    def test_session_with_messages(self, tmp_path: Path):
        """Create session and message files together."""
        # Create session
        session_builder = SessionBuilder().with_id("sess-int").with_title("Integration")
        session_builder.write_file(tmp_path)

        # Create messages
        msg1 = MessageBuilder().with_id("msg-001").for_session("sess-int").as_user()
        msg1.write_file(tmp_path)

        msg2 = (
            MessageBuilder()
            .with_id("msg-002")
            .for_session("sess-int")
            .as_assistant("executor")
        )
        msg2.write_file(tmp_path)

        # Verify files exist (using OpenCode singular folder names)
        assert (tmp_path / "session" / "default" / "sess-int.json").exists()
        assert (tmp_path / "message" / "sess-int" / "msg-001.json").exists()
        assert (tmp_path / "message" / "sess-int" / "msg-002.json").exists()

    def test_trace_tree_with_token_totals(self):
        """TraceBuilder calculates token totals correctly."""
        tree = (
            TraceBuilder()
            .with_root("sess-001", "Token Test")
            .add_delegation("trace-001", "executor", tokens_in=500, tokens_out=250)
            .add_delegation("trace-002", "tester", tokens_in=300, tokens_out=150)
            .build()
        )

        total_in = sum(t["tokens_in"] for t in tree["traces"])
        total_out = sum(t["tokens_out"] for t in tree["traces"])

        assert total_in == 800
        assert total_out == 400
