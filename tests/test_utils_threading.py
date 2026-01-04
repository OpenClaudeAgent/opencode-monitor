"""Tests for threading utilities."""

import threading
import time
from typing import Any

import pytest

from opencode_monitor.utils.threading import run_in_background, start_background_task


class TestRunInBackground:
    """Tests for run_in_background decorator."""

    def test_decorator_properties(self):
        """Test decorator creates daemon thread, runs in background, preserves metadata."""
        results: dict[str, Any] = {"thread_id": None, "daemon": None}
        main_thread_id = threading.current_thread().ident

        @run_in_background
        def my_special_function():
            results["thread_id"] = threading.current_thread().ident
            results["daemon"] = threading.current_thread().daemon
            time.sleep(0.2)

        # Verify decorator preserves function name
        assert my_special_function.__name__ == "my_special_function"

        # Verify returns None immediately (non-blocking)
        return_value = my_special_function()
        assert return_value == None

        time.sleep(0.1)

        # Verify runs in different thread
        assert results["thread_id"] != main_thread_id
        # Verify thread is daemon
        assert results["daemon"] == True

    @pytest.mark.parametrize(
        "args,kwargs,expected",
        [
            ((5, 3), {}, 8),
            ((10, 20), {}, 30),
            ((1,), {"b": 7}, 8),
            ((), {"a": 100, "b": 200}, 300),
        ],
        ids=["positional", "large-positional", "mixed", "kwargs-only"],
    )
    def test_with_arguments(self, args, kwargs, expected):
        """Test decorated function handles args and kwargs correctly."""
        results: list[int] = []

        @run_in_background
        def add_numbers(a, b):
            results.append(a + b)

        add_numbers(*args, **kwargs)
        time.sleep(0.1)

        assert len(results) == 1
        assert results[0] == expected

    def test_concurrent_execution(self):
        """Test multiple calls run in parallel, not sequentially."""
        results: list[int] = []
        start_time = time.time()

        @run_in_background
        def slow_append(value):
            time.sleep(0.1)
            results.append(value)

        # Start 3 background tasks
        slow_append(1)
        slow_append(2)
        slow_append(3)

        # Wait for all to complete
        time.sleep(0.3)
        elapsed = time.time() - start_time

        # Should complete faster than sequential (3 * 0.1 = 0.3s)
        assert elapsed < 0.4
        assert sorted(results) == [1, 2, 3]


class TestStartBackgroundTask:
    """Tests for start_background_task function."""

    def test_thread_properties_and_lifecycle(self):
        """Test returns started daemon Thread that can be joined."""
        results: dict[str, Any] = {"thread_id": None, "started": False}
        main_thread_id = threading.current_thread().ident
        started_event = threading.Event()

        def task_function():
            results["thread_id"] = threading.current_thread().ident
            results["started"] = True
            started_event.set()
            time.sleep(0.05)

        thread = start_background_task(task_function)

        # Verify returns Thread object
        assert type(thread).__name__ == "Thread"
        # Verify thread is daemon
        assert thread.daemon == True

        # Verify thread is started (wait for signal)
        wait_result = started_event.wait(timeout=0.5)
        assert wait_result == True

        # Verify can be joined
        thread.join(timeout=1)

        # Verify ran in different thread
        assert results["thread_id"] != main_thread_id
        assert results["started"] == True
