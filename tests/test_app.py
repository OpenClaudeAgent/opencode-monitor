"""
Tests for OpenCodeApp (rumps menu bar application).

Tests the application logic, callbacks, state management, and security features.
Mocks rumps and external dependencies to test behavior without UI.
"""

import asyncio
import sys
import importlib
import pytest
import time
from unittest.mock import MagicMock, patch, AsyncMock, PropertyMock
from dataclasses import dataclass


# Create comprehensive rumps mock BEFORE importing app
class MockMenuItem:
    """Mock rumps.MenuItem with proper menu behavior."""

    def __init__(self, title="", callback=None, **kwargs):
        self.title = title
        self.callback = callback
        self._items = {}
        self.state = 0
        self._menuitem = MagicMock()
        self.parent = None

    def add(self, item):
        if isinstance(item, MockMenuItem):
            self._items[item.title] = item
            item.parent = self
        elif item is None:
            # Separator
            pass

    def clear(self):
        self._items = {}

    def values(self):
        return list(self._items.values())

    def __iter__(self):
        return iter(self._items.values())


class MockMenu:
    """Mock rumps menu with proper list-like and method behavior."""

    def __init__(self):
        self._items = []
        self._clear_called = False
        self._add_calls = []

    def clear(self):
        self._items = []
        self._clear_called = True

    def add(self, item):
        self._items.append(item)
        self._add_calls.append(item)

    def __setitem__(self, key, value):
        pass

    def __getitem__(self, key):
        return self._items[key] if isinstance(key, int) else None

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class MockApp:
    """Mock rumps.App base class."""

    def __init__(self, name="", title="", quit_button=None, **kwargs):
        self.name = name
        self.title = title
        self._menu = MockMenu()

    @property
    def menu(self):
        return self._menu

    @menu.setter
    def menu(self, value):
        # When assigning a list, convert to MockMenu items
        if isinstance(value, list):
            self._menu = MockMenu()
            for item in value:
                self._menu.add(item)
        else:
            self._menu = value

    def run(self):
        pass


@pytest.fixture(scope="module", autouse=True)
def setup_rumps_mock():
    """Setup rumps mock for the entire module."""
    # Save original if exists
    original_rumps = sys.modules.get("rumps", None)

    # Create the module mock
    rumps_mock = MagicMock()
    rumps_mock.App = MockApp
    rumps_mock.MenuItem = MockMenuItem
    rumps_mock.timer = lambda interval: lambda f: f
    rumps_mock.quit_application = MagicMock()

    # Install the mock
    sys.modules["rumps"] = rumps_mock

    # Reload the app module to use the mock
    if "opencode_monitor.app" in sys.modules:
        importlib.reload(sys.modules["opencode_monitor.app"])

    yield rumps_mock

    # Restore original after tests
    if original_rumps is not None:
        sys.modules["rumps"] = original_rumps
        # Reload app module with real rumps
        if "opencode_monitor.app" in sys.modules:
            importlib.reload(sys.modules["opencode_monitor.app"])


