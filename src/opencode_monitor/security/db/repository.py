"""
Security Database Repository - SQLite operations for security audit data

Also provides DuckDB integration for efficient file scanning via file_index table.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Type, Optional

from ...utils.logger import debug
from ..mitre_utils import serialize_mitre_techniques

from .models import (
    AuditedCommand,
    AuditedFileRead,
    AuditedFileWrite,
    AuditedWebFetch,
)

# Paths
CONFIG_DIR = Path.home() / ".config/opencode-monitor"
DB_PATH = CONFIG_DIR / "security.db"


@dataclass(frozen=True)
class TableConfig:
    """Configuration for a database table."""

    table: str
    columns: str
    timestamp_col: str
    model: Type[Any]


# Table configurations - defines select columns for each table
COMMANDS_CONFIG = TableConfig(
    table="commands",
    columns="""id, file_id, session_id, tool, command, 
               risk_score, risk_level, risk_reason, command_timestamp, scanned_at,
               COALESCE(mitre_techniques, '[]'), 
               COALESCE(edr_sequence_bonus, 0), 
               COALESCE(edr_correlation_bonus, 0)""",
    timestamp_col="command_timestamp",
    model=AuditedCommand,
)

READS_CONFIG = TableConfig(
    table="file_reads",
    columns="""id, file_id, session_id, file_path, 
               risk_score, risk_level, risk_reason, read_timestamp, scanned_at,
               COALESCE(mitre_techniques, '[]'), 
               COALESCE(edr_sequence_bonus, 0), 
               COALESCE(edr_correlation_bonus, 0)""",
    timestamp_col="read_timestamp",
    model=AuditedFileRead,
)

WRITES_CONFIG = TableConfig(
    table="file_writes",
    columns="""id, file_id, session_id, file_path, operation,
               risk_score, risk_level, risk_reason, write_timestamp, scanned_at,
               COALESCE(mitre_techniques, '[]'), 
               COALESCE(edr_sequence_bonus, 0), 
               COALESCE(edr_correlation_bonus, 0)""",
    timestamp_col="write_timestamp",
    model=AuditedFileWrite,
)

WEBFETCHES_CONFIG = TableConfig(
    table="webfetches",
    columns="""id, file_id, session_id, url,
               risk_score, risk_level, risk_reason, fetch_timestamp, scanned_at,
               COALESCE(mitre_techniques, '[]'), 
               COALESCE(edr_sequence_bonus, 0), 
               COALESCE(edr_correlation_bonus, 0)""",
    timestamp_col="fetch_timestamp",
    model=AuditedWebFetch,
)


class SecurityDatabase:
    """SQLite repository for security audit data"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection"""
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize SQLite database schema"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Commands table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE NOT NULL,
                content_hash TEXT NOT NULL,
                session_id TEXT,
                tool TEXT NOT NULL,
                command TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                risk_reason TEXT,
                command_timestamp INTEGER,
                scanned_at TEXT NOT NULL,
                mitre_techniques TEXT DEFAULT '[]',
                edr_sequence_bonus INTEGER DEFAULT 0,
                edr_correlation_bonus INTEGER DEFAULT 0
            )
        """)

        # File reads table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_reads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE NOT NULL,
                content_hash TEXT NOT NULL,
                session_id TEXT,
                file_path TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                risk_reason TEXT,
                read_timestamp INTEGER,
                scanned_at TEXT NOT NULL,
                mitre_techniques TEXT DEFAULT '[]',
                edr_sequence_bonus INTEGER DEFAULT 0,
                edr_correlation_bonus INTEGER DEFAULT 0
            )
        """)

        # File writes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_writes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE NOT NULL,
                content_hash TEXT NOT NULL,
                session_id TEXT,
                file_path TEXT NOT NULL,
                operation TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                risk_reason TEXT,
                write_timestamp INTEGER,
                scanned_at TEXT NOT NULL,
                mitre_techniques TEXT DEFAULT '[]',
                edr_sequence_bonus INTEGER DEFAULT 0,
                edr_correlation_bonus INTEGER DEFAULT 0
            )
        """)

        # Webfetches table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webfetches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE NOT NULL,
                content_hash TEXT NOT NULL,
                session_id TEXT,
                url TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                risk_reason TEXT,
                fetch_timestamp INTEGER,
                scanned_at TEXT NOT NULL,
                mitre_techniques TEXT DEFAULT '[]',
                edr_sequence_bonus INTEGER DEFAULT 0,
                edr_correlation_bonus INTEGER DEFAULT 0
            )
        """)

        # Stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_stats (
                id INTEGER PRIMARY KEY,
                last_full_scan TEXT,
                total_files_scanned INTEGER DEFAULT 0,
                total_commands INTEGER DEFAULT 0
            )
        """)

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_id ON commands(file_id)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_risk_level ON commands(risk_level)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_risk_score ON commands(risk_score DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_reads_file_id ON file_reads(file_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_reads_risk_level ON file_reads(risk_level)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_writes_file_id ON file_writes(file_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_writes_risk_level ON file_writes(risk_level)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_webfetches_file_id ON webfetches(file_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_webfetches_risk_level ON webfetches(risk_level)"
        )

        cursor.execute("INSERT OR IGNORE INTO scan_stats (id) VALUES (1)")

        # Migrate existing tables - add EDR/MITRE columns if missing
        self._migrate_edr_columns(cursor)

        conn.commit()
        conn.close()
        debug("Security database initialized")

    def _migrate_edr_columns(self, cursor: sqlite3.Cursor):
        """Add EDR/MITRE columns to existing tables if they don't exist"""
        tables_columns = {
            "commands": [
                "mitre_techniques",
                "edr_sequence_bonus",
                "edr_correlation_bonus",
            ],
            "file_reads": [
                "mitre_techniques",
                "edr_sequence_bonus",
                "edr_correlation_bonus",
            ],
            "file_writes": [
                "mitre_techniques",
                "edr_sequence_bonus",
                "edr_correlation_bonus",
            ],
            "webfetches": [
                "mitre_techniques",
                "edr_sequence_bonus",
                "edr_correlation_bonus",
            ],
        }

        for table, columns in tables_columns.items():
            # Get existing columns
            cursor.execute(f"PRAGMA table_info({table})")
            existing_cols = {row[1] for row in cursor.fetchall()}

            # Add missing columns
            for col in columns:
                if col not in existing_cols:
                    if col == "mitre_techniques":
                        cursor.execute(
                            f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT '[]'"
                        )
                    else:
                        cursor.execute(
                            f"ALTER TABLE {table} ADD COLUMN {col} INTEGER DEFAULT 0"
                        )
                    debug(f"Migrated: Added {col} to {table}")

    # ===== Generic Query Methods =====

    def _get_by_level(
        self, config: TableConfig, levels: List[str], limit: int = 50
    ) -> List[Any]:
        """Generic method to get records by risk levels.

        Args:
            config: Table configuration with columns and model
            levels: List of risk levels to filter by
            limit: Maximum number of records to return

        Returns:
            List of model instances
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            placeholders = ",".join("?" * len(levels))
            cursor.execute(
                f"""
                SELECT {config.columns}
                FROM {config.table} WHERE risk_level IN ({placeholders})
                ORDER BY risk_score DESC, {config.timestamp_col} DESC LIMIT ?
            """,
                (*levels, limit),
            )
            return [config.model(*row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _get_all(
        self, config: TableConfig, limit: int = 100, offset: int = 0
    ) -> List[Any]:
        """Generic method to get all records with pagination.

        Args:
            config: Table configuration with columns and model
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of model instances
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"""
                SELECT {config.columns}
                FROM {config.table} ORDER BY {config.timestamp_col} DESC 
                LIMIT ? OFFSET ?
            """,
                (limit, offset),
            )
            return [config.model(*row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # ===== Insert Methods =====

    def _execute_insert(
        self, sql: str, data: Dict[str, Any], specific_values: tuple
    ) -> bool:
        """Execute an INSERT statement with common field handling.

        Handles connection management, MITRE serialization, and common fields.

        Args:
            sql: The INSERT SQL statement
            data: The data dict with common fields (file_id, content_hash, etc.)
            specific_values: Table-specific values inserted between session_id and risk_score

        Returns:
            True if a row was inserted, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            mitre_json = serialize_mitre_techniques(data.get("mitre_techniques", []))
            values = (
                data["file_id"],
                data["content_hash"],
                data["session_id"],
                *specific_values,
                data["risk_score"],
                data["risk_level"],
                data["risk_reason"],
                data["timestamp"],
                data["scanned_at"],
                mitre_json,
                data.get("edr_sequence_bonus", 0),
                data.get("edr_correlation_bonus", 0),
            )
            cursor.execute(sql, values)
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def insert_command(self, data: Dict[str, Any]) -> bool:
        """Insert a command record"""
        return self._execute_insert(
            """
            INSERT OR IGNORE INTO commands 
            (file_id, content_hash, session_id, tool, command, 
             risk_score, risk_level, risk_reason, command_timestamp, scanned_at,
             mitre_techniques, edr_sequence_bonus, edr_correlation_bonus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
            (data["tool"], data["command"]),
        )

    def insert_read(self, data: Dict[str, Any]) -> bool:
        """Insert a file read record"""
        return self._execute_insert(
            """
            INSERT OR IGNORE INTO file_reads 
            (file_id, content_hash, session_id, file_path, 
             risk_score, risk_level, risk_reason, read_timestamp, scanned_at,
             mitre_techniques, edr_sequence_bonus, edr_correlation_bonus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
            (data["file_path"],),
        )

    def insert_write(self, data: Dict[str, Any]) -> bool:
        """Insert a file write/edit record"""
        return self._execute_insert(
            """
            INSERT OR IGNORE INTO file_writes 
            (file_id, content_hash, session_id, file_path, operation,
             risk_score, risk_level, risk_reason, write_timestamp, scanned_at,
             mitre_techniques, edr_sequence_bonus, edr_correlation_bonus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
            (data["file_path"], data["operation"]),
        )

    def insert_webfetch(self, data: Dict[str, Any]) -> bool:
        """Insert a webfetch record"""
        return self._execute_insert(
            """
            INSERT OR IGNORE INTO webfetches 
            (file_id, content_hash, session_id, url,
             risk_score, risk_level, risk_reason, fetch_timestamp, scanned_at,
             mitre_techniques, edr_sequence_bonus, edr_correlation_bonus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
            (data["url"],),
        )

    # ===== Query Methods =====

    def get_all_scanned_ids(self) -> set:
        """Get all scanned file IDs from all tables"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            ids = set()
            for table in ["commands", "file_reads", "file_writes", "webfetches"]:
                cursor.execute(f"SELECT file_id FROM {table}")
                ids.update(row[0] for row in cursor.fetchall())
            return ids
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, int]:
        """Get statistics from all tables"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            stats = {
                "total_scanned": 0,
                "total_commands": 0,
                "total_reads": 0,
                "total_writes": 0,
                "total_webfetches": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "reads_critical": 0,
                "reads_high": 0,
                "reads_medium": 0,
                "reads_low": 0,
                "writes_critical": 0,
                "writes_high": 0,
                "writes_medium": 0,
                "writes_low": 0,
                "webfetches_critical": 0,
                "webfetches_high": 0,
                "webfetches_medium": 0,
                "webfetches_low": 0,
            }

            # Load scan stats
            cursor.execute(
                "SELECT total_files_scanned, total_commands FROM scan_stats WHERE id=1"
            )
            row = cursor.fetchone()
            if row:
                stats["total_scanned"] = row[0] or 0
                stats["total_commands"] = row[1] or 0

            # Count by risk level for each table
            for table, prefix in [
                ("commands", ""),
                ("file_reads", "reads_"),
                ("file_writes", "writes_"),
                ("webfetches", "webfetches_"),
            ]:
                cursor.execute(
                    f"SELECT risk_level, COUNT(*) FROM {table} GROUP BY risk_level"
                )
                for level, count in cursor.fetchall():
                    key = f"{prefix}{level}" if prefix else level
                    if key in stats:
                        stats[key] = count

            # Count totals
            cursor.execute("SELECT COUNT(*) FROM file_reads")
            stats["total_reads"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM file_writes")
            stats["total_writes"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM webfetches")
            stats["total_webfetches"] = cursor.fetchone()[0]

            # EDR stats - count records with sequence/correlation bonuses
            stats["edr_sequences"] = 0
            stats["edr_correlations"] = 0
            stats["mitre_tagged"] = 0

            for table in ["commands", "file_reads", "file_writes", "webfetches"]:
                try:
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE edr_sequence_bonus > 0"
                    )
                    stats["edr_sequences"] += cursor.fetchone()[0]

                    cursor.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE edr_correlation_bonus > 0"
                    )
                    stats["edr_correlations"] += cursor.fetchone()[0]

                    cursor.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE mitre_techniques != '[]' AND mitre_techniques IS NOT NULL"
                    )
                    stats["mitre_tagged"] += cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    # Columns may not exist in older schemas
                    pass

            return stats
        finally:
            conn.close()

    def update_scan_stats(
        self, total_scanned: int, total_commands: int, last_scan: str
    ):
        """Update scan statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE scan_stats SET 
                    total_files_scanned = ?, total_commands = ?, last_full_scan = ?
                WHERE id = 1
            """,
                (total_scanned, total_commands, last_scan),
            )
            conn.commit()
        finally:
            conn.close()

    # ===== Public Query Methods (using generics) =====

    def get_commands_by_level(
        self, levels: List[str], limit: int = 50
    ) -> List[AuditedCommand]:
        """Get commands by risk levels"""
        return self._get_by_level(COMMANDS_CONFIG, levels, limit)

    def get_all_commands(
        self, limit: int = 100, offset: int = 0
    ) -> List[AuditedCommand]:
        """Get all commands with pagination"""
        return self._get_all(COMMANDS_CONFIG, limit, offset)

    def get_reads_by_level(
        self, levels: List[str], limit: int = 50
    ) -> List[AuditedFileRead]:
        """Get file reads by risk levels"""
        return self._get_by_level(READS_CONFIG, levels, limit)

    def get_all_reads(self, limit: int = 10000) -> List[AuditedFileRead]:
        """Get all file reads"""
        return self._get_all(READS_CONFIG, limit, 0)

    def get_writes_by_level(
        self, levels: List[str], limit: int = 50
    ) -> List[AuditedFileWrite]:
        """Get file writes by risk levels"""
        return self._get_by_level(WRITES_CONFIG, levels, limit)

    def get_all_writes(self, limit: int = 10000) -> List[AuditedFileWrite]:
        """Get all file writes"""
        return self._get_all(WRITES_CONFIG, limit, 0)

    def get_webfetches_by_level(
        self, levels: List[str], limit: int = 50
    ) -> List[AuditedWebFetch]:
        """Get webfetches by risk levels"""
        return self._get_by_level(WEBFETCHES_CONFIG, levels, limit)

    def get_all_webfetches(self, limit: int = 10000) -> List[AuditedWebFetch]:
        """Get all webfetches"""
        return self._get_all(WEBFETCHES_CONFIG, limit, 0)


class SecurityScannerDuckDB:
    """DuckDB-based file scanner for security auditor.

    Uses file_index table to find unscanned files efficiently via SQL query
    instead of expensive filesystem iteration (152k files → O(1) query).

    Architecture:
    - file_index: populated by analytics indexer, contains all prt_*.json files
    - security_scanned: tracks files already processed by security auditor
    - Query: LEFT JOIN to find files in file_index but not in security_scanned
    """

    def __init__(self, db: Optional["AnalyticsDB"] = None):
        """Initialize with optional injected DuckDB connection.

        Args:
            db: Optional AnalyticsDB instance. If None, creates one lazily.
                Pass a mock or in-memory DB for testing.
        """
        self._db: Optional["AnalyticsDB"] = db
        self._owns_db = db is None  # Track if we should close the connection

    def _get_db(self) -> "AnalyticsDB":
        """Get or create DuckDB connection (lazy initialization)."""
        if self._db is None:
            from ...analytics.db import AnalyticsDB

            self._db = AnalyticsDB()
            self._owns_db = True
        return self._db

    def get_unscanned_files(self, limit: int = 1000) -> List[Path]:
        """Get files from file_index that haven't been security scanned.

        Uses efficient SQL query instead of filesystem iteration.

        Args:
            limit: Maximum number of files to return

        Returns:
            List of Path objects for unscanned files
        """
        db = self._get_db()
        conn = db.connect()

        # Query: find part files not yet scanned
        result = conn.execute(
            """
            SELECT f.file_path
            FROM file_index f
            LEFT JOIN security_scanned s ON f.file_path = s.file_path
            WHERE f.file_type = 'part' AND s.file_path IS NULL
            ORDER BY f.mtime DESC
            LIMIT ?
            """,
            [limit],
        ).fetchall()

        return [Path(row[0]) for row in result]

    def mark_scanned(self, file_path: Path) -> None:
        """Mark a single file as scanned.

        Args:
            file_path: Path to the file that was scanned
        """
        db = self._get_db()
        conn = db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO security_scanned (file_path, scanned_at)
            VALUES (?, CURRENT_TIMESTAMP)
            """,
            [str(file_path)],
        )

    def mark_scanned_batch(self, file_paths: List[Path]) -> int:
        """Mark multiple files as scanned in a single batch.

        Args:
            file_paths: List of paths to mark as scanned

        Returns:
            Number of files marked
        """
        if not file_paths:
            return 0

        db = self._get_db()
        conn = db.connect()

        records = [(str(p),) for p in file_paths]
        conn.executemany(
            """
            INSERT OR REPLACE INTO security_scanned (file_path, scanned_at)
            VALUES (?, CURRENT_TIMESTAMP)
            """,
            records,
        )
        return len(records)

    def get_scanned_count(self) -> int:
        """Get count of files already scanned.

        Returns:
            Number of files in security_scanned table
        """
        db = self._get_db()
        conn = db.connect()
        result = conn.execute("SELECT COUNT(*) FROM security_scanned").fetchone()
        return result[0] if result else 0

    def clear_scanned(self) -> None:
        """Clear all scanned records (for testing/reset)."""
        db = self._get_db()
        conn = db.connect()
        conn.execute("DELETE FROM security_scanned")
        debug("[SecurityScannerDuckDB] Cleared security_scanned table")

    def close(self) -> None:
        """Close the DuckDB connection if we own it."""
        if self._db is not None and self._owns_db:
            self._db.close()
            self._db = None
