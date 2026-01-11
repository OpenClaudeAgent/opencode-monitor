"""
Tests for Dashboard adaptive polling behavior.

Tests cover:
- Monitoring data refreshes every cycle (real-time requirement)
- Secondary data (security, analytics, tracing) refreshes every 5th cycle
- Health check uses cache to reduce API calls
"""

import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# =============================================================================
# Tests for Dashboard adaptive polling
# =============================================================================


class TestDashboardPolling:
    """Tests for DashboardWindow adaptive polling behavior."""

    def test_monitoring_refreshes_every_cycle(self, qapp):
        """Monitoring data fetch is called on every refresh cycle."""
        import threading
        from opencode_monitor.dashboard.window.main import DashboardWindow

        # Track fetch method calls
        monitoring_calls = []

        def mock_monitoring():
            monitoring_calls.append(threading.current_thread().name)

        # Create window with mocked fetch methods
        with patch.object(
            DashboardWindow, "_fetch_monitoring_data", side_effect=mock_monitoring
        ):
            with patch.object(DashboardWindow, "_fetch_security_data"):
                with patch.object(DashboardWindow, "_fetch_analytics_data"):
                    with patch.object(DashboardWindow, "_fetch_tracing_data"):
                        window = DashboardWindow()

                        # Reset call count after initial load
                        initial_calls = len(monitoring_calls)
                        monitoring_calls.clear()

                        # Manually trigger refresh 6 times
                        for _ in range(6):
                            window._refresh_all_data()
                            # Wait for threads to complete
                            time.sleep(0.01)

                        # All 6 calls should have triggered monitoring fetch
                        assert len(monitoring_calls) == 6

                        window.close()

    def test_secondary_data_refreshes_every_fifth_cycle(self, qapp):
        """Secondary data (security, analytics, tracing) refreshes every 5th cycle."""
        import threading
        from opencode_monitor.dashboard.window.main import DashboardWindow

        # Track fetch method calls
        security_calls = []
        analytics_calls = []

        def mock_security():
            security_calls.append(threading.current_thread().name)

        def mock_analytics():
            analytics_calls.append(threading.current_thread().name)

        with patch.object(DashboardWindow, "_fetch_monitoring_data"):
            with patch.object(
                DashboardWindow, "_fetch_security_data", side_effect=mock_security
            ):
                with patch.object(
                    DashboardWindow, "_fetch_analytics_data", side_effect=mock_analytics
                ):
                    with patch.object(DashboardWindow, "_fetch_tracing_data"):
                        window = DashboardWindow()

                        # Reset counter to 0 for clean test
                        window._refresh_count = 0
                        security_calls.clear()
                        analytics_calls.clear()

                        # Trigger refresh 10 times (should trigger secondary at 0 and 5)
                        for _ in range(10):
                            window._refresh_all_data()
                            # Wait for threads to complete
                            time.sleep(0.01)

                        # Secondary is called at _refresh_count 0, 5 (2 times in 10 cycles)
                        # Verify SECONDARY_REFRESH_DIVISOR is 5
                        assert window.SECONDARY_REFRESH_DIVISOR == 5

                        # Verify secondary data was fetched 2 times
                        assert len(security_calls) == 2
                        assert len(analytics_calls) == 2

                        window.close()

    def test_refresh_count_increments(self, qapp):
        """_refresh_count increments after each refresh cycle."""
        from opencode_monitor.dashboard.window.main import DashboardWindow

        with patch.object(DashboardWindow, "_fetch_monitoring_data"):
            with patch.object(DashboardWindow, "_fetch_security_data"):
                with patch.object(DashboardWindow, "_fetch_analytics_data"):
                    with patch.object(DashboardWindow, "_fetch_tracing_data"):
                        window = DashboardWindow()

                        # Reset counter
                        window._refresh_count = 0

                        # Call refresh 3 times
                        window._refresh_all_data()
                        # Wait for threads to complete
                        time.sleep(0.01)
                        assert window._refresh_count == 1

                        window._refresh_all_data()
                        time.sleep(0.01)
                        assert window._refresh_count == 2

                        window._refresh_all_data()
                        time.sleep(0.01)
                        assert window._refresh_count == 3

                        window.close()


# =============================================================================
# Tests for API client health check cache
# =============================================================================


class TestHealthCheckCache:
    """Tests for AnalyticsAPIClient health check caching."""

    def test_health_check_uses_cache(self):
        """is_available uses cached result within HEALTH_CHECK_CACHE_DURATION."""
        from opencode_monitor.api.client import (
            AnalyticsAPIClient,
            HEALTH_CHECK_CACHE_DURATION,
        )

        client = AnalyticsAPIClient()

        with patch.object(client, "health_check") as mock_health_check:
            mock_health_check.return_value = True

            # First call - should call health_check (cache empty)
            result1 = client.is_available
            assert result1 is True
            assert mock_health_check.call_count == 1

            # Simulate that health_check set these values
            client._available = True
            client._last_health_check = time.time()

            # Second call immediately - should use cache (not call health_check again)
            result2 = client.is_available
            assert result2 is True
            assert mock_health_check.call_count == 1  # Still 1, cached

            # Third call immediately - still cached
            result3 = client.is_available
            assert result3 is True
            assert mock_health_check.call_count == 1  # Still 1, cached

    def test_health_check_cache_expires(self):
        """is_available makes new request after cache expires."""
        from opencode_monitor.api.client import (
            AnalyticsAPIClient,
            HEALTH_CHECK_CACHE_DURATION,
        )

        client = AnalyticsAPIClient()

        with patch.object(client, "_request") as mock_request:
            mock_request.return_value = {"status": "ok"}

            # First call
            client.is_available
            assert mock_request.call_count == 1

            # Simulate cache expiration by setting last check in the past
            client._last_health_check = time.time() - HEALTH_CHECK_CACHE_DURATION - 1

            # Second call after expiration - should make new request
            client.is_available
            assert mock_request.call_count == 2

    def test_health_check_cache_duration_is_5_seconds(self):
        """Verify HEALTH_CHECK_CACHE_DURATION is 5 seconds as specified."""
        from opencode_monitor.api.client import HEALTH_CHECK_CACHE_DURATION

        assert HEALTH_CHECK_CACHE_DURATION == 5

    def test_health_check_updates_timestamp(self):
        """health_check updates _last_health_check timestamp."""
        from opencode_monitor.api.client import AnalyticsAPIClient

        client = AnalyticsAPIClient()

        with patch.object(client, "_request") as mock_request:
            mock_request.return_value = {"status": "ok"}

            before = time.time()
            client.health_check()
            after = time.time()

            assert before <= client._last_health_check <= after
