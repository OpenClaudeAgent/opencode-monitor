"""
Tests for trace builder token aggregation.

These tests verify that:
1. Tokens are correctly aggregated from child session messages
2. create_trace_from_delegation updates tokens immediately
3. backfill_missing_tokens fixes traces created before messages

This is a regression test for the bug where subagent traces had
tokens: None because messages were indexed before the trace was created.
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.trace_builder.builder import TraceBuilder
from opencode_monitor.analytics.indexer.parsers import ParsedDelegation, ParsedPart


# === Fixtures ===


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=True) as f:
        db_path = Path(f.name)

    db = AnalyticsDB(db_path=db_path)
    db.connect()
    yield db
    db.close()

    try:
        db_path.unlink()
    except Exception:
        pass


@pytest.fixture
def trace_builder(temp_db):
    """Create a TraceBuilder instance."""
    return TraceBuilder(temp_db)


def create_test_messages(db, session_id: str, count: int = 3):
    """Create test messages in the database."""
    conn = db.connect()
    base_time = datetime.now() - timedelta(minutes=10)

    for i in range(count):
        msg_time = base_time + timedelta(seconds=i * 10)
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, tokens_input, tokens_output, created_at)
            VALUES (?, ?, 'assistant', ?, ?, ?)
            """,
            [
                f"msg_{session_id}_{i}",
                session_id,
                100 + i * 10,  # tokens_input: 100, 110, 120...
                500 + i * 50,  # tokens_output: 500, 550, 600...
                msg_time,
            ],
        )


# === Tests for update_trace_tokens ===


class TestUpdateTraceTokens:
    """Tests for update_trace_tokens method."""

    def test_updates_tokens_from_child_session(self, temp_db, trace_builder):
        """Verify tokens are aggregated from child session messages."""
        child_session_id = "ses_child_123"

        # Create messages in child session
        create_test_messages(temp_db, child_session_id, count=3)
        # Expected: input = 100 + 110 + 120 = 330, output = 500 + 550 + 600 = 1650

        # Create a trace with this child_session_id (no tokens yet)
        conn = temp_db.connect()
        conn.execute(
            """
            INSERT INTO agent_traces 
            (trace_id, session_id, subagent_type, prompt_input, started_at, child_session_id)
            VALUES ('trace_1', 'ses_parent', 'explore', 'test prompt', ?, ?)
            """,
            [datetime.now(), child_session_id],
        )

        # Call update_trace_tokens
        trace_builder.update_trace_tokens(child_session_id)

        # Verify tokens were updated
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'trace_1'"
        ).fetchone()

        assert result[0] == 330, f"Expected tokens_in=330, got {result[0]}"
        assert result[1] == 1650, f"Expected tokens_out=1650, got {result[1]}"

    def test_no_update_when_no_messages(self, temp_db, trace_builder):
        """Verify no update when child session has no messages."""
        child_session_id = "ses_empty"

        # Create trace without messages in child session
        conn = temp_db.connect()
        conn.execute(
            """
            INSERT INTO agent_traces 
            (trace_id, session_id, subagent_type, prompt_input, started_at, child_session_id)
            VALUES ('trace_2', 'ses_parent', 'explore', 'test', ?, ?)
            """,
            [datetime.now(), child_session_id],
        )

        # Call update_trace_tokens
        trace_builder.update_trace_tokens(child_session_id)

        # Verify tokens remain NULL
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'trace_2'"
        ).fetchone()

        assert result[0] is None, "tokens_in should remain NULL"
        assert result[1] is None, "tokens_out should remain NULL"


# === Tests for create_trace_from_delegation with token update ===


class TestCreateTraceUpdatesTokens:
    """Tests for token update during trace creation."""

    def test_creates_trace_and_updates_tokens(self, temp_db, trace_builder):
        """Verify trace creation updates tokens from existing child messages."""
        child_session_id = "ses_child_new"
        parent_session_id = "ses_parent_new"

        # First, create messages in the child session (simulating they arrived first)
        create_test_messages(temp_db, child_session_id, count=2)
        # Expected: input = 100 + 110 = 210, output = 500 + 550 = 1050

        # Now create delegation and part
        delegation = ParsedDelegation(
            id="prt_test_123",
            session_id=parent_session_id,
            message_id="msg_test",
            parent_agent="user",
            child_session_id=child_session_id,
            child_agent="explore",
            created_at=datetime.now() - timedelta(minutes=5),
        )

        part = ParsedPart(
            id="prt_test_123",
            message_id="msg_test",
            session_id=parent_session_id,
            part_type="tool_use",
            content=None,
            tool_name="task",
            tool_status="completed",
            call_id="call_123",
            arguments='{"prompt": "test"}',
            created_at=datetime.now() - timedelta(minutes=5),
            ended_at=datetime.now(),
            duration_ms=300000,
            error_message=None,
        )

        # Create trace (should update tokens immediately)
        trace_id = trace_builder.create_trace_from_delegation(delegation, part)

        # Verify trace was created with tokens
        conn = temp_db.connect()
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = ?",
            [trace_id],
        ).fetchone()

        assert result is not None, "Trace should be created"
        assert result[0] == 210, f"Expected tokens_in=210, got {result[0]}"
        assert result[1] == 1050, f"Expected tokens_out=1050, got {result[1]}"


# === Tests for backfill_missing_tokens ===


