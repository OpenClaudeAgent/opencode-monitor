"""
Real-Time Indexer for OpenCode analytics.

HybridIndexer: Fast bulk loading via DuckDB native JSON,
then real-time watching. ~20,000 files/sec for bulk, ~250/sec realtime.

Usage:
    from opencode_monitor.analytics.indexer import (
        start_indexer,
        stop_indexer,
        get_sync_status,
    )

    # Start the indexer
    start_indexer()

    # Get sync status for dashboard
    status = get_sync_status()
    print(f"Phase: {status.phase}, Progress: {status.progress}%")

    # Stop when done
    stop_indexer()
"""

from .hybrid import (
    HybridIndexer,
    IndexerRegistry,
    get_hybrid_indexer,
    start_hybrid_indexer,
    stop_hybrid_indexer,
    get_sync_status,
)
from .sync_state import SyncState, SyncPhase, SyncStatus
from .tracker import FileTracker, FileInfo
from .parsers import (
    FileParser,
    ParsedSession,
    ParsedMessage,
    ParsedPart,
    ParsedDelegation,
    ParsedSkill,
    ParsedTodo,
    ParsedProject,
    ParsedFileOperation,
)
from .trace_builder import TraceBuilder
from .watcher import FileWatcher, ProcessingQueue


# Default to HybridIndexer
def start_indexer():
    """Start the indexer."""
    start_hybrid_indexer()


def stop_indexer():
    """Stop the indexer."""
    stop_hybrid_indexer()


def get_indexer():
    """Get the indexer instance."""
    return get_hybrid_indexer()


__all__ = [
    # Main classes
    "HybridIndexer",
    "IndexerRegistry",
    # Global functions
    "get_indexer",
    "start_indexer",
    "stop_indexer",
    "get_sync_status",
    # Hybrid-specific
    "get_hybrid_indexer",
    "start_hybrid_indexer",
    "stop_hybrid_indexer",
    # Sync state
    "SyncState",
    "SyncPhase",
    "SyncStatus",
    # Components
    "FileTracker",
    "FileInfo",
    "FileParser",
    "TraceBuilder",
    "FileWatcher",
    "ProcessingQueue",
    # Parsed data classes
    "ParsedSession",
    "ParsedMessage",
    "ParsedPart",
    "ParsedDelegation",
    "ParsedSkill",
    "ParsedTodo",
    "ParsedProject",
    "ParsedFileOperation",
]
