"""
Tests for AnalyticsQueries - Date filtering and query coverage tests.

These tests verify that:
1. Tool and skill statistics respect date filtering
2. All query modules have adequate test coverage

Bug context: tools and skills queries were not filtering by date, causing
data from several days ago to appear when selecting "24h" period.
"""

import uuid
from datetime import datetime, timedelta

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.queries import AnalyticsQueries
from opencode_monitor.analytics.queries.agent_queries import AgentQueries
from opencode_monitor.analytics.queries.base import BaseQueries
from opencode_monitor.analytics.queries.delegation_queries import DelegationQueries
from opencode_monitor.analytics.queries.dimension_queries import DimensionQueries
from opencode_monitor.analytics.queries.enriched_queries import EnrichedQueries
from opencode_monitor.analytics.queries.session_queries import SessionQueries
from opencode_monitor.analytics.queries.time_series_queries import TimeSeriesQueries
from opencode_monitor.analytics.queries.tool_queries import ToolQueries


@pytest.fixture
def analytics_db(tmp_path):
    """Create an in-memory analytics database for testing."""
    db_path = tmp_path / "test_analytics.duckdb"
    db = AnalyticsDB(db_path=db_path)
    db.connect()  # Initialize schema
    yield db
    db.close()


@pytest.fixture
def queries(analytics_db):
    """Create AnalyticsQueries instance with test database."""
    return AnalyticsQueries(analytics_db)


def generate_id():
    """Generate a unique ID for test data."""
    return str(uuid.uuid4())


def insert_test_session(db: AnalyticsDB, session_id: str, created_at: datetime):
    """Insert a test session."""
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO sessions (id, directory, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [session_id, "/test/dir", "Test Session", created_at, created_at],
    )


def insert_test_message(
    db: AnalyticsDB,
    message_id: str,
    session_id: str,
    created_at: datetime,
    agent: str = "main",
):
    """Insert a test message."""
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO messages (id, session_id, role, agent, created_at, tokens_input, tokens_output)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [message_id, session_id, "assistant", agent, created_at, 100, 50],
    )


def insert_test_tool(
    db: AnalyticsDB,
    part_id: str,
    message_id: str,
    tool_name: str,
    created_at: datetime,
    status: str = "success",
):
    """Insert a test tool part."""
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO parts (id, message_id, part_type, tool_name, tool_status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [part_id, message_id, "tool", tool_name, status, created_at],
    )


def insert_test_skill(
    db: AnalyticsDB,
    skill_id: str,
    message_id: str,
    session_id: str,
    skill_name: str,
    loaded_at: datetime = None,
):
    """Insert a test skill."""
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO skills (id, message_id, session_id, skill_name, loaded_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [skill_id, message_id, session_id, skill_name, loaded_at],
    )


# =============================================================================
# Tool Stats Date Filtering Tests
# =============================================================================


class TestToolStatsDateFiltering:
    """Tests for _get_tool_stats() date filtering."""

    def test_tool_within_period_is_counted(self, analytics_db, queries):
        """Tools used within the date range should be counted."""
        now = datetime.now()
        yesterday = now - timedelta(hours=12)

        # Create session and message within period
        session_id = generate_id()
        message_id = generate_id()
        insert_test_session(analytics_db, session_id, yesterday)
        insert_test_message(analytics_db, message_id, session_id, yesterday)

        # Add tool invocation
        insert_test_tool(analytics_db, generate_id(), message_id, "bash", yesterday)

        # Query for last 24 hours
        start_date = now - timedelta(days=1)
        end_date = now
        tools = queries._get_tool_stats(start_date, end_date)

        assert len(tools) == 1
        assert tools[0].tool_name == "bash"
        assert tools[0].invocations == 1

    def test_tool_outside_period_is_excluded(self, analytics_db, queries):
        """Tools used outside the date range should NOT be counted."""
        now = datetime.now()
        two_days_ago = now - timedelta(days=2)

        # Create session and message OUTSIDE period (2 days ago)
        session_id = generate_id()
        message_id = generate_id()
        insert_test_session(analytics_db, session_id, two_days_ago)
        insert_test_message(analytics_db, message_id, session_id, two_days_ago)

        # Add tool invocation from 2 days ago
        insert_test_tool(analytics_db, generate_id(), message_id, "bash", two_days_ago)

        # Query for last 24 hours only
        start_date = now - timedelta(days=1)
        end_date = now
        tools = queries._get_tool_stats(start_date, end_date)

        # Should be empty - tool is outside period
        assert len(tools) == 0

    def test_mixed_tools_only_recent_counted(self, analytics_db, queries):
        """Only tools within period should be counted when mixed data exists."""
        now = datetime.now()
        yesterday = now - timedelta(hours=12)
        three_days_ago = now - timedelta(days=3)

        # Recent tool (within period)
        session1 = generate_id()
        message1 = generate_id()
        insert_test_session(analytics_db, session1, yesterday)
        insert_test_message(analytics_db, message1, session1, yesterday)
        insert_test_tool(analytics_db, generate_id(), message1, "read", yesterday)

        # Old tool (outside period)
        session2 = generate_id()
        message2 = generate_id()
        insert_test_session(analytics_db, session2, three_days_ago)
        insert_test_message(analytics_db, message2, session2, three_days_ago)
        insert_test_tool(analytics_db, generate_id(), message2, "bash", three_days_ago)

        # Query for last 24 hours
        start_date = now - timedelta(days=1)
        end_date = now
        tools = queries._get_tool_stats(start_date, end_date)

        # Only "read" should be counted
        assert len(tools) == 1
        assert tools[0].tool_name == "read"

    def test_tool_failure_counts_filtered_by_date(self, analytics_db, queries):
        """Tool failure counts should also respect date filtering."""
        now = datetime.now()
        yesterday = now - timedelta(hours=12)
        three_days_ago = now - timedelta(days=3)

        # Recent failed tool (within period)
        session1 = generate_id()
        message1 = generate_id()
        insert_test_session(analytics_db, session1, yesterday)
        insert_test_message(analytics_db, message1, session1, yesterday)
        insert_test_tool(
            analytics_db, generate_id(), message1, "bash", yesterday, status="error"
        )

        # Old failed tool (outside period)
        session2 = generate_id()
        message2 = generate_id()
        insert_test_session(analytics_db, session2, three_days_ago)
        insert_test_message(analytics_db, message2, session2, three_days_ago)
        insert_test_tool(
            analytics_db,
            generate_id(),
            message2,
            "bash",
            three_days_ago,
            status="error",
        )

        # Query for last 24 hours
        start_date = now - timedelta(days=1)
        end_date = now
        tools = queries._get_tool_stats(start_date, end_date)

        # Only 1 failure should be counted (the recent one)
        assert len(tools) == 1
        assert tools[0].failures == 1


