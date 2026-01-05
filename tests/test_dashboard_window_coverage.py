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
# Factories
# =============================================================================


def make_mock_state(
    agents=None,
    pending_todos=0,
    in_progress_todos=0,
    port=8080,
    tty="/dev/ttys001",
):
    """Factory for creating mock State objects."""
    from opencode_monitor.core.models import State, Instance, Todos

    if agents is None:
        agents = []

    return State(
        instances=[Instance(port=port, tty=tty, agents=agents)],
        todos=Todos(pending=pending_todos, in_progress=in_progress_todos),
    )


def make_mock_agent(
    agent_id="agent-1",
    title="Test Agent",
    status=None,
    tools=None,
    has_pending_ask_user=False,
    ask_user_title="",
    ask_user_question="",
    ask_user_options=None,
    ask_user_agent="",
    ask_user_repo="",
    ask_user_branch="",
):
    """Factory for creating mock Agent objects."""
    from opencode_monitor.core.models import Agent, SessionStatus

    if status is None:
        status = SessionStatus.BUSY
    if tools is None:
        tools = []
    if ask_user_options is None:
        ask_user_options = []

    return Agent(
        id=agent_id,
        title=title,
        dir="project",
        full_dir="/home/user/project",
        status=status,
        tools=tools,
        has_pending_ask_user=has_pending_ask_user,
        ask_user_title=ask_user_title,
        ask_user_question=ask_user_question,
        ask_user_options=ask_user_options,
        ask_user_agent=ask_user_agent,
        ask_user_repo=ask_user_repo,
        ask_user_branch=ask_user_branch,
    )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_client_for_window():
    """Mock API client to avoid real API calls."""
    mock_client = MagicMock()
    mock_client.is_available = True
    mock_client.get_stats.return_value = {"sessions": 0}
    mock_client.get_sync_status.return_value = {"backfill_active": False}
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
    mock_client.get_security_data.return_value = {
        "stats": {"critical": 0, "high": 1},
        "commands": [
            {
                "command": "rm -rf",
                "risk": "high",
                "score": 80,
                "reason": "dangerous",
            }
        ],
        "files": [],
        "critical_items": [],
    }

    with patch("opencode_monitor.api.get_api_client") as mock_get:
        mock_get.return_value = mock_client
        yield mock_client


@pytest.fixture
def dashboard_window_simple(qapp, mock_api_client_for_window):
    """Simple DashboardWindow for testing - no auto-refresh, easy cleanup."""
    from opencode_monitor.dashboard.window import DashboardWindow

    with patch.object(DashboardWindow, "_start_refresh"):
        window = DashboardWindow()
        yield window
        window.close()
        window.deleteLater()


@pytest.fixture
def dashboard_window_isolated(qapp, mock_api_client_for_window):
    """DashboardWindow without auto-refresh for isolated testing."""
    from opencode_monitor.dashboard.window import DashboardWindow

    with patch.object(DashboardWindow, "_start_refresh"):
        window = DashboardWindow()
        yield window
        window.close()
        window.deleteLater()


@pytest.fixture
def dashboard_window_minimal(qapp, mock_api_client_for_window):
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
        window._sidebar.set_status.assert_called_once()

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
# Parameterized Tests - Exception Handling
# =============================================================================


class TestFetchExceptionHandling:
    """Parameterized tests for fetch method exception handling."""

    @pytest.mark.parametrize(
        "patch_target,method_name,error_msg_contains",
        [
            pytest.param(
                "asyncio.new_event_loop",
                "_fetch_monitoring_data",
                "Monitoring fetch error",
                id="monitoring",
            ),
            pytest.param(
                "opencode_monitor.api.get_api_client",
                "_fetch_security_data",
                "Security fetch error",
                id="security",
            ),
            pytest.param(
                "opencode_monitor.api.get_api_client",
                "_fetch_analytics_data",
                "Analytics fetch error",
                id="analytics",
            ),
        ],
    )
    def test_fetch_handles_exception(
        self, dashboard_window_simple, patch_target, method_name, error_msg_contains
    ):
        """Fetch methods log error and continue on exception."""
        window = dashboard_window_simple

        with patch(patch_target, side_effect=RuntimeError("Test error")):
            with patch("opencode_monitor.utils.logger.error") as mock_error:
                # Call the method - should not raise
                getattr(window, method_name)()
                mock_error.assert_called_once()
                assert error_msg_contains in mock_error.call_args[0][0]


