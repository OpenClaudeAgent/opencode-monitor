"""
Unified Real-Time Indexer for OpenCode analytics.

This module replaces collector.py and loader.py with a single,
efficient system that provides:

- Real-time file watching via watchdog
- Change detection using mtime + size
- Progressive backfill for historical data
- Immediate agent trace creation

Usage:
    from opencode_monitor.analytics.indexer import (
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