# =============================================================================
# Skill Stats Date Filtering Tests
# =============================================================================


class TestSkillStatsDateFiltering:
    """Tests for _get_skill_stats() date filtering."""

    def test_skill_within_period_is_counted(self, analytics_db, queries):
        """Skills loaded within the date range should be counted."""
        now = datetime.now()
        yesterday = now - timedelta(hours=12)

        # Create session and message within period
        session_id = generate_id()
        message_id = generate_id()
        insert_test_session(analytics_db, session_id, yesterday)
        insert_test_message(analytics_db, message_id, session_id, yesterday)

        # Add skill load
        insert_test_skill(
            analytics_db, generate_id(), message_id, session_id, "qml", yesterday
        )

        # Query for last 24 hours
        start_date = now - timedelta(days=1)
        end_date = now
        skills = queries._get_skill_stats(start_date, end_date)

        assert len(skills) == 1
        assert skills[0].skill_name == "qml"
        assert skills[0].load_count == 1

    def test_skill_outside_period_is_excluded(self, analytics_db, queries):
        """Skills loaded outside the date range should NOT be counted."""
        now = datetime.now()
        two_days_ago = now - timedelta(days=2)

        # Create session and message OUTSIDE period (2 days ago)
        session_id = generate_id()
        message_id = generate_id()
        insert_test_session(analytics_db, session_id, two_days_ago)
        insert_test_message(analytics_db, message_id, session_id, two_days_ago)

        # Add skill load from 2 days ago
        insert_test_skill(
            analytics_db, generate_id(), message_id, session_id, "qml", two_days_ago
        )

        # Query for last 24 hours only
        start_date = now - timedelta(days=1)
        end_date = now
        skills = queries._get_skill_stats(start_date, end_date)

        # Should be empty - skill is outside period
        assert len(skills) == 0

    def test_mixed_skills_only_recent_counted(self, analytics_db, queries):
        """Only skills within period should be counted when mixed data exists."""
        now = datetime.now()
        yesterday = now - timedelta(hours=12)
        three_days_ago = now - timedelta(days=3)

        # Recent skill (within period)
        session1 = generate_id()
        message1 = generate_id()
        insert_test_session(analytics_db, session1, yesterday)
        insert_test_message(analytics_db, message1, session1, yesterday)
        insert_test_skill(
            analytics_db, generate_id(), message1, session1, "agentic-flow", yesterday
        )

        # Old skill (outside period)
        session2 = generate_id()
        message2 = generate_id()
        insert_test_session(analytics_db, session2, three_days_ago)
        insert_test_message(analytics_db, message2, session2, three_days_ago)
        insert_test_skill(
            analytics_db, generate_id(), message2, session2, "qml", three_days_ago
        )

        # Query for last 24 hours
        start_date = now - timedelta(days=1)
        end_date = now
        skills = queries._get_skill_stats(start_date, end_date)

        # Only "agentic-flow" should be counted
        assert len(skills) == 1
        assert skills[0].skill_name == "agentic-flow"


# =============================================================================
# Skills by Agent Date Filtering Tests
# =============================================================================


class TestSkillsByAgentDateFiltering:
    """Tests for _get_skills_by_agent() date filtering."""

    def test_skills_by_agent_within_period(self, analytics_db, queries):
        """Skills by agent within the date range should be counted."""
        now = datetime.now()
        yesterday = now - timedelta(hours=12)

        # Create session and message within period
        session_id = generate_id()
        message_id = generate_id()
        insert_test_session(analytics_db, session_id, yesterday)
        insert_test_message(
            analytics_db, message_id, session_id, yesterday, agent="executor"
        )

        # Add skill load
        insert_test_skill(
            analytics_db, generate_id(), message_id, session_id, "testability-patterns"
        )

        # Query for last 24 hours
        start_date = now - timedelta(days=1)
        end_date = now
        skills_by_agent = queries._get_skills_by_agent(start_date, end_date)

        assert len(skills_by_agent) == 1
        assert skills_by_agent[0].agent == "executor"
        assert skills_by_agent[0].skill_name == "testability-patterns"
        assert skills_by_agent[0].count == 1

    def test_skills_by_agent_outside_period_excluded(self, analytics_db, queries):
        """Skills by agent outside the date range should NOT be counted."""
        now = datetime.now()
        two_days_ago = now - timedelta(days=2)

        # Create session and message OUTSIDE period
        session_id = generate_id()
        message_id = generate_id()
        insert_test_session(analytics_db, session_id, two_days_ago)
        insert_test_message(
            analytics_db, message_id, session_id, two_days_ago, agent="tester"
        )

        # Add skill load from 2 days ago
        insert_test_skill(
            analytics_db, generate_id(), message_id, session_id, "functional-testing"
        )

        # Query for last 24 hours only
        start_date = now - timedelta(days=1)
        end_date = now
        skills_by_agent = queries._get_skills_by_agent(start_date, end_date)

        # Should be empty - skill is outside period
        assert len(skills_by_agent) == 0

    def test_mixed_agents_only_recent_skills_counted(self, analytics_db, queries):
        """Only skills within period should be counted for each agent."""
        now = datetime.now()
        yesterday = now - timedelta(hours=12)
        three_days_ago = now - timedelta(days=3)

        # Recent skill by executor (within period)
        session1 = generate_id()
        message1 = generate_id()
        insert_test_session(analytics_db, session1, yesterday)
        insert_test_message(
            analytics_db, message1, session1, yesterday, agent="executor"
        )
        insert_test_skill(
            analytics_db, generate_id(), message1, session1, "agentic-flow"
        )

        # Old skill by same executor (outside period)
        session2 = generate_id()
        message2 = generate_id()
        insert_test_session(analytics_db, session2, three_days_ago)
        insert_test_message(
            analytics_db, message2, session2, three_days_ago, agent="executor"
        )
        insert_test_skill(analytics_db, generate_id(), message2, session2, "qml")

        # Query for last 24 hours
        start_date = now - timedelta(days=1)
        end_date = now
        skills_by_agent = queries._get_skills_by_agent(start_date, end_date)

        # Only "agentic-flow" should be counted for executor
        assert len(skills_by_agent) == 1
        assert skills_by_agent[0].agent == "executor"
        assert skills_by_agent[0].skill_name == "agentic-flow"


