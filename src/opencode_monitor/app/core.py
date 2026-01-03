"""
Core OpenCodeApp class - Main menu bar application.

This module provides the OpenCodeApp class which:
- Manages application state and lifecycle
- Runs background monitoring loop
- Combines MenuMixin and HandlersMixin for functionality
"""

import asyncio
import threading
import time
from typing import Optional

import rumps

from ..core.models import State, SessionStatus, Usage
from ..core.monitor import fetch_all_instances
from ..core.usage import fetch_usage
from ..ui.menu import MenuBuilder
from ..utils.settings import get_settings
from ..utils.logger import info, error, debug
from ..security.auditor import start_auditor
from ..analytics.collector import start_collector

from .handlers import HandlersMixin, AnalyticsSyncManager
from .menu import MenuMixin


class OpenCodeApp(HandlersMixin, MenuMixin, rumps.App):
    """Main menu bar application.

    Combines:
    - HandlersMixin: Callback handlers (must come first for MRO)
    - MenuMixin: Menu building and preferences
    - rumps.App: macOS menu bar functionality
    """

    POLL_INTERVAL = 2  # seconds
    USAGE_INTERVALS = [30, 60, 120, 300, 600]  # Available options
    # Ask user timeout options (in seconds) - how long to show 🔔 before dismissing
    ASK_USER_TIMEOUTS = [300, 900, 1800, 3600]  # 5m, 15m, 30m, 1h

    def __init__(self):
        super().__init__(
            name="OpenCode Monitor",
            title="🤖",
            quit_button=None,
        )

        # State tracking
        self._state: Optional[State] = None
        self._usage: Optional[Usage] = None
        self._state_lock = threading.Lock()
        self._last_usage_update = 0
        self._previous_busy_agents: set = set()
        self._running = True
        self._needs_refresh = True
        self._port_names: dict[int, str] = {}
        self._PORT_NAMES_LIMIT = 50

        # Cache of sessions we've seen as BUSY, with their port
        # Format: {session_id: port} - allows invalidation when port dies
        self._known_active_sessions: dict[str, int] = {}
        self._KNOWN_SESSIONS_LIMIT = 200

        # Security monitoring
        self._security_alerts: list = []
        self._max_alerts = 20
        self._has_critical_alert = False

        # Menu builder
        self._menu_builder = MenuBuilder(self._port_names, self._PORT_NAMES_LIMIT)

        # Start security auditor
        start_auditor()

        # Start analytics collector (incremental background loading)
        start_collector()

        # Start analytics sync manager (sole DB writer)
        self._sync_manager = AnalyticsSyncManager()
        self._sync_manager.start_background_sync(max_days=30)

        # Build initial menu
        self._build_static_menu()

        # Start background monitoring
        self._monitor_thread = threading.Thread(
            target=self._run_monitor_loop, daemon=True
        )
        self._monitor_thread.start()

    @rumps.timer(2)
    def _ui_refresh(self, _):
        """Timer callback to refresh UI on main thread."""
        if self._needs_refresh:
            self._build_menu()
            self._update_title()
            self._needs_refresh = False

    def _update_title(self):
        """Update menu bar title based on state."""
        with self._state_lock:
            state = self._state
            usage = self._usage

        if state is None or not state.connected:
            self.title = "🤖"
            return

        parts = []

        # Busy count
        if state.busy_count > 0:
            parts.append(str(state.busy_count))

        # Idle instances count (instances with no main agents)
        idle_instances = sum(
            1
            for inst in state.instances
            if not any(not a.is_subagent for a in inst.agents)
        )
        if idle_instances > 0:
            parts.append(f"💤 {idle_instances}")

        # Permission pending indicator
        has_permission_pending = any(
            tool.may_need_permission
            for instance in state.instances
            for agent in instance.agents
            for tool in agent.tools
        )
        if has_permission_pending:
            parts.append("🔒")

        # Ask user pending indicator (MCP Notify)
        if state.has_pending_ask_user:
            parts.append("🔔")

        # Todos
        total_todos = state.todos.pending + state.todos.in_progress
        if total_todos > 0:
            parts.append(f"⏳{total_todos}")

        # Usage
        if usage and not usage.error:
            five_h = usage.five_hour.utilization
            if five_h >= 90:
                icon = "🔴"
            elif five_h >= 70:
                icon = "🟠"
            elif five_h >= 50:
                icon = "🟡"
            else:
                icon = "🟢"
            parts.append(f"{icon}{five_h}%")

        if parts:
            self.title = "🤖 " + " ".join(parts)
        else:
            self.title = "🤖"

    def _update_session_cache(self, new_state: State) -> set[str]:
        """Update the known active sessions cache based on new state."""
        current_ports = {inst.port for inst in new_state.instances}

        # Remove sessions from ports that no longer exist
        dead_sessions = [
            sid
            for sid, port in self._known_active_sessions.items()
            if port not in current_ports
        ]
        for sid in dead_sessions:
            del self._known_active_sessions[sid]

        # Collect currently busy sessions
        current_busy_agents: set[str] = set()
        for instance in new_state.instances:
            for agent in instance.agents:
                if agent.status == SessionStatus.BUSY:
                    current_busy_agents.add(agent.id)
                    self._known_active_sessions[agent.id] = instance.port

        # Limit cache size (remove oldest entries, but keep currently busy)
        if len(self._known_active_sessions) > self._KNOWN_SESSIONS_LIMIT:
            excess = len(self._known_active_sessions) - self._KNOWN_SESSIONS_LIMIT
            to_remove = [
                sid
                for sid in list(self._known_active_sessions.keys())[:excess]
                if sid not in current_busy_agents
            ]
            for sid in to_remove:
                del self._known_active_sessions[sid]

        return current_busy_agents

    def _run_monitor_loop(self):
        """Background monitoring loop."""
        info("OpenCode Monitor started (rumps)")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while self._running:
                start_time = time.time()

                try:
                    new_state = loop.run_until_complete(
                        fetch_all_instances(
                            known_active_sessions=set(
                                self._known_active_sessions.keys()
                            )
                        )
                    )

                    with self._state_lock:
                        self._state = new_state

                    # Update session cache and track busy agents
                    self._previous_busy_agents = self._update_session_cache(new_state)
                    self._needs_refresh = True

                    debug(f"State updated: {new_state.instance_count} instances")

                except Exception as e:
                    error(f"Monitor error: {e}")

                # Update usage periodically
                settings = get_settings()
                now = time.time()
                if now - self._last_usage_update >= settings.usage_refresh_interval:
                    try:
                        new_usage = fetch_usage()
                        with self._state_lock:
                            self._usage = new_usage
                        self._last_usage_update = now
                        self._needs_refresh = True
                    except Exception as e:
                        error(f"Usage update error: {e}")

                elapsed = time.time() - start_time
                sleep_time = max(0, self.POLL_INTERVAL - elapsed)
                time.sleep(sleep_time)

        finally:
            loop.close()
            info("OpenCode Monitor stopped")


def main():
    """Main entry point."""
    app = OpenCodeApp()
    app.run()


if __name__ == "__main__":
    main()
