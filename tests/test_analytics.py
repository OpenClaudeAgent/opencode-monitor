"""
Tests for Analytics module - DuckDB database and queries.

Tests the enriched data model with todos, projects, and new fields.
Schema tests verify the database structure.
Query tests verify analytics queries work correctly.

Note: Data loading tests are in test_bulk_loader.py and test_hybrid_indexer.py.
The former collector insert tests have been migrated there.

LEGACY: These tests use mocks. Migrated to tests/integration/database/ with real DuckDB.
"""

import time
from datetime import datetime

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.models import Todo, Project
from opencode_monitor.analytics.queries import AnalyticsQueries

pytestmark = pytest.mark.legacy


# Note: 'temp_db' fixture is provided by conftest.py (analytics_db)


# =====================================================
# Helper functions for direct SQL insertion
# =====================================================


def insert_session(conn, session_id: str, **kwargs) -> None:
    """Insert a session directly via SQL."""
    now = datetime.now()
    conn.execute(
        """
        INSERT INTO sessions (
            id, project_id, directory, title, created_at, updated_at,
            parent_id, version, additions, deletions, files_changed
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            session_id,
            kwargs.get("project_id", "proj_001"),
            kwargs.get("directory", "/test"),
            kwargs.get("title", "Test Session"),
            kwargs.get("created_at", now),
            kwargs.get("updated_at", now),
            kwargs.get("parent_id"),
            kwargs.get("version"),
            kwargs.get("additions", 0),
            kwargs.get("deletions", 0),
            kwargs.get("files_changed", 0),
        ],
    )


def insert_message(conn, message_id: str, session_id: str, **kwargs) -> None:
    """Insert a message directly via SQL."""
    now = datetime.now()
    conn.execute(
        """
        INSERT INTO messages (
            id, session_id, role, agent, model_id, provider_id,
            tokens_input, tokens_output, cost, created_at, mode, finish_reason
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            message_id,
            session_id,
            kwargs.get("role", "assistant"),
            kwargs.get("agent", "main"),
            kwargs.get("model_id", "claude-sonnet"),
            kwargs.get("provider_id", "anthropic"),
            kwargs.get("tokens_input", 100),
            kwargs.get("tokens_output", 50),
            kwargs.get("cost", 0.0),
            kwargs.get("created_at", now),
            kwargs.get("mode"),
            kwargs.get("finish_reason"),
        ],
    )


def insert_part(conn, part_id: str, session_id: str, message_id: str, **kwargs) -> None:
    """Insert a part directly via SQL."""
    now = datetime.now()
    conn.execute(
        """
        INSERT INTO parts (
            id, session_id, message_id, part_type, tool_name, tool_status,
            created_at, ended_at, duration_ms
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            part_id,
            session_id,
            message_id,
            kwargs.get("part_type", "tool"),
            kwargs.get("tool_name", "bash"),
            kwargs.get("tool_status", "completed"),
            kwargs.get("created_at", now),
            kwargs.get("ended_at"),
            kwargs.get("duration_ms"),
        ],
    )


def insert_todo(conn, todo_id: str, session_id: str, **kwargs) -> None:
    """Insert a todo directly via SQL."""
    now = datetime.now()
    conn.execute(
        """
        INSERT INTO todos (id, session_id, content, status, priority, position, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            todo_id,
            session_id,
            kwargs.get("content", "Test todo"),
            kwargs.get("status", "pending"),
            kwargs.get("priority", "medium"),
            kwargs.get("position", 0),
            kwargs.get("created_at", now),
            kwargs.get("updated_at", now),
        ],
    )


