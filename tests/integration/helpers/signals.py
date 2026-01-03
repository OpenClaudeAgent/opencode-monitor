"""
Signal handling helpers for integration tests.

Provides utilities for waiting on Qt signals with proper timeout handling.
"""

import pytest


@pytest.fixture
def wait_for_signal():
    """Fixture to wait for Qt signals with timeout."""

    def waiter(qtbot, signal, timeout: int = 1000) -> bool:
        try:
            with qtbot.waitSignal(signal, timeout=timeout):
                return True
        except TimeoutError:
            # Signal was not emitted within timeout
            return False
        # Let other exceptions propagate for debugging

    return waiter
