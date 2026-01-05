"""
Tests for DashboardWindow coverage improvement.

Target: Improve dashboard/window/ module coverage from 49% to 80%+.

Focuses on:
- launcher.py: show_dashboard() subprocess management (29% → 80%+)
- main.py: fetch methods, signal handlers, UI callbacks (43% → 80%+)
- sync.py: idle mode transition (88% → 95%+)
"""

import time
import subprocess
from unittest.mock import patch, MagicMock, PropertyMock
import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_client():
    """Mock API client to avoid real API calls."""
    mock_client = MagicMock()
    mock_client.is_available = True
    mock_client.get_stats.return_value = {"sessions": 0}
    mock_client.get_global_stats.return_value = {
        "summary": {
            "total_sessions": 10,
            "total_messages": 100,
            "total_tokens": 5000,
        },
        "details": {
            "tokens": {
                "input": 2000,
                "cache_read": 3000,
            }
        },
    }
    mock_client.get_tracing_tree.return_value = [
        {"session_id": "sess-1", "title": "Test Session"}
    ]

    with patch("opencode_monitor.api.get_api_client") as mock_get:
        mock_get.return_value = mock_client
        yield mock_client


@pytest.fixture
def dashboard_window_isolated(qapp, mock_api_client):
    """DashboardWindow without auto-refresh for isolated testing."""
    from opencode_monitor.dashboard.window import DashboardWindow

    with patch.object(DashboardWindow, "_start_refresh"):
        window = DashboardWindow()
        yield window
        window.close()
        window.deleteLater()


@pytest.fixture
def dashboard_window_minimal(qapp, mock_api_client):
    """Create a DashboardWindow with mocked fetch methods.

    Uses the same approach as test_dashboard_sync.py which works.
    After creation, we swap internal widgets with mocks for testing handlers.
    """
    from opencode_monitor.dashboard.window import DashboardWindow

    # Patch fetch methods to avoid real data fetching
    with patch.object(DashboardWindow, "_fetch_monitoring_data"):
        with patch.object(DashboardWindow, "_fetch_security_data"):
            with patch.object(DashboardWindow, "_fetch_analytics_data"):
                with patch.object(DashboardWindow, "_fetch_tracing_data"):
                    window = DashboardWindow()

                    # Create mock sections for testing handlers
                    mock_sections = {
                        "monitoring": MagicMock(),
                        "security": MagicMock(),
                        "analytics": MagicMock(),
                        "tracing": MagicMock(),
                    }

                    # Swap real sections with mocks for handler testing
                    window._monitoring = mock_sections["monitoring"]
                    window._security = mock_sections["security"]
                    window._analytics = mock_sections["analytics"]
                    window._tracing = mock_sections["tracing"]

                    # Also mock sidebar for status updates
                    window._sidebar = MagicMock()

                    yield window, mock_sections
                    window.close()
                    window.deleteLater()


# =============================================================================
# launcher.py Tests - show_dashboard()
# =============================================================================


