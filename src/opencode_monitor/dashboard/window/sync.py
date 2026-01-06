"""
Sync checker for detecting when menubar has synced new data.

The dashboard operates in read-only mode. The menubar updates sync_meta
when it syncs new data. SyncChecker polls that table and triggers a
refresh when new data is detected.

Performance optimization: Skips refresh during backfill to avoid
hammering the API with heavy requests while indexing is in progress.
"""

import time
from datetime import datetime
from typing import Callable, Optional

from PyQt6.QtCore import QTimer


class SyncChecker:
    """Polls sync_meta to detect when menubar has synced new data.

    The dashboard operates in read-only mode. The menubar updates sync_meta
    when it syncs new data. This class polls that table and triggers a
    refresh when new data is detected.

    Performance optimization: Skips refresh during backfill to avoid
    hammering the API with heavy requests while indexing is in progress.
    """

    POLL_FAST_MS = 2000  # During activity
    POLL_SLOW_MS = 5000  # At rest
    POLL_BACKFILL_MS = 10000  # During backfill - much slower
    IDLE_THRESHOLD_S = 30  # Switch to slow after 30s without change

    def __init__(self, on_sync_detected: Callable[[], None]):
        """Initialize the sync checker.

        Args:
            on_sync_detected: Callback to invoke when new sync is detected.
        """
        self._on_sync = on_sync_detected
        self._known_sync: Optional[datetime] = None
        self._last_change_time = time.time()
        self._backfill_active = False

        self._timer = QTimer()
        self._timer.timeout.connect(self._check)
        self._timer.start(self.POLL_FAST_MS)

    @property
    def is_backfill_active(self) -> bool:
        """Check if backfill is currently active."""
        return self._backfill_active

    def _check(self) -> None:
        """Check if API is available and data has changed."""
        try:
            from ...api import get_api_client

            client = get_api_client()

            # Use API health check instead of direct DB access
            if client.is_available:
                # Check backfill status first
                sync_status = client.get_sync_status()
                if sync_status:
                    self._backfill_active = sync_status.get("backfill_active", False)

                    if self._backfill_active:
                        # During backfill, slow down polling and skip refresh
                        self._timer.setInterval(self.POLL_BACKFILL_MS)
                        return  # Don't trigger refresh during backfill

                # Get stats to check for changes
                stats = client.get_stats()
                if stats:
                    # Use session count as change indicator
                    current = stats.get("sessions", 0)

                    if current != self._known_sync:
                        self._known_sync = current
                        self._last_change_time = time.time()
                        self._timer.setInterval(self.POLL_FAST_MS)  # Active mode
                        self._on_sync()  # Trigger refresh
                    elif time.time() - self._last_change_time > self.IDLE_THRESHOLD_S:
                        self._timer.setInterval(self.POLL_SLOW_MS)  # Quiet mode
        except Exception:
            pass  # nosec B110 - API may not be available

    def stop(self) -> None:
        """Stop the sync checker."""
        self._timer.stop()
