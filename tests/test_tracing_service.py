"""
Tests for TracingDataService.

Covers:
- get_session_summary()
- get_session_tokens()
- get_session_tools()
- get_session_files()
- get_session_timeline()
- get_session_agents()
- get_global_stats()
- get_comparison()
- update_session_stats()
- update_daily_stats()
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.tracing_service import (
    TracingDataService,
    TracingConfig,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def db(tmp_path: Path) -> AnalyticsDB:
    """Create a fresh DuckDB database for each test."""
    db_path = tmp_path / "test_tracing_service.duckdb"
    db = AnalyticsDB(db_path)
    db.connect()
    return db


@pytest.fixture
def service(db: AnalyticsDB) -> TracingDataService:
    """Create a TracingDataService instance."""
    return TracingDataService(db=db)


@pytest.fixture
def populated_db(db: AnalyticsDB) -> AnalyticsDB:
    """Populate database with test data."""
    conn = db.connect()

    # Insert test session
    conn.execute(
        """INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "ses_001",
            "proj_001",
            "/projects/test",
            "Test Session",
            datetime(2026, 1, 1, 10, 0, 0),
            datetime(2026, 1, 1, 10, 30, 0),
        ],
    )

    # Insert test messages
    messages = [
        (
            "msg_001",
            "ses_001",
            None,
            "user",
            "user",
            "claude-3",
            "anthropic",
            100,
            50,
            0,
            20,
            0,
            datetime(2026, 1, 1, 10, 0, 0),
            datetime(2026, 1, 1, 10, 0, 5),
        ),
        (
            "msg_002",
            "ses_001",
            "msg_001",
            "assistant",
            "executor",
            "claude-3",
            "anthropic",
            200,
            150,
            10,
            50,
            30,
            datetime(2026, 1, 1, 10, 0, 5),
            datetime(2026, 1, 1, 10, 5, 0),
        ),
        (
            "msg_003",
            "ses_001",
            "msg_002",
            "user",
            "user",
            "claude-3",
            "anthropic",
            80,
            40,
            0,
            10,
            0,
            datetime(2026, 1, 1, 10, 5, 0),
            datetime(2026, 1, 1, 10, 5, 5),
        ),
    ]

    for msg in messages:
        conn.execute(
            """INSERT INTO messages 
               (id, session_id, parent_id, role, agent, model_id, provider_id,
                tokens_input, tokens_output, tokens_reasoning,
                tokens_cache_read, tokens_cache_write, created_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            list(msg),
        )

    # Insert test parts (tool calls)
    parts = [
        (
            "prt_001",
            "msg_002",
            "tool",
            "read",
            "completed",
            datetime(2026, 1, 1, 10, 1, 0),
            "ses_001",
            None,
            datetime(2026, 1, 1, 10, 1, 2),
            2000,
        ),
        (
            "prt_002",
            "msg_002",
            "tool",
            "write",
            "completed",
            datetime(2026, 1, 1, 10, 2, 0),
            "ses_001",
            None,
            datetime(2026, 1, 1, 10, 2, 5),
            5000,
        ),
        (
            "prt_003",
            "msg_002",
            "tool",
            "bash",
            "error",
            datetime(2026, 1, 1, 10, 3, 0),
            "ses_001",
            None,
            datetime(2026, 1, 1, 10, 3, 1),
            1000,
        ),
    ]

    for prt in parts:
        conn.execute(
            """INSERT INTO parts 
               (id, message_id, part_type, tool_name, tool_status, created_at,
                session_id, call_id, ended_at, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            list(prt),
        )

    # Insert test traces
    conn.execute(
        """INSERT INTO agent_traces 
           (trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
            prompt_input, prompt_output, started_at, ended_at, duration_ms,
            tokens_in, tokens_out, status, tools_used, child_session_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "trace_001",
            "ses_001",
            None,
            "user",
            "executor",
            "Implement feature X",
            "Feature implemented",
            datetime(2026, 1, 1, 10, 0, 0),
            datetime(2026, 1, 1, 10, 30, 0),
            1800000,
            500,
            300,
            "completed",
            ["read", "write", "bash"],
            None,
        ],
    )

    return db


# =============================================================================
# Test get_session_summary
# =============================================================================


class TestGetSessionSummary:
    """Tests for get_session_summary method."""

    def test_returns_empty_for_nonexistent_session(self, service: TracingDataService):
        """Should return empty response for non-existent session."""
        result = service.get_session_summary("nonexistent")

        assert result["meta"]["error"] == "Session not found"
        assert result["summary"] == {}

    def test_returns_complete_summary(self, db: AnalyticsDB, populated_db: AnalyticsDB):
        """Should return complete session summary with all KPIs."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_summary("ses_001")

        # Check meta
        assert result["meta"]["session_id"] == "ses_001"
        assert result["meta"]["title"] == "Test Session"
        assert "generated_at" in result["meta"]

        # Check summary
        summary = result["summary"]
        assert summary["total_tokens"] > 0
        assert summary["total_tool_calls"] == 3
        assert summary["unique_agents"] > 0
        assert "estimated_cost_usd" in summary
        assert "duration_ms" in summary

        # Check details sections exist
        assert "tokens" in result["details"]
        assert "tools" in result["details"]
        assert "files" in result["details"]
        assert "agents" in result["details"]

        # Check charts sections exist
        assert "tokens_by_type" in result["charts"]
        assert "tools_by_name" in result["charts"]

    def test_calculates_token_metrics(self, db: AnalyticsDB, populated_db: AnalyticsDB):
        """Should correctly calculate token metrics."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_summary("ses_001")

        tokens = result["details"]["tokens"]
        # 100 + 200 + 80 = 380 input
        assert tokens["input"] == 380
        # 50 + 150 + 40 = 240 output
        assert tokens["output"] == 240
        # 20 + 50 + 10 = 80 cache_read
        assert tokens["cache_read"] == 80
        # Total = input + output = 620
        assert tokens["total"] == 620

    def test_calculates_tool_metrics(self, db: AnalyticsDB, populated_db: AnalyticsDB):
        """Should correctly calculate tool metrics."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_summary("ses_001")

        tools = result["details"]["tools"]
        assert tools["total_calls"] == 3
        assert tools["unique_tools"] == 3
        assert tools["success_count"] == 2
        assert tools["error_count"] == 1
        # 2/3 success rate
        assert tools["success_rate"] == pytest.approx(66.7, abs=0.1)


# =============================================================================
# Test get_session_tokens
# =============================================================================


class TestGetSessionTokens:
    """Tests for get_session_tokens method."""

    def test_returns_token_details(self, db: AnalyticsDB, populated_db: AnalyticsDB):
        """Should return detailed token breakdown."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_tokens("ses_001")

        assert result["meta"]["session_id"] == "ses_001"
        assert result["summary"]["total"] == 620
        assert result["summary"]["input"] == 380
        assert result["summary"]["output"] == 240
        assert "cache_hit_ratio" in result["summary"]


# =============================================================================
# Test get_session_tools
# =============================================================================


class TestGetSessionTools:
    """Tests for get_session_tools method."""

    def test_returns_tool_details(self, db: AnalyticsDB, populated_db: AnalyticsDB):
        """Should return detailed tool breakdown."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_tools("ses_001")

        assert result["meta"]["session_id"] == "ses_001"
        assert result["summary"]["total_calls"] == 3
        assert result["summary"]["unique_tools"] == 3
        assert "success_rate" in result["summary"]
        assert "avg_duration_ms" in result["summary"]


# =============================================================================
# Test get_session_files
# =============================================================================


class TestGetSessionFiles:
    """Tests for get_session_files method."""

    def test_returns_file_details(self, db: AnalyticsDB, populated_db: AnalyticsDB):
        """Should return file operation details."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_files("ses_001")

        assert result["meta"]["session_id"] == "ses_001"
        # From parts table - 1 read, 1 write, 0 edit
        assert result["summary"]["total_reads"] == 1
        assert result["summary"]["total_writes"] == 1


# =============================================================================
# Test get_session_timeline
# =============================================================================


class TestGetSessionTimeline:
    """Tests for get_session_timeline method."""

    def test_returns_chronological_events(
        self, db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should return events sorted chronologically."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_timeline("ses_001")

        assert len(result) > 0
        # Check all events have required fields
        for event in result:
            assert "type" in event
            assert "id" in event
            assert "timestamp" in event

    def test_returns_empty_for_nonexistent_session(self, service: TracingDataService):
        """Should return empty list for non-existent session."""
        result = service.get_session_timeline("nonexistent")
        assert result == []


# =============================================================================
# Test get_session_agents
# =============================================================================


class TestGetSessionAgents:
    """Tests for get_session_agents method."""

    def test_returns_agent_list(self, db: AnalyticsDB, populated_db: AnalyticsDB):
        """Should return list of agents involved in session."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_agents("ses_001")

        assert len(result) > 0
        for agent in result:
            assert "agent" in agent
            assert "message_count" in agent


# =============================================================================
# Test get_session_prompts
# =============================================================================


class TestGetSessionPrompts:
    """Tests for get_session_prompts method."""

    def test_returns_prompt_data(self, db: AnalyticsDB, populated_db: AnalyticsDB):
        """Should return user prompt and output."""
        service = TracingDataService(db=populated_db)
        result = service.get_session_prompts("ses_001")

        assert result["meta"]["session_id"] == "ses_001"
        assert "prompt_input" in result
        assert "prompt_output" in result

    def test_returns_none_for_nonexistent_session(self, service: TracingDataService):
        """Should return None values for non-existent session."""
        result = service.get_session_prompts("nonexistent")

        assert result["meta"]["session_id"] == "nonexistent"
        assert result["prompt_input"] is None
        assert result["prompt_output"] is None


# =============================================================================
# Test get_global_stats
# =============================================================================


class TestGetGlobalStats:
    """Tests for get_global_stats method."""

    def test_returns_global_statistics(
        self, db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should return aggregated global statistics."""
        service = TracingDataService(db=populated_db)
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 2)

        result = service.get_global_stats(start, end)

        assert "meta" in result
        assert "summary" in result
        assert result["summary"]["total_sessions"] == 1
        assert result["summary"]["total_messages"] == 3
        assert result["summary"]["total_tokens"] > 0

    def test_uses_default_date_range(self, service: TracingDataService):
        """Should use last 30 days as default range."""
        result = service.get_global_stats()

        assert "period" in result["meta"]
        # Period should span 30 days
        period = result["meta"]["period"]
        assert period["start"] is not None
        assert period["end"] is not None


# =============================================================================
# Test get_comparison
# =============================================================================


class TestGetComparison:
    """Tests for get_comparison method."""

    def test_compares_multiple_sessions(
        self, db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should compare metrics across sessions."""
        service = TracingDataService(db=populated_db)

        # Add another session for comparison
        conn = populated_db.connect()
        conn.execute(
            """INSERT INTO sessions (id, title, created_at)
               VALUES (?, ?, ?)""",
            ["ses_002", "Another Session", datetime(2026, 1, 2, 10, 0, 0)],
        )

        result = service.get_comparison(["ses_001", "ses_002"])

        assert result["meta"]["sessions_compared"] == 2
        assert len(result["comparisons"]) == 2


# =============================================================================
# Test update_session_stats
# =============================================================================


class TestUpdateSessionStats:
    """Tests for update_session_stats method."""

    def test_updates_session_stats_table(
        self, db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should update session_stats aggregation table."""
        service = TracingDataService(db=populated_db)
        service.update_session_stats("ses_001")

        conn = populated_db.connect()
        result = conn.execute(
            "SELECT total_messages, total_tokens_in FROM session_stats WHERE session_id = ?",
            ["ses_001"],
        ).fetchone()

        assert result is not None
        assert result[0] == 3  # 3 messages
        assert result[1] == 380  # total input tokens


# =============================================================================
# Test update_daily_stats
# =============================================================================


class TestUpdateDailyStats:
    """Tests for update_daily_stats method."""

    def test_updates_daily_stats_table(
        self, db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Should update daily_stats aggregation table."""
        service = TracingDataService(db=populated_db)
        test_date = datetime(2026, 1, 1)
        service.update_daily_stats(test_date)

        conn = populated_db.connect()
        result = conn.execute(
            "SELECT total_sessions FROM daily_stats WHERE date = ?",
            ["2026-01-01"],
        ).fetchone()

        assert result is not None
        assert result[0] >= 1


# =============================================================================
# Test TracingConfig
# =============================================================================


class TestTracingConfig:
    """Tests for TracingConfig dataclass."""

    def test_default_values(self):
        """Should have sensible default values."""
        config = TracingConfig()

        assert config.cost_per_1k_input == 0.003
        assert config.cost_per_1k_output == 0.015
        assert config.cost_per_1k_cache == 0.0003

    def test_custom_values(self):
        """Should accept custom pricing."""
        config = TracingConfig(
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.03,
            cost_per_1k_cache=0.001,
        )

        assert config.cost_per_1k_input == 0.01
        assert config.cost_per_1k_output == 0.03
        assert config.cost_per_1k_cache == 0.001

    def test_service_uses_custom_config(
        self, db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Service should use custom config for calculations."""
        custom_config = TracingConfig(
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.05,
        )
        service = TracingDataService(db=populated_db, config=custom_config)

        result = service.get_session_summary("ses_001")

        # Cost should be higher with custom pricing
        assert result["summary"]["estimated_cost_usd"] > 0


# =============================================================================
# Test Response Format
# =============================================================================


class TestPerformance:
    """Tests for performance requirements."""

    def test_get_session_summary_under_100ms(
        self, db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """get_session_summary should complete in under 100ms."""
        import time

        service = TracingDataService(db=populated_db)

        # Warm up
        service.get_session_summary("ses_001")

        # Measure
        start = time.perf_counter()
        for _ in range(10):
            service.get_session_summary("ses_001")
        elapsed = (time.perf_counter() - start) * 1000 / 10  # Average ms

        assert elapsed < 100, (
            f"get_session_summary took {elapsed:.1f}ms (target: <100ms)"
        )

    def test_get_global_stats_under_100ms(
        self, db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """get_global_stats should complete in under 100ms."""
        import time
        from datetime import datetime

        service = TracingDataService(db=populated_db)
        start_date = datetime(2026, 1, 1)
        end_date = datetime(2026, 1, 2)

        # Warm up
        service.get_global_stats(start_date, end_date)

        # Measure
        start = time.perf_counter()
        for _ in range(10):
            service.get_global_stats(start_date, end_date)
        elapsed = (time.perf_counter() - start) * 1000 / 10  # Average ms

        assert elapsed < 100, f"get_global_stats took {elapsed:.1f}ms (target: <100ms)"


class TestResponseFormat:
    """Tests for standardized response format."""

    def test_all_responses_have_meta(self, db: AnalyticsDB, populated_db: AnalyticsDB):
        """All responses should have meta section."""
        service = TracingDataService(db=populated_db)

        responses = [
            service.get_session_summary("ses_001"),
            service.get_session_tokens("ses_001"),
            service.get_session_tools("ses_001"),
            service.get_session_files("ses_001"),
            service.get_global_stats(),
        ]

        for response in responses:
            assert "meta" in response
            assert "generated_at" in response["meta"]

    def test_summary_and_details_structure(
        self, db: AnalyticsDB, populated_db: AnalyticsDB
    ):
        """Responses should have summary and details sections."""
        service = TracingDataService(db=populated_db)

        result = service.get_session_summary("ses_001")

        # Summary should have quick access metrics
        assert isinstance(result["summary"], dict)
        assert "duration_ms" in result["summary"]
        assert "total_tokens" in result["summary"]

        # Details should have full breakdown
        assert isinstance(result["details"], dict)
        assert "tokens" in result["details"]
        assert "tools" in result["details"]
