"""
Unified Real-Time Indexer for OpenCode data.

Replaces collector.py and loader.py with a single, efficient module that:
- Watches for file changes in real-time (via watchdog)
- Uses change detection (mtime + size) to skip unchanged files
- Performs progressive backfill for historical data
- Creates agent_traces immediately when tasks complete
- Uses multithreading for parallel file processing

Performance:
- Parallel file parsing with ThreadPoolExecutor
- Sequential DB writes (DuckDB constraint)
- ~1000+ files/second throughput
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..db import AnalyticsDB
from .tracker import FileTracker
from .parsers import FileParser
from .trace_builder import TraceBuilder
from .watcher import FileWatcher, ProcessingQueue
from ...utils.logger import debug, info


# Default storage path
OPENCODE_STORAGE = Path.home() / ".local" / "share" / "opencode" / "storage"

# Backfill configuration
BACKFILL_BATCH_SIZE = 50000  # Max files per cycle (large for fast initial backfill)
BACKFILL_THROTTLE_MS = 1  # Minimal pause
BACKFILL_INTERVAL = 2  # Seconds between backfill cycles (during initial)
BACKFILL_INTERVAL_SLOW = 60  # Seconds between cycles after initial backfill
NUM_WORKERS = 8  # Number of parallel workers


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
        self._backfilling = False  # True when backfill is actively processing
        self._start_timestamp: Optional[float] = None  # Cutoff for backfill
        self._initial_backfill_done = False  # True after first complete pass

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

    def start(self) -> None:
        """Start the indexer (watcher + backfill + processor)."""
        if self._running:
            return

        self._running = True
        self._stats["start_time"] = datetime.now().isoformat()
        self._start_timestamp = (
            time.time()
        )  # Cutoff: backfill only processes files older than this

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
        """Process files from the queue continuously.

        IMPORTANT: Waits until initial backfill completes to avoid
        DuckDB write-write conflicts between threads.
        """
        # Wait for initial backfill to complete before processing
        # Files detected by watcher will queue up and be processed after
        while self._running and not self._initial_backfill_done:
            time.sleep(0.5)

        if self._running:
            queued = self._queue.size
            if queued > 0:
                info(f"[Processor] Starting - {queued} files queued during backfill")

        while self._running:
            batch = self._queue.get_batch(max_items=50, timeout=0.1)
            if not batch:
                continue

            for file_type, path in batch:
                if not self._running:
                    break
                self._process_file(file_type, path)

    def _backfill_loop(self) -> None:
        """Run backfill periodically to catch missed files."""
        # Initial backfill immediately
        time.sleep(1)  # Wait for watcher to start
        if self._running:
            info("[UnifiedIndexer] Running initial backfill...")
            self._run_backfill()

        # Then periodic backfill (slower after initial pass)
        while self._running:
            interval = (
                BACKFILL_INTERVAL_SLOW
                if self._initial_backfill_done
                else BACKFILL_INTERVAL
            )
            time.sleep(interval)
            if self._running:
                self._run_backfill()

    @property
    def is_backfilling(self) -> bool:
        """Check if backfill is currently active."""
        return self._backfilling

    @property
    def initial_backfill_done(self) -> bool:
        """Check if initial backfill has completed."""
        return self._initial_backfill_done

    def _run_backfill(self) -> None:
        """Run a backfill cycle for unindexed files.

        Uses batch INSERT for high performance.

        Only processes files created BEFORE the indexer started (cutoff timestamp).
        Files created AFTER are handled by the real-time watcher.
        """
        self._backfilling = True
        start_time = time.time()
        total_processed = 0
        cycle_num = self._stats.get("backfill_cycles", 0) + 1

        for file_type in ["session", "message", "part", "todo", "project"]:
            if not self._running:
                break

            directory = self._storage_path / file_type
            scan_start = time.time()
            # Backfill only processes files that have NEVER been indexed.
            # Modified files are handled by the watcher in real-time.
            # Also use start_timestamp as cutoff to ignore files created after start.
            unindexed = self._tracker.get_unindexed_files(
                directory,
                file_type,
                limit=BACKFILL_BATCH_SIZE,
                max_mtime=self._start_timestamp,
                only_new=True,  # Don't re-process modified files - watcher handles those
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
            speed = total_processed / elapsed if elapsed > 0 else 0
            info(
                f"[Backfill #{cycle_num}] DONE: {total_processed} files in {elapsed:.1f}s ({speed:.0f}/s) | "
                f"Sessions: {self._stats.get('sessions_indexed', 0)} | "
                f"Messages: {self._stats.get('messages_indexed', 0)} | "
                f"Parts: {self._stats.get('parts_indexed', 0)} | "
                f"Traces: {self._stats.get('traces_created', 0)}"
            )
        else:
            if not self._initial_backfill_done:
                self._initial_backfill_done = True
                info(
                    f"[Backfill #{cycle_num}] Initial backfill COMPLETE - running post-processing..."
                )

                # Run post-processing ONCE after initial backfill completes
                # (not after each batch, to avoid write-write conflicts)
                self._run_post_backfill_processing(cycle_num)
            else:
                debug(f"[Backfill #{cycle_num}] No new files to index ({elapsed:.1f}s)")

        self._backfilling = False

    def _run_post_backfill_processing(self, cycle_num: int) -> None:
        """Run post-processing after initial backfill completes.

        This is called ONCE after all files are indexed, not after each batch.
        This avoids DuckDB write-write conflicts between concurrent operations.

        Args:
            cycle_num: Current backfill cycle number for logging
        """
        # Update root trace agents from messages (root traces created with user type)
        updated_agents = self._trace_builder.update_root_trace_agents()
        if updated_agents > 0:
            debug(f"[Backfill #{cycle_num}] Updated {updated_agents} root trace agents")

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
            debug(f"[Backfill #{cycle_num}] Backfilled tokens for {backfilled} traces")

        info(
            f"[Backfill #{cycle_num}] Post-processing complete - switching to maintenance mode"
        )

    def _batch_process_files(self, file_type: str, files: list[Path]) -> int:
        """Process files in batch with bulk INSERT.

        Args:
            file_type: Type of files to process
            files: List of file paths

        Returns:
            Number of files successfully processed
        """
        if file_type == "session":
            return self._batch_process_sessions(files)
        elif file_type == "message":
            return self._batch_process_messages(files)
        elif file_type == "part":
            return self._batch_process_parts(files)
        else:
            # Fallback to individual processing for todo/project
            count = 0
            for path in files:
                if self._process_file(file_type, path):
                    count += 1
            return count

    def _batch_process_sessions(self, files: list[Path]) -> int:
        """Batch process session files."""
        records = []
        root_sessions = []
        paths_processed = []

        # Parse all files
        for path in files:
            raw_data = self._parser.read_json(path)
            if raw_data is None:
                self._tracker.mark_error(path, "session", "Failed to read JSON")
                continue

            parsed = self._parser.parse_session(raw_data)
            if not parsed:
                self._tracker.mark_error(path, "session", "Invalid data")
                continue

            records.append(
                (
                    parsed.id,
                    parsed.project_id,
                    parsed.directory,
                    parsed.title,
                    parsed.parent_id,
                    parsed.version,
                    parsed.additions,
                    parsed.deletions,
                    parsed.files_changed,
                    parsed.created_at,
                    parsed.updated_at,
                )
            )
            paths_processed.append((path, parsed.id))

            if not parsed.parent_id:
                root_sessions.append(parsed)

        if not records:
            return 0

        # Batch INSERT
        conn = self._db.connect()
        conn.executemany(
            """
            INSERT OR REPLACE INTO sessions
            (id, project_id, directory, title, parent_id, version,
             additions, deletions, files_changed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

        # Mark all as indexed (batch)
        self._tracker.mark_indexed_batch(
            [(path, "session", record_id) for path, record_id in paths_processed]
        )

        # Create root traces
        for parsed in root_sessions:
            self._trace_builder.create_root_trace(
                session_id=parsed.id,
                title=parsed.title,
                agent=None,
                first_message=None,
                created_at=parsed.created_at,
                updated_at=parsed.updated_at,
            )
            self._stats["traces_created"] += 1

        self._stats["sessions_indexed"] += len(records)
        return len(records)

    def _batch_process_messages(self, files: list[Path]) -> int:
        """Batch process message files with parallel parsing."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        records: list[tuple] = []
        paths_processed: list[tuple[Path, str]] = []
        errors: list[tuple[Path, str]] = []

        def parse_file(path: Path) -> dict:
            """Parse a single file - runs in thread pool."""
            raw_data = self._parser.read_json(path)
            if raw_data is None:
                return {"status": "error", "path": path, "error": "Failed to read JSON"}

            parsed = self._parser.parse_message(raw_data)
            if not parsed:
                return {"status": "error", "path": path, "error": "Invalid data"}

            return {"status": "ok", "path": path, "parsed": parsed}

        # Parallel file parsing with thread pool
        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = [executor.submit(parse_file, path) for path in files]

            for future in as_completed(futures):
                result = future.result()

                if result["status"] == "error":
                    errors.append((result["path"], result["error"]))
                else:
                    parsed = result["parsed"]
                    records.append(
                        (
                            parsed.id,
                            parsed.session_id,
                            parsed.parent_id,
                            parsed.role,
                            parsed.agent,
                            parsed.model_id,
                            parsed.provider_id,
                            parsed.mode,
                            parsed.cost,
                            parsed.finish_reason,
                            parsed.working_dir,
                            parsed.tokens_input,
                            parsed.tokens_output,
                            parsed.tokens_reasoning,
                            parsed.tokens_cache_read,
                            parsed.tokens_cache_write,
                            parsed.created_at,
                            parsed.completed_at,
                        )
                    )
                    paths_processed.append((result["path"], parsed.id))

        # Mark errors
        for path, error_msg in errors:
            self._tracker.mark_error(path, "message", error_msg)

        if not records:
            return 0

        # Batch INSERT
        conn = self._db.connect()
        conn.executemany(
            """
            INSERT OR REPLACE INTO messages
            (id, session_id, parent_id, role, agent, model_id, provider_id,
             mode, cost, finish_reason, working_dir,
             tokens_input, tokens_output, tokens_reasoning,
             tokens_cache_read, tokens_cache_write, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

        # Mark all as indexed (batch)
        self._tracker.mark_indexed_batch(
            [(path, "message", record_id) for path, record_id in paths_processed]
        )

        self._stats["messages_indexed"] += len(records)
        return len(records)

    def _batch_process_parts(self, files: list[Path]) -> int:
        """Batch process part files with parallel parsing."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        records: list[tuple] = []
        paths_processed: list[tuple[Path, str]] = []
        delegations: list[tuple] = []
        errors: list[tuple[Path, str]] = []

        def parse_file(path: Path) -> dict:
            """Parse a single file - runs in thread pool."""
            raw_data = self._parser.read_json(path)
            if raw_data is None:
                return {"status": "error", "path": path, "error": "Failed to read JSON"}

            parsed = self._parser.parse_part(raw_data)
            if not parsed:
                return {"status": "error", "path": path, "error": "Invalid data"}

            # Check for delegation
            delegation = None
            if parsed.tool_name == "task" and parsed.tool_status == "completed":
                delegation = self._parser.parse_delegation(raw_data)

            return {
                "status": "ok",
                "path": path,
                "parsed": parsed,
                "delegation": delegation,
            }

        # Parallel file parsing with thread pool
        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = [executor.submit(parse_file, path) for path in files]

            for future in as_completed(futures):
                result = future.result()

                if result["status"] == "error":
                    errors.append((result["path"], result["error"]))
                else:
                    parsed = result["parsed"]
                    records.append(
                        (
                            parsed.id,
                            parsed.session_id,
                            parsed.message_id,
                            parsed.part_type,
                            parsed.content,
                            parsed.tool_name,
                            parsed.tool_status,
                            parsed.call_id,
                            parsed.created_at,
                            parsed.ended_at,
                            parsed.duration_ms,
                            parsed.arguments,
                            parsed.error_message,
                        )
                    )
                    paths_processed.append((result["path"], parsed.id))

                    if result["delegation"]:
                        delegations.append((result["delegation"], parsed))

        # Mark errors
        for path, error_msg in errors:
            self._tracker.mark_error(path, "part", error_msg)

        if not records:
            return 0

        # Batch INSERT
        conn = self._db.connect()
        conn.executemany(
            """
            INSERT OR REPLACE INTO parts
            (id, session_id, message_id, part_type, content, tool_name, tool_status,
             call_id, created_at, ended_at, duration_ms, arguments, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

        # Mark all as indexed (batch)
        self._tracker.mark_indexed_batch(
            [(path, "part", record_id) for path, record_id in paths_processed]
        )

        # Create traces for delegations
        # Skip during initial backfill for performance - traces created in post-processing
        if self._initial_backfill_done:
            for delegation, part in delegations:
                trace_id = self._trace_builder.create_trace_from_delegation(
                    delegation, part
                )
                if trace_id:
                    self._stats["traces_created"] += 1

        self._stats["parts_indexed"] += len(records)
        return len(records)

    def _process_file(self, file_type: str, path: Path) -> bool:
        """Process a single file.

        Args:
            file_type: Type of file
            path: Path to the file

        Returns:
            True if processed successfully, False otherwise
        """
        # Read and parse
        raw_data = self._parser.read_json(path)
        if raw_data is None:
            self._tracker.mark_error(path, file_type, "Failed to read JSON")
            self._stats["files_error"] += 1
            return False

        # Process based on type
        try:
            record_id = None

            if file_type == "session":
                record_id = self._process_session(raw_data)
            elif file_type == "message":
                record_id = self._process_message(raw_data)
            elif file_type == "part":
                record_id = self._process_part(raw_data)
            elif file_type == "todo":
                record_id = self._process_todos(path.stem, raw_data, path)
            elif file_type == "project":
                record_id = self._process_project(raw_data)

            if record_id:
                self._tracker.mark_indexed(path, file_type, record_id)
                self._stats["files_processed"] += 1
                return True
            else:
                self._tracker.mark_error(path, file_type, "Invalid data")
                self._stats["files_error"] += 1
                return False

        except Exception as e:
            self._tracker.mark_error(path, file_type, str(e))
            self._stats["files_error"] += 1
            debug(f"[UnifiedIndexer] Error processing {path}: {e}")
            return False

    def _process_session(self, data: dict) -> Optional[str]:
        """Process a session file.

        Args:
            data: Parsed JSON data

        Returns:
            Session ID if successful, None otherwise
        """
        parsed = self._parser.parse_session(data)
        if not parsed:
            return None

        conn = self._db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO sessions
            (id, project_id, directory, title, parent_id, version,
             additions, deletions, files_changed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                parsed.id,
                parsed.project_id,
                parsed.directory,
                parsed.title,
                parsed.parent_id,
                parsed.version,
                parsed.additions,
                parsed.deletions,
                parsed.files_changed,
                parsed.created_at,
                parsed.updated_at,
            ],
        )

        self._stats["sessions_indexed"] += 1

        # Create root trace for sessions without parent
        if not parsed.parent_id:
            self._trace_builder.create_root_trace(
                session_id=parsed.id,
                title=parsed.title,
                agent=None,  # Will be resolved when messages are indexed
                first_message=None,
                created_at=parsed.created_at,
                updated_at=parsed.updated_at,
            )
            self._stats["traces_created"] += 1

        return parsed.id

    def _process_message(self, data: dict) -> Optional[str]:
        """Process a message file.

        Args:
            data: Parsed JSON data

        Returns:
            Message ID if successful, None otherwise
        """
        parsed = self._parser.parse_message(data)
        if not parsed:
            return None

        conn = self._db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO messages
            (id, session_id, parent_id, role, agent, model_id, provider_id,
             mode, cost, finish_reason, working_dir,
             tokens_input, tokens_output, tokens_reasoning,
             tokens_cache_read, tokens_cache_write, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                parsed.id,
                parsed.session_id,
                parsed.parent_id,
                parsed.role,
                parsed.agent,
                parsed.model_id,
                parsed.provider_id,
                parsed.mode,
                parsed.cost,
                parsed.finish_reason,
                parsed.working_dir,
                parsed.tokens_input,
                parsed.tokens_output,
                parsed.tokens_reasoning,
                parsed.tokens_cache_read,
                parsed.tokens_cache_write,
                parsed.created_at,
                parsed.completed_at,
            ],
        )

        self._stats["messages_indexed"] += 1

        # Update trace tokens if this is part of a child session
        if parsed.session_id:
            self._trace_builder.update_trace_tokens(parsed.session_id)

        return parsed.id

    def _process_part(self, data: dict) -> Optional[str]:
        """Process a part file.

        Args:
            data: Parsed JSON data

        Returns:
            Part ID if successful, None otherwise
        """
        parsed = self._parser.parse_part(data)
        if not parsed:
            return None

        conn = self._db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO parts
            (id, session_id, message_id, part_type, content, tool_name, tool_status,
             call_id, created_at, ended_at, duration_ms, arguments, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                parsed.id,
                parsed.session_id,
                parsed.message_id,
                parsed.part_type,
                parsed.content,
                parsed.tool_name,
                parsed.tool_status,
                parsed.call_id,
                parsed.created_at,
                parsed.ended_at,
                parsed.duration_ms,
                parsed.arguments,
                parsed.error_message,
            ],
        )

        self._stats["parts_indexed"] += 1

        # Handle special tools
        if parsed.tool_name == "skill":
            self._process_skill(data)
        elif parsed.tool_name == "task":
            self._process_delegation(data, parsed)
        elif parsed.tool_name in ("read", "write", "edit"):
            self._process_file_operation(data)

        return parsed.id

    def _process_skill(self, data: dict) -> None:
        """Process a skill tool invocation.

        Args:
            data: Raw JSON data
        """
        parsed = self._parser.parse_skill(data)
        if not parsed:
            return

        conn = self._db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO skills
            (id, message_id, session_id, skill_name, loaded_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                parsed.id,
                parsed.message_id,
                parsed.session_id,
                parsed.skill_name,
                parsed.loaded_at,
            ],
        )

    def _process_delegation(self, data: dict, part: Any) -> None:
        """Process a delegation (task tool) invocation.

        Creates both delegation record and agent_trace.

        Args:
            data: Raw JSON data
            part: Parsed part data
        """
        delegation = self._parser.parse_delegation(data)
        if not delegation:
            return

        # Insert delegation record
        conn = self._db.connect()

        # Resolve parent agent
        parent_agent = None
        if delegation.message_id:
            result = conn.execute(
                "SELECT agent FROM messages WHERE id = ?",
                [delegation.message_id],
            ).fetchone()
            if result:
                parent_agent = result[0]
                delegation.parent_agent = parent_agent

        conn.execute(
            """
            INSERT OR REPLACE INTO delegations
            (id, message_id, session_id, parent_agent, child_agent, child_session_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                delegation.id,
                delegation.message_id,
                delegation.session_id,
                delegation.parent_agent,
                delegation.child_agent,
                delegation.child_session_id,
                delegation.created_at,
            ],
        )

        # Create agent trace in real-time
        trace_id = self._trace_builder.create_trace_from_delegation(delegation, part)
        if trace_id:
            self._stats["traces_created"] += 1

    def _process_file_operation(self, data: dict) -> None:
        """Process a file operation (read/write/edit).

        Args:
            data: Raw JSON data
        """
        parsed = self._parser.parse_file_operation(data)
        if not parsed:
            return

        conn = self._db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO file_operations
            (id, session_id, trace_id, operation, file_path, timestamp, risk_level, risk_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                parsed.id,
                parsed.session_id,
                parsed.trace_id,
                parsed.operation,
                parsed.file_path,
                parsed.timestamp,
                parsed.risk_level,
                parsed.risk_reason,
            ],
        )

    def _process_todos(self, session_id: str, data: Any, path: Path) -> Optional[str]:
        """Process a todos file.

        Args:
            session_id: Session ID (from filename)
            data: Parsed JSON data (list of todos)
            path: Path to file for mtime

        Returns:
            Session ID if successful, None otherwise
        """
        if not isinstance(data, list):
            return None

        try:
            file_mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            file_mtime = datetime.now()

        todos = self._parser.parse_todos(session_id, data, file_mtime)
        if not todos:
            return None

        conn = self._db.connect()
        for todo in todos:
            conn.execute(
                """
                INSERT OR REPLACE INTO todos
                (id, session_id, content, status, priority, position, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    todo.id,
                    todo.session_id,
                    todo.content,
                    todo.status,
                    todo.priority,
                    todo.position,
                    todo.created_at,
                    todo.updated_at,
                ],
            )

        return session_id

    def _process_project(self, data: dict) -> Optional[str]:
        """Process a project file.

        Args:
            data: Parsed JSON data

        Returns:
            Project ID if successful, None otherwise
        """
        parsed = self._parser.parse_project(data)
        if not parsed:
            return None

        conn = self._db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO projects
            (id, worktree, vcs, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                parsed.id,
                parsed.worktree,
                parsed.vcs,
                parsed.created_at,
                parsed.updated_at,
            ],
        )

        return parsed.id

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
