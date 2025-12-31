"""Tests for threading utilities."""

import pytest
import threading
import time
from unittest.mock import Mock

from opencode_monitor.utils.threading import run_in_background, start_background_task


class TestRunInBackground:
    """Tests for run_in_background decorator."""

    def test_function_runs_in_background(self):
        """Test that decorated function runs in a separate thread."""
        results = []
        main_thread_id = threading.current_thread().ident

        @run_in_background
        def capture_thread_id():
            results.append(threading.current_thread().ident)

        capture_thread_id()
        time.sleep(0.1)  # Give thread time to execute

        assert len(results) == 1
        assert results[0] != main_thread_id

    def test_function_is_daemon(self):
        """Test that background thread is a daemon thread."""
        thread_info = {}

        @run_in_background
        def capture_daemon_status():
            thread_info["daemon"] = threading.current_thread().daemon
            time.sleep(0.5)  # Keep thread alive for inspection

        capture_daemon_status()
        time.sleep(0.1)

        assert thread_info.get("daemon") is True

    def test_preserves_function_name(self):
        """Test that decorator preserves function metadata."""

        @run_in_background
        def my_special_function():
            pass

        assert my_special_function.__name__ == "my_special_function"

    def test_accepts_arguments(self):
        """Test that decorated function accepts arguments."""
        results = []

        @run_in_background
        def add_numbers(a, b):
            results.append(a + b)

        add_numbers(5, 3)
        time.sleep(0.1)

        assert len(results) == 1
        assert results[0] == 8

    def test_accepts_kwargs(self):
        """Test that decorated function accepts keyword arguments."""
        results = []

        @run_in_background
        def greet(name, greeting="Hello"):
            results.append(f"{greeting}, {name}!")

        greet("World", greeting="Hi")
        time.sleep(0.1)

        assert len(results) == 1
        assert results[0] == "Hi, World!"

    def test_returns_none(self):
        """Test that decorated function returns None immediately."""

        @run_in_background
        def slow_function():
            time.sleep(1)
            return "result"

        result = slow_function()
        assert result is None

    def test_multiple_calls_run_concurrently(self):
        """Test that multiple calls run in parallel."""
        results = []
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

        # Should complete faster than sequential execution
        assert elapsed < 0.4  # 3 * 0.1 = 0.3, add buffer
        assert sorted(results) == [1, 2, 3]


class TestStartBackgroundTask:
    """Tests for start_background_task function."""

    def test_starts_function_in_background(self):
        """Test that function runs in a separate thread."""
        results = []
        main_thread_id = threading.current_thread().ident

        def capture_thread_id():
            results.append(threading.current_thread().ident)

        start_background_task(capture_thread_id)
        time.sleep(0.1)

        assert len(results) == 1
        assert results[0] != main_thread_id

    def test_returns_thread_object(self):
        """Test that function returns the Thread object."""

        def dummy():
            pass

        thread = start_background_task(dummy)

        assert isinstance(thread, threading.Thread)

    def test_returned_thread_is_daemon(self):
        """Test that returned thread is a daemon."""

        def slow_function():
            time.sleep(1)

        thread = start_background_task(slow_function)

        assert thread.daemon is True

    def test_thread_is_started(self):
        """Test that thread is automatically started."""
        started = threading.Event()

        def signal_started():
            started.set()

        thread = start_background_task(signal_started)

        # Should be either running or finished
        assert started.wait(timeout=0.5) is True

    def test_thread_can_be_joined(self):
        """Test that returned thread can be joined."""
        results = []

        def append_value():
            time.sleep(0.05)
            results.append("done")

        thread = start_background_task(append_value)
        thread.join(timeout=1)

        assert len(results) == 1
        assert results[0] == "done"
