"""Tests for bulk_load module - fast initial loading using read_json_auto()."""

import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.unified.bulk_load import (
    is_cold_start,
    bulk_load_initial,
    COLD_START_THRESHOLD,
)


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_bulk_load.duckdb"


@pytest.fixture
def temp_storage(tmp_path):
    """Create temporary storage directory with subdirectories."""
    storage = tmp_path / "storage"
    (storage / "session" / "proj_001").mkdir(parents=True)
    (storage / "message" / "ses_001").mkdir(parents=True)
    (storage / "part" / "msg_001").mkdir(parents=True)
    return storage


@pytest.fixture
def db(temp_db_path):
    """Create a database instance."""
    db = AnalyticsDB(temp_db_path)
    db.connect()
    yield db
    db.close()


def _now_ms():
    """Get current time in milliseconds."""
    return int(datetime.now().timestamp() * 1000)


def create_session_json(
    session_id: str,
    project_id: str = "proj_001",
    title: str = "Test Session",
    parent_id: str | None = None,
) -> dict:
    """Create a session JSON structure.

    Always includes parentID field (null if not set) to ensure
    DuckDB read_json_auto can infer consistent schema.
    """
    now = _now_ms()
    return {
        "id": session_id,
        "projectID": project_id,
        "directory": "/path/to/project",
        "title": title,
        "parentID": parent_id,  # Always include, even if None
        "version": "1.0.0",
        "summary": {"additions": 10, "deletions": 5, "files": 3},
        "time": {"created": now, "updated": now + 5000},
    }


def create_message_json(
    message_id: str,
    session_id: str,
    agent: str = "executor",
    tokens_input: int = 1000,
    tokens_output: int = 500,
) -> dict:
    """Create a message JSON structure."""
    now = _now_ms()
    return {
        "id": message_id,
        "sessionID": session_id,
        "parentID": None,
        "role": "assistant",
        "agent": agent,
        "modelID": "claude-3-5-sonnet",
        "providerID": "anthropic",
        "mode": "agent",
        "cost": 0.001,
        "finish": "completed",
        "path": {"cwd": "/path/to/project"},
        "tokens": {
            "input": tokens_input,
            "output": tokens_output,
            "reasoning": 0,
            "cache": {"read": 100, "write": 50},
        },
        "time": {"created": now, "completed": now + 5000},
    }


def create_part_json(
    part_id: str,
    session_id: str,
    message_id: str,
    part_type: str = "tool",
    tool: str = "read",
) -> dict:
    """Create a part JSON structure.

    Matches the real OpenCode storage format:
    - 'text' field for text content (null for tool parts)
    - 'state' for tool execution details
    """
    now = _now_ms()
    data = {
        "id": part_id,
        "sessionID": session_id,
        "messageID": message_id,
        "type": part_type,
        "text": None,  # Text content field (null for tool parts)
        "callID": f"call_{part_id}",
        "tool": tool,
        "state": {
            "status": "completed",
            "input": {"filePath": "/path/to/file.py"},
            "output": "File content here",
            "title": "file.py",
            "time": {"start": now, "end": now + 100},
        },
    }
    if part_type == "text":
        data["text"] = "Some text content"
        data["tool"] = None
        data["state"] = None
    return data


class TestIsColdStart:
    """Tests for is_cold_start() function."""

    def test_cold_start_empty_db(self, db):
        """Empty database should be detected as cold start."""
        assert is_cold_start(db) is True

    def test_cold_start_few_sessions(self, db, temp_storage):
        """Database with few sessions should be detected as cold start."""
        conn = db.connect()
        # Insert a few sessions (below threshold)
        for i in range(10):
            conn.execute(
                "INSERT INTO sessions (id, title) VALUES (?, ?)",
                [f"ses_{i:03d}", f"Session {i}"],
            )

        assert is_cold_start(db) is True

    def test_warm_start_many_sessions(self, db):
        """Database with many sessions should NOT be cold start."""
        conn = db.connect()
        # Insert many sessions (above threshold)
        for i in range(COLD_START_THRESHOLD + 10):
            conn.execute(
                "INSERT INTO sessions (id, title) VALUES (?, ?)",
                [f"ses_{i:03d}", f"Session {i}"],
            )

        assert is_cold_start(db) is False