# =============================================================================
# Integration Tests
# =============================================================================


class TestDateFilteringIntegration:
    """Integration tests for date filtering across all queries."""

    def test_period_stats_respects_date_filtering(self, analytics_db, queries):
        """get_period_stats should filter all data by date."""
        now = datetime.now()
        yesterday = now - timedelta(hours=12)
        three_days_ago = now - timedelta(days=3)

        # === Recent data (within period) ===
        session1 = generate_id()
        message1 = generate_id()
        insert_test_session(analytics_db, session1, yesterday)
        insert_test_message(analytics_db, message1, session1, yesterday, agent="main")
        insert_test_tool(analytics_db, generate_id(), message1, "read", yesterday)
        insert_test_skill(analytics_db, generate_id(), message1, session1, "qml")

        # === Old data (outside period) ===
        session2 = generate_id()
        message2 = generate_id()
        insert_test_session(analytics_db, session2, three_days_ago)
        insert_test_message(
            analytics_db, message2, session2, three_days_ago, agent="executor"
        )
        insert_test_tool(analytics_db, generate_id(), message2, "bash", three_days_ago)
        insert_test_skill(analytics_db, generate_id(), message2, session2, "clean-code")

        # Query for last 24 hours (days=1)
        stats = queries.get_period_stats(days=1)

        # Only recent session should be counted
        assert stats.session_count == 1

        # Only recent tool should be in tools list
        tool_names = [t.tool_name for t in stats.tools]
        assert "read" in tool_names
        assert "bash" not in tool_names

        # Only recent skill should be in skills list
        skill_names = [s.skill_name for s in stats.skills]
        assert "qml" in skill_names
        assert "clean-code" not in skill_names


# =============================================================================
# Helper functions for enriched data
# =============================================================================


def insert_test_todo(
    db: AnalyticsDB,
    todo_id: str,
    session_id: str,
    content: str,
    status: str = "pending",
    priority: str = "medium",
    position: int = 0,
    created_at: datetime = None,
):
    """Insert a test todo."""
    conn = db.connect()
    created_at = created_at or datetime.now()
    conn.execute(
        """
        INSERT INTO todos (id, session_id, content, status, priority, position, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            todo_id,
            session_id,
            content,
            status,
            priority,
            position,
            created_at,
            created_at,
        ],
    )


def insert_test_project(
    db: AnalyticsDB,
    project_id: str,
    worktree: str,
    vcs: str = "git",
    created_at: datetime = None,
):
    """Insert a test project."""
    conn = db.connect()
    created_at = created_at or datetime.now()
    conn.execute(
        """
        INSERT INTO projects (id, worktree, vcs, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [project_id, worktree, vcs, created_at, created_at],
    )


def insert_test_session_with_project(
    db: AnalyticsDB,
    session_id: str,
    project_id: str,
    created_at: datetime,
    additions: int = 0,
    deletions: int = 0,
    files_changed: int = 0,
):
    """Insert a test session linked to a project."""
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO sessions (id, directory, title, created_at, updated_at, project_id, additions, deletions, files_changed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            session_id,
            "/test/dir",
            "Test Session",
            created_at,
            created_at,
            project_id,
            additions,
            deletions,
            files_changed,
        ],
    )