class TestLauncherShowDashboard:
    """Tests for launcher.py show_dashboard() function."""

    def test_show_dashboard_first_launch(self):
        """show_dashboard() launches subprocess when no existing process."""
        import opencode_monitor.dashboard.window.launcher as launcher

        # Reset global state
        launcher._dashboard_process = None

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_popen.return_value = mock_process

            launcher.show_dashboard()

            # Verify Popen was called with correct args
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            assert "-m" in call_args[0][0]
            assert "opencode_monitor.dashboard" in call_args[0][0]
            assert call_args[1]["start_new_session"] is True

    def test_show_dashboard_kills_existing_running(self):
        """show_dashboard() terminates existing running process first."""
        import opencode_monitor.dashboard.window.launcher as launcher

        # Setup existing process that's still running
        mock_existing = MagicMock()
        mock_existing.poll.return_value = None  # Still running
        launcher._dashboard_process = mock_existing

        with patch("subprocess.Popen") as mock_popen:
            mock_new = MagicMock()
            mock_popen.return_value = mock_new

            launcher.show_dashboard()

            # Verify terminate was called on existing
            mock_existing.terminate.assert_called_once()
            mock_existing.wait.assert_called_once_with(timeout=2)

    def test_show_dashboard_kill_after_timeout(self):
        """show_dashboard() kills process if terminate times out."""
        import opencode_monitor.dashboard.window.launcher as launcher

        # Setup existing process that won't terminate gracefully
        mock_existing = MagicMock()
        mock_existing.poll.return_value = None  # Still running
        mock_existing.wait.side_effect = subprocess.TimeoutExpired(
            cmd="test", timeout=2
        )
        launcher._dashboard_process = mock_existing

        with patch("subprocess.Popen") as mock_popen:
            mock_new = MagicMock()
            mock_popen.return_value = mock_new

            launcher.show_dashboard()

            # Verify kill was called after timeout
            mock_existing.kill.assert_called_once()

    def test_show_dashboard_skips_dead_process(self):
        """show_dashboard() doesn't terminate already-dead process."""
        import opencode_monitor.dashboard.window.launcher as launcher

        # Setup existing process that's already dead
        mock_existing = MagicMock()
        mock_existing.poll.return_value = 0  # Already terminated
        launcher._dashboard_process = mock_existing

        with patch("subprocess.Popen") as mock_popen:
            mock_new = MagicMock()
            mock_popen.return_value = mock_new

            launcher.show_dashboard()

            # Verify terminate was NOT called
            mock_existing.terminate.assert_not_called()


# =============================================================================
# main.py Tests - Signal Handlers
# =============================================================================


class TestDashboardSignalHandlers:
    """Tests for DashboardWindow signal handler methods."""

    def test_on_section_changed(self, dashboard_window_minimal):
        """_on_section_changed updates pages stack index."""
        window, sections = dashboard_window_minimal

        # Mock the pages widget
        window._pages = MagicMock()

        window._on_section_changed(2)

        window._pages.setCurrentIndex.assert_called_once_with(2)

    def test_on_open_terminal_with_known_agent(self, dashboard_window_minimal):
        """_on_open_terminal focuses terminal when agent has TTY mapping."""
        window, sections = dashboard_window_minimal

        # Setup TTY mapping
        window._agent_tty_map = {"agent-123": "/dev/ttys001"}

        with patch("opencode_monitor.ui.terminal.focus_iterm2") as mock_focus:
            window._on_open_terminal("agent-123")
            mock_focus.assert_called_once_with("/dev/ttys001")

    def test_on_open_terminal_with_unknown_agent(self, dashboard_window_minimal):
        """_on_open_terminal does nothing for unknown agent."""
        window, sections = dashboard_window_minimal

        window._agent_tty_map = {}

        with patch("opencode_monitor.ui.terminal.focus_iterm2") as mock_focus:
            window._on_open_terminal("unknown-agent")
            mock_focus.assert_not_called()

    def test_on_open_terminal_session(self, dashboard_window_minimal):
        """_on_open_terminal_session logs the request."""
        window, sections = dashboard_window_minimal

        with patch("opencode_monitor.utils.logger.debug") as mock_debug:
            window._on_open_terminal_session("session-abc")
            mock_debug.assert_called_once()
            assert "session-abc" in mock_debug.call_args[0][0]

    def test_on_analytics_period_changed(self, dashboard_window_minimal):
        """_on_analytics_period_changed triggers analytics data fetch."""
        window, sections = dashboard_window_minimal

        with patch.object(window, "_fetch_analytics_data") as mock_fetch:
            with patch("threading.Thread") as mock_thread:
                mock_thread_instance = MagicMock()
                mock_thread.return_value = mock_thread_instance

                window._on_analytics_period_changed(30)

                mock_thread.assert_called_once()
                mock_thread_instance.start.assert_called_once()


# =============================================================================
# main.py Tests - Data Update Handlers
# =============================================================================


