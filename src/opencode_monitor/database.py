"""
Security Database - SQLite repository for security audit data
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from .logger import debug, info

# Paths
CONFIG_DIR = Path.home() / ".config/opencode-monitor"
DB_PATH = CONFIG_DIR / "security.db"


@dataclass
class AuditedCommand:
    """A command that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    tool: str
    command: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str


@dataclass
class AuditedFileRead:
    """A file read operation that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    file_path: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str


@dataclass
class AuditedFileWrite:
    """A file write/edit operation that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    file_path: str
    operation: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str


@dataclass
class AuditedWebFetch:
    """A webfetch operation that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    url: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str


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
                scanned_at TEXT NOT NULL
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
                scanned_at TEXT NOT NULL
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
                scanned_at TEXT NOT NULL
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
                scanned_at TEXT NOT NULL
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

        conn.commit()
        conn.close()
        debug("Security database initialized")

    # ===== Insert Methods =====

    def insert_command(self, data: Dict[str, Any]) -> bool:
        """Insert a command record"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO commands 
                (file_id, content_hash, session_id, tool, command, 
                 risk_score, risk_level, risk_reason, command_timestamp, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["file_id"],
                    data["content_hash"],
                    data["session_id"],
                    data["tool"],
                    data["command"],
                    data["risk_score"],
                    data["risk_level"],
                    data["risk_reason"],
                    data["timestamp"],
                    data["scanned_at"],
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def insert_read(self, data: Dict[str, Any]) -> bool:
        """Insert a file read record"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO file_reads 
                (file_id, content_hash, session_id, file_path, 
                 risk_score, risk_level, risk_reason, read_timestamp, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["file_id"],
                    data["content_hash"],
                    data["session_id"],
                    data["file_path"],
                    data["risk_score"],
                    data["risk_level"],
                    data["risk_reason"],
                    data["timestamp"],
                    data["scanned_at"],
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def insert_write(self, data: Dict[str, Any]) -> bool:
        """Insert a file write/edit record"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO file_writes 
                (file_id, content_hash, session_id, file_path, operation,
                 risk_score, risk_level, risk_reason, write_timestamp, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["file_id"],
                    data["content_hash"],
                    data["session_id"],
                    data["file_path"],
                    data["operation"],
                    data["risk_score"],
                    data["risk_level"],
                    data["risk_reason"],
                    data["timestamp"],
                    data["scanned_at"],
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def insert_webfetch(self, data: Dict[str, Any]) -> bool:
        """Insert a webfetch record"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO webfetches 
                (file_id, content_hash, session_id, url,
                 risk_score, risk_level, risk_reason, fetch_timestamp, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["file_id"],
                    data["content_hash"],
                    data["session_id"],
                    data["url"],
                    data["risk_score"],
                    data["risk_level"],
                    data["risk_reason"],
                    data["timestamp"],
                    data["scanned_at"],
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ===== Query Methods =====

    def get_all_scanned_ids(self) -> set:
        """Get all scanned file IDs from all tables"""
        conn = self._get_connection()
        cursor = conn.cursor()

        ids = set()
        for table in ["commands", "file_reads", "file_writes", "webfetches"]:
            cursor.execute(f"SELECT file_id FROM {table}")
            ids.update(row[0] for row in cursor.fetchall())

        conn.close()
        return ids

    def get_stats(self) -> Dict[str, int]:
        """Get statistics from all tables"""
        conn = self._get_connection()
        cursor = conn.cursor()

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

        conn.close()
        return stats

    def update_scan_stats(
        self, total_scanned: int, total_commands: int, last_scan: str
    ):
        """Update scan statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE scan_stats SET 
                total_files_scanned = ?, total_commands = ?, last_full_scan = ?
            WHERE id = 1
        """,
            (total_scanned, total_commands, last_scan),
        )
        conn.commit()
        conn.close()

    def get_commands_by_level(
        self, levels: List[str], limit: int = 50
    ) -> List[AuditedCommand]:
        """Get commands by risk levels"""
        conn = self._get_connection()
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(levels))
        cursor.execute(
            f"""
            SELECT id, file_id, session_id, tool, command, 
                   risk_score, risk_level, risk_reason, command_timestamp, scanned_at
            FROM commands WHERE risk_level IN ({placeholders})
            ORDER BY risk_score DESC, command_timestamp DESC LIMIT ?
        """,
            (*levels, limit),
        )

        results = [AuditedCommand(*row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_all_commands(
        self, limit: int = 100, offset: int = 0
    ) -> List[AuditedCommand]:
        """Get all commands with pagination"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, file_id, session_id, tool, command, 
                   risk_score, risk_level, risk_reason, command_timestamp, scanned_at
            FROM commands ORDER BY command_timestamp DESC LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )
        results = [AuditedCommand(*row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_reads_by_level(
        self, levels: List[str], limit: int = 50
    ) -> List[AuditedFileRead]:
        """Get file reads by risk levels"""
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(levels))
        cursor.execute(
            f"""
            SELECT id, file_id, session_id, file_path, 
                   risk_score, risk_level, risk_reason, read_timestamp, scanned_at
            FROM file_reads WHERE risk_level IN ({placeholders})
            ORDER BY risk_score DESC, read_timestamp DESC LIMIT ?
        """,
            (*levels, limit),
        )
        results = [AuditedFileRead(*row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_all_reads(self, limit: int = 10000) -> List[AuditedFileRead]:
        """Get all file reads"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, file_id, session_id, file_path, 
                   risk_score, risk_level, risk_reason, read_timestamp, scanned_at
            FROM file_reads ORDER BY read_timestamp DESC LIMIT ?
        """,
            (limit,),
        )
        results = [AuditedFileRead(*row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_writes_by_level(
        self, levels: List[str], limit: int = 50
    ) -> List[AuditedFileWrite]:
        """Get file writes by risk levels"""
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(levels))
        cursor.execute(
            f"""
            SELECT id, file_id, session_id, file_path, operation,
                   risk_score, risk_level, risk_reason, write_timestamp, scanned_at
            FROM file_writes WHERE risk_level IN ({placeholders})
            ORDER BY risk_score DESC, write_timestamp DESC LIMIT ?
        """,
            (*levels, limit),
        )
        results = [AuditedFileWrite(*row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_all_writes(self, limit: int = 10000) -> List[AuditedFileWrite]:
        """Get all file writes"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, file_id, session_id, file_path, operation,
                   risk_score, risk_level, risk_reason, write_timestamp, scanned_at
            FROM file_writes ORDER BY write_timestamp DESC LIMIT ?
        """,
            (limit,),
        )
        results = [AuditedFileWrite(*row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_webfetches_by_level(
        self, levels: List[str], limit: int = 50
    ) -> List[AuditedWebFetch]:
        """Get webfetches by risk levels"""
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(levels))
        cursor.execute(
            f"""
            SELECT id, file_id, session_id, url,
                   risk_score, risk_level, risk_reason, fetch_timestamp, scanned_at
            FROM webfetches WHERE risk_level IN ({placeholders})
            ORDER BY risk_score DESC, fetch_timestamp DESC LIMIT ?
        """,
            (*levels, limit),
        )
        results = [AuditedWebFetch(*row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_all_webfetches(self, limit: int = 10000) -> List[AuditedWebFetch]:
        """Get all webfetches"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, file_id, session_id, url,
                   risk_score, risk_level, risk_reason, fetch_timestamp, scanned_at
            FROM webfetches ORDER BY fetch_timestamp DESC LIMIT ?
        """,
            (limit,),
        )
        results = [AuditedWebFetch(*row) for row in cursor.fetchall()]
        conn.close()
        return results
