"""
Integration tests for cross-section visibility and navigation.

Consolidated tests verify:
- Navigation updates visible section correctly
- Data persists across section switches
- API client isolation works properly
"""

import pytest

from ..conftest import (
    SECTION_MONITORING,
    SECTION_ANALYTICS,
)
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


class TestSectionVisibility:
    """Consolidated tests for section visibility and navigation."""

    def test_navigation_and_data_persistence(self, dashboard_window, qtbot, click_nav):
        """
        Navigation shows correct section and data persists across switches.

        Verifies:
        - Monitoring visible by default (index 0)
        - Analytics visible after navigation
        - Data persists when navigating away and back
        """
        # 1. Initial state: Monitoring visible by default
        assert dashboard_window._pages.currentIndex() == SECTION_MONITORING
        assert dashboard_window._monitoring.isVisible()

        # 2. Set monitoring data before navigating away
        data = MockAPIResponses.realistic_monitoring()
        dashboard_window._signals.monitoring_updated.emit(data)
        qtbot.wait(50)

        # 3. Navigate to Analytics - verify section changes
        click_nav(dashboard_window, SECTION_ANALYTICS)
        assert dashboard_window._pages.currentIndex() == SECTION_ANALYTICS

        # 4. Navigate back to Monitoring - verify data persisted
        click_nav(dashboard_window, SECTION_MONITORING)
        assert dashboard_window._pages.currentIndex() == SECTION_MONITORING

        metrics = dashboard_window._monitoring._metrics
        assert metrics._cards["agents"]._value_label.text() == "3"

    def test_api_client_isolation(self, patched_api_client):
        """
        Mock API client is properly isolated and tracks calls.

        Verifies:
        - Mock is available by default
        - All API calls are logged with arguments
        - Availability can be toggled
        """
        # 1. Verify mock is available
        assert patched_api_client.is_available

        # 2. Make API calls and verify tracking
        patched_api_client.get_stats()
        patched_api_client.get_global_stats(days=7)
        patched_api_client.get_session_summary(session_id="test-123")

        calls = patched_api_client.get_call_log()
        assert len(calls) == 3
        assert calls[0] == ("get_stats", {})
        assert calls[1] == ("get_global_stats", {"days": 7})
        assert calls[2] == ("get_session_summary", {"session_id": "test-123"})

        # 3. Verify availability toggle works
        patched_api_client.set_available(False)
        assert not patched_api_client.is_available

        # Mock still returns responses when unavailable
        stats = patched_api_client.get_stats()
        assert stats is not None
