"""
Individual file processing for the Unified Indexer.

Handles processing of individual files for real-time indexing.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from ....utils.logger import debug

if TYPE_CHECKING:
    from ...db import AnalyticsDB
    from ..parsers import FileParser
    from ..tracker import FileTracker
    from ..trace_builder import TraceBuilder


class FileProcessor:
    """Handles individual file processing for real-time indexing.

    Processes files one at a time, suitable for real-time updates
    from the file watcher.
    """

    def __init__(
        self,
        db: "AnalyticsDB",
        parser: "FileParser",
        tracker: "FileTracker",
        trace_builder: "TraceBuilder",
        stats: dict,
    ):
        """Initialize the file processor.

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

    def process_file(self, file_type: str, path: Path) -> bool:
        """Process a single file.

        Args:
            file_type: Type of file
            path: Path to the file

        Returns:
            True if processed successfully, False otherwise
        """
        # Read and parse
        raw_data = self._parser.read_json(path)
        if raw_data is None:
            self._tracker.mark_error(path, file_type, "Failed to read JSON")
            self._stats["files_error"] += 1
            return False

        # Process based on type
        try:
            record_id = None

            if file_type == "session":
                record_id = self._process_session(raw_data)
            elif file_type == "message":
                record_id = self._process_message(raw_data)
            elif file_type == "part":
                record_id = self._process_part(raw_data)
            elif file_type == "todo":
                record_id = self._process_todos(path.stem, raw_data, path)
            elif file_type == "project":
                record_id = self._process_project(raw_data)

            if record_id:
                self._tracker.mark_indexed(path, file_type, record_id)
                self._stats["files_processed"] += 1
                return True
            else:
                self._tracker.mark_error(path, file_type, "Invalid data")
                self._stats["files_error"] += 1
                return False

        except Exception as e:
            self._tracker.mark_error(path, file_type, str(e))
            self._stats["files_error"] += 1
            debug(f"[UnifiedIndexer] Error processing {path}: {e}")
            return False

    def _process_session(self, data: dict) -> Optional[str]:
        """Process a session file.

        Args:
            data: Parsed JSON data

        Returns:
            Session ID if successful, None otherwise
        """
        parsed = self._parser.parse_session(data)
        if not parsed:
            return None

        conn = self._db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO sessions
            (id, project_id, directory, title, parent_id, version,
             additions, deletions, files_changed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
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
            ],
        )

        self._stats["sessions_indexed"] += 1

        # Create root trace for sessions without parent
        if not parsed.parent_id:
            self._trace_builder.create_root_trace(
                session_id=parsed.id,
                title=parsed.title,
                agent=None,  # Will be resolved when messages are indexed
                first_message=None,
                created_at=parsed.created_at,
                updated_at=parsed.updated_at,
            )
            self._stats["traces_created"] += 1

        return parsed.id

    def _process_message(self, data: dict) -> Optional[str]:
        """Process a message file.

        Args:
            data: Parsed JSON data

        Returns:
            Message ID if successful, None otherwise
        """
        parsed = self._parser.parse_message(data)
        if not parsed:
            return None

        conn = self._db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO messages
            (id, session_id, parent_id, role, agent, model_id, provider_id,
             mode, cost, finish_reason, working_dir,
             tokens_input, tokens_output, tokens_reasoning,
             tokens_cache_read, tokens_cache_write, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
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
            ],
        )

        self._stats["messages_indexed"] += 1

        # Update trace tokens if this is part of a child session
        if parsed.session_id:
            self._trace_builder.update_trace_tokens(parsed.session_id)

        return parsed.id

    def _process_part(self, data: dict) -> Optional[str]:
        """Process a part file.

        Args:
            data: Parsed JSON data

        Returns:
            Part ID if successful, None otherwise
        """
        parsed = self._parser.parse_part(data)
        if not parsed:
            return None

        conn = self._db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO parts
            (id, session_id, message_id, part_type, content, tool_name, tool_status,
             call_id, created_at, ended_at, duration_ms, arguments, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
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
            ],
        )

        self._stats["parts_indexed"] += 1

        # Handle special tools
        if parsed.tool_name == "skill":
            self._process_skill(data)
        elif parsed.tool_name == "task":
            self._process_delegation(data, parsed)
        elif parsed.tool_name in ("read", "write", "edit"):
            self._process_file_operation(data)

        return parsed.id

    def _process_skill(self, data: dict) -> None:
        """Process a skill tool invocation.

        Args:
            data: Raw JSON data
        """
        parsed = self._parser.parse_skill(data)
        if not parsed:
            return

        conn = self._db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO skills
            (id, message_id, session_id, skill_name, loaded_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                parsed.id,
                parsed.message_id,
                parsed.session_id,
                parsed.skill_name,
                parsed.loaded_at,
            ],
        )

    def _process_delegation(self, data: dict, part: Any) -> None:
        """Process a delegation (task tool) invocation.

        Creates both delegation record and agent_trace.

        Args:
            data: Raw JSON data
            part: Parsed part data
        """
        delegation = self._parser.parse_delegation(data)
        if not delegation:
            return

        # Insert delegation record
        conn = self._db.connect()

        # Resolve parent agent
        parent_agent = None
        if delegation.message_id:
            result = conn.execute(
                "SELECT agent FROM messages WHERE id = ?",
                [delegation.message_id],
            ).fetchone()
            if result:
                parent_agent = result[0]
                delegation.parent_agent = parent_agent

        conn.execute(
            """
            INSERT OR REPLACE INTO delegations
            (id, message_id, session_id, parent_agent, child_agent, child_session_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                delegation.id,
                delegation.message_id,
                delegation.session_id,
                delegation.parent_agent,
                delegation.child_agent,
                delegation.child_session_id,
                delegation.created_at,
            ],
        )

        # Create agent trace in real-time
        trace_id = self._trace_builder.create_trace_from_delegation(delegation, part)
        if trace_id:
            self._stats["traces_created"] += 1

    def _process_file_operation(self, data: dict) -> None:
        """Process a file operation (read/write/edit).

        Args:
            data: Raw JSON data
        """
        parsed = self._parser.parse_file_operation(data)
        if not parsed:
            return

        conn = self._db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO file_operations
            (id, session_id, trace_id, operation, file_path, timestamp, risk_level, risk_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                parsed.id,
                parsed.session_id,
                parsed.trace_id,
                parsed.operation,
                parsed.file_path,
                parsed.timestamp,
                parsed.risk_level,
                parsed.risk_reason,
            ],
        )

    def _process_todos(self, session_id: str, data: Any, path: Path) -> Optional[str]:
        """Process a todos file.

        Args:
            session_id: Session ID (from filename)
            data: Parsed JSON data (list of todos)
            path: Path to file for mtime

        Returns:
            Session ID if successful, None otherwise
        """
        if not isinstance(data, list):
            return None

        try:
            file_mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            file_mtime = datetime.now()

        todos = self._parser.parse_todos(session_id, data, file_mtime)
        if not todos:
            return None

        conn = self._db.connect()
        for todo in todos:
            conn.execute(
                """
                INSERT OR REPLACE INTO todos
                (id, session_id, content, status, priority, position, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    todo.id,
                    todo.session_id,
                    todo.content,
                    todo.status,
                    todo.priority,
                    todo.position,
                    todo.created_at,
                    todo.updated_at,
                ],
            )

        return session_id

    def _process_project(self, data: dict) -> Optional[str]:
        """Process a project file.

        Args:
            data: Parsed JSON data

        Returns:
            Project ID if successful, None otherwise
        """
        parsed = self._parser.parse_project(data)
        if not parsed:
            return None

        conn = self._db.connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO projects
            (id, worktree, vcs, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                parsed.id,
                parsed.worktree,
                parsed.vcs,
                parsed.created_at,
                parsed.updated_at,
            ],
        )

        return parsed.id
