"""
Tests for Analytics module - DuckDB database and collector.

Tests the enriched data model with todos, projects, and new fields.
"""

import json
import time
from pathlib import Path

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.collector import AnalyticsCollector
from opencode_monitor.analytics.models import Todo, Project
from opencode_monitor.analytics.queries import AnalyticsQueries


# Note: 'db' fixture is now provided by conftest.py (analytics_db)


@pytest.fixture
def collector():
    """Create a fresh collector instance."""
    collector = AnalyticsCollector.__new__(AnalyticsCollector)
    collector._stats = {
        "sessions": 0,
        "messages": 0,
        "parts": 0,
        "skills": 0,
        "delegations": 0,
        "todos": 0,
        "projects": 0,
    }
    return collector


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
# Collector Insert Tests
# =====================================================


class TestCollectorInserts:
    """Tests for collector insert methods."""

    def test_insert_session_with_summary(
        self, temp_db: AnalyticsDB, collector: AnalyticsCollector
    ):
        """Insert session with summary data (additions, deletions, files)."""
        conn = temp_db.connect()
        data = {
            "id": "ses_test",
            "projectID": "proj_001",
            "directory": "/test/path",
            "title": "Test Session",
            "parentID": "ses_parent",
            "version": "1.0.0",
            "time": {"created": 1700000000000, "updated": 1700001000000},
            "summary": {"additions": 100, "deletions": 50, "files": 5},
        }

        collector._insert_session(conn, data)
        result = conn.execute(
            "SELECT parent_id, version, additions, deletions, files_changed "
            "FROM sessions WHERE id = 'ses_test'"
        ).fetchone()

        assert result is not None
        # Verify new fields: parent_id, version, additions, deletions, files_changed
        assert result[0] == "ses_parent"  # parent_id
        assert result[1] == "1.0.0"  # version
        assert result[2] == 100  # additions
        assert result[3] == 50  # deletions
        assert result[4] == 5  # files_changed

    def test_insert_message_with_cost(
        self, temp_db: AnalyticsDB, collector: AnalyticsCollector
    ):
        """Insert message with cost, mode, and finish_reason."""
        conn = temp_db.connect()
        data = {
            "id": "msg_test",
            "sessionID": "ses_test",
            "parentID": "msg_parent",
            "role": "assistant",
            "agent": "executor",
            "modelID": "claude-sonnet",
            "providerID": "anthropic",
            "mode": "code",
            "cost": 0.005,
            "finish": "tool-calls",
            "path": {"cwd": "/test/path"},
            "time": {"created": 1700000500000, "completed": 1700000600000},
            "tokens": {
                "input": 1000,
                "output": 500,
                "reasoning": 0,
                "cache": {"read": 200, "write": 50},
            },
        }

        collector._insert_message(conn, data)
        result = conn.execute(
            "SELECT mode, cost, finish_reason, working_dir FROM messages WHERE id = 'msg_test'"
        ).fetchone()

        assert result is not None
        assert result[0] == "code"
        assert float(result[1]) == 0.005
        assert result[2] == "tool-calls"
        assert result[3] == "/test/path"

    def test_insert_part_with_duration(
        self, temp_db: AnalyticsDB, collector: AnalyticsCollector
    ):
        """Insert part with session_id, call_id, and duration."""
        conn = temp_db.connect()
        data = {
            "id": "prt_test",
            "sessionID": "ses_test",
            "messageID": "msg_test",
            "type": "tool",
            "tool": "edit",
            "callID": "call_123",
            "state": {"status": "completed"},
            "time": {"start": 1700000550000, "end": 1700000560000},
        }

        collector._insert_part(conn, data)
        result = conn.execute(
            "SELECT session_id, call_id, duration_ms FROM parts WHERE id = 'prt_test'"
        ).fetchone()

        assert result is not None
        assert result[0] == "ses_test"
        assert result[1] == "call_123"
        assert result[2] == 10000  # 10 seconds in ms

    def test_insert_todos(
        self, temp_db: AnalyticsDB, collector: AnalyticsCollector, tmp_path: Path
    ):
        """Insert todos for a session."""
        conn = temp_db.connect()
        todos = [
            {
                "id": "1",
                "content": "First task",
                "status": "completed",
                "priority": "high",
            },
            {
                "id": "2",
                "content": "Second task",
                "status": "in_progress",
                "priority": "medium",
            },
        ]
        todo_file = tmp_path / "ses_test.json"
        todo_file.write_text(json.dumps(todos))

        collector._insert_todos(conn, "ses_test", todos, todo_file)
        results = conn.execute("SELECT * FROM todos ORDER BY position").fetchall()

        assert len(results) == 2
        assert results[0][2] == "First task"  # content
        assert results[0][3] == "completed"  # status
        assert results[1][2] == "Second task"
        assert results[1][3] == "in_progress"

    def test_insert_project(self, temp_db: AnalyticsDB, collector: AnalyticsCollector):
        """Insert a project."""
        conn = temp_db.connect()
        data = {
            "id": "proj_001",
            "worktree": "/test/path",
            "vcs": "git",
            "time": {"created": 1699999000000, "updated": 1700001000000},
        }

        collector._insert_project(conn, data)
        result = conn.execute("SELECT * FROM projects WHERE id = 'proj_001'").fetchone()

        assert result is not None
        assert result[1] == "/test/path"  # worktree
        assert result[2] == "git"  # vcs


# =====================================================
# Queries Tests
# =====================================================


