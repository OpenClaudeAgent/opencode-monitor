"""
Tests for OpenCodeApp (rumps menu bar application).

Tests the application logic, callbacks, state management, and security features.
Mocks rumps and external dependencies to test behavior without UI.

Consolidated tests: Each test validates multiple related assertions for better coverage.
"""

import sys
import pytest
from typing import cast
from unittest.mock import MagicMock, patch, AsyncMock

# Import RiskLevel at module level for parametrized tests
from opencode_monitor.security.analyzer import RiskLevel


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
    """Setup rumps mock for the entire module.

    Only mocks rumps itself. Does NOT reload app module here.
    The app module reload happens in mock_dependencies with all patches active.
    """
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

    # DON'T reload here - let mock_dependencies do it with patches active

    yield rumps_mock

    # Restore original after tests
    if original_rumps is not None:
        sys.modules["rumps"] = original_rumps
        # Clean up app module
        if "opencode_monitor.app" in sys.modules:
            del sys.modules["opencode_monitor.app"]


@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies for OpenCodeApp.

    Strategy: Patch at SOURCE level BEFORE reloading the app module.
    This ensures that when the module is reloaded, all imports resolve
    to our mocks rather than the real functions.
    """
    # Create mock objects
    mock_start_auditor = MagicMock()
    mock_get_auditor = MagicMock()
    mock_menu_builder = MagicMock()
    mock_get_settings = MagicMock()
    mock_save_settings = MagicMock()
    mock_focus_iterm2 = MagicMock()
    mock_fetch_instances = MagicMock()
    mock_fetch_usage = MagicMock()
    mock_info = MagicMock()
    mock_error = MagicMock()
    mock_debug = MagicMock()
    mock_start_collector = MagicMock()
    mock_get_collector = MagicMock()
    mock_start_indexer = MagicMock()
    mock_get_indexer = MagicMock()

    # Configure mocks
    mock_settings = MagicMock()
    mock_settings.usage_refresh_interval = 60
    mock_settings.permission_threshold_seconds = 5  # 5 seconds threshold
    mock_settings.ask_user_timeout = 3600  # 1 hour default
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
    mock_builder_instance.build_security_menu.return_value = MockMenuItem("Security")
    mock_builder_instance.build_analytics_menu.return_value = MockMenuItem("Analytics")
    mock_menu_builder.return_value = mock_builder_instance

    # Patch at SOURCE level (where functions are defined)
    # Then reload the app module so imports resolve to mocks
    with (
        patch("opencode_monitor.security.auditor.start_auditor", mock_start_auditor),
        patch("opencode_monitor.security.auditor.get_auditor", mock_get_auditor),
        patch("opencode_monitor.ui.menu.MenuBuilder", mock_menu_builder),
        patch("opencode_monitor.utils.settings.get_settings", mock_get_settings),
        patch("opencode_monitor.utils.settings.save_settings", mock_save_settings),
        patch("opencode_monitor.ui.terminal.focus_iterm2", mock_focus_iterm2),
        patch(
            "opencode_monitor.core.monitor.fetch_all_instances", mock_fetch_instances
        ),
        patch("opencode_monitor.core.usage.fetch_usage", mock_fetch_usage),
        patch("opencode_monitor.utils.logger.info", mock_info),
        patch("opencode_monitor.utils.logger.error", mock_error),
        patch("opencode_monitor.utils.logger.debug", mock_debug),
        patch(
            "opencode_monitor.analytics.collector.start_collector", mock_start_collector
        ),
        patch("opencode_monitor.analytics.collector.get_collector", mock_get_collector),
        patch(
            "opencode_monitor.analytics.indexer.start_indexer",
            mock_start_indexer,
        ),
        patch("opencode_monitor.analytics.indexer.get_indexer", mock_get_indexer),
    ):
        # Remove ALL cached app modules so they get re-imported with mocks
        # The app package has: __init__, core, menu, handlers
        # NOTE: Do NOT remove indexer modules - we need the mock to stay applied
        modules_to_remove = [
            "opencode_monitor.app",
            "opencode_monitor.app.core",
            "opencode_monitor.app.menu",
            "opencode_monitor.app.handlers",
        ]
        for mod_name in modules_to_remove:
            if mod_name in sys.modules:
                del sys.modules[mod_name]

        # Now import the app module - imports will resolve to mocks
        import opencode_monitor.app  # noqa: F401

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

        # Clean up - remove all app modules so next test gets fresh ones
        for mod_name in modules_to_remove:
            if mod_name in sys.modules:
                del sys.modules[mod_name]


def create_app_with_mocks(mock_dependencies, skip_monitor=True):
    """Helper to create OpenCodeApp with proper mocking."""
    from opencode_monitor.app import OpenCodeApp

    if skip_monitor:
        with patch.object(OpenCodeApp, "_run_monitor_loop"):
            app = OpenCodeApp()
    else:
        app = OpenCodeApp()

    return app


def get_title(app) -> str:
    """Get app title as string (handles None case for type checker)."""
    return str(app.title) if app.title else ""


# =============================================================================
# Group 1: Init (2 → 1 test)
# =============================================================================


class TestOpenCodeAppInit:
    """Tests for OpenCodeApp.__init__"""

    def test_init_full(self, mock_dependencies):
        """App should initialize with default state, constants, and start services."""
        from opencode_monitor.app import OpenCodeApp

        app = create_app_with_mocks(mock_dependencies)

        # State initialization
        assert app._state is None
        assert app._usage is None
        assert app._running is True
        assert app._needs_refresh is True
        assert app._previous_busy_agents == set()
        assert app._security_alerts == []
        assert app._has_critical_alert is False

        # Class constants
        assert OpenCodeApp.POLL_INTERVAL == 2
        assert OpenCodeApp.USAGE_INTERVALS == [30, 60, 120, 300, 600]
        assert app._PORT_NAMES_LIMIT == 50

        # Services started
        mock_dependencies["start_auditor"].assert_called_once()
        mock_dependencies["menu_builder"].assert_called_once()
        assert app._monitor_thread is not None
        assert app._monitor_thread.daemon is True


# =============================================================================
# Group 2: Static Menu (1 test - unchanged)
# =============================================================================


class TestBuildStaticMenu:
    """Tests for OpenCodeApp._build_static_menu"""

    def test_build_static_menu_creates_all_items(self, mock_dependencies):
        """Should create preferences menu, refresh item, quit item, and initial menu."""
        app = create_app_with_mocks(mock_dependencies)

        # All menu items exist
        assert hasattr(app, "_prefs_menu")
        assert hasattr(app, "_refresh_item")
        assert hasattr(app, "_quit_item")
        assert hasattr(app, "menu")


# =============================================================================
# Group 3: Interval Callback (1 test - unchanged)
# =============================================================================


class TestMakeIntervalCallback:
    """Tests for OpenCodeApp._make_interval_callback"""

    def test_make_interval_callback_full_behavior(self, mock_dependencies):
        """Callback should update settings, clear sibling states, set sender state, and log."""
        app = create_app_with_mocks(mock_dependencies)

        callback = app._make_interval_callback(120)

        # Create mock sender with sibling items
        mock_item1 = MagicMock()
        mock_item2 = MagicMock()
        mock_sender = MagicMock()
        mock_sender.parent.values.return_value = [mock_item1, mock_item2]

        callback(mock_sender)

        # Settings updated
        assert mock_dependencies["settings"].usage_refresh_interval == 120
        mock_dependencies["save_settings"].assert_called_once()

        # Sibling states cleared
        assert mock_item1.state == 0
        assert mock_item2.state == 0

        # Sender state set to selected
        assert mock_sender.state == 1

        # Logged the change
        mock_dependencies["info"].assert_called()
        call_args = str(mock_dependencies["info"].call_args)
        assert "120" in call_args


# =============================================================================
# Group 4: Ask Timeout Callback (2 → 1 test)
# =============================================================================


class TestMakeAskTimeoutCallback:
    """Tests for OpenCodeApp._make_ask_timeout_callback"""

    @pytest.mark.parametrize(
        "timeout_seconds,expected_format",
        [
            (3600, "1h"),  # 1 hour
            (7200, "2h"),  # 2 hours
            (1800, "30m"),  # 30 minutes
            (900, "15m"),  # 15 minutes
        ],
    )
    def test_make_ask_timeout_callback_full(
        self, mock_dependencies, timeout_seconds, expected_format
    ):
        """Callback should update settings, set sender state, and log correct format."""
        app = create_app_with_mocks(mock_dependencies)

        callback = app._make_ask_timeout_callback(timeout_seconds)

        mock_item1 = MagicMock()
        mock_item2 = MagicMock()
        mock_sender = MagicMock()
        mock_sender.parent.values.return_value = [mock_item1, mock_item2]

        callback(mock_sender)

        # Settings updated
        assert mock_dependencies["settings"].ask_user_timeout == timeout_seconds
        mock_dependencies["save_settings"].assert_called()

        # States managed
        assert mock_item1.state == 0
        assert mock_item2.state == 0
        assert mock_sender.state == 1

        # Logging with correct format
        mock_dependencies["info"].assert_called()
        call_args = str(mock_dependencies["info"].call_args)
        assert expected_format in call_args


# =============================================================================
# Group 5: UI Refresh (1 test - unchanged)
# =============================================================================


class TestUIRefresh:
    """Tests for OpenCodeApp._ui_refresh"""

    @pytest.mark.parametrize(
        "needs_refresh,should_rebuild",
        [
            (True, True),
            (False, False),
        ],
    )
    def test_ui_refresh_behavior(
        self, mock_dependencies, needs_refresh, should_rebuild
    ):
        """Should rebuild menu only when _needs_refresh is True."""
        app = create_app_with_mocks(mock_dependencies)
        app._needs_refresh = needs_refresh

        app._build_menu = MagicMock()
        app._update_title = MagicMock()

        app._ui_refresh(None)

        if should_rebuild:
            app._build_menu.assert_called_once()
            app._update_title.assert_called_once()
            assert app._needs_refresh is False
        else:
            app._build_menu.assert_not_called()
            app._update_title.assert_not_called()


# =============================================================================
# Group 6: Build Menu (2 → 1 test)
# =============================================================================


class TestBuildMenu:
    """Tests for OpenCodeApp._build_menu"""

    @pytest.mark.parametrize(
        "critical,high,expected_flag",
        [
            (2, 3, True),  # Critical alerts → flag True
            (0, 5, True),  # High alerts → flag True
            (0, 0, False),  # No alerts → flag False
        ],
    )
    def test_build_menu_full(self, mock_dependencies, critical, high, expected_flag):
        """Should use MenuBuilder, clear menu, add items, and update critical flag."""
        mock_item1 = MockMenuItem("Item 1")
        mock_item2 = MockMenuItem("Item 2")
        mock_dependencies["builder_instance"].build_dynamic_items.return_value = [
            mock_item1,
            mock_item2,
        ]
        mock_dependencies["auditor"].get_stats.return_value = {
            "critical": critical,
            "high": high,
            "medium": 5,
        }

        app = create_app_with_mocks(mock_dependencies)
        app._has_critical_alert = not expected_flag  # Start with opposite

        app._build_menu()

        # Uses MenuBuilder
        mock_dependencies["builder_instance"].build_dynamic_items.assert_called()
        mock_dependencies["builder_instance"].build_security_menu.assert_called()

        # Menu cleared and items added (cast to MockMenu for test access)
        menu = cast(MockMenu, app.menu)
        assert menu._clear_called is True
        assert len(menu._add_calls) >= 2
        assert None in menu._add_calls  # Separators

        # Critical flag updated
        assert app._has_critical_alert is expected_flag


# =============================================================================
# Group 7: Update Title - Usage (1 test - unchanged)
# =============================================================================


class TestUpdateTitleUsage:
    """Tests for usage display in OpenCodeApp._update_title"""

    @pytest.mark.parametrize(
        "utilization,expected_emoji,expected_percent",
        [
            (95, "🔴", "95%"),  # >= 90%
            (75, "🟠", None),  # >= 70%
            (55, "🟡", None),  # >= 50%
            (30, "🟢", None),  # < 50%
        ],
    )
    def test_update_title_usage_levels(
        self, mock_dependencies, utilization, expected_emoji, expected_percent
    ):
        """Should show correct color indicator based on usage level."""
        from opencode_monitor.core.models import State, Usage, UsagePeriod, Todos

        app = create_app_with_mocks(mock_dependencies)
        app._state = State(todos=Todos(), connected=True)
        app._usage = Usage(
            five_hour=UsagePeriod(utilization=utilization),
            seven_day=UsagePeriod(utilization=50),
        )

        app._update_title()

        title = get_title(app)
        assert expected_emoji in title
        if expected_percent:
            assert expected_percent in title


# =============================================================================
# Group 8: Update Title - Default (1 test - unchanged)
# =============================================================================


class TestUpdateTitleDefault:
    """Tests for default emoji in OpenCodeApp._update_title"""

    @pytest.mark.parametrize(
        "state_config",
        [
            {"state": None},  # No state
            {"connected": False},  # Not connected
            {"connected": True, "empty_parts": True},  # Connected but no data
            {"usage_error": True},  # Usage has error
        ],
    )
    def test_update_title_default_emoji(self, mock_dependencies, state_config):
        """Should show default emoji when no state, not connected, or no data."""
        from opencode_monitor.core.models import State, Usage, UsagePeriod, Todos

        app = create_app_with_mocks(mock_dependencies)

        if state_config.get("state") is None:
            app._state = None
        elif state_config.get("connected") is False:
            app._state = State(connected=False)
        elif state_config.get("empty_parts"):
            app._state = State(todos=Todos(pending=0, in_progress=0), connected=True)
            app._usage = None
        elif state_config.get("usage_error"):
            app._state = State(todos=Todos(), connected=True)
            app._usage = Usage(five_hour=UsagePeriod(utilization=50), error="API error")

        app._update_title()

        title = get_title(app)
        assert "🤖" in title
        if state_config.get("usage_error"):
            assert "%" not in title


# =============================================================================
# Group 9: Update Title - Permission (2 → 1 test)
# =============================================================================


class TestUpdateTitlePermission:
    """Tests for permission detection in OpenCodeApp._update_title"""

    @pytest.mark.parametrize(
        "tool_name,elapsed_ms,expected_lock,check_position",
        [
            ("bash", 10000, True, True),  # bash > threshold → lock, check position
            ("bash", 2000, False, False),  # bash < threshold → no lock
            ("task", 60000, False, False),  # task excluded even if long
            (None, 0, False, False),  # no tools → no lock
        ],
    )
    def test_update_title_permission_full(
        self, mock_dependencies, tool_name, elapsed_ms, expected_lock, check_position
    ):
        """Should show lock emoji based on tool type and elapsed time, positioned after busy count."""
        from opencode_monitor.core.models import (
            State,
            Instance,
            Agent,
            Tool,
            SessionStatus,
            Todos,
        )

        app = create_app_with_mocks(mock_dependencies)

        if tool_name:
            tool = Tool(name=tool_name, arg="test", elapsed_ms=elapsed_ms)
            tools = [tool]
        else:
            tools = []

        agent = Agent(
            id="1",
            title="test",
            dir=".",
            full_dir="/test",
            status=SessionStatus.BUSY,
            tools=tools,
        )
        instance = Instance(port=1234, agents=[agent])
        app._state = State(instances=[instance], todos=Todos(), connected=True)

        app._update_title()

        title = get_title(app)
        if expected_lock:
            assert "🔒" in title
            if check_position:
                # Lock should appear after busy count
                assert title.index("1") < title.index("🔒")
        else:
            assert "🔒" not in title


# =============================================================================
# Group 10: Update Title - Idle (1 test - unchanged)
# =============================================================================


class TestUpdateTitleIdle:
    """Tests for idle instances in OpenCodeApp._update_title"""

    @pytest.mark.parametrize(
        "idle_count,expected_idle_display",
        [
            (2, True),  # 2 idle → show 💤 2
            (1, True),  # 1 idle → show 💤 1
            (0, False),  # 0 idle → no 💤
        ],
    )
    def test_update_title_idle_instances(
        self, mock_dependencies, idle_count, expected_idle_display
    ):
        """Should show sleep emoji when there are idle instances."""
        from opencode_monitor.core.models import (
            State,
            Instance,
            Agent,
            SessionStatus,
            Todos,
        )

        app = create_app_with_mocks(mock_dependencies)

        # Create busy instance
        busy_agent = Agent(
            id="busy-1",
            title="Busy",
            dir=".",
            full_dir="/test",
            status=SessionStatus.BUSY,
        )
        busy_instance = Instance(port=1234, agents=[busy_agent])

        # Create idle instances
        idle_instances = [Instance(port=1235 + i, agents=[]) for i in range(idle_count)]

        app._state = State(
            instances=[busy_instance] + idle_instances,
            todos=Todos(),
            connected=True,
        )

        app._update_title()

        title = get_title(app)
        if expected_idle_display:
            assert "💤" in title
            assert f"💤 {idle_count}" in title
            # Idle should come after busy count
            busy_index = title.index("1")
            idle_index = title.index("💤")
            assert busy_index < idle_index
        else:
            assert "💤" not in title


# =============================================================================
# Group 11: Security Alerts (3 → 1 test)
# =============================================================================


class TestAddSecurityAlert:
    """Tests for OpenCodeApp._add_security_alert"""

    @pytest.mark.parametrize(
        "level,expected_log_text",
        [
            (RiskLevel.CRITICAL, "CRITICAL"),
            (RiskLevel.HIGH, "HIGH"),
        ],
    )
    def test_add_security_alert_full(self, mock_dependencies, level, expected_log_text):
        """Should store alerts, limit max, prevent duplicates, set critical flag, and log."""
        from opencode_monitor.security.analyzer import SecurityAlert, RiskLevel

        app = create_app_with_mocks(mock_dependencies)
        app._max_alerts = 5

        # Add multiple alerts to test storage and limiting
        for i in range(7):
            alert = SecurityAlert(
                command=f"command_{i}",
                tool="bash",
                score=100 if level == RiskLevel.CRITICAL else 60,
                level=level,
                reason="Test",
            )
            app._add_security_alert(alert)

        # Limited to max_alerts
        assert len(app._security_alerts) == 5

        # Newest at front
        assert app._security_alerts[0].command == "command_6"

        # Critical flag set correctly
        expected_critical = level == RiskLevel.CRITICAL
        assert app._has_critical_alert is expected_critical

        # Logging with correct level
        mock_dependencies["info"].assert_called()
        call_args = str(mock_dependencies["info"].call_args)
        assert expected_log_text in call_args

        # Test duplicate prevention
        duplicate_alert = SecurityAlert(
            command="command_6",  # Same as last added
            tool="bash",
            score=100,
            level=level,
            reason="Duplicate",
        )
        initial_count = len(app._security_alerts)
        app._add_security_alert(duplicate_alert)
        assert len(app._security_alerts) == initial_count  # No change


# =============================================================================
# Group 12: Security Reports (2 → 1 test)
# =============================================================================


class TestSecurityReports:
    """Tests for security report and export functionality"""

    def test_security_reports_full(self, mock_dependencies):
        """Should generate report/export, write to temp/config file, and open it."""
        with (
            patch("subprocess.run") as mock_run,
            patch("builtins.open", MagicMock()) as mock_open,
            patch(
                "opencode_monitor.app.handlers.SecurityReporter"
            ) as mock_reporter_class,
        ):
            mock_reporter = MagicMock()
            mock_reporter.generate_full_export.return_value = "Export content"
            mock_reporter_class.return_value = mock_reporter

            app = create_app_with_mocks(mock_dependencies)
            mock_dependencies["auditor"].generate_report.return_value = "Report content"
            mock_dependencies["auditor"].get_all_commands.return_value = []
            mock_dependencies["auditor"].get_all_reads.return_value = []
            mock_dependencies["auditor"].get_all_writes.return_value = []
            mock_dependencies["auditor"].get_all_webfetches.return_value = []

            # Test show_security_report
            app._show_security_report(None)
            mock_dependencies["auditor"].generate_report.assert_called_once()
            mock_run.assert_called()
            args = mock_run.call_args[0][0]
            assert args[0] == "open"
            assert "opencode_security_report.txt" in args[1]

            mock_run.reset_mock()

            # Test export_all_commands
            app._export_all_commands(None)

            # All data fetched
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

            # Reporter used
            mock_reporter.generate_full_export.assert_called_once()

            # Written to config dir and file opened
            mock_open.assert_called()
            call_args = mock_open.call_args[0][0]
            assert ".config/opencode-monitor" in call_args
            assert "security_audit_" in call_args
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0][0] == "open"


# =============================================================================
# Group 13: Main (1 test - unchanged)
# =============================================================================


class TestMain:
    """Tests for main() entry point"""

    def test_main_creates_and_runs_app(self, mock_dependencies):
        """Should create OpenCodeApp instance and call run()."""
        from opencode_monitor.app import main, OpenCodeApp

        with (
            patch.object(OpenCodeApp, "_run_monitor_loop"),
            patch.object(OpenCodeApp, "run") as mock_run,
        ):
            main()

            mock_run.assert_called_once()


# =============================================================================
# Group 14: Monitor Loop (4 → 2 tests)
# =============================================================================


class TestMonitorLoop:
    """Tests for OpenCodeApp._run_monitor_loop"""

    def test_monitor_loop_updates_state_and_tracks_agents(self, mock_dependencies):
        """Should fetch instances, update state, track busy agents, and update usage."""
        from opencode_monitor.core.models import (
            State,
            Instance,
            Agent,
            SessionStatus,
            Usage,
            UsagePeriod,
        )

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

        mock_fetch = AsyncMock(return_value=state)
        mock_dependencies["fetch_usage"].return_value = Usage(
            five_hour=UsagePeriod(utilization=75)
        )
        mock_dependencies["settings"].usage_refresh_interval = 0  # Always update

        app = create_app_with_mocks(mock_dependencies)
        app._needs_refresh = False
        app._last_usage_update = 0

        call_count = [0]

        def stop_after_one(*args):
            call_count[0] += 1
            if call_count[0] >= 1:
                app._running = False
            return 0

        with (
            patch("opencode_monitor.app.core.fetch_all_instances", mock_fetch),
            patch("time.sleep", side_effect=stop_after_one),
        ):
            app._running = True
            app._run_monitor_loop()

        # State updated
        assert app._state is not None
        assert app._state.connected is True

        # Busy agent tracked, idle not
        assert "busy-agent-1" in app._previous_busy_agents
        assert "idle-agent-1" not in app._previous_busy_agents

        # Usage fetched
        mock_dependencies["fetch_usage"].assert_called()

    @pytest.mark.parametrize(
        "error_source,error_message",
        [
            ("fetch", "Network error"),
            ("usage", "Usage API error"),
        ],
    )
    def test_monitor_loop_handles_errors(
        self, mock_dependencies, error_source, error_message
    ):
        """Should handle and log errors during fetch or usage update."""
        from opencode_monitor.core.models import State

        if error_source == "fetch":

            async def mock_fetch_error():
                raise Exception(error_message)

            mock_dependencies["fetch_instances"].return_value = mock_fetch_error()
        else:

            async def mock_fetch():
                return State(connected=True)

            mock_dependencies["fetch_instances"].return_value = mock_fetch()
            mock_dependencies["fetch_usage"].side_effect = Exception(error_message)
            mock_dependencies["settings"].usage_refresh_interval = 0

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

        # Error logged
        mock_dependencies["error"].assert_called()


# =============================================================================
# Group 15: Thread Safety & On Refresh (2 → 1 test)
# =============================================================================


class TestThreadSafetyAndRefresh:
    """Tests for thread safety and refresh behavior"""

    def test_state_access_and_refresh(self, mock_dependencies):
        """State/usage access should use lock, and refresh should set flag and log."""
        from opencode_monitor.core.models import State, Usage, UsagePeriod

        app = create_app_with_mocks(mock_dependencies)

        # Verify lock exists and works
        assert hasattr(app, "_state_lock")

        with app._state_lock:
            app._state = State(connected=True)
            state = app._state

        assert state.connected is True

        with app._state_lock:
            app._usage = Usage(five_hour=UsagePeriod(utilization=75))
            usage = app._usage

        assert usage.five_hour.utilization == 75

        # Test refresh behavior
        app._needs_refresh = False
        app._on_refresh(None)

        mock_dependencies["info"].assert_called()
        assert app._needs_refresh is True


# =============================================================================
# Group 16: Additional Coverage (5 → 2 tests)
# =============================================================================


class TestAdditionalCoverage:
    """Additional tests for complete coverage"""

    def test_title_with_all_elements_and_edge_cases(self, mock_dependencies):
        """Should handle complex title, empty instances, and focus terminal."""
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

        # Test complex title with all elements
        agent = Agent(
            id="1",
            title="test",
            dir=".",
            full_dir="/test",
            status=SessionStatus.BUSY,
            has_pending_ask_user=True,
            ask_user_title="Validation requise",
        )
        instance = Instance(port=1234, agents=[agent])
        app._state = State(
            instances=[instance], todos=Todos(pending=3, in_progress=1), connected=True
        )
        app._usage = Usage(
            five_hour=UsagePeriod(utilization=60), seven_day=UsagePeriod(utilization=40)
        )

        app._update_title()

        title = get_title(app)
        assert "1" in title  # busy count
        assert "4" in title  # todos (3 + 1)
        assert "60%" in title  # usage
        assert "🟡" in title  # yellow for 50-70%
        assert "🔔" in title  # pending ask_user

        # Test empty state
        app._state = State(instances=[], todos=Todos(), connected=True)
        app._usage = None
        app._update_title()
        assert get_title(app) == "🤖"

        # Test focus terminal
        app._focus_terminal("/dev/ttys001")
        mock_dependencies["focus_iterm2"].assert_called_once_with("/dev/ttys001")

    def test_session_cache_and_max_alerts(self, mock_dependencies):
        """Should manage session cache, handle max alerts boundary correctly."""
        from opencode_monitor.core.models import (
            State,
            Instance,
            Agent,
            SessionStatus,
            Todos,
        )
        from opencode_monitor.security.analyzer import SecurityAlert, RiskLevel

        app = create_app_with_mocks(mock_dependencies)

        # Test session cache cleanup and limit
        app._known_active_sessions = {"session_1": 1234, "session_2": 5678}

        for i in range(app._KNOWN_SESSIONS_LIMIT + 5):
            app._known_active_sessions[f"old_session_{i}"] = 1234

        agent = Agent(
            id="new_busy_session",
            title="test",
            dir=".",
            full_dir="/test",
            status=SessionStatus.BUSY,
        )
        instance = Instance(port=5678, agents=[agent])
        new_state = State(instances=[instance], todos=Todos(), connected=True)

        app._update_session_cache(new_state)

        # session_1 removed (port 1234 dead), session_2 kept (port 5678 alive)
        assert "session_1" not in app._known_active_sessions
        assert "session_2" in app._known_active_sessions
        assert len(app._known_active_sessions) <= app._KNOWN_SESSIONS_LIMIT
        assert "new_busy_session" in app._known_active_sessions

        # Test max alerts boundary
        app._max_alerts = 3
        app._security_alerts = []

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

        # Add one more - should trim oldest
        alert = SecurityAlert(
            command="cmd_new",
            tool="bash",
            score=50,
            level=RiskLevel.HIGH,
            reason="Test",
        )
        app._add_security_alert(alert)

        assert len(app._security_alerts) == 3
        assert app._security_alerts[0].command == "cmd_new"
