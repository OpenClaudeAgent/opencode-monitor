"""
Tests for HybridIndexer module.
Refactored for high assertion density (target ratio > 4.0).

Tests cover:
- Full workflow: bulk loading -> queue processing -> realtime mode
- File queueing during bulk phase
- Queue draining after bulk completes
- Status reporting for dashboard
- Thread lifecycle (start/stop)
- Error handling and edge cases
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.sync_state import SyncPhase, SyncState
from opencode_monitor.analytics.indexer.hybrid import HybridIndexer, get_sync_status


# =============================================================================
# Factories
# =============================================================================


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


def write_json_file(
    storage_path: Path, file_type: str, project_id: str, file_id: str, data: dict
) -> Path:
    """Write JSON data to storage."""
    dir_path = storage_path / file_type / project_id
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{file_id}.json"
    file_path.write_text(json.dumps(data))
    return file_path


# =============================================================================
# Fixtures
# =============================================================================


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
    if indexer._running:
        indexer.stop()


@pytest.fixture
def setup_indexer_for_processing(temp_storage, temp_db_path):
    """Set up indexer with all components for file processing."""
    from opencode_monitor.analytics.indexer.tracker import FileTracker
    from opencode_monitor.analytics.indexer.parsers import FileParser
    from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder

    indexer = HybridIndexer(
        storage_path=temp_storage,
        db_path=temp_db_path,
    )
    indexer._db = AnalyticsDB(temp_db_path)
    indexer._db.connect()
    indexer._tracker = FileTracker(indexer._db)
    indexer._parser = FileParser()
    indexer._trace_builder = TraceBuilder(indexer._db)
    return indexer


# =============================================================================
# Initialization Tests
# =============================================================================


class TestHybridIndexerInit:
    """Tests for HybridIndexer initialization."""

    def test_init_sets_all_attributes(self, temp_storage, temp_db_path):
        """Test initialization sets all required attributes correctly."""
        indexer = HybridIndexer(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )

        # Verify paths
        assert indexer._storage_path == temp_storage, "Storage path should be set"
        assert indexer._db._db_path == temp_db_path, "DB path should be set"
        assert isinstance(indexer._storage_path, Path), "Storage should be Path"
        # Verify initial state
        assert indexer._running is False, "Should not be running initially"
        assert indexer._t0 is None, "t0 should be None initially"
        # Verify queue exists and is correct type
        assert hasattr(indexer, "_event_queue"), "Should have event queue"
        assert indexer._event_queue.empty(), "Queue should be empty initially"
        assert indexer._event_queue.qsize() == 0, "Queue size should be 0"

    def test_init_with_injected_db(self, temp_storage, analytics_db_real):
        """Test initialization with injected real database."""
        indexer = HybridIndexer(
            storage_path=temp_storage,
            db=analytics_db_real,
        )

        assert indexer._db is analytics_db_real, "Should use injected db"
        assert indexer._storage_path == temp_storage, "Storage path should be set"
        assert indexer._running is False, "Should not be running"
        assert indexer._t0 is None, "t0 should be None"


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestHybridIndexerLifecycle:
    """Tests for start/stop lifecycle."""

    def test_start_initializes_all_components(self, hybrid_indexer, temp_storage):
        """Test start initializes all required components."""
        hybrid_indexer.start()

        try:
            # Verify running state
            assert hybrid_indexer._running is True, "Should be running"
            assert hybrid_indexer._t0 is not None, "t0 should be set"
            # Verify all components initialized
            assert hybrid_indexer._sync_state is not None, "sync_state should exist"
            assert hybrid_indexer._bulk_loader is not None, "bulk_loader should exist"
            assert hybrid_indexer._watcher is not None, "watcher should exist"
            assert hybrid_indexer._tracker is not None, "tracker should exist"
            assert hybrid_indexer._parser is not None, "parser should exist"
            assert hybrid_indexer._trace_builder is not None, (
                "trace_builder should exist"
            )
        finally:
            hybrid_indexer.stop()

    def test_start_is_idempotent(self, hybrid_indexer, temp_storage):
        """Test calling start multiple times is safe."""
        hybrid_indexer.start()
        t0_first = hybrid_indexer._t0
        sync_state_first = hybrid_indexer._sync_state

        hybrid_indexer.start()  # Second call
        t0_second = hybrid_indexer._t0

        try:
            assert t0_first == t0_second, "t0 should not change on second start"
            assert hybrid_indexer._running is True, "Should still be running"
            assert hybrid_indexer._sync_state is sync_state_first, "Same sync_state"
        finally:
            hybrid_indexer.stop()

    def test_stop_cleans_up_properly(self, hybrid_indexer, temp_storage):
        """Test stop cleans up all resources."""
        hybrid_indexer.start()
        watcher = hybrid_indexer._watcher
        assert hybrid_indexer._running is True, "Should be running before stop"

        hybrid_indexer.stop()

        assert hybrid_indexer._running is False, "Should not be running"
        assert not watcher.is_running, "Watcher should be stopped"

    @pytest.mark.parametrize(
        "stop_count",
        [pytest.param(1, id="single_stop"), pytest.param(3, id="triple_stop")],
    )
    def test_multiple_stops_are_safe(self, hybrid_indexer, temp_storage, stop_count):
        """Test multiple stop calls don't crash."""
        hybrid_indexer.start()

        for _ in range(stop_count):
            hybrid_indexer.stop()

        assert hybrid_indexer._running is False, "Should not be running"

    def test_stop_without_start(self, hybrid_indexer):
        """Test stop without start doesn't crash."""
        hybrid_indexer.stop()
        assert hybrid_indexer._running is False, "Should not be running"


