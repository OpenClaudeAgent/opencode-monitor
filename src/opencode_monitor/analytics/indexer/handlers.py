"""
File handlers for processing different file types in realtime mode.

Each handler encapsulates the logic for parsing and persisting a specific
file type (session, message, part). This follows the Strategy pattern and
improves testability by allowing handlers to be mocked independently.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from ..ingestion.processor import IngestionProcessor
from ..path_matcher import DiffPathMatcher, build_diff_stats_map

if TYPE_CHECKING:
    from .parsers import FileParser
    from .trace_builder import TraceBuilder


class FileHandler(ABC):
    """
    Abstract base class for file handlers.

    Each handler processes a specific file type and persists it to the database.
    """

    @abstractmethod
    def process(
        self,
        file_path: Path,
        raw_data: Any,
        conn,
        parser: "FileParser",
        trace_builder: "TraceBuilder",
    ) -> Optional[str]:
        pass


class SessionHandler(FileHandler):
    """Handler for session files."""

    def process(
        self,
        file_path: Path,
        raw_data: dict,
        conn,
        parser: "FileParser",
        trace_builder: "TraceBuilder",
    ) -> Optional[str]:
        """Process a session file and persist to database."""
        # Use processor for unified ingestion logic
        processor = IngestionProcessor()
        processor.process_session(file_path, conn)

        # Legacy logic for root trace (using parser to check parent_id)
        # We parse just to get metadata for trace builder
        parsed = parser.parse_session(raw_data)
        if not parsed:
            return None

        # Create root trace if no parent
        if not parsed.parent_id:
            trace_builder.create_root_trace(
                session_id=parsed.id,
                title=parsed.title,
                agent=None,
                first_message=None,
                created_at=parsed.created_at,
                updated_at=parsed.updated_at,
            )

        return parsed.id


class MessageHandler(FileHandler):
    """Handler for message files."""

    def process(
        self,
        file_path: Path,
        raw_data: dict,
        conn,
        parser: "FileParser",
        trace_builder: "TraceBuilder",
    ) -> Optional[str]:
        """Process a message file and persist to database."""
        processor = IngestionProcessor()
        processor.process_message(file_path, conn)

        parsed = parser.parse_message(raw_data)
        if not parsed:
            return None

        return parsed.id


class PartHandler(FileHandler):
    """Handler for part files."""

    def process(
        self,
        file_path: Path,
        raw_data: dict,
        conn,
        parser: "FileParser",
        trace_builder: "TraceBuilder",
    ) -> Optional[str]:
        """Process a part file and persist to database."""
        processor = IngestionProcessor()
        processor.process_part(file_path, conn)

        parsed = parser.parse_part(raw_data)
        if not parsed:
            return None

        return parsed.id


class SessionDiffHandler(FileHandler):
    """Handler for session_diff files - enriches file_operations with diff stats."""

    def process(
        self,
        file_path: Path,
        raw_data: Any,
        conn,
        parser: "FileParser",
        trace_builder: "TraceBuilder",
    ) -> Optional[str]:
        session_id = file_path.stem

        if not isinstance(raw_data, list):
            return None

        diff_by_file = build_diff_stats_map(raw_data)
        if not diff_by_file:
            return session_id

        matcher = DiffPathMatcher(diff_by_file)

        file_ops = conn.execute(
            """SELECT id, file_path FROM file_operations 
               WHERE session_id = ? AND operation IN ('write', 'edit')""",
            [session_id],
        ).fetchall()

        for op_id, op_file_path in file_ops:
            stats = matcher.match(op_file_path)
            if stats:
                conn.execute(
                    """UPDATE file_operations 
                       SET additions = ?, deletions = ? 
                       WHERE id = ?""",
                    [stats["additions"], stats["deletions"], op_id],
                )

        return session_id
