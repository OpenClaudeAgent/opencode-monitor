"""
Tests for FileBatchAccumulator - US-2: Micro-batch accumulator.

TDD tests for the batch accumulator that groups file events before DuckDB insertion.
Covers: thread safety, deduplication, timer triggers, max_files triggers.
"""

import pytest
import threading
import time
from pathlib import Path
from typing import List
from unittest.mock import Mock

from opencode_monitor.analytics.indexer.batch_accumulator import (
    AccumulatorConfig,
    FileBatchAccumulator,
)


@pytest.fixture
def mock_callback() -> Mock:
    """Create a mock callback for batch ready events."""
    return Mock()


@pytest.fixture
def default_config() -> AccumulatorConfig:
    """Default config with fast timer for tests."""
    return AccumulatorConfig(window_ms=50, max_files=10, flush_on_stop=True)


@pytest.fixture
def accumulator(
    default_config: AccumulatorConfig, mock_callback: Mock
) -> FileBatchAccumulator:
    """Create accumulator with default config and mock callback."""
    acc = FileBatchAccumulator(default_config, mock_callback)
    yield acc
    acc.stop()


class TestAddSingleFile:
    """Tests for adding a single file."""

    def test_add_single_file(
        self, accumulator: FileBatchAccumulator, mock_callback: Mock
    ):
        """Adding a single file should accumulate it without immediate flush."""
        file_path = Path("/tmp/test/file1.json")

        accumulator.add(file_path)

        # Give a tiny bit of time but not enough for timer
        time.sleep(0.01)

        # Should not have flushed yet (timer is 50ms, max_files is 10)
        mock_callback.assert_not_called()

        # Stats should show 1 file accumulated
        stats = accumulator.get_stats()
        assert stats.files_accumulated == 1


