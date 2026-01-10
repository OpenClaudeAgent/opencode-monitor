"""
Configuration constants for the Unified Indexer.
"""

from pathlib import Path


# Default storage path
OPENCODE_STORAGE = Path.home() / ".local" / "share" / "opencode" / "storage"

# Backfill configuration (tuned for smooth startup)
BACKFILL_BATCH_SIZE = 2000  # Max files per cycle (reduced for smoother UI)
BACKFILL_THROTTLE_MS = 1  # Minimal pause
BACKFILL_INTERVAL = 10  # Seconds between backfill cycles (less aggressive)
NUM_WORKERS = 4  # Number of parallel workers

# v2 Accumulator configuration
ACCUMULATOR_WINDOW_MS = 500  # 500ms window for batching
ACCUMULATOR_MAX_FILES = 200  # Max files per micro-batch

# v2 Reconciler configuration
RECONCILER_INTERVAL = 30  # Seconds between scans (30s is plenty)
RECONCILER_MAX_FILES = 5000  # Max files per scan (smaller = faster startup)
RECONCILER_INITIAL_DELAY = 5  # Delay before first scan (let UI start first)