class TestAnalyticsQueries:
    """Tests for analytics query methods."""

    def _setup_test_todos(
        self,
        temp_db: AnalyticsDB,
        collector: AnalyticsCollector,
        tmp_path: Path,
    ) -> list[dict]:
        """Helper to setup test todos in database.

        Creates 2 todos (one completed, one pending) and inserts them.
        Returns the todo list for assertions.
        """
        conn = temp_db.connect()
        todos = [
            {"id": "1", "content": "Task 1", "status": "completed", "priority": "high"},
            {"id": "2", "content": "Task 2", "status": "pending", "priority": "low"},
        ]
        todo_file = tmp_path / "ses_test.json"
        todo_file.write_text(json.dumps(todos))
        collector._insert_todos(conn, "ses_test", todos, todo_file)
        return todos

    def test_get_todos_empty(self, temp_db: AnalyticsDB):
        """Get todos returns empty list when no data."""
        queries = AnalyticsQueries(temp_db)
        result = queries.get_todos()
        assert result == []

    def test_get_todos_with_data(
        self, temp_db: AnalyticsDB, collector: AnalyticsCollector, tmp_path: Path
    ):
        """Get todos returns correct data."""
        self._setup_test_todos(temp_db, collector, tmp_path)

        queries = AnalyticsQueries(temp_db)
        result = queries.get_todos()

        assert len(result) == 2
        assert isinstance(result[0], Todo)
        assert result[0].content == "Task 1"

    def test_get_todos_filter_by_status(
        self, temp_db: AnalyticsDB, collector: AnalyticsCollector, tmp_path: Path
    ):
        """Get todos can filter by status."""
        self._setup_test_todos(temp_db, collector, tmp_path)

        queries = AnalyticsQueries(temp_db)
        result = queries.get_todos(status="completed")

        assert len(result) == 1
        assert result[0].status == "completed"

    def test_get_projects_empty(self, temp_db: AnalyticsDB):
        """Get projects returns empty list when no data."""
        queries = AnalyticsQueries(temp_db)
        result = queries.get_projects()
        assert result == []

    def test_get_projects_with_data(
        self, temp_db: AnalyticsDB, collector: AnalyticsCollector
    ):
        """Get projects returns correct data."""
        conn = temp_db.connect()
        data = {
            "id": "proj_001",
            "worktree": "/test/path",
            "vcs": "git",
            "time": {"created": 1699999000000, "updated": 1700001000000},
        }
        collector._insert_project(conn, data)

        queries = AnalyticsQueries(temp_db)
        result = queries.get_projects()

        assert len(result) == 1
        assert isinstance(result[0], Project)
        assert result[0].worktree == "/test/path"
        assert result[0].vcs == "git"

    def test_get_code_stats(self, temp_db: AnalyticsDB, collector: AnalyticsCollector):
        """Get code stats returns additions/deletions totals."""
        conn = temp_db.connect()

        # Use current timestamp (in ms) for recent data
        now_ms = int(time.time() * 1000)

        # Insert sessions with code changes
        for i in range(3):
            data = {
                "id": f"ses_{i}",
                "projectID": "proj_001",
                "directory": "/test",
                "title": f"Session {i}",
                "time": {"created": now_ms - i * 1000, "updated": now_ms},
                "summary": {"additions": 100, "deletions": 50, "files": 5},
            }
            collector._insert_session(conn, data)

        queries = AnalyticsQueries(temp_db)
        result = queries.get_code_stats(days=30)

        assert result["additions"] == 300
        assert result["deletions"] == 150
        assert result["files_changed"] == 15
        assert result["sessions_with_changes"] == 3

    def test_get_cost_stats(self, temp_db: AnalyticsDB, collector: AnalyticsCollector):
        """Get cost stats returns cost totals."""
        conn = temp_db.connect()

        # Use current timestamp (in ms) for recent data
        now_ms = int(time.time() * 1000)

        # Insert messages with cost
        for i in range(3):
            data = {
                "id": f"msg_{i}",
                "sessionID": "ses_test",
                "role": "assistant",
                "cost": 0.01,
                "time": {"created": now_ms - i * 1000},
                "tokens": {"input": 100, "output": 50, "cache": {}},
            }
            collector._insert_message(conn, data)

        queries = AnalyticsQueries(temp_db)
        result = queries.get_cost_stats(days=30)

        assert result["total_cost"] == pytest.approx(0.03, rel=0.01)
        assert result["messages_with_cost"] == 3

    def test_get_tool_performance(self, temp_db: AnalyticsDB, collector: AnalyticsCollector):
        """Get tool performance stats."""
        conn = temp_db.connect()

        # Use current timestamp (in ms) for recent data
        now_ms = int(time.time() * 1000)

        # Insert parts with duration
        for i in range(3):
            data = {
                "id": f"prt_{i}",
                "sessionID": "ses_test",
                "messageID": "msg_test",
                "type": "tool",
                "tool": "edit",
                "state": {"status": "completed"},
                "time": {
                    "start": now_ms - 60000,
                    "end": now_ms - 60000 + (i + 1) * 1000,
                },
            }
            collector._insert_part(conn, data)

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

    def test_clear_data_clears_new_tables(
        self, temp_db: AnalyticsDB, collector: AnalyticsCollector, tmp_path: Path
    ):
        """Clear data clears todos and projects too."""
        conn = temp_db.connect()

        # Insert some data
        collector._insert_project(
            conn,
            {
                "id": "proj_001",
                "worktree": "/test",
                "vcs": "git",
                "time": {"created": 1700000000000, "updated": 1700001000000},
            },
        )

        todo_file = tmp_path / "ses_test.json"
        todo_file.write_text("[]")
        collector._insert_todos(
            conn,
            "ses_test",
            [{"id": "1", "content": "Test", "status": "pending", "priority": "high"}],
            todo_file,
        )

        # Clear and verify
        temp_db.clear_data()

        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0] == 0
