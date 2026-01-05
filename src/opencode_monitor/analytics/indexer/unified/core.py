"""
Core UnifiedIndexer class and global instance management.

This module contains the main orchestrator class that combines
real-time file watching with progressive backfill.
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from ...db import AnalyticsDB
from ..tracker import FileTracker
from ..parsers import FileParser
from ..trace_builder import TraceBuilder
from ..watcher import FileWatcher, ProcessingQueue
from ....utils.logger import debug, info

from .config import (
    OPENCODE_STORAGE,
    BACKFILL_BATCH_SIZE,
    BACKFILL_INTERVAL,
)
from .batch import BatchProcessor
from .processing import FileProcessor


class UnifiedIndexer:
    """Unified indexer for OpenCode storage.

    Combines real-time file watching with progressive backfill
    to maintain an up-to-date analytics database.

    Usage:
        indexer = UnifiedIndexer()
        indexer.start()
        # ... indexer runs in background ...
        indexer.stop()
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        db_path: Optional[Path] = None,
    ):
        """Initialize the indexer.

        Args:
            storage_path: Path to OpenCode storage (default: ~/.local/share/opencode/storage)
            db_path: Path to analytics database (default: ~/.config/opencode-monitor/analytics.duckdb)
        """
        self._storage_path = storage_path or OPENCODE_STORAGE
        self._db = AnalyticsDB(db_path)

        # Components
        self._tracker = FileTracker(self._db)
        self._parser = FileParser()
        self._trace_builder = TraceBuilder(self._db)
        self._queue = ProcessingQueue()
        self._watcher: Optional[FileWatcher] = None

        # Threads
        self._processor_thread: Optional[threading.Thread] = None
        self._backfill_thread: Optional[threading.Thread] = None

        # State
        self._running = False
        self._lock = threading.Lock()

        # Statistics
        self._stats = {
            "files_processed": 0,
            "files_skipped": 0,
            "files_error": 0,
            "sessions_indexed": 0,
            "messages_indexed": 0,
            "parts_indexed": 0,
            "traces_created": 0,
            "backfill_cycles": 0,
            "last_backfill": None,
            "start_time": None,
        }

        # Processors (initialized with shared stats)
        self._batch_processor = BatchProcessor(
            self._db,
            self._parser,
            self._tracker,
            self._trace_builder,
            self._stats,
        )
        self._file_processor = FileProcessor(
            self._db,
            self._parser,
            self._tracker,
            self._trace_builder,
            self._stats,
        )

    def start(self) -> None:
        """Start the indexer (watcher + backfill + processor)."""
        if self._running:
            return

        self._running = True
        self._stats["start_time"] = datetime.now().isoformat()

        info("[UnifiedIndexer] Starting...")
        info(f"[UnifiedIndexer] Storage path: {self._storage_path}")
        info(
            f"[UnifiedIndexer] Batch size: {BACKFILL_BATCH_SIZE}, Interval: {BACKFILL_INTERVAL}s"
        )

        # Connect to database
        self._db.connect()
        info("[UnifiedIndexer] Database connected")

        # Start watcher
        self._watcher = FileWatcher(
            self._storage_path,
            self._on_file_detected,
        )
        self._watcher.start()
        info("[UnifiedIndexer] File watcher started")

        # Start queue processor thread
        self._processor_thread = threading.Thread(
            target=self._process_queue_loop,
            daemon=True,
            name="indexer-processor",
        )
        self._processor_thread.start()

        # Start backfill thread
        self._backfill_thread = threading.Thread(
            target=self._backfill_loop,
            daemon=True,
            name="indexer-backfill",
        )
        self._backfill_thread.start()

        info("[UnifiedIndexer] All threads started - beginning indexation")

    def stop(self) -> None:
        """Stop the indexer."""
        self._running = False

        if self._watcher:
            self._watcher.stop()

        if self._processor_thread:
            self._processor_thread.join(timeout=5)

        if self._backfill_thread:
            self._backfill_thread.join(timeout=5)

        self._db.close()
        info("[UnifiedIndexer] Stopped")

    def _on_file_detected(self, file_type: str, path: Path) -> None:
        """Callback when watcher detects a file change.

        Args:
            file_type: Type of file (session, message, part, etc.)
            path: Path to the file
        """
        self._queue.put(file_type, path)

    def _process_queue_loop(self) -> None:
        """Process files from the queue continuously."""
        while self._running:
            batch = self._queue.get_batch(max_items=50, timeout=0.1)
            if not batch:
                continue

            for file_type, path in batch:
                if not self._running:
                    break
                self._file_processor.process_file(file_type, path)

    def _backfill_loop(self) -> None:
        """Run backfill periodically to catch missed files."""
        # Initial backfill immediately
        time.sleep(1)  # Wait for watcher to start
        if self._running:
            info("[UnifiedIndexer] Running initial backfill...")
            self._run_backfill()

        # Then periodic backfill
        while self._running:
            time.sleep(BACKFILL_INTERVAL)
            if self._running:
                self._run_backfill()

    def _run_backfill(self) -> None:
        """Run a backfill cycle for unindexed files.

        Uses batch INSERT for high performance.
        """
        start_time = time.time()
        total_processed = 0
        cycle_num = self._stats.get("backfill_cycles", 0) + 1

        for file_type in ["session", "message", "part", "todo", "project"]:
            if not self._running:
                break

            directory = self._storage_path / file_type
            scan_start = time.time()
            unindexed = self._tracker.get_unindexed_files(
                directory, file_type, limit=BACKFILL_BATCH_SIZE
            )
            scan_time = time.time() - scan_start

            if not unindexed:
                continue

            info(
                f"[Backfill #{cycle_num}] {file_type}: "
                f"found {len(unindexed)} files (scan: {scan_time:.2f}s)"
            )

            # Batch process files
            process_start = time.time()
            processed_count = self._batch_process_files(file_type, unindexed)
            process_time = time.time() - process_start

            total_processed += processed_count
            files_per_sec = processed_count / process_time if process_time > 0 else 0

            info(
                f"[Backfill #{cycle_num}] {file_type}: "
                f"{processed_count} files in {process_time:.1f}s ({files_per_sec:.0f}/s) | "
                f"Parts: {self._stats.get('parts_indexed', 0)} | "
                f"Traces: {self._stats.get('traces_created', 0)}"
            )

        elapsed = time.time() - start_time
        self._stats["backfill_cycles"] = cycle_num
        self._stats["last_backfill"] = datetime.now().isoformat()

        if total_processed > 0:
            # Update root trace agents from messages (root traces created with user type)
            updated_agents = self._trace_builder.update_root_trace_agents()
            if updated_agents > 0:
                debug(
                    f"[Backfill #{cycle_num}] Updated {updated_agents} root trace agents"
                )

            # Create conversation segments for sessions with multiple agents
            segments_created = self._trace_builder.analyze_all_sessions_for_segments()
            if segments_created > 0:
                debug(
                    f"[Backfill #{cycle_num}] Created {segments_created} conversation segments"
                )

            # Resolve parent traces after processing new data
            resolved = self._trace_builder.resolve_parent_traces()
            if resolved > 0:
                debug(f"[Backfill #{cycle_num}] Resolved {resolved} parent traces")

            speed = total_processed / elapsed if elapsed > 0 else 0
            info(
                f"[Backfill #{cycle_num}] DONE: {total_processed} files in {elapsed:.1f}s ({speed:.0f}/s) | "
                f"Sessions: {self._stats.get('sessions_indexed', 0)} | "
                f"Messages: {self._stats.get('messages_indexed', 0)} | "
                f"Parts: {self._stats.get('parts_indexed', 0)} | "
                f"Traces: {self._stats.get('traces_created', 0)}"
            )
        else:
            info(f"[Backfill #{cycle_num}] No new files to index ({elapsed:.1f}s)")

    def _batch_process_files(self, file_type: str, files: list[Path]) -> int:
        """Process files in batch with bulk INSERT.

        Args:
            file_type: Type of files to process
            files: List of file paths

        Returns:
            Number of files successfully processed
        """
        # Try batch processing first
        count = self._batch_processor.process_files(file_type, files)
        if count > 0 or file_type in ("session", "message", "part"):
            return count

        # Fallback to individual processing for todo/project
        for path in files:
            if self._file_processor.process_file(file_type, path):
                count += 1
        return count

    def _process_file(self, file_type: str, path: Path) -> bool:
        """Process a single file (delegate to FileProcessor).

        This method is kept for backward compatibility with tests.

        Args:
            file_type: Type of file
            path: Path to the file

        Returns:
            True if processed successfully, False otherwise
        """
        return self._file_processor.process_file(file_type, path)

    def get_stats(self) -> dict:
        """Get indexer statistics.

        Returns:
            Dict with all statistics
        """
        with self._lock:
            stats = self._stats.copy()

        # Add component stats
        stats["tracker"] = self._tracker.get_stats()
        stats["traces"] = self._trace_builder.get_stats()
        stats["queue_size"] = self._queue.size

        if self._watcher:
            stats["watcher"] = self._watcher.get_stats()

        return stats

    def force_backfill(self) -> dict:
        """Force an immediate backfill cycle.

        Can be called without start() for one-shot indexing.

        Returns:
            Statistics from the backfill
        """
        # Ensure DB is connected for standalone use
        self._db.connect()

        # Temporarily enable running flag so _run_backfill doesn't skip
        was_running = self._running
        self._running = True

        try:
            before = self._stats["files_processed"]
            self._run_backfill()
            after = self._stats["files_processed"]

            return {
                "files_processed": after - before,
                "total_files": self._stats["files_processed"],
            }
        finally:
            # Restore original state
            self._running = was_running

    def resolve_parent_traces(self) -> int:
        """Resolve parent_trace_id for all traces.

        Returns:
            Number of traces updated
        """
        return self._trace_builder.resolve_parent_traces()


# Global instance
_indexer: Optional[UnifiedIndexer] = None


def get_indexer() -> UnifiedIndexer:
    """Get or create the global indexer instance."""
    global _indexer
    if _indexer is None:
        _indexer = UnifiedIndexer()
    return _indexer


def start_indexer() -> None:
    """Start the global indexer."""
    get_indexer().start()


def stop_indexer() -> None:
    """Stop the global indexer."""
    global _indexer
    if _indexer:
        _indexer.stop()
        _indexer = None
