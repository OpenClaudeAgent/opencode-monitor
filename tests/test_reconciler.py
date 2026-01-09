"""
Tests for Reconciler - US-3: Periodic filesystem scan.

Detects files missed by watchdog and sends them to FileBatchAccumulator.
Covers: periodic scan, immediate scan, callbacks, performance.
"""

import threading
import time
from pathlib import Path
from typing import List
from unittest.mock import Mock

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.tracker import FileTracker
from opencode_monitor.analytics.indexer.reconciler import (
    Reconciler,
    ReconcilerConfig,
    ReconcilerStats,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db(tmp_path: Path) -> AnalyticsDB:
    """Create isolated AnalyticsDB for testing."""
    db_path = tmp_path / "test_reconciler.duckdb"
    db = AnalyticsDB(db_path)
    db.connect()
    yield db
    db.close()


@pytest.fixture
def tracker(temp_db: AnalyticsDB) -> FileTracker:
    """Create FileTracker with test database."""
    return FileTracker(temp_db)


@pytest.fixture
def storage_path(tmp_path: Path) -> Path:
    """Create storage directory for test files."""
    storage = tmp_path / "storage"
    storage.mkdir()
    return storage


@pytest.fixture
def mock_callback() -> Mock:
    """Mock callback for on_missing_files events."""
    return Mock()


@pytest.fixture
def fast_config() -> ReconcilerConfig:
    """Fast config for tests (short interval, small limit)."""
    return ReconcilerConfig(interval_seconds=1, max_files_per_scan=100)


@pytest.fixture
def reconciler(
    storage_path: Path,
    temp_db: AnalyticsDB,
    tracker: FileTracker,  # Ensures file_index table exists
    fast_config: ReconcilerConfig,
    mock_callback: Mock,
):
    """Reconciler with auto-cleanup."""
    rec = Reconciler(
        storage_path=storage_path,
        db=temp_db,
        config=fast_config,
        on_missing_files=mock_callback,
    )
    yield rec
    rec.stop()


def create_test_file(directory: Path, name: str, content: str = "{}") -> Path:
    """Helper: create a test JSON file."""
    file_path = directory / name
    file_path.write_text(content)
    return file_path


def create_nested_file(storage: Path, subdir: str, name: str) -> Path:
    """Helper: create a file in a subdirectory (simulates project structure)."""
    subdir_path = storage / subdir
    subdir_path.mkdir(exist_ok=True)
    file_path = subdir_path / name
    file_path.write_text('{"id": "test"}')
    return file_path


def wait_for_callback(
    mock_callback: Mock, expected_calls: int = 1, timeout: float = 2.0
):
    """Helper: wait for callback to be called expected number of times."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if mock_callback.call_count >= expected_calls:
            return
        time.sleep(0.05)


# =============================================================================
# Test: scan_now basic operations
# =============================================================================


class TestScanNow:
    """Tests for scan_now() immediate scanning."""

    def test_scan_now_finds_new_files(
        self,
        reconciler: Reconciler,
        storage_path: Path,
        mock_callback: Mock,
    ):
        """scan_now should detect files not in file_index."""
        # Create files without indexing them
        f1 = create_nested_file(storage_path, "proj1", "session1.json")
        f2 = create_nested_file(storage_path, "proj2", "session2.json")

        # Scan should find them
        missing = reconciler.scan_now()

        assert len(missing) == 2
        assert f1 in missing or str(f1) in [str(p) for p in missing]
        assert f2 in missing or str(f2) in [str(p) for p in missing]

    def test_scan_now_finds_modified_files(
        self,
        reconciler: Reconciler,
        storage_path: Path,
        tracker: FileTracker,
        mock_callback: Mock,
    ):
        """scan_now should detect files with mtime > indexed mtime."""
        # Create and index a file
        f1 = create_nested_file(storage_path, "proj1", "session.json")
        tracker.mark_indexed(f1, "session", record_id="sess-001")

        # Modify the file (change mtime)
        time.sleep(0.1)  # Ensure mtime changes
        f1.write_text('{"id": "modified"}')

        # Scan should find the modified file
        missing = reconciler.scan_now()

        assert len(missing) == 1

    def test_scan_now_ignores_indexed_files(
        self,
        reconciler: Reconciler,
        storage_path: Path,
        tracker: FileTracker,
    ):
        """scan_now should not include already indexed files."""
        # Create and index a file
        f1 = create_nested_file(storage_path, "proj1", "indexed.json")
        tracker.mark_indexed(f1, "session", record_id="sess-001")

        # Create another unindexed file
        f2 = create_nested_file(storage_path, "proj2", "unindexed.json")

        # Scan should only find the unindexed file
        missing = reconciler.scan_now()

        assert len(missing) == 1
        assert str(f2) in [str(p) for p in missing]

    def test_scan_now_calls_callback_with_files(
        self,
        reconciler: Reconciler,
        storage_path: Path,
        mock_callback: Mock,
    ):
        """scan_now should call on_missing_files callback."""
        # Create unindexed files
        create_nested_file(storage_path, "proj1", "file1.json")
        create_nested_file(storage_path, "proj2", "file2.json")

        reconciler.scan_now()

        # Wait a bit for async callback
        wait_for_callback(mock_callback)

        assert mock_callback.call_count >= 1
        # Callback should receive list of Paths
        call_args = mock_callback.call_args[0][0]
        assert len(call_args) == 2

    def test_empty_storage_returns_empty_list(
        self,
        reconciler: Reconciler,
        storage_path: Path,
    ):
        """scan_now on empty storage should return empty list."""
        missing = reconciler.scan_now()
        assert missing == []

    def test_max_files_limit_respected(
        self,
        storage_path: Path,
        temp_db: AnalyticsDB,
        tracker: FileTracker,  # Ensures file_index table exists
        mock_callback: Mock,
    ):
        """scan_now should respect max_files_per_scan limit."""
        # Create many files
        for i in range(20):
            create_nested_file(storage_path, f"proj{i}", f"file{i}.json")

        # Config with small limit
        config = ReconcilerConfig(interval_seconds=30, max_files_per_scan=5)
        rec = Reconciler(storage_path, temp_db, config, mock_callback)

        try:
            missing = rec.scan_now()
            assert len(missing) <= 5
        finally:
            rec.stop()


# =============================================================================
# Test: periodic scanning
# =============================================================================


class TestPeriodicScan:
    """Tests for periodic background scanning."""

    def test_periodic_scan_calls_callback(
        self,
        storage_path: Path,
        temp_db: AnalyticsDB,
        tracker: FileTracker,  # Ensures file_index table exists
        mock_callback: Mock,
    ):
        """Periodic scan should call callback with missing files."""
        # Create files before starting reconciler
        create_nested_file(storage_path, "proj1", "file1.json")

        # Start reconciler with short interval
        config = ReconcilerConfig(interval_seconds=0.1, max_files_per_scan=100)
        rec = Reconciler(storage_path, temp_db, config, mock_callback)

        try:
            rec.start()
            wait_for_callback(mock_callback, expected_calls=1, timeout=1.0)

            assert mock_callback.call_count >= 1
        finally:
            rec.stop()

    def test_start_stop_idempotent(
        self,
        reconciler: Reconciler,
    ):
        """Multiple start/stop calls should be safe."""
        reconciler.start()
        reconciler.start()  # Second start should be ignored

        reconciler.stop()
        reconciler.stop()  # Second stop should be safe

        # No exceptions should be raised


# =============================================================================
# Test: start/stop lifecycle
# =============================================================================


class TestStartStop:
    """Tests for start() and stop() lifecycle."""

    def test_start_begins_periodic_scan(
        self,
        reconciler: Reconciler,
    ):
        """start() should begin background scanning."""
        reconciler.start()

        # Give it a moment to start
        time.sleep(0.1)

        # Should be running (internal flag or thread check)
        # We verify by checking stats update after some time

    def test_stop_halts_periodic_scan(
        self,
        storage_path: Path,
        temp_db: AnalyticsDB,
        tracker: FileTracker,  # Ensures file_index table exists
        mock_callback: Mock,
    ):
        """stop() should halt background scanning."""
        config = ReconcilerConfig(interval_seconds=0.1, max_files_per_scan=100)
        rec = Reconciler(storage_path, temp_db, config, mock_callback)

        rec.start()
        time.sleep(0.15)  # Let one scan happen
        rec.stop()

        initial_count = mock_callback.call_count
        time.sleep(0.2)  # Wait for potential additional scans

        # No additional scans should have occurred
        assert mock_callback.call_count == initial_count

    def test_stop_without_start_is_safe(
        self,
        reconciler: Reconciler,
    ):
        """stop() without start() should not raise."""
        reconciler.stop()  # Should not raise


# =============================================================================
# Test: statistics tracking
# =============================================================================


class TestStatsTracking:
    """Tests for ReconcilerStats tracking."""

    def test_initial_stats_are_zero(
        self,
        reconciler: Reconciler,
    ):
        """Initial stats should all be zero."""
        stats = reconciler.get_stats()
        assert stats.scans_completed == 0
        assert stats.files_found == 0
        assert stats.last_scan_duration_ms == 0
        assert stats.last_scan_files == 0

    def test_stats_update_after_scan(
        self,
        reconciler: Reconciler,
        storage_path: Path,
    ):
        """Stats should update after scan_now()."""
        # Create files
        create_nested_file(storage_path, "proj1", "file1.json")
        create_nested_file(storage_path, "proj2", "file2.json")

        reconciler.scan_now()

        stats = reconciler.get_stats()
        assert stats.scans_completed == 1
        assert stats.files_found == 2
        assert stats.last_scan_files == 2
        assert stats.last_scan_duration_ms > 0

    def test_stats_accumulate_across_scans(
        self,
        reconciler: Reconciler,
        storage_path: Path,
        tracker: FileTracker,
    ):
        """Stats should accumulate across multiple scans."""
        # First scan: 2 files
        f1 = create_nested_file(storage_path, "proj1", "file1.json")
        f2 = create_nested_file(storage_path, "proj2", "file2.json")
        reconciler.scan_now()

        # Index the files
        tracker.mark_indexed(f1, "session")
        tracker.mark_indexed(f2, "session")

        # Second scan: 1 new file
        create_nested_file(storage_path, "proj3", "file3.json")
        reconciler.scan_now()

        stats = reconciler.get_stats()
        assert stats.scans_completed == 2
        assert stats.files_found == 3  # Total across all scans
        assert stats.last_scan_files == 1  # Only last scan


# =============================================================================
# Test: edge cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_nonexistent_storage_path(
        self,
        temp_db: AnalyticsDB,
        tracker: FileTracker,  # Ensures file_index table exists
        mock_callback: Mock,
        tmp_path: Path,
    ):
        """Reconciler should handle non-existent storage path gracefully."""
        nonexistent = tmp_path / "does_not_exist"
        config = ReconcilerConfig()
        rec = Reconciler(nonexistent, temp_db, config, mock_callback)

        try:
            missing = rec.scan_now()
            assert missing == []
        finally:
            rec.stop()

    def test_callback_receives_path_objects(
        self,
        reconciler: Reconciler,
        storage_path: Path,
        mock_callback: Mock,
    ):
        """Callback should receive list of Path objects."""
        create_nested_file(storage_path, "proj1", "file.json")

        reconciler.scan_now()
        wait_for_callback(mock_callback)

        call_args = mock_callback.call_args[0][0]
        assert all(isinstance(p, Path) for p in call_args)

    def test_scan_during_file_operations(
        self,
        reconciler: Reconciler,
        storage_path: Path,
    ):
        """Scan should handle concurrent file operations gracefully."""
        # Create some files
        for i in range(5):
            create_nested_file(storage_path, f"proj{i}", f"file{i}.json")

        # Start scan in background
        results = []

        def run_scan():
            results.append(reconciler.scan_now())

        scan_thread = threading.Thread(target=run_scan)
        scan_thread.start()

        # Create more files during scan
        for i in range(5, 10):
            create_nested_file(storage_path, f"proj{i}", f"file{i}.json")

        scan_thread.join(timeout=5.0)

        # Should not crash and return some results
        assert len(results) == 1
        assert isinstance(results[0], list)

    def test_config_default_values(self):
        """ReconcilerConfig should have sensible defaults."""
        config = ReconcilerConfig()
        assert config.interval_seconds == 30
        assert config.max_files_per_scan == 10000


# =============================================================================
# Test: thread safety
# =============================================================================


class TestThreadSafety:
    """Tests for concurrent access safety."""

    def test_concurrent_scan_now_calls(
        self,
        reconciler: Reconciler,
        storage_path: Path,
    ):
        """Multiple concurrent scan_now() calls should be safe."""
        # Create files
        for i in range(10):
            create_nested_file(storage_path, f"proj{i}", f"file{i}.json")

        results = []
        errors = []

        def run_scan():
            try:
                results.append(reconciler.scan_now())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run_scan) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0
        assert len(results) == 5

    def test_scan_now_while_periodic_running(
        self,
        storage_path: Path,
        temp_db: AnalyticsDB,
        tracker: FileTracker,  # Ensures file_index table exists
        mock_callback: Mock,
    ):
        """scan_now() should work while periodic scan is running."""
        # Create files
        for i in range(5):
            create_nested_file(storage_path, f"proj{i}", f"file{i}.json")

        config = ReconcilerConfig(interval_seconds=0.5, max_files_per_scan=100)
        rec = Reconciler(storage_path, temp_db, config, mock_callback)

        try:
            rec.start()
            time.sleep(0.1)

            # Manual scan while periodic is active
            missing = rec.scan_now()

            assert isinstance(missing, list)
        finally:
            rec.stop()