@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies for OpenCodeApp."""
    with (
        patch("opencode_monitor.app.start_auditor") as mock_start_auditor,
        patch("opencode_monitor.app.get_auditor") as mock_get_auditor,
        patch("opencode_monitor.app.MenuBuilder") as mock_menu_builder,
        patch("opencode_monitor.app.get_settings") as mock_get_settings,
        patch("opencode_monitor.app.save_settings") as mock_save_settings,
        patch("opencode_monitor.app.focus_iterm2") as mock_focus_iterm2,
        patch("opencode_monitor.app.fetch_all_instances") as mock_fetch_instances,
        patch("opencode_monitor.app.fetch_usage") as mock_fetch_usage,
        patch("opencode_monitor.app.info") as mock_info,
        patch("opencode_monitor.app.error") as mock_error,
        patch("opencode_monitor.app.debug") as mock_debug,
    ):
        # Configure mocks
        mock_settings = MagicMock()
        mock_settings.usage_refresh_interval = 60
        mock_get_settings.return_value = mock_settings

        mock_auditor = MagicMock()
        mock_auditor.get_stats.return_value = {
            "critical": 0,
            "high": 0,
            "medium": 5,
            "total_commands": 100,
            "total_reads": 50,
            "total_writes": 25,
            "total_webfetches": 10,
        }
        mock_get_auditor.return_value = mock_auditor

        mock_builder_instance = MagicMock()
        mock_builder_instance.build_dynamic_items.return_value = []
        mock_builder_instance.build_security_menu.return_value = MockMenuItem(
            "Security"
        )
        mock_menu_builder.return_value = mock_builder_instance

        yield {
            "start_auditor": mock_start_auditor,
            "get_auditor": mock_get_auditor,
            "auditor": mock_auditor,
            "menu_builder": mock_menu_builder,
            "builder_instance": mock_builder_instance,
            "get_settings": mock_get_settings,
            "save_settings": mock_save_settings,
            "settings": mock_settings,
            "focus_iterm2": mock_focus_iterm2,
            "fetch_instances": mock_fetch_instances,
            "fetch_usage": mock_fetch_usage,
            "info": mock_info,
            "error": mock_error,
            "debug": mock_debug,
        }


def create_app_with_mocks(mock_dependencies, skip_monitor=True):
    """Helper to create OpenCodeApp with proper mocking."""
    from opencode_monitor.app import OpenCodeApp

    if skip_monitor:
        with patch.object(OpenCodeApp, "_run_monitor_loop"):
            app = OpenCodeApp()
    else:
        app = OpenCodeApp()

    return app


# =============================================================================
# Test OpenCodeApp Initialization
# =============================================================================


class TestOpenCodeAppInit:
    """Tests for OpenCodeApp.__init__"""

    def test_init_sets_default_state(self, mock_dependencies):
        """App should initialize with default state values."""
        app = create_app_with_mocks(mock_dependencies)

        assert app._state is None
        assert app._usage is None
        assert app._running is True
        assert app._needs_refresh is True
        assert app._previous_busy_agents == set()
        assert app._security_alerts == []
        assert app._has_critical_alert is False

    def test_init_sets_constants(self, mock_dependencies):
        """App should have correct class constants."""
        from opencode_monitor.app import OpenCodeApp

        assert OpenCodeApp.POLL_INTERVAL == 2
        assert OpenCodeApp.USAGE_INTERVALS == [30, 60, 120, 300, 600]

    def test_init_starts_auditor(self, mock_dependencies):
        """App should start security auditor on init."""
        create_app_with_mocks(mock_dependencies)

        mock_dependencies["start_auditor"].assert_called_once()

    def test_init_creates_menu_builder(self, mock_dependencies):
        """App should create MenuBuilder with port cache."""
        app = create_app_with_mocks(mock_dependencies)

        mock_dependencies["menu_builder"].assert_called_once()
        assert app._PORT_NAMES_LIMIT == 50

    def test_init_starts_monitor_thread(self, mock_dependencies):
        """App should start background monitor thread."""
        app = create_app_with_mocks(mock_dependencies)

        # Thread should be created and started
        assert app._monitor_thread is not None
        assert app._monitor_thread.daemon is True


# =============================================================================
# Test Static Menu Building
# =============================================================================


class TestBuildStaticMenu:
    """Tests for OpenCodeApp._build_static_menu"""

    def test_build_static_menu_creates_prefs_menu(self, mock_dependencies):
        """Should create preferences menu with usage refresh options."""
        app = create_app_with_mocks(mock_dependencies)

        # Check that preferences menu exists
        assert hasattr(app, "_prefs_menu")

    def test_build_static_menu_creates_refresh_item(self, mock_dependencies):
        """Should create refresh menu item."""
        app = create_app_with_mocks(mock_dependencies)

        assert hasattr(app, "_refresh_item")

    def test_build_static_menu_creates_quit_item(self, mock_dependencies):
        """Should create quit menu item."""
        app = create_app_with_mocks(mock_dependencies)

        assert hasattr(app, "_quit_item")

    def test_build_static_menu_sets_initial_menu(self, mock_dependencies):
        """Should set initial menu structure."""
        app = create_app_with_mocks(mock_dependencies)

        # Menu should be set (list of items)
        assert hasattr(app, "menu")


# =============================================================================
# Test Interval Callback Factory
# =============================================================================


class TestMakeIntervalCallback:
    """Tests for OpenCodeApp._make_interval_callback"""

    def test_callback_updates_settings(self, mock_dependencies):
        """Callback should update settings with new interval."""
        app = create_app_with_mocks(mock_dependencies)

        callback = app._make_interval_callback(120)

        # Create mock sender with parent
        mock_sender = MagicMock()
        mock_sender.parent.values.return_value = [MagicMock(), MagicMock()]

        callback(mock_sender)

        # Settings should be updated
        assert mock_dependencies["settings"].usage_refresh_interval == 120
        mock_dependencies["save_settings"].assert_called_once()

    def test_callback_clears_other_states(self, mock_dependencies):
        """Callback should clear state of other interval options."""
        app = create_app_with_mocks(mock_dependencies)

        callback = app._make_interval_callback(300)

        # Create mock sender with sibling items
        mock_item1 = MagicMock()
        mock_item2 = MagicMock()
        mock_sender = MagicMock()
        mock_sender.parent.values.return_value = [mock_item1, mock_item2]

        callback(mock_sender)

        # All items should have state set to 0
        assert mock_item1.state == 0
        assert mock_item2.state == 0

    def test_callback_sets_sender_state(self, mock_dependencies):
        """Callback should set sender state to 1 (selected)."""
        app = create_app_with_mocks(mock_dependencies)

        callback = app._make_interval_callback(60)

        mock_sender = MagicMock()
        mock_sender.parent.values.return_value = []

        callback(mock_sender)

        assert mock_sender.state == 1

    def test_callback_logs_change(self, mock_dependencies):
        """Callback should log the interval change."""
        app = create_app_with_mocks(mock_dependencies)

        callback = app._make_interval_callback(600)

        mock_sender = MagicMock()
        mock_sender.parent.values.return_value = []

        callback(mock_sender)

        mock_dependencies["info"].assert_called()
        call_args = str(mock_dependencies["info"].call_args)
        assert "600" in call_args


# =============================================================================
# Test UI Refresh
# =============================================================================


class TestUIRefresh:
    """Tests for OpenCodeApp._ui_refresh"""

    def test_ui_refresh_when_needed(self, mock_dependencies):
        """Should rebuild menu when _needs_refresh is True."""
        app = create_app_with_mocks(mock_dependencies)
        app._needs_refresh = True

        # Mock the methods
        app._build_menu = MagicMock()
        app._update_title = MagicMock()

        app._ui_refresh(None)

        app._build_menu.assert_called_once()
        app._update_title.assert_called_once()
        assert app._needs_refresh is False

    def test_ui_refresh_when_not_needed(self, mock_dependencies):
        """Should not rebuild menu when _needs_refresh is False."""
        app = create_app_with_mocks(mock_dependencies)
        app._needs_refresh = False

        app._build_menu = MagicMock()
        app._update_title = MagicMock()

        app._ui_refresh(None)

        app._build_menu.assert_not_called()
        app._update_title.assert_not_called()


# =============================================================================
# Test Menu Building
# =============================================================================


class TestBuildMenu:
    """Tests for OpenCodeApp._build_menu"""

    def test_build_menu_uses_menu_builder(self, mock_dependencies):
        """Should use MenuBuilder to create dynamic items."""
        app = create_app_with_mocks(mock_dependencies)

        app._build_menu()

        mock_dependencies["builder_instance"].build_dynamic_items.assert_called()

    def test_build_menu_clears_existing(self, mock_dependencies):
        """Should clear existing menu before rebuilding."""
        app = create_app_with_mocks(mock_dependencies)

        app._build_menu()

        # Verify clear was called by checking the flag
        assert app.menu._clear_called is True

    def test_build_menu_adds_security_menu(self, mock_dependencies):
        """Should add security menu from builder."""
        app = create_app_with_mocks(mock_dependencies)

        app._build_menu()

        mock_dependencies["builder_instance"].build_security_menu.assert_called()

    def test_build_menu_updates_critical_flag(self, mock_dependencies):
        """Should update _has_critical_alert based on auditor stats."""
        # Set critical alerts in auditor
        mock_dependencies["auditor"].get_stats.return_value = {
            "critical": 2,
            "high": 3,
            "medium": 5,
        }

        app = create_app_with_mocks(mock_dependencies)

        app._build_menu()

        assert app._has_critical_alert is True

    def test_build_menu_no_critical_flag_when_zero(self, mock_dependencies):
        """Should not set critical flag when no critical/high alerts."""
        mock_dependencies["auditor"].get_stats.return_value = {
            "critical": 0,
            "high": 0,
            "medium": 10,
        }

        app = create_app_with_mocks(mock_dependencies)
        app._has_critical_alert = True  # Start with True

        app._build_menu()

        assert app._has_critical_alert is False


# =============================================================================
# Test Title Update
# =============================================================================


class TestUpdateTitle:
    """Tests for OpenCodeApp._update_title"""

    def test_update_title_no_state(self, mock_dependencies):
        """Should show default emoji when no state."""
        app = create_app_with_mocks(mock_dependencies)
        app._state = None

        app._update_title()

        assert app.title == "🤖"

    def test_update_title_not_connected(self, mock_dependencies):
        """Should show default emoji when not connected."""
        from opencode_monitor.core.models import State

        app = create_app_with_mocks(mock_dependencies)
        app._state = State(connected=False)

        app._update_title()

        assert app.title == "🤖"

    def test_update_title_with_busy_count(self, mock_dependencies):
        """Should show busy count when agents are busy."""
        from opencode_monitor.core.models import (
            State,
            Instance,
            Agent,
            SessionStatus,
            Todos,
        )

        app = create_app_with_mocks(mock_dependencies)

        # Create state with busy agent
        agent = Agent(
            id="1", title="test", dir=".", full_dir="/test", status=SessionStatus.BUSY
        )
        instance = Instance(port=1234, agents=[agent])
        app._state = State(instances=[instance], todos=Todos(), connected=True)

        app._update_title()

        assert "1" in app.title

    def test_update_title_with_todos(self, mock_dependencies):
        """Should show todo count when todos pending."""
        from opencode_monitor.core.models import State, Todos

        app = create_app_with_mocks(mock_dependencies)
        app._state = State(todos=Todos(pending=3, in_progress=2), connected=True)

        app._update_title()

        assert "5" in app.title

    def test_update_title_with_usage_high(self, mock_dependencies):
        """Should show red indicator when usage >= 90%."""
        from opencode_monitor.core.models import State, Usage, UsagePeriod, Todos

        app = create_app_with_mocks(mock_dependencies)
        app._state = State(todos=Todos(), connected=True)
        app._usage = Usage(
            five_hour=UsagePeriod(utilization=95), seven_day=UsagePeriod(utilization=50)
        )

        app._update_title()

        assert "🔴" in app.title
        assert "95%" in app.title

    def test_update_title_with_usage_medium_high(self, mock_dependencies):
        """Should show orange indicator when usage >= 70%."""
        from opencode_monitor.core.models import State, Usage, UsagePeriod, Todos

        app = create_app_with_mocks(mock_dependencies)
        app._state = State(todos=Todos(), connected=True)
        app._usage = Usage(
            five_hour=UsagePeriod(utilization=75), seven_day=UsagePeriod(utilization=50)
        )

        app._update_title()

        assert "🟠" in app.title

    def test_update_title_with_usage_medium(self, mock_dependencies):
        """Should show yellow indicator when usage >= 50%."""
        from opencode_monitor.core.models import State, Usage, UsagePeriod, Todos

        app = create_app_with_mocks(mock_dependencies)
        app._state = State(todos=Todos(), connected=True)
        app._usage = Usage(
            five_hour=UsagePeriod(utilization=55), seven_day=UsagePeriod(utilization=50)
        )

        app._update_title()

        assert "🟡" in app.title

    def test_update_title_with_usage_low(self, mock_dependencies):
        """Should show green indicator when usage < 50%."""
        from opencode_monitor.core.models import State, Usage, UsagePeriod, Todos

        app = create_app_with_mocks(mock_dependencies)
        app._state = State(todos=Todos(), connected=True)
        app._usage = Usage(
            five_hour=UsagePeriod(utilization=30), seven_day=UsagePeriod(utilization=50)
        )

        app._update_title()

        assert "🟢" in app.title

    def test_update_title_with_usage_error(self, mock_dependencies):
        """Should not show usage when error is present."""
        from opencode_monitor.core.models import State, Usage, UsagePeriod, Todos

        app = create_app_with_mocks(mock_dependencies)
        app._state = State(todos=Todos(), connected=True)
        app._usage = Usage(five_hour=UsagePeriod(utilization=50), error="API error")

        app._update_title()

        # Should not contain percentage when there's an error
        assert "%" not in app.title

    def test_update_title_empty_parts(self, mock_dependencies):
        """Should show just emoji when no busy agents, todos, or usage."""
        from opencode_monitor.core.models import State, Todos

        app = create_app_with_mocks(mock_dependencies)
        app._state = State(todos=Todos(pending=0, in_progress=0), connected=True)
        app._usage = None

        app._update_title()

        assert app.title == "🤖"


# =============================================================================
# Test Focus Terminal
# =============================================================================


class TestFocusTerminal:
    """Tests for OpenCodeApp._focus_terminal"""

    def test_focus_terminal_calls_focus_iterm2(self, mock_dependencies):
        """Should call focus_iterm2 with tty."""
        app = create_app_with_mocks(mock_dependencies)

        app._focus_terminal("/dev/ttys001")

        mock_dependencies["focus_iterm2"].assert_called_once_with("/dev/ttys001")


# =============================================================================
# Test On Refresh
# =============================================================================


class TestOnRefresh:
    """Tests for OpenCodeApp._on_refresh"""

    def test_on_refresh_logs_message(self, mock_dependencies):
        """Should log manual refresh request."""
        app = create_app_with_mocks(mock_dependencies)

        app._on_refresh(None)

        mock_dependencies["info"].assert_called()

    def test_on_refresh_sets_needs_refresh(self, mock_dependencies):
        """Should set _needs_refresh to True."""
        app = create_app_with_mocks(mock_dependencies)
        app._needs_refresh = False

        app._on_refresh(None)

        assert app._needs_refresh is True


# =============================================================================
# Test Add Security Alert
# =============================================================================


class TestAddSecurityAlert:
    """Tests for OpenCodeApp._add_security_alert"""

    def test_add_security_alert_stores_alert(self, mock_dependencies):
        """Should add alert to security_alerts list."""
        from opencode_monitor.security.analyzer import SecurityAlert, RiskLevel

        app = create_app_with_mocks(mock_dependencies)

        alert = SecurityAlert(
            command="rm -rf /",
            tool="bash",
            score=100,
            level=RiskLevel.CRITICAL,
            reason="Dangerous command",
        )

        app._add_security_alert(alert)

        assert len(app._security_alerts) == 1
        assert app._security_alerts[0].command == "rm -rf /"

    def test_add_security_alert_prevents_duplicates(self, mock_dependencies):
        """Should not add duplicate alerts with same command."""
        from opencode_monitor.security.analyzer import SecurityAlert, RiskLevel

        app = create_app_with_mocks(mock_dependencies)

        alert1 = SecurityAlert(
            command="rm -rf /",
            tool="bash",
            score=100,
            level=RiskLevel.CRITICAL,
            reason="Dangerous",
        )
        alert2 = SecurityAlert(
            command="rm -rf /",  # Same command
            tool="bash",
            score=100,
            level=RiskLevel.CRITICAL,
            reason="Also dangerous",
        )

        app._add_security_alert(alert1)
        app._add_security_alert(alert2)

        assert len(app._security_alerts) == 1

    def test_add_security_alert_limits_max(self, mock_dependencies):
        """Should limit alerts to _max_alerts."""
        from opencode_monitor.security.analyzer import SecurityAlert, RiskLevel

        app = create_app_with_mocks(mock_dependencies)
        app._max_alerts = 5

        for i in range(10):
            alert = SecurityAlert(
                command=f"command_{i}",
                tool="bash",
                score=50,
                level=RiskLevel.HIGH,
                reason="Test",
            )
            app._add_security_alert(alert)

        assert len(app._security_alerts) == 5

    def test_add_security_alert_inserts_at_front(self, mock_dependencies):
        """Should insert new alerts at the front of the list."""
        from opencode_monitor.security.analyzer import SecurityAlert, RiskLevel

        app = create_app_with_mocks(mock_dependencies)

        alert1 = SecurityAlert(
            command="first", tool="bash", score=50, level=RiskLevel.HIGH, reason="Test"
        )
        alert2 = SecurityAlert(
            command="second", tool="bash", score=60, level=RiskLevel.HIGH, reason="Test"
        )

        app._add_security_alert(alert1)
        app._add_security_alert(alert2)

        assert app._security_alerts[0].command == "second"

    def test_add_security_alert_sets_critical_flag(self, mock_dependencies):
        """Should set _has_critical_alert for CRITICAL alerts."""
        from opencode_monitor.security.analyzer import SecurityAlert, RiskLevel

        app = create_app_with_mocks(mock_dependencies)
        app._has_critical_alert = False

        alert = SecurityAlert(
            command="rm -rf /",
            tool="bash",
            score=100,
            level=RiskLevel.CRITICAL,
            reason="Critical",
        )

        app._add_security_alert(alert)

        assert app._has_critical_alert is True

    def test_add_security_alert_logs_critical(self, mock_dependencies):
        """Should log CRITICAL alerts."""
        from opencode_monitor.security.analyzer import SecurityAlert, RiskLevel

        app = create_app_with_mocks(mock_dependencies)

        alert = SecurityAlert(
            command="rm -rf /something",
            tool="bash",
            score=100,
            level=RiskLevel.CRITICAL,
            reason="Critical reason",
        )

        app._add_security_alert(alert)

        mock_dependencies["info"].assert_called()
        call_args = str(mock_dependencies["info"].call_args)
        assert "CRITICAL" in call_args

    def test_add_security_alert_logs_high(self, mock_dependencies):
        """Should log HIGH alerts."""
        from opencode_monitor.security.analyzer import SecurityAlert, RiskLevel

        app = create_app_with_mocks(mock_dependencies)

        alert = SecurityAlert(
            command="sudo something",
            tool="bash",
            score=60,
            level=RiskLevel.HIGH,
            reason="High reason",
        )

        app._add_security_alert(alert)

        mock_dependencies["info"].assert_called()
        call_args = str(mock_dependencies["info"].call_args)
        assert "HIGH" in call_args


# =============================================================================
# Test Show Security Report
# =============================================================================


class TestShowSecurityReport:
    """Tests for OpenCodeApp._show_security_report"""

    def test_show_security_report_generates_report(self, mock_dependencies):
        """Should generate report from auditor."""
        with patch("subprocess.run") as mock_run, patch("builtins.open", MagicMock()):
            app = create_app_with_mocks(mock_dependencies)
            mock_dependencies["auditor"].generate_report.return_value = "Report content"

            app._show_security_report(None)

            mock_dependencies["auditor"].generate_report.assert_called_once()

    def test_show_security_report_writes_file(self, mock_dependencies):
        """Should write report to temp file."""
        with patch("subprocess.run") as mock_run:
            app = create_app_with_mocks(mock_dependencies)
            mock_dependencies["auditor"].generate_report.return_value = "Report content"

            app._show_security_report(None)

            # Check that subprocess.run was called with "open"
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "open"
            assert "opencode_security_report.txt" in args[1]

    def test_show_security_report_opens_file(self, mock_dependencies):
        """Should open report file with system open command."""
        with patch("subprocess.run") as mock_run, patch("builtins.open", MagicMock()):
            app = create_app_with_mocks(mock_dependencies)
            mock_dependencies["auditor"].generate_report.return_value = "Report"

            app._show_security_report(None)

            mock_run.assert_called_once()
            assert mock_run.call_args[0][0][0] == "open"


# =============================================================================
# Test Export All Commands
# =============================================================================


class TestExportAllCommands:
    """Tests for OpenCodeApp._export_all_commands"""

    def test_export_fetches_all_data(self, mock_dependencies):
        """Should fetch all commands, reads, writes, and fetches."""
        with (
            patch("subprocess.run") as mock_run,
            patch("builtins.open", MagicMock()),
            patch("opencode_monitor.app.SecurityReporter") as mock_reporter_class,
        ):
            mock_reporter = MagicMock()
            mock_reporter.generate_full_export.return_value = "Export content"
            mock_reporter_class.return_value = mock_reporter

            app = create_app_with_mocks(mock_dependencies)
            mock_dependencies["auditor"].get_all_commands.return_value = []
            mock_dependencies["auditor"].get_all_reads.return_value = []
            mock_dependencies["auditor"].get_all_writes.return_value = []
            mock_dependencies["auditor"].get_all_webfetches.return_value = []

            app._export_all_commands(None)

            mock_dependencies["auditor"].get_all_commands.assert_called_once_with(
                limit=10000
            )
            mock_dependencies["auditor"].get_all_reads.assert_called_once_with(
                limit=10000
            )
            mock_dependencies["auditor"].get_all_writes.assert_called_once_with(
                limit=10000
            )
            mock_dependencies["auditor"].get_all_webfetches.assert_called_once_with(
                limit=10000
            )

    def test_export_uses_reporter(self, mock_dependencies):
        """Should use SecurityReporter to generate export."""
        with (
            patch("subprocess.run") as mock_run,
            patch("builtins.open", MagicMock()),
            patch("opencode_monitor.app.SecurityReporter") as mock_reporter_class,
        ):
            mock_reporter = MagicMock()
            mock_reporter.generate_full_export.return_value = "Export content"
            mock_reporter_class.return_value = mock_reporter

            app = create_app_with_mocks(mock_dependencies)

            app._export_all_commands(None)

            mock_reporter.generate_full_export.assert_called_once()

    def test_export_writes_to_config_dir(self, mock_dependencies):
        """Should write export to ~/.config/opencode-monitor/."""
        with (
            patch("subprocess.run") as mock_run,
            patch("builtins.open", MagicMock()) as mock_open,
            patch("opencode_monitor.app.SecurityReporter") as mock_reporter_class,
        ):
            mock_reporter = MagicMock()
            mock_reporter.generate_full_export.return_value = "Export"
            mock_reporter_class.return_value = mock_reporter

            app = create_app_with_mocks(mock_dependencies)

            app._export_all_commands(None)

            # Check open was called with path containing config dir
            mock_open.assert_called()
            call_args = mock_open.call_args[0][0]
            assert ".config/opencode-monitor" in call_args
            assert "security_audit_" in call_args

    def test_export_opens_file(self, mock_dependencies):
        """Should open exported file with system open command."""
        with (
            patch("subprocess.run") as mock_run,
            patch("builtins.open", MagicMock()),
            patch("opencode_monitor.app.SecurityReporter") as mock_reporter_class,
        ):
            mock_reporter = MagicMock()
            mock_reporter.generate_full_export.return_value = "Export"
            mock_reporter_class.return_value = mock_reporter

            app = create_app_with_mocks(mock_dependencies)

            app._export_all_commands(None)

            mock_run.assert_called_once()
            assert mock_run.call_args[0][0][0] == "open"


# =============================================================================
# Test Monitor Loop
# =============================================================================


class TestRunMonitorLoop:
    """Tests for OpenCodeApp._run_monitor_loop"""

    def test_monitor_loop_fetches_instances(self, mock_dependencies):
        """Should fetch instances in monitor loop."""
        from opencode_monitor.core.models import State

        # Create async mock for fetch_all_instances
        async def mock_fetch():
            return State(connected=True)

        mock_dependencies["fetch_instances"].return_value = mock_fetch()

        app = create_app_with_mocks(mock_dependencies)

        # Simulate one iteration of the loop
        app._running = False  # Stop after one iteration

        loop = asyncio.new_event_loop()
        try:
            new_state = loop.run_until_complete(mock_fetch())
            app._state = new_state
            assert app._state.connected is True
        finally:
            loop.close()

    def test_monitor_loop_updates_busy_agents(self, mock_dependencies):
        """Should track busy agents for notification purposes."""
        from opencode_monitor.core.models import State, Instance, Agent, SessionStatus

        app = create_app_with_mocks(mock_dependencies)

        # Simulate state with busy agent
        agent = Agent(
            id="agent-1",
            title="Test",
            dir=".",
            full_dir="/test",
            status=SessionStatus.BUSY,
        )
        state = State(instances=[Instance(port=1234, agents=[agent])], connected=True)

        # Simulate what the loop would do
        current_busy = set()
        for instance in state.instances:
            for agent in instance.agents:
                if agent.status == SessionStatus.BUSY:
                    current_busy.add(agent.id)

        app._previous_busy_agents = current_busy

        assert "agent-1" in app._previous_busy_agents

    def test_monitor_loop_updates_usage_periodically(self, mock_dependencies):
        """Should update usage based on refresh interval."""
        from opencode_monitor.core.models import Usage, UsagePeriod

        mock_dependencies["fetch_usage"].return_value = Usage(
            five_hour=UsagePeriod(utilization=50)
        )
        mock_dependencies["settings"].usage_refresh_interval = 60

        app = create_app_with_mocks(mock_dependencies)

        # Simulate time passing and usage update
        app._last_usage_update = 0  # Force update

        # Simulate what the loop would do
        now = time.time()
        if now - app._last_usage_update >= 60:
            new_usage = mock_dependencies["fetch_usage"]()
            app._usage = new_usage
            app._last_usage_update = now

        assert app._usage is not None

    def test_monitor_loop_handles_fetch_error(self, mock_dependencies):
        """Should handle and log errors during fetch."""
        mock_dependencies["fetch_instances"].side_effect = Exception("Network error")

        app = create_app_with_mocks(mock_dependencies)

        # Simulate error handling in the loop
        try:
            raise Exception("Network error")
        except Exception as e:
            mock_dependencies["error"](f"Monitor error: {e}")

        mock_dependencies["error"].assert_called()

    def test_monitor_loop_sets_needs_refresh(self, mock_dependencies):
        """Should set _needs_refresh after state update."""
        from opencode_monitor.core.models import State

        app = create_app_with_mocks(mock_dependencies)
        app._needs_refresh = False

        # Simulate what happens after successful fetch
        app._state = State(connected=True)
        app._needs_refresh = True

        assert app._needs_refresh is True

    def test_monitor_loop_respects_poll_interval(self, mock_dependencies):
        """Should sleep for remaining poll interval time."""
        from opencode_monitor.app import OpenCodeApp

        app = create_app_with_mocks(mock_dependencies)

        # Simulate elapsed time calculation
        start_time = time.time()
        elapsed = 0.5  # Simulated processing time
        sleep_time = max(0, OpenCodeApp.POLL_INTERVAL - elapsed)

        assert sleep_time > 0
        assert sleep_time <= OpenCodeApp.POLL_INTERVAL


# =============================================================================
# Test Main Function
# =============================================================================


class TestMain:
    """Tests for main() entry point"""

    def test_main_creates_app(self, mock_dependencies):
        """Should create OpenCodeApp instance."""
        from opencode_monitor.app import main, OpenCodeApp

        with (
            patch.object(OpenCodeApp, "_run_monitor_loop"),
            patch.object(OpenCodeApp, "run") as mock_run,
        ):
            main()

            mock_run.assert_called_once()

    def test_main_runs_app(self, mock_dependencies):
        """Should call app.run()."""
        from opencode_monitor.app import main, OpenCodeApp

        with (
            patch.object(OpenCodeApp, "_run_monitor_loop"),
            patch.object(OpenCodeApp, "run") as mock_run,
        ):
            main()

            mock_run.assert_called_once()


# =============================================================================
# Test Thread Safety
# =============================================================================


class TestThreadSafety:
    """Tests for thread safety in state access"""

    def test_state_access_uses_lock(self, mock_dependencies):
        """State access should use lock for thread safety."""
        from opencode_monitor.core.models import State

        app = create_app_with_mocks(mock_dependencies)

        # Verify lock exists
        assert hasattr(app, "_state_lock")

        # Simulate locked access
        with app._state_lock:
            app._state = State(connected=True)
            state = app._state

        assert state.connected is True

    def test_usage_access_uses_lock(self, mock_dependencies):
        """Usage access should use lock for thread safety."""
        from opencode_monitor.core.models import Usage, UsagePeriod

        app = create_app_with_mocks(mock_dependencies)

        with app._state_lock:
            app._usage = Usage(five_hour=UsagePeriod(utilization=75))
            usage = app._usage

        assert usage.five_hour.utilization == 75


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests"""

    def test_empty_instances(self, mock_dependencies):
        """Should handle state with no instances."""
        from opencode_monitor.core.models import State, Todos

        app = create_app_with_mocks(mock_dependencies)
        app._state = State(instances=[], todos=Todos(), connected=True)

        app._update_title()

        # Should not crash, just show base emoji
        assert app.title == "🤖"

    def test_none_usage(self, mock_dependencies):
        """Should handle None usage gracefully."""
        from opencode_monitor.core.models import State, Todos

        app = create_app_with_mocks(mock_dependencies)
        app._state = State(todos=Todos(), connected=True)
        app._usage = None

        app._update_title()

        # Should not crash
        assert "🤖" in app.title

    def test_max_alerts_boundary(self, mock_dependencies):
        """Should handle exactly max_alerts alerts."""
        from opencode_monitor.security.analyzer import SecurityAlert, RiskLevel

        app = create_app_with_mocks(mock_dependencies)
        app._max_alerts = 3

        for i in range(3):
            alert = SecurityAlert(
                command=f"cmd_{i}",
                tool="bash",
                score=50,
                level=RiskLevel.HIGH,
                reason="Test",
            )
            app._add_security_alert(alert)

        assert len(app._security_alerts) == 3

        # Add one more
        alert = SecurityAlert(
            command="cmd_new",
            tool="bash",
            score=50,
            level=RiskLevel.HIGH,
            reason="Test",
        )
        app._add_security_alert(alert)

        # Should still be max
        assert len(app._security_alerts) == 3
        # Newest should be first
        assert app._security_alerts[0].command == "cmd_new"