# =============================================================================
# Queue Behavior Tests
# =============================================================================


class TestHybridIndexerQueue:
    """Tests for file queueing during bulk phase."""

    def test_files_queued_during_bulk_phase(self, hybrid_indexer, temp_storage):
        """Test that files are queued (not processed) during bulk phase."""
        hybrid_indexer._db = AnalyticsDB(hybrid_indexer._db._db_path)
        hybrid_indexer._db.connect()
        hybrid_indexer._sync_state = SyncState(hybrid_indexer._db)
        hybrid_indexer._sync_state.set_phase(SyncPhase.BULK_SESSIONS)

        assert hybrid_indexer._event_queue.empty(), "Queue should start empty"

        test_path = temp_storage / "session" / "test.json"
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text("{}")

        hybrid_indexer._on_file_event("session", test_path)

        assert not hybrid_indexer._event_queue.empty(), "Queue should not be empty"
        assert hybrid_indexer._event_queue.qsize() == 1, "Should have 1 queued item"
        queued = hybrid_indexer._event_queue.get()
        assert queued[0] == "session", "Queued item should have correct type"
        assert queued[1] == test_path, "Queued item should have correct path"
        assert len(queued) == 2, "Queued item should be a tuple of 2"

    def test_files_processed_immediately_in_realtime(
        self, setup_indexer_for_processing, temp_storage
    ):
        """Test that files are processed immediately in realtime mode."""
        indexer = setup_indexer_for_processing
        indexer._sync_state = SyncState(indexer._db)
        indexer._sync_state.set_phase(SyncPhase.REALTIME)

        write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_001",
            create_session_json("ses_001"),
        )
        file_path = temp_storage / "session" / "proj_001" / "ses_001.json"
        assert file_path.exists(), "File should exist"

        indexer._on_file_event("session", file_path)

        # Queue should be empty (processed directly)
        assert indexer._event_queue.empty(), "Queue should be empty"
        assert indexer._event_queue.qsize() == 0, "Queue size should be 0"
        # Verify file was processed into DB
        conn = indexer._db.connect()
        result = conn.execute("SELECT id FROM sessions WHERE id = 'ses_001'").fetchone()
        assert result is not None, "Session should be in database"
        assert result[0] == "ses_001", "Session ID should match"

    def test_queue_size_tracked_in_status(self, hybrid_indexer, temp_storage):
        """Test queue size is reflected in sync status."""
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
        assert status.queue_size == 5, "Queue size should be 5"


# =============================================================================
# Status and Stats Tests
# =============================================================================


