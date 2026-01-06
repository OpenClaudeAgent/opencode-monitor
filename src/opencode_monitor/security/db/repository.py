"""
Security Database Repository - DuckDB operations for security audit data.

All security audit data is now stored in the unified analytics.duckdb database.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, List, Dict, Any, Type, Optional

if TYPE_CHECKING:
    from opencode_monitor.analytics.db import AnalyticsDB

from ...utils.logger import debug
from ..mitre_utils import serialize_mitre_techniques

from .models import (
    AuditedCommand,
    AuditedFileRead,
    AuditedFileWrite,
    AuditedWebFetch,
)

# Allowed table names - whitelist for SQL injection prevention
_ALLOWED_TABLES = frozenset(
    {
        "security_commands",
        "security_file_reads",
        "security_file_writes",
        "security_webfetches",
    }
)


@dataclass(frozen=True)
class TableConfig:
    """Configuration for a database table."""

    table: str
    columns: str
    timestamp_col: str
    model: Type[Any]


# Table configurations - defines select columns for each table
COMMANDS_CONFIG = TableConfig(
    table="security_commands",
    columns="""id, file_id, session_id, tool, command, 
               risk_score, risk_level, risk_reason, command_timestamp, scanned_at,
               COALESCE(mitre_techniques, '[]'), 
               COALESCE(edr_sequence_bonus, 0), 
               COALESCE(edr_correlation_bonus, 0)""",
    timestamp_col="command_timestamp",
    model=AuditedCommand,
)

READS_CONFIG = TableConfig(
    table="security_file_reads",
    columns="""id, file_id, session_id, file_path, 
               risk_score, risk_level, risk_reason, read_timestamp, scanned_at,
               COALESCE(mitre_techniques, '[]'), 
               COALESCE(edr_sequence_bonus, 0), 
               COALESCE(edr_correlation_bonus, 0)""",
    timestamp_col="read_timestamp",
    model=AuditedFileRead,
)

WRITES_CONFIG = TableConfig(
    table="security_file_writes",
    columns="""id, file_id, session_id, file_path, operation,
               risk_score, risk_level, risk_reason, write_timestamp, scanned_at,
               COALESCE(mitre_techniques, '[]'), 
               COALESCE(edr_sequence_bonus, 0), 
               COALESCE(edr_correlation_bonus, 0)""",
    timestamp_col="write_timestamp",
    model=AuditedFileWrite,
)

WEBFETCHES_CONFIG = TableConfig(
    table="security_webfetches",
    columns="""id, file_id, session_id, url,
               risk_score, risk_level, risk_reason, fetch_timestamp, scanned_at,
               COALESCE(mitre_techniques, '[]'), 
               COALESCE(edr_sequence_bonus, 0), 
               COALESCE(edr_correlation_bonus, 0)""",
    timestamp_col="fetch_timestamp",
    model=AuditedWebFetch,
)


class SecurityDatabase:
    """DuckDB repository for security audit data.

    All security data is stored in the unified analytics.duckdb database.
    """

    # Storage path for part files
    STORAGE_PATH = Path.home() / ".local/share/opencode/storage/part"

    def __init__(self, db: Optional["AnalyticsDB"] = None):
        """Initialize with optional injected DuckDB connection.

        Args:
            db: Optional AnalyticsDB instance. If None, creates one lazily.
                Pass a mock or in-memory DB for testing.
        """
        self._db: Optional["AnalyticsDB"] = db
        self._owns_db = db is None

    def _get_db(self) -> "AnalyticsDB":
        """Get or create DuckDB connection (lazy initialization)."""
        if self._db is None:
            from ...analytics.db import AnalyticsDB

            self._db = AnalyticsDB()
            self._owns_db = True
        return self._db

    def _get_connection(self):
        """Get DuckDB connection."""
        return self._get_db().connect()

    def close(self) -> None:
        """Close the DuckDB connection if we own it."""
        if self._db is not None and self._owns_db:
            self._db.close()
            self._db = None

    # ===== Generic Query Methods =====

    def _get_by_level(
        self, config: TableConfig, levels: List[str], limit: int = 50
    ) -> List[Any]:
        """Generic method to get records by risk levels."""
        if config.table not in _ALLOWED_TABLES:
            return []

        conn = self._get_connection()
        placeholders = ",".join(["?" for _ in levels])
        # Table/columns from validated TableConfig
        result = conn.execute(
            f"""
            SELECT {config.columns}
            FROM {config.table} WHERE risk_level IN ({placeholders})
            ORDER BY risk_score DESC, {config.timestamp_col} DESC LIMIT ?
            """,  # nosec B608
            [*levels, limit],
        ).fetchall()
        return [config.model(*row) for row in result]

    def _get_all(
        self, config: TableConfig, limit: int = 100, offset: int = 0
    ) -> List[Any]:
        """Generic method to get all records with pagination."""
        if config.table not in _ALLOWED_TABLES:
            return []

        conn = self._get_connection()
        result = conn.execute(
            f"""
            SELECT {config.columns}
            FROM {config.table} ORDER BY {config.timestamp_col} DESC 
            LIMIT ? OFFSET ?
            """,  # nosec B608
            [limit, offset],
        ).fetchall()
        return [config.model(*row) for row in result]

    # ===== Insert Methods =====

    def _generate_id(self) -> str:
        """Generate a unique ID for a record."""
        return f"sec_{uuid.uuid4().hex[:12]}"

    def _execute_insert(
        self, table: str, columns: str, placeholders: str, values: tuple
    ) -> bool:
        """Execute an INSERT statement."""
        if table not in _ALLOWED_TABLES:
            return False

        conn = self._get_connection()
        try:
            conn.execute(
                f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})",  # nosec B608
                values,
            )
            return True
        except Exception as e:
            debug(f"Insert error: {e}")
            return False

    def insert_command(self, data: Dict[str, Any]) -> bool:
        """Insert a command record."""
        mitre_json = serialize_mitre_techniques(data.get("mitre_techniques", []))
        values = (
            self._generate_id(),
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
            mitre_json,
            data.get("edr_sequence_bonus", 0),
            data.get("edr_correlation_bonus", 0),
        )
        return self._execute_insert(
            "security_commands",
            "id, file_id, content_hash, session_id, tool, command, risk_score, risk_level, risk_reason, command_timestamp, scanned_at, mitre_techniques, edr_sequence_bonus, edr_correlation_bonus",
            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?",
            values,
        )

    def insert_read(self, data: Dict[str, Any]) -> bool:
        """Insert a file read record."""
        mitre_json = serialize_mitre_techniques(data.get("mitre_techniques", []))
        values = (
            self._generate_id(),
            data["file_id"],
            data["content_hash"],
            data["session_id"],
            data["file_path"],
            data["risk_score"],
            data["risk_level"],
            data["risk_reason"],
            data["timestamp"],
            data["scanned_at"],
            mitre_json,
            data.get("edr_sequence_bonus", 0),
            data.get("edr_correlation_bonus", 0),
        )
        return self._execute_insert(
            "security_file_reads",
            "id, file_id, content_hash, session_id, file_path, risk_score, risk_level, risk_reason, read_timestamp, scanned_at, mitre_techniques, edr_sequence_bonus, edr_correlation_bonus",
            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?",
            values,
        )

    def insert_write(self, data: Dict[str, Any]) -> bool:
        """Insert a file write/edit record."""
        mitre_json = serialize_mitre_techniques(data.get("mitre_techniques", []))
        values = (
            self._generate_id(),
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
            mitre_json,
            data.get("edr_sequence_bonus", 0),
            data.get("edr_correlation_bonus", 0),
        )
        return self._execute_insert(
            "security_file_writes",
            "id, file_id, content_hash, session_id, file_path, operation, risk_score, risk_level, risk_reason, write_timestamp, scanned_at, mitre_techniques, edr_sequence_bonus, edr_correlation_bonus",
            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?",
            values,
        )

    def insert_webfetch(self, data: Dict[str, Any]) -> bool:
        """Insert a webfetch record."""
        mitre_json = serialize_mitre_techniques(data.get("mitre_techniques", []))
        values = (
            self._generate_id(),
            data["file_id"],
            data["content_hash"],
            data["session_id"],
            data["url"],
            data["risk_score"],
            data["risk_level"],
            data["risk_reason"],
            data["timestamp"],
            data["scanned_at"],
            mitre_json,
            data.get("edr_sequence_bonus", 0),
            data.get("edr_correlation_bonus", 0),
        )
        return self._execute_insert(
            "security_webfetches",
            "id, file_id, content_hash, session_id, url, risk_score, risk_level, risk_reason, fetch_timestamp, scanned_at, mitre_techniques, edr_sequence_bonus, edr_correlation_bonus",
            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?",
            values,
        )

    # ===== Query Methods =====

    def get_all_scanned_ids(self) -> set[str]:
        """Get all scanned file IDs from all tables."""
        conn = self._get_connection()
        ids: set[str] = set()
        for table in _ALLOWED_TABLES:
            try:
                result = conn.execute(f"SELECT file_id FROM {table}").fetchall()  # nosec B608
                ids.update(row[0] for row in result)
            except Exception:
                pass
        return ids

    def get_stats(self) -> Dict[str, int]:
        """Get statistics from all tables."""
        conn = self._get_connection()
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

        try:
            # Load scan stats
            result = conn.execute(
                "SELECT total_files_scanned, total_commands FROM security_stats WHERE id=1"
            ).fetchone()
            if result:
                stats["total_scanned"] = result[0] or 0
                stats["total_commands"] = result[1] or 0

            # Count by risk level for each table
            table_prefixes = [
                ("security_commands", ""),
                ("security_file_reads", "reads_"),
                ("security_file_writes", "writes_"),
                ("security_webfetches", "webfetches_"),
            ]
            for table, prefix in table_prefixes:
                result = conn.execute(
                    f"SELECT risk_level, COUNT(*) FROM {table} GROUP BY risk_level"  # nosec B608
                ).fetchall()
                for level, count in result:
                    key = f"{prefix}{level}" if prefix else level
                    if key in stats:
                        stats[key] = count

            # Count totals
            stats["total_reads"] = conn.execute(
                "SELECT COUNT(*) FROM security_file_reads"
            ).fetchone()[0]
            stats["total_writes"] = conn.execute(
                "SELECT COUNT(*) FROM security_file_writes"
            ).fetchone()[0]
            stats["total_webfetches"] = conn.execute(
                "SELECT COUNT(*) FROM security_webfetches"
            ).fetchone()[0]

            # EDR stats
            stats["edr_sequences"] = 0
            stats["edr_correlations"] = 0
            stats["mitre_tagged"] = 0

            for table in _ALLOWED_TABLES:
                try:
                    stats["edr_sequences"] += conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE edr_sequence_bonus > 0"  # nosec B608
                    ).fetchone()[0]
                    stats["edr_correlations"] += conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE edr_correlation_bonus > 0"  # nosec B608
                    ).fetchone()[0]
                    stats["mitre_tagged"] += conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE mitre_techniques != '[]' AND mitre_techniques IS NOT NULL"  # nosec B608
                    ).fetchone()[0]
                except Exception:
                    pass

        except Exception as e:
            debug(f"Error getting stats: {e}")

        return stats

    def update_scan_stats(
        self, total_scanned: int, total_commands: int, last_scan: str
    ) -> None:
        """Update scan statistics."""
        conn = self._get_connection()
        conn.execute(
            """
            UPDATE security_stats SET 
                total_files_scanned = ?, total_commands = ?, last_full_scan = ?
            WHERE id = 1
            """,
            [total_scanned, total_commands, last_scan],
        )

    # ===== Public Query Methods (using generics) =====

    def get_commands_by_level(
        self, levels: List[str], limit: int = 50
    ) -> List[AuditedCommand]:
        """Get commands by risk levels."""
        return self._get_by_level(COMMANDS_CONFIG, levels, limit)

    def get_all_commands(
        self, limit: int = 100, offset: int = 0
    ) -> List[AuditedCommand]:
        """Get all commands with pagination."""
        return self._get_all(COMMANDS_CONFIG, limit, offset)

    def get_reads_by_level(
        self, levels: List[str], limit: int = 50
    ) -> List[AuditedFileRead]:
        """Get file reads by risk levels."""
        return self._get_by_level(READS_CONFIG, levels, limit)

    def get_all_reads(self, limit: int = 10000) -> List[AuditedFileRead]:
        """Get all file reads."""
        return self._get_all(READS_CONFIG, limit, 0)

    def get_writes_by_level(
        self, levels: List[str], limit: int = 50
    ) -> List[AuditedFileWrite]:
        """Get file writes by risk levels."""
        return self._get_by_level(WRITES_CONFIG, levels, limit)

    def get_all_writes(self, limit: int = 10000) -> List[AuditedFileWrite]:
        """Get all file writes."""
        return self._get_all(WRITES_CONFIG, limit, 0)

    def get_webfetches_by_level(
        self, levels: List[str], limit: int = 50
    ) -> List[AuditedWebFetch]:
        """Get webfetches by risk levels."""
        return self._get_by_level(WEBFETCHES_CONFIG, levels, limit)

    def get_all_webfetches(self, limit: int = 10000) -> List[AuditedWebFetch]:
        """Get all webfetches."""
        return self._get_all(WEBFETCHES_CONFIG, limit, 0)

    # ===== Security Scanner Methods (merged from SecurityScannerDuckDB) =====

    @staticmethod
    def _extract_part_id(file_path: Path) -> str:
        """Extract part_id from file path."""
        return file_path.stem

    def get_unscanned_files(self, limit: int = 1000) -> List[Path]:
        """Get files from parts table that haven't been security scanned."""
        conn = self._get_connection()
        result = conn.execute(
            """
            SELECT p.id as part_id, p.message_id
            FROM parts p
            LEFT JOIN security_scanned s ON p.id = s.part_id
            WHERE s.part_id IS NULL
            ORDER BY p.created_at DESC
            LIMIT ?
            """,
            [limit],
        ).fetchall()

        paths = []
        for part_id, message_id in result:
            if message_id:
                path = self.STORAGE_PATH / message_id / f"{part_id}.json"
                paths.append(path)
        return paths

    def mark_scanned(self, file_path: Path) -> None:
        """Mark a single file as scanned."""
        conn = self._get_connection()
        part_id = self._extract_part_id(file_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO security_scanned (part_id, scanned_at)
            VALUES (?, CURRENT_TIMESTAMP)
            """,
            [part_id],
        )

    def mark_scanned_batch(self, file_paths: List[Path]) -> int:
        """Mark multiple files as scanned in a single batch."""
        if not file_paths:
            return 0

        conn = self._get_connection()
        records = [(self._extract_part_id(p),) for p in file_paths]
        conn.executemany(
            """
            INSERT OR REPLACE INTO security_scanned (part_id, scanned_at)
            VALUES (?, CURRENT_TIMESTAMP)
            """,
            records,
        )
        return len(records)

    def get_scanned_count(self) -> int:
        """Get count of files already scanned."""
        conn = self._get_connection()
        result = conn.execute("SELECT COUNT(*) FROM security_scanned").fetchone()
        return result[0] if result else 0

    def clear_scanned(self) -> None:
        """Clear all scanned records (for testing/reset)."""
        conn = self._get_connection()
        conn.execute("DELETE FROM security_scanned")
        debug("[SecurityDatabase] Cleared security_scanned table")


# Backwards compatibility alias
SecurityScannerDuckDB = SecurityDatabase
