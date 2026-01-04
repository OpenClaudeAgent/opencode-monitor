"""
Tests for DashboardWindow sync functionality.

Coverage target: SyncChecker and read-only dashboard architecture.

The dashboard now operates in read-only mode. The menubar handles all DB writes
and updates sync_meta table. The dashboard polls the API via SyncChecker
to detect when new data is available.
"""

import pytest
from unittest.mock import patch, MagicMock


# =============================================================================
# Fixtures (qapp is provided by conftest.py with session scope)
# =============================================================================


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


@pytest.fixture
def sync_checker_with_tracker(qapp, mock_api_client):
    """Create a SyncChecker instance with callback tracker for testing."""
    from opencode_monitor.dashboard.window import SyncChecker

    callback_calls: list[bool] = []
    checker = SyncChecker(on_sync_detected=lambda: callback_calls.append(True))
    yield checker, callback_calls
    checker.stop()


@pytest.fixture
def dashboard_window(qapp, mock_api_client):
    """Create a DashboardWindow with mocked fetch methods."""
    from opencode_monitor.dashboard.window import DashboardWindow

    with patch.object(DashboardWindow, "_fetch_monitoring_data"):
        with patch.object(DashboardWindow, "_fetch_security_data"):
            with patch.object(DashboardWindow, "_fetch_analytics_data"):
                with patch.object(DashboardWindow, "_fetch_tracing_data"):
                    window = DashboardWindow()
                    yield window
                    window.close()
                    window.deleteLater()


# =============================================================================
# SyncChecker Tests (consolidated)
# =============================================================================


class TestSyncChecker:
    """Tests for SyncChecker class - constants, callback, and timer behavior."""

    @pytest.mark.parametrize(
        "constant_name,expected_value",
        [
            ("POLL_FAST_MS", 2000),
            ("POLL_SLOW_MS", 5000),
            ("IDLE_THRESHOLD_S", 30),
        ],
    )
    def test_sync_checker_constants(self, constant_name, expected_value):
        """SyncChecker has correct poll interval constants."""
        from opencode_monitor.dashboard.window import SyncChecker

        assert getattr(SyncChecker, constant_name) == expected_value

    def test_sync_checker_callback_and_timer(
        self, sync_checker_with_tracker, mock_api_client
    ):
        """SyncChecker calls callback on change and stop() stops timer."""
        checker, callback_calls = sync_checker_with_tracker

        # Timer should be active initially
        assert checker._timer.isActive() == True

        # Simulate session count change - triggers callback
        mock_api_client.get_stats.return_value = {"sessions": 10}
        checker._check()
        assert len(callback_calls) == 1

        # Stop and verify timer is inactive
        checker.stop()
        assert checker._timer.isActive() == False


# =============================================================================
# DashboardWindow Read-Only Architecture Tests (consolidated)
# =============================================================================


class TestDashboardReadOnly:
    """Tests for read-only dashboard architecture."""

    @pytest.mark.parametrize(
        "attr_name,should_exist",
        [
            ("_sync_config", False),
            ("_sync_opencode_data", False),
            ("_sync_checker", True),
        ],
    )
    def test_dashboard_architecture_attributes(
        self, qapp, mock_api_client, attr_name, should_exist
    ):
        """DashboardWindow has correct read-only architecture attributes."""
        from opencode_monitor.dashboard.window import DashboardWindow

        with patch.object(DashboardWindow, "_fetch_monitoring_data"):
            with patch.object(DashboardWindow, "_fetch_security_data"):
                with patch.object(DashboardWindow, "_fetch_analytics_data"):
                    with patch.object(DashboardWindow, "_fetch_tracing_data"):
                        window = DashboardWindow()
                        try:
                            assert hasattr(window, attr_name) == should_exist
                        finally:
                            window.close()
                            window.deleteLater()

    def test_dashboard_close_stops_sync_checker(self, dashboard_window):
        """DashboardWindow.closeEvent stops the sync checker timer."""
        sync_checker = dashboard_window._sync_checker

        # Timer active before close
        assert sync_checker._timer.isActive() == True

        # Close triggers timer stop
        dashboard_window.close()
        assert sync_checker._timer.isActive() == False


# =============================================================================
# DataSignals Tests (consolidated)
# =============================================================================


class TestDataSignals:
    """Tests for DataSignals class."""

    @pytest.mark.parametrize(
        "signal_name,should_exist",
        [
            ("monitoring_updated", True),
            ("security_updated", True),
            ("analytics_updated", True),
            ("tracing_updated", True),
            ("sync_completed", False),  # Removed - dashboard uses SyncChecker now
        ],
    )
    def test_data_signals_structure(self, signal_name, should_exist):
        """DataSignals has expected signals (sync_completed removed)."""
        from opencode_monitor.dashboard.window import DataSignals

        signals = DataSignals()
        assert hasattr(signals, signal_name) == should_exist


# =============================================================================
# SyncChecker Integration Tests
# =============================================================================


class TestSyncCheckerIntegration:
    """Integration tests for SyncChecker with dashboard."""

    def test_sync_checker_triggers_refresh(self, qapp, mock_api_client):
        """SyncChecker triggers _refresh_all_data when sync detected."""
        from opencode_monitor.dashboard.window import DashboardWindow, SyncChecker

        refresh_calls = []

        with patch.object(DashboardWindow, "_start_refresh"):
            with patch.object(
                DashboardWindow, "_refresh_all_data", lambda s: refresh_calls.append(1)
            ):
                window = DashboardWindow()
                try:
                    checker = SyncChecker(
                        on_sync_detected=lambda: refresh_calls.append(1)
                    )

                    # Simulate session count change
                    mock_api_client.get_stats.return_value = {"sessions": 5}
                    checker._check()

                    # Verify refresh was called exactly once
                    assert len(refresh_calls) == 1

                    checker.stop()
                finally:
                    window.close()
                    window.deleteLater()