class TestBatchTriggerByMaxFiles:
    """Tests for batch trigger when max_files is reached."""

    def test_batch_trigger_by_max_files(self, mock_callback: Mock):
        """Batch should trigger immediately when max_files is reached."""
        config = AccumulatorConfig(window_ms=5000, max_files=5, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        try:
            # Add exactly max_files
            files = [Path(f"/tmp/test/file{i}.json") for i in range(5)]
            for f in files:
                acc.add(f)

            # Give callback thread time to execute
            time.sleep(0.05)

            # Should have triggered batch
            mock_callback.assert_called_once()
            batch = mock_callback.call_args[0][0]
            assert len(batch) == 5
            assert set(batch) == set(files)

            # Stats should reflect max_files trigger
            stats = acc.get_stats()
            assert stats.batches_sent == 1
            assert stats.batches_by_max_files == 1
            assert stats.batches_by_timer == 0
        finally:
            acc.stop()


class TestBatchTriggerByTimer:
    """Tests for batch trigger after window_ms expires."""

    def test_batch_trigger_by_timer(self, mock_callback: Mock):
        """Batch should trigger after window_ms even with fewer than max_files."""
        config = AccumulatorConfig(window_ms=30, max_files=100, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        try:
            # Add fewer than max_files
            files = [Path(f"/tmp/test/file{i}.json") for i in range(3)]
            for f in files:
                acc.add(f)

            # Wait for timer (30ms + buffer)
            time.sleep(0.1)

            # Should have triggered batch by timer
            mock_callback.assert_called_once()
            batch = mock_callback.call_args[0][0]
            assert len(batch) == 3

            # Stats should reflect timer trigger
            stats = acc.get_stats()
            assert stats.batches_sent == 1
            assert stats.batches_by_timer == 1
            assert stats.batches_by_max_files == 0
        finally:
            acc.stop()


class TestDeduplication:
    """Tests for file deduplication."""

    def test_deduplication(self, mock_callback: Mock):
        """Duplicate files should be deduplicated."""
        config = AccumulatorConfig(window_ms=5000, max_files=10, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        try:
            file_path = Path("/tmp/test/same_file.json")

            # Add same file multiple times
            acc.add(file_path)
            acc.add(file_path)
            acc.add(file_path)

            # Force flush to see result
            flushed = acc.force_flush()

            # Should only have 1 unique file
            assert flushed == 1

            # Wait for callback
            time.sleep(0.05)

            mock_callback.assert_called_once()
            batch = mock_callback.call_args[0][0]
            assert len(batch) == 1
            assert batch[0] == file_path

            # Stats should show deduplication
            stats = acc.get_stats()
            assert stats.files_accumulated == 1
            assert stats.files_deduplicated == 2
        finally:
            acc.stop()


class TestForceFlush:
    """Tests for force_flush method."""

    def test_force_flush(self, mock_callback: Mock):
        """force_flush should immediately flush pending files."""
        config = AccumulatorConfig(window_ms=5000, max_files=100, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        try:
            files = [Path(f"/tmp/test/file{i}.json") for i in range(5)]
            for f in files:
                acc.add(f)

            # Force flush
            count = acc.force_flush()

            assert count == 5

            # Wait for callback
            time.sleep(0.05)

            mock_callback.assert_called_once()
            batch = mock_callback.call_args[0][0]
            assert len(batch) == 5
        finally:
            acc.stop()

    def test_force_flush_empty(
        self, accumulator: FileBatchAccumulator, mock_callback: Mock
    ):
        """force_flush on empty accumulator should return 0 and not call callback."""
        count = accumulator.force_flush()

        assert count == 0
        time.sleep(0.02)
        mock_callback.assert_not_called()


class TestAddMany:
    """Tests for add_many method."""

    def test_add_many(self, mock_callback: Mock):
        """add_many should add all files and trigger if needed."""
        config = AccumulatorConfig(window_ms=5000, max_files=5, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        try:
            files = [Path(f"/tmp/test/file{i}.json") for i in range(5)]

            acc.add_many(files)

            # Should trigger immediately since max_files reached
            time.sleep(0.05)

            mock_callback.assert_called_once()
            batch = mock_callback.call_args[0][0]
            assert len(batch) == 5
            assert set(batch) == set(files)

            stats = acc.get_stats()
            assert stats.files_accumulated == 5
        finally:
            acc.stop()

    def test_add_many_with_duplicates(self, mock_callback: Mock):
        """add_many should deduplicate files."""
        config = AccumulatorConfig(window_ms=5000, max_files=100, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        try:
            file1 = Path("/tmp/test/file1.json")
            file2 = Path("/tmp/test/file2.json")
            files = [file1, file2, file1, file2, file1]  # 3 duplicates

            acc.add_many(files)

            count = acc.force_flush()
            assert count == 2  # Only unique files

            stats = acc.get_stats()
            assert stats.files_accumulated == 2
            assert stats.files_deduplicated == 3
        finally:
            acc.stop()


class TestThreadSafety:
    """Tests for thread safety."""

    def test_thread_safety(self, mock_callback: Mock):
        """Concurrent adds from multiple threads should be safe."""
        config = AccumulatorConfig(window_ms=5000, max_files=1000, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        try:
            num_threads = 10
            files_per_thread = 50
            errors: List[Exception] = []

            def add_files(thread_id: int) -> None:
                try:
                    for i in range(files_per_thread):
                        # Each thread adds unique files
                        acc.add(Path(f"/tmp/test/thread{thread_id}_file{i}.json"))
                except Exception as e:
                    errors.append(e)

            threads = [
                threading.Thread(target=add_files, args=(i,))
                for i in range(num_threads)
            ]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # No errors should have occurred
            assert len(errors) == 0

            # Force flush to check count
            count = acc.force_flush()

            # All unique files should be accumulated
            expected = num_threads * files_per_thread
            assert count == expected

            stats = acc.get_stats()
            assert stats.files_accumulated == expected
            assert stats.files_deduplicated == 0
        finally:
            acc.stop()

    def test_thread_safety_with_duplicates(self, mock_callback: Mock):
        """Concurrent adds of same files should deduplicate correctly."""
        config = AccumulatorConfig(window_ms=5000, max_files=1000, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        try:
            num_threads = 5
            shared_files = [Path(f"/tmp/test/shared{i}.json") for i in range(10)]

            def add_shared_files() -> None:
                for f in shared_files:
                    acc.add(f)

            threads = [
                threading.Thread(target=add_shared_files) for _ in range(num_threads)
            ]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            count = acc.force_flush()

            # Only unique files should remain
            assert count == 10

            stats = acc.get_stats()
            assert stats.files_accumulated == 10
            # Each file added by 5 threads, 4 duplicates each = 40 total
            assert stats.files_deduplicated == 40
        finally:
            acc.stop()


class TestStopFlushes:
    """Tests for stop() behavior."""

    def test_stop_flushes_pending(self, mock_callback: Mock):
        """stop() should flush pending files when flush_on_stop=True."""
        config = AccumulatorConfig(window_ms=5000, max_files=100, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        files = [Path(f"/tmp/test/file{i}.json") for i in range(3)]
        for f in files:
            acc.add(f)

        # Stop should flush
        acc.stop()

        # Wait for callback
        time.sleep(0.05)

        mock_callback.assert_called_once()
        batch = mock_callback.call_args[0][0]
        assert len(batch) == 3

    def test_stop_no_flush_when_disabled(self, mock_callback: Mock):
        """stop() should NOT flush when flush_on_stop=False."""
        config = AccumulatorConfig(window_ms=5000, max_files=100, flush_on_stop=False)
        acc = FileBatchAccumulator(config, mock_callback)

        files = [Path(f"/tmp/test/file{i}.json") for i in range(3)]
        for f in files:
            acc.add(f)

        acc.stop()

        time.sleep(0.05)

        # Should NOT have called callback
        mock_callback.assert_not_called()


class TestStatsTracking:
    """Tests for statistics tracking."""

    def test_stats_tracking(self, mock_callback: Mock):
        """Statistics should accurately track all operations."""
        config = AccumulatorConfig(window_ms=30, max_files=5, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        try:
            # First batch: trigger by max_files
            for i in range(5):
                acc.add(Path(f"/tmp/test/batch1_file{i}.json"))
            time.sleep(0.05)

            # Second batch: trigger by timer
            for i in range(2):
                acc.add(Path(f"/tmp/test/batch2_file{i}.json"))
            time.sleep(0.1)  # Wait for timer

            # Add some duplicates
            acc.add(Path("/tmp/test/dup.json"))
            acc.add(Path("/tmp/test/dup.json"))
            acc.add(Path("/tmp/test/dup.json"))
            acc.force_flush()

            time.sleep(0.05)

            stats = acc.get_stats()

            # 5 + 2 + 1 unique = 8 files
            assert stats.files_accumulated == 8
            assert stats.files_deduplicated == 2
            assert stats.batches_sent == 3
            assert stats.batches_by_max_files == 1
            assert stats.batches_by_timer == 1
            # force_flush counts as neither timer nor max_files
        finally:
            acc.stop()

    def test_stats_initial_values(self, accumulator: FileBatchAccumulator):
        """Initial stats should be all zeros."""
        stats = accumulator.get_stats()

        assert stats.batches_sent == 0
        assert stats.files_accumulated == 0
        assert stats.files_deduplicated == 0
        assert stats.batches_by_timer == 0
        assert stats.batches_by_max_files == 0


class TestCallbackReceivesPaths:
    """Tests for callback receiving correct paths."""

    def test_callback_receives_paths(self, mock_callback: Mock):
        """Callback should receive list of Path objects."""
        config = AccumulatorConfig(window_ms=5000, max_files=3, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        try:
            files = [
                Path("/tmp/test/a.json"),
                Path("/tmp/test/b.json"),
                Path("/tmp/test/c.json"),
            ]

            for f in files:
                acc.add(f)

            time.sleep(0.05)

            mock_callback.assert_called_once()
            batch = mock_callback.call_args[0][0]

            # Should be a list
            assert isinstance(batch, list)

            # All items should be Path objects
            for item in batch:
                assert isinstance(item, Path)

            # Should contain all files
            assert set(batch) == set(files)
        finally:
            acc.stop()

    def test_callback_not_blocking(self, mock_callback: Mock):
        """Callback should execute in separate thread (non-blocking)."""
        config = AccumulatorConfig(window_ms=5000, max_files=2, flush_on_stop=True)

        callback_thread_ids: List[int] = []
        main_thread_id = threading.current_thread().ident or 0

        def slow_callback(files: List[Path]) -> None:
            tid = threading.current_thread().ident
            if tid is not None:
                callback_thread_ids.append(tid)
            time.sleep(0.2)  # Simulate slow processing

        acc = FileBatchAccumulator(config, slow_callback)

        try:
            start = time.time()

            # Add files to trigger batch
            acc.add(Path("/tmp/test/file1.json"))
            acc.add(Path("/tmp/test/file2.json"))

            elapsed = time.time() - start

            # add() should return quickly (not wait for slow callback)
            assert elapsed < 0.1

            # Wait for callback to complete
            time.sleep(0.3)

            # Callback should have run in different thread
            assert len(callback_thread_ids) == 1
            assert callback_thread_ids[0] != main_thread_id
        finally:
            acc.stop()


class TestEdgeCases:
    """Tests for edge cases."""

    def test_multiple_force_flush(self, mock_callback: Mock):
        """Multiple force_flush calls should work correctly."""
        config = AccumulatorConfig(window_ms=5000, max_files=100, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        try:
            acc.add(Path("/tmp/test/file1.json"))
            count1 = acc.force_flush()

            acc.add(Path("/tmp/test/file2.json"))
            count2 = acc.force_flush()

            count3 = acc.force_flush()  # Empty

            assert count1 == 1
            assert count2 == 1
            assert count3 == 0

            time.sleep(0.05)

            assert mock_callback.call_count == 2
        finally:
            acc.stop()

    def test_stop_idempotent(self, mock_callback: Mock):
        """Calling stop() multiple times should be safe."""
        config = AccumulatorConfig(window_ms=5000, max_files=100, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        acc.add(Path("/tmp/test/file1.json"))

        # Multiple stops should not raise
        acc.stop()
        acc.stop()
        acc.stop()

        time.sleep(0.05)

        # Should only flush once
        assert mock_callback.call_count == 1

    def test_add_after_stop(self, mock_callback: Mock):
        """Adding files after stop should be handled gracefully."""
        config = AccumulatorConfig(window_ms=5000, max_files=100, flush_on_stop=True)
        acc = FileBatchAccumulator(config, mock_callback)

        acc.stop()

        # Should not raise, but file won't be processed
        acc.add(Path("/tmp/test/file1.json"))

        stats = acc.get_stats()
        assert stats.files_accumulated == 0