class TestFetchApiUnavailable:
    """Parameterized tests for API unavailable handling."""

    @pytest.mark.parametrize(
        "method_name,signal_name",
        [
            pytest.param("_fetch_analytics_data", "analytics_updated", id="analytics"),
            pytest.param("_fetch_tracing_data", "tracing_updated", id="tracing"),
        ],
    )
    def test_fetch_returns_early_when_api_unavailable(
        self, qapp, method_name, signal_name
    ):
        """Fetch methods return early when API is unavailable."""
        from opencode_monitor.dashboard.window import DashboardWindow

        mock_client = MagicMock()
        mock_client.is_available = False

        with patch("opencode_monitor.api.get_api_client", return_value=mock_client):
            with patch.object(DashboardWindow, "_start_refresh"):
                window = DashboardWindow()
                try:
                    received_data = []
                    signal = getattr(window._signals, signal_name)
                    signal.connect(lambda d: received_data.append(d))

                    getattr(window, method_name)()

                    assert len(received_data) == 0
                finally:
                    window.close()
                    window.deleteLater()


# =============================================================================
# main.py Tests - Fetch Methods
# =============================================================================


class TestDashboardFetchMethods:
    """Tests for DashboardWindow fetch methods."""

    def test_fetch_monitoring_data_success(self, qapp, mock_api_client_for_window):
        """_fetch_monitoring_data fetches and emits monitoring data."""
        from opencode_monitor.dashboard.window import DashboardWindow
        from opencode_monitor.core.models import Tool

        agent = make_mock_agent(tools=[Tool(name="bash", arg="ls -la", elapsed_ms=100)])
        mock_state = make_mock_state(
            agents=[agent], pending_todos=2, in_progress_todos=1
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

    def test_fetch_security_data_success(self, qapp, mock_api_client_for_window):
        """_fetch_security_data fetches and emits security data via API."""
        from opencode_monitor.dashboard.window import DashboardWindow

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

    def test_fetch_monitoring_with_waiting_agents(
        self, qapp, mock_api_client_for_window
    ):
        """_fetch_monitoring_data correctly processes agents with pending ask_user."""
        from opencode_monitor.dashboard.window import DashboardWindow

        agent = make_mock_agent(
            agent_id="agent-wait",
            title="Waiting Agent",
            has_pending_ask_user=True,
            ask_user_title="Need Input",
            ask_user_question="What next?",
            ask_user_options=["Option A", "Option B"],
            ask_user_agent="my-agent",
            ask_user_branch="main",
        )
        mock_state = make_mock_state(agents=[agent], tty="")

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

    def test_fetch_monitoring_idle_instance_count(
        self, qapp, mock_api_client_for_window
    ):
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
        mock_client.get_sync_status.return_value = {"backfill_active": False}

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
        mock_client.get_sync_status.return_value = {"backfill_active": False}

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

    def test_fetch_security_with_critical_items(self, qapp, mock_api_client_for_window):
        """_fetch_security_data processes critical items from all sources via API."""
        from opencode_monitor.dashboard.window import DashboardWindow

        # Mock API to return security data with all item types
        mock_api_client_for_window.get_security_data.return_value = {
            "stats": {"critical": 2, "high": 2},
            "commands": [],
            "files": [
                {
                    "operation": "READ",
                    "path": "/home/user/file.txt",
                    "risk": "low",
                    "score": 10,
                    "reason": "Normal read",
                },
                {
                    "operation": "WRITE",
                    "path": "/tmp/output.txt",
                    "risk": "low",
                    "score": 5,
                    "reason": "Normal write",
                },
            ],
            "critical_items": [
                {
                    "type": "COMMAND",
                    "details": "rm -rf /",
                    "risk": "critical",
                    "reason": "Dangerous",
                    "score": 100,
                },
                {
                    "type": "READ",
                    "details": "/etc/passwd",
                    "risk": "high",
                    "reason": "Sensitive file",
                    "score": 80,
                },
                {
                    "type": "WRITE",
                    "details": "/etc/shadow",
                    "risk": "critical",
                    "reason": "Password file",
                    "score": 95,
                },
                {
                    "type": "WEBFETCH",
                    "details": "http://malware.com",
                    "risk": "high",
                    "reason": "Suspicious URL",
                    "score": 85,
                },
            ],
        }

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

    def test_fetch_monitoring_with_repo_context(self, qapp, mock_api_client_for_window):
        """_fetch_monitoring_data uses repo when agent name not available."""
        from opencode_monitor.dashboard.window import DashboardWindow

        # Agent with ask_user_repo but no ask_user_agent
        agent = make_mock_agent(
            agent_id="agent-repo",
            title="Repo Agent",
            has_pending_ask_user=True,
            ask_user_title="Input needed",
            ask_user_question="Question?",
            ask_user_agent="",  # No agent name
            ask_user_repo="my-repo",  # Has repo
            ask_user_branch="feature",
        )
        mock_state = make_mock_state(agents=[agent], tty="")

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


# =============================================================================
# AnalyticsSection Tests - Key Format Compatibility
# =============================================================================


class TestAnalyticsSectionKeyFormats:
    """Tests for AnalyticsSection handling of different key formats.

    The API returns data with keys 'tool' and 'skill', but we should
    also accept 'tool_name' and 'skill_name' for backward compatibility.
    """

    @pytest.fixture
    def analytics_section(self, qapp):
        """Create AnalyticsSection for testing."""
        from opencode_monitor.dashboard.sections.analytics import AnalyticsSection

        section = AnalyticsSection()
        yield section
        section.deleteLater()

    def test_update_data_with_tool_key(self, analytics_section):
        """AnalyticsSection accepts 'tool' key (API format)."""
        # API format uses 'tool' key
        tools = [
            {"tool": "bash", "invocations": 10, "failures": 1, "failure_rate": "10.0%"},
            {"tool": "read", "invocations": 5, "failures": 0, "failure_rate": "0.0%"},
        ]

        analytics_section.update_data(
            sessions=10,
            messages=100,
            tokens="5K",
            cache_hit="60%",
            agents=[],
            tools=tools,
            skills=[],
        )

        # Verify data was processed - check first row in tools table
        assert analytics_section._tools_table.rowCount() == 2
        assert analytics_section._tools_table.item(0, 0).text() == "bash"

    def test_update_data_with_tool_name_key(self, analytics_section):
        """AnalyticsSection accepts 'tool_name' key (fallback format)."""
        # Fallback format uses 'tool_name' key
        tools = [
            {
                "tool_name": "write",
                "invocations": 8,
                "failures": 2,
                "failure_rate": "25.0%",
            },
        ]

        analytics_section.update_data(
            sessions=5,
            messages=50,
            tokens="2K",
            cache_hit="40%",
            agents=[],
            tools=tools,
            skills=[],
        )

        # Verify data was processed
        assert analytics_section._tools_table.rowCount() == 1
        assert analytics_section._tools_table.item(0, 0).text() == "write"

    def test_update_data_with_skill_key(self, analytics_section):
        """AnalyticsSection accepts 'skill' key (API format)."""
        # API format uses 'skill' key
        skills = [
            {"skill": "functional-testing", "load_count": 5},
            {"skill": "agentic-flow", "load_count": 3},
        ]

        analytics_section.update_data(
            sessions=10,
            messages=100,
            tokens="5K",
            cache_hit="60%",
            agents=[],
            tools=[],
            skills=skills,
        )

        # Verify data was processed
        assert analytics_section._skills_table.rowCount() == 2
        assert analytics_section._skills_table.item(0, 0).text() == "functional-testing"

    def test_update_data_with_skill_name_key(self, analytics_section):
        """AnalyticsSection accepts 'skill_name' key (fallback format)."""
        # Fallback format uses 'skill_name' key
        skills = [
            {"skill_name": "qml-testing", "load_count": 2},
        ]

        analytics_section.update_data(
            sessions=5,
            messages=50,
            tokens="2K",
            cache_hit="40%",
            agents=[],
            tools=[],
            skills=skills,
        )

        # Verify data was processed
        assert analytics_section._skills_table.rowCount() == 1
        assert analytics_section._skills_table.item(0, 0).text() == "qml-testing"

    def test_update_data_uses_api_failure_rate(self, analytics_section):
        """AnalyticsSection uses failure_rate from API if available."""
        # API provides pre-calculated failure_rate
        tools = [
            {"tool": "bash", "invocations": 10, "failures": 2, "failure_rate": "20.0%"},
        ]

        analytics_section.update_data(
            sessions=10,
            messages=100,
            tokens="5K",
            cache_hit="60%",
            agents=[],
            tools=tools,
            skills=[],
        )

        # Check that failure_rate from API is displayed (column 3)
        assert analytics_section._tools_table.item(0, 3).text() == "20.0%"

    def test_update_data_calculates_failure_rate_if_missing(self, analytics_section):
        """AnalyticsSection calculates failure_rate if not provided by API."""
        # No failure_rate provided - should calculate
        tools = [
            {"tool": "bash", "invocations": 10, "failures": 3},
        ]

        analytics_section.update_data(
            sessions=10,
            messages=100,
            tokens="5K",
            cache_hit="60%",
            agents=[],
            tools=tools,
            skills=[],
        )

        # Should calculate 3/10 = 30%
        assert analytics_section._tools_table.item(0, 3).text() == "30.0%"

    def test_update_data_agents_format(self, analytics_section):
        """AnalyticsSection correctly processes agents data."""
        agents = [
            {"agent": "executor", "messages": 50, "tokens": 10000},
            {"agent": "tester", "messages": 30, "tokens": 5000},
        ]

        analytics_section.update_data(
            sessions=10,
            messages=100,
            tokens="15K",
            cache_hit="60%",
            agents=agents,
            tools=[],
            skills=[],
        )

        # Verify agents table has data
        assert analytics_section._agents_table.rowCount() == 2
        assert analytics_section._agents_table.item(0, 0).text() == "executor"
        # Share column (index 3) should show percentage
        share_text = analytics_section._agents_table.item(0, 3).text()
        assert "%" in share_text
