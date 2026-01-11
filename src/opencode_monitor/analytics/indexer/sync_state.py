"""
Sync state management for hybrid indexer.

Tracks the indexing phase and progress, enabling:
- Dashboard to show sync status
- Crash recovery (resume from last checkpoint)
- Coordination between bulk loader and watcher
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import threading

from ..db import AnalyticsDB


class SyncPhase(str, Enum):
    """Current phase of the sync process."""

    INIT = "init"
    BULK_SESSIONS = "bulk_sessions"
    BULK_MESSAGES = "bulk_messages"
    BULK_PARTS = "bulk_parts"
    PROCESSING_QUEUE = "processing_queue"
    REALTIME = "realtime"


@dataclass
class SyncStatus:
    """Current sync status for API/dashboard."""

    phase: SyncPhase
    t0: Optional[float]  # Cutoff timestamp
    progress: float  # 0-100
    files_total: int
    files_done: int
    queue_size: int
    eta_seconds: Optional[float]
    last_indexed: Optional[datetime]
    is_ready: bool  # True when basic data is available for queries

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "phase": self.phase.value,
            "t0": self.t0,
            "progress": round(self.progress, 1),
            "files_total": self.files_total,
            "files_done": self.files_done,
            "queue_size": self.queue_size,
            "eta_seconds": round(self.eta_seconds, 1) if self.eta_seconds else None,
            "last_indexed": self.last_indexed.isoformat()
            if self.last_indexed
            else None,
            "is_ready": self.is_ready,
        }


class SyncState:
    """
    Manages sync state with persistence for crash recovery.

    State is stored in DuckDB table 'sync_state' and updated
    at each checkpoint (phase transition, progress update).

    Thread-safe for concurrent access from bulk loader, watcher, and API.
    """

    def __init__(self, db: AnalyticsDB):
        self._db = db
        self._lock = threading.Lock()
        self._ensure_table()

        # In-memory state (faster access)
        self._phase = SyncPhase.INIT
        self._t0: Optional[float] = None
        self._files_total = 0
        self._files_done = 0
        self._queue_size = 0
        self._last_indexed: Optional[datetime] = None
        self._start_time: Optional[float] = None

        # Load from DB if exists
        self._load_from_db()

    def _ensure_table(self) -> None:
        """Create sync_state table if not exists."""
        conn = self._db.connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                phase VARCHAR NOT NULL DEFAULT 'init',
                t0 DOUBLE,
                files_total INTEGER DEFAULT 0,
                files_done INTEGER DEFAULT 0,
                sessions_done BOOLEAN DEFAULT FALSE,
                messages_done BOOLEAN DEFAULT FALSE,
                parts_done BOOLEAN DEFAULT FALSE,
                queue_processed BOOLEAN DEFAULT FALSE,
                last_indexed TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert initial row if not exists
        conn.execute("""
            INSERT OR IGNORE INTO sync_state (id) VALUES (1)
        """)

    def _load_from_db(self) -> None:
        """Load state from database (for crash recovery)."""
        conn = self._db.connect()
        row = conn.execute("""
            SELECT phase, t0, files_total, files_done, last_indexed
            FROM sync_state WHERE id = 1
        """).fetchone()

        if row:
            try:
                self._phase = SyncPhase(row[0])
            except ValueError:
                self._phase = SyncPhase.INIT
            self._t0 = row[1]
            self._files_total = row[2] or 0
            self._files_done = row[3] or 0
            self._last_indexed = row[4]

    def _save_to_db(self) -> None:
        """Persist current state to database."""
        conn = self._db.connect()
        conn.execute(
            """
            UPDATE sync_state SET
                phase = ?,
                t0 = ?,
                files_total = ?,
                files_done = ?,
                last_indexed = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        """,
            [
                self._phase.value,
                self._t0,
                self._files_total,
                self._files_done,
                self._last_indexed,
            ],
        )

    def start_bulk(self, t0: float, total_files: int) -> None:
        """Start bulk loading phase."""
        with self._lock:
            self._phase = SyncPhase.BULK_SESSIONS
            self._t0 = t0
            self._files_total = total_files
            self._files_done = 0
            self._start_time = t0
            self._save_to_db()

    def set_phase(self, phase: SyncPhase) -> None:
        """Update current phase."""
        with self._lock:
            self._phase = phase
            self._save_to_db()

    def update_progress(self, files_done: int, queue_size: int = 0) -> None:
        """Update progress counters."""
        with self._lock:
            self._files_done = files_done
            self._queue_size = queue_size
            self._last_indexed = datetime.now()
            # Don't save to DB on every progress update (too slow)
            # Only save on phase transitions

    def checkpoint(self) -> None:
        """Save current state to DB (call at phase transitions)."""
        with self._lock:
            self._save_to_db()

    def set_queue_size(self, size: int) -> None:
        """Update queue size."""
        with self._lock:
            self._queue_size = size

    def get_status(self) -> SyncStatus:
        """Get current status for API/dashboard."""
        with self._lock:
            # Calculate ETA
            eta = None
            if self._start_time and self._files_done > 0:
                elapsed = datetime.now().timestamp() - self._start_time
                rate = self._files_done / elapsed
                remaining = self._files_total - self._files_done
                if rate > 0:
                    eta = remaining / rate

            # Calculate progress
            progress = 0.0
            if self._files_total > 0:
                progress = (self._files_done / self._files_total) * 100

            is_ready = self._phase == SyncPhase.REALTIME

            return SyncStatus(
                phase=self._phase,
                t0=self._t0,
                progress=progress,
                files_total=self._files_total,
                files_done=self._files_done,
                queue_size=self._queue_size,
                eta_seconds=eta,
                last_indexed=self._last_indexed,
                is_ready=is_ready,
            )

    def reset(self) -> None:
        """Reset state for fresh start."""
        with self._lock:
            self._phase = SyncPhase.INIT
            self._t0 = None
            self._files_total = 0
            self._files_done = 0
            self._queue_size = 0
            self._last_indexed = None
            self._start_time = None
            self._save_to_db()

    @property
    def phase(self) -> SyncPhase:
        """Current phase."""
        return self._phase

    @property
    def t0(self) -> Optional[float]:
        """Cutoff timestamp."""
        return self._t0

    @property
    def is_realtime(self) -> bool:
        """True if in realtime mode."""
        return self._phase == SyncPhase.REALTIME
