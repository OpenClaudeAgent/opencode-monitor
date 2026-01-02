"""
Tests for DashboardWindow sync functionality.

Coverage target: 100% for SyncConfig and sync methods.
Tests SyncConfig defaults, injection, _sync_opencode_data, and sync_completed signal.
"""

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import fields

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
def mock_load_opencode_data():
    """Mock load_opencode_data to avoid real data loading."""
    with patch("opencode_monitor.dashboard.window.load_opencode_data") as mock_loader:
        mock_loader.return_value = {
            "sessions": 10,
            "messages": 100,
            "traces": 50,
        }
        yield mock_loader


@pytest.fixture
def mock_analytics_db():
    """Mock AnalyticsDB to avoid real database operations."""
    with patch("opencode_monitor.dashboard.window.AnalyticsDB") as mock_db:
        mock_instance = MagicMock()
        mock_db.return_value = mock_instance
        yield mock_db


@pytest.fixture
def mock_trace_queries():
    """Mock TraceQueries to avoid real database queries."""
    with patch("opencode_monitor.dashboard.window.TraceQueries") as mock_queries:
        mock_instance = MagicMock()
        mock_instance.get_trace_stats.return_value = {}
        mock_instance.get_sessions_with_traces.return_value = []
        mock_instance.get_traces_by_date_range.return_value = []
        mock_instance.get_session_hierarchy.return_value = []
        mock_queries.return_value = mock_instance
        yield mock_queries


# =============================================================================
# SyncConfig Tests
# =============================================================================


class TestSyncConfig:
    """Tests for SyncConfig dataclass."""

    def test_sync_config_is_dataclass(self):
        """SyncConfig is a dataclass with expected fields."""
        from opencode_monitor.dashboard.window import SyncConfig

        field_names = [f.name for f in fields(SyncConfig)]
        assert "clear_first" in field_names
        assert "max_days" in field_names
        assert "skip_parts" in field_names

    def test_sync_config_default_clear_first(self):
        """SyncConfig default clear_first is False."""
        from opencode_monitor.dashboard.window import SyncConfig

        config = SyncConfig()
        assert config.clear_first is False

    def test_sync_config_default_max_days(self):
        """SyncConfig default max_days is 30."""
        from opencode_monitor.dashboard.window import SyncConfig

        config = SyncConfig()
        assert config.max_days == 30

    def test_sync_config_default_skip_parts(self):
        """SyncConfig default skip_parts is True."""
        from opencode_monitor.dashboard.window import SyncConfig

        config = SyncConfig()
        assert config.skip_parts is True

    def test_sync_config_custom_values(self):
        """SyncConfig accepts custom values."""
        from opencode_monitor.dashboard.window import SyncConfig

        config = SyncConfig(clear_first=True, max_days=7, skip_parts=False)
        assert config.clear_first is True
        assert config.max_days == 7
        assert config.skip_parts is False

    def test_sync_config_partial_override(self):
        """SyncConfig allows partial override of defaults."""
        from opencode_monitor.dashboard.window import SyncConfig

        config = SyncConfig(max_days=14)
        assert config.clear_first is False  # default
        assert config.max_days == 14  # overridden
        assert config.skip_parts is True  # default

    def test_sync_config_immutable_defaults(self):
        """SyncConfig instances are independent."""
        from opencode_monitor.dashboard.window import SyncConfig

        config1 = SyncConfig()
        config2 = SyncConfig(max_days=7)

        assert config1.max_days == 30
        assert config2.max_days == 7


# =============================================================================
# DashboardWindow SyncConfig Injection Tests
# =============================================================================


