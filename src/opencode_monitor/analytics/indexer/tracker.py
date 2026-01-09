"""
File change tracker for efficient indexing.

Uses mtime + size comparison to detect file changes and skip
already-indexed files. Persists tracking info in a file_index table.

Performance:
- O(1) lookup per file via DB index
- Avoids re-reading unchanged files
- Persists across restarts
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..db import AnalyticsDB
from ...utils.logger import debug


@dataclass
class FileInfo:
    """File metadata for change detection."""

    file_path: str
    file_type: str  # session, message, part, todo, project
    mtime: float
    size: int
    record_id: Optional[str] = None
    indexed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    status: str = "indexed"  # indexed, error, pending


class FileTracker:
    """Tracks indexed files to detect changes.

    Uses mtime + size for fast change detection without reading file contents.
    Persists tracking info in the database for cross-restart persistence.
    """

    def __init__(self, db: AnalyticsDB):
        """Initialize the file tracker.

        Args:
            db: Database instance for persisting file index
        """
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create the file_index table if it doesn't exist."""
        conn = self._db.connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_index (
                file_path VARCHAR PRIMARY KEY,
                file_type VARCHAR NOT NULL,
                mtime DOUBLE NOT NULL,
                size INTEGER NOT NULL,
                record_id VARCHAR,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error_message VARCHAR,
                status VARCHAR DEFAULT 'indexed'
            )
        """)

        # Migration: add status column to existing tables (US-1)
        try:
            result = conn.execute(
                "SELECT * FROM information_schema.columns "
                "WHERE table_name = 'file_index' AND column_name = 'status'"
            ).fetchone()
            if result is None:
                conn.execute(
                    "ALTER TABLE file_index ADD COLUMN status VARCHAR DEFAULT 'indexed'"
                )
                debug("[FileTracker] Added status column via migration")
        except Exception:
            pass  # Column already exists or table doesn't exist yet

        # Indexes for efficient queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_index_type
            ON file_index(file_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_index_mtime
            ON file_index(mtime DESC)
        """)
        # Index for status queries (US-1: reconciliation support)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_index_status
            ON file_index(status)
        """)
        debug("[FileTracker] file_index table ensured")

    def needs_indexing(self, path: Path | str) -> bool:
        """Check if a file needs (re)indexing based on mtime and size.

        Fast check that avoids reading file contents.

        Args:
            path: Path to the file to check (accepts Path or str)

        Returns:
            True if file needs indexing (new or changed), False otherwise
        """
        # Convert str to Path for compatibility
        path = Path(path) if isinstance(path, str) else path

        if not path.exists():
            return False

        try:
            stat = path.stat()
            current_mtime = stat.st_mtime
            current_size = stat.st_size
        except OSError:
            return False

        conn = self._db.connect()
        result = conn.execute(
            """
            SELECT mtime, size FROM file_index
            WHERE file_path = ?
            """,
            [str(path)],
        ).fetchone()

        if result is None:
            # File not in index -> needs indexing
            return True

        stored_mtime, stored_size = result
        # Changed if mtime OR size differs
        return current_mtime != stored_mtime or current_size != stored_size

    def get_file_info(self, path: Path) -> Optional[FileInfo]:
        """Get stored info for a file.

        Args:
            path: Path to the file

        Returns:
            FileInfo if file is in index, None otherwise
        """
        conn = self._db.connect()
        result = conn.execute(
            """
            SELECT file_path, file_type, mtime, size, record_id, indexed_at, error_message, status
            FROM file_index WHERE file_path = ?
            """,
            [str(path)],
        ).fetchone()

        if result is None:
            return None

        return FileInfo(
            file_path=result[0],
            file_type=result[1],
            mtime=result[2],
            size=result[3],
            record_id=result[4],
            indexed_at=result[5],
            error_message=result[6],
            status=result[7] or "indexed",
        )

    def mark_indexed(
        self,
        path: Path,
        file_type: str,
        record_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Mark a file as indexed with its current mtime and size.

        Args:
            path: Path to the file
            file_type: Type of file (session, message, part, todo, project)
            record_id: ID of the created/updated record
            error_message: Error message if indexing failed
        """
        try:
            stat = path.stat()
            mtime = stat.st_mtime
            size = stat.st_size
        except OSError:
            return

        conn = self._db.connect()
        now = datetime.now()
        conn.execute(
            """
            INSERT INTO file_index
            (file_path, file_type, mtime, size, record_id, indexed_at, error_message, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'indexed')
            ON CONFLICT (file_path) DO UPDATE SET
                file_type = EXCLUDED.file_type,
                mtime = EXCLUDED.mtime,
                size = EXCLUDED.size,
                record_id = EXCLUDED.record_id,
                indexed_at = EXCLUDED.indexed_at,
                error_message = EXCLUDED.error_message,
                status = 'indexed'
            """,
            [str(path), file_type, mtime, size, record_id, now, error_message],
        )

    def mark_error(self, path: Path, file_type: str, error: str) -> None:
        """Mark a file as having an indexing error.

        The file's mtime/size are still stored so we don't retry unchanged
        files that consistently fail. Sets status='error'.

        Args:
            path: Path to the file
            file_type: Type of file
            error: Error message describing the failure
        """
        try:
            stat = path.stat()
            mtime = stat.st_mtime
            size = stat.st_size
        except OSError:
            return

        conn = self._db.connect()
        now = datetime.now()
        conn.execute(
            """
            INSERT INTO file_index
            (file_path, file_type, mtime, size, record_id, indexed_at, error_message, status)
            VALUES (?, ?, ?, ?, NULL, ?, ?, 'error')
            ON CONFLICT (file_path) DO UPDATE SET
                file_type = EXCLUDED.file_type,
                mtime = EXCLUDED.mtime,
                size = EXCLUDED.size,
                record_id = NULL,
                indexed_at = EXCLUDED.indexed_at,
                error_message = EXCLUDED.error_message,
                status = 'error'
            """,
            [str(path), file_type, mtime, size, now, error],
        )

    def mark_indexed_batch(
        self,
        items: list[tuple[Path, str, str | None]],
    ) -> int:
        """Mark multiple files as indexed in a single batch INSERT.

        Much faster than individual mark_indexed calls for large batches.
        Sets status='indexed' for all files.

        Args:
            items: List of (path, file_type, record_id) tuples

        Returns:
            Number of files successfully marked
        """
        if not items:
            return 0

        records = []
        for path, file_type, record_id in items:
            try:
                stat = path.stat()
                records.append(
                    (
                        str(path),
                        file_type,
                        stat.st_mtime,
                        stat.st_size,
                        record_id,
                        None,  # error_message
                        "indexed",  # status
                    )
                )
            except OSError:
                continue

        if not records:
            return 0

        conn = self._db.connect()
        conn.executemany(
            """
            INSERT INTO file_index
            (file_path, file_type, mtime, size, record_id, error_message, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (file_path) DO UPDATE SET
                file_type = EXCLUDED.file_type,
                mtime = EXCLUDED.mtime,
                size = EXCLUDED.size,
                record_id = EXCLUDED.record_id,
                error_message = EXCLUDED.error_message,
                status = EXCLUDED.status
            """,
            records,
        )
        return len(records)

    def mark_pending(self, paths: list[Path], file_type: str) -> int:
        """Mark multiple files as pending processing.

        Used for reconciliation to mark files that need to be processed.
        Sets status='pending' for all specified files.

        Args:
            paths: List of file paths to mark as pending
            file_type: Type of files (session, message, part, todo, project)

        Returns:
            Number of files successfully marked as pending
        """
        if not paths:
            return 0

        records = []
        for path in paths:
            try:
                stat = path.stat()
                records.append(
                    (
                        str(path),
                        file_type,
                        stat.st_mtime,
                        stat.st_size,
                        None,  # record_id (not yet processed)
                        None,  # error_message
                        "pending",  # status
                    )
                )
            except OSError:
                continue

        if not records:
            return 0

        conn = self._db.connect()
        conn.executemany(
            """
            INSERT INTO file_index
            (file_path, file_type, mtime, size, record_id, error_message, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (file_path) DO UPDATE SET
                file_type = EXCLUDED.file_type,
                mtime = EXCLUDED.mtime,
                size = EXCLUDED.size,
                record_id = EXCLUDED.record_id,
                error_message = EXCLUDED.error_message,
                status = EXCLUDED.status
            """,
            records,
        )
        return len(records)

    def get_unindexed_files(
        self,
        directory: Path,
        file_type: str,
        limit: int = 100,
        max_mtime: Optional[float] = None,
        only_new: bool = False,
    ) -> list[Path]:
        """Get files not yet indexed or changed since last indexing.

        Efficiently finds files needing indexing by comparing filesystem
        with database index.

        Args:
            max_mtime: If provided, only include files with mtime <= this value.
                      Used by backfill to ignore files created after indexer start.
            only_new: If True, only return files that have NEVER been indexed.
                     Ignores modified files. Used by backfill to avoid
                     re-processing files that the watcher should handle.

        Args:
            directory: Directory to scan
            file_type: Type of files to look for
            limit: Maximum number of files to return

        Returns:
            List of paths needing indexing, sorted by mtime DESC (recent first)
        """
        if not directory.exists():
            return []

        # Collect all JSON files with their mtime
        files_with_mtime: list[tuple[float, Path]] = []

        if file_type in ("todo", "project"):
            # Flat directory (no subdirs)
            for json_file in directory.glob("*.json"):
                try:
                    mtime = json_file.stat().st_mtime
                    files_with_mtime.append((mtime, json_file))
                except OSError:
                    continue
        else:
            # Nested directory structure (project_id/file.json)
            for subdir in directory.iterdir():
                if not subdir.is_dir():
                    continue
                for json_file in subdir.glob("*.json"):
                    try:
                        mtime = json_file.stat().st_mtime
                        files_with_mtime.append((mtime, json_file))
                    except OSError:
                        continue

        # Filter by max_mtime if provided (backfill cutoff)
        if max_mtime is not None:
            files_with_mtime = [(m, p) for m, p in files_with_mtime if m <= max_mtime]

        # Sort by mtime DESC (most recent first)
        files_with_mtime.sort(key=lambda x: x[0], reverse=True)

        # Load ALL indexed files for this type in ONE query (much faster than per-file)
        conn = self._db.connect()
        indexed_files = {}
        try:
            rows = conn.execute(
                """
                SELECT file_path, mtime, size FROM file_index
                WHERE file_type = ?
                """,
                [file_type],
            ).fetchall()
            for row in rows:
                indexed_files[row[0]] = (row[1], row[2])
        finally:
            pass  # Connection managed by pool

        # Filter to only files needing indexing (in-memory comparison)
        unindexed: list[Path] = []
        for mtime, path in files_with_mtime:
            if len(unindexed) >= limit:
                break
            path_str = str(path)
            if path_str not in indexed_files:
                # New file - needs indexing
                unindexed.append(path)
            elif not only_new:
                # Check if changed (only if we're not in "only_new" mode)
                # In only_new mode, we skip modified files - watcher handles those
                stored_mtime, stored_size = indexed_files[path_str]
                try:
                    current_size = path.stat().st_size
                    if mtime != stored_mtime or current_size != stored_size:
                        unindexed.append(path)
                except OSError:
                    continue

        return unindexed

    def get_stats(self) -> dict:
        """Get indexing statistics.

        Returns:
            Dict with counts by file type and error stats
        """
        conn = self._db.connect()

        # Count by type
        type_counts = conn.execute("""
            SELECT file_type, COUNT(*) as count
            FROM file_index
            GROUP BY file_type
        """).fetchall()

        # Count errors
        error_result = conn.execute("""
            SELECT COUNT(*) FROM file_index
            WHERE error_message IS NOT NULL
        """).fetchone()
        error_count = error_result[0] if error_result else 0

        # Total count
        total_result = conn.execute("SELECT COUNT(*) FROM file_index").fetchone()
        total = total_result[0] if total_result else 0

        return {
            "total_files": total,
            "by_type": {row[0]: row[1] for row in type_counts if row},
            "errors": error_count,
        }

    def clear(self) -> None:
        """Clear all tracking data (for testing/reset)."""
        conn = self._db.connect()
        conn.execute("DELETE FROM file_index")
        debug("[FileTracker] Cleared file_index table")
