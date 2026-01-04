"""
DuckDB database management for analytics.

Uses a singleton pattern to ensure only one connection to the database,
avoiding DuckDB lock conflicts.
"""

import threading
from pathlib import Path
from typing import Optional

import duckdb

from datetime import datetime

from ..utils.logger import info, debug


def get_db_path() -> Path:
    """Get the path to the analytics database."""
    config_dir = Path.home() / ".config" / "opencode-monitor"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "analytics.duckdb"


# Global singleton connection - DEPRECATED
# WARNING: This singleton keeps a connection open indefinitely, which
# blocks dashboard readers. Use AnalyticsDB() directly with context manager.
_db_instance: Optional["AnalyticsDB"] = None
_db_lock = threading.Lock()


def get_analytics_db() -> "AnalyticsDB":
    """Get the singleton AnalyticsDB instance.

    DEPRECATED: This function keeps a connection open indefinitely,
    which blocks concurrent readers (like the dashboard).

    Prefer using AnalyticsDB directly with context manager:

        with AnalyticsDB(read_only=True) as db:
            stats = db.get_stats()

    Or manage connection lifecycle explicitly:

        db = AnalyticsDB()
        try:
            # ... use db ...
        finally:
            db.close()
    """
    global _db_instance
    with _db_lock:
        if _db_instance is None:
            _db_instance = AnalyticsDB()
        return _db_instance


