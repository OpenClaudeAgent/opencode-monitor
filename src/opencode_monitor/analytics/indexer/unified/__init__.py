"""
Unified Real-Time Indexer for OpenCode data.

This package replaces the monolithic unified.py with a modular structure:

- config.py: Configuration constants
- batch.py: Batch processing for high-throughput indexing
- processing.py: Individual file processing for real-time updates
- core.py: Main UnifiedIndexer class and global instance management

Usage:
    from opencode_monitor.analytics.indexer.unified import (
        UnifiedIndexer,
        start_indexer,
        stop_indexer,
        get_indexer,
    )

    # Start the indexer (runs in background)
    start_indexer()

    # Or create a custom instance
    indexer = UnifiedIndexer(storage_path=my_path)
    indexer.start()

    # Get stats
    stats = indexer.get_stats()

    # Stop when done
    stop_indexer()
"""

from .core import (
    UnifiedIndexer,
    get_indexer,
    start_indexer,
    stop_indexer,
)

from .config import (
    OPENCODE_STORAGE,
    BACKFILL_BATCH_SIZE,
    BACKFILL_THROTTLE_MS,
    BACKFILL_INTERVAL,
    NUM_WORKERS,
)

from .batch import BatchProcessor
from .processing import FileProcessor
from .bulk_load import is_cold_start, bulk_load_initial


__all__ = [
    # Main class
    "UnifiedIndexer",
    # Global functions
    "get_indexer",
    "start_indexer",
    "stop_indexer",
    # Configuration
    "OPENCODE_STORAGE",
    "BACKFILL_BATCH_SIZE",
    "BACKFILL_THROTTLE_MS",
    "BACKFILL_INTERVAL",
    "NUM_WORKERS",
    # Internal components (for testing)
    "BatchProcessor",
    "FileProcessor",
    # Bulk load (for initial indexing)
    "is_cold_start",
    "bulk_load_initial",
]
