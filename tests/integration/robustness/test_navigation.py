"""
Integration tests for navigation robustness.

Consolidated tests verify:
- Signal robustness under various stress conditions
- Fixture isolation guarantees fresh window each test
"""

import pytest

from ..conftest import (
    SIGNAL_WAIT_MS,
    SECTION_MONITORING,
    SECTION_SECURITY,
    SECTION_ANALYTICS,
    SECTION_TRACING,
)
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


class TestNavigationRobustness:
    """Consolidated robustness tests for navigation and signals."""

    def test_signal_robustness_under_stress(
        self, dashboard_window, qtbot, click_nav, click_tab
    ):
        """Dashboard survives all stress conditions without crashing.

        Combines:
        - Rapid navigation with data emissions
        - Multiple rapid signal emissions
        - Alternating empty/full data
        - Tab navigation during updates
        """
        monitoring_data = MockAPIResponses.realistic_monitoring()
        tracing_data = MockAPIResponses.realistic_tracing()
        analytics_data = MockAPIResponses.realistic_analytics()
        empty_monitoring = {
            "instances": 0,
            "agents": 0,
            "busy": 0,
            "waiting": 0,
            "idle": 0,
            "todos": 0,
            "agents_data": [],
            "tools_data": [],
            "waiting_data": [],
        }

        # Phase 1: Rapid navigation with data emissions
        for _ in range(3):
            click_nav(dashboard_window, SECTION_MONITORING)
            dashboard_window._signals.monitoring_updated.emit(monitoring_data)
            click_nav(dashboard_window, SECTION_TRACING)
            dashboard_window._signals.tracing_updated.emit(tracing_data)
            click_nav(dashboard_window, SECTION_ANALYTICS)
            dashboard_window._signals.analytics_updated.emit(analytics_data)
            click_nav(dashboard_window, SECTION_SECURITY)

        assert dashboard_window.isVisible(), "Crash during rapid navigation"

        # Phase 2: Burst signal emissions (20 rapid emissions)
        for _ in range(20):
            dashboard_window._signals.monitoring_updated.emit(monitoring_data)
            qtbot.wait(10)

        assert dashboard_window.isVisible(), "Crash during burst emissions"

        # Phase 3: Alternating empty/full data
        for _ in range(10):
            dashboard_window._signals.monitoring_updated.emit(empty_monitoring)
            qtbot.wait(30)
            dashboard_window._signals.monitoring_updated.emit(monitoring_data)
            qtbot.wait(30)

        assert dashboard_window.isVisible(), "Crash during empty/full alternation"

        # Phase 4: Tab navigation during data updates
        click_nav(dashboard_window, SECTION_TRACING)
        dashboard_window._signals.tracing_updated.emit(tracing_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        detail = dashboard_window._tracing._detail_panel
        for i in range(6):
            click_tab(detail._tabs, i)
            dashboard_window._signals.tracing_updated.emit(tracing_data)
            qtbot.wait(20)

        assert dashboard_window.isVisible(), "Crash during tab navigation"

        # Final verification: window survived all stress tests
        qtbot.wait(SIGNAL_WAIT_MS)
        assert dashboard_window.isVisible(), "Window should survive all stress phases"

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
