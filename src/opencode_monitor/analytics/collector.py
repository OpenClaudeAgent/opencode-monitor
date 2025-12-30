"""
Analytics Collector - Hybrid watcher + reconciliation approach.

Uses filesystem watcher for real-time detection of new files,
with periodic reconciliation to catch any missed files.

Performance:
- Watcher: instant notification of new files (0ms latency)
- Reconciliation: every 5 minutes, only processes files not in DB
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from .db import AnalyticsDB, get_analytics_db
from ..utils.logger import info, error, debug

# Paths
OPENCODE_STORAGE = Path.home() / ".local/share/opencode/storage"

# Timing
RECONCILIATION_INTERVAL = 300  # 5 minutes - catch missed files
BATCH_SIZE = 500  # Max files per reconciliation scan


class StorageEventHandler(FileSystemEventHandler):
    """Handle filesystem events for OpenCode storage."""

    def __init__(self, collector: "AnalyticsCollector"):
        super().__init__()
        self._collector = collector

    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle new file creation."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix != ".json":
            return

        # Determine file type from path
        parts = path.parts
        if "session" in parts:
            self._collector._queue_file("session", path)
        elif "message" in parts:
            self._collector._queue_file("message", path)
        elif "part" in parts:
            self._collector._queue_file("part", path)


class AnalyticsCollector:
    """Hybrid collector: watcher for real-time + reconciliation for safety."""

    def __init__(self):
        self._running = False
        self._observer: Optional[Observer] = None
        self._reconcile_thread: Optional[threading.Thread] = None
        self._process_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Queue for files to process (from watcher)
        self._file_queue: list[tuple[str, Path]] = []
        self._queue_lock = threading.Lock()

        # Track scanned file IDs (loaded from DB on init)
        self._scanned_sessions: Set[str] = set()
        self._scanned_messages: Set[str] = set()
        self._scanned_parts: Set[str] = set()

        # Stats
        self._stats = {
            "sessions": 0,
            "messages": 0,
            "parts": 0,
            "skills": 0,
            "delegations": 0,
            "last_reconciliation": None,
            "watcher_events": 0,
        }

        # Load already scanned IDs from DB
        self._load_scanned_ids()

    def _get_db(self) -> AnalyticsDB:
        """Get a fresh DB connection (connect/disconnect per batch for concurrency)."""
        db = AnalyticsDB()
        db.connect()
        return db

    def _load_scanned_ids(self) -> None:
        """Load already scanned file IDs from database."""
        db = None
        try:
            db = self._get_db()
            conn = db.connect()

            # Load session IDs
            rows = conn.execute("SELECT id FROM sessions").fetchall()
            self._scanned_sessions = {row[0] for row in rows}

            # Load message IDs
            rows = conn.execute("SELECT id FROM messages").fetchall()
            self._scanned_messages = {row[0] for row in rows}

            # Load part IDs
            rows = conn.execute("SELECT id FROM parts").fetchall()
            self._scanned_parts = {row[0] for row in rows}

            # Update stats
            self._stats["sessions"] = len(self._scanned_sessions)
            self._stats["messages"] = len(self._scanned_messages)
            self._stats["parts"] = len(self._scanned_parts)

            info(
                f"[AnalyticsCollector] Loaded {len(self._scanned_sessions)} sessions, "
                f"{len(self._scanned_messages)} messages, {len(self._scanned_parts)} parts"
            )
        except Exception as e:
            error(f"[AnalyticsCollector] Failed to load scanned IDs: {e}")
        finally:
            if db:
                db.close()

    def start(self) -> None:
        """Start the collector (watcher + reconciliation)."""
        if self._running:
            return

        self._running = True

        # Start filesystem watcher
        self._start_watcher()

        # Start queue processor thread
        self._process_thread = threading.Thread(
            target=self._process_queue_loop, daemon=True
        )
        self._process_thread.start()

        # Start reconciliation thread
        self._reconcile_thread = threading.Thread(
            target=self._reconciliation_loop, daemon=True
        )
        self._reconcile_thread.start()

        info("[AnalyticsCollector] Started (watcher + reconciliation)")

    def stop(self) -> None:
        """Stop the collector."""
        self._running = False

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)

        if self._process_thread:
            self._process_thread.join(timeout=5)

        if self._reconcile_thread:
            self._reconcile_thread.join(timeout=5)

        info("[AnalyticsCollector] Stopped")

    def _start_watcher(self) -> None:
        """Start the filesystem watcher."""
        if not OPENCODE_STORAGE.exists():
            debug("[AnalyticsCollector] Storage path not found, skipping watcher")
            return

        try:
            handler = StorageEventHandler(self)
            self._observer = Observer()

            # Watch session, message, and part directories
            for subdir in ["session", "message", "part"]:
                path = OPENCODE_STORAGE / subdir
                if path.exists():
                    self._observer.schedule(handler, str(path), recursive=True)
                    debug(f"[AnalyticsCollector] Watching {path}")

            self._observer.start()
            info("[AnalyticsCollector] Filesystem watcher started")
        except Exception as e:
            error(f"[AnalyticsCollector] Failed to start watcher: {e}")

    def _queue_file(self, file_type: str, path: Path) -> None:
        """Add a file to the processing queue."""
        with self._queue_lock:
            self._file_queue.append((file_type, path))
            self._stats["watcher_events"] += 1

    def _process_queue_loop(self) -> None:
        """Process queued files from watcher events."""
        while self._running:
            # Get batch of files to process
            with self._queue_lock:
                if not self._file_queue:
                    time.sleep(0.1)  # Short sleep when idle
                    continue
                batch = self._file_queue[:50]  # Process up to 50 at a time
                self._file_queue = self._file_queue[50:]

            # Process batch
            for file_type, path in batch:
                if not self._running:
                    break
                try:
                    self._process_single_file(file_type, path)
                except Exception as e:
                    debug(f"[AnalyticsCollector] Error processing {path}: {e}")

    def _process_single_file(self, file_type: str, path: Path, conn=None) -> bool:
        """Process a single file. Returns True if processed.

        Args:
            file_type: Type of file (session, message, part)
            path: Path to the JSON file
            conn: Optional DB connection (creates one if not provided)
        """
        file_id = path.stem

        # Check if already scanned
        if file_type == "session" and file_id in self._scanned_sessions:
            return False
        elif file_type == "message" and file_id in self._scanned_messages:
            return False
        elif file_type == "part" and file_id in self._scanned_parts:
            return False

        # Read and parse
        data = self._read_json(path)
        if not data or not data.get("id"):
            return False

        # Use provided connection or create temporary one
        db = None
        if conn is None:
            db = self._get_db()
            conn = db.connect()

        try:
            if file_type == "session":
                self._insert_session(conn, data)
                self._scanned_sessions.add(file_id)
                self._stats["sessions"] += 1
            elif file_type == "message":
                self._insert_message(conn, data)
                self._scanned_messages.add(file_id)
                self._stats["messages"] += 1
            elif file_type == "part":
                self._insert_part(conn, data)
                self._scanned_parts.add(file_id)
                self._stats["parts"] += 1
            return True
        except Exception as e:
            debug(f"[AnalyticsCollector] Insert error: {e}")
            return False
        finally:
            if db:
                db.close()

    def _reconciliation_loop(self) -> None:
        """Periodic reconciliation to catch missed files."""
        # Initial reconciliation immediately (1s delay for watcher to start)
        time.sleep(1)
        if self._running:
            info("[AnalyticsCollector] Running initial reconciliation (full scan)...")
            self._run_reconciliation(initial=True)

        # Then every RECONCILIATION_INTERVAL
        while self._running:
            time.sleep(RECONCILIATION_INTERVAL)
            if self._running:
                self._run_reconciliation(initial=False)

    def _run_reconciliation(self, initial: bool = False) -> None:
        """Run a reconciliation scan to catch missed files.

        Args:
            initial: If True, scan all files without batch limit (first run)
        """
        start_time = time.time()
        new_counts = {"sessions": 0, "messages": 0, "parts": 0}

        if not OPENCODE_STORAGE.exists():
            return

        # For initial reconciliation, no limit to scan everything
        batch_limit = None if initial else BATCH_SIZE

        # Single DB connection for entire reconciliation batch
        db = None
        try:
            db = self._get_db()
            conn = db.connect()

            # Reconcile each type with batch limit
            new_counts["sessions"] = self._reconcile_directory(
                "session",
                OPENCODE_STORAGE / "session",
                self._scanned_sessions,
                conn,
                batch_limit,
            )

            if not self._running and self._reconcile_thread is not None:
                return  # Early exit if shutting down

            new_counts["messages"] = self._reconcile_directory(
                "message",
                OPENCODE_STORAGE / "message",
                self._scanned_messages,
                conn,
                batch_limit,
            )

            if not self._running and self._reconcile_thread is not None:
                return

            new_counts["parts"] = self._reconcile_directory(
                "part",
                OPENCODE_STORAGE / "part",
                self._scanned_parts,
                conn,
                batch_limit,
            )

            with self._lock:
                self._stats["last_reconciliation"] = datetime.now().isoformat()

        except Exception as e:
            error(f"[AnalyticsCollector] Reconciliation error: {e}")
        finally:
            if db:
                db.close()

        elapsed = time.time() - start_time
        total_new = sum(new_counts.values())
        if total_new > 0:
            info(
                f"[AnalyticsCollector] Reconciliation: +{new_counts} in {elapsed:.2f}s"
            )
        else:
            debug(f"[AnalyticsCollector] Reconciliation: no new files ({elapsed:.2f}s)")

    def _reconcile_directory(
        self,
        file_type: str,
        directory: Path,
        scanned_set: Set[str],
        conn,
        batch_limit: Optional[int] = BATCH_SIZE,
    ) -> int:
        """Reconcile a directory, processing missed files.

        Args:
            file_type: Type of files to process
            directory: Directory to scan
            scanned_set: Set of already processed file IDs
            conn: Database connection to use
            batch_limit: Max files to process (None = no limit for initial scan)
        """
        if not directory.exists():
            return 0

        new_count = 0
        processed = 0

        # Sort subdirs by modification time (most recent first) for better coverage
        try:
            subdirs = sorted(
                [d for d in directory.iterdir() if d.is_dir()],
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            subdirs = [d for d in directory.iterdir() if d.is_dir()]

        for subdir in subdirs:
            if batch_limit is not None and processed >= batch_limit:
                break

            for json_file in subdir.glob("*.json"):
                if batch_limit is not None and processed >= batch_limit:
                    break

                file_id = json_file.stem
                if file_id in scanned_set:
                    continue

                if self._process_single_file(file_type, json_file, conn):
                    new_count += 1

                processed += 1

        return new_count

    def _read_json(self, path: Path) -> Optional[dict]:
        """Read and parse a JSON file."""
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _insert_session(self, conn, data: dict) -> None:
        """Insert a session record."""
        time_data = data.get("time", {})
        created = time_data.get("created")
        updated = time_data.get("updated")

        conn.execute(
            """INSERT OR REPLACE INTO sessions
            (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            [
                data.get("id"),
                data.get("projectID"),
                data.get("directory"),
                data.get("title"),
                datetime.fromtimestamp(created / 1000) if created else None,
                datetime.fromtimestamp(updated / 1000) if updated else None,
            ],
        )

    def _insert_message(self, conn, data: dict) -> None:
        """Insert a message record."""
        time_data = data.get("time", {})
        tokens = data.get("tokens", {})
        cache = tokens.get("cache", {})

        created = time_data.get("created")
        completed = time_data.get("completed")

        conn.execute(
            """INSERT OR REPLACE INTO messages
            (id, session_id, parent_id, role, agent, model_id, provider_id,
             tokens_input, tokens_output, tokens_reasoning,
             tokens_cache_read, tokens_cache_write, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                data.get("id"),
                data.get("sessionID"),
                data.get("parentID"),
                data.get("role"),
                data.get("agent"),
                data.get("modelID"),
                data.get("providerID"),
                tokens.get("input", 0),
                tokens.get("output", 0),
                tokens.get("reasoning", 0),
                cache.get("read", 0),
                cache.get("write", 0),
                datetime.fromtimestamp(created / 1000) if created else None,
                datetime.fromtimestamp(completed / 1000) if completed else None,
            ],
        )

    def _insert_part(self, conn, data: dict) -> None:
        """Insert a part record."""
        time_data = data.get("time", {})
        state = data.get("state", {})
        created = time_data.get("start")

        # Only insert tool parts
        if data.get("type") != "tool":
            return

        tool_name = data.get("tool")
        if not tool_name:
            return

        conn.execute(
            """INSERT OR REPLACE INTO parts
            (id, message_id, part_type, tool_name, tool_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            [
                data.get("id"),
                data.get("messageID"),
                data.get("type"),
                tool_name,
                state.get("status"),
                datetime.fromtimestamp(created / 1000) if created else None,
            ],
        )

        # Handle special tools: skill and task (delegation)
        if tool_name == "skill":
            self._insert_skill(conn, data)
        elif tool_name == "task":
            self._insert_delegation(conn, data)

    def _insert_skill(self, conn, data: dict) -> None:
        """Insert a skill usage record."""
        state = data.get("state", {})
        input_data = state.get("input", {})
        skill_name = input_data.get("name")

        if not skill_name:
            return

        time_data = data.get("time", {})
        loaded_at = time_data.get("start")

        conn.execute(
            """INSERT OR REPLACE INTO skills
            (id, message_id, session_id, skill_name, loaded_at)
            VALUES (?, ?, ?, ?, ?)""",
            [
                data.get("id"),
                data.get("messageID"),
                data.get("sessionID"),
                skill_name,
                datetime.fromtimestamp(loaded_at / 1000) if loaded_at else None,
            ],
        )
        self._stats["skills"] += 1

    def _insert_delegation(self, conn, data: dict) -> None:
        """Insert a delegation record."""
        state = data.get("state", {})
        input_data = state.get("input", {})
        subagent_type = input_data.get("subagent_type")

        if not subagent_type:
            return

        time_data = state.get("time", {})
        created_at = time_data.get("start")
        metadata = state.get("metadata", {})

        # Get parent agent from message
        parent_agent = None
        try:
            row = conn.execute(
                "SELECT agent FROM messages WHERE id = ?", [data.get("messageID")]
            ).fetchone()
            if row:
                parent_agent = row[0]
        except Exception:
            pass

        conn.execute(
            """INSERT OR REPLACE INTO delegations
            (id, message_id, session_id, parent_agent, child_agent, child_session_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                data.get("id"),
                data.get("messageID"),
                data.get("sessionID"),
                parent_agent,
                subagent_type,
                metadata.get("sessionId"),
                datetime.fromtimestamp(created_at / 1000) if created_at else None,
            ],
        )
        self._stats["delegations"] += 1

    # ===== Public API =====

    def get_stats(self) -> dict:
        """Get current collection statistics."""
        with self._lock:
            return self._stats.copy()

    def get_db(self) -> AnalyticsDB:
        """Get a new analytics database instance.

        Note: Returns a new instance each time. Caller should close() when done.
        """
        return self._get_db()


# Global instance
_collector: Optional[AnalyticsCollector] = None


def get_collector() -> AnalyticsCollector:
    """Get or create the global collector instance."""
    global _collector
    if _collector is None:
        _collector = AnalyticsCollector()
    return _collector


def start_collector() -> None:
    """Start the analytics collector."""
    get_collector().start()


def stop_collector() -> None:
    """Stop the analytics collector."""
    global _collector
    if _collector:
        _collector.stop()
        _collector = None