class TestDashboardDataHandlers:
    """Tests for DashboardWindow data update handlers."""

    def test_on_monitoring_data(self, dashboard_window_minimal):
        """_on_monitoring_data updates monitoring section and sidebar."""
        window, sections = dashboard_window_minimal

        data = {
            "instances": 2,
            "agents": 3,
            "busy": 1,
            "waiting": 0,
            "idle": 2,
            "todos": 5,
            "agents_data": [{"agent_id": "a1"}],
            "tools_data": [],
            "waiting_data": [],
        }

        window._on_monitoring_data(data)

        # Verify section update
        sections["monitoring"].update_data.assert_called_once_with(
            instances=2,
            agents=3,
            busy=1,
            waiting=0,
            idle=2,
            todos=5,
            agents_data=[{"agent_id": "a1"}],
            tools_data=[],
            waiting_data=[],
        )

        # Verify sidebar status update
        window._sidebar.set_status.assert_called()

    def test_on_monitoring_data_with_zero_agents(self, dashboard_window_minimal):
        """_on_monitoring_data shows 'Idle' status when no agents."""
        window, sections = dashboard_window_minimal

        data = {
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

        window._on_monitoring_data(data)

        # Check sidebar shows Idle
        call_args = window._sidebar.set_status.call_args
        assert call_args[0][0] is False  # not active
        assert call_args[0][1] == "Idle"

    def test_on_monitoring_data_singular_agent(self, dashboard_window_minimal):
        """_on_monitoring_data uses singular 'agent' for count of 1."""
        window, sections = dashboard_window_minimal

        data = {
            "instances": 1,
            "agents": 1,
            "busy": 1,
            "waiting": 0,
            "idle": 0,
            "todos": 0,
            "agents_data": [{"agent_id": "a1"}],
            "tools_data": [],
            "waiting_data": [],
        }

        window._on_monitoring_data(data)

        call_args = window._sidebar.set_status.call_args
        assert call_args[0][1] == "1 agent"  # Singular

    def test_on_security_data(self, dashboard_window_minimal):
        """_on_security_data updates security section."""
        window, sections = dashboard_window_minimal

        data = {
            "stats": {"critical": 0},
            "commands": [{"command": "ls"}],
            "files": [],
            "critical_items": [],
        }

        window._on_security_data(data)

        sections["security"].update_data.assert_called_once_with(
            stats={"critical": 0},
            commands=[{"command": "ls"}],
            files=[],
            critical_items=[],
        )

    def test_on_analytics_data(self, dashboard_window_minimal):
        """_on_analytics_data updates analytics section."""
        window, sections = dashboard_window_minimal

        data = {
            "sessions": 10,
            "messages": 100,
            "tokens": "5K",
            "cache_hit": "60%",
            "agents": [],
            "tools": [],
            "skills": [],
        }

        window._on_analytics_data(data)

        sections["analytics"].update_data.assert_called_once_with(
            sessions=10,
            messages=100,
            tokens="5K",
            cache_hit="60%",
            agents=[],
            tools=[],
            skills=[],
        )

    def test_on_tracing_data(self, dashboard_window_minimal):
        """_on_tracing_data updates tracing section."""
        window, sections = dashboard_window_minimal

        data = {
            "session_hierarchy": [{"session_id": "s1"}],
        }

        window._on_tracing_data(data)

        sections["tracing"].update_data.assert_called_once_with(
            session_hierarchy=[{"session_id": "s1"}],
        )


# =============================================================================
# main.py Tests - Fetch Methods
# =============================================================================


class TestDashboardFetchMethods:
    """Tests for DashboardWindow fetch methods."""

    def test_fetch_monitoring_data_success(self, qapp, mock_api_client):
        """_fetch_monitoring_data fetches and emits monitoring data."""
        from opencode_monitor.dashboard.window import DashboardWindow
        from opencode_monitor.core.models import (
            State,
            Instance,
            Agent,
            SessionStatus,
            Todos,
            Tool,
        )

        # Create mock state
        mock_state = State(
            instances=[
                Instance(
                    port=8080,
                    tty="/dev/ttys001",
                    agents=[
                        Agent(
                            id="agent-1",
                            title="Test Agent",
                            dir="project",
                            full_dir="/home/user/project",
                            status=SessionStatus.BUSY,
                            tools=[Tool(name="bash", arg="ls -la", elapsed_ms=100)],
                        ),
                    ],
                )
            ],
            todos=Todos(pending=2, in_progress=1),
        )

        with patch("asyncio.new_event_loop") as mock_loop_factory:
            mock_loop = MagicMock()
            mock_loop.run_until_complete.return_value = mock_state
            mock_loop_factory.return_value = mock_loop

            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    # Track emitted data
                    received_data = []
                    window._signals.monitoring_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    window._fetch_monitoring_data()

                    assert len(received_data) == 1
                    data = received_data[0]
                    assert data["instances"] == 1
                    assert data["agents"] == 1
                    assert data["busy"] == 1
                    assert len(data["agents_data"]) == 1
                    assert len(data["tools_data"]) == 1
                finally:
                    window.close()
                    window.deleteLater()

    def test_fetch_monitoring_data_handles_exception(self, qapp, mock_api_client):
        """_fetch_monitoring_data logs error and continues on exception."""
        from opencode_monitor.dashboard.window import DashboardWindow

        with patch("asyncio.new_event_loop") as mock_loop_factory:
            mock_loop_factory.side_effect = RuntimeError("Test error")

            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    with patch("opencode_monitor.utils.logger.error") as mock_error:
                        # Should not raise
                        window._fetch_monitoring_data()
                        mock_error.assert_called_once()
                        assert "Monitoring fetch error" in mock_error.call_args[0][0]
                finally:
                    window.close()
                    window.deleteLater()

    def test_fetch_security_data_success(self, qapp, mock_api_client):
        """_fetch_security_data fetches and emits security data."""
        from opencode_monitor.dashboard.window import DashboardWindow

        # Create mock command record
        mock_cmd = MagicMock()
        mock_cmd.command = "rm -rf"
        mock_cmd.risk_level = "high"
        mock_cmd.risk_score = 80
        mock_cmd.risk_reason = "dangerous"

        mock_auditor = MagicMock()
        mock_auditor.get_stats.return_value = {"critical": 0, "high": 1}
        mock_auditor.get_all_commands.return_value = [mock_cmd]
        mock_auditor.get_all_reads.return_value = []
        mock_auditor.get_all_writes.return_value = []
        mock_auditor.get_critical_commands.return_value = []
        mock_auditor.get_commands_by_level.return_value = []
        mock_auditor.get_sensitive_reads.return_value = []
        mock_auditor.get_sensitive_writes.return_value = []
        mock_auditor.get_risky_webfetches.return_value = []

        with patch(
            "opencode_monitor.security.auditor.get_auditor", return_value=mock_auditor
        ):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    received_data = []
                    window._signals.security_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    window._fetch_security_data()

                    assert len(received_data) == 1
                    data = received_data[0]
                    assert data["stats"]["critical"] == 0
                    assert len(data["commands"]) == 1
                finally:
                    window.close()
                    window.deleteLater()

    def test_fetch_security_data_handles_exception(self, qapp, mock_api_client):
        """_fetch_security_data logs error and continues on exception."""
        from opencode_monitor.dashboard.window import DashboardWindow

        with patch(
            "opencode_monitor.security.auditor.get_auditor",
            side_effect=RuntimeError("DB error"),
        ):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    with patch("opencode_monitor.utils.logger.error") as mock_error:
                        window._fetch_security_data()
                        mock_error.assert_called_once()
                        assert "Security fetch error" in mock_error.call_args[0][0]
                finally:
                    window.close()
                    window.deleteLater()

    def test_fetch_analytics_data_success(self, dashboard_window_isolated):
        """_fetch_analytics_data fetches and emits analytics data."""
        window = dashboard_window_isolated

        received_data = []
        window._signals.analytics_updated.connect(lambda d: received_data.append(d))

        # Mock the analytics section's get_current_period
        window._analytics = MagicMock()
        window._analytics.get_current_period.return_value = 7

        window._fetch_analytics_data()

        assert len(received_data) == 1
        data = received_data[0]
        assert data["sessions"] == 10
        assert data["messages"] == 100

    def test_fetch_analytics_data_api_unavailable(self, qapp):
        """_fetch_analytics_data returns early when API unavailable."""
        from opencode_monitor.dashboard.window import DashboardWindow

        mock_client = MagicMock()
        mock_client.is_available = False

        with patch("opencode_monitor.api.get_api_client", return_value=mock_client):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    received_data = []
                    window._signals.analytics_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    with patch("opencode_monitor.utils.logger.debug") as mock_debug:
                        window._fetch_analytics_data()

                    # No data emitted
                    assert len(received_data) == 0
                finally:
                    window.close()
                    window.deleteLater()

    def test_fetch_analytics_data_no_stats(self, qapp):
        """_fetch_analytics_data returns early when no stats returned."""
        from opencode_monitor.dashboard.window import DashboardWindow

        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.get_global_stats.return_value = None

        with patch("opencode_monitor.api.get_api_client", return_value=mock_client):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    window._analytics = MagicMock()
                    window._analytics.get_current_period.return_value = 7

                    received_data = []
                    window._signals.analytics_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    window._fetch_analytics_data()

                    assert len(received_data) == 0
                finally:
                    window.close()
                    window.deleteLater()

    @pytest.mark.parametrize(
        "total_tokens,expected_str",
        [
            pytest.param(500, "500", id="small"),
            pytest.param(5000, "5.0K", id="thousands"),
            pytest.param(1500000, "1.5M", id="millions"),
        ],
    )
    def test_fetch_analytics_data_token_formatting(
        self, qapp, total_tokens, expected_str
    ):
        """_fetch_analytics_data formats tokens correctly for different scales."""
        from opencode_monitor.dashboard.window import DashboardWindow

        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.get_global_stats.return_value = {
            "summary": {
                "total_sessions": 1,
                "total_messages": 1,
                "total_tokens": total_tokens,
            },
            "details": {"tokens": {"input": total_tokens, "cache_read": 0}},
        }

        with patch("opencode_monitor.api.get_api_client", return_value=mock_client):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    window._analytics = MagicMock()
                    window._analytics.get_current_period.return_value = 7

                    received_data = []
                    window._signals.analytics_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    window._fetch_analytics_data()

                    assert len(received_data) == 1
                    assert received_data[0]["tokens"] == expected_str
                finally:
                    window.close()
                    window.deleteLater()

    def test_fetch_analytics_data_handles_exception(self, qapp):
        """_fetch_analytics_data logs error and continues on exception."""
        from opencode_monitor.dashboard.window import DashboardWindow

        with patch(
            "opencode_monitor.api.get_api_client",
            side_effect=RuntimeError("API error"),
        ):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    with patch("opencode_monitor.utils.logger.error") as mock_error:
                        window._fetch_analytics_data()
                        mock_error.assert_called_once()
                        assert "Analytics fetch error" in mock_error.call_args[0][0]
                finally:
                    window.close()
                    window.deleteLater()

    def test_fetch_tracing_data_success(self, dashboard_window_isolated):
        """_fetch_tracing_data fetches and emits tracing data."""
        window = dashboard_window_isolated

        received_data = []
        window._signals.tracing_updated.connect(lambda d: received_data.append(d))

        window._fetch_tracing_data()

        assert len(received_data) == 1
        data = received_data[0]
        assert "session_hierarchy" in data
        assert len(data["session_hierarchy"]) == 1

    def test_fetch_tracing_data_api_unavailable(self, qapp):
        """_fetch_tracing_data returns early when API unavailable."""
        from opencode_monitor.dashboard.window import DashboardWindow

        mock_client = MagicMock()
        mock_client.is_available = False

        with patch("opencode_monitor.api.get_api_client", return_value=mock_client):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    received_data = []
                    window._signals.tracing_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    with patch("opencode_monitor.utils.logger.debug"):
                        window._fetch_tracing_data()

                    assert len(received_data) == 0
                finally:
                    window.close()
                    window.deleteLater()

    def test_fetch_tracing_data_handles_exception(self, qapp):
        """_fetch_tracing_data logs error with traceback on exception."""
        from opencode_monitor.dashboard.window import DashboardWindow

        with patch(
            "opencode_monitor.api.get_api_client",
            side_effect=RuntimeError("Tracing error"),
        ):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    with patch("opencode_monitor.utils.logger.error") as mock_error:
                        window._fetch_tracing_data()
                        # Called twice: once for message, once for traceback
                        assert mock_error.call_count == 2
                finally:
                    window.close()
                    window.deleteLater()


# =============================================================================
# main.py Tests - Monitoring Data Processing
# =============================================================================


class TestMonitoringDataProcessing:
    """Tests for monitoring data edge cases and processing."""

    def test_fetch_monitoring_with_waiting_agents(self, qapp, mock_api_client):
        """_fetch_monitoring_data correctly processes agents with pending ask_user."""
        from opencode_monitor.dashboard.window import DashboardWindow
        from opencode_monitor.core.models import (
            State,
            Instance,
            Agent,
            SessionStatus,
            Todos,
        )

        mock_state = State(
            instances=[
                Instance(
                    port=8080,
                    tty="",
                    agents=[
                        Agent(
                            id="agent-wait",
                            title="Waiting Agent",
                            dir="project",
                            full_dir="/home/user/project",
                            status=SessionStatus.BUSY,
                            has_pending_ask_user=True,
                            ask_user_title="Need Input",
                            ask_user_question="What next?",
                            ask_user_options=["Option A", "Option B"],
                            ask_user_agent="my-agent",
                            ask_user_branch="main",
                        ),
                    ],
                )
            ],
            todos=Todos(pending=0, in_progress=0),
        )

        with patch("asyncio.new_event_loop") as mock_loop_factory:
            mock_loop = MagicMock()
            mock_loop.run_until_complete.return_value = mock_state
            mock_loop_factory.return_value = mock_loop

            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    received_data = []
                    window._signals.monitoring_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    window._fetch_monitoring_data()

                    data = received_data[0]
                    assert data["waiting"] == 1
                    assert len(data["waiting_data"]) == 1
                    waiting = data["waiting_data"][0]
                    assert waiting["title"] == "Need Input"
                    assert waiting["question"] == "What next?"
                    assert "Option A | Option B" in waiting["options"]
                    assert waiting["context"] == "my-agent @ main"
                finally:
                    window.close()
                    window.deleteLater()

    def test_fetch_monitoring_idle_instance_count(self, qapp, mock_api_client):
        """_fetch_monitoring_data counts idle instances correctly."""
        from opencode_monitor.dashboard.window import DashboardWindow
        from opencode_monitor.core.models import (
            State,
            Instance,
            Agent,
            SessionStatus,
            Todos,
        )

        mock_state = State(
            instances=[
                Instance(
                    port=8080,
                    tty="",
                    agents=[
                        Agent(
                            id="agent-idle",
                            title="Idle Agent",
                            dir="project",
                            full_dir="/home",
                            status=SessionStatus.IDLE,
                        ),
                    ],
                ),
                Instance(
                    port=8081,
                    tty="",
                    agents=[],  # No agents = idle
                ),
            ],
            todos=Todos(pending=0, in_progress=0),
        )

        with patch("asyncio.new_event_loop") as mock_loop_factory:
            mock_loop = MagicMock()
            mock_loop.run_until_complete.return_value = mock_state
            mock_loop_factory.return_value = mock_loop

            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    received_data = []
                    window._signals.monitoring_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    window._fetch_monitoring_data()

                    data = received_data[0]
                    # Both instances have busy_count=0, so both are idle
                    assert data["idle"] == 2
                finally:
                    window.close()
                    window.deleteLater()


# =============================================================================
# sync.py Tests - Idle Mode Transition
# =============================================================================


class TestSyncCheckerIdleMode:
    """Tests for SyncChecker idle mode transition (lines 62-65)."""

    def test_sync_checker_switches_to_slow_mode(self, qapp):
        """SyncChecker switches to slow polling after idle threshold."""
        from opencode_monitor.dashboard.window import SyncChecker

        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.get_stats.return_value = {"sessions": 5}

        callback_calls = []

        with patch("opencode_monitor.api.get_api_client", return_value=mock_client):
            checker = SyncChecker(on_sync_detected=lambda: callback_calls.append(True))
            try:
                # Initial check sets known_sync
                checker._check()
                initial_interval = checker._timer.interval()
                assert initial_interval == SyncChecker.POLL_FAST_MS

                # Simulate time passing beyond idle threshold
                checker._last_change_time = (
                    time.time() - SyncChecker.IDLE_THRESHOLD_S - 1
                )

                # Next check with same session count should switch to slow mode
                checker._check()

                assert checker._timer.interval() == SyncChecker.POLL_SLOW_MS
            finally:
                checker.stop()

    def test_sync_checker_stays_fast_on_changes(self, qapp):
        """SyncChecker stays in fast mode when data keeps changing."""
        from opencode_monitor.dashboard.window import SyncChecker

        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.get_stats.return_value = {"sessions": 1}

        callback_calls = []

        with patch("opencode_monitor.api.get_api_client", return_value=mock_client):
            checker = SyncChecker(on_sync_detected=lambda: callback_calls.append(True))
            try:
                # First check
                checker._check()
                assert len(callback_calls) == 1

                # Change data
                mock_client.get_stats.return_value = {"sessions": 2}
                checker._check()
                assert len(callback_calls) == 2

                # Should still be in fast mode
                assert checker._timer.interval() == SyncChecker.POLL_FAST_MS
            finally:
                checker.stop()

    def test_sync_checker_handles_api_unavailable(self, qapp):
        """SyncChecker handles unavailable API gracefully."""
        from opencode_monitor.dashboard.window import SyncChecker

        mock_client = MagicMock()
        mock_client.is_available = False

        callback_calls = []

        with patch("opencode_monitor.api.get_api_client", return_value=mock_client):
            checker = SyncChecker(on_sync_detected=lambda: callback_calls.append(True))
            try:
                # Should not crash
                checker._check()
                assert len(callback_calls) == 0
            finally:
                checker.stop()

    def test_sync_checker_handles_exception(self, qapp):
        """SyncChecker handles exceptions in _check gracefully."""
        from opencode_monitor.dashboard.window import SyncChecker

        callback_calls = []

        with patch(
            "opencode_monitor.api.get_api_client",
            side_effect=RuntimeError("Connection error"),
        ):
            checker = SyncChecker(on_sync_detected=lambda: callback_calls.append(True))
            try:
                # Should not crash
                checker._check()
                assert len(callback_calls) == 0
            finally:
                checker.stop()


# =============================================================================
# Additional Coverage Tests - Edge Cases
# =============================================================================


class TestSecurityDataEdgeCases:
    """Tests for security data processing edge cases."""

    def test_fetch_security_with_critical_items(self, qapp, mock_api_client):
        """_fetch_security_data processes critical items from all sources."""
        from opencode_monitor.dashboard.window import DashboardWindow

        # Create mock records for each type
        mock_critical_cmd = MagicMock()
        mock_critical_cmd.command = "rm -rf /"
        mock_critical_cmd.risk_level = "critical"
        mock_critical_cmd.risk_score = 100
        mock_critical_cmd.risk_reason = "Dangerous"

        mock_sensitive_read = MagicMock()
        mock_sensitive_read.file_path = "/etc/passwd"
        mock_sensitive_read.risk_level = "high"
        mock_sensitive_read.risk_score = 80
        mock_sensitive_read.risk_reason = "Sensitive file"

        mock_sensitive_write = MagicMock()
        mock_sensitive_write.file_path = "/etc/shadow"
        mock_sensitive_write.risk_level = "critical"
        mock_sensitive_write.risk_score = 95
        mock_sensitive_write.risk_reason = "Password file"

        mock_risky_fetch = MagicMock()
        mock_risky_fetch.url = "http://malware.com"
        mock_risky_fetch.risk_level = "high"
        mock_risky_fetch.risk_score = 85
        mock_risky_fetch.risk_reason = "Suspicious URL"

        mock_read = MagicMock()
        mock_read.file_path = "/home/user/file.txt"
        mock_read.risk_level = "low"
        mock_read.risk_score = 10
        mock_read.risk_reason = "Normal read"

        mock_write = MagicMock()
        mock_write.file_path = "/tmp/output.txt"
        mock_write.risk_level = "low"
        mock_write.risk_score = 5
        mock_write.risk_reason = "Normal write"

        mock_auditor = MagicMock()
        mock_auditor.get_stats.return_value = {"critical": 2, "high": 2}
        mock_auditor.get_all_commands.return_value = []
        mock_auditor.get_all_reads.return_value = [mock_read]
        mock_auditor.get_all_writes.return_value = [mock_write]
        mock_auditor.get_critical_commands.return_value = [mock_critical_cmd]
        mock_auditor.get_commands_by_level.return_value = []
        mock_auditor.get_sensitive_reads.return_value = [mock_sensitive_read]
        mock_auditor.get_sensitive_writes.return_value = [mock_sensitive_write]
        mock_auditor.get_risky_webfetches.return_value = [mock_risky_fetch]

        with patch(
            "opencode_monitor.security.auditor.get_auditor", return_value=mock_auditor
        ):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    received_data = []
                    window._signals.security_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    window._fetch_security_data()

                    assert len(received_data) == 1
                    data = received_data[0]

                    # Check critical items include all types
                    critical_items = data["critical_items"]
                    types = [item["type"] for item in critical_items]
                    assert "COMMAND" in types
                    assert "READ" in types
                    assert "WRITE" in types
                    assert "WEBFETCH" in types

                    # Check files include reads and writes
                    files = data["files"]
                    operations = [f["operation"] for f in files]
                    assert "READ" in operations
                    assert "WRITE" in operations
                finally:
                    window.close()
                    window.deleteLater()


class TestMonitoringContextEdgeCases:
    """Tests for monitoring context string edge cases."""

    def test_fetch_monitoring_with_repo_context(self, qapp, mock_api_client):
        """_fetch_monitoring_data uses repo when agent name not available."""
        from opencode_monitor.dashboard.window import DashboardWindow
        from opencode_monitor.core.models import (
            State,
            Instance,
            Agent,
            SessionStatus,
            Todos,
        )

        # Agent with ask_user_repo but no ask_user_agent
        mock_state = State(
            instances=[
                Instance(
                    port=8080,
                    tty="",
                    agents=[
                        Agent(
                            id="agent-repo",
                            title="Repo Agent",
                            dir="project",
                            full_dir="/home/user/project",
                            status=SessionStatus.BUSY,
                            has_pending_ask_user=True,
                            ask_user_title="Input needed",
                            ask_user_question="Question?",
                            ask_user_options=[],
                            ask_user_agent="",  # No agent name
                            ask_user_repo="my-repo",  # Has repo
                            ask_user_branch="feature",
                        ),
                    ],
                )
            ],
            todos=Todos(pending=0, in_progress=0),
        )

        with patch("asyncio.new_event_loop") as mock_loop_factory:
            mock_loop = MagicMock()
            mock_loop.run_until_complete.return_value = mock_state
            mock_loop_factory.return_value = mock_loop

            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    received_data = []
                    window._signals.monitoring_updated.connect(
                        lambda d: received_data.append(d)
                    )

                    window._fetch_monitoring_data()

                    data = received_data[0]
                    waiting = data["waiting_data"][0]
                    # Context should use repo @ branch
                    assert waiting["context"] == "my-repo @ feature"
                finally:
                    window.close()
                    window.deleteLater()
