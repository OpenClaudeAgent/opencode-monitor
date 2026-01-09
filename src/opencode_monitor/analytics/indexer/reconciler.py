"""
Reconciler - US-3: Periodic filesystem scan for missed files.

Scans the filesystem periodically to detect files missed by watchdog
and sends them to the FileBatchAccumulator for processing.

Features:
- Periodic background scanning (configurable interval)
- DuckDB glob() for fast filesystem enumeration
- Detects new files (not in file_index)
- Detects modified files (mtime > indexed mtime)
- Thread-safe start/stop lifecycle
- Callback for found files (non-blocking)

Performance target: < 1s for 100k files using DuckDB glob()
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional
import threading
import time

from ..db import AnalyticsDB
from ...utils.logger import debug


@dataclass
class ReconcilerConfig:
    """Configuration for Reconciler.

    Attributes:
        interval_seconds: Seconds between periodic scans.
        max_files_per_scan: Safety limit for files per scan.
    """

    interval_seconds: int = 30
    max_files_per_scan: int = 10000


@dataclass
class ReconcilerStats:
    """Statistics for Reconciler.

    Attributes:
        scans_completed: Total scans completed.
        files_found: Total files found across all scans.
        last_scan_duration_ms: Duration of last scan in milliseconds.
        last_scan_files: Files found in last scan.
    """

    scans_completed: int = 0
    files_found: int = 0
    last_scan_duration_ms: float = 0
    last_scan_files: int = 0


class Reconciler:
    """Periodic filesystem scanner for missed files.

    Scans the storage directory periodically to find files that were
    missed by the watchdog file watcher (e.g., during restarts, race
    conditions, or filesystem events not captured).

    Thread-safe implementation with background scanning support.

    Example:
        >>> def handle_missing(files: List[Path]) -> None:
        ...     print(f"Found {len(files)} missing files")
        >>>
        >>> config = ReconcilerConfig(interval_seconds=30)
        >>> rec = Reconciler(storage_path, db, config, handle_missing)
        >>> rec.start()  # Start background scanning
        >>> # ... later ...
        >>> rec.stop()   # Stop background scanning
    """

    def __init__(
        self,
        storage_path: Path,
        db: AnalyticsDB,
        config: ReconcilerConfig,
        on_missing_files: Callable[[List[Path]], None],
    ) -> None:
        """Initialize the Reconciler.

        Args:
            storage_path: Root directory to scan for JSON files.
            db: AnalyticsDB instance (reused, not owned).
            config: Reconciler configuration.
            on_missing_files: Callback called with list of missing files.
        """
        self._storage_path = storage_path
        self._db = db
        self._config = config
        self._on_missing_files = on_missing_files

        # Thread safety
        self._lock = threading.Lock()
        self._scan_lock = threading.Lock()  # Serialize scan operations
        self._stopped = True
        self._scan_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Statistics
        self._stats = ReconcilerStats()

    def start(self) -> None:
        """Start periodic background scanning.

        Spawns a daemon thread that scans at the configured interval.
        Safe to call multiple times (idempotent).
        """
        with self._lock:
            if not self._stopped:
                return  # Already running

            self._stopped = False
            self._stop_event.clear()

            self._scan_thread = threading.Thread(
                target=self._periodic_scan_loop,
                daemon=True,
                name="Reconciler-Scanner",
            )
            self._scan_thread.start()
            debug(
                f"[Reconciler] Started periodic scan (interval={self._config.interval_seconds}s)"
            )

    def stop(self) -> None:
        """Stop periodic background scanning.

        Safe to call multiple times (idempotent).
        Safe to call without start().
        """
        with self._lock:
            if self._stopped:
                return  # Already stopped

            self._stopped = True
            self._stop_event.set()

            if self._scan_thread is not None:
                # Wait for thread to finish (with timeout)
                self._scan_thread.join(timeout=2.0)
                self._scan_thread = None

            debug("[Reconciler] Stopped periodic scan")

    def scan_now(self) -> List[Path]:
        """Execute an immediate scan. Blocking/synchronous.

        Scans the filesystem for missing/modified files and calls
        the callback with the results.

        Thread-safe: serializes concurrent scan requests.

        Returns:
            List of missing/modified file paths found.
        """
        # Serialize scans to avoid DuckDB concurrent access issues
        with self._scan_lock:
            start_time = time.time()

            # Find missing files
            missing_files = self._find_missing_files()

            # Update stats
            duration_ms = (time.time() - start_time) * 1000
            with self._lock:
                self._stats.scans_completed += 1
                self._stats.files_found += len(missing_files)
                self._stats.last_scan_duration_ms = duration_ms
                self._stats.last_scan_files = len(missing_files)

            debug(
                f"[Reconciler] Scan completed: {len(missing_files)} files in {duration_ms:.1f}ms"
            )

            # Call callback in separate thread (non-blocking)
            if missing_files:
                callback_thread = threading.Thread(
                    target=self._on_missing_files,
                    args=(missing_files,),
                    daemon=True,
                )
                callback_thread.start()

            return missing_files

    def get_stats(self) -> ReconcilerStats:
        """Get current reconciler statistics.

        Returns:
            ReconcilerStats with current counters.
        """
        with self._lock:
            return ReconcilerStats(
                scans_completed=self._stats.scans_completed,
                files_found=self._stats.files_found,
                last_scan_duration_ms=self._stats.last_scan_duration_ms,
                last_scan_files=self._stats.last_scan_files,
            )

    def _periodic_scan_loop(self) -> None:
        """Background thread loop for periodic scanning."""
        while not self._stop_event.is_set():
            try:
                self.scan_now()
            except Exception as e:
                debug(f"[Reconciler] Scan error: {e}")

            # Wait for next scan or stop signal
            self._stop_event.wait(timeout=self._config.interval_seconds)

    def _find_missing_files(self) -> List[Path]:
        """Find files missing from file_index or modified since indexing.

        Uses DuckDB glob() for efficient filesystem enumeration combined
        with optimized mtime checking for modified files.

        Strategy:
        1. DuckDB glob() + anti-join finds NEW files (O(1) with index)
        2. For MODIFIED files: batch fetch indexed mtimes, limit stat() calls

        Performance: < 1s for 100k files (glob is fast, modified check is bounded)

        Returns:
            List of Path objects for missing/modified files.
        """
        if not self._storage_path.exists():
            return []

        conn = self._db.connect()
        storage_str = str(self._storage_path)
        max_files = self._config.max_files_per_scan

        try:
            # Step 1: Find NEW files using DuckDB anti-join (very fast)
            query_new = f"""
                WITH filesystem AS (
                    SELECT file AS path
                    FROM glob('{storage_str}/**/*.json')
                ),
                indexed AS (
                    SELECT file_path
                    FROM file_index
                )
                SELECT f.path
                FROM filesystem f
                LEFT JOIN indexed i ON f.path = i.file_path
                WHERE i.file_path IS NULL
                LIMIT {max_files}
            """
            new_files_result = conn.execute(query_new).fetchall()
            new_files = [Path(row[0]) for row in new_files_result]

            # Step 2: Find MODIFIED files (mtime changed since indexing)
            remaining_limit = max_files - len(new_files)
            if remaining_limit <= 0:
                return new_files

            # Get indexed files with mtimes - limit to avoid huge memory usage
            # Only check files that exist in current filesystem scan
            query_modified = f"""
                WITH filesystem AS (
                    SELECT file AS path
                    FROM glob('{storage_str}/**/*.json')
                )
                SELECT i.file_path, i.mtime
                FROM file_index i
                INNER JOIN filesystem f ON i.file_path = f.path
                WHERE i.status = 'indexed'
                LIMIT {remaining_limit * 2}
            """
            indexed_result = conn.execute(query_modified).fetchall()

            # Check mtimes in Python (bounded by query limit)
            modified_files: List[Path] = []
            for path_str, stored_mtime in indexed_result:
                if len(modified_files) >= remaining_limit:
                    break
                path = Path(path_str)
                try:
                    if path.stat().st_mtime > stored_mtime:
                        modified_files.append(path)
                except OSError:
                    continue

            return new_files + modified_files

        except Exception as e:
            debug(f"[Reconciler] Query error: {e}")
            return []