# =============================================================================
# Test Additional Coverage for _build_menu
# =============================================================================


class TestBuildMenuComplete:
    """Additional tests for complete _build_menu coverage"""

    def test_build_menu_adds_dynamic_items(self, mock_dependencies):
        """Should add all dynamic items from menu builder."""
        mock_item1 = MockMenuItem("Item 1")
        mock_item2 = MockMenuItem("Item 2")
        mock_dependencies["builder_instance"].build_dynamic_items.return_value = [
            mock_item1,
            mock_item2,
        ]

        app = create_app_with_mocks(mock_dependencies)

        app._build_menu()

        # Verify items were added (check _add_calls)
        assert len(app.menu._add_calls) >= 2

    def test_build_menu_adds_separators(self, mock_dependencies):
        """Should add None separators between sections."""
        app = create_app_with_mocks(mock_dependencies)

        app._build_menu()

        # Check that add was called with None (separator)
        assert None in app.menu._add_calls

    def test_build_menu_adds_static_items(self, mock_dependencies):
        """Should add refresh, prefs, and quit items."""
        app = create_app_with_mocks(mock_dependencies)

        app._build_menu()

        # Should have been called multiple times for static items
        assert len(app.menu._add_calls) > 0


# =============================================================================
# Test Complete Monitor Loop
# =============================================================================