class TestBackfillMissingTokens:
    """Tests for backfill_missing_tokens method."""

    def test_backfills_traces_with_missing_tokens(self, temp_db, trace_builder):
        """Verify backfill updates all traces with missing tokens."""
        # Create 3 traces with child sessions but no tokens
        conn = temp_db.connect()
        for i in range(3):
            child_id = f"ses_child_{i}"
            # Create messages first
            create_test_messages(temp_db, child_id, count=2)

            # Create trace with NULL tokens
            conn.execute(
                """
                INSERT INTO agent_traces 
                (trace_id, session_id, subagent_type, prompt_input, started_at, 
                 child_session_id, tokens_in, tokens_out)
                VALUES (?, 'ses_parent', 'explore', 'test', ?, ?, NULL, NULL)
                """,
                [f"trace_{i}", datetime.now(), child_id],
            )

        # Run backfill
        updated = trace_builder.backfill_missing_tokens()

        assert updated == 3, f"Expected 3 traces updated, got {updated}"

        # Verify all traces have tokens now
        results = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces ORDER BY trace_id"
        ).fetchall()

        for i, (tokens_in, tokens_out) in enumerate(results):
            assert tokens_in == 210, (
                f"Trace {i}: expected tokens_in=210, got {tokens_in}"
            )
            assert tokens_out == 1050, (
                f"Trace {i}: expected tokens_out=1050, got {tokens_out}"
            )

    def test_skips_traces_with_existing_tokens(self, temp_db, trace_builder):
        """Verify backfill skips traces that already have tokens."""
        conn = temp_db.connect()
        child_id = "ses_child_existing"

        # Create messages
        create_test_messages(temp_db, child_id, count=2)

        # Create trace WITH existing tokens
        conn.execute(
            """
            INSERT INTO agent_traces 
            (trace_id, session_id, subagent_type, prompt_input, started_at, 
             child_session_id, tokens_in, tokens_out)
            VALUES ('trace_existing', 'ses_parent', 'explore', 'test', ?, ?, 999, 888)
            """,
            [datetime.now(), child_id],
        )

        # Run backfill
        updated = trace_builder.backfill_missing_tokens()

        assert updated == 0, "Should not update traces with existing tokens"

        # Verify tokens unchanged
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'trace_existing'"
        ).fetchone()

        assert result[0] == 999, "tokens_in should be unchanged"
        assert result[1] == 888, "tokens_out should be unchanged"

    def test_handles_traces_without_messages(self, temp_db, trace_builder):
        """Verify backfill handles traces whose child sessions have no messages."""
        conn = temp_db.connect()

        # Create trace with child session that has no messages
        conn.execute(
            """
            INSERT INTO agent_traces 
            (trace_id, session_id, subagent_type, prompt_input, started_at, 
             child_session_id, tokens_in, tokens_out)
            VALUES ('trace_no_msgs', 'ses_parent', 'explore', 'test', ?, 'ses_empty', NULL, NULL)
            """,
            [datetime.now()],
        )

        # Run backfill
        updated = trace_builder.backfill_missing_tokens()

        assert updated == 0, "Should not update traces without messages"

        # Verify tokens still NULL
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'trace_no_msgs'"
        ).fetchone()

        assert result[0] is None, "tokens_in should remain NULL"
        assert result[1] is None, "tokens_out should remain NULL"


# === Integration test: Full flow ===


class TestTokenAggregationFlow:
    """Integration tests for the complete token aggregation flow."""

    def test_messages_before_trace_scenario(self, temp_db, trace_builder):
        """Test the exact bug scenario: messages indexed before trace exists.

        This simulates the race condition where:
        1. Child session messages are indexed
        2. update_trace_tokens is called (but trace doesn't exist yet)
        3. Trace is created later
        4. backfill_missing_tokens should fix it
        """
        child_session_id = "ses_race_condition"
        parent_session_id = "ses_parent_race"

        # Step 1: Messages arrive and are indexed
        create_test_messages(temp_db, child_session_id, count=5)
        # Expected: input = 100+110+120+130+140 = 600
        # Expected: output = 500+550+600+650+700 = 3000

        # Step 2: update_trace_tokens called (trace doesn't exist - no effect)
        trace_builder.update_trace_tokens(child_session_id)

        # Step 3: Trace created later (without tokens because call already happened)
        conn = temp_db.connect()
        conn.execute(
            """
            INSERT INTO agent_traces 
            (trace_id, session_id, subagent_type, prompt_input, started_at, 
             child_session_id, tokens_in, tokens_out)
            VALUES ('trace_race', ?, 'explore', 'test', ?, ?, NULL, NULL)
            """,
            [parent_session_id, datetime.now(), child_session_id],
        )

        # Verify tokens are NULL (bug state)
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'trace_race'"
        ).fetchone()
        assert result[0] is None, "Bug: tokens should be NULL at this point"

        # Step 4: backfill_missing_tokens fixes the issue
        updated = trace_builder.backfill_missing_tokens()

        assert updated == 1, "Should fix 1 trace"

        # Verify tokens are now correct
        result = conn.execute(
            "SELECT tokens_in, tokens_out FROM agent_traces WHERE trace_id = 'trace_race'"
        ).fetchone()

        assert result[0] == 600, f"Expected tokens_in=600, got {result[0]}"
        assert result[1] == 3000, f"Expected tokens_out=3000, got {result[1]}"
