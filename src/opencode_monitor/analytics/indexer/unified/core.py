"""
Core UnifiedIndexer class and global instance management.

This module contains the main orchestrator class that combines
real-time file watching with progressive backfill.

v2 Architecture (Plan 46):
- FileWatcher → FileBatchAccumulator → BatchProcessor (micro-batch)
- Reconciler → FileBatchAccumulator (periodic scan for missed files)
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from ...db import AnalyticsDB, get_analytics_db, get_db_access_lock
from ..tracker import FileTracker
from ..parsers import FileParser
from ..trace_builder import TraceBuilder
from ..watcher import FileWatcher, ProcessingQueue
from ..batch_accumulator import FileBatchAccumulator, AccumulatorConfig
from ..reconciler import Reconciler, ReconcilerConfig
from ....utils.logger import debug, info

from .config import (
    OPENCODE_STORAGE,
    BACKFILL_BATCH_SIZE,
    BACKFILL_INTERVAL,
)
from .batch import BatchProcessor
from .processing import FileProcessor
from .bulk_load import is_cold_start, bulk_load_initial


# Feature flag for v2 architecture
USE_V2_INDEXER = True


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
        # Use shared singleton DB to avoid DuckDB connection conflicts with API
        # DuckDB doesn't allow multiple connections to the same file
        if db_path is None:
            self._db = get_analytics_db()
            self._owns_db = False  # Don't close shared singleton
        else:
            self._db = AnalyticsDB(db_path)
            self._owns_db = True  # We created it, we close it

        # Components
        self._tracker = FileTracker(self._db)
        self._parser = FileParser()
        self._trace_builder = TraceBuilder(self._db)
        self._watcher: Optional[FileWatcher] = None

        # v1 components (kept for backward compatibility)
        self._queue = ProcessingQueue()

        # v2 components (Plan 46)
        self._accumulator: Optional[FileBatchAccumulator] = None
        self._reconciler: Optional[Reconciler] = None

        # Threads (v1 - kept for backward compatibility)
        self._processor_thread: Optional[threading.Thread] = None
        self._backfill_thread: Optional[threading.Thread] = None

        # State
        self._running = False
        self._lock = threading.Lock()

        # Statistics (mixed types: int, str, dict, None)
        self._stats: dict[str, Any] = {
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

        if USE_V2_INDEXER:
            self._start_v2()
        else:
            self._start_v1()

        info("[UnifiedIndexer] All threads started - beginning indexation")

    def _start_v2(self) -> None:
        """Start v2 architecture (Plan 46): Accumulator + Reconciler.

        If cold start detected, performs bulk load first for fast initial indexing.
        """
        info("[UnifiedIndexer] Using v2 architecture (Plan 46)")

        # Check for cold start and perform bulk load if needed
        if is_cold_start(self._db):
            info("[UnifiedIndexer] Cold start detected - using bulk load")
            bulk_results = bulk_load_initial(
                self._db,
                self._storage_path,
                self._stats,
            )
            info(
                f"[UnifiedIndexer] Bulk load complete: "
                f"{bulk_results['sessions']} sessions, "
                f"{bulk_results['messages']} messages, "
                f"{bulk_results['parts']} parts, "
                f"{bulk_results['traces_created']} traces "
                f"in {bulk_results['duration_s']}s"
            )
        else:
            info("[UnifiedIndexer] Warm start - skipping bulk load")

        # Create FileBatchAccumulator with callback to process batches
        # window_ms=200, max_files=200 (validated by POC)
        acc_config = AccumulatorConfig(
            window_ms=200,
            max_files=200,
            flush_on_stop=True,
        )
        self._accumulator = FileBatchAccumulator(
            config=acc_config,
            on_batch_ready=self._on_batch_ready,
        )
        info("[UnifiedIndexer] FileBatchAccumulator created (200ms/200 files)")

        # Create Reconciler with callback to feed accumulator
        rec_config = ReconcilerConfig(
            interval_seconds=BACKFILL_INTERVAL,
            max_files_per_scan=BACKFILL_BATCH_SIZE * 5,  # Allow larger scans
        )
        self._reconciler = Reconciler(
            storage_path=self._storage_path,
            db=self._db,
            config=rec_config,
            on_missing_files=self._on_missing_files,
        )
        info(f"[UnifiedIndexer] Reconciler created (interval={BACKFILL_INTERVAL}s)")

        # Start watcher (feeds accumulator via _on_file_detected)
        self._watcher = FileWatcher(
            self._storage_path,
            self._on_file_detected,
        )
        self._watcher.start()
        info("[UnifiedIndexer] File watcher started")

        # Start reconciler (periodic background scanning)
        self._reconciler.start()
        info("[UnifiedIndexer] Reconciler started")

    def _start_v1(self) -> None:
        """Start v1 architecture (legacy): Queue + Backfill loop."""
        info("[UnifiedIndexer] Using v1 architecture (legacy)")

        # Start watcher
        self._watcher = FileWatcher(
            self._storage_path,
            self._on_file_detected_v1,
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

    def stop(self) -> None:
        """Stop the indexer."""
        # For v2: Stop components BEFORE setting _running = False
        # This allows accumulator's flush callback to process remaining files
        if USE_V2_INDEXER:
            self._stop_v2()
        else:
            self._stop_v1()

        # Now mark as not running (after v2 flush completed)
        self._running = False

        # Only close DB if we own it (not shared singleton)
        if self._owns_db:
            self._db.close()
        info("[UnifiedIndexer] Stopped")

    def _stop_v2(self) -> None:
        """Stop v2 architecture components.

        Order matters:
        1. Stop watcher (no more new file events)
        2. Stop reconciler (no more periodic scans)
        3. Stop accumulator (flushes pending files while _running is still True)
        """
        # Stop watcher first (no more file events)
        if self._watcher:
            self._watcher.stop()
            debug("[UnifiedIndexer] Watcher stopped")

        # Stop reconciler (no more periodic scans)
        if self._reconciler:
            self._reconciler.stop()
            debug("[UnifiedIndexer] Reconciler stopped")

        # Stop accumulator last (flushes pending files)
        # IMPORTANT: This must happen while _running is still True
        # so the on_batch_ready callback can process the flushed files
        if self._accumulator:
            self._accumulator.stop()
            debug("[UnifiedIndexer] Accumulator stopped")

    def _stop_v1(self) -> None:
        """Stop v1 architecture components."""
        if self._watcher:
            self._watcher.stop()

        if self._processor_thread:
            self._processor_thread.join(timeout=5)

        if self._backfill_thread:
            self._backfill_thread.join(timeout=5)

    def _on_file_detected(self, file_type: str, path: Path) -> None:
        """Callback when watcher detects a file change.

        v2: Feeds the FileBatchAccumulator for micro-batch processing.
        v1: Feeds the ProcessingQueue (legacy).

        Args:
            file_type: Type of file (session, message, part, etc.)
            path: Path to the file
        """
        if USE_V2_INDEXER and self._accumulator:
            self._accumulator.add(path)
        else:
            self._queue.put(file_type, path)

    def _on_file_detected_v1(self, file_type: str, path: Path) -> None:
        """v1 callback: Feeds the ProcessingQueue."""
        self._queue.put(file_type, path)

    # =========================================================================
    # v2 Callbacks (Plan 46)
    # =========================================================================

    def _on_batch_ready(self, files: List[Path]) -> None:
        """v2 callback: Process a micro-batch of files.

        Called by FileBatchAccumulator when batch is ready (timer or max_files).
        Groups files by type and processes them via BatchProcessor.

        Args:
            files: List of file paths to process
        """
        if not files or not self._running:
            return

        debug(f"[UnifiedIndexer] Processing batch of {len(files)} files")

        # Group files by type
        by_type = self._group_files_by_type(files)

        # Process each type with BatchProcessor
        total_processed = 0
        for file_type, type_files in by_type.items():
            if not type_files:
                continue
            processed = self._batch_processor.process_files(file_type, type_files)
            total_processed += processed
            debug(
                f"[UnifiedIndexer] Processed {processed}/{len(type_files)} {file_type} files"
            )

        # Update files_processed stat (BatchProcessor updates type-specific stats)
        with self._lock:
            self._stats["files_processed"] += total_processed

        # Post-batch trace resolution (like in _run_backfill)
        self._post_batch_processing()

    def _on_missing_files(self, files: List[Path]) -> None:
        """v2 callback: Handle files found by Reconciler.

        Called by Reconciler when it finds missing/modified files.
        Feeds them to the FileBatchAccumulator for batched processing.

        Args:
            files: List of missing/modified file paths
        """
        if not files or not self._running:
            return

        debug(f"[UnifiedIndexer] Reconciler found {len(files)} missing files")

        if self._accumulator:
            self._accumulator.add_many(files)

    def _group_files_by_type(self, files: List[Path]) -> dict[str, List[Path]]:
        """Group files by their type based on path.

        Args:
            files: List of file paths

        Returns:
            Dict mapping file_type to list of paths
        """
        by_type: dict[str, List[Path]] = {
            "session": [],
            "message": [],
            "part": [],
            "todo": [],
            "project": [],
        }

        for path in files:
            file_type = self._get_file_type(path)
            if file_type in by_type:
                by_type[file_type].append(path)

        return by_type

    def _get_file_type(self, path: Path) -> str:
        """Determine file type from path.

        Path structure: storage/{type}/{project_id}/{file}.json
        or: storage/{type}/{file}.json (for todo/project)

        Args:
            path: File path

        Returns:
            File type (session, message, part, todo, project)
        """
        # OpenCode uses plural folder names, but we use singular type names
        folder_to_type = {
            "sessions": "session",
            "messages": "message",
            "parts": "part",
            "todos": "todo",
            "projects": "project",
        }

        # Get path relative to storage
        try:
            rel_path = path.relative_to(self._storage_path)
            # First part of relative path is the folder name (plural)
            parts = rel_path.parts
            if parts:
                folder_name = parts[0]
                # Map plural folder name to singular type
                return folder_to_type.get(folder_name, folder_name)
        except ValueError:
            pass

        # Fallback: check parent directories
        path_str = str(path)
        for folder, file_type in folder_to_type.items():
            if f"/{folder}/" in path_str:
                return file_type

        return "unknown"

    def _post_batch_processing(self) -> None:
        """Run post-batch processing tasks (trace resolution, etc.)."""
        # Update root trace agents from messages
        updated_agents = self._trace_builder.update_root_trace_agents()
        if updated_agents > 0:
            debug(f"[UnifiedIndexer] Updated {updated_agents} root trace agents")

        # Create conversation segments
        segments_created = self._trace_builder.analyze_all_sessions_for_segments()
        if segments_created > 0:
            debug(f"[UnifiedIndexer] Created {segments_created} conversation segments")

        # Resolve parent traces
        resolved = self._trace_builder.resolve_parent_traces()
        if resolved > 0:
            debug(f"[UnifiedIndexer] Resolved {resolved} parent traces")

        # Backfill missing tokens
        backfilled = self._trace_builder.backfill_missing_tokens()
        if backfilled > 0:
            debug(f"[UnifiedIndexer] Backfilled tokens for {backfilled} traces")

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

        # Update files_processed stat
        with self._lock:
            self._stats["files_processed"] += total_processed

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

            # Backfill tokens for traces created before their child session messages
            backfilled = self._trace_builder.backfill_missing_tokens()
            if backfilled > 0:
                debug(
                    f"[Backfill #{cycle_num}] Backfilled tokens for {backfilled} traces"
                )

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
        stats["v2_enabled"] = USE_V2_INDEXER

        if self._watcher:
            stats["watcher"] = self._watcher.get_stats()

        # v2 component stats
        if self._accumulator:
            acc_stats = self._accumulator.get_stats()
            stats["accumulator"] = {
                "batches_sent": acc_stats.batches_sent,
                "files_accumulated": acc_stats.files_accumulated,
                "files_deduplicated": acc_stats.files_deduplicated,
                "batches_by_timer": acc_stats.batches_by_timer,
                "batches_by_max_files": acc_stats.batches_by_max_files,
            }

        if self._reconciler:
            rec_stats = self._reconciler.get_stats()
            stats["reconciler"] = {
                "scans_completed": rec_stats.scans_completed,
                "files_found": rec_stats.files_found,
                "last_scan_duration_ms": rec_stats.last_scan_duration_ms,
                "last_scan_files": rec_stats.last_scan_files,
            }

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