class TestDashboardWindowSyncConfig:
    """Tests for SyncConfig injection in DashboardWindow."""

    def test_dashboard_default_sync_config(
        self,
        qapp,
        mock_load_opencode_data,
        mock_analytics_db,
        mock_trace_queries,
    ):
        """DashboardWindow uses default SyncConfig when none provided."""
        from opencode_monitor.dashboard.window import DashboardWindow, SyncConfig

        with patch.object(DashboardWindow, "_start_refresh"):
            window = DashboardWindow()
            try:
                assert window._sync_config is not None
                assert isinstance(window._sync_config, SyncConfig)
                assert window._sync_config.clear_first is False
                assert window._sync_config.max_days == 30
                assert window._sync_config.skip_parts is True
            finally:
                window.close()
                window.deleteLater()

    def test_dashboard_custom_sync_config(
        self,
        qapp,
        mock_load_opencode_data,
        mock_analytics_db,
        mock_trace_queries,
    ):
        """DashboardWindow accepts custom SyncConfig."""
        from opencode_monitor.dashboard.window import DashboardWindow, SyncConfig

        custom_config = SyncConfig(clear_first=True, max_days=7, skip_parts=False)

        with patch.object(DashboardWindow, "_start_refresh"):
            window = DashboardWindow(sync_config=custom_config)
            try:
                assert window._sync_config is custom_config
                assert window._sync_config.clear_first is True
                assert window._sync_config.max_days == 7
                assert window._sync_config.skip_parts is False
            finally:
                window.close()
                window.deleteLater()

    def test_dashboard_sync_config_none_uses_default(
        self,
        qapp,
        mock_load_opencode_data,
        mock_analytics_db,
        mock_trace_queries,
    ):
        """DashboardWindow with sync_config=None uses default SyncConfig."""
        from opencode_monitor.dashboard.window import DashboardWindow, SyncConfig

        with patch.object(DashboardWindow, "_start_refresh"):
            window = DashboardWindow(sync_config=None)
            try:
                assert window._sync_config is not None
                # Should be equivalent to default SyncConfig
                assert window._sync_config.max_days == 30
            finally:
                window.close()
                window.deleteLater()


# =============================================================================
# _sync_opencode_data Tests
# =============================================================================


class TestSyncOpencodeData:
    """Tests for _sync_opencode_data method."""

    def test_sync_opencode_data_calls_loader(
        self,
        qapp,
        mock_load_opencode_data,
        mock_analytics_db,
        mock_trace_queries,
    ):
        """_sync_opencode_data calls load_opencode_data with config params."""
        from opencode_monitor.dashboard.window import DashboardWindow, SyncConfig

        config = SyncConfig(clear_first=True, max_days=14, skip_parts=False)

        with patch.object(DashboardWindow, "_start_refresh"):
            window = DashboardWindow(sync_config=config)
            try:
                # Call sync method directly (not via thread)
                window._sync_opencode_data()

                # Verify load_opencode_data was called with correct params
                mock_load_opencode_data.assert_called_once_with(
                    clear_first=True,
                    max_days=14,
                    skip_parts=False,
                )
            finally:
                window.close()
                window.deleteLater()

    def test_sync_opencode_data_uses_default_config(
        self,
        qapp,
        mock_load_opencode_data,
        mock_analytics_db,
        mock_trace_queries,
    ):
        """_sync_opencode_data uses default config params when no custom config."""
        from opencode_monitor.dashboard.window import DashboardWindow

        with patch.object(DashboardWindow, "_start_refresh"):
            window = DashboardWindow()
            try:
                window._sync_opencode_data()

                # Verify default params
                mock_load_opencode_data.assert_called_once_with(
                    clear_first=False,
                    max_days=30,
                    skip_parts=True,
                )
            finally:
                window.close()
                window.deleteLater()

    def test_sync_opencode_data_handles_exception(
        self,
        qapp,
        mock_analytics_db,
        mock_trace_queries,
    ):
        """_sync_opencode_data handles exceptions gracefully."""
        from opencode_monitor.dashboard.window import DashboardWindow

        with patch(
            "opencode_monitor.dashboard.window.load_opencode_data",
            side_effect=Exception("Database error"),
        ):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    # Should not raise
                    window._sync_opencode_data()
                finally:
                    window.close()
                    window.deleteLater()


# =============================================================================
# sync_completed Signal Tests
# =============================================================================


