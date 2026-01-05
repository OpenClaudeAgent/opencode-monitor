"""
Tests for HybridIndexer module.

Tests cover:
- Full workflow: bulk loading -> queue processing -> realtime mode
- File queueing during bulk phase
- Queue draining after bulk completes
- Status reporting for dashboard
- Thread lifecycle (start/stop)
- Error handling and edge cases
"""

import json
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from typing import List, Tuple
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.sync_state import (
    SyncPhase,
    SyncState,
    SyncStatus,
)
from opencode_monitor.analytics.indexer.bulk_loader import BulkLoader
from opencode_monitor.analytics.indexer.hybrid import HybridIndexer, get_sync_status


# === Fixtures ===


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_analytics.duckdb"


@pytest.fixture
def temp_storage(tmp_path):
    """Create a temporary storage directory structure."""
    storage_path = tmp_path / "opencode_storage"
    for subdir in ["session", "message", "part", "todo", "project"]:
        (storage_path / subdir).mkdir(parents=True, exist_ok=True)
    return storage_path


@pytest.fixture
def hybrid_indexer(temp_storage, temp_db_path):
    """Create a HybridIndexer instance (not started)."""
    indexer = HybridIndexer(
        storage_path=temp_storage,
        db_path=temp_db_path,
    )
    yield indexer
    # Cleanup
    if indexer._running:
        indexer.stop()


# === Sample Data Factories ===


def create_session_json(session_id: str, title: str = "Test Session") -> dict:
    """Factory to create session JSON data."""
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": session_id,
        "projectID": "proj_001",
        "directory": "/path/to/project",
        "title": title,
        "parentID": None,
        "version": "1.0.0",
        "summary": {"additions": 10, "deletions": 5, "files": 3},
        "time": {"created": now_ms, "updated": now_ms},
    }


def create_message_json(message_id: str, session_id: str) -> dict:
    """Factory to create message JSON data."""
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": message_id,
        "sessionID": session_id,
        "parentID": None,
        "role": "assistant",
        "agent": "executor",
        "modelID": "claude-3-5-sonnet",
        "providerID": "anthropic",
        "mode": "agent",
        "cost": 0.001,
        "finish": "completed",
        "path": {"cwd": "/path/to/project"},
        "tokens": {
            "input": 1000,
            "output": 500,
            "reasoning": 0,
            "cache": {"read": 0, "write": 0},
        },
        "time": {"created": now_ms, "completed": now_ms + 5000},
    }


def create_part_json(part_id: str, session_id: str, message_id: str) -> dict:
    """Factory to create part JSON data."""
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": part_id,
        "sessionID": session_id,
        "messageID": message_id,
        "type": "tool",
        "tool": "read",
        "callID": f"call_{part_id}",
        "state": {
            "status": "completed",
            "input": {"filePath": "/path/to/file.py"},
        },
        "time": {"start": now_ms, "end": now_ms + 100},
    }


def write_json_file(
    storage_path: Path, file_type: str, project_id: str, file_id: str, data: dict
) -> Path:
    """Write JSON data to storage."""
    dir_path = storage_path / file_type / project_id
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{file_id}.json"
    file_path.write_text(json.dumps(data))
    return file_path


# === HybridIndexer Initialization Tests ===


class TestHybridIndexerInit:
    """Tests for HybridIndexer initialization."""

    def test_init_sets_paths(self, temp_storage, temp_db_path):
        """Test initialization sets storage and db paths."""
        indexer = HybridIndexer(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )

        assert indexer._storage_path == temp_storage
        assert indexer._running is False
        assert indexer._t0 is None

    def test_init_with_default_paths(self, tmp_path):
        """Test initialization uses defaults when paths not provided."""
        # Can't test actual defaults (they use home directory)
        # Just verify indexer can be created
        indexer = HybridIndexer(
            storage_path=tmp_path / "storage",
            db_path=tmp_path / "db.duckdb",
        )
        assert indexer is not None


# === HybridIndexer Start/Stop Tests ===


