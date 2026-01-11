"""
Integration tests for navigation robustness.

Tests verify fixture isolation guarantees fresh window each test.
"""

import pytest

pytestmark = pytest.mark.integration


class TestNavigationRobustness:
    """Robustness tests for dashboard fixtures."""

    def test_fixture_provides_isolated_window(self, dashboard_window, qtbot):
        """Each test receives a fresh, isolated window instance.

        Verifies:
        - No stale markers from previous tests
        - Initial state is default (not polluted)
        - Fixture properly isolates test state
        """
        # Verify no marker from any previous test
        marker = getattr(dashboard_window, "_test_marker", None)
        assert marker is None, "Window has stale marker from previous test"

        # Verify initial metrics state is default (0, -, or empty)
        metric_cards = dashboard_window._monitoring._metric_cards
        initial_value = metric_cards["agents"]._value_label.text()
        assert initial_value in ("0", "-", ""), (
            f"Expected default value (0, -, empty), got: '{initial_value}'"
        )

        # Set marker to prove we have writable fresh instance
        dashboard_window._test_marker = "isolation_verified"
        assert dashboard_window._test_marker == "isolation_verified"

        # Verify window is properly initialized and visible
        assert dashboard_window.isVisible()
