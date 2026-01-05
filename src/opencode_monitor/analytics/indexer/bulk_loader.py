"""
Bulk loader using DuckDB native JSON reading.

Uses read_json_auto() to load JSON files directly into DuckDB,
achieving 20,000+ files/second vs ~250 files/second with Python loops.

Schema mapping from OpenCode JSON format to our analytics tables.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

from ..db import AnalyticsDB
from .sync_state import SyncState, SyncPhase
from ...utils.logger import info, debug


@dataclass
class BulkLoadResult:
    """Result of a bulk load operation."""

    file_type: str
    files_loaded: int
    duration_seconds: float
    files_per_second: float
    errors: int


class BulkLoader:
    """
    High-performance bulk loader using DuckDB native JSON reading.

    Loads historical files (mtime < T0) directly via SQL, bypassing
    Python loops for massive performance gains.

    Usage:
        loader = BulkLoader(db, storage_path, sync_state)
        loader.load_all(cutoff_timestamp)
    """

    def __init__(
        self,
        db: AnalyticsDB,
        storage_path: Path,
        sync_state: SyncState,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ):
        """
        Initialize bulk loader.

        Args:
            db: Analytics database instance
            storage_path: Path to OpenCode storage
            sync_state: Sync state manager
            on_progress: Optional callback(files_done, files_total)
        """
        self._db = db
        self._storage_path = storage_path
        self._sync_state = sync_state
        self._on_progress = on_progress

        # Track what's loaded
        self._sessions_loaded = 0
        self._messages_loaded = 0
        self._parts_loaded = 0

    def count_files(self) -> dict[str, int]:
        """Count files to be loaded by type."""
        conn = self._db.connect()
        counts = {}

        for file_type in ["session", "message", "part"]:
            path = self._storage_path / file_type
            if path.exists():
                try:
                    result = conn.execute(f"""
                        SELECT COUNT(*) FROM glob('{path}/**/*.json')
                    """).fetchone()
                    counts[file_type] = result[0] if result else 0
                except Exception:
                    counts[file_type] = 0
            else:
                counts[file_type] = 0

        return counts

    def load_all(
        self, cutoff_time: Optional[float] = None
    ) -> dict[str, BulkLoadResult]:
        """
        Load all historical files.

        Args:
            cutoff_time: Only load files with mtime < this timestamp.
                        If None, loads all files.

        Returns:
            Dict of results by file type
        """
        results = {}

        # Count total files first
        counts = self.count_files()
        total = sum(counts.values())

        self._sync_state.start_bulk(cutoff_time or time.time(), total)

        # Load in order: sessions, messages, parts
        done = 0

        # Sessions
        self._sync_state.set_phase(SyncPhase.BULK_SESSIONS)
        results["session"] = self.load_sessions(cutoff_time)
        done += results["session"].files_loaded
        self._sync_state.update_progress(done)
        self._sync_state.checkpoint()

        # Messages
        self._sync_state.set_phase(SyncPhase.BULK_MESSAGES)
        results["message"] = self.load_messages(cutoff_time)
        done += results["message"].files_loaded
        self._sync_state.update_progress(done)
        self._sync_state.checkpoint()

        # Parts
        self._sync_state.set_phase(SyncPhase.BULK_PARTS)
        results["part"] = self.load_parts(cutoff_time)
        done += results["part"].files_loaded
        self._sync_state.update_progress(done)
        self._sync_state.checkpoint()

        return results

    def load_sessions(self, cutoff_time: Optional[float] = None) -> BulkLoadResult:
        """Load session files via DuckDB native JSON reading."""
        start = time.time()
        path = self._storage_path / "session"

        if not path.exists():
            return BulkLoadResult("session", 0, 0, 0, 0)

        conn = self._db.connect()

        try:
            # Build query with optional time filter
            time_filter = ""
            if cutoff_time:
                # DuckDB doesn't directly support file mtime in read_json_auto
                # We'll filter by the file's created timestamp from the JSON
                time_filter = f"WHERE (time.created / 1000.0) < {cutoff_time}"

            # Load and transform in one query
            conn.execute(f"""
                INSERT OR REPLACE INTO sessions (
                    id, project_id, directory, title, parent_id, version,
                    additions, deletions, files_changed, created_at, updated_at
                )
                SELECT 
                    id,
                    projectID as project_id,
                    directory,
                    title,
                    parentID as parent_id,
                    version,
                    COALESCE(summary.additions, 0) as additions,
                    COALESCE(summary.deletions, 0) as deletions,
                    COALESCE(summary.files, 0) as files_changed,
                    to_timestamp(time.created / 1000.0) as created_at,
                    to_timestamp(time.updated / 1000.0) as updated_at
                FROM read_json_auto('{path}/**/*.json',
                    maximum_object_size=10485760,
                    ignore_errors=true
                )
                {time_filter}
            """)

            # Count loaded (DuckDB doesn't have changes(), count directly)
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            self._sessions_loaded = count

            elapsed = time.time() - start
            speed = count / elapsed if elapsed > 0 else 0

            info(f"[BulkLoader] Sessions: {count:,} in {elapsed:.1f}s ({speed:.0f}/s)")

            # Create root traces for sessions without parent
            self._create_root_traces(conn)

            return BulkLoadResult("session", count, elapsed, speed, 0)

        except Exception as e:
            debug(f"[BulkLoader] Session load error: {e}")
            return BulkLoadResult("session", 0, time.time() - start, 0, 1)

    def load_messages(self, cutoff_time: Optional[float] = None) -> BulkLoadResult:
        """Load message files via DuckDB native JSON reading."""
        start = time.time()
        path = self._storage_path / "message"

        if not path.exists():
            return BulkLoadResult("message", 0, 0, 0, 0)

        conn = self._db.connect()

        try:
            time_filter = ""
            if cutoff_time:
                time_filter = f"WHERE (time.created / 1000.0) < {cutoff_time}"

            conn.execute(f"""
                INSERT OR REPLACE INTO messages (
                    id, session_id, parent_id, role, agent, model_id, provider_id,
                    mode, cost, finish_reason, working_dir,
                    tokens_input, tokens_output, tokens_reasoning,
                    tokens_cache_read, tokens_cache_write, created_at, completed_at
                )
                SELECT 
                    id,
                    sessionID as session_id,
                    parentID as parent_id,
                    role,
                    agent,
                    COALESCE(modelID, model.modelID) as model_id,
                    COALESCE(providerID, model.providerID) as provider_id,
                    mode,
                    cost,
                    finish as finish_reason,
                    path.cwd as working_dir,
                    COALESCE(tokens."input", 0) as tokens_input,
                    COALESCE(tokens.output, 0) as tokens_output,
                    COALESCE(tokens.reasoning, 0) as tokens_reasoning,
                    COALESCE(tokens."cache".read, 0) as tokens_cache_read,
                    COALESCE(tokens."cache".write, 0) as tokens_cache_write,
                    to_timestamp(time.created / 1000.0) as created_at,
                    to_timestamp(time.completed / 1000.0) as completed_at
                FROM read_json_auto('{path}/**/*.json',
                    maximum_object_size=10485760,
                    ignore_errors=true
                )
                {time_filter}
            """)

            # Count loaded
            count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            self._messages_loaded = count

            elapsed = time.time() - start
            speed = count / elapsed if elapsed > 0 else 0

            info(f"[BulkLoader] Messages: {count:,} in {elapsed:.1f}s ({speed:.0f}/s)")

            return BulkLoadResult("message", count, elapsed, speed, 0)

        except Exception as e:
            debug(f"[BulkLoader] Message load error: {e}")
            return BulkLoadResult("message", 0, time.time() - start, 0, 1)

    def load_parts(self, cutoff_time: Optional[float] = None) -> BulkLoadResult:
        """Load part files via DuckDB native JSON reading."""
        start = time.time()
        path = self._storage_path / "part"

        if not path.exists():
            return BulkLoadResult("part", 0, 0, 0, 0)

        conn = self._db.connect()

        try:
            # Note: For bulk loading, we don't filter by time since we want ALL historical files.
            # The cutoff_time is handled by the HybridIndexer via file mtime, not JSON content.
            # Parts have inconsistent timestamp locations (time.start vs state.time.start),
            # so filtering here would miss many files.
            #
            # IMPORTANT: We use explicit columns schema to ensure both 'time' and 'state.time'
            # columns exist even if some JSON files don't have them. Without this, DuckDB fails
            # with "column not found" error when referencing missing struct keys.

            conn.execute(f"""
                INSERT OR REPLACE INTO parts (
                    id, session_id, message_id, part_type, content, tool_name, tool_status,
                    call_id, created_at, ended_at, duration_ms, arguments, error_message
                )
                SELECT 
                    id,
                    sessionID as session_id,
                    messageID as message_id,
                    type as part_type,
                    text as content,
                    tool as tool_name,
                    TRY(state.status) as tool_status,
                    callID as call_id,
                    -- Use state.time for tool parts, time for others
                    -- TRY() handles NULL values, explicit schema handles missing columns
                    COALESCE(
                        to_timestamp(TRY(state."time"."start") / 1000.0),
                        to_timestamp(TRY("time"."start") / 1000.0)
                    ) as created_at,
                    COALESCE(
                        to_timestamp(TRY(state."time"."end") / 1000.0),
                        to_timestamp(TRY("time"."end") / 1000.0)
                    ) as ended_at,
                    CASE 
                        WHEN TRY(state."time"."end") IS NOT NULL AND TRY(state."time"."start") IS NOT NULL 
                        THEN (TRY(state."time"."end") - TRY(state."time"."start")) 
                        WHEN TRY("time"."end") IS NOT NULL AND TRY("time"."start") IS NOT NULL 
                        THEN (TRY("time"."end") - TRY("time"."start")) 
                        ELSE NULL 
                    END as duration_ms,
                    to_json(TRY(state."input")) as arguments,
                    NULL as error_message
                FROM read_json_auto('{path}/**/*.json',
                    maximum_object_size=10485760,
                    ignore_errors=true,
                    union_by_name=true,
                    columns={{
                        'id': 'VARCHAR',
                        'sessionID': 'VARCHAR',
                        'messageID': 'VARCHAR',
                        'type': 'VARCHAR',
                        'text': 'VARCHAR',
                        'tool': 'VARCHAR',
                        'callID': 'VARCHAR',
                        'state': 'STRUCT(status VARCHAR, "input" JSON, "time" STRUCT("start" BIGINT, "end" BIGINT))',
                        'time': 'STRUCT("start" BIGINT, "end" BIGINT)'
                    }}
                )
            """)

            # Count loaded
            count = conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
            self._parts_loaded = count

            elapsed = time.time() - start
            speed = count / elapsed if elapsed > 0 else 0

            info(f"[BulkLoader] Parts: {count:,} in {elapsed:.1f}s ({speed:.0f}/s)")

            # Create delegation traces from task parts
            self._create_delegation_traces(conn)

            return BulkLoadResult("part", count, elapsed, speed, 0)

        except Exception as e:
            debug(f"[BulkLoader] Part load error: {e}")
            return BulkLoadResult("part", 0, time.time() - start, 0, 1)

    def _create_root_traces(self, conn) -> int:
        """Create root traces for sessions without parent."""
        try:
            conn.execute("""
                INSERT OR IGNORE INTO agent_traces (
                    trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
                    prompt_input, prompt_output, started_at, ended_at, duration_ms,
                    tokens_in, tokens_out, status, child_session_id
                )
                SELECT 
                    'root_' || id as trace_id,
                    id as session_id,
                    NULL as parent_trace_id,
                    NULL as parent_agent,
                    'user' as subagent_type,
                    title as prompt_input,
                    NULL as prompt_output,
                    created_at as started_at,
                    updated_at as ended_at,
                    NULL as duration_ms,
                    0 as tokens_in,
                    0 as tokens_out,
                    'completed' as status,
                    id as child_session_id
                FROM sessions
                WHERE parent_id IS NULL
            """)

            # Count traces created for root sessions
            count = conn.execute("""
                SELECT COUNT(*) FROM agent_traces WHERE trace_id LIKE 'root_%'
            """).fetchone()[0]
            if count > 0:
                debug(f"[BulkLoader] Created {count} root traces")
            return count

        except Exception as e:
            debug(f"[BulkLoader] Root trace creation error: {e}")
            return 0

    def _create_delegation_traces(self, conn) -> int:
        """Create traces for task delegations."""
        try:
            # Find task parts with completed status and extract delegation info
            conn.execute("""
                INSERT OR IGNORE INTO agent_traces (
                    trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
                    prompt_input, prompt_output, started_at, ended_at, duration_ms,
                    tokens_in, tokens_out, status, child_session_id
                )
                SELECT 
                    'del_' || p.id as trace_id,
                    p.session_id,
                    'root_' || p.session_id as parent_trace_id,
                    m.agent as parent_agent,
                    COALESCE(
                        json_extract_string(p.arguments, '$.subagent_type'),
                        'task'
                    ) as subagent_type,
                    COALESCE(
                        json_extract_string(p.arguments, '$.prompt'),
                        json_extract_string(p.arguments, '$.description'),
                        ''
                    ) as prompt_input,
                    NULL as prompt_output,
                    p.created_at as started_at,
                    p.ended_at as ended_at,
                    p.duration_ms,
                    0 as tokens_in,
                    0 as tokens_out,
                    CASE p.tool_status
                        WHEN 'completed' THEN 'completed'
                        WHEN 'error' THEN 'error'
                        ELSE 'running'
                    END as status,
                    json_extract_string(p.arguments, '$.session_id') as child_session_id
                FROM parts p
                LEFT JOIN messages m ON p.message_id = m.id
                WHERE p.tool_name = 'task'
                  AND p.tool_status IS NOT NULL
                  AND p.created_at IS NOT NULL
            """)

            # Count delegation traces
            count = conn.execute("""
                SELECT COUNT(*) FROM agent_traces WHERE trace_id LIKE 'del_%'
            """).fetchone()[0]
            if count > 0:
                debug(f"[BulkLoader] Created {count} delegation traces")
            return count

        except Exception as e:
            debug(f"[BulkLoader] Delegation trace creation error: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get loading statistics."""
        return {
            "sessions_loaded": self._sessions_loaded,
            "messages_loaded": self._messages_loaded,
            "parts_loaded": self._parts_loaded,
            "total_loaded": self._sessions_loaded
            + self._messages_loaded
            + self._parts_loaded,
        }
