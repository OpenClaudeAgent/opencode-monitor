"""
DuckDB database management for analytics.

Uses a singleton pattern to ensure only one connection to the database,
avoiding DuckDB lock conflicts.
"""

import os
import threading
from pathlib import Path
from typing import Optional

import duckdb

from ..utils.logger import info, debug, error


def get_db_path() -> Path:
    """Get the path to the analytics database."""
    config_dir = Path.home() / ".config" / "opencode-monitor"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "analytics.duckdb"


# Global singleton connection
_db_instance: Optional["AnalyticsDB"] = None
_db_lock = threading.Lock()


def get_analytics_db() -> "AnalyticsDB":
    """Get the singleton AnalyticsDB instance."""
    global _db_instance
    with _db_lock:
        if _db_instance is None:
            _db_instance = AnalyticsDB()
        return _db_instance


class AnalyticsDB:
    """Manages the DuckDB database for analytics.

    Use get_analytics_db() to get the singleton instance.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the analytics database.

        Args:
            db_path: Optional path to database. Uses default if not provided.
        """
        self._db_path = db_path or get_db_path()
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._lock = threading.Lock()

    def connect(self, read_only: bool = False) -> duckdb.DuckDBPyConnection:
        """Get or create a database connection (thread-safe).

        Args:
            read_only: If True, open in read-only mode (allows concurrent access)
        """
        with self._lock:
            if self._conn is None:
                self._conn = duckdb.connect(str(self._db_path), read_only=read_only)
                if not read_only:
                    self._create_schema()
            return self._conn

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def _create_schema(self) -> None:
        """Create the database schema if it doesn't exist.

        Order of operations:
        1. Create base tables (without new columns for existing DBs)
        2. Run migrations to add any missing columns
        3. Create indexes (including those on migrated columns)
        """
        conn = self._conn
        if not conn:
            return

        # Sessions table (base columns only - new columns added via migration)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR,
                directory VARCHAR,
                title VARCHAR,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        # Messages table with token metrics (base columns only)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR,
                parent_id VARCHAR,
                role VARCHAR,
                agent VARCHAR,
                model_id VARCHAR,
                provider_id VARCHAR,
                tokens_input INTEGER DEFAULT 0,
                tokens_output INTEGER DEFAULT 0,
                tokens_reasoning INTEGER DEFAULT 0,
                tokens_cache_read INTEGER DEFAULT 0,
                tokens_cache_write INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # Parts table for tool calls (base columns only)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS parts (
                id VARCHAR PRIMARY KEY,
                message_id VARCHAR,
                part_type VARCHAR,
                tool_name VARCHAR,
                tool_status VARCHAR,
                created_at TIMESTAMP
            )
        """)

        # Skills tracking table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id VARCHAR PRIMARY KEY,
                message_id VARCHAR,
                session_id VARCHAR,
                skill_name VARCHAR,
                loaded_at TIMESTAMP
            )
        """)

        # Agent delegations table (task tool invocations)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS delegations (
                id VARCHAR PRIMARY KEY,
                message_id VARCHAR,
                session_id VARCHAR,
                parent_agent VARCHAR,
                child_agent VARCHAR,
                child_session_id VARCHAR,
                created_at TIMESTAMP
            )
        """)

        # Todos table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR,
                content VARCHAR,
                status VARCHAR,
                priority VARCHAR,
                position INTEGER,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        # Projects table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id VARCHAR PRIMARY KEY,
                worktree VARCHAR,
                vcs VARCHAR,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        # Run migrations to add any missing columns BEFORE creating indexes
        self._migrate_columns(conn)

        # Create indexes for performance (base tables)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_created
            ON messages(created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_parts_message
            ON parts(message_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_created
            ON sessions(created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_delegations_session
            ON delegations(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_delegations_parent
            ON delegations(parent_agent)
        """)

        # Indexes for todos/projects tables
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_todos_session
            ON todos(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_todos_status
            ON todos(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_projects_worktree
            ON projects(worktree)
        """)

        # Indexes on migrated columns (safe now that columns exist)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_parts_session
            ON parts(session_id)
        """)

        debug("Analytics database schema created")

    def _migrate_columns(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Add missing columns to existing tables (idempotent).

        This method checks if each column exists before adding it,
        making it safe to call multiple times.

        Args:
            conn: Active database connection
        """

        # Helper to check if column exists
        def column_exists(table: str, column: str) -> bool:
            try:
                result = conn.execute(
                    f"SELECT * FROM information_schema.columns "
                    f"WHERE table_name = '{table}' AND column_name = '{column}'"
                ).fetchone()
                return result is not None
            except Exception:
                return False

        # Helper to add column if not exists
        def add_column(
            table: str, column: str, col_type: str, default: str = ""
        ) -> None:
            if not column_exists(table, column):
                default_clause = f" DEFAULT {default}" if default else ""
                try:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"
                    )
                    debug(f"Added column {table}.{column}")
                except Exception as e:
                    debug(f"Failed to add column {table}.{column}: {e}")

        # Sessions - new columns
        add_column("sessions", "parent_id", "VARCHAR")
        add_column("sessions", "version", "VARCHAR")
        add_column("sessions", "additions", "INTEGER", "0")
        add_column("sessions", "deletions", "INTEGER", "0")
        add_column("sessions", "files_changed", "INTEGER", "0")

        # Messages - new columns
        add_column("messages", "mode", "VARCHAR")
        add_column("messages", "cost", "DECIMAL(10,6)", "0")
        add_column("messages", "finish_reason", "VARCHAR")
        add_column("messages", "working_dir", "VARCHAR")

        # Parts - new columns
        add_column("parts", "session_id", "VARCHAR")
        add_column("parts", "call_id", "VARCHAR")
        add_column("parts", "ended_at", "TIMESTAMP")
        add_column("parts", "duration_ms", "INTEGER")

    def clear_data(self) -> None:
        """Clear all data from the database."""
        conn = self.connect()
        conn.execute("DELETE FROM delegations")
        conn.execute("DELETE FROM skills")
        conn.execute("DELETE FROM parts")
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM todos")
        conn.execute("DELETE FROM projects")
        info("Analytics database cleared")

    def get_stats(self) -> dict:
        """Get basic stats about the database."""
        conn = self.connect()
        result = {}

        for table in [
            "sessions",
            "messages",
            "parts",
            "skills",
            "delegations",
            "todos",
            "projects",
        ]:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            result[table] = count[0] if count else 0

        return result

    def get_last_refresh(self) -> float:
        """Get timestamp of last data refresh (0 if never refreshed)."""
        conn = self.connect()
        try:
            # Use the max updated_at from sessions as proxy for last refresh
            result = conn.execute("SELECT MAX(updated_at) FROM sessions").fetchone()
            if result and result[0]:
                # DuckDB returns datetime objects
                from datetime import datetime

                if isinstance(result[0], datetime):
                    return result[0].timestamp()
                return float(result[0]) / 1000  # Convert ms to seconds if int
            return 0
        except Exception:
            return 0

    def migrate_schema(self) -> None:
        """Migrate existing database to add new columns.

        This is safe to call multiple times - it checks if columns exist
        before adding them. Delegates to _migrate_columns() which contains
        the actual migration logic.
        """
        conn = self.connect()
        self._migrate_columns(conn)
        info("Database schema migration completed")

    def needs_refresh(self, max_age_hours: int = 24) -> bool:
        """Check if data needs refresh based on age."""
        import time

        last_refresh = self.get_last_refresh()
        if last_refresh == 0:
            return True
        age_hours = (time.time() - last_refresh) / 3600
        return age_hours > max_age_hours
