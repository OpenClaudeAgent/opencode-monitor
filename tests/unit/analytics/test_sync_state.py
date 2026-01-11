"""
Tests for SyncState module.

Tests cover:
- Table creation and schema
- Phase transitions (INIT -> BULK_SESSIONS -> ... -> REALTIME)
- Progress tracking and ETA calculation
- Persistence (checkpoint/restore from DB)
- Thread-safety
- Reset functionality
"""

import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.sync_state import (
    SyncPhase,
    SyncState,
    SyncStatus,
)


# === Fixtures ===


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=True) as f:
        db_path = Path(f.name)

    db = AnalyticsDB(db_path=db_path)
    db.connect()
    yield db
    db.close()

    try:
        db_path.unlink()
    except Exception:
        pass


# === SyncPhase Enum Tests ===


class TestSyncPhase:
    """Tests for SyncPhase enum."""

    def test_all_phases_defined(self):
        """Verify all expected phases exist."""
        expected_phases = [
            "init",
            "bulk_sessions",
            "bulk_messages",
            "bulk_parts",
            "processing_queue",
            "realtime",
        ]
        actual_phases = [p.value for p in SyncPhase]
        assert actual_phases == expected_phases

    def test_phase_string_values(self):
        """Test that phases have correct string values."""
        assert SyncPhase.INIT.value == "init"
        assert SyncPhase.BULK_SESSIONS.value == "bulk_sessions"
        assert SyncPhase.BULK_MESSAGES.value == "bulk_messages"
        assert SyncPhase.BULK_PARTS.value == "bulk_parts"
        assert SyncPhase.PROCESSING_QUEUE.value == "processing_queue"
        assert SyncPhase.REALTIME.value == "realtime"

    def test_phase_is_str_enum(self):
        """Test that SyncPhase is a str enum for JSON serialization."""
        # Should be usable as string directly
        assert str(SyncPhase.INIT) == "SyncPhase.INIT"
        assert SyncPhase.INIT.value == "init"
        # Can be created from string value
        assert SyncPhase("init") == SyncPhase.INIT


# === SyncStatus Dataclass Tests ===


class TestSyncStatus:
    """Tests for SyncStatus dataclass."""

    def test_to_dict_all_fields(self):
        """Test to_dict serializes all fields correctly."""
        status = SyncStatus(
            phase=SyncPhase.BULK_SESSIONS,
            t0=1704067200.0,
            progress=45.5,
            files_total=1000,
            files_done=455,
            queue_size=50,
            eta_seconds=120.5,
            last_indexed=datetime(2024, 1, 1, 12, 0, 0),
            is_ready=False,
        )

        result = status.to_dict()

        assert result["phase"] == "bulk_sessions"
        assert result["t0"] == 1704067200.0
        assert result["progress"] == 45.5
        assert result["files_total"] == 1000
        assert result["files_done"] == 455
        assert result["queue_size"] == 50
        assert result["eta_seconds"] == 120.5
        assert result["last_indexed"] == "2024-01-01T12:00:00"
        assert result["is_ready"] is False

    def test_to_dict_none_values(self):
        """Test to_dict handles None values correctly."""
        status = SyncStatus(
            phase=SyncPhase.INIT,
            t0=None,
            progress=0,
            files_total=0,
            files_done=0,
            queue_size=0,
            eta_seconds=None,
            last_indexed=None,
            is_ready=False,
        )

        result = status.to_dict()

        assert result["t0"] is None
        assert result["eta_seconds"] is None
        assert result["last_indexed"] is None

    def test_progress_rounding(self):
        """Test that progress is rounded to 1 decimal place."""
        status = SyncStatus(
            phase=SyncPhase.BULK_PARTS,
            t0=None,
            progress=33.3333333,
            files_total=100,
            files_done=33,
            queue_size=0,
            eta_seconds=100.123456,
            last_indexed=None,
            is_ready=True,
        )

        result = status.to_dict()

        assert result["progress"] == 33.3
        assert result["eta_seconds"] == 100.1