def insert_project(conn, project_id: str, **kwargs) -> None:
    """Insert a project directly via SQL."""
    now = datetime.now()
    conn.execute(
        """
        INSERT INTO projects (id, worktree, vcs, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            project_id,
            kwargs.get("worktree", "/test/path"),
            kwargs.get("vcs", "git"),
            kwargs.get("created_at", now),
            kwargs.get("updated_at", now),
        ],
    )


# =====================================================
# Schema Tests
# =====================================================


class TestDatabaseSchema:
    """Tests for database schema creation."""

    def test_creates_all_tables(self, temp_db: AnalyticsDB):
        """Database creates all required tables including new ones."""
        conn = temp_db.connect()
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        table_names = {t[0] for t in tables}

        expected = {
            "sessions",
            "messages",
            "parts",
            "skills",
            "delegations",
            "todos",
            "projects",
        }
        assert expected.issubset(table_names)

    def test_sessions_has_new_columns(self, temp_db: AnalyticsDB):
        """Sessions table has enriched columns."""
        conn = temp_db.connect()
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'sessions'"
        ).fetchall()
        col_names = {c[0] for c in cols}

        new_cols = {"parent_id", "version", "additions", "deletions", "files_changed"}
        assert new_cols.issubset(col_names)

    def test_messages_has_new_columns(self, temp_db: AnalyticsDB):
        """Messages table has enriched columns."""
        conn = temp_db.connect()
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'messages'"
        ).fetchall()
        col_names = {c[0] for c in cols}

        new_cols = {"mode", "cost", "finish_reason", "working_dir"}
        assert new_cols.issubset(col_names)

    def test_parts_has_new_columns(self, temp_db: AnalyticsDB):
        """Parts table has enriched columns."""
        conn = temp_db.connect()
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'parts'"
        ).fetchall()
        col_names = {c[0] for c in cols}

        new_cols = {"session_id", "call_id", "ended_at", "duration_ms"}
        assert new_cols.issubset(col_names)

    def test_todos_table_structure(self, temp_db: AnalyticsDB):
        """Todos table has correct structure."""
        conn = temp_db.connect()
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'todos'"
        ).fetchall()
        col_names = {c[0] for c in cols}

        expected = {
            "id",
            "session_id",
            "content",
            "status",
            "priority",
            "position",
            "created_at",
            "updated_at",
        }
        assert expected == col_names

    def test_projects_table_structure(self, temp_db: AnalyticsDB):
        """Projects table has correct structure."""
        conn = temp_db.connect()
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'projects'"
        ).fetchall()
        col_names = {c[0] for c in cols}

        expected = {"id", "worktree", "vcs", "created_at", "updated_at"}
        assert expected == col_names


# =====================================================
# Queries Tests
# =====================================================


class TestAnalyticsQueries:
    """Tests for analytics query methods."""

    def test_get_todos_empty(self, temp_db: AnalyticsDB):
        """Get todos returns empty list when no data."""
        queries = AnalyticsQueries(temp_db)
        result = queries.get_todos()
        assert result == []

    def test_get_todos_with_data(self, temp_db: AnalyticsDB):
        """Get todos returns correct data."""
        conn = temp_db.connect()
        insert_todo(
            conn, "todo_1", "ses_test", content="Task 1", status="completed", position=0
        )
        insert_todo(
            conn, "todo_2", "ses_test", content="Task 2", status="pending", position=1
        )

        queries = AnalyticsQueries(temp_db)
        result = queries.get_todos()

        assert len(result) == 2
        assert isinstance(result[0], Todo)
        assert result[0].content == "Task 1"

    def test_get_todos_filter_by_status(self, temp_db: AnalyticsDB):
        """Get todos can filter by status."""
        conn = temp_db.connect()
        insert_todo(
            conn, "todo_1", "ses_test", content="Task 1", status="completed", position=0
        )
        insert_todo(
            conn, "todo_2", "ses_test", content="Task 2", status="pending", position=1
        )

        queries = AnalyticsQueries(temp_db)
        result = queries.get_todos(status="completed")

        assert len(result) == 1
        assert result[0].status == "completed"

    def test_get_projects_empty(self, temp_db: AnalyticsDB):
        """Get projects returns empty list when no data."""
        queries = AnalyticsQueries(temp_db)
        result = queries.get_projects()
        assert result == []

    def test_get_projects_with_data(self, temp_db: AnalyticsDB):
        """Get projects returns correct data."""
        conn = temp_db.connect()
        insert_project(conn, "proj_001", worktree="/test/path", vcs="git")

        queries = AnalyticsQueries(temp_db)
        result = queries.get_projects()

        assert len(result) == 1
        assert isinstance(result[0], Project)
        assert result[0].worktree == "/test/path"
        assert result[0].vcs == "git"

    def test_get_code_stats(self, temp_db: AnalyticsDB):
        """Get code stats returns additions/deletions totals."""
        conn = temp_db.connect()
        now = datetime.now()

        # Insert sessions with code changes
        for i in range(3):
            insert_session(
                conn,
                f"ses_{i}",
                created_at=now,
                additions=100,
                deletions=50,
                files_changed=5,
            )

        queries = AnalyticsQueries(temp_db)
        result = queries.get_code_stats(days=30)

        assert result["additions"] == 300
        assert result["deletions"] == 150
        assert result["files_changed"] == 15
        assert result["sessions_with_changes"] == 3

    def test_get_cost_stats(self, temp_db: AnalyticsDB):
        """Get cost stats returns cost totals."""
        conn = temp_db.connect()
        now = datetime.now()

        # Insert messages with cost
        for i in range(3):
            insert_message(conn, f"msg_{i}", "ses_test", cost=0.01, created_at=now)

        queries = AnalyticsQueries(temp_db)
        result = queries.get_cost_stats(days=30)

        assert result["total_cost"] == pytest.approx(0.03, rel=0.01)
        assert result["messages_with_cost"] == 3

    def test_get_tool_performance(self, temp_db: AnalyticsDB):
        """Get tool performance stats."""
        conn = temp_db.connect()
        now = datetime.now()

        # Insert parts with duration
        for i in range(3):
            insert_part(
                conn,
                f"prt_{i}",
                "ses_test",
                "msg_test",
                tool_name="edit",
                tool_status="completed",
                created_at=now,
                duration_ms=(i + 1) * 1000,  # 1000, 2000, 3000
            )

        queries = AnalyticsQueries(temp_db)
        result = queries.get_tool_performance(days=30)

        assert len(result) == 1
        assert result[0]["tool_name"] == "edit"
        assert result[0]["invocations"] == 3
        assert result[0]["avg_duration_ms"] == 2000  # avg of 1000, 2000, 3000


# =====================================================
# Database Utilities Tests
# =====================================================


class TestDatabaseUtilities:
    """Tests for database utility methods."""

    def test_get_stats_includes_new_tables(self, temp_db: AnalyticsDB):
        """Get stats includes todos and projects."""
        result = temp_db.get_stats()
        assert "todos" in result
        assert "projects" in result

    def test_clear_data_clears_new_tables(self, temp_db: AnalyticsDB):
        """Clear data clears todos and projects too."""
        conn = temp_db.connect()

        # Insert some data using direct SQL
        insert_project(conn, "proj_001", worktree="/test", vcs="git")
        insert_todo(conn, "todo_1", "ses_test", content="Test", status="pending")

        # Verify data was inserted
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0] == 1

        # Clear and verify
        temp_db.clear_data()

        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0] == 0