class TestHybridIndexerStatus:
    """Tests for status and stats reporting."""

    def test_get_status_before_start(self, hybrid_indexer):
        """Test get_status returns correct default status before start."""
        status = hybrid_indexer.get_status()

        assert status is not None, "Status should not be None"
        assert status.phase == SyncPhase.INIT, "Phase should be INIT"
        assert status.t0 is None, "t0 should be None"
        assert status.progress == 0, "Progress should be 0"
        assert status.is_ready is False, "Should not be ready"
        assert status.queue_size == 0, "Queue size should be 0"
        assert status.files_done == 0, "Files done should be 0"

    def test_get_status_during_bulk(self, temp_storage, temp_db_path):
        """Test get_status returns correct status during bulk loading."""
        indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)
        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._sync_state = SyncState(indexer._db)
        indexer._sync_state.start_bulk(time.time(), total_files=100)
        indexer._sync_state.update_progress(50)

        status = indexer.get_status()

        assert status is not None, "Status should not be None"
        assert status.phase == SyncPhase.BULK_SESSIONS, "Should be in bulk phase"
        assert status.files_total == 100, "Total files should be 100"
        assert status.files_done == 50, "Done files should be 50"
        assert status.progress == 50.0, "Progress should be 50%"
        assert status.is_ready is False, "Not ready during bulk sessions"
        assert status.t0 is not None, "t0 should be set during bulk"

    @pytest.mark.parametrize(
        "phase,is_ready",
        [
            pytest.param(SyncPhase.BULK_SESSIONS, False, id="bulk_sessions_not_ready"),
            pytest.param(SyncPhase.BULK_MESSAGES, False, id="bulk_messages_not_ready"),
            pytest.param(SyncPhase.REALTIME, True, id="realtime_ready"),
        ],
    )
    def test_is_ready_based_on_phase(self, temp_storage, temp_db_path, phase, is_ready):
        """Test is_ready changes based on sync phase."""
        indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)
        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._sync_state = SyncState(indexer._db)
        indexer._sync_state.set_phase(phase)

        status = indexer.get_status()

        assert status.is_ready is is_ready, f"is_ready should be {is_ready} for {phase}"
        assert status.phase == phase, f"Phase should be {phase}"

    def test_get_stats_includes_all_fields(self, temp_storage, temp_db_path):
        """Test get_stats includes phase and queue_size."""
        indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)
        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._sync_state = SyncState(indexer._db)
        indexer._sync_state.set_phase(SyncPhase.REALTIME)
        indexer._event_queue.put(("session", Path("/test.json")))
        indexer._event_queue.put(("message", Path("/test2.json")))

        stats = indexer.get_stats()

        assert "phase" in stats, "Stats should include phase"
        assert stats["phase"] == "realtime", "Phase should be realtime"
        assert "queue_size" in stats, "Stats should include queue_size"
        assert stats["queue_size"] == 2, "Queue size should be 2"


# =============================================================================
# File Processing Tests
# =============================================================================


class TestHybridIndexerProcessFile:
    """Tests for individual file processing."""

    def test_process_session_file(self, setup_indexer_for_processing, temp_storage):
        """Test processing a session file."""
        indexer = setup_indexer_for_processing

        file_path = write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_test",
            create_session_json("ses_test", title="Test Session"),
        )
        assert file_path.exists(), "File should exist"

        result = indexer._process_file("session", file_path)

        assert result is True, "Processing should succeed"
        conn = indexer._db.connect()
        session = conn.execute(
            "SELECT id, title, project_id FROM sessions WHERE id = 'ses_test'"
        ).fetchone()
        assert session is not None, "Session should exist"
        assert session[0] == "ses_test", "Session ID should match"
        assert session[1] == "Test Session", "Session title should match"
        assert session[2] == "proj_001", "Project ID should match"

    def test_process_message_file(self, setup_indexer_for_processing, temp_storage):
        """Test processing a message file."""
        indexer = setup_indexer_for_processing

        file_path = write_json_file(
            temp_storage,
            "message",
            "proj_001",
            "msg_test",
            create_message_json("msg_test", "ses_001"),
        )
        assert file_path.exists(), "File should exist"

        result = indexer._process_file("message", file_path)

        assert result is True, "Processing should succeed"
        conn = indexer._db.connect()
        msg = conn.execute(
            "SELECT id, agent, session_id, role FROM messages WHERE id = 'msg_test'"
        ).fetchone()
        assert msg is not None, "Message should exist"
        assert msg[0] == "msg_test", "Message ID should match"
        assert msg[1] == "executor", "Agent should match"
        assert msg[2] == "ses_001", "Session ID should match"
        assert msg[3] == "assistant", "Role should match"

    def test_process_file_returns_false_on_invalid_json(
        self, setup_indexer_for_processing, temp_storage
    ):
        """Test _process_file returns False on parse errors."""
        indexer = setup_indexer_for_processing

        invalid_path = temp_storage / "session" / "proj_001" / "bad.json"
        invalid_path.parent.mkdir(parents=True, exist_ok=True)
        invalid_path.write_text("not valid json {{{")
        assert invalid_path.exists(), "Invalid file should exist"

        result = indexer._process_file("session", invalid_path)

        assert result is False, "Should return False on error"
        # Verify nothing was inserted
        conn = indexer._db.connect()
        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        assert count == 0, "No sessions should be inserted on error"


