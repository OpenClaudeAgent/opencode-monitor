"""
Batch processing for the Unified Indexer.

Handles high-performance batch processing of files using bulk INSERT operations.
"""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...db import AnalyticsDB
    from ..parsers import FileParser
    from ..tracker import FileTracker
    from ..trace_builder import TraceBuilder


class BatchProcessor:
    """Handles batch processing of files for high-throughput indexing.

    Uses bulk INSERT operations for efficient database writes.
    """

    def __init__(
        self,
        db: "AnalyticsDB",
        parser: "FileParser",
        tracker: "FileTracker",
        trace_builder: "TraceBuilder",
        stats: dict,
    ):
        """Initialize the batch processor.

        Args:
            db: Analytics database connection
            parser: File parser for reading JSON files
            tracker: File tracker for marking indexed files
            trace_builder: Trace builder for creating agent traces
            stats: Shared statistics dictionary
        """
        self._db = db
        self._parser = parser
        self._tracker = tracker
        self._trace_builder = trace_builder
        self._stats = stats

    def process_files(self, file_type: str, files: list[Path]) -> int:
        """Process files in batch with bulk INSERT.

        Args:
            file_type: Type of files to process
            files: List of file paths

        Returns:
            Number of files successfully processed
        """
        if file_type == "session":
            return self._process_sessions(files)
        elif file_type == "message":
            return self._process_messages(files)
        elif file_type == "part":
            return self._process_parts(files)
        else:
            # Unsupported type for batch processing
            return 0

    def _process_sessions(self, files: list[Path]) -> int:
        """Batch process session files."""
        records = []
        root_sessions = []
        paths_processed = []

        # Parse all files
        for path in files:
            raw_data = self._parser.read_json(path)
            if raw_data is None:
                self._tracker.mark_error(path, "session", "Failed to read JSON")
                continue

            parsed = self._parser.parse_session(raw_data)
            if not parsed:
                self._tracker.mark_error(path, "session", "Invalid data")
                continue

            records.append(
                (
                    parsed.id,
                    parsed.project_id,
                    parsed.directory,
                    parsed.title,
                    parsed.parent_id,
                    parsed.version,
                    parsed.additions,
                    parsed.deletions,
                    parsed.files_changed,
                    parsed.created_at,
                    parsed.updated_at,
                )
            )
            paths_processed.append((path, parsed.id))

            if not parsed.parent_id:
                root_sessions.append(parsed)

        if not records:
            return 0

        # Batch INSERT
        conn = self._db.connect()
        conn.executemany(
            """
            INSERT OR REPLACE INTO sessions
            (id, project_id, directory, title, parent_id, version,
             additions, deletions, files_changed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

        # Mark all as indexed (batch)
        self._tracker.mark_indexed_batch(
            [(path, "session", record_id) for path, record_id in paths_processed]
        )

        # Create root traces
        for parsed in root_sessions:
            self._trace_builder.create_root_trace(
                session_id=parsed.id,
                title=parsed.title,
                agent=None,
                first_message=None,
                created_at=parsed.created_at,
                updated_at=parsed.updated_at,
            )
            self._stats["traces_created"] += 1

        self._stats["sessions_indexed"] += len(records)
        return len(records)

    def _process_messages(self, files: list[Path]) -> int:
        """Batch process message files."""
        records = []
        paths_processed = []

        # Parse all files
        for path in files:
            raw_data = self._parser.read_json(path)
            if raw_data is None:
                self._tracker.mark_error(path, "message", "Failed to read JSON")
                continue

            parsed = self._parser.parse_message(raw_data)
            if not parsed:
                self._tracker.mark_error(path, "message", "Invalid data")
                continue

            records.append(
                (
                    parsed.id,
                    parsed.session_id,
                    parsed.parent_id,
                    parsed.role,
                    parsed.agent,
                    parsed.model_id,
                    parsed.provider_id,
                    parsed.mode,
                    parsed.cost,
                    parsed.finish_reason,
                    parsed.working_dir,
                    parsed.tokens_input,
                    parsed.tokens_output,
                    parsed.tokens_reasoning,
                    parsed.tokens_cache_read,
                    parsed.tokens_cache_write,
                    parsed.created_at,
                    parsed.completed_at,
                )
            )
            paths_processed.append((path, parsed.id))

        if not records:
            return 0

        # Batch INSERT
        conn = self._db.connect()
        conn.executemany(
            """
            INSERT OR REPLACE INTO messages
            (id, session_id, parent_id, role, agent, model_id, provider_id,
             mode, cost, finish_reason, working_dir,
             tokens_input, tokens_output, tokens_reasoning,
             tokens_cache_read, tokens_cache_write, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

        # Mark all as indexed (batch)
        self._tracker.mark_indexed_batch(
            [(path, "message", record_id) for path, record_id in paths_processed]
        )

        self._stats["messages_indexed"] += len(records)
        return len(records)

    def _process_parts(self, files: list[Path]) -> int:
        """Batch process part files."""
        records = []
        paths_processed = []
        delegations = []

        # Parse all files
        for path in files:
            raw_data = self._parser.read_json(path)
            if raw_data is None:
                self._tracker.mark_error(path, "part", "Failed to read JSON")
                continue

            parsed = self._parser.parse_part(raw_data)
            if not parsed:
                self._tracker.mark_error(path, "part", "Invalid data")
                continue

            records.append(
                (
                    parsed.id,
                    parsed.session_id,
                    parsed.message_id,
                    parsed.part_type,
                    parsed.content,
                    parsed.tool_name,
                    parsed.tool_status,
                    parsed.call_id,
                    parsed.created_at,
                    parsed.ended_at,
                    parsed.duration_ms,
                    parsed.arguments,
                    parsed.error_message,
                )
            )
            paths_processed.append((path, parsed.id))

            # Check for delegation (task tool)
            if parsed.tool_name == "task" and parsed.tool_status == "completed":
                delegation = self._parser.parse_delegation(raw_data)
                if delegation:
                    delegations.append((delegation, parsed))

        if not records:
            return 0

        # Batch INSERT
        conn = self._db.connect()
        conn.executemany(
            """
            INSERT OR REPLACE INTO parts
            (id, session_id, message_id, part_type, content, tool_name, tool_status,
             call_id, created_at, ended_at, duration_ms, arguments, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

        # Mark all as indexed (batch)
        self._tracker.mark_indexed_batch(
            [(path, "part", record_id) for path, record_id in paths_processed]
        )

        # Create traces for delegations
        for delegation, part in delegations:
            trace_id = self._trace_builder.create_trace_from_delegation(
                delegation, part
            )
            if trace_id:
                self._stats["traces_created"] += 1

        self._stats["parts_indexed"] += len(records)
        return len(records)
