"""
Hybrid Indexer - Combines bulk loading with real-time file watching.

Architecture:
1. T0 = start timestamp (boundary between bulk and realtime)
2. Bulk loader: processes files with mtime < T0 via DuckDB native
3. Watcher: queues files detected during bulk, then processes in realtime
4. No conflicts: watcher only queues during bulk phase

Performance:
- Bulk: ~20,000 files/second (DuckDB native JSON)
- Realtime: ~250 files/second (Python processing)
- Total 180k files: ~10 seconds vs 10+ minutes
"""

import threading
import time
from pathlib import Path
from typing import Any, Optional
from queue import Queue, Empty, Full

from ..db import AnalyticsDB
from .sync_state import SyncState, SyncPhase, SyncStatus
from .bulk_loader import BulkLoader
from .watcher import FileWatcher
from .parsers import FileParser
from .tracker import FileTracker
from .trace_builder import TraceBuilder
from .file_processing import FileProcessingState
from .handlers import FileHandler, SessionHandler, MessageHandler, PartHandler
from ...utils.logger import info, debug


# Default storage path
OPENCODE_STORAGE = Path.home() / ".local" / "share" / "opencode" / "storage"


class HybridIndexer:
    """
    Hybrid indexer combining bulk loading with real-time watching.

    Phases:
    1. BULK: Load historical files via DuckDB native (very fast)
    2. QUEUE: Process files that changed during bulk
    3. REALTIME: Process new files as they arrive

    Usage:
        indexer = HybridIndexer()
        indexer.start()
        # ... runs in background ...
        status = indexer.get_status()
        indexer.stop()
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        db_path: Optional[Path] = None,
        # Injected dependencies (for testability)
        db: Optional[AnalyticsDB] = None,
        sync_state: Optional[SyncState] = None,
        bulk_loader: Optional[BulkLoader] = None,
        tracker: Optional[FileTracker] = None,
        parser: Optional[FileParser] = None,
        trace_builder: Optional[TraceBuilder] = None,
    ):
        """
        Initialize the hybrid indexer.

        Args:
            storage_path: Path to opencode storage directory
            db_path: Path to DuckDB database file

            # Dependency injection (optional, for testing):
            db: Injected AnalyticsDB instance
            sync_state: Injected SyncState instance
            bulk_loader: Injected BulkLoader instance
            tracker: Injected FileTracker instance
            parser: Injected FileParser instance
            trace_builder: Injected TraceBuilder instance

        Example (production):
            indexer = HybridIndexer(storage_path=Path("/data"))

        Example (testing with mocks):
            mock_db = Mock(spec=AnalyticsDB)
            indexer = HybridIndexer(db=mock_db)
        """
        self._storage_path = storage_path or OPENCODE_STORAGE

        # Use injected db or create from path
        self._db = db or AnalyticsDB(db_path)
        self._db_injected = db is not None

        # Injected components (will be used in start() if provided)
        self._injected_sync_state = sync_state
        self._injected_bulk_loader = bulk_loader
        self._injected_tracker = tracker
        self._injected_parser = parser
        self._injected_trace_builder = trace_builder

        # Active components (set in start())
        self._sync_state: Optional[SyncState] = None
        self._bulk_loader: Optional[BulkLoader] = None
        self._watcher: Optional[FileWatcher] = None
        self._tracker: Optional[FileTracker] = None
        self._parser: Optional[FileParser] = None
        self._trace_builder: Optional[TraceBuilder] = None
        self._file_processing: Optional[FileProcessingState] = None

        # Queue for files detected during bulk (bounded to prevent OOM)
        self._event_queue: Queue = Queue(maxsize=10000)

        # Handlers for different file types (Strategy pattern)
        self._handlers: dict[str, FileHandler] = {
            "session": SessionHandler(),
            "message": MessageHandler(),
            "part": PartHandler(),
        }

        # Threads
        self._bulk_thread: Optional[threading.Thread] = None
        self._processor_thread: Optional[threading.Thread] = None

        # State
        self._running = False
        self._t0: Optional[float] = None
        self._dropped_events = 0  # Counter for dropped events (queue full)

    def start(self) -> None:
        """Start the hybrid indexer."""
        if self._running:
            return

        self._running = True
        self._t0 = time.time()

        info("[HybridIndexer] Starting...")
        info(f"[HybridIndexer] Storage: {self._storage_path}")
        info(f"[HybridIndexer] T0 (cutoff): {self._t0}")

        # Connect to database
        self._db.connect()

        # Initialize components (use injected if available, else create)
        self._sync_state = self._injected_sync_state or SyncState(self._db)
        self._tracker = self._injected_tracker or FileTracker(self._db)
        self._parser = self._injected_parser or FileParser()
        self._trace_builder = self._injected_trace_builder or TraceBuilder(self._db)
        self._file_processing = FileProcessingState(self._db)
        self._bulk_loader = self._injected_bulk_loader or BulkLoader(
            self._db, self._storage_path, self._sync_state
        )

        # Start watcher (queue-only mode during bulk)
        self._watcher = FileWatcher(
            self._storage_path,
            self._on_file_event,
        )
        self._watcher.start()
        info("[HybridIndexer] Watcher started (queue mode)")

        # Start bulk loading in separate thread
        self._bulk_thread = threading.Thread(
            target=self._run_bulk_phase, daemon=True, name="hybrid-bulk"
        )
        self._bulk_thread.start()

        info("[HybridIndexer] Bulk loading started")

    def stop(self) -> None:
        """Stop the hybrid indexer."""
        self._running = False

        if self._watcher:
            self._watcher.stop()

        if self._bulk_thread:
            self._bulk_thread.join(timeout=5)

        if self._processor_thread:
            self._processor_thread.join(timeout=5)

        self._db.close()
        info("[HybridIndexer] Stopped")

    def _on_file_event(self, file_type: str, path: Path) -> None:
        """Handle file event from watcher."""
        # During bulk phase, just queue the event
        # After bulk, process immediately
        if self._sync_state and self._sync_state.is_realtime:
            self._process_file(file_type, path)
        else:
            try:
                # Try to add to queue with timeout (bounded queue)
                self._event_queue.put((file_type, path), timeout=1.0)
                if self._sync_state:
                    self._sync_state.set_queue_size(self._event_queue.qsize())
            except Full:
                # Queue is full - drop event and log
                self._dropped_events += 1
                if self._dropped_events % 100 == 0:
                    info(
                        f"[HybridIndexer] Dropped {self._dropped_events} events (queue full)"
                    )
                debug(f"[HybridIndexer] Event queue full, dropping {path}")

    def _run_bulk_phase(self) -> None:
        """Run the bulk loading phase."""
        # Guard: sync_state is always set in start() before this is called
        if self._sync_state is None:
            return

        # Skip if already in realtime mode (from previous run)
        if self._sync_state.is_realtime:
            info("[HybridIndexer] Already in realtime mode, skipping bulk")
            # Run post-processing to fix any pending traces
            self._run_post_bulk_processing()
            # Start realtime processor directly
            self._processor_thread = threading.Thread(
                target=self._run_realtime_phase, daemon=True, name="hybrid-realtime"
            )
            self._processor_thread.start()
            return

        try:
            # Load all historical files
            if self._bulk_loader is None:
                return
            results = self._bulk_loader.load_all(self._t0)

            total_loaded = sum(r.files_loaded for r in results.values())
            total_time = sum(r.duration_seconds for r in results.values())

            info(
                f"[HybridIndexer] Bulk complete: {total_loaded:,} files in {total_time:.1f}s"
            )

            # Process the queue (files detected during bulk)
            self._run_queue_phase()

            # Run post-processing to resolve traces and backfill tokens
            self._run_post_bulk_processing()

            # Switch to realtime mode
            self._sync_state.set_phase(SyncPhase.REALTIME)
            self._sync_state.checkpoint()

            info("[HybridIndexer] Switched to realtime mode")

            # Start processor thread for realtime
            self._processor_thread = threading.Thread(
                target=self._run_realtime_phase, daemon=True, name="hybrid-realtime"
            )
            self._processor_thread.start()

        except Exception as e:
            info(f"[HybridIndexer] Bulk phase error: {e}")
            import traceback

            debug(traceback.format_exc())

    def _run_queue_phase(self) -> None:
        """Process files that were queued during bulk loading."""
        if self._sync_state is None:
            return
        self._sync_state.set_phase(SyncPhase.PROCESSING_QUEUE)

        queue_size = self._event_queue.qsize()
        if queue_size == 0:
            info("[HybridIndexer] Queue empty, skipping queue phase")
            return

        info(f"[HybridIndexer] Processing queue: {queue_size} files")

        processed = 0
        while not self._event_queue.empty() and self._running:
            try:
                file_type, path = self._event_queue.get_nowait()
                self._process_file(file_type, path)
                processed += 1

                if processed % 100 == 0:
                    debug(f"[HybridIndexer] Queue progress: {processed}/{queue_size}")

            except Empty:
                break

        info(f"[HybridIndexer] Queue processed: {processed} files")

        # Report dropped events (if any)
        if self._dropped_events > 0:
            info(
                f"[HybridIndexer] Total events dropped during bulk: {self._dropped_events}"
            )

    def _run_post_bulk_processing(self) -> None:
        """Run post-processing after bulk load completes.

        Order matters:
        1. Update root trace agents (user -> actual agent)
        2. Resolve parent traces (copies subagent_type to child's parent_agent)
        3. Backfill tokens
        """
        if not self._trace_builder:
            return

        # Step 1: Update root trace agents from messages
        # Root traces are created with subagent_type='user', update to actual agent
        updated_agents = self._trace_builder.update_root_trace_agents()
        if updated_agents > 0:
            info(f"[HybridIndexer] Updated {updated_agents} root trace agents")

        # Step 2: Resolve parent traces (must run AFTER update_root_trace_agents)
        # This sets parent_agent from parent's subagent_type
        resolved = self._trace_builder.resolve_parent_traces()
        if resolved > 0:
            info(f"[HybridIndexer] Resolved {resolved} parent traces")

        # Step 3: Backfill tokens for traces with child_session_id
        backfilled = self._trace_builder.backfill_missing_tokens()
        if backfilled > 0:
            info(f"[HybridIndexer] Backfilled tokens for {backfilled} traces")

        # Step 4: Build derived trace tables (exchanges, exchange_traces, session_traces)
        # These tables power the Timeline and Delegations UI views
        try:
            stats = self._trace_builder.build_all()
            exchanges = stats.get("exchanges", 0)
            exchange_traces = stats.get("exchange_traces", 0)
            session_traces = stats.get("session_traces", 0)
            if exchanges > 0 or exchange_traces > 0 or session_traces > 0:
                info(
                    f"[HybridIndexer] Built trace tables: "
                    f"{exchanges} exchanges, {exchange_traces} events, {session_traces} sessions"
                )
        except Exception as e:
            debug(f"[HybridIndexer] Failed to build trace tables: {e}")

    def _run_realtime_phase(self) -> None:
        """Process files in realtime as they arrive."""
        while self._running:
            try:
                file_type, path = self._event_queue.get(timeout=0.1)
                self._process_file(file_type, path)
                if self._sync_state is not None:
                    self._sync_state.set_queue_size(self._event_queue.qsize())
            except Empty:
                continue

    def _process_file(self, file_type: str, path: Path) -> bool:
        """
        Process a single file (for realtime mode).

        Uses the Strategy pattern to delegate processing to the appropriate handler.
        """
        try:
            # Ensure components are initialized
            if not self._tracker or not self._parser or not self._trace_builder:
                debug("[HybridIndexer] Components not initialized")
                return False

            # Check if already processed by bulk loader (race condition prevention)
            if self._file_processing and self._file_processing.is_already_processed(
                str(path)
            ):
                debug(
                    f"[HybridIndexer] Skipping {path} - already processed by bulk loader"
                )
                return True

            # Check if needs indexing (not indexed or modified)
            if not self._tracker.needs_indexing(path):
                return True  # Already up to date

            # Get handler for this file type
            handler = self._handlers.get(file_type)
            if not handler:
                debug(f"[HybridIndexer] Unknown file type: {file_type}")
                return False

            # Read and parse
            raw_data = self._parser.read_json(path)
            if raw_data is None:
                self._tracker.mark_error(path, file_type, "Failed to read JSON")
                return False

            # Delegate to handler
            conn = self._db.connect()
            record_id = handler.process(
                file_path=path,
                raw_data=raw_data,
                conn=conn,
                parser=self._parser,
                trace_builder=self._trace_builder,
            )

            if record_id:
                self._tracker.mark_indexed(path, file_type, record_id)
                # Also mark in file_processing to prevent reprocessing
                if self._file_processing:
                    self._file_processing.mark_processed(
                        str(path), file_type, status="processed"
                    )
                return True
            else:
                self._tracker.mark_error(path, file_type, "Invalid data")
                # Mark as failed to prevent retrying
                if self._file_processing:
                    self._file_processing.mark_processed(
                        str(path), file_type, status="failed"
                    )
                return False

        except Exception as e:
            debug(f"[HybridIndexer] Error processing {path}: {e}")
            if self._tracker:
                self._tracker.mark_error(path, file_type, str(e))
            return False

    def get_status(self) -> SyncStatus:
        """Get current sync status for dashboard/API."""
        if self._sync_state:
            return self._sync_state.get_status()
        else:
            return SyncStatus(
                phase=SyncPhase.INIT,
                t0=None,
                progress=0,
                files_total=0,
                files_done=0,
                queue_size=0,
                eta_seconds=None,
                last_indexed=None,
                is_ready=False,
            )

    def get_stats(self) -> dict:
        """Get indexer statistics."""
        stats: dict[str, Any] = {
            "phase": self._sync_state.phase.value if self._sync_state else "init",
            "queue_size": self._event_queue.qsize(),
            "dropped_events": self._dropped_events,
        }

        if self._bulk_loader:
            stats["bulk"] = self._bulk_loader.get_stats()

        return stats


# =============================================================================
# IndexerRegistry - Manages HybridIndexer instance for testability
# =============================================================================


class IndexerRegistry:
    """
    Registry for managing HybridIndexer instance.

    Replaces global singleton pattern for better testability:
    - clear() method for test cleanup between tests
    - Dependency injection support via create()
    - No global keyword needed

    Usage in tests:
        # Setup with mock
        mock_db = Mock(spec=AnalyticsDB)
        indexer = HybridIndexer(db=mock_db)
        IndexerRegistry.set(indexer)

        # Teardown
        IndexerRegistry.clear()
    """

    _instance: Optional[HybridIndexer] = None

    @classmethod
    def get(cls) -> Optional[HybridIndexer]:
        """Get the current indexer instance (may be None)."""
        return cls._instance

    @classmethod
    def get_or_create(
        cls,
        storage_path: Optional[Path] = None,
        db_path: Optional[Path] = None,
        **kwargs,
    ) -> HybridIndexer:
        """Get existing indexer or create a new one."""
        if cls._instance is None:
            cls._instance = HybridIndexer(
                storage_path=storage_path,
                db_path=db_path,
                **kwargs,
            )
        return cls._instance

    @classmethod
    def set(cls, indexer: HybridIndexer) -> None:
        """Set the indexer instance (useful for tests with mocks)."""
        cls._instance = indexer

    @classmethod
    def clear(cls) -> None:
        """
        Clear the registry (useful for test cleanup).

        Stops the indexer if running before clearing.
        """
        if cls._instance:
            cls._instance.stop()
        cls._instance = None

    @classmethod
    def create(
        cls,
        storage_path: Optional[Path] = None,
        db_path: Optional[Path] = None,
        db: Optional[AnalyticsDB] = None,
        sync_state: Optional[SyncState] = None,
        **kwargs,
    ) -> HybridIndexer:
        """
        Factory method to create and register an indexer.

        Supports dependency injection for testability.

        Args:
            storage_path: Path to storage directory
            db_path: Path to database file
            db: Injected AnalyticsDB instance (for testing)
            sync_state: Injected SyncState instance (for testing)
            **kwargs: Additional arguments passed to HybridIndexer

        Returns:
            The created and registered HybridIndexer instance
        """
        # Clear existing instance if any
        cls.clear()

        indexer = HybridIndexer(
            storage_path=storage_path,
            db_path=db_path,
            db=db,
            sync_state=sync_state,
            **kwargs,
        )
        cls._instance = indexer
        return indexer


# =============================================================================
# Module-level functions (backward compatible)
# =============================================================================


def get_hybrid_indexer() -> HybridIndexer:
    """Get or create the global hybrid indexer instance."""
    return IndexerRegistry.get_or_create()


def start_hybrid_indexer() -> None:
    """Start the global hybrid indexer."""
    get_hybrid_indexer().start()


def stop_hybrid_indexer() -> None:
    """Stop the global hybrid indexer."""
    IndexerRegistry.clear()


def get_sync_status() -> SyncStatus:
    """Get current sync status."""
    indexer = IndexerRegistry.get()
    if indexer:
        return indexer.get_status()
    # Return default status if no indexer
    return SyncStatus(
        phase=SyncPhase.INIT,
        t0=None,
        progress=0,
        files_total=0,
        files_done=0,
        queue_size=0,
        eta_seconds=None,
        last_indexed=None,
        is_ready=False,
    )