def insert_test_delegation(
    db: AnalyticsDB,
    delegation_id: str,
    session_id: str,
    parent_agent: str,
    child_agent: str,
    child_session_id: str = None,
    created_at: datetime = None,
):
    """Insert a test delegation."""
    conn = db.connect()
    created_at = created_at or datetime.now()
    conn.execute(
        """
        INSERT INTO delegations (id, session_id, parent_agent, child_agent, child_session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            delegation_id,
            session_id,
            parent_agent,
            child_agent,
            child_session_id,
            created_at,
        ],
    )


def insert_test_message_with_cost(
    db: AnalyticsDB,
    message_id: str,
    session_id: str,
    created_at: datetime,
    cost: float = 0.0,
    model_id: str = None,
    provider_id: str = None,
):
    """Insert a test message with cost info."""
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO messages (id, session_id, role, created_at, tokens_input, tokens_output, cost, model_id, provider_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            message_id,
            session_id,
            "assistant",
            created_at,
            100,
            50,
            cost,
            model_id,
            provider_id,
        ],
    )


def insert_test_part_with_duration(
    db: AnalyticsDB,
    part_id: str,
    message_id: str,
    tool_name: str,
    created_at: datetime,
    duration_ms: int = 100,
    status: str = "success",
):
    """Insert a test part with duration."""
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO parts (id, message_id, part_type, tool_name, tool_status, created_at, duration_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [part_id, message_id, "tool", tool_name, status, created_at, duration_ms],
    )


# =============================================================================
# EnrichedQueries Tests
# =============================================================================


class TestEnrichedQueries:
    """Tests for EnrichedQueries module."""

    def test_get_todos_returns_all_when_no_filters(self, analytics_db, queries):
        """get_todos should return all todos when no filters provided."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        insert_test_todo(
            analytics_db, generate_id(), session_id, "Task 1", status="pending"
        )
        insert_test_todo(
            analytics_db, generate_id(), session_id, "Task 2", status="completed"
        )

        todos = queries.get_todos()
        assert len(todos) == 2

    def test_get_todos_filters_by_session_id(self, analytics_db, queries):
        """get_todos should filter by session_id."""
        now = datetime.now()
        session1 = generate_id()
        session2 = generate_id()
        insert_test_session(analytics_db, session1, now)
        insert_test_session(analytics_db, session2, now)

        insert_test_todo(analytics_db, generate_id(), session1, "Task in session 1")
        insert_test_todo(analytics_db, generate_id(), session2, "Task in session 2")

        todos = queries.get_todos(session_id=session1)
        assert len(todos) == 1
        assert todos[0].session_id == session1

    def test_get_todos_filters_by_status(self, analytics_db, queries):
        """get_todos should filter by status."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        insert_test_todo(
            analytics_db, generate_id(), session_id, "Pending task", status="pending"
        )
        insert_test_todo(
            analytics_db,
            generate_id(),
            session_id,
            "Completed task",
            status="completed",
        )

        todos = queries.get_todos(status="completed")
        assert len(todos) == 1
        assert todos[0].status == "completed"

    def test_get_todos_filters_by_session_and_status(self, analytics_db, queries):
        """get_todos should filter by both session_id and status."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        insert_test_todo(
            analytics_db, generate_id(), session_id, "Task 1", status="pending"
        )
        insert_test_todo(
            analytics_db, generate_id(), session_id, "Task 2", status="completed"
        )

        todos = queries.get_todos(session_id=session_id, status="pending")
        assert len(todos) == 1
        assert todos[0].status == "pending"

    def test_get_todo_stats(self, analytics_db, queries):
        """get_todo_stats should return correct statistics."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        insert_test_todo(
            analytics_db,
            generate_id(),
            session_id,
            "Task 1",
            status="pending",
            created_at=now,
        )
        insert_test_todo(
            analytics_db,
            generate_id(),
            session_id,
            "Task 2",
            status="completed",
            created_at=now,
        )
        insert_test_todo(
            analytics_db,
            generate_id(),
            session_id,
            "Task 3",
            status="completed",
            created_at=now,
        )
        insert_test_todo(
            analytics_db,
            generate_id(),
            session_id,
            "Task 4",
            status="in_progress",
            created_at=now,
        )

        stats = queries.get_todo_stats(days=1)
        assert stats is not None
        assert stats.total == 4
        assert stats.completed == 2
        assert stats.in_progress == 1
        assert stats.pending == 1
        assert stats.completion_rate == 50.0

    def test_get_todo_stats_returns_none_when_empty(self, analytics_db, queries):
        """get_todo_stats should return None when no todos exist."""
        stats = queries.get_todo_stats(days=1)
        assert stats is None

    def test_get_projects(self, analytics_db, queries):
        """get_projects should return all projects."""
        now = datetime.now()
        insert_test_project(analytics_db, generate_id(), "/project/a", created_at=now)
        insert_test_project(analytics_db, generate_id(), "/project/b", created_at=now)

        projects = queries.get_projects()
        assert len(projects) == 2

    def test_get_project_stats(self, analytics_db, queries):
        """get_project_stats should return per-project statistics."""
        now = datetime.now()
        project_id = generate_id()
        session_id = generate_id()

        insert_test_project(analytics_db, project_id, "/project/test", created_at=now)
        insert_test_session_with_project(analytics_db, session_id, project_id, now)
        insert_test_message(analytics_db, generate_id(), session_id, now)

        stats = queries.get_project_stats(days=1)
        assert len(stats) >= 1
        project_stat = next((s for s in stats if s.project_id == project_id), None)
        assert project_stat is not None
        assert project_stat.sessions == 1

    def test_get_code_stats(self, analytics_db, queries):
        """get_code_stats should return code change statistics."""
        now = datetime.now()
        project_id = generate_id()
        session_id = generate_id()

        insert_test_project(analytics_db, project_id, "/project/test", created_at=now)
        insert_test_session_with_project(
            analytics_db,
            session_id,
            project_id,
            now,
            additions=100,
            deletions=50,
            files_changed=5,
        )

        stats = queries.get_code_stats(days=1)
        assert stats["additions"] == 100
        assert stats["deletions"] == 50
        assert stats["files_changed"] == 5
        assert stats["sessions_with_changes"] == 1

    def test_get_code_stats_empty(self, analytics_db, queries):
        """get_code_stats should return zeros when no data."""
        stats = queries.get_code_stats(days=1)
        assert stats["additions"] == 0
        assert stats["deletions"] == 0

    def test_get_cost_stats(self, analytics_db, queries):
        """get_cost_stats should return cost statistics."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        insert_test_message_with_cost(
            analytics_db, generate_id(), session_id, now, cost=0.05
        )
        insert_test_message_with_cost(
            analytics_db, generate_id(), session_id, now, cost=0.10
        )

        stats = queries.get_cost_stats(days=1)
        assert stats["total_cost"] == pytest.approx(0.15, rel=0.01)
        assert stats["messages_with_cost"] == 2

    def test_get_cost_stats_empty(self, analytics_db, queries):
        """get_cost_stats should return zeros when no data."""
        stats = queries.get_cost_stats(days=1)
        assert stats["total_cost"] == 0.0


# =============================================================================
# DelegationQueries Tests
# =============================================================================