class TestHybridIndexerLifecycle:
    """Tests for start/stop lifecycle."""

    def test_start_sets_running_flag(self, hybrid_indexer, temp_storage):
        """Test start sets _running to True."""
        # Need storage to exist for watcher
        hybrid_indexer.start()

        try:
            assert hybrid_indexer._running is True
            assert hybrid_indexer._t0 is not None
        finally:
            hybrid_indexer.stop()

    def test_start_initializes_components(self, hybrid_indexer, temp_storage):
        """Test start initializes all components."""
        hybrid_indexer.start()

        try:
            assert hybrid_indexer._sync_state is not None
            assert hybrid_indexer._bulk_loader is not None
            assert hybrid_indexer._watcher is not None
            assert hybrid_indexer._tracker is not None
            assert hybrid_indexer._parser is not None
            assert hybrid_indexer._trace_builder is not None
        finally:
            hybrid_indexer.stop()

    def test_start_is_idempotent(self, hybrid_indexer, temp_storage):
        """Test calling start multiple times is safe."""
        hybrid_indexer.start()
        t0_first = hybrid_indexer._t0

        # Second call should be ignored
        hybrid_indexer.start()
        t0_second = hybrid_indexer._t0

        try:
            assert t0_first == t0_second
        finally:
            hybrid_indexer.stop()

    def test_stop_sets_running_false(self, hybrid_indexer, temp_storage):
        """Test stop sets _running to False."""
        hybrid_indexer.start()
        hybrid_indexer.stop()

        assert hybrid_indexer._running is False

    def test_stop_stops_watcher(self, hybrid_indexer, temp_storage):
        """Test stop stops the watcher."""
        hybrid_indexer.start()
        watcher = hybrid_indexer._watcher

        hybrid_indexer.stop()

        # Watcher should not be running
        assert not watcher.is_running


# === HybridIndexer Queue Behavior Tests ===


class TestHybridIndexerQueue:
    """Tests for file queueing during bulk phase."""

    def test_files_queued_during_bulk_phase(self, hybrid_indexer, temp_storage):
        """Test that files are queued (not processed) during bulk phase."""
        # Don't start (which triggers bulk loading)
        # Instead, manually set up minimal state
        from opencode_monitor.analytics.indexer.sync_state import SyncState

        hybrid_indexer._db = AnalyticsDB(hybrid_indexer._db._db_path)
        hybrid_indexer._db.connect()
        hybrid_indexer._sync_state = SyncState(hybrid_indexer._db)
        hybrid_indexer._sync_state.set_phase(SyncPhase.BULK_SESSIONS)  # Not realtime

        # Simulate file event during bulk
        test_path = temp_storage / "session" / "test.json"
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text("{}")

        hybrid_indexer._on_file_event("session", test_path)

        # File should be queued, not processed
        assert hybrid_indexer._event_queue.qsize() == 1

    def test_files_processed_immediately_in_realtime(self, temp_storage, temp_db_path):
        """Test that files are processed immediately in realtime mode."""
        indexer = HybridIndexer(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )

        # Set up realtime mode manually
        from opencode_monitor.analytics.indexer.sync_state import SyncState
        from opencode_monitor.analytics.indexer.tracker import FileTracker
        from opencode_monitor.analytics.indexer.parsers import FileParser
        from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder

        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._sync_state = SyncState(indexer._db)
        indexer._tracker = FileTracker(indexer._db)
        indexer._parser = FileParser()
        indexer._trace_builder = TraceBuilder(indexer._db)
        indexer._sync_state.set_phase(SyncPhase.REALTIME)

        # Create valid session file
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_001",
            create_session_json("ses_001"),
        )

        file_path = temp_storage / "session" / "proj_001" / "ses_001.json"

        # In realtime mode, file should be processed (not queued)
        indexer._on_file_event("session", file_path)

        # Queue should still be empty (processed directly)
        assert indexer._event_queue.qsize() == 0

        # Verify file was processed
        conn = indexer._db.connect()
        result = conn.execute("SELECT id FROM sessions WHERE id = 'ses_001'").fetchone()
        assert result is not None

    def test_queue_size_tracked_in_sync_state(self, hybrid_indexer, temp_storage):
        """Test queue size is reflected in sync state."""
        hybrid_indexer._db = AnalyticsDB(hybrid_indexer._db._db_path)
        hybrid_indexer._db.connect()
        hybrid_indexer._sync_state = SyncState(hybrid_indexer._db)
        hybrid_indexer._sync_state.set_phase(SyncPhase.BULK_SESSIONS)

        # Queue multiple files
        for i in range(5):
            test_path = temp_storage / "session" / f"test_{i}.json"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_text("{}")
            hybrid_indexer._on_file_event("session", test_path)

        status = hybrid_indexer.get_status()
        assert status.queue_size == 5


