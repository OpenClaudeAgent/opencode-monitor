"""
Unified Real-Time Indexer for OpenCode analytics.

This module provides the UnifiedIndexer v2 with:
- Real-time file watching via watchdog
- Micro-batch processing for high throughput (~10,000 files/sec)
- Periodic reconciliation for missed files
- DuckDB-based persistence

Usage:
    from opencode_monitor.analytics.indexer import (
        start_indexer,
        stop_indexer,
        get_indexer,
    )

    # Start the indexer
    start_indexer()

    # Get stats
    indexer = get_indexer()
    stats = indexer.get_stats()

    # Stop when done
    stop_indexer()
"""

from .unified import (
    UnifiedIndexer,
    get_indexer,
    start_indexer,
    stop_indexer,
)
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
from .batch_accumulator import FileBatchAccumulator, AccumulatorConfig, AccumulatorStats
from .reconciler import Reconciler, ReconcilerConfig, ReconcilerStats


__all__ = [
    # Main class
    "UnifiedIndexer",
    # Global functions
    "get_indexer",
    "start_indexer",
    "stop_indexer",
    # Components
    "FileTracker",
    "FileInfo",
    "FileParser",
    "TraceBuilder",
    "FileWatcher",
    "ProcessingQueue",
    # v2 Components
    "FileBatchAccumulator",
    "AccumulatorConfig",
    "AccumulatorStats",
    "Reconciler",
    "ReconcilerConfig",
    "ReconcilerStats",
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