class TestSyncCompletedSignal:
    """Tests for sync_completed signal emission."""

    def test_sync_completed_signal_exists(
        self,
        qapp,
        mock_load_opencode_data,
        mock_analytics_db,
        mock_trace_queries,
    ):
        """DashboardWindow has sync_completed signal on _signals."""
        from opencode_monitor.dashboard.window import DashboardWindow

        with patch.object(DashboardWindow, "_start_refresh"):
            window = DashboardWindow()
            try:
                assert hasattr(window._signals, "sync_completed")
            finally:
                window.close()
                window.deleteLater()

    def test_sync_completed_signal_emitted_on_success(
        self,
        qapp,
        mock_load_opencode_data,
        mock_analytics_db,
        mock_trace_queries,
    ):
        """_sync_opencode_data emits sync_completed signal on success."""
        from opencode_monitor.dashboard.window import DashboardWindow, SyncConfig

        mock_load_opencode_data.return_value = {
            "sessions": 5,
            "messages": 50,
        }

        with patch.object(DashboardWindow, "_start_refresh"):
            window = DashboardWindow()
            try:
                # Capture signal emissions
                signal_received = []
                window._signals.sync_completed.connect(
                    lambda result: signal_received.append(result)
                )

                # Call sync
                window._sync_opencode_data()

                # Verify signal was emitted
                assert len(signal_received) == 1
                assert signal_received[0] == {"sessions": 5, "messages": 50}
            finally:
                window.close()
                window.deleteLater()

    def test_sync_completed_signal_not_emitted_on_error(
        self,
        qapp,
        mock_analytics_db,
        mock_trace_queries,
    ):
        """_sync_opencode_data does not emit signal on exception."""
        from opencode_monitor.dashboard.window import DashboardWindow

        with patch(
            "opencode_monitor.dashboard.window.load_opencode_data",
            side_effect=Exception("Network error"),
        ):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    signal_received = []
                    window._signals.sync_completed.connect(
                        lambda result: signal_received.append(result)
                    )

                    window._sync_opencode_data()

                    # Signal should NOT be emitted on error
                    assert len(signal_received) == 0
                finally:
                    window.close()
                    window.deleteLater()

    def test_on_sync_completed_refreshes_data(
        self,
        qapp,
        mock_load_opencode_data,
        mock_analytics_db,
        mock_trace_queries,
    ):
        """_on_sync_completed triggers _refresh_all_data."""
        from opencode_monitor.dashboard.window import DashboardWindow

        with patch.object(DashboardWindow, "_start_refresh"):
            window = DashboardWindow()
            try:
                with patch.object(window, "_refresh_all_data") as mock_refresh:
                    window._on_sync_completed({"sessions": 10})

                    mock_refresh.assert_called_once()
            finally:
                window.close()
                window.deleteLater()


# =============================================================================
# DataSignals Tests
# =============================================================================


class TestDataSignals:
    """Tests for DataSignals class."""

    def test_data_signals_has_sync_completed(self):
        """DataSignals has sync_completed pyqtSignal."""
        from opencode_monitor.dashboard.window import DataSignals

        signals = DataSignals()
        assert hasattr(signals, "sync_completed")

    def test_data_signals_sync_completed_accepts_dict(self):
        """sync_completed signal accepts dict argument."""
        from opencode_monitor.dashboard.window import DataSignals

        signals = DataSignals()
        received = []
        signals.sync_completed.connect(lambda data: received.append(data))

        # Emit with dict
        signals.sync_completed.emit({"key": "value"})

        assert len(received) == 1
        assert received[0] == {"key": "value"}

    def test_data_signals_all_signals_exist(self):
        """DataSignals has all expected signals."""
        from opencode_monitor.dashboard.window import DataSignals

        signals = DataSignals()
        expected_signals = [
            "monitoring_updated",
            "security_updated",
            "analytics_updated",
            "tracing_updated",
            "sync_completed",
        ]
        for signal_name in expected_signals:
            assert hasattr(signals, signal_name), f"Missing signal: {signal_name}"
