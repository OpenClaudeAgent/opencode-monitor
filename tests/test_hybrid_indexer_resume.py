"""
Tests for HybridIndexer resume behavior.

Tests cover:
- Skip bulk loading when already in realtime mode (resume scenario)
- Run bulk loading when fresh start (is_realtime=False)
- SyncState phase transitions and is_realtime property
"""

import time
from unittest.mock import MagicMock, patch

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
def temp_db(tmp_path):
    """Create temporary database."""
    db = AnalyticsDB(tmp_path / "test_analytics.duckdb")
    db.connect()
    return db


@pytest.fixture
def mock_bulk_loader():
    """Create mock bulk loader with standard return values."""
    loader = MagicMock(spec=BulkLoader)
    loader.load_all.return_value = {
        "session": MagicMock(files_loaded=10, duration_seconds=0.1),
        "message": MagicMock(files_loaded=20, duration_seconds=0.1),
        "part": MagicMock(files_loaded=30, duration_seconds=0.1),
    }
    return loader


def create_indexer(storage, db, sync_state, bulk_loader=None, running=True):
    """Helper to create a configured HybridIndexer for testing."""
    indexer = HybridIndexer(
        storage_path=storage,
        db=db,
        sync_state=sync_state,
        bulk_loader=bulk_loader,
    )
    indexer._running = running
    indexer._t0 = time.time()
    indexer._sync_state = sync_state
    if bulk_loader:
        indexer._bulk_loader = bulk_loader
    return indexer


# =============================================================================
# HybridIndexer Resume Tests
# =============================================================================


class TestHybridIndexerResume:
    """Tests for HybridIndexer resume behavior when already in realtime mode."""

    def test_skips_bulk_when_already_realtime(
        self, temp_storage, temp_db, mock_bulk_loader
    ):
        """When sync_state.is_realtime is True, bulk loading is skipped entirely."""
        sync_state = SyncState(temp_db)
        sync_state.set_phase(SyncPhase.REALTIME)

        indexer = create_indexer(temp_storage, temp_db, sync_state, mock_bulk_loader)

        # Verify preconditions
        assert sync_state.is_realtime is True
        assert sync_state.phase == SyncPhase.REALTIME

        indexer._run_bulk_phase()

        # Bulk loader should NOT be called
        mock_bulk_loader.load_all.assert_not_called()
        # Phase should remain REALTIME
        assert sync_state.phase == SyncPhase.REALTIME

    def test_runs_bulk_when_fresh_start(self, temp_storage, temp_db, mock_bulk_loader):
        """When sync_state.is_realtime is False, bulk loading runs completely."""
        sync_state = SyncState(temp_db)

        # Verify fresh start state
        assert sync_state.is_realtime is False
        assert sync_state.phase == SyncPhase.INIT

        indexer = create_indexer(temp_storage, temp_db, sync_state, mock_bulk_loader)
        indexer._run_bulk_phase()

        # Bulk loader SHOULD be called
        mock_bulk_loader.load_all.assert_called_once()

        # Verify T0 was passed correctly
        call_args = mock_bulk_loader.load_all.call_args
        t0_arg = call_args[0][0]
        assert t0_arg is not None
        assert isinstance(t0_arg, float)
        assert t0_arg > 0

        # Phase should transition to REALTIME
        assert sync_state.phase == SyncPhase.REALTIME
        assert sync_state.is_realtime is True

    def test_bulk_phase_transitions_through_all_phases(
        self, temp_storage, temp_db, mock_bulk_loader
    ):
        """Bulk phase correctly transitions sync_state to realtime after completion."""
        sync_state = SyncState(temp_db)

        # Track phase changes
        initial_phase = sync_state.phase
        assert initial_phase == SyncPhase.INIT

        indexer = create_indexer(temp_storage, temp_db, sync_state, mock_bulk_loader)
        indexer._run_bulk_phase()

        # Final state verification
        assert sync_state.phase == SyncPhase.REALTIME
        assert sync_state.is_realtime is True
        # Verify the transition was persisted (survives reload)
        fresh_state = SyncState(temp_db)
        assert fresh_state.phase == SyncPhase.REALTIME

    def test_skip_bulk_starts_realtime_processor_thread(self, temp_storage, temp_db):
        """When bulk is skipped, realtime processor thread is started correctly."""
        sync_state = SyncState(temp_db)
        sync_state.set_phase(SyncPhase.REALTIME)

        indexer = create_indexer(temp_storage, temp_db, sync_state)

        with patch("threading.Thread") as mock_thread:
            mock_instance = MagicMock()
            mock_thread.return_value = mock_instance

            indexer._run_bulk_phase()

            # Thread created with correct parameters
            mock_thread.assert_called_once()
            call_kwargs = mock_thread.call_args[1]
            assert call_kwargs.get("name") == "hybrid-realtime"
            assert call_kwargs.get("daemon") is True
            assert "target" in call_kwargs

            # Thread was started
            mock_instance.start.assert_called_once()


# =============================================================================
# SyncState is_realtime Property Tests
# =============================================================================


class TestSyncStateIsRealtime:
    """Tests for SyncState.is_realtime property across all phases."""

    @pytest.mark.parametrize(
        "phase,expected_realtime",
        [
            (SyncPhase.INIT, False),
            (SyncPhase.BULK_SESSIONS, False),
            (SyncPhase.BULK_MESSAGES, False),
            (SyncPhase.BULK_PARTS, False),
            (SyncPhase.REALTIME, True),
        ],
    )
    def test_is_realtime_for_each_phase(self, analytics_db, phase, expected_realtime):
        """is_realtime correctly reflects whether phase is REALTIME."""
        sync_state = SyncState(analytics_db)
        sync_state.set_phase(phase)

        assert sync_state.is_realtime is expected_realtime
        assert sync_state.phase == phase
        # Verify phase name is accessible
        assert phase.name in [
            "INIT",
            "BULK_SESSIONS",
            "BULK_MESSAGES",
            "BULK_PARTS",
            "REALTIME",
        ]

    def test_phase_persistence(self, analytics_db):
        """Phase changes are persisted to database."""
        sync_state = SyncState(analytics_db)

        # Set to realtime
        sync_state.set_phase(SyncPhase.REALTIME)
        assert sync_state.phase == SyncPhase.REALTIME

        # Create new instance - should load persisted state
        fresh_state = SyncState(analytics_db)
        assert fresh_state.phase == SyncPhase.REALTIME
        assert fresh_state.is_realtime is True
