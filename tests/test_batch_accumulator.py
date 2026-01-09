"""
Tests for FileBatchAccumulator - US-2: Micro-batch accumulator.

Covers: thread safety, deduplication, timer triggers, max_files triggers.
"""

import threading
import time
from pathlib import Path
from typing import List
from unittest.mock import Mock

import pytest

from opencode_monitor.analytics.indexer.batch_accumulator import (
    AccumulatorConfig,
    AccumulatorStats,
    FileBatchAccumulator,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_callback() -> Mock:
    """Mock callback for batch ready events."""
    return Mock()


@pytest.fixture
def fast_config() -> AccumulatorConfig:
    """Fast config for tests (short timer, small batch)."""
    return AccumulatorConfig(window_ms=50, max_files=10, flush_on_stop=True)


@pytest.fixture
def accumulator(fast_config: AccumulatorConfig, mock_callback: Mock):
    """Accumulator with auto-cleanup."""
    acc = FileBatchAccumulator(fast_config, mock_callback)
    yield acc
    acc.stop()


def wait_for_callback(
    mock_callback: Mock, expected_calls: int = 1, timeout: float = 0.1
):
    """Helper: wait for callback to be called expected number of times."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if mock_callback.call_count >= expected_calls:
            return
        time.sleep(0.01)


def make_files(prefix: str, count: int) -> List[Path]:
    """Helper: create list of test file paths."""
    return [Path(f"/tmp/test/{prefix}_{i}.json") for i in range(count)]


# =============================================================================
# Basic Operations
# =============================================================================


class TestBasicOperations:
    """Tests for add, add_many, force_flush, stop."""

    def test_add_single_file_accumulates(
        self, accumulator: FileBatchAccumulator, mock_callback: Mock
    ):
        """Adding a single file should accumulate without immediate flush."""
        accumulator.add(Path("/tmp/test/file1.json"))
        time.sleep(0.01)  # Less than window_ms

        mock_callback.assert_not_called()
        assert accumulator.get_stats().files_accumulated == 1

    def test_add_many_files(self, mock_callback: Mock):
        """add_many should add all files and trigger if max_files reached."""
        acc = FileBatchAccumulator(
            AccumulatorConfig(window_ms=5000, max_files=5), mock_callback
        )

        files = make_files("batch", 5)
        acc.add_many(files)
        wait_for_callback(mock_callback)

        assert mock_callback.call_count == 1
        assert set(mock_callback.call_args[0][0]) == set(files)
        acc.stop()

    def test_add_many_deduplicates(self, mock_callback: Mock):
        """add_many should deduplicate files."""
        acc = FileBatchAccumulator(
            AccumulatorConfig(window_ms=5000, max_files=100), mock_callback
        )

        f1, f2 = Path("/tmp/a.json"), Path("/tmp/b.json")
        acc.add_many([f1, f2, f1, f2, f1])  # 3 duplicates

        assert acc.force_flush() == 2
        stats = acc.get_stats()
        assert stats.files_accumulated == 2
        assert stats.files_deduplicated == 3
        acc.stop()

    def test_force_flush_returns_count(self, mock_callback: Mock):
        """force_flush should return count and trigger callback."""
        acc = FileBatchAccumulator(
            AccumulatorConfig(window_ms=5000, max_files=100), mock_callback
        )

        for f in make_files("flush", 5):
            acc.add(f)

        assert acc.force_flush() == 5
        assert acc.force_flush() == 0  # Already flushed

        wait_for_callback(mock_callback)
        assert mock_callback.call_count == 1
        acc.stop()

    def test_stop_flushes_pending_when_enabled(self, mock_callback: Mock):
        """stop() should flush pending files when flush_on_stop=True."""
        acc = FileBatchAccumulator(AccumulatorConfig(flush_on_stop=True), mock_callback)
        acc.add_many(make_files("stop", 3))
        acc.stop()

        wait_for_callback(mock_callback)
        assert len(mock_callback.call_args[0][0]) == 3

    def test_stop_no_flush_when_disabled(self, mock_callback: Mock):
        """stop() should NOT flush when flush_on_stop=False."""
        acc = FileBatchAccumulator(
            AccumulatorConfig(flush_on_stop=False), mock_callback
        )
        acc.add_many(make_files("noflu", 3))
        acc.stop()

        time.sleep(0.05)
        mock_callback.assert_not_called()


# =============================================================================
# Batch Triggers
# =============================================================================


class TestBatchTriggers:
    """Tests for timer and max_files triggers."""

    def test_trigger_by_max_files(self, mock_callback: Mock):
        """Batch triggers immediately when max_files reached."""
        acc = FileBatchAccumulator(
            AccumulatorConfig(window_ms=5000, max_files=5), mock_callback
        )

        acc.add_many(make_files("max", 5))
        wait_for_callback(mock_callback)

        stats = acc.get_stats()
        assert stats.batches_sent == 1
        assert stats.batches_by_max_files == 1
        assert stats.batches_by_timer == 0
        acc.stop()

    def test_trigger_by_timer(self, mock_callback: Mock):
        """Batch triggers after window_ms expires."""
        acc = FileBatchAccumulator(
            AccumulatorConfig(window_ms=30, max_files=100), mock_callback
        )

        acc.add_many(make_files("timer", 3))
        time.sleep(0.1)  # Wait for timer

        stats = acc.get_stats()
        assert stats.batches_sent == 1
        assert stats.batches_by_timer == 1
        assert stats.batches_by_max_files == 0
        acc.stop()


# =============================================================================
# Deduplication
# =============================================================================


class TestDeduplication:
    """Tests for file deduplication."""

    def test_duplicate_files_ignored(self, mock_callback: Mock):
        """Same file added multiple times should be deduplicated."""
        acc = FileBatchAccumulator(
            AccumulatorConfig(window_ms=5000, max_files=10), mock_callback
        )

        same_file = Path("/tmp/same.json")
        acc.add(same_file)
        acc.add(same_file)
        acc.add(same_file)

        assert acc.force_flush() == 1
        wait_for_callback(mock_callback)

        assert len(mock_callback.call_args[0][0]) == 1
        stats = acc.get_stats()
        assert stats.files_accumulated == 1
        assert stats.files_deduplicated == 2
        acc.stop()


# =============================================================================
# Thread Safety
# =============================================================================


class TestThreadSafety:
    """Tests for concurrent access."""

    def test_concurrent_adds_unique_files(self, mock_callback: Mock):
        """Concurrent adds from multiple threads should be safe."""
        acc = FileBatchAccumulator(
            AccumulatorConfig(window_ms=5000, max_files=1000), mock_callback
        )

        num_threads, files_per_thread = 10, 50
        errors: List[Exception] = []

        def add_files(thread_id: int):
            try:
                for i in range(files_per_thread):
                    acc.add(Path(f"/tmp/t{thread_id}_f{i}.json"))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_files, args=(i,)) for i in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert acc.force_flush() == num_threads * files_per_thread
        acc.stop()

    def test_concurrent_adds_same_files_deduplicate(self, mock_callback: Mock):
        """Concurrent adds of same files should deduplicate correctly."""
        acc = FileBatchAccumulator(
            AccumulatorConfig(window_ms=5000, max_files=1000), mock_callback
        )

        shared_files = make_files("shared", 10)
        num_threads = 5

        def add_shared():
            for f in shared_files:
                acc.add(f)

        threads = [threading.Thread(target=add_shared) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert acc.force_flush() == 10
        stats = acc.get_stats()
        assert stats.files_accumulated == 10
        assert (
            stats.files_deduplicated == 40
        )  # 10 files x 5 threads - 10 unique = 40 dupes
        acc.stop()

    def test_callback_runs_in_separate_thread(self, mock_callback: Mock):
        """Callback should not block the caller."""
        callback_thread_ids: List[int] = []
        main_thread_id = threading.current_thread().ident

        def slow_callback(files: List[Path]):
            tid = threading.current_thread().ident
            if tid is not None:
                callback_thread_ids.append(tid)
            time.sleep(0.2)

        acc = FileBatchAccumulator(
            AccumulatorConfig(window_ms=5000, max_files=2), slow_callback
        )

        start = time.time()
        acc.add_many(make_files("slow", 2))
        elapsed = time.time() - start

        assert elapsed < 0.1  # add() returns quickly
        time.sleep(0.3)
        assert callback_thread_ids[0] != main_thread_id
        acc.stop()


# =============================================================================
# Statistics
# =============================================================================


class TestStatistics:
    """Tests for stats tracking."""

    def test_initial_stats_are_zero(self, accumulator: FileBatchAccumulator):
        """Initial stats should all be zero."""
        stats = accumulator.get_stats()
        assert stats == AccumulatorStats()

    def test_stats_track_all_operations(self, mock_callback: Mock):
        """Stats should accurately track operations."""
        acc = FileBatchAccumulator(
            AccumulatorConfig(window_ms=30, max_files=5), mock_callback
        )

        # Batch 1: trigger by max_files
        acc.add_many(make_files("b1", 5))
        wait_for_callback(mock_callback, expected_calls=1)

        # Batch 2: trigger by timer
        acc.add_many(make_files("b2", 2))
        time.sleep(0.1)

        # Batch 3: force flush with duplicates
        dup = Path("/tmp/dup.json")
        acc.add(dup)
        acc.add(dup)
        acc.add(dup)
        acc.force_flush()

        wait_for_callback(mock_callback, expected_calls=3)

        stats = acc.get_stats()
        assert stats.files_accumulated == 8  # 5 + 2 + 1
        assert stats.files_deduplicated == 2
        assert stats.batches_sent == 3
        assert stats.batches_by_max_files == 1
        assert stats.batches_by_timer == 1
        acc.stop()


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_stop_is_idempotent(self, mock_callback: Mock):
        """Calling stop() multiple times should be safe."""
        acc = FileBatchAccumulator(AccumulatorConfig(), mock_callback)
        acc.add(Path("/tmp/file.json"))

        acc.stop()
        acc.stop()
        acc.stop()

        wait_for_callback(mock_callback)
        assert mock_callback.call_count == 1

    def test_add_after_stop_is_ignored(self, mock_callback: Mock):
        """Adding files after stop should be handled gracefully."""
        acc = FileBatchAccumulator(AccumulatorConfig(), mock_callback)
        acc.stop()

        acc.add(Path("/tmp/file.json"))

        assert acc.get_stats().files_accumulated == 0

    def test_callback_receives_path_objects(self, mock_callback: Mock):
        """Callback should receive list of Path objects."""
        acc = FileBatchAccumulator(
            AccumulatorConfig(window_ms=5000, max_files=3), mock_callback
        )

        files = make_files("path", 3)
        acc.add_many(files)
        wait_for_callback(mock_callback)

        batch = mock_callback.call_args[0][0]
        assert isinstance(batch, list)
        assert all(isinstance(p, Path) for p in batch)
        assert set(batch) == set(files)
        acc.stop()