class TestBulkLoadInitial:
    """Tests for bulk_load_initial() function."""

    def test_bulk_load_empty_storage(self, db, temp_storage):
        """Bulk load with empty storage should return zero counts."""
        results = bulk_load_initial(db, temp_storage)

        assert results["sessions"] == 0
        assert results["messages"] == 0
        assert results["parts"] == 0
        assert results["duration_s"] >= 0

    def test_bulk_load_sessions(self, db, temp_storage):
        """Bulk load should correctly load session files."""
        # Create session files
        session_dir = temp_storage / "session" / "proj_001"

        for i in range(5):
            session_data = create_session_json(
                f"ses_{i:03d}",
                title=f"Session {i}",
                parent_id=None if i == 0 else f"ses_{i - 1:03d}",
            )
            with open(session_dir / f"ses_{i:03d}.json", "w") as f:
                json.dump(session_data, f)

        # Run bulk load
        results = bulk_load_initial(db, temp_storage)

        # Verify results
        assert results["sessions"] == 5

        # Verify data in database
        conn = db.connect()
        rows = conn.execute(
            "SELECT id, title, parent_id FROM sessions ORDER BY id"
        ).fetchall()
        assert len(rows) == 5
        assert rows[0][0] == "ses_000"
        assert rows[0][2] is None  # First session has no parent

    def test_bulk_load_messages(self, db, temp_storage):
        """Bulk load should correctly load message files."""
        # Create a session first
        session_dir = temp_storage / "session" / "proj_001"
        session_data = create_session_json("ses_001")
        with open(session_dir / "ses_001.json", "w") as f:
            json.dump(session_data, f)

        # Create message files
        message_dir = temp_storage / "message" / "ses_001"
        message_dir.mkdir(parents=True, exist_ok=True)

        for i in range(3):
            msg_data = create_message_json(
                f"msg_{i:03d}",
                "ses_001",
                tokens_input=1000 + i * 100,
                tokens_output=500 + i * 50,
            )
            with open(message_dir / f"msg_{i:03d}.json", "w") as f:
                json.dump(msg_data, f)

        # Run bulk load
        results = bulk_load_initial(db, temp_storage)

        # Verify results
        assert results["messages"] == 3

        # Verify data in database
        conn = db.connect()
        rows = conn.execute(
            "SELECT id, session_id, tokens_input FROM messages ORDER BY id"
        ).fetchall()
        assert len(rows) == 3
        assert rows[0][1] == "ses_001"
        assert rows[0][2] == 1000

    def test_bulk_load_parts(self, db, temp_storage):
        """Bulk load should correctly load part files."""
        # Create a session
        session_dir = temp_storage / "session" / "proj_001"
        session_data = create_session_json("ses_001")
        with open(session_dir / "ses_001.json", "w") as f:
            json.dump(session_data, f)

        # Create a message
        message_dir = temp_storage / "message" / "ses_001"
        message_dir.mkdir(parents=True, exist_ok=True)
        msg_data = create_message_json("msg_001", "ses_001")
        with open(message_dir / "msg_001.json", "w") as f:
            json.dump(msg_data, f)

        # Create part files
        part_dir = temp_storage / "part" / "msg_001"
        part_dir.mkdir(parents=True, exist_ok=True)

        for i in range(4):
            part_data = create_part_json(
                f"prt_{i:03d}",
                "ses_001",
                "msg_001",
                tool="read" if i % 2 == 0 else "write",
            )
            with open(part_dir / f"prt_{i:03d}.json", "w") as f:
                json.dump(part_data, f)

        # Run bulk load
        results = bulk_load_initial(db, temp_storage)

        # Verify results
        assert results["parts"] == 4

        # Verify data in database
        conn = db.connect()
        rows = conn.execute("SELECT id, tool_name FROM parts ORDER BY id").fetchall()
        assert len(rows) == 4

    def test_bulk_load_creates_root_traces(self, db, temp_storage):
        """Bulk load should create agent_traces for root sessions."""
        # Create root and child sessions
        session_dir = temp_storage / "session" / "proj_001"

        # Root session (no parent)
        root_session = create_session_json("ses_root", title="Root Session")
        with open(session_dir / "ses_root.json", "w") as f:
            json.dump(root_session, f)

        # Child session (has parent)
        child_session = create_session_json(
            "ses_child",
            title="Child Session",
            parent_id="ses_root",
        )
        with open(session_dir / "ses_child.json", "w") as f:
            json.dump(child_session, f)

        # Run bulk load
        results = bulk_load_initial(db, temp_storage)

        # Verify root trace was created
        assert results["traces_created"] >= 1

        # Verify trace in database
        conn = db.connect()
        traces = conn.execute(
            "SELECT trace_id, session_id, child_session_id FROM agent_traces WHERE trace_id LIKE 'root_%'"
        ).fetchall()

        # Should have root trace for the root session only
        root_traces = [t for t in traces if t[0] == "root_ses_root"]
        assert len(root_traces) == 1
        assert root_traces[0][2] == "ses_root"  # child_session_id = itself

    def test_bulk_load_updates_stats(self, db, temp_storage):
        """Bulk load should update provided stats dict."""
        # Create some data
        session_dir = temp_storage / "session" / "proj_001"
        for i in range(3):
            session_data = create_session_json(f"ses_{i:03d}")
            with open(session_dir / f"ses_{i:03d}.json", "w") as f:
                json.dump(session_data, f)

        # Run bulk load with stats
        stats = {
            "sessions_indexed": 0,
            "messages_indexed": 0,
            "parts_indexed": 0,
            "traces_created": 0,
            "files_processed": 0,
        }

        bulk_load_initial(db, temp_storage, stats)

        # Verify stats were updated
        assert stats["sessions_indexed"] == 3
        assert stats["traces_created"] >= 3  # Root traces

    def test_bulk_load_marks_files_indexed(self, db, temp_storage):
        """Bulk load should mark files as indexed in file_index."""
        # Create some session files
        session_dir = temp_storage / "session" / "proj_001"
        for i in range(2):
            session_data = create_session_json(f"ses_{i:03d}")
            with open(session_dir / f"ses_{i:03d}.json", "w") as f:
                json.dump(session_data, f)

        # Run bulk load
        results = bulk_load_initial(db, temp_storage)

        # Verify file_index entries
        conn = db.connect()
        indexed = conn.execute(
            "SELECT COUNT(*) FROM file_index WHERE file_type = 'session'"
        ).fetchone()

        assert indexed[0] == 2

    def test_bulk_load_performance(self, db, temp_storage):
        """Bulk load should be fast (>1000 files/sec target)."""
        # Create many session files
        session_dir = temp_storage / "session" / "proj_001"

        num_files = 100
        for i in range(num_files):
            session_data = create_session_json(f"ses_{i:04d}")
            with open(session_dir / f"ses_{i:04d}.json", "w") as f:
                json.dump(session_data, f)

        # Run bulk load and measure time
        start = time.time()
        results = bulk_load_initial(db, temp_storage)
        elapsed = time.time() - start

        # Verify performance
        assert results["sessions"] == num_files
        files_per_sec = num_files / elapsed if elapsed > 0 else num_files

        # Should be much faster than 100 files/sec
        # (Target is 20k/sec but test is too small to measure accurately)
        assert files_per_sec > 50, f"Too slow: {files_per_sec:.0f} files/sec"


class TestBulkLoadIntegration:
    """Integration tests for bulk_load with UnifiedIndexer."""

    def test_indexer_uses_bulk_load_on_cold_start(self, temp_storage, temp_db_path):
        """UnifiedIndexer should use bulk load on cold start."""
        from opencode_monitor.analytics.indexer.unified import UnifiedIndexer

        # Create some data
        session_dir = temp_storage / "session" / "proj_001"
        for i in range(5):
            session_data = create_session_json(f"ses_{i:03d}")
            with open(session_dir / f"ses_{i:03d}.json", "w") as f:
                json.dump(session_data, f)

        # Create indexer and start it
        indexer = UnifiedIndexer(storage_path=temp_storage, db_path=temp_db_path)
        indexer.start()

        # Give it a moment to process
        time.sleep(0.5)

        # Check stats - should show sessions indexed via bulk load
        stats = indexer.get_stats()

        indexer.stop()

        # Should have indexed all sessions quickly
        assert stats["sessions_indexed"] >= 5