# === HybridIndexer Status Tests ===


class TestHybridIndexerStatus:
    """Tests for status reporting."""

    def test_get_status_before_start(self, hybrid_indexer):
        """Test get_status returns default status before start."""
        status = hybrid_indexer.get_status()

        assert status.phase == SyncPhase.INIT
        assert status.t0 is None
        assert status.progress == 0
        assert status.is_ready is False

    def test_get_status_during_bulk(self, temp_storage, temp_db_path):
        """Test get_status returns correct status during bulk."""
        indexer = HybridIndexer(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )

        # Manually set up bulk state
        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._sync_state = SyncState(indexer._db)
        indexer._sync_state.start_bulk(time.time(), total_files=100)
        indexer._sync_state.update_progress(50)

        status = indexer.get_status()

        assert status.phase == SyncPhase.BULK_SESSIONS
        assert status.files_total == 100
        assert status.files_done == 50
        assert status.progress == 50.0

    def test_get_status_after_bulk_is_ready(self, temp_storage, temp_db_path):
        """Test is_ready becomes True after bulk sessions complete."""
        indexer = HybridIndexer(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )

        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._sync_state = SyncState(indexer._db)

        # During bulk sessions - not ready
        indexer._sync_state.set_phase(SyncPhase.BULK_SESSIONS)
        assert indexer.get_status().is_ready is False

        # After sessions loaded - ready
        indexer._sync_state.set_phase(SyncPhase.BULK_MESSAGES)
        assert indexer.get_status().is_ready is True


# === HybridIndexer Stats Tests ===


class TestHybridIndexerStats:
    """Tests for get_stats functionality."""

    def test_get_stats_includes_phase(self, temp_storage, temp_db_path):
        """Test get_stats includes current phase."""
        indexer = HybridIndexer(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )

        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._sync_state = SyncState(indexer._db)
        indexer._sync_state.set_phase(SyncPhase.REALTIME)

        stats = indexer.get_stats()

        assert stats["phase"] == "realtime"

    def test_get_stats_includes_queue_size(self, hybrid_indexer, temp_storage):
        """Test get_stats includes queue size."""
        hybrid_indexer._db = AnalyticsDB(hybrid_indexer._db._db_path)
        hybrid_indexer._db.connect()
        hybrid_indexer._sync_state = SyncState(hybrid_indexer._db)

        # Add items to queue
        hybrid_indexer._event_queue.put(("session", Path("/test.json")))
        hybrid_indexer._event_queue.put(("message", Path("/test2.json")))

        stats = hybrid_indexer.get_stats()

        assert stats["queue_size"] == 2


# === HybridIndexer Process File Tests ===