class TestDelegationQueries:
    """Tests for DelegationQueries module."""

    def test_get_delegation_metrics(self, analytics_db, queries):
        """_get_delegation_metrics should return metrics."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        # Add delegations
        insert_test_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "tester",
            created_at=now,
        )
        insert_test_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "quality",
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        metrics = queries._get_delegation_metrics(start_date, end_date)
        assert metrics is not None
        assert metrics.total_delegations == 2
        assert metrics.sessions_with_delegations == 1
        assert metrics.unique_patterns == 2

    def test_get_delegation_metrics_returns_none_when_empty(
        self, analytics_db, queries
    ):
        """_get_delegation_metrics should return None when no delegations."""
        now = datetime.now()
        start_date = now - timedelta(days=1)
        end_date = now

        metrics = queries._get_delegation_metrics(start_date, end_date)
        assert metrics is None

    def test_get_delegation_patterns(self, analytics_db, queries):
        """_get_delegation_patterns should return patterns."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_message(analytics_db, generate_id(), session_id, now)

        # Add multiple delegations of the same pattern
        for _ in range(3):
            insert_test_delegation(
                analytics_db,
                generate_id(),
                session_id,
                "executor",
                "tester",
                created_at=now,
            )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        patterns = queries._get_delegation_patterns(start_date, end_date)
        assert len(patterns) >= 1
        pattern = patterns[0]
        assert pattern.parent == "executor"
        assert pattern.child == "tester"
        assert pattern.count == 3

    def test_get_delegation_patterns_empty(self, analytics_db, queries):
        """_get_delegation_patterns should return empty list when no data."""
        now = datetime.now()
        start_date = now - timedelta(days=1)
        end_date = now

        patterns = queries._get_delegation_patterns(start_date, end_date)
        assert patterns == []

    def test_get_agent_chains(self, analytics_db, queries):
        """_get_agent_chains should return delegation chains."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        insert_test_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "tester",
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        chains = queries._get_agent_chains(start_date, end_date)
        assert len(chains) >= 1
        assert "executor -> tester" in chains[0].chain

    def test_get_delegation_sessions(self, analytics_db, queries):
        """_get_delegation_sessions should return sessions with multiple delegations."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        # Add multiple delegations from same agent in same session
        insert_test_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "tester",
            created_at=now,
        )
        insert_test_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "quality",
            created_at=now + timedelta(seconds=1),
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        sessions = queries._get_delegation_sessions(start_date, end_date)
        assert len(sessions) >= 1
        session = sessions[0]
        assert session.delegation_count >= 2


# =============================================================================
# SessionQueries Tests
# =============================================================================


class TestSessionQueries:
    """Tests for SessionQueries module."""

    def test_get_top_sessions(self, analytics_db, queries):
        """_get_top_sessions should return sessions by token usage."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_message(analytics_db, generate_id(), session_id, now)

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        sessions = queries._get_top_sessions(start_date, end_date)
        assert len(sessions) == 1
        assert sessions[0].session_id == session_id

    def test_get_session_token_stats(self, analytics_db, queries):
        """_get_session_token_stats should return token distribution."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_message(analytics_db, generate_id(), session_id, now)

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        stats = queries._get_session_token_stats(start_date, end_date)
        assert stats is not None
        assert stats.total_sessions == 1

    def test_get_session_token_stats_returns_none_when_empty(
        self, analytics_db, queries
    ):
        """_get_session_token_stats should return None when no data."""
        now = datetime.now()
        start_date = now - timedelta(days=1)
        end_date = now

        stats = queries._get_session_token_stats(start_date, end_date)
        assert stats is None

    def test_get_session_hierarchy(self, analytics_db, queries):
        """get_session_hierarchy should return parent-child hierarchy."""
        now = datetime.now()
        parent_id = generate_id()
        child_id = generate_id()

        insert_test_session(analytics_db, parent_id, now)

        # Insert child session with parent reference
        conn = analytics_db.connect()
        conn.execute(
            """
            INSERT INTO sessions (id, directory, title, created_at, updated_at, parent_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [child_id, "/test/dir", "Child Session", now, now, parent_id],
        )

        hierarchy = queries.get_session_hierarchy(parent_id)
        assert hierarchy["current"] == parent_id
        assert len(hierarchy["children"]) == 1
        assert hierarchy["children"][0]["id"] == child_id

    def test_get_session_hierarchy_empty(self, analytics_db, queries):
        """get_session_hierarchy should handle non-existent session."""
        hierarchy = queries.get_session_hierarchy("nonexistent")
        assert hierarchy["current"] == "nonexistent"
        assert hierarchy["children"] == []
        assert hierarchy["parents"] == []

    def test_get_avg_session_duration(self, analytics_db, queries):
        """_get_avg_session_duration should calculate average duration."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        # Insert messages with time gap
        msg1 = generate_id()
        msg2 = generate_id()
        insert_test_message(analytics_db, msg1, session_id, now)
        insert_test_message(analytics_db, msg2, session_id, now + timedelta(minutes=30))

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        duration = queries._get_avg_session_duration(start_date, end_date)
        assert duration >= 0


# =============================================================================
# AgentQueries Tests
# =============================================================================


class TestAgentQueries:
    """Tests for AgentQueries module."""

    def test_get_agent_stats(self, analytics_db, queries):
        """_get_agent_stats should return per-agent statistics."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        insert_test_message(
            analytics_db, generate_id(), session_id, now, agent="executor"
        )
        insert_test_message(
            analytics_db, generate_id(), session_id, now, agent="tester"
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        stats = queries._get_agent_stats(start_date, end_date)
        assert len(stats) == 2
        agents = [s.agent for s in stats]
        assert "executor" in agents
        assert "tester" in agents

    def test_get_agent_roles_orchestrator(self, analytics_db, queries):
        """_get_agent_roles should identify orchestrator (only sends, never receives)."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_message(
            analytics_db, generate_id(), session_id, now, agent="coordinator"
        )

        # Coordinator only sends delegations
        insert_test_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "coordinator",
            "executor",
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        roles = queries._get_agent_roles(start_date, end_date)
        assert len(roles) >= 1
        coordinator_role = next((r for r in roles if r.agent == "coordinator"), None)
        assert coordinator_role is not None
        assert coordinator_role.role == "orchestrator"

    def test_get_agent_roles_worker(self, analytics_db, queries):
        """_get_agent_roles should identify worker (only receives, never sends)."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_message(
            analytics_db, generate_id(), session_id, now, agent="tester"
        )

        # Tester only receives delegations
        insert_test_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "tester",
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        roles = queries._get_agent_roles(start_date, end_date)
        tester_role = next((r for r in roles if r.agent == "tester"), None)
        assert tester_role is not None
        assert tester_role.role == "worker"

    def test_get_agent_roles_hub(self, analytics_db, queries):
        """_get_agent_roles should identify hub (both sends and receives)."""
        now = datetime.now()
        session_id = generate_id()
        child_session = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_session(analytics_db, child_session, now)
        insert_test_message(
            analytics_db, generate_id(), session_id, now, agent="executor"
        )

        # Executor receives from coordinator
        insert_test_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "coordinator",
            "executor",
            created_at=now,
        )
        # Executor sends to tester
        insert_test_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "tester",
            child_session_id=child_session,
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        roles = queries._get_agent_roles(start_date, end_date)
        executor_role = next((r for r in roles if r.agent == "executor"), None)
        assert executor_role is not None
        assert executor_role.role == "hub"

    def test_get_agent_delegation_stats(self, analytics_db, queries):
        """_get_agent_delegation_stats should return delegation stats per agent."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        # Multiple delegations from executor
        for _ in range(3):
            insert_test_delegation(
                analytics_db,
                generate_id(),
                session_id,
                "executor",
                "tester",
                created_at=now,
            )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        stats = queries._get_agent_delegation_stats(start_date, end_date)
        assert len(stats) >= 1
        executor_stats = next((s for s in stats if s.agent == "executor"), None)
        assert executor_stats is not None
        assert executor_stats.total_delegations == 3


