"""
Tests for DashboardWindow sync functionality.

Coverage target: SyncChecker and read-only dashboard architecture.

The dashboard now operates in read-only mode. The menubar handles all DB writes
and updates sync_meta table. The dashboard polls the API via SyncChecker
to detect when new data is available.
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from PyQt6.QtWidgets import QApplication


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for all tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_api_client():
    """Mock API client to avoid real API calls."""
    mock_client = MagicMock()
    mock_client.is_available = True
    mock_client.get_stats.return_value = {"sessions": 0}

    # Patch at the source module where it's imported from
    with patch("opencode_monitor.api.get_api_client") as mock_get:
        mock_get.return_value = mock_client
        yield mock_client


# =============================================================================
# SyncChecker Tests
# =============================================================================


class TestSyncChecker:
    """Tests for SyncChecker class."""

    def test_sync_checker_exists(self):
        """SyncChecker class is available."""
        from opencode_monitor.dashboard.window import SyncChecker

        assert SyncChecker is not None

    def test_sync_checker_has_poll_constants(self):
        """SyncChecker has poll interval constants."""
        from opencode_monitor.dashboard.window import SyncChecker

        assert hasattr(SyncChecker, "POLL_FAST_MS")
        assert hasattr(SyncChecker, "POLL_SLOW_MS")
        assert hasattr(SyncChecker, "IDLE_THRESHOLD_S")
        assert SyncChecker.POLL_FAST_MS == 2000
        assert SyncChecker.POLL_SLOW_MS == 5000
        assert SyncChecker.IDLE_THRESHOLD_S == 30

    def test_sync_checker_calls_callback_on_change(self, qapp, mock_api_client):
        """SyncChecker calls callback when session count changes."""
        from opencode_monitor.dashboard.window import SyncChecker

        callback_calls = []

        def callback():
            callback_calls.append(True)

        # Create checker with mock callback
        checker = SyncChecker(on_sync_detected=callback)

        # Simulate a session count change
        mock_api_client.get_stats.return_value = {"sessions": 10}

        # Manually trigger check (normally done by timer)
        checker._check()

        # Should have called callback
        assert len(callback_calls) == 1

        checker.stop()

    def test_sync_checker_stop_stops_timer(self, qapp, mock_api_client):
        """SyncChecker.stop() stops the internal timer."""
        from opencode_monitor.dashboard.window import SyncChecker

        checker = SyncChecker(on_sync_detected=lambda: None)

        # Timer should be active
        assert checker._timer.isActive()

        # Stop it
        checker.stop()

        # Timer should be stopped
        assert not checker._timer.isActive()


# =============================================================================
# DashboardWindow Read-Only Architecture Tests
# =============================================================================


class TestDashboardReadOnly:
    """Tests for read-only dashboard architecture."""

    def test_dashboard_no_sync_config(
        self,
        qapp,
        mock_api_client,
    ):
        """DashboardWindow no longer has sync_config attribute."""
        from opencode_monitor.dashboard.window import DashboardWindow

        with patch.object(DashboardWindow, "_start_refresh"):
            window = DashboardWindow()
            try:
                # Old attribute should not exist
                assert not hasattr(window, "_sync_config")
            finally:
                window.close()
                window.deleteLater()

    def test_dashboard_has_sync_checker(
        self,
        qapp,
        mock_api_client,
    ):
        """DashboardWindow has _sync_checker attribute after start."""
        from opencode_monitor.dashboard.window import DashboardWindow

        # Don't patch _start_refresh to allow sync_checker creation
        with patch.object(DashboardWindow, "_fetch_monitoring_data"):
            with patch.object(DashboardWindow, "_fetch_security_data"):
                with patch.object(DashboardWindow, "_fetch_analytics_data"):
                    with patch.object(DashboardWindow, "_fetch_tracing_data"):
                        window = DashboardWindow()
                        try:
                            assert hasattr(window, "_sync_checker")
                            assert window._sync_checker is not None
                        finally:
                            window.close()
                            window.deleteLater()

    def test_dashboard_no_sync_opencode_data_method(
        self,
        qapp,
        mock_api_client,
    ):
        """DashboardWindow no longer has _sync_opencode_data method."""
        from opencode_monitor.dashboard.window import DashboardWindow

        with patch.object(DashboardWindow, "_start_refresh"):
            window = DashboardWindow()
            try:
                # Old method should not exist
                assert not hasattr(window, "_sync_opencode_data")
            finally:
                window.close()
                window.deleteLater()

    def test_dashboard_close_stops_sync_checker(
        self,
        qapp,
        mock_api_client,
    ):
        """DashboardWindow.closeEvent stops the sync checker."""
        from opencode_monitor.dashboard.window import DashboardWindow

        with patch.object(DashboardWindow, "_fetch_monitoring_data"):
            with patch.object(DashboardWindow, "_fetch_security_data"):
                with patch.object(DashboardWindow, "_fetch_analytics_data"):
                    with patch.object(DashboardWindow, "_fetch_tracing_data"):
                        window = DashboardWindow()
                        sync_checker = window._sync_checker
                        assert sync_checker is not None

                        # Close the window
                        window.close()

                        # Sync checker timer should be stopped
                        assert not sync_checker._timer.isActive()

                        window.deleteLater()


# =============================================================================
# DataSignals Tests (Updated)
# =============================================================================


class TestDataSignals:
    """Tests for DataSignals class."""

    def test_data_signals_no_sync_completed(self):
        """DataSignals no longer has sync_completed signal."""
        from opencode_monitor.dashboard.window import DataSignals

        signals = DataSignals()
        # sync_completed was removed - dashboard uses SyncChecker now
        assert not hasattr(signals, "sync_completed")

    def test_data_signals_all_signals_exist(self):
        """DataSignals has all expected signals (without sync_completed)."""
        from opencode_monitor.dashboard.window import DataSignals

        signals = DataSignals()
        expected_signals = [
            "monitoring_updated",
            "security_updated",
            "analytics_updated",
            "tracing_updated",
        ]
        for signal_name in expected_signals:
            assert hasattr(signals, signal_name), f"Missing signal: {signal_name}"


# =============================================================================
# SyncChecker Integration Tests
# =============================================================================


class TestSyncCheckerIntegration:
    """Integration tests for SyncChecker with dashboard."""

    def test_sync_checker_triggers_refresh(self, qapp, mock_api_client):
        """SyncChecker triggers _refresh_all_data when sync detected."""
        from opencode_monitor.dashboard.window import DashboardWindow

        refresh_calls = []

        def mock_refresh():
            refresh_calls.append(True)

        with patch.object(DashboardWindow, "_start_refresh"):
            with patch.object(DashboardWindow, "_refresh_all_data", mock_refresh):
                window = DashboardWindow()
                try:
                    # Create a sync checker that uses our mock refresh
                    from opencode_monitor.dashboard.window import SyncChecker

                    checker = SyncChecker(on_sync_detected=mock_refresh)

                    # Simulate session count change
                    mock_api_client.get_stats.return_value = {"sessions": 5}
                    checker._check()

                    # Refresh should have been called
                    assert len(refresh_calls) >= 1

                    checker.stop()
                finally:
                    window.close()
                    window.deleteLater()
