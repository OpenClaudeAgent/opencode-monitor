"""
OpenCode Monitor - rumps menu bar application
"""

import asyncio
import subprocess
import threading
import time
from datetime import datetime
from typing import Optional

import rumps

from .models import State, SessionStatus, Usage
from .monitor import fetch_all_instances
from .usage import fetch_usage
from .sounds import check_and_notify_completion
from .logger import info, error, debug


class OpenCodeApp(rumps.App):
    """Main menu bar application"""

    POLL_INTERVAL = 2  # seconds
    USAGE_INTERVAL = 60  # 1 minute

    def __init__(self):
        super().__init__(
            name="OpenCode Monitor",
            title="🤖",
            quit_button="Quit",
        )

        # State tracking
        self._state: Optional[State] = None
        self._usage: Optional[Usage] = None
        self._state_lock = threading.Lock()
        self._last_usage_update = 0
        self._previous_busy_agents: set = set()
        self._running = True
        self._needs_refresh = True
        self._port_names: dict[int, str] = {}  # Cache: port -> last known name
        self._PORT_NAMES_LIMIT = 50  # Max cached names before reset

        # Add menu items
        self.menu = [
            rumps.MenuItem("Loading...", callback=None),
            None,  # separator
            rumps.MenuItem("Refresh", callback=self._on_refresh),
        ]

        # Start background monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._run_monitor_loop, daemon=True
        )
        self._monitor_thread.start()

    @rumps.timer(2)
    def _ui_refresh(self, _):
        """Timer callback to refresh UI on main thread"""
        if self._needs_refresh:
            self._build_menu()
            self._update_title()
            self._needs_refresh = False

    def _build_menu(self):
        """Build the menu from current state - flat tree structure"""
        with self._state_lock:
            state = self._state
            usage = self._usage

        # Clear existing menu items except Refresh and Quit
        keys_to_remove = [k for k in self.menu.keys() if k not in ("Refresh", "Quit")]
        for key in keys_to_remove:
            del self.menu[key]

        if state is None or not state.connected:
            self.menu.insert_before("Refresh", rumps.MenuItem("No OpenCode instances"))
            self.menu.insert_before("Refresh", None)
            return

        # Display each instance (port) with its agents
        for instance in state.instances:
            tty = instance.tty

            # Separate main agents from sub-agents
            main_agents = [a for a in instance.agents if not a.is_subagent]
            sub_agents_map = {}  # parent_id -> list of sub-agents
            for a in instance.agents:
                if a.is_subagent:
                    if a.parent_id not in sub_agents_map:
                        sub_agents_map[a.parent_id] = []
                    sub_agents_map[a.parent_id].append(a)

            if main_agents:
                # Instance has agents - show agents and cache the name
                # Use first main agent's name for the port cache
                self._port_names[instance.port] = main_agents[0].title

                # Rotate cache if too large (remove oldest half)
                if len(self._port_names) > self._PORT_NAMES_LIMIT:
                    keys = list(self._port_names.keys())
                    for k in keys[: len(keys) // 2]:
                        del self._port_names[k]

                for agent in main_agents:
                    self._add_agent_to_menu(agent, tty, indent=0)

                    # Add sub-agents under this main agent
                    for sub_agent in sub_agents_map.get(agent.id, []):
                        self._add_agent_to_menu(sub_agent, tty, indent=1)
            else:
                # Instance has no busy agents - show instance as idle with cached name
                cached_name = self._port_names.get(
                    instance.port, f"Port {instance.port}"
                )

                def make_focus_cb(t):
                    def cb(_):
                        if t:
                            self._focus_terminal(t)

                    return cb

                idle_item = rumps.MenuItem(
                    f"⚪ {cached_name} (idle)", callback=make_focus_cb(tty)
                )
                self.menu.insert_before("Refresh", idle_item)

        self.menu.insert_before("Refresh", None)  # separator

        # Usage info (from memory)
        if usage:
            if usage.error:
                self.menu.insert_before(
                    "Refresh", rumps.MenuItem(f"⚠️ Usage: {usage.error}")
                )
            else:
                five_h = usage.five_hour.utilization
                seven_d = usage.seven_day.utilization

                # Session (5h) color
                if five_h >= 90:
                    icon = "🔴"
                elif five_h >= 70:
                    icon = "🟠"
                elif five_h >= 50:
                    icon = "🟡"
                else:
                    icon = "🟢"

                # Session reset time
                session_reset = ""
                if usage.five_hour.resets_at:
                    try:
                        reset_time = datetime.fromisoformat(
                            usage.five_hour.resets_at.replace("Z", "+00:00")
                        )
                        now = datetime.now(reset_time.tzinfo)
                        diff = reset_time - now
                        minutes = int(diff.total_seconds() / 60)
                        if minutes > 60:
                            session_reset = f"{minutes // 60}h{minutes % 60}m"
                        elif minutes > 0:
                            session_reset = f"{minutes}m"
                    except:
                        pass

                # Weekly reset time (day + hour)
                weekly_reset = ""
                if usage.seven_day.resets_at:
                    try:
                        reset_time = datetime.fromisoformat(
                            usage.seven_day.resets_at.replace("Z", "+00:00")
                        )
                        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                        weekly_reset = (
                            f"{days[reset_time.weekday()]} {reset_time.hour}h"
                        )
                    except:
                        pass

                # Session line
                session_text = f"{icon} Session: {five_h}%"
                if session_reset:
                    session_text += f" (reset {session_reset})"
                self.menu.insert_before("Refresh", rumps.MenuItem(session_text))

                # Weekly line
                weekly_text = f"📅 Weekly: {seven_d}%"
                if weekly_reset:
                    weekly_text += f" (reset {weekly_reset})"
                self.menu.insert_before("Refresh", rumps.MenuItem(weekly_text))

            # Link to Claude usage page
            self.menu.insert_before(
                "Refresh",
                rumps.MenuItem(
                    "📊 Open Claude Usage",
                    callback=lambda _: subprocess.run(
                        ["open", "https://claude.ai/settings/usage"]
                    ),
                ),
            )
            self.menu.insert_before("Refresh", None)

    def _add_agent_to_menu(self, agent, tty: str, indent: int = 0):
        """Add an agent and its details to the menu"""
        # Indentation prefix
        prefix = "    " * indent
        sub_prefix = "    " * (indent + 1)

        # Agent icon
        if indent > 0:
            # Sub-agent: minimal unicode, NOT clickable
            status_icon = "└ ●" if agent.status == SessionStatus.BUSY else "└ ○"
            callback = None
        else:
            # Main agent: robot icon, CLICKABLE to focus terminal
            status_icon = "🤖"

            def make_focus_callback(tty_val):
                def cb(_):
                    if tty_val:
                        self._focus_terminal(tty_val)

                return cb

            callback = make_focus_callback(tty)

        # Clean title (remove @tester subagent suffix for display)
        title = agent.title
        if "(@" in title:
            title = title.split("(@")[0].strip()
        if len(title) > 40:
            title = title[:37] + "..."

        agent_item = rumps.MenuItem(f"{prefix}{status_icon} {title}", callback=callback)
        self.menu.insert_before("Refresh", agent_item)

        # Tools (indented)
        if agent.tools:
            for tool in agent.tools:
                arg = tool.arg[:30] + "..." if len(tool.arg) > 30 else tool.arg
                self.menu.insert_before(
                    "Refresh", rumps.MenuItem(f"{sub_prefix}🔧 {tool.name}: {arg}")
                )

        # Todos (indented)
        if agent.todos:
            if agent.todos.in_progress > 0 and agent.todos.current_label:
                label = agent.todos.current_label[:35]
                self.menu.insert_before(
                    "Refresh", rumps.MenuItem(f"{sub_prefix}🔄 {label}")
                )

            if agent.todos.pending > 0 and agent.todos.next_label:
                label = agent.todos.next_label[:30]
                if agent.todos.pending > 1:
                    label += f" (+{agent.todos.pending - 1})"
                self.menu.insert_before(
                    "Refresh", rumps.MenuItem(f"{sub_prefix}⏳ {label}")
                )

    def _update_title(self):
        """Update menu bar title based on state"""
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

        # Todos
        total_todos = state.todos.pending + state.todos.in_progress
        if total_todos > 0:
            parts.append(f"⏳{total_todos}")

        # Usage from memory
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

    def _focus_terminal(self, tty: str):
        """Focus iTerm2 on the given TTY"""
        tty_path = f"/dev/{tty}" if not tty.startswith("/dev/") else tty
        script = f'''
            on run
                set searchTerm to "{tty_path}"
                tell application "iTerm2"
                    activate
                    repeat with w in windows
                        repeat with t in tabs of w
                            try
                                set s to current session of t
                                if (tty of s) is equal to searchTerm then
                                    select t
                                    select w
                                    return
                                else if name of s contains searchTerm then
                                    select t
                                    select w
                                    return
                                end if
                            end try
                        end repeat
                    end repeat
                end tell
            end run
        '''
        try:
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
        except Exception as e:
            error(f"Focus terminal failed: {e}")

    def _on_refresh(self, _):
        """Manual refresh callback"""
        info("Manual refresh requested")
        self._needs_refresh = True

    def _run_monitor_loop(self):
        """Background monitoring loop (runs in separate thread)"""
        info("OpenCode Monitor started (rumps)")

        # Create event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while self._running:
                start_time = time.time()

                try:
                    # Fetch all instances
                    new_state = loop.run_until_complete(fetch_all_instances())

                    # Update state with lock
                    with self._state_lock:
                        self._state = new_state

                    # Track busy agents for notifications
                    current_busy_agents = set()

                    for instance in new_state.instances:
                        for agent in instance.agents:
                            agent_id = agent.id
                            is_busy = agent.status == SessionStatus.BUSY
                            was_busy = agent_id in self._previous_busy_agents

                            if is_busy:
                                current_busy_agents.add(agent_id)

                            if was_busy and not is_busy:
                                check_and_notify_completion(
                                    agent_id, 0, 0, was_busy=True
                                )

                    self._previous_busy_agents = current_busy_agents

                    # Signal UI needs refresh
                    self._needs_refresh = True

                    debug(f"State updated: {new_state.instance_count} instances")

                except Exception as e:
                    error(f"Monitor error: {e}")

                # Update usage periodically
                now = time.time()
                if now - self._last_usage_update >= self.USAGE_INTERVAL:
                    try:
                        new_usage = fetch_usage()
                        with self._state_lock:
                            self._usage = new_usage
                        self._last_usage_update = now
                        self._needs_refresh = True
                    except Exception as e:
                        error(f"Usage update error: {e}")

                # Sleep until next poll
                elapsed = time.time() - start_time
                sleep_time = max(0, self.POLL_INTERVAL - elapsed)
                time.sleep(sleep_time)

        finally:
            loop.close()
            info("OpenCode Monitor stopped")


def main():
    """Main entry point"""
    app = OpenCodeApp()
    app.run()


if __name__ == "__main__":
    main()