# =============================================================================
# DimensionQueries Tests
# =============================================================================


class TestDimensionQueries:
    """Tests for DimensionQueries module."""

    def test_get_directory_stats(self, analytics_db, queries):
        """_get_directory_stats should return per-directory statistics."""
        now = datetime.now()
        session_id = generate_id()

        # Insert session with directory
        conn = analytics_db.connect()
        conn.execute(
            """
            INSERT INTO sessions (id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [session_id, "/home/user/project", "Test Session", now, now],
        )
        insert_test_message(analytics_db, generate_id(), session_id, now)

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        stats = queries._get_directory_stats(start_date, end_date)
        assert len(stats) >= 1
        dir_stat = next((s for s in stats if s.directory == "/home/user/project"), None)
        assert dir_stat is not None

    def test_get_model_stats(self, analytics_db, queries):
        """_get_model_stats should return per-model statistics."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        insert_test_message_with_cost(
            analytics_db,
            generate_id(),
            session_id,
            now,
            model_id="claude-3-sonnet",
            provider_id="anthropic",
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        stats = queries._get_model_stats(start_date, end_date)
        assert len(stats) >= 1
        model_stat = next((s for s in stats if s.model_id == "claude-3-sonnet"), None)
        assert model_stat is not None
        assert model_stat.provider_id == "anthropic"

    def test_get_anomalies_excessive_tasks(self, analytics_db, queries):
        """_get_anomalies should detect sessions with excessive task calls."""
        now = datetime.now()
        session_id = generate_id()
        message_id = generate_id()

        # Create session with title
        conn = analytics_db.connect()
        conn.execute(
            """
            INSERT INTO sessions (id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [session_id, "/test", "Long Session Title Here", now, now],
        )
        insert_test_message(analytics_db, message_id, session_id, now)

        # Add more than 10 task calls
        for _ in range(12):
            insert_test_tool(analytics_db, generate_id(), message_id, "task", now)

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        anomalies = queries._get_anomalies(start_date, end_date)
        assert len(anomalies) >= 1
        assert any("task" in a.lower() for a in anomalies)

    def test_get_anomalies_high_failure_rate(self, analytics_db, queries):
        """_get_anomalies should detect tools with high failure rate."""
        now = datetime.now()
        session_id = generate_id()
        message_id = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_message(analytics_db, message_id, session_id, now)

        # Add 10 tool calls with 3 failures (30% failure rate)
        for i in range(10):
            status = "error" if i < 3 else "success"
            insert_test_tool(
                analytics_db,
                generate_id(),
                message_id,
                "flaky_tool",
                now,
                status=status,
            )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        anomalies = queries._get_anomalies(start_date, end_date)
        assert len(anomalies) >= 1
        assert any("failure" in a.lower() for a in anomalies)

    def test_get_anomalies_public_method(self, analytics_db, queries):
        """get_anomalies (public) should work with days parameter."""
        anomalies = queries.get_anomalies(days=7)
        assert isinstance(anomalies, list)


# =============================================================================
# ToolQueries Tests
# =============================================================================


class TestToolQueries:
    """Tests for ToolQueries module."""

    def test_get_tool_performance(self, analytics_db, queries):
        """get_tool_performance should return duration statistics."""
        now = datetime.now()
        session_id = generate_id()
        message_id = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_message(analytics_db, message_id, session_id, now)

        # Add tools with duration
        insert_test_part_with_duration(
            analytics_db, generate_id(), message_id, "bash", now, duration_ms=100
        )
        insert_test_part_with_duration(
            analytics_db, generate_id(), message_id, "bash", now, duration_ms=200
        )

        perf = queries.get_tool_performance(days=1)
        assert len(perf) >= 1
        bash_perf = next((p for p in perf if p["tool_name"] == "bash"), None)
        assert bash_perf is not None
        assert bash_perf["invocations"] == 2
        assert bash_perf["avg_duration_ms"] == 150

    def test_get_tool_performance_empty(self, analytics_db, queries):
        """get_tool_performance should return empty list when no data."""
        perf = queries.get_tool_performance(days=1)
        assert perf == []


# =============================================================================
# TimeSeriesQueries Tests
# =============================================================================


class TestTimeSeriesQueries:
    """Tests for TimeSeriesQueries module."""

    def test_get_hourly_usage(self, analytics_db, queries):
        """_get_hourly_usage should return usage by hour."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_message(analytics_db, generate_id(), session_id, now)

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        hourly = queries._get_hourly_usage(start_date, end_date)
        assert len(hourly) >= 1
        assert hourly[0].hour == now.hour

    def test_get_hourly_delegations(self, analytics_db, queries):
        """_get_hourly_delegations should return delegations by hour."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        insert_test_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "tester",
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        hourly = queries._get_hourly_delegations(start_date, end_date)
        assert len(hourly) >= 1

    def test_get_daily_stats(self, analytics_db, queries):
        """_get_daily_stats should return daily statistics."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_message(analytics_db, generate_id(), session_id, now)

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        daily = queries._get_daily_stats(start_date, end_date)
        assert len(daily) >= 1


# =============================================================================
# BaseQueries Tests
# =============================================================================


class TestBaseQueries:
    """Tests for BaseQueries module."""

    def test_get_date_range(self, analytics_db, queries):
        """_get_date_range should calculate correct date range."""
        start, end = queries._get_date_range(7)

        # End should be now
        assert (datetime.now() - end).total_seconds() < 1

        # Start should be 7 days ago
        delta = end - start
        assert delta.days == 7


# =============================================================================
# Extended Chain Tests (DelegationQueries)
# =============================================================================


class TestDelegationExtendedChains:
    """Tests for extended delegation chains (depth > 2)."""

    def test_get_extended_chains(self, analytics_db, queries):
        """_get_extended_chains should find chains of depth 3."""
        now = datetime.now()

        # Create sessions for chain
        session1 = generate_id()
        session2 = generate_id()
        session3 = generate_id()

        insert_test_session(analytics_db, session1, now)
        insert_test_session(analytics_db, session2, now)
        insert_test_session(analytics_db, session3, now)

        # Create chain: executor -> tester -> quality
        insert_test_delegation(
            analytics_db,
            generate_id(),
            session1,
            "executor",
            "tester",
            child_session_id=session2,
            created_at=now,
        )
        insert_test_delegation(
            analytics_db,
            generate_id(),
            session2,
            "tester",
            "quality",
            child_session_id=session3,
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        chains = queries._get_extended_chains(start_date, end_date)
        # Extended chains are depth 3+
        assert isinstance(chains, list)

    def test_recursive_delegations(self, analytics_db, queries):
        """Test recursive delegation detection (agent delegates to itself)."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        # Agent delegates to itself
        insert_test_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "executor",
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        metrics = queries._get_delegation_metrics(start_date, end_date)
        assert metrics is not None
        assert metrics.recursive_delegations == 1


# =============================================================================
# Edge Cases and Exception Handler Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases to improve coverage."""

    @pytest.mark.parametrize(
        "method_name,call_args",
        [
            ("get_todos", {}),
            ("get_projects", {}),
            ("get_project_stats", {"days": 1}),
        ],
    )
    def test_simple_methods_return_empty_list(
        self, analytics_db, queries, method_name, call_args
    ):
        """Methods should return empty list when no data exists."""
        method = getattr(queries, method_name)
        result = method(**call_args)
        assert result == []

    @pytest.mark.parametrize(
        "method_name",
        [
            "_get_directory_stats",
            "_get_model_stats",
            "_get_agent_roles",
            "_get_agent_delegation_stats",
            "_get_hourly_delegations",
            "_get_daily_stats",
            "_get_skills_by_agent",
        ],
    )
    def test_date_range_methods_return_empty_list(
        self, analytics_db, queries, method_name
    ):
        """Date-range methods should return empty list when no data exists."""
        now = datetime.now()
        start_date = now - timedelta(days=1)
        end_date = now

        method = getattr(queries, method_name)
        result = method(start_date, end_date)
        assert result == []

    def test_session_with_null_title(self, analytics_db, queries):
        """Sessions with NULL title should display as 'Untitled'."""
        now = datetime.now()
        session_id = generate_id()

        # Insert session with NULL title
        conn = analytics_db.connect()
        conn.execute(
            """
            INSERT INTO sessions (id, directory, title, created_at, updated_at)
            VALUES (?, ?, NULL, ?, ?)
            """,
            [session_id, "/test", now, now],
        )
        insert_test_message(analytics_db, generate_id(), session_id, now)

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        sessions = queries._get_top_sessions(start_date, end_date)
        assert len(sessions) == 1
        assert sessions[0].title == "Untitled"

    def test_delegation_sessions_empty(self, analytics_db, queries):
        """_get_delegation_sessions should return empty when no multi-delegations."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        # Only 1 delegation (need >= 2 to be included)
        insert_test_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "tester",
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        sessions = queries._get_delegation_sessions(start_date, end_date)
        assert sessions == []

    def test_anomalies_no_excessive_tasks(self, analytics_db, queries):
        """_get_anomalies should not flag sessions with <= 10 task calls."""
        now = datetime.now()
        session_id = generate_id()
        message_id = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_message(analytics_db, message_id, session_id, now)

        # Add exactly 10 task calls (threshold is > 10)
        for _ in range(10):
            insert_test_tool(analytics_db, generate_id(), message_id, "task", now)

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        anomalies = queries._get_anomalies(start_date, end_date)
        # Should not have excessive task anomaly
        assert not any("task" in a.lower() for a in anomalies)

    def test_anomalies_low_failure_rate_not_flagged(self, analytics_db, queries):
        """_get_anomalies should not flag tools with <= 20% failure rate."""
        now = datetime.now()
        session_id = generate_id()
        message_id = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_message(analytics_db, message_id, session_id, now)

        # Add 10 tool calls with 2 failures (20% - at threshold)
        for i in range(10):
            status = "error" if i < 2 else "success"
            insert_test_tool(
                analytics_db,
                generate_id(),
                message_id,
                "stable_tool",
                now,
                status=status,
            )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        anomalies = queries._get_anomalies(start_date, end_date)
        # Should not flag stable_tool (20% is at threshold, not above)
        assert not any("stable_tool" in a for a in anomalies)


# =============================================================================
# Additional Coverage Tests
# =============================================================================


class TestModelStatsPercentage:
    """Tests for model stats with percentage calculation."""

    def test_model_percentage_calculation(self, analytics_db, queries):
        """Model percentage should be calculated correctly."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        # Add messages with different models
        insert_test_message_with_cost(
            analytics_db,
            generate_id(),
            session_id,
            now,
            model_id="model-a",
            provider_id="provider-a",
        )
        insert_test_message_with_cost(
            analytics_db,
            generate_id(),
            session_id,
            now,
            model_id="model-b",
            provider_id="provider-b",
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        stats = queries._get_model_stats(start_date, end_date)
        assert len(stats) == 2
        # Percentages should sum to 100%
        total_percentage = sum(s.percentage for s in stats)
        assert abs(total_percentage - 100.0) < 0.1


class TestTodoWithCancelledStatus:
    """Test todos with cancelled status."""

    def test_todo_stats_with_cancelled(self, analytics_db, queries):
        """get_todo_stats should count cancelled todos."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        insert_test_todo(
            analytics_db,
            generate_id(),
            session_id,
            "Cancelled task",
            status="cancelled",
            created_at=now,
        )

        stats = queries.get_todo_stats(days=1)
        assert stats is not None
        assert stats.cancelled == 1


# =============================================================================
# Additional Delegation Tests for Coverage
# =============================================================================


class TestDelegationPatternsDetails:
    """Additional tests for delegation patterns."""

    def test_delegation_patterns_with_tokens(self, analytics_db, queries):
        """_get_delegation_patterns should calculate token totals correctly."""
        now = datetime.now()

        # Create parent and child sessions
        parent_session = generate_id()
        child_session = generate_id()

        insert_test_session(analytics_db, parent_session, now)
        insert_test_session(analytics_db, child_session, now)

        # Add messages to both sessions for token counting
        insert_test_message(analytics_db, generate_id(), parent_session, now)
        insert_test_message(analytics_db, generate_id(), child_session, now)

        # Add delegation with child_session_id
        insert_test_delegation(
            analytics_db,
            generate_id(),
            parent_session,
            "executor",
            "tester",
            child_session_id=child_session,
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        patterns = queries._get_delegation_patterns(start_date, end_date)
        assert len(patterns) >= 1
        assert patterns[0].tokens_total >= 0
        assert patterns[0].tokens_avg >= 0

    def test_delegation_patterns_percentage(self, analytics_db, queries):
        """_get_delegation_patterns should calculate percentage correctly."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_message(analytics_db, generate_id(), session_id, now)

        # Add 2 executor->tester and 1 executor->quality
        for _ in range(2):
            insert_test_delegation(
                analytics_db,
                generate_id(),
                session_id,
                "executor",
                "tester",
                created_at=now,
            )
        insert_test_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "quality",
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        patterns = queries._get_delegation_patterns(start_date, end_date)

        # Verify percentages
        total_percentage = sum(p.percentage for p in patterns)
        assert abs(total_percentage - 100.0) < 0.1


class TestSessionDurationEdgeCases:
    """Edge cases for session duration calculations."""

    def test_session_duration_single_message(self, analytics_db, queries):
        """Sessions with single message should have 0 duration."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)

        # Single message - no duration
        insert_test_message(analytics_db, generate_id(), session_id, now)

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        # avg_session_duration filters out single-message sessions
        duration = queries._get_avg_session_duration(start_date, end_date)
        assert duration == 0  # No sessions with > 1 message


class TestAgentRolesFanOut:
    """Test fan-out calculation in agent roles."""

    def test_agent_role_fan_out_calculation(self, analytics_db, queries):
        """Fan-out should be sent/received ratio."""
        now = datetime.now()
        session_id = generate_id()
        insert_test_session(analytics_db, session_id, now)
        insert_test_message(analytics_db, generate_id(), session_id, now, agent="hub")

        # Hub receives 2 and sends 4 = fan-out of 2.0
        for _ in range(2):
            insert_test_delegation(
                analytics_db,
                generate_id(),
                session_id,
                "coordinator",
                "hub",
                created_at=now,
            )
        for _ in range(4):
            insert_test_delegation(
                analytics_db, generate_id(), session_id, "hub", "worker", created_at=now
            )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        roles = queries._get_agent_roles(start_date, end_date)
        hub_role = next((r for r in roles if r.agent == "hub"), None)
        assert hub_role is not None
        assert hub_role.fan_out == 2.0


class TestDirectoryStatsWithTokens:
    """Test directory stats with token aggregation."""

    def test_directory_stats_aggregates_tokens(self, analytics_db, queries):
        """Directory stats should aggregate tokens from all sessions."""
        now = datetime.now()

        # Two sessions in same directory
        session1 = generate_id()
        session2 = generate_id()

        conn = analytics_db.connect()
        for sid in [session1, session2]:
            conn.execute(
                """
                INSERT INTO sessions (id, directory, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [sid, "/same/directory", f"Session {sid}", now, now],
            )
            insert_test_message(analytics_db, generate_id(), sid, now)

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        stats = queries._get_directory_stats(start_date, end_date)
        assert len(stats) >= 1
        dir_stat = next((s for s in stats if s.directory == "/same/directory"), None)
        assert dir_stat is not None
        assert dir_stat.sessions == 2