# === SyncState Table Creation Tests ===


class TestSyncStateTableCreation:
    """Tests for sync_state table creation."""

    def test_table_created_on_init(self, temp_db):
        """Test that sync_state table is created on initialization."""
        sync_state = SyncState(temp_db)

        conn = temp_db.connect()
        result = conn.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'sync_state'
        """).fetchone()

        assert result[0] == 1

    def test_initial_row_exists(self, temp_db):
        """Test that initial row with id=1 is created."""
        sync_state = SyncState(temp_db)

        conn = temp_db.connect()
        result = conn.execute("""
            SELECT id, phase FROM sync_state WHERE id = 1
        """).fetchone()

        assert result is not None
        assert result[0] == 1
        assert result[1] == "init"

    def test_table_schema_complete(self, temp_db):
        """Test that all required columns exist."""
        sync_state = SyncState(temp_db)

        conn = temp_db.connect()
        columns = conn.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'sync_state'
        """).fetchall()

        column_names = {row[0] for row in columns}
        expected_columns = {
            "id",
            "phase",
            "t0",
            "files_total",
            "files_done",
            "sessions_done",
            "messages_done",
            "parts_done",
            "queue_processed",
            "last_indexed",
            "updated_at",
        }

        assert expected_columns.issubset(column_names)


# === SyncState Phase Transition Tests ===


class TestSyncStatePhaseTransitions:
    """Tests for phase transition logic."""

    def test_initial_phase_is_init(self, temp_db):
        """Test that initial phase is INIT."""
        sync_state = SyncState(temp_db)
        assert sync_state.phase == SyncPhase.INIT

    def test_start_bulk_sets_phase_to_bulk_sessions(self, temp_db):
        """Test start_bulk transitions to BULK_SESSIONS."""
        sync_state = SyncState(temp_db)
        t0 = time.time()

        sync_state.start_bulk(t0, total_files=1000)

        assert sync_state.phase == SyncPhase.BULK_SESSIONS
        assert sync_state.t0 == t0

    def test_set_phase_transitions_correctly(self, temp_db):
        """Test explicit phase transitions via set_phase."""
        sync_state = SyncState(temp_db)

        # Simulate full transition sequence
        transitions = [
            SyncPhase.BULK_SESSIONS,
            SyncPhase.BULK_MESSAGES,
            SyncPhase.BULK_PARTS,
            SyncPhase.PROCESSING_QUEUE,
            SyncPhase.REALTIME,
        ]

        for expected_phase in transitions:
            sync_state.set_phase(expected_phase)
            assert sync_state.phase == expected_phase

    def test_is_realtime_property(self, temp_db):
        """Test is_realtime returns correct values."""
        sync_state = SyncState(temp_db)

        sync_state.set_phase(SyncPhase.BULK_SESSIONS)
        assert sync_state.is_realtime is False

        sync_state.set_phase(SyncPhase.PROCESSING_QUEUE)
        assert sync_state.is_realtime is False

        sync_state.set_phase(SyncPhase.REALTIME)
        assert sync_state.is_realtime is True


# === SyncState Progress Tracking Tests ===