class TestHybridIndexerProcessFile:
    """Tests for individual file processing."""

    def test_process_session_file(self, temp_storage, temp_db_path):
        """Test processing a single session file."""
        indexer = HybridIndexer(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )

        from opencode_monitor.analytics.indexer.tracker import FileTracker
        from opencode_monitor.analytics.indexer.parsers import FileParser
        from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder

        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._tracker = FileTracker(indexer._db)
        indexer._parser = FileParser()
        indexer._trace_builder = TraceBuilder(indexer._db)

        # Create session file
        file_path = write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_test",
            create_session_json("ses_test", title="Test Session"),
        )

        result = indexer._process_file("session", file_path)

        assert result is True

        # Verify in database
        conn = indexer._db.connect()
        session = conn.execute(
            "SELECT title FROM sessions WHERE id = 'ses_test'"
        ).fetchone()
        assert session[0] == "Test Session"

    def test_process_message_file(self, temp_storage, temp_db_path):
        """Test processing a single message file."""
        indexer = HybridIndexer(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )

        from opencode_monitor.analytics.indexer.tracker import FileTracker
        from opencode_monitor.analytics.indexer.parsers import FileParser
        from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder

        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._tracker = FileTracker(indexer._db)
        indexer._parser = FileParser()
        indexer._trace_builder = TraceBuilder(indexer._db)

        # Create message file
        file_path = write_json_file(
            temp_storage,
            "message",
            "proj_001",
            "msg_test",
            create_message_json("msg_test", "ses_001"),
        )

        result = indexer._process_file("message", file_path)

        assert result is True

        conn = indexer._db.connect()
        msg = conn.execute(
            "SELECT agent FROM messages WHERE id = 'msg_test'"
        ).fetchone()
        assert msg[0] == "executor"

    def test_process_file_returns_false_on_error(self, temp_storage, temp_db_path):
        """Test _process_file returns False on parse errors."""
        indexer = HybridIndexer(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )

        from opencode_monitor.analytics.indexer.tracker import FileTracker
        from opencode_monitor.analytics.indexer.parsers import FileParser
        from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder

        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._tracker = FileTracker(indexer._db)
        indexer._parser = FileParser()
        indexer._trace_builder = TraceBuilder(indexer._db)

        # Create file with invalid JSON
        invalid_path = temp_storage / "session" / "proj_001" / "bad.json"
        invalid_path.parent.mkdir(parents=True, exist_ok=True)
        invalid_path.write_text("not valid json {{{")

        result = indexer._process_file("session", invalid_path)

        assert result is False


# === Integration Tests ===


class TestHybridIndexerIntegration:
    """Integration tests for full workflow."""

    def test_bulk_then_realtime_workflow(self, temp_storage, temp_db_path):
        """Test complete workflow: bulk -> queue -> realtime."""
        # Create initial data for bulk load
        for i in range(3):
            write_json_file(
                temp_storage,
                "session",
                "proj_001",
                f"ses_{i:03d}",
                create_session_json(f"ses_{i:03d}"),
            )

        indexer = HybridIndexer(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )

        indexer.start()

        # Wait for bulk to complete (with timeout)
        timeout = 10
        start = time.time()
        while time.time() - start < timeout:
            status = indexer.get_status()
            if status.phase == SyncPhase.REALTIME:
                break
            time.sleep(0.1)

        try:
            # Should be in realtime mode
            assert indexer.get_status().phase == SyncPhase.REALTIME

            # Verify bulk data was loaded
            conn = indexer._db.connect()
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            assert count >= 3

        finally:
            indexer.stop()

    def test_queue_processed_after_bulk(self, temp_storage, temp_db_path):
        """Test that queued files are processed after bulk phase."""
        # Create initial session for bulk
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_bulk",
            create_session_json("ses_bulk", title="Bulk Session"),
        )

        indexer = HybridIndexer(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )

        indexer.start()

        # Wait a bit for bulk to start, then add new file
        time.sleep(0.5)

        # Create new file (should be queued then processed)
        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_queued",
            create_session_json("ses_queued", title="Queued Session"),
        )

        # Wait for processing to complete
        timeout = 15
        start = time.time()
        while time.time() - start < timeout:
            status = indexer.get_status()
            if status.phase == SyncPhase.REALTIME and status.queue_size == 0:
                break
            time.sleep(0.1)

        try:
            # Queue should be empty
            assert indexer.get_status().queue_size == 0

        finally:
            indexer.stop()


