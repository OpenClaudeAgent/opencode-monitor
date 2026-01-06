"""
Unified Real-Time Indexer for OpenCode analytics.

This module provides two indexing strategies:

1. HybridIndexer (recommended): Fast bulk loading via DuckDB native JSON,
   then real-time watching. ~20,000 files/sec for bulk, ~250/sec realtime.

2. UnifiedIndexer (legacy): Python-based processing, ~250 files/sec.

Usage:
    from opencode_monitor.analytics.indexer import (
        start_indexer,
        stop_indexer,
        get_sync_status,
    )

    # Start the indexer (uses HybridIndexer by default)
    start_indexer()

    # Get sync status for dashboard
    status = get_sync_status()
    print(f"Phase: {status.phase}, Progress: {status.progress}%")

    # Stop when done
    stop_indexer()
"""

from .unified import (
    UnifiedIndexer,
    get_indexer as get_unified_indexer,
    start_indexer as start_unified_indexer,
    stop_indexer as stop_unified_indexer,
)
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


# Default to HybridIndexer for better performance
def start_indexer():
    """Start the indexer (uses HybridIndexer for fast bulk loading)."""
    start_hybrid_indexer()


def stop_indexer():
    """Stop the indexer."""
    stop_hybrid_indexer()


def get_indexer():
    """Get the indexer instance."""
    return get_hybrid_indexer()


from .parsers import (  # noqa: E402
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
from .trace_builder import TraceBuilder  # noqa: E402
from .watcher import FileWatcher, ProcessingQueue  # noqa: E402


__all__ = [
    # Main classes
    "HybridIndexer",
    "IndexerRegistry",
    "UnifiedIndexer",
    # Global functions (default to Hybrid)
    "get_indexer",
    "start_indexer",
    "stop_indexer",
    "get_sync_status",
    # Hybrid-specific
    "get_hybrid_indexer",
    "start_hybrid_indexer",
    "stop_hybrid_indexer",
    # Legacy/unified-specific
    "get_unified_indexer",
    "start_unified_indexer",
    "stop_unified_indexer",
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