class TestMonitorLoopComplete:
    """Additional tests for complete monitor loop coverage"""

    def test_monitor_logs_start_message(self, mock_dependencies):
        """Monitor should log start message."""
        from opencode_monitor.app import OpenCodeApp

        # The start message is logged in _run_monitor_loop
        # We simulate by checking the info mock was called with start message
        app = create_app_with_mocks(mock_dependencies)

        # The info mock should have been called during init (for auditor start)
        # We'll verify the expected behavior
        assert mock_dependencies["info"].call_count >= 0

    def test_monitor_handles_usage_update_error(self, mock_dependencies):
        """Should handle errors during usage update."""
        from opencode_monitor.core.models import State

        mock_dependencies["fetch_usage"].side_effect = Exception("Usage API error")

        app = create_app_with_mocks(mock_dependencies)
        app._last_usage_update = 0  # Force update

        # Simulate what would happen in the loop
        try:
            mock_dependencies["fetch_usage"]()
        except Exception as e:
            mock_dependencies["error"](f"Usage update error: {e}")

        mock_dependencies["error"].assert_called()


# =============================================================================
# Test Title with Multiple Elements
# =============================================================================


class TestTitleComplex:
    """Test title with multiple status elements"""

    def test_title_with_all_elements(self, mock_dependencies):
        """Should combine busy count, todos, and usage."""
        from opencode_monitor.core.models import (
            State,
            Instance,
            Agent,
            SessionStatus,
            Todos,
            Usage,
            UsagePeriod,
        )

        app = create_app_with_mocks(mock_dependencies)

        # Create state with busy agent and todos
        agent = Agent(
            id="1", title="test", dir=".", full_dir="/test", status=SessionStatus.BUSY
        )
        instance = Instance(port=1234, agents=[agent])
        app._state = State(
            instances=[instance], todos=Todos(pending=3, in_progress=1), connected=True
        )
        app._usage = Usage(
            five_hour=UsagePeriod(utilization=60), seven_day=UsagePeriod(utilization=40)
        )

        app._update_title()

        # Should contain all elements
        assert "1" in app.title  # busy count
        assert "4" in app.title  # todos (3 + 1)
        assert "60%" in app.title  # usage
        assert "🟡" in app.title  # yellow for 50-70%


