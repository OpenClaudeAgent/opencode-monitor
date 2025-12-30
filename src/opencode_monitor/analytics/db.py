"""
DuckDB database management for analytics.
"""

import os
from pathlib import Path
from typing import Optional

import duckdb

from ..utils.logger import info, debug, error


def get_db_path() -> Path:
    """Get the path to the analytics database."""
    config_dir = Path.home() / ".config" / "opencode-monitor"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "analytics.duckdb"


class AnalyticsDB:
    """Manages the DuckDB database for analytics."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the analytics database.

        Args:
            db_path: Optional path to database. Uses default if not provided.
        """
        self._db_path = db_path or get_db_path()
        self._conn: Optional[duckdb.DuckDBPyConnection] = None

    def connect(self) -> duckdb.DuckDBPyConnection:
        """Get or create a database connection."""
        if self._conn is None:
            self._conn = duckdb.connect(str(self._db_path))
            self._create_schema()
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _create_schema(self) -> None:
        """Create the database schema if it doesn't exist."""
        conn = self._conn
        if not conn:
            return

        # Sessions table
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

        # Messages table with token metrics
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

        # Parts table for tool calls
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
                id INTEGER PRIMARY KEY,
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

        # Create indexes for performance
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

        debug("Analytics database schema created")

    def clear_data(self) -> None:
        """Clear all data from the database."""
        conn = self.connect()
        conn.execute("DELETE FROM delegations")
        conn.execute("DELETE FROM skills")
        conn.execute("DELETE FROM parts")
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
        info("Analytics database cleared")

    def get_stats(self) -> dict:
        """Get basic stats about the database."""
        conn = self.connect()
        result = {}

        for table in ["sessions", "messages", "parts", "skills", "delegations"]:
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
        except Exception:
            return 0

    def needs_refresh(self, max_age_hours: int = 24) -> bool:
        """Check if data needs refresh based on age."""
        import time

        last_refresh = self.get_last_refresh()
        if last_refresh == 0:
            return True
        age_hours = (time.time() - last_refresh) / 3600
        return age_hours > max_age_hours