class AnalyticsDB:
    """Manages the DuckDB database for analytics.

    Supports context manager for automatic connection cleanup:

        with AnalyticsDB(read_only=True) as db:
            stats = db.get_stats()
        # Connection automatically closed

    IMPORTANT for concurrency:
    - DuckDB does not allow concurrent readers when a writer holds a lock
    - The menubar is the sole writer; dashboard opens read_only connections
    - Always close connections promptly to avoid blocking readers
    """

    def __init__(self, db_path: Optional[Path] = None, read_only: bool = False):
        """Initialize the analytics database.

        Args:
            db_path: Optional path to database. Uses default if not provided.
            read_only: If True, open in read-only mode (allows concurrent reads).
        """
        self._db_path = db_path or get_db_path()
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._lock = threading.Lock()
        self._read_only = read_only

    def __enter__(self) -> "AnalyticsDB":
        """Context manager entry - connects to database."""
        self.connect()
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb) -> None:
        """Context manager exit - closes connection."""
        self.close()

    def connect(self, read_only: Optional[bool] = None) -> duckdb.DuckDBPyConnection:
        """Get or create a database connection (thread-safe).

        Args:
            read_only: If True, open in read-only mode. Defaults to instance setting.
        """
        if read_only is None:
            read_only = self._read_only
        with self._lock:
            if self._conn is None:
                self._conn = duckdb.connect(str(self._db_path), read_only=read_only)
                # Performance settings: reduce CPU/memory usage for background loading
                self._conn.execute("PRAGMA disable_progress_bar")
                self._conn.execute("SET threads = 2")
                self._conn.execute("SET memory_limit = '512MB'")
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

        # Parts table for message content and tool calls
        conn.execute("""
            CREATE TABLE IF NOT EXISTS parts (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR,
                message_id VARCHAR,
                part_type VARCHAR,
                content VARCHAR,
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

        # Agent traces table for task tool invocations
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_traces (
                trace_id VARCHAR PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                parent_trace_id VARCHAR,
                parent_agent VARCHAR,
                subagent_type VARCHAR NOT NULL,
                prompt_input TEXT NOT NULL,
                prompt_output TEXT,
                started_at TIMESTAMP NOT NULL,
                ended_at TIMESTAMP,
                duration_ms INTEGER,
                tokens_in INTEGER,
                tokens_out INTEGER,
                status VARCHAR DEFAULT 'running',
                tools_used TEXT[],
                child_session_id VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

        # Indexes for agent_traces table
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_session
            ON agent_traces(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_parent
            ON agent_traces(parent_trace_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_subagent
            ON agent_traces(subagent_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_date
            ON agent_traces(started_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_child_session
            ON agent_traces(child_session_id)
        """)

        # Sync metadata table (for dashboard polling)
        # This allows the dashboard to detect when menubar has synced new data
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_meta (
                id INTEGER PRIMARY KEY DEFAULT 1,
                last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sync_count INTEGER DEFAULT 0
            )
        """)
        # Insert initial row if empty
        conn.execute("""
            INSERT INTO sync_meta (id, last_sync, sync_count)
            SELECT 1, CURRENT_TIMESTAMP, 0
            WHERE NOT EXISTS (SELECT 1 FROM sync_meta WHERE id = 1)
        """)

        # File operations table (for tracing file reads/writes/edits)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_operations (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR,
                trace_id VARCHAR,
                operation VARCHAR,
                file_path VARCHAR,
                timestamp TIMESTAMP,
                risk_level VARCHAR,
                risk_reason VARCHAR
            )
        """)

        # Session stats aggregation table (pre-calculated KPIs)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_stats (
                session_id VARCHAR PRIMARY KEY,
                total_messages INTEGER DEFAULT 0,
                total_tokens_in INTEGER DEFAULT 0,
                total_tokens_out INTEGER DEFAULT 0,
                total_tokens_cache INTEGER DEFAULT 0,
                total_tool_calls INTEGER DEFAULT 0,
                tool_success_rate DECIMAL(5,2) DEFAULT 0,
                total_file_reads INTEGER DEFAULT 0,
                total_file_writes INTEGER DEFAULT 0,
                unique_agents INTEGER DEFAULT 0,
                max_delegation_depth INTEGER DEFAULT 0,
                estimated_cost_usd DECIMAL(10,6) DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Daily stats aggregation table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date DATE PRIMARY KEY,
                total_sessions INTEGER DEFAULT 0,
                total_traces INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                total_tool_calls INTEGER DEFAULT 0,
                avg_session_duration_ms INTEGER DEFAULT 0,
                error_rate DECIMAL(5,2) DEFAULT 0
            )
        """)

        # Indexes for new tables
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_ops_session
            ON file_operations(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_ops_trace
            ON file_operations(trace_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_ops_operation
            ON file_operations(operation)
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
            except (
                Exception
            ):  # Intentional catch-all: schema query may fail on edge cases
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
                except Exception as e:  # Intentional catch-all: migration failures are logged and skipped
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
        add_column("parts", "content", "TEXT")  # Text content for prompts/responses
        add_column("parts", "call_id", "VARCHAR")
        add_column("parts", "ended_at", "TIMESTAMP")
        add_column("parts", "duration_ms", "INTEGER")
        add_column("parts", "arguments", "TEXT")
        add_column("parts", "result_summary", "TEXT")
        add_column("parts", "error_message", "TEXT")

        # Sessions - additional columns for stats
        add_column("sessions", "ended_at", "TIMESTAMP")
        add_column("sessions", "duration_ms", "INTEGER")
        add_column("sessions", "is_root", "BOOLEAN", "TRUE")
        add_column("sessions", "project_name", "VARCHAR")

    def clear_data(self) -> None:
        """Clear all data from the database."""
        conn = self.connect()
        conn.execute("DELETE FROM agent_traces")
        conn.execute("DELETE FROM delegations")
        conn.execute("DELETE FROM skills")
        conn.execute("DELETE FROM parts")
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM todos")
        conn.execute("DELETE FROM projects")
        conn.execute("DELETE FROM file_operations")
        conn.execute("DELETE FROM session_stats")
        conn.execute("DELETE FROM daily_stats")
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
            "agent_traces",
            "file_operations",
            "session_stats",
            "daily_stats",
        ]:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                result[table] = count[0] if count else 0
            except Exception:
                result[table] = 0  # Table may not exist yet

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
        except Exception:  # Intentional catch-all: return safe default
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

    def update_sync_timestamp(self) -> None:
        """Mark that a sync just completed (called by menubar only).

        This updates the sync_meta table to signal to dashboard readers
        that new data is available.
        """
        conn = self.connect()
        conn.execute("""
            UPDATE sync_meta
            SET last_sync = CURRENT_TIMESTAMP, sync_count = sync_count + 1
            WHERE id = 1
        """)

    def get_sync_timestamp(self) -> Optional[datetime]:
        """Get last sync timestamp (for dashboard polling).

        Returns:
            The timestamp of the last sync, or None if no sync has occurred.
        """
        conn = self.connect()
        result = conn.execute("SELECT last_sync FROM sync_meta WHERE id = 1").fetchone()
        return result[0] if result else None
