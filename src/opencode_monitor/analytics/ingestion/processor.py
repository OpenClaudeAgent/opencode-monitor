"""
Unified ingestion processor using DuckDB SQL templates.
Replaces legacy python-based handlers.
"""

from pathlib import Path
from typing import Optional

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.utils.logger import debug, error
from .bulk_queries import (
    LOAD_SESSIONS_SQL,
    LOAD_MESSAGES_SQL,
    LOAD_PARTS_SQL,
    LOAD_STEP_EVENTS_SQL,
    LOAD_PATCHES_SQL,
    LOAD_FILE_OPERATIONS_SQL,
    CREATE_ROOT_TRACES_SQL,
    CREATE_DELEGATION_TRACES_SQL,
)


class IngestionProcessor:
    """
    Process individual files using the same SQL logic as the BulkLoader.
    """

    def __init__(self, db: Optional[AnalyticsDB] = None):
        self.db = db

    def process_session(self, file_path: Path, conn=None) -> Optional[str]:
        """Ingest a single session file."""
        return self._run_query(LOAD_SESSIONS_SQL, file_path, "session", conn)

    def process_message(self, file_path: Path, conn=None) -> Optional[str]:
        """Ingest a single message file."""
        return self._run_query(LOAD_MESSAGES_SQL, file_path, "message", conn)

    def process_part(self, file_path: Path, conn=None) -> Optional[str]:
        res = self._run_query(LOAD_PARTS_SQL, file_path, "part", conn)

        self._run_query(LOAD_STEP_EVENTS_SQL, file_path, "step_event", conn)
        self._run_query(LOAD_PATCHES_SQL, file_path, "patch", conn)
        self._run_query(LOAD_FILE_OPERATIONS_SQL, file_path, "file_operation", conn)

        self._run_delegation_trace(conn)

        return res

    def _run_query(
        self, sql_template: str, file_path: Path, entity_name: str, conn=None
    ) -> Optional[str]:
        """Execute the SQL template for a specific file."""
        if not file_path.exists():
            error(f"File not found: {file_path}")
            return None

        if conn is None:
            if self.db is None:
                raise ValueError("Either conn or db must be provided")
            conn = self.db.connect()

        try:
            query = sql_template.format(file_pattern=str(file_path), time_filter="")

            conn.execute(query)
            return file_path.stem

        except Exception as e:
            error(f"Failed to ingest {entity_name} from {file_path}: {e}")
            return None

    def _run_delegation_trace(self, conn=None):
        """Run delegation trace creation."""
        if conn is None:
            if self.db is None:
                raise ValueError("Either conn or db must be provided")
            conn = self.db.connect()

        try:
            conn.execute(CREATE_DELEGATION_TRACES_SQL)
        except Exception as e:
            debug(f"Delegation trace creation failed: {e}")
