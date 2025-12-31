"""
Tests for AnalyticsQueries - Date filtering regression tests.

These tests verify that tool and skill statistics respect date filtering,
preventing the display of data outside the selected time period.

Bug context: tools and skills queries were not filtering by date, causing
data from several days ago to appear when selecting "24h" period.
"""

import uuid
from datetime import datetime, timedelta

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.queries import AnalyticsQueries


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
