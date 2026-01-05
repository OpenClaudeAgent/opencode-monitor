"""
Configuration constants for the Unified Indexer.
"""

from pathlib import Path


# Default storage path
OPENCODE_STORAGE = Path.home() / ".local" / "share" / "opencode" / "storage"

# Backfill configuration
BACKFILL_BATCH_SIZE = 10000  # Max files per cycle (increased for parallel)
BACKFILL_THROTTLE_MS = 1  # Minimal pause
BACKFILL_INTERVAL = 2  # Seconds between backfill cycles
NUM_WORKERS = 8  # Number of parallel workers