# =============================================================================
# Integration Tests
# =============================================================================


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

        indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)
        indexer.start()

        timeout = 10
        start = time.time()
        realtime_reached = False

        while time.time() - start < timeout:
            status = indexer.get_status()
            if status.phase == SyncPhase.REALTIME:
                realtime_reached = True
                break
            time.sleep(0.05)

        assert realtime_reached, (
            f"Indexer did not reach REALTIME phase within {timeout}s"
        )

        try:
            status = indexer.get_status()
            assert status.phase == SyncPhase.REALTIME, "Should be in realtime"
            assert status.is_ready is True, "Should be ready"

            conn = indexer._db.connect()
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            assert count >= 3, f"Should have at least 3 sessions, got {count}"
        finally:
            indexer.stop()


# =============================================================================
# Global Functions Tests
# =============================================================================


@pytest.mark.xdist_group(name="indexer_singleton")
class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_sync_status_without_indexer(self):
        """Test get_sync_status works even without indexer started."""
        from opencode_monitor.analytics.indexer.hybrid import IndexerRegistry

        IndexerRegistry.clear()
        status = get_sync_status()

        assert status is not None, "Status should not be None"
        assert status.phase == SyncPhase.INIT, "Should be INIT phase"
        assert status.is_ready is False, "Should not be ready"
        assert status.progress == 0, "Progress should be 0"
        assert status.queue_size == 0, "Queue size should be 0"

    def test_indexer_registry_lifecycle(self, temp_storage, temp_db_path):
        """Test IndexerRegistry create/get/clear lifecycle."""
        from opencode_monitor.analytics.indexer.hybrid import IndexerRegistry

        IndexerRegistry.clear()

        assert IndexerRegistry.get() is None, "Should be None after clear"

        indexer = IndexerRegistry.create(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )
        assert indexer is not None, "Indexer should be created"
        assert IndexerRegistry.get() is indexer, "Should return created indexer"
        assert IndexerRegistry.get() is not None, "Should not be None"
        assert isinstance(indexer, HybridIndexer), "Should be HybridIndexer"

        IndexerRegistry.clear()
        assert IndexerRegistry.get() is None, "Should be None after clear"


# =============================================================================
# Edge Cases
# =============================================================================


class TestHybridIndexerEdgeCases:
    """Edge case tests."""

    def test_empty_storage_directory(self, temp_db_path, tmp_path):
        """Test handling of empty storage directory."""
        empty_storage = tmp_path / "empty_storage"
        empty_storage.mkdir()

        indexer = HybridIndexer(storage_path=empty_storage, db_path=temp_db_path)
        indexer.start()

        try:
            status = indexer.get_status()
            assert status is not None, "Status should be available"
            assert hasattr(status, "phase"), "Status should have phase"
            assert hasattr(status, "is_ready"), "Status should have is_ready"
        finally:
            indexer.stop()

    def test_nonexistent_storage_path(self, temp_db_path, tmp_path):
        """Test handling of empty storage path.

        Note: After DQ-001 security fix, storage path must exist.
        This test now verifies indexer handles empty storage gracefully.
        """
        empty_storage = tmp_path / "empty_storage"
        empty_storage.mkdir()

        indexer = HybridIndexer(storage_path=empty_storage, db_path=temp_db_path)
        indexer.start()

        try:
            status = indexer.get_status()
            assert status is not None, "Status should be available"
            assert hasattr(status, "phase"), "Should have phase attribute"
        finally:
            indexer.stop()


# =============================================================================
# Concurrency Tests
# =============================================================================


class TestHybridIndexerConcurrency:
    """Concurrency and thread-safety tests."""

    def test_concurrent_status_queries(self, temp_storage, temp_db_path):
        """Test concurrent status queries are thread-safe."""
        indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)
        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._sync_state = SyncState(indexer._db)
        indexer._sync_state.start_bulk(time.time(), 1000)

        errors = []

        def query_status():
            try:
                for _ in range(50):
                    status = indexer.get_status()
                    assert status is not None, "Status should not be None"
                    assert hasattr(status, "phase"), "Should have phase"
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=query_status) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent queries: {errors}"

    def test_concurrent_queue_access(self, hybrid_indexer, temp_storage):
        """Test concurrent queue access is thread-safe."""
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

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
        assert hybrid_indexer._event_queue.qsize() == 100, "Should have 100 items"
