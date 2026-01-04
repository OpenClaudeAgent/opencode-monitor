"""
Integration tests for navigation robustness.

Tests verify:
- Signal robustness under various stress conditions
- Fixture isolation guarantees fresh window each test
"""

import pytest

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING
from ..fixtures import MockAPIResponses, empty_monitoring

pytestmark = pytest.mark.integration


class TestNavigationRobustness:
    """Focused robustness tests for signals under stress."""

    def test_burst_signal_emissions(self, dashboard_window, qtbot):
        """Dashboard survives 20 rapid signal emissions without crashing."""
        monitoring_data = MockAPIResponses.realistic_monitoring()

        for _ in range(20):
            dashboard_window._signals.monitoring_updated.emit(monitoring_data)
            qtbot.wait(10)

        assert dashboard_window.isVisible()

    def test_alternating_data_emissions(self, dashboard_window, qtbot):
        """Dashboard handles alternating empty/full data without crashing."""
        monitoring_data = MockAPIResponses.realistic_monitoring()
        empty_data = empty_monitoring()

        for _ in range(10):
            dashboard_window._signals.monitoring_updated.emit(empty_data)
            qtbot.wait(30)
            dashboard_window._signals.monitoring_updated.emit(monitoring_data)
            qtbot.wait(30)

        assert dashboard_window.isVisible()

    def test_rapid_tab_switching(self, dashboard_window, qtbot, click_nav, click_tab):
        """Dashboard survives rapid tab switching during data updates."""
        tracing_data = MockAPIResponses.realistic_tracing()

        click_nav(dashboard_window, SECTION_TRACING)
        dashboard_window._signals.tracing_updated.emit(tracing_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        detail = dashboard_window._tracing._detail_panel
        for i in range(6):
            click_tab(detail._tabs, i)
            dashboard_window._signals.tracing_updated.emit(tracing_data)
            qtbot.wait(20)

        assert dashboard_window.isVisible()


class TestFixtureIsolation:
    """Verify fixture provides isolated window instances."""

    def test_fixture_provides_isolated_window(self, dashboard_window, qtbot):
        """Each test receives a fresh, isolated window instance."""
        # No stale markers
        assert getattr(dashboard_window, "_test_marker", None) is None

        # Initial state is default
        metrics = dashboard_window._monitoring._metrics
        initial_value = metrics._cards["agents"]._value_label.text()
        assert initial_value in ("0", "-", "")

        # Can write to fresh instance
        dashboard_window._test_marker = "isolation_verified"
        assert dashboard_window._test_marker == "isolation_verified"
        assert dashboard_window.isVisible()