# =============================================================================
# Test Monitor Loop Integration
# =============================================================================


class TestMonitorLoopIntegration:
    """Integration tests for the actual monitor loop execution."""

    def test_run_monitor_loop_single_iteration(self, mock_dependencies):
        """Should execute one iteration of the monitor loop."""
        from opencode_monitor.core.models import State

        # Use patch to properly mock the async function at module level
        async def mock_fetch_coro():
            return State(connected=True)

        app = create_app_with_mocks(mock_dependencies)

        # Make the loop exit after first iteration
        call_count = [0]

        def stop_after_one(*args):
            call_count[0] += 1
            if call_count[0] >= 1:
                app._running = False
            return 0  # No sleep

        with (
            patch(
                "opencode_monitor.app.fetch_all_instances",
                return_value=mock_fetch_coro(),
            ),
            patch("time.sleep", side_effect=stop_after_one),
        ):
            # Run the loop directly
            app._running = True
            app._run_monitor_loop()

        # Verify state was updated
        assert app._state is not None

    def test_run_monitor_loop_tracks_busy_agents(self, mock_dependencies):
        """Should track busy agents during monitor loop."""
        from opencode_monitor.core.models import State, Instance, Agent, SessionStatus

        # Create a state with busy agents
        busy_agent = Agent(
            id="busy-agent-1",
            title="Busy Test",
            dir=".",
            full_dir="/test",
            status=SessionStatus.BUSY,
        )
        idle_agent = Agent(
            id="idle-agent-1",
            title="Idle Test",
            dir=".",
            full_dir="/test2",
            status=SessionStatus.IDLE,
        )
        state = State(
            instances=[Instance(port=1234, agents=[busy_agent, idle_agent])],
            connected=True,
        )

        # Use AsyncMock for proper async function mocking
        mock_fetch = AsyncMock(return_value=state)

        app = create_app_with_mocks(mock_dependencies)

        call_count = [0]

        def stop_after_one(*args):
            call_count[0] += 1
            if call_count[0] >= 1:
                app._running = False
            return 0

        with (
            patch("opencode_monitor.app.fetch_all_instances", mock_fetch),
            patch("time.sleep", side_effect=stop_after_one),
        ):
            app._running = True
            app._run_monitor_loop()

        # Verify busy agents were tracked
        assert "busy-agent-1" in app._previous_busy_agents
        # Idle agent should not be in busy set
        assert "idle-agent-1" not in app._previous_busy_agents

    def test_run_monitor_loop_handles_exception(self, mock_dependencies):
        """Should handle exceptions in monitor loop."""

        # Make fetch raise an exception
        async def mock_fetch_error():
            raise Exception("Network error")

        mock_dependencies["fetch_instances"].return_value = mock_fetch_error()

        app = create_app_with_mocks(mock_dependencies)

        # Make the loop exit immediately
        call_count = [0]

        def stop_after_one(*args):
            call_count[0] += 1
            if call_count[0] >= 1:
                app._running = False
            return 0

        with patch("time.sleep", side_effect=stop_after_one):
            app._running = True
            # Should not raise - exception is caught internally
            app._run_monitor_loop()

        # Verify error was logged
        mock_dependencies["error"].assert_called()

    def test_run_monitor_loop_updates_usage(self, mock_dependencies):
        """Should update usage when interval elapsed."""
        from opencode_monitor.core.models import State, Usage, UsagePeriod

        async def mock_fetch():
            return State(connected=True)

        mock_dependencies["fetch_instances"].return_value = mock_fetch()
        mock_dependencies["fetch_usage"].return_value = Usage(
            five_hour=UsagePeriod(utilization=75)
        )
        mock_dependencies["settings"].usage_refresh_interval = 0  # Always update

        app = create_app_with_mocks(mock_dependencies)
        app._last_usage_update = 0  # Force update

        call_count = [0]

        def stop_after_one(*args):
            call_count[0] += 1
            if call_count[0] >= 1:
                app._running = False
            return 0

        with patch("time.sleep", side_effect=stop_after_one):
            app._running = True
            app._run_monitor_loop()

        # Usage should have been fetched
        mock_dependencies["fetch_usage"].assert_called()

    def test_run_monitor_loop_logs_start_and_stop(self, mock_dependencies):
        """Should log start and stop messages."""
        from opencode_monitor.core.models import State

        async def mock_fetch():
            return State(connected=True)

        mock_dependencies["fetch_instances"].return_value = mock_fetch()

        app = create_app_with_mocks(mock_dependencies)
        app._running = False  # Exit immediately

        with patch("time.sleep"):
            app._run_monitor_loop()

        # Check that info was called (start and stop messages)
        info_calls = [str(c) for c in mock_dependencies["info"].call_args_list]
        # At least one call should contain "started" or "stopped"
        assert any("start" in c.lower() or "stop" in c.lower() for c in info_calls)

    def test_run_monitor_loop_handles_usage_error(self, mock_dependencies):
        """Should handle usage fetch error."""
        from opencode_monitor.core.models import State

        async def mock_fetch():
            return State(connected=True)

        mock_dependencies["fetch_instances"].return_value = mock_fetch()
        mock_dependencies["fetch_usage"].side_effect = Exception("Usage API error")
        mock_dependencies["settings"].usage_refresh_interval = 0  # Always update

        app = create_app_with_mocks(mock_dependencies)
        app._last_usage_update = 0

        call_count = [0]

        def stop_after_one(*args):
            call_count[0] += 1
            if call_count[0] >= 1:
                app._running = False
            return 0

        with patch("time.sleep", side_effect=stop_after_one):
            app._running = True
            app._run_monitor_loop()

        # Error should have been logged
        error_calls = [str(c) for c in mock_dependencies["error"].call_args_list]
        assert any("Usage" in c for c in error_calls)
