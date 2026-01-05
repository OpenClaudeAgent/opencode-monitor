"""
Tests for HybridIndexer resume behavior.

Tests cover:
- Skip bulk loading when already in realtime mode (resume scenario)
- Run bulk loading when fresh start (is_realtime=False)
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.sync_state import SyncPhase, SyncState
from opencode_monitor.analytics.indexer.bulk_loader import BulkLoader
from opencode_monitor.analytics.indexer.hybrid import HybridIndexer


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_storage(tmp_path):
    """Create temporary storage directory structure."""
    storage_path = tmp_path / "opencode_storage"
    for subdir in ["session", "message", "part"]:
        (storage_path / subdir).mkdir(parents=True, exist_ok=True)
    return storage_path


@pytest.fixture
def temp_db_path(tmp_path):
    """Create temporary database path."""
    return tmp_path / "test_analytics.duckdb"


# =============================================================================
# Tests for bulk phase skip behavior
# =============================================================================


class TestHybridIndexerResume:
    """Tests for HybridIndexer resume behavior when already in realtime mode."""

    def test_skips_bulk_when_already_realtime(self, temp_storage, temp_db_path):
        """When sync_state.is_realtime is True, bulk loading is skipped."""
        # Create mock components
        mock_db = MagicMock(spec=AnalyticsDB)
        mock_db._db_path = temp_db_path

        mock_sync_state = MagicMock(spec=SyncState)
        # Key condition: already in realtime mode
        mock_sync_state.is_realtime = True
        mock_sync_state.phase = SyncPhase.REALTIME

        mock_bulk_loader = MagicMock(spec=BulkLoader)

        # Create indexer with mocked dependencies
        indexer = HybridIndexer(
            storage_path=temp_storage,
            db=mock_db,
            sync_state=mock_sync_state,
            bulk_loader=mock_bulk_loader,
        )

        # Call _run_bulk_phase directly (simulating what happens after start)
        indexer._sync_state = mock_sync_state
        indexer._bulk_loader = mock_bulk_loader
        indexer._running = True

        indexer._run_bulk_phase()

        # Bulk loader should NOT be called when already in realtime
        mock_bulk_loader.load_all.assert_not_called()

    def test_runs_bulk_when_fresh_start(self, temp_storage, temp_db_path):
        """When sync_state.is_realtime is False, bulk loading runs."""
        # Create real database for this test
        db = AnalyticsDB(temp_db_path)
        db.connect()

        # Create real sync state (will start in INIT phase)
        sync_state = SyncState(db)

        # Verify it's not in realtime mode
        assert sync_state.is_realtime is False

        # Create mock bulk loader to track calls
        mock_bulk_loader = MagicMock(spec=BulkLoader)
        mock_bulk_loader.load_all.return_value = {
            "session": MagicMock(files_loaded=10, duration_seconds=0.5),
            "message": MagicMock(files_loaded=20, duration_seconds=0.3),
            "part": MagicMock(files_loaded=50, duration_seconds=0.2),
        }

        # Create indexer
        indexer = HybridIndexer(
            storage_path=temp_storage,
            db=db,
            sync_state=sync_state,
            bulk_loader=mock_bulk_loader,
        )

        # Set up required state (normally set in start())
        indexer._running = True
        indexer._t0 = time.time()
        indexer._sync_state = sync_state
        indexer._bulk_loader = mock_bulk_loader

        # Call _run_bulk_phase
        indexer._run_bulk_phase()

        # Bulk loader SHOULD be called when not in realtime mode
        mock_bulk_loader.load_all.assert_called_once()

        # Verify T0 was passed to load_all
        call_args = mock_bulk_loader.load_all.call_args
        assert call_args[0][0] is not None  # T0 timestamp passed

    def test_bulk_phase_transitions_to_realtime(self, temp_storage, temp_db_path):
        """After bulk phase completes, sync_state transitions to realtime."""
        db = AnalyticsDB(temp_db_path)
        db.connect()

        sync_state = SyncState(db)

        # Mock bulk loader
        mock_bulk_loader = MagicMock(spec=BulkLoader)
        mock_bulk_loader.load_all.return_value = {
            "session": MagicMock(files_loaded=5, duration_seconds=0.1),
            "message": MagicMock(files_loaded=10, duration_seconds=0.1),
            "part": MagicMock(files_loaded=15, duration_seconds=0.1),
        }

        indexer = HybridIndexer(
            storage_path=temp_storage,
            db=db,
            sync_state=sync_state,
            bulk_loader=mock_bulk_loader,
        )

        # Set up required state (normally set in start())
        indexer._running = True
        indexer._t0 = time.time()
        indexer._sync_state = sync_state
        indexer._bulk_loader = mock_bulk_loader

        # Before: not in realtime
        assert sync_state.phase != SyncPhase.REALTIME

        # Run bulk phase
        indexer._run_bulk_phase()

        # After: should be in realtime
        assert sync_state.phase == SyncPhase.REALTIME
        assert sync_state.is_realtime is True

    def test_skip_bulk_starts_realtime_processor(self, temp_storage, temp_db_path):
        """When bulk is skipped, realtime processor thread is started."""
        mock_db = MagicMock(spec=AnalyticsDB)
        mock_db._db_path = temp_db_path

        mock_sync_state = MagicMock(spec=SyncState)
        mock_sync_state.is_realtime = True

        indexer = HybridIndexer(
            storage_path=temp_storage,
            db=mock_db,
            sync_state=mock_sync_state,
        )

        indexer._sync_state = mock_sync_state
        indexer._running = True

        with patch("threading.Thread") as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            indexer._run_bulk_phase()

            # Thread should be created for realtime processing
            mock_thread.assert_called_once()
            call_kwargs = mock_thread.call_args[1]
            assert call_kwargs.get("name") == "hybrid-realtime"
            assert call_kwargs.get("daemon") is True

            # Thread should be started
            mock_thread_instance.start.assert_called_once()


class TestSyncStateRealtimeProperty:
    """Tests for SyncState.is_realtime property."""

    def test_is_realtime_false_for_init(self, analytics_db):
        """is_realtime is False when phase is INIT."""
        sync_state = SyncState(analytics_db)
        sync_state.set_phase(SyncPhase.INIT)

        assert sync_state.is_realtime is False

    def test_is_realtime_false_for_bulk_phases(self, analytics_db):
        """is_realtime is False during bulk loading phases."""
        sync_state = SyncState(analytics_db)

        for phase in [
            SyncPhase.BULK_SESSIONS,
            SyncPhase.BULK_MESSAGES,
            SyncPhase.BULK_PARTS,
        ]:
            sync_state.set_phase(phase)
            assert sync_state.is_realtime is False, f"Expected False for {phase}"

    def test_is_realtime_true_for_realtime_phase(self, analytics_db):
        """is_realtime is True when phase is REALTIME."""
        sync_state = SyncState(analytics_db)
        sync_state.set_phase(SyncPhase.REALTIME)

        assert sync_state.is_realtime is True