class TestSyncStateProgressTracking:
    """Tests for progress and ETA tracking."""

    def test_update_progress_tracks_files(self, temp_db):
        """Test update_progress updates file counters."""
        sync_state = SyncState(temp_db)
        sync_state.start_bulk(time.time(), total_files=1000)

        sync_state.update_progress(files_done=250, queue_size=10)

        status = sync_state.get_status()
        assert status.files_done == 250
        assert status.queue_size == 10
        assert status.files_total == 1000

    def test_progress_percentage_calculated(self, temp_db):
        """Test progress percentage is calculated correctly."""
        sync_state = SyncState(temp_db)
        sync_state.start_bulk(time.time(), total_files=1000)

        sync_state.update_progress(files_done=500)

        status = sync_state.get_status()
        assert status.progress == 50.0

    def test_progress_zero_when_no_files(self, temp_db):
        """Test progress is 0 when total files is 0."""
        sync_state = SyncState(temp_db)
        sync_state.start_bulk(time.time(), total_files=0)

        status = sync_state.get_status()
        assert status.progress == 0.0

    def test_eta_calculated_after_progress(self, temp_db):
        """Test ETA is calculated based on rate."""
        sync_state = SyncState(temp_db)
        start_time = time.time() - 10  # Started 10 seconds ago

        sync_state.start_bulk(start_time, total_files=1000)
        sync_state._start_time = start_time
        sync_state._files_done = 500  # 500 files in 10 seconds = 50 files/sec

        status = sync_state.get_status()

        # ETA should be ~10 seconds (500 remaining / 50 per second)
        assert status.eta_seconds is not None
        assert 5 < status.eta_seconds < 15  # Allow some variance

    def test_eta_none_when_no_progress(self, temp_db):
        """Test ETA is None when no files processed yet."""
        sync_state = SyncState(temp_db)
        sync_state.start_bulk(time.time(), total_files=1000)

        status = sync_state.get_status()
        assert status.eta_seconds is None

    def test_set_queue_size(self, temp_db):
        """Test set_queue_size updates queue counter."""
        sync_state = SyncState(temp_db)

        sync_state.set_queue_size(100)

        status = sync_state.get_status()
        assert status.queue_size == 100

    def test_last_indexed_updated(self, temp_db):
        """Test last_indexed is updated on progress."""
        sync_state = SyncState(temp_db)
        sync_state.start_bulk(time.time(), total_files=100)

        before = sync_state.get_status().last_indexed
        sync_state.update_progress(files_done=10)
        after = sync_state.get_status().last_indexed

        assert after is not None
        if before is not None:
            assert after >= before


# === SyncState Persistence Tests ===


class TestSyncStatePersistence:
    """Tests for checkpoint/restore persistence."""

    def test_checkpoint_saves_to_db(self, temp_db):
        """Test checkpoint persists state to database."""
        sync_state = SyncState(temp_db)
        sync_state.start_bulk(1704067200.0, total_files=5000)
        sync_state.set_phase(SyncPhase.BULK_MESSAGES)
        sync_state._files_done = 2500

        sync_state.checkpoint()

        # Verify in DB
        conn = temp_db.connect()
        result = conn.execute("""
            SELECT phase, t0, files_total, files_done
            FROM sync_state WHERE id = 1
        """).fetchone()

        assert result[0] == "bulk_messages"
        assert result[1] == 1704067200.0
        assert result[2] == 5000
        assert result[3] == 2500

    def test_restore_from_db_on_init(self, temp_db):
        """Test state is restored from DB on initialization."""
        # First instance - set state
        sync_state1 = SyncState(temp_db)
        sync_state1.start_bulk(1704067200.0, total_files=1000)
        sync_state1.set_phase(SyncPhase.BULK_PARTS)
        sync_state1._files_done = 750
        sync_state1.checkpoint()

        # Second instance - should restore
        sync_state2 = SyncState(temp_db)

        assert sync_state2.phase == SyncPhase.BULK_PARTS
        assert sync_state2.t0 == 1704067200.0
        assert sync_state2._files_total == 1000
        assert sync_state2._files_done == 750

    def test_restore_handles_invalid_phase(self, temp_db):
        """Test restore handles invalid phase values gracefully."""
        sync_state = SyncState(temp_db)

        # Manually insert invalid phase
        conn = temp_db.connect()
        conn.execute("""
            UPDATE sync_state SET phase = 'invalid_phase' WHERE id = 1
        """)

        # Create new instance - should fallback to INIT
        sync_state2 = SyncState(temp_db)
        assert sync_state2.phase == SyncPhase.INIT


# === SyncState Reset Tests ===