# === Global Function Tests ===


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_sync_status_before_any_indexer(
        self, temp_storage, temp_db_path, monkeypatch
    ):
        """Test get_sync_status works even without indexer started."""
        from opencode_monitor.analytics.indexer.hybrid import IndexerRegistry

        # Clear registry to ensure no indexer exists
        IndexerRegistry.clear()

        # get_sync_status should return default status when no indexer
        status = get_sync_status()
        assert status.phase == SyncPhase.INIT

    def test_indexer_registry_lifecycle(self, temp_storage, temp_db_path):
        """Test IndexerRegistry create/get/clear lifecycle."""
        from opencode_monitor.analytics.indexer.hybrid import IndexerRegistry

        # Clear first
        IndexerRegistry.clear()
        assert IndexerRegistry.get() is None

        # Create indexer via registry
        indexer = IndexerRegistry.create(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )
        assert IndexerRegistry.get() is indexer

        # Clear should stop and remove
        IndexerRegistry.clear()
        assert IndexerRegistry.get() is None

    def test_indexer_registry_with_mock_db(self, temp_storage, temp_db_path):
        """Test IndexerRegistry supports dependency injection."""
        from unittest.mock import Mock
        from opencode_monitor.analytics.indexer.hybrid import IndexerRegistry

        # Clear first
        IndexerRegistry.clear()

        # Create indexer with mock db
        mock_db = Mock(spec=AnalyticsDB)
        mock_db._db_path = temp_db_path

        indexer = HybridIndexer(
            storage_path=temp_storage,
            db=mock_db,
        )
        IndexerRegistry.set(indexer)

        assert IndexerRegistry.get() is indexer
        assert indexer._db is mock_db

        # Cleanup
        IndexerRegistry.clear()


# === Edge Cases ===


class TestHybridIndexerEdgeCases:
    """Edge case tests."""

    def test_stop_without_start(self, hybrid_indexer):
        """Test stop without start doesn't crash."""
        # Should not raise
        hybrid_indexer.stop()
        assert hybrid_indexer._running is False

    def test_multiple_stops(self, hybrid_indexer, temp_storage):
        """Test multiple stop calls are safe."""
        hybrid_indexer.start()
        hybrid_indexer.stop()
        hybrid_indexer.stop()
        hybrid_indexer.stop()

        assert hybrid_indexer._running is False

    def test_empty_storage_directory(self, temp_db_path, tmp_path):
        """Test handling of empty storage directory."""
        empty_storage = tmp_path / "empty_storage"
        empty_storage.mkdir()
        # Don't create subdirectories

        indexer = HybridIndexer(
            storage_path=empty_storage,
            db_path=temp_db_path,
        )

        # Should handle gracefully
        indexer.start()
        time.sleep(0.5)

        try:
            status = indexer.get_status()
            # Should still work, just with no files
            assert status is not None
        finally:
            indexer.stop()

    def test_nonexistent_storage_path(self, temp_db_path, tmp_path):
        """Test handling of non-existent storage path."""
        fake_storage = tmp_path / "does_not_exist"

        indexer = HybridIndexer(
            storage_path=fake_storage,
            db_path=temp_db_path,
        )

        # Start should handle gracefully (watcher won't start)
        indexer.start()

        try:
            # Should still be able to get status
            status = indexer.get_status()
            assert status is not None
        finally:
            indexer.stop()


# === Concurrency Tests ===


class TestHybridIndexerConcurrency:
    """Concurrency and thread-safety tests."""

    def test_concurrent_status_queries(self, temp_storage, temp_db_path):
        """Test concurrent status queries are safe."""
        indexer = HybridIndexer(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )

        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._sync_state = SyncState(indexer._db)
        indexer._sync_state.start_bulk(time.time(), 1000)

        errors = []

        def query_status():
            try:
                for _ in range(50):
                    status = indexer.get_status()
                    assert status is not None
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=query_status) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent queries: {errors}"

    def test_concurrent_queue_access(self, hybrid_indexer, temp_storage):
        """Test concurrent queue access is safe."""
        hybrid_indexer._db = AnalyticsDB(hybrid_indexer._db._db_path)
        hybrid_indexer._db.connect()
        hybrid_indexer._sync_state = SyncState(hybrid_indexer._db)
        hybrid_indexer._sync_state.set_phase(SyncPhase.BULK_SESSIONS)

        errors = []

        def add_to_queue(thread_id: int):
            try:
                for i in range(20):
                    path = temp_storage / f"session_{thread_id}_{i}.json"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("{}")
                    hybrid_indexer._on_file_event("session", path)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_to_queue, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        # Should have queued 100 items (5 threads x 20 items)
        assert hybrid_indexer._event_queue.qsize() == 100
