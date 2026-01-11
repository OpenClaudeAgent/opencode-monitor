"""
Examples of timing tests without fragile time.sleep patches.

Demonstrates:
- Using freezegun for deterministic time-based tests
- Using threading.Barrier for thread synchronization
- Using threading.Event for completion signals
"""

import threading
import time
from datetime import datetime, timedelta

import pytest


class TestTimingWithFreezegun:
    def test_time_based_logic(self, freezer):
        start = datetime.now()

        freezer.move_to(start + timedelta(seconds=30))

        end = datetime.now()
        elapsed = (end - start).total_seconds()

        assert elapsed == 30.0

    def test_multiple_time_jumps(self, freezer):
        results = []

        for i in range(5):
            results.append(datetime.now())
            freezer.tick(delta=timedelta(seconds=10))

        assert (results[1] - results[0]).total_seconds() == 10.0
        assert (results[4] - results[0]).total_seconds() == 40.0


class TestThreadSynchronization:
    def test_concurrent_execution_with_barrier(self, thread_barrier):
        results = []

        def worker():
            thread_barrier.wait()
            results.append(threading.current_thread().name)

        thread = threading.Thread(target=worker, name="worker-1")
        thread.start()

        thread_barrier.wait()

        thread.join()

        assert len(results) == 1
        assert "worker-1" in results

    def test_completion_signal_with_event(self):
        completed = threading.Event()
        result = []

        def worker():
            time.sleep(0.1)
            result.append("done")
            completed.set()

        thread = threading.Thread(target=worker)
        thread.start()

        assert completed.wait(timeout=1.0)
        assert result == ["done"]
        thread.join()

    def test_multiple_workers_coordination(self):
        barrier = threading.Barrier(parties=3)
        results = []
        results_lock = threading.Lock()

        def worker(worker_id):
            barrier.wait()

            with results_lock:
                results.append(worker_id)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]

        for t in threads:
            t.start()

        barrier.wait()

        for t in threads:
            t.join()

        assert len(results) == 2
        assert set(results) == {0, 1}
