"""Tests for database utilities."""

import pytest
import sqlite3
import tempfile
import os

from opencode_monitor.utils.db import db_connection, db_cursor


class TestDbConnection:
    """Tests for db_connection context manager."""

    def test_connection_opens_and_closes(self):
        """Test that connection properly opens and closes."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Connection should be open inside context
            with db_connection(db_path) as conn:
                assert conn is not None
                # Verify it's usable
                conn.execute("SELECT 1")

            # After context, connection should be closed
            # Attempting to use it should raise an error
            with pytest.raises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")
        finally:
            os.unlink(db_path)

    def test_creates_database_file(self):
        """Test that connection creates database file if not exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            assert not os.path.exists(db_path)

            with db_connection(db_path) as conn:
                conn.execute("CREATE TABLE test (id INTEGER)")

            assert os.path.exists(db_path)

    def test_connection_yields_valid_connection(self):
        """Test that yielded connection is a valid sqlite3 Connection."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with db_connection(db_path) as conn:
                assert isinstance(conn, sqlite3.Connection)
                # Create and query a table
                conn.execute("CREATE TABLE test (value TEXT)")
                conn.execute("INSERT INTO test VALUES ('hello')")
                result = conn.execute("SELECT value FROM test").fetchone()
                assert result[0] == "hello"
        finally:
            os.unlink(db_path)


class TestDbCursor:
    """Tests for db_cursor context manager."""

    def test_cursor_auto_commits_on_success(self):
        """Test that cursor auto-commits when context exits normally."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with db_connection(db_path) as conn:
                conn.execute("CREATE TABLE test (value TEXT)")

                with db_cursor(conn) as cursor:
                    cursor.execute("INSERT INTO test VALUES ('committed')")

                # Verify data was committed
                result = conn.execute("SELECT value FROM test").fetchone()
                assert result[0] == "committed"
        finally:
            os.unlink(db_path)

    def test_cursor_rollback_on_exception(self):
        """Test that cursor rolls back on exception."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with db_connection(db_path) as conn:
                conn.execute("CREATE TABLE test (value TEXT)")
                conn.commit()

                # This should rollback
                with pytest.raises(ValueError):
                    with db_cursor(conn) as cursor:
                        cursor.execute("INSERT INTO test VALUES ('should_rollback')")
                        raise ValueError("Test exception")

                # Verify data was NOT committed
                result = conn.execute("SELECT COUNT(*) FROM test").fetchone()
                assert result[0] == 0
        finally:
            os.unlink(db_path)

    def test_cursor_yields_valid_cursor(self):
        """Test that yielded cursor is a valid sqlite3 Cursor."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with db_connection(db_path) as conn:
                conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")

                with db_cursor(conn) as cursor:
                    assert isinstance(cursor, sqlite3.Cursor)
                    cursor.execute("INSERT INTO test VALUES (1, 'test')")
                    cursor.execute("SELECT * FROM test WHERE id = 1")
                    row = cursor.fetchone()
                    assert row == (1, "test")
        finally:
            os.unlink(db_path)

    def test_multiple_operations_in_cursor(self):
        """Test multiple operations within single cursor context."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with db_connection(db_path) as conn:
                conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
                conn.commit()

                with db_cursor(conn) as cursor:
                    cursor.execute("INSERT INTO items (name) VALUES ('item1')")
                    cursor.execute("INSERT INTO items (name) VALUES ('item2')")
                    cursor.execute("INSERT INTO items (name) VALUES ('item3')")

                # All three should be committed together
                result = conn.execute("SELECT COUNT(*) FROM items").fetchone()
                assert result[0] == 3
        finally:
            os.unlink(db_path)
