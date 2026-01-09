"""
Integration tests for Plan 46 Unified Indexer v2 components.

Tests the interaction between:
- FileTracker (US-1): Status tracking with indexed/pending/error states
- FileBatchAccumulator (US-2): Micro-batch accumulation with deduplication
- Reconciler (US-3): Periodic filesystem scan for missed files

These tests verify that the components work correctly together in realistic scenarios.
"""

import threading
import time
from pathlib import Path
from typing import List

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.tracker import FileTracker
from opencode_monitor.analytics.indexer.batch_accumulator import (
    AccumulatorConfig,
    FileBatchAccumulator,
)
from opencode_monitor.analytics.indexer.reconciler import (
    Reconciler,
    ReconcilerConfig,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db(tmp_path: Path) -> AnalyticsDB:
    """Create isolated AnalyticsDB for testing."""
    db_path = tmp_path / "test_integration.duckdb"
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


def create_nested_file(
    storage: Path, subdir: str, name: str, content: str = '{"id": "test"}'
) -> Path:
    """Helper: create a file in a subdirectory (simulates project structure)."""
    subdir_path = storage / subdir
    subdir_path.mkdir(exist_ok=True)
    file_path = subdir_path / name
    file_path.write_text(content)
    return file_path


def wait_for_condition(
    condition_fn, timeout: float = 2.0, poll_interval: float = 0.02
) -> bool:
    """Helper: wait for a condition to be true with polling."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition_fn():
            return True
        time.sleep(poll_interval)
    return False


# =============================================================================
# Test: Reconciler → FileBatchAccumulator Integration
# =============================================================================


class TestReconcilerAccumulatorIntegration:
    """Tests Reconciler → FileBatchAccumulator pipeline."""

    def test_reconciler_feeds_accumulator(
        self,
        storage_path: Path,
        temp_db: AnalyticsDB,
        tracker: FileTracker,
    ):
        """Reconciler missing files should flow to accumulator batches.

        Scenario:
        1. Setup: Reconciler with callback that feeds Accumulator
        2. Create unindexed files
        3. Reconciler.scan_now() finds them
        4. Accumulator receives the files
        5. Force flush and verify batch callback received correct files
        """
        # Track received batches
        received_batches: List[List[Path]] = []
        batch_received = threading.Event()

        def on_batch_ready(files: List[Path]) -> None:
            received_batches.append(files)
            batch_received.set()

        # Setup Accumulator with callback
        acc_config = AccumulatorConfig(
            window_ms=5000, max_files=100, flush_on_stop=True
        )
        accumulator = FileBatchAccumulator(acc_config, on_batch_ready)

        # Setup Reconciler that feeds Accumulator
        def on_missing_files(files: List[Path]) -> None:
            accumulator.add_many(files)

        rec_config = ReconcilerConfig(interval_seconds=60, max_files_per_scan=1000)
        reconciler = Reconciler(storage_path, temp_db, rec_config, on_missing_files)

        try:
            # Create unindexed files
            f1 = create_nested_file(storage_path, "proj1", "session1.json")
            f2 = create_nested_file(storage_path, "proj2", "session2.json")
            f3 = create_nested_file(storage_path, "proj3", "session3.json")

            # Scan should find them and feed to accumulator
            missing = reconciler.scan_now()
            assert len(missing) == 3

            # Force flush accumulator
            count = accumulator.force_flush()
            assert count == 3

            # Wait for batch callback
            assert batch_received.wait(timeout=1.0), "Batch callback not received"

            # Verify batch contains correct files
            assert len(received_batches) == 1
            batch_files = received_batches[0]
            assert len(batch_files) == 3
            batch_paths = {str(p) for p in batch_files}
            assert str(f1) in batch_paths
            assert str(f2) in batch_paths
            assert str(f3) in batch_paths

        finally:
            accumulator.stop()
            reconciler.stop()

    def test_reconciler_accumulator_deduplication(
        self,
        storage_path: Path,
        temp_db: AnalyticsDB,
        tracker: FileTracker,
    ):
        """Multiple reconciler scans should deduplicate in accumulator.

        Scenario:
        1. Create files
        2. Scan multiple times (simulates overlapping scans)
        3. Accumulator should deduplicate same files
        """
        received_batches: List[List[Path]] = []

        def on_batch_ready(files: List[Path]) -> None:
            received_batches.append(files)

        acc_config = AccumulatorConfig(
            window_ms=5000, max_files=100, flush_on_stop=True
        )
        accumulator = FileBatchAccumulator(acc_config, on_batch_ready)

        def on_missing_files(files: List[Path]) -> None:
            accumulator.add_many(files)

        rec_config = ReconcilerConfig(interval_seconds=60, max_files_per_scan=1000)
        reconciler = Reconciler(storage_path, temp_db, rec_config, on_missing_files)

        try:
            # Create 2 files
            f1 = create_nested_file(storage_path, "proj1", "file1.json")
            f2 = create_nested_file(storage_path, "proj2", "file2.json")

            # Scan 3 times (simulates rapid scans)
            reconciler.scan_now()
            reconciler.scan_now()
            reconciler.scan_now()

            # Accumulator should have deduplicated
            stats = accumulator.get_stats()
            assert stats.files_accumulated == 2  # Only 2 unique files
            assert (
                stats.files_deduplicated == 4
            )  # 3 scans x 2 files - 2 unique = 4 dupes

            # Force flush - should only get 2 files
            count = accumulator.force_flush()
            assert count == 2

        finally:
            accumulator.stop()
            reconciler.stop()


# =============================================================================
# Test: Full Pipeline (Reconciler → Accumulator → FileTracker)
# =============================================================================


class TestFullPipeline:
    """Tests the complete indexing pipeline."""

    def test_full_pipeline_new_files(
        self,
        storage_path: Path,
        temp_db: AnalyticsDB,
        tracker: FileTracker,
    ):
        """New files: detect → batch → mark indexed.

        Complete flow:
        1. Create files
        2. Reconciler scans → finds files
        3. Accumulator receives → creates batch
        4. Simulate processing → FileTracker.mark_indexed_batch()
        5. Re-scan → 0 files (all indexed now)
        """
        # Track batches for "processing"
        batches_to_process: List[List[Path]] = []
        processing_done = threading.Event()

        def on_batch_ready(files: List[Path]) -> None:
            batches_to_process.append(files)
            processing_done.set()

        acc_config = AccumulatorConfig(window_ms=50, max_files=100, flush_on_stop=True)
        accumulator = FileBatchAccumulator(acc_config, on_batch_ready)

        def on_missing_files(files: List[Path]) -> None:
            accumulator.add_many(files)

        rec_config = ReconcilerConfig(interval_seconds=60, max_files_per_scan=1000)
        reconciler = Reconciler(storage_path, temp_db, rec_config, on_missing_files)

        try:
            # Step 1: Create new files
            f1 = create_nested_file(storage_path, "proj1", "session1.json")
            f2 = create_nested_file(storage_path, "proj2", "session2.json")
            f3 = create_nested_file(storage_path, "proj3", "session3.json")

            # Step 2: First scan - should find all 3 files
            missing = reconciler.scan_now()
            assert len(missing) == 3

            # Step 3: Force flush to trigger batch callback
            accumulator.force_flush()

            # Wait for batch callback
            assert processing_done.wait(timeout=1.0), "Batch not received"
            assert len(batches_to_process) == 1
            batch = batches_to_process[0]
            assert len(batch) == 3

            # Step 4: Simulate processing - mark files as indexed
            items = [(p, "session", f"record-{i}") for i, p in enumerate(batch)]
            count = tracker.mark_indexed_batch(items)
            assert count == 3

            # Verify files are now indexed
            for f in [f1, f2, f3]:
                info = tracker.get_file_info(f)
                assert info is not None
                assert info.status == "indexed"

            # Step 5: Re-scan - should find 0 files (all indexed)
            processing_done.clear()
            missing_after = reconciler.scan_now()
            assert len(missing_after) == 0

        finally:
            accumulator.stop()
            reconciler.stop()

    def test_full_pipeline_modified_files(
        self,
        storage_path: Path,
        temp_db: AnalyticsDB,
        tracker: FileTracker,
    ):
        """Modified files: detect mtime change → re-index.

        Complete flow:
        1. Create and index files
        2. Modify mtime of one file
        3. Reconciler scans → detects modified file
        4. Re-index the modified file
        """
        batches_received: List[List[Path]] = []
        batch_event = threading.Event()

        def on_batch_ready(files: List[Path]) -> None:
            batches_received.append(files)
            batch_event.set()

        acc_config = AccumulatorConfig(window_ms=50, max_files=100, flush_on_stop=True)
        accumulator = FileBatchAccumulator(acc_config, on_batch_ready)

        def on_missing_files(files: List[Path]) -> None:
            accumulator.add_many(files)

        rec_config = ReconcilerConfig(interval_seconds=60, max_files_per_scan=1000)
        reconciler = Reconciler(storage_path, temp_db, rec_config, on_missing_files)

        try:
            # Step 1: Create files and mark them as indexed
            f1 = create_nested_file(storage_path, "proj1", "session1.json")
            f2 = create_nested_file(storage_path, "proj2", "session2.json")

            tracker.mark_indexed(f1, "session", record_id="sess-001")
            tracker.mark_indexed(f2, "session", record_id="sess-002")

            # Verify initial scan finds nothing (all indexed)
            initial_missing = reconciler.scan_now()
            assert len(initial_missing) == 0

            # Step 2: Modify f1 (change mtime by rewriting)
            time.sleep(0.1)  # Ensure mtime changes
            f1.write_text('{"id": "modified-content"}')

            # Step 3: Scan should detect the modified file
            modified = reconciler.scan_now()
            assert len(modified) == 1
            assert str(f1) in [str(p) for p in modified]

            # Flush and verify
            accumulator.force_flush()
            assert batch_event.wait(timeout=1.0), "Batch not received"

            assert len(batches_received) == 1
            assert len(batches_received[0]) == 1

            # Step 4: Re-index the modified file
            tracker.mark_indexed(f1, "session", record_id="sess-001-v2")

            # Verify re-scan finds nothing
            batch_event.clear()
            final_missing = reconciler.scan_now()
            assert len(final_missing) == 0

        finally:
            accumulator.stop()
            reconciler.stop()

    def test_full_pipeline_error_handling(
        self,
        storage_path: Path,
        temp_db: AnalyticsDB,
        tracker: FileTracker,
    ):
        """Error files should be properly tracked and recoverable.

        Design: Error files are NOT automatically re-scanned by reconciler.
        This is intentional - files that fail parsing would keep failing.
        They must be explicitly reset or processed via a different mechanism.

        Flow:
        1. Create new file -> reconciler finds it
        2. Mark as error (simulates parsing failure)
        3. Scan should not find it (error files are excluded from modified check)
        4. New file created -> reconciler finds it (not the error one)
        5. Mark error file as indexed -> confirms status transitions work
        """
        batches_received: List[List[Path]] = []

        def on_batch_ready(files: List[Path]) -> None:
            batches_received.append(files)

        acc_config = AccumulatorConfig(
            window_ms=5000, max_files=100, flush_on_stop=True
        )
        accumulator = FileBatchAccumulator(acc_config, on_batch_ready)

        def on_missing_files(files: List[Path]) -> None:
            accumulator.add_many(files)

        rec_config = ReconcilerConfig(interval_seconds=60, max_files_per_scan=1000)
        reconciler = Reconciler(storage_path, temp_db, rec_config, on_missing_files)

        try:
            # Step 1: Create file - reconciler should find it (new file)
            f1 = create_nested_file(
                storage_path, "proj1", "file1.json", '{"id": "test"}'
            )

            missing = reconciler.scan_now()
            assert len(missing) == 1
            assert str(f1) in [str(p) for p in missing]

            # Step 2: Mark as error (simulates parsing failure)
            tracker.mark_error(f1, "session", "JSON parse error")

            # Verify error status
            info = tracker.get_file_info(f1)
            assert info is not None
            assert info.status == "error"
            assert info.error_message == "JSON parse error"

            # Step 3: Scan should not find the error file
            # (error files are excluded from the "modified" check by design)
            missing = reconciler.scan_now()
            assert len(missing) == 0

            # Step 4: Create a new file - reconciler should find it
            f2 = create_nested_file(
                storage_path, "proj2", "file2.json", '{"id": "test2"}'
            )

            missing = reconciler.scan_now()
            assert len(missing) == 1
            assert str(f2) in [str(p) for p in missing]
            # Error file f1 should NOT be in the results
            assert str(f1) not in [str(p) for p in missing]

            # Step 5: Recovery - manually mark error file as indexed (after fix)
            tracker.mark_indexed(f1, "session", record_id="sess-fixed")
            info = tracker.get_file_info(f1)
            assert info.status == "indexed"
            assert info.error_message is None

        finally:
            accumulator.stop()
            reconciler.stop()

    def test_full_pipeline_concurrent_operations(
        self,
        storage_path: Path,
        temp_db: AnalyticsDB,
        tracker: FileTracker,
    ):
        """Pipeline should handle concurrent file creation and scanning.

        Stress test with:
        - Multiple files created
        - Concurrent scans
        - Batch processing
        """
        total_batches: List[List[Path]] = []
        batch_lock = threading.Lock()

        def on_batch_ready(files: List[Path]) -> None:
            with batch_lock:
                total_batches.append(files)

        acc_config = AccumulatorConfig(window_ms=100, max_files=50, flush_on_stop=True)
        accumulator = FileBatchAccumulator(acc_config, on_batch_ready)

        def on_missing_files(files: List[Path]) -> None:
            accumulator.add_many(files)

        rec_config = ReconcilerConfig(interval_seconds=60, max_files_per_scan=1000)
        reconciler = Reconciler(storage_path, temp_db, rec_config, on_missing_files)

        try:
            # Create many files
            created_files: List[Path] = []
            for i in range(20):
                f = create_nested_file(storage_path, f"proj{i % 5}", f"file{i}.json")
                created_files.append(f)

            # Run concurrent scans
            scan_results: List[List[Path]] = []
            errors: List[Exception] = []

            def run_scan():
                try:
                    result = reconciler.scan_now()
                    scan_results.append(result)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=run_scan) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5.0)

            assert len(errors) == 0, f"Errors during scans: {errors}"
            assert len(scan_results) == 3

            # Each scan should find 20 files (before any indexing)
            # Due to serialization, they all see the same state
            for result in scan_results:
                assert len(result) == 20

            # Flush and process
            accumulator.force_flush()
            time.sleep(0.2)  # Wait for callbacks

            # Due to deduplication, we should have 20 unique files total
            stats = accumulator.get_stats()
            assert stats.files_accumulated == 20

            # Mark all as indexed
            items = [(f, "session", f"record-{i}") for i, f in enumerate(created_files)]
            tracker.mark_indexed_batch(items)

            # Final scan should find 0
            final = reconciler.scan_now()
            assert len(final) == 0

        finally:
            accumulator.stop()
            reconciler.stop()


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestIntegrationEdgeCases:
    """Edge cases for component integration."""

    def test_empty_storage_no_errors(
        self,
        storage_path: Path,
        temp_db: AnalyticsDB,
        tracker: FileTracker,
    ):
        """Empty storage should work without errors."""
        batches_received: List[List[Path]] = []

        def on_batch_ready(files: List[Path]) -> None:
            batches_received.append(files)

        acc_config = AccumulatorConfig(window_ms=50, max_files=100, flush_on_stop=True)
        accumulator = FileBatchAccumulator(acc_config, on_batch_ready)

        def on_missing_files(files: List[Path]) -> None:
            accumulator.add_many(files)

        rec_config = ReconcilerConfig(interval_seconds=60, max_files_per_scan=1000)
        reconciler = Reconciler(storage_path, temp_db, rec_config, on_missing_files)

        try:
            # Scan empty storage
            missing = reconciler.scan_now()
            assert missing == []

            # No batches should be created
            accumulator.stop()
            time.sleep(0.1)
            assert len(batches_received) == 0

        finally:
            reconciler.stop()

    def test_rapid_file_changes(
        self,
        storage_path: Path,
        temp_db: AnalyticsDB,
        tracker: FileTracker,
    ):
        """Rapid file changes should be handled correctly."""
        batches_received: List[List[Path]] = []
        batch_event = threading.Event()

        def on_batch_ready(files: List[Path]) -> None:
            batches_received.append(files)
            batch_event.set()

        acc_config = AccumulatorConfig(window_ms=100, max_files=100, flush_on_stop=True)
        accumulator = FileBatchAccumulator(acc_config, on_batch_ready)

        def on_missing_files(files: List[Path]) -> None:
            accumulator.add_many(files)

        rec_config = ReconcilerConfig(interval_seconds=60, max_files_per_scan=1000)
        reconciler = Reconciler(storage_path, temp_db, rec_config, on_missing_files)

        try:
            # Create, modify, modify rapidly
            f1 = create_nested_file(storage_path, "proj1", "rapid.json", '{"v": 1}')

            # Scan 1 - finds new file
            reconciler.scan_now()
            accumulator.force_flush()
            batch_event.wait(timeout=1.0)

            # Index it
            tracker.mark_indexed(f1, "session", record_id="v1")
            batch_event.clear()

            # Rapid modifications
            for v in range(2, 5):
                time.sleep(0.05)  # Small delay to ensure mtime changes
                f1.write_text(f'{{"v": {v}}}')

            # Scan should find the modified file
            modified = reconciler.scan_now()
            assert len(modified) == 1

            # Re-index
            tracker.mark_indexed(f1, "session", record_id="v4")

            # Final check
            final = reconciler.scan_now()
            assert len(final) == 0

        finally:
            accumulator.stop()
            reconciler.stop()

    def test_file_deleted_during_scan(
        self,
        storage_path: Path,
        temp_db: AnalyticsDB,
        tracker: FileTracker,
    ):
        """Deleted files should be handled gracefully."""
        batches_received: List[List[Path]] = []

        def on_batch_ready(files: List[Path]) -> None:
            batches_received.append(files)

        acc_config = AccumulatorConfig(
            window_ms=5000, max_files=100, flush_on_stop=True
        )
        accumulator = FileBatchAccumulator(acc_config, on_batch_ready)

        def on_missing_files(files: List[Path]) -> None:
            # Simulate: delete file before adding to accumulator
            valid_files = [f for f in files if f.exists()]
            if valid_files:
                accumulator.add_many(valid_files)

        rec_config = ReconcilerConfig(interval_seconds=60, max_files_per_scan=1000)
        reconciler = Reconciler(storage_path, temp_db, rec_config, on_missing_files)

        try:
            # Create files
            f1 = create_nested_file(storage_path, "proj1", "keep.json")
            f2 = create_nested_file(storage_path, "proj2", "delete.json")

            # Delete f2 before scan
            f2.unlink()

            # Scan should handle missing file gracefully
            missing = reconciler.scan_now()
            # Only f1 should be found (f2 doesn't exist)
            assert len(missing) == 1

        finally:
            accumulator.stop()
            reconciler.stop()