class TestSyncStateReset:
    """Tests for reset functionality."""

    def test_reset_clears_all_state(self, temp_db):
        """Test reset clears all state to defaults."""
        sync_state = SyncState(temp_db)
        sync_state.start_bulk(1704067200.0, total_files=1000)
        sync_state.set_phase(SyncPhase.BULK_PARTS)
        sync_state.update_progress(500, queue_size=50)

        sync_state.reset()

        assert sync_state.phase == SyncPhase.INIT
        assert sync_state.t0 is None

        status = sync_state.get_status()
        assert status.files_total == 0
        assert status.files_done == 0
        assert status.queue_size == 0
        assert status.is_ready is False

    def test_reset_persists_to_db(self, temp_db):
        """Test reset persists the cleared state to DB."""
        sync_state = SyncState(temp_db)
        sync_state.start_bulk(1704067200.0, total_files=1000)
        sync_state.checkpoint()

        sync_state.reset()

        # Verify in DB
        conn = temp_db.connect()
        result = conn.execute("""
            SELECT phase, t0, files_total, files_done
            FROM sync_state WHERE id = 1
        """).fetchone()

        assert result[0] == "init"
        assert result[1] is None
        assert result[2] == 0
        assert result[3] == 0


# === SyncState Thread Safety Tests ===


class TestSyncStateThreadSafety:
    """Tests for thread-safe operations."""

    def test_concurrent_updates_dont_crash(self, temp_db):
        """Test concurrent updates from multiple threads."""
        sync_state = SyncState(temp_db)
        sync_state.start_bulk(time.time(), total_files=10000)

        errors = []

        def updater(thread_id: int):
            try:
                for i in range(100):
                    sync_state.update_progress(thread_id * 100 + i)
                    sync_state.set_queue_size(i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=updater, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_checkpoint_safe(self, temp_db):
        """Test concurrent checkpoint calls are safe."""
        sync_state = SyncState(temp_db)
        sync_state.start_bulk(time.time(), total_files=1000)

        errors = []

        def checkpointer():
            try:
                for _ in range(50):
                    sync_state.checkpoint()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=checkpointer) for _ in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# === SyncState is_ready Tests ===


class TestSyncStateIsReady:
    """Tests for is_ready property."""

    def test_not_ready_during_init(self, temp_db):
        """Test is_ready is False during INIT phase."""
        sync_state = SyncState(temp_db)
        status = sync_state.get_status()
        assert status.is_ready is False

    def test_not_ready_during_bulk_sessions(self, temp_db):
        """Test is_ready is False during BULK_SESSIONS (no data yet)."""
        sync_state = SyncState(temp_db)
        sync_state.set_phase(SyncPhase.BULK_SESSIONS)

        status = sync_state.get_status()
        assert status.is_ready is False

    def test_ready_only_in_realtime(self, temp_db):
        """Test is_ready is True only in REALTIME phase."""
        sync_state = SyncState(temp_db)

        sync_state.set_phase(SyncPhase.BULK_MESSAGES)
        assert sync_state.get_status().is_ready is False

        sync_state.set_phase(SyncPhase.BULK_PARTS)
        assert sync_state.get_status().is_ready is False

        sync_state.set_phase(SyncPhase.PROCESSING_QUEUE)
        assert sync_state.get_status().is_ready is False

        sync_state.set_phase(SyncPhase.REALTIME)
        assert sync_state.get_status().is_ready is True


# === Edge Cases ===


class TestSyncStateEdgeCases:
    """Edge case tests."""

    def test_multiple_start_bulk_calls(self, temp_db):
        """Test multiple start_bulk calls override previous values."""
        sync_state = SyncState(temp_db)

        sync_state.start_bulk(1000.0, total_files=100)
        sync_state.start_bulk(2000.0, total_files=200)

        assert sync_state.t0 == 2000.0
        status = sync_state.get_status()
        assert status.files_total == 200

    def test_update_progress_without_start_bulk(self, temp_db):
        """Test update_progress works without start_bulk."""
        sync_state = SyncState(temp_db)

        # Should not crash
        sync_state.update_progress(files_done=10)

        status = sync_state.get_status()
        assert status.files_done == 10
        assert status.files_total == 0
        assert status.progress == 0.0  # 0/0 = 0
