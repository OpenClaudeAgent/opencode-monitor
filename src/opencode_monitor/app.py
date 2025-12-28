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

from .settings import get_settings, save_settings
from .logger import info, error, debug
from .security import analyze_command, SecurityAlert, RiskLevel, get_level_emoji
from .security_auditor import get_auditor, start_auditor
from .terminal import focus_iterm2
from .reporter import SecurityReporter


# Truncation limits for menu items
TITLE_MAX_LENGTH = 40
TOOL_ARG_MAX_LENGTH = 30
TODO_CURRENT_MAX_LENGTH = 35
TODO_PENDING_MAX_LENGTH = 30


def _truncate_with_tooltip(text: str, max_length: int, prefix: str = "", callback=None):
    """Create a menu item, adding a tooltip if text exceeds max_length.

    Args:
        text: The full text to display
        max_length: Maximum length before truncation
        prefix: Prefix to prepend (icons, indentation)
        callback: Optional click callback

    Returns:
        A rumps.MenuItem with tooltip set if text was truncated
    """
    is_truncated = len(text) > max_length

    if is_truncated:
        display_text = text[: max_length - 3] + "..."
    else:
        display_text = text

    item = rumps.MenuItem(f"{prefix}{display_text}", callback=callback)

    # Set native macOS tooltip only if truncated
    # Note: _menuitem is rumps internal access to NSMenuItem.
    # setToolTip_ is the PyObjC binding for Cocoa's setToolTip:
    if is_truncated:
        item._menuitem.setToolTip_(text)

    return item


class OpenCodeApp(rumps.App):
    """Main menu bar application"""

    POLL_INTERVAL = 2  # seconds
    USAGE_INTERVALS = [30, 60, 120, 300, 600]  # Available options

    def __init__(self):
        super().__init__(
            name="OpenCode Monitor",
            title="🤖",
            quit_button=None,  # We'll add our own quit with preferences before it
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

        # Security monitoring (legacy real-time, kept for compatibility)
        self._security_alerts: list[SecurityAlert] = []
        self._max_alerts = 20
        self._has_critical_alert = False

        # Start security auditor (background scanning)
        start_auditor()

        # Build initial menu (stores static items as instance vars)
        self._build_static_menu()

        # Start background monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._run_monitor_loop, daemon=True
        )
        self._monitor_thread.start()

    def _build_static_menu(self):
        """Build the static menu items (stored as instance vars for reuse)"""
        settings = get_settings()

        # Preferences submenu
        self._prefs_menu = rumps.MenuItem("⚙️ Preferences")

        # Usage refresh submenu
        refresh_menu = rumps.MenuItem("Usage refresh")
        for interval in self.USAGE_INTERVALS:
            label = f"{interval}s" if interval < 60 else f"{interval // 60}m"
            item = rumps.MenuItem(
                label, callback=self._make_interval_callback(interval)
            )
            item.state = 1 if settings.usage_refresh_interval == interval else 0
            refresh_menu.add(item)
        self._prefs_menu.add(refresh_menu)

        # Static items
        self._refresh_item = rumps.MenuItem("Refresh", callback=self._on_refresh)
        self._quit_item = rumps.MenuItem("Quit", callback=rumps.quit_application)

        # Initial menu
        self.menu = [
            rumps.MenuItem("Loading...", callback=None),
            None,
            self._refresh_item,
            None,
            self._prefs_menu,
            None,
            self._quit_item,
        ]

    def _make_interval_callback(self, interval: int):
        """Create a callback for setting usage refresh interval"""

        def callback(sender):
            settings = get_settings()
            settings.usage_refresh_interval = interval
            save_settings()
            # Update checkmarks
            for item in sender.parent.values():
                item.state = 0
            sender.state = 1
            info(f"Usage refresh interval set to {interval}s")

        return callback

    @rumps.timer(2)
    def _ui_refresh(self, _):
        """Timer callback to refresh UI on main thread"""
        if self._needs_refresh:
            self._build_menu()
            self._update_title()
            self._needs_refresh = False

    def _build_menu(self):
        """Build the menu from current state - complete rebuild each time"""
        with self._state_lock:
            state = self._state
            usage = self._usage

        # Build dynamic items list
        dynamic_items = []

        if state is None or not state.connected:
            dynamic_items.append(rumps.MenuItem("No OpenCode instances"))
        else:
            # Clean up port name cache: remove ports no longer active
            active_ports = {inst.port for inst in state.instances}
            self._port_names = {
                p: n for p, n in self._port_names.items() if p in active_ports
            }

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
                    self._port_names[instance.port] = main_agents[0].title

                    # Rotate cache if too large
                    if len(self._port_names) > self._PORT_NAMES_LIMIT:
                        keys = list(self._port_names.keys())
                        for k in keys[: len(keys) // 2]:
                            del self._port_names[k]

                    for agent in main_agents:
                        dynamic_items.extend(
                            self._build_agent_items(agent, tty, indent=0)
                        )
                        for sub_agent in sub_agents_map.get(agent.id, []):
                            dynamic_items.extend(
                                self._build_agent_items(sub_agent, tty, indent=1)
                            )
                else:
                    # Instance idle - show with cached name or port number
                    display_name = self._port_names.get(
                        instance.port, f"Port {instance.port}"
                    )

                    def make_focus_cb(t):
                        def cb(_):
                            if t:
                                self._focus_terminal(t)

                        return cb

                    dynamic_items.append(
                        rumps.MenuItem(
                            f"⚪ {display_name} (idle)", callback=make_focus_cb(tty)
                        )
                    )

            # Usage info
            if usage:
                dynamic_items.append(None)  # separator
                if usage.error:
                    dynamic_items.append(rumps.MenuItem(f"⚠️ Usage: {usage.error}"))
                else:
                    five_h = usage.five_hour.utilization
                    seven_d = usage.seven_day.utilization

                    if five_h >= 90:
                        icon = "🔴"
                    elif five_h >= 70:
                        icon = "🟠"
                    elif five_h >= 50:
                        icon = "🟡"
                    else:
                        icon = "🟢"

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

                    session_text = f"{icon} Session: {five_h}%"
                    if session_reset:
                        session_text += f" (reset {session_reset})"
                    dynamic_items.append(rumps.MenuItem(session_text))

                    weekly_text = f"📅 Weekly: {seven_d}%"
                    if weekly_reset:
                        weekly_text += f" (reset {weekly_reset})"
                    dynamic_items.append(rumps.MenuItem(weekly_text))

                dynamic_items.append(
                    rumps.MenuItem(
                        "📊 Open Claude Usage",
                        callback=lambda _: subprocess.run(
                            ["open", "https://claude.ai/settings/usage"]
                        ),
                    )
                )

        # Rebuild complete menu
        self.menu.clear()
        for item in dynamic_items:
            self.menu.add(item)

        # Security Audit section (from background auditor)
        self.menu.add(None)  # separator

        auditor = get_auditor()
        stats = auditor.get_stats()
        critical_count = stats.get("critical", 0) + stats.get("high", 0)

        # Security menu title with alert indicator
        if critical_count > 0:
            security_title = f"🛡️ Security Audit ({critical_count} alerts)"
            self._has_critical_alert = True
        else:
            security_title = "🛡️ Security Audit"
            self._has_critical_alert = False

        security_menu = rumps.MenuItem(security_title)

        # Stats summary
        total_cmds = stats.get("total_commands", 0)
        total_reads = stats.get("total_reads", 0)
        total_writes = stats.get("total_writes", 0)
        total_fetches = stats.get("total_webfetches", 0)
        security_menu.add(
            rumps.MenuItem(
                f"📊 {total_cmds} cmds, {total_reads} reads, {total_writes} writes, {total_fetches} fetches"
            )
        )
        security_menu.add(
            rumps.MenuItem(
                f"💻 Commands: 🔴{stats.get('critical', 0)} 🟠{stats.get('high', 0)} 🟡{stats.get('medium', 0)}"
            )
        )
        security_menu.add(
            rumps.MenuItem(
                f"📖 Reads: 🔴{stats.get('reads_critical', 0)} 🟠{stats.get('reads_high', 0)} 🟡{stats.get('reads_medium', 0)}"
            )
        )
        security_menu.add(
            rumps.MenuItem(
                f"✏️ Writes: 🔴{stats.get('writes_critical', 0)} 🟠{stats.get('writes_high', 0)} 🟡{stats.get('writes_medium', 0)}"
            )
        )
        security_menu.add(
            rumps.MenuItem(
                f"🌐 Fetches: 🔴{stats.get('webfetches_critical', 0)} 🟠{stats.get('webfetches_high', 0)} 🟡{stats.get('webfetches_medium', 0)}"
            )
        )
        security_menu.add(None)  # separator

        # Top critical/high commands
        critical_cmds = auditor.get_critical_commands(5)
        if critical_cmds:
            security_menu.add(rumps.MenuItem("💻 ── Commands ──"))
            for cmd in critical_cmds:
                emoji = "🔴" if cmd.risk_level == "critical" else "🟠"
                cmd_short = (
                    cmd.command[:40] + "..." if len(cmd.command) > 40 else cmd.command
                )
                item = rumps.MenuItem(f"{emoji} {cmd_short}")
                item._menuitem.setToolTip_(
                    f"⚠️ {cmd.risk_reason}\nScore: {cmd.risk_score}/100\n\n{cmd.command}"
                )
                security_menu.add(item)

        # Top sensitive reads
        sensitive_reads = auditor.get_sensitive_reads(5)
        if sensitive_reads:
            security_menu.add(rumps.MenuItem("📖 ── File Reads ──"))
            for read in sensitive_reads:
                emoji = "🔴" if read.risk_level == "critical" else "🟠"
                path_short = (
                    "..." + read.file_path[-40:]
                    if len(read.file_path) > 40
                    else read.file_path
                )
                item = rumps.MenuItem(f"{emoji} {path_short}")
                item._menuitem.setToolTip_(
                    f"⚠️ {read.risk_reason}\nScore: {read.risk_score}/100\n\n{read.file_path}"
                )
                security_menu.add(item)

        # Top sensitive writes
        sensitive_writes = auditor.get_sensitive_writes(5)
        if sensitive_writes:
            security_menu.add(rumps.MenuItem("✏️ ── File Writes ──"))
            for write in sensitive_writes:
                emoji = "🔴" if write.risk_level == "critical" else "🟠"
                path_short = (
                    "..." + write.file_path[-40:]
                    if len(write.file_path) > 40
                    else write.file_path
                )
                item = rumps.MenuItem(f"{emoji} {path_short}")
                item._menuitem.setToolTip_(
                    f"⚠️ {write.risk_reason}\nScore: {write.risk_score}/100\nOperation: {write.operation}\n\n{write.file_path}"
                )
                security_menu.add(item)

        # Top risky webfetches
        risky_fetches = auditor.get_risky_webfetches(5)
        if risky_fetches:
            security_menu.add(rumps.MenuItem("🌐 ── Web Fetches ──"))
            for fetch in risky_fetches:
                emoji = "🔴" if fetch.risk_level == "critical" else "🟠"
                url_short = fetch.url[:40] + "..." if len(fetch.url) > 40 else fetch.url
                item = rumps.MenuItem(f"{emoji} {url_short}")
                item._menuitem.setToolTip_(
                    f"⚠️ {fetch.risk_reason}\nScore: {fetch.risk_score}/100\n\n{fetch.url}"
                )
                security_menu.add(item)

        if (
            not critical_cmds
            and not sensitive_reads
            and not sensitive_writes
            and not risky_fetches
        ):
            security_menu.add(rumps.MenuItem("✅ No critical items"))

        security_menu.add(None)
        security_menu.add(
            rumps.MenuItem("📋 View Full Report", callback=self._show_security_report)
        )
        security_menu.add(
            rumps.MenuItem("📜 Export All Data", callback=self._export_all_commands)
        )

        self.menu.add(security_menu)

        self.menu.add(None)  # separator
        self.menu.add(self._refresh_item)
        self.menu.add(None)
        self.menu.add(self._prefs_menu)
        self.menu.add(None)
        self.menu.add(self._quit_item)

    def _build_agent_items(self, agent, tty: str, indent: int = 0) -> list:
        """Build menu items for an agent and return them as a list"""
        items = []
        prefix = "    " * indent
        sub_prefix = "    " * (indent + 1)

        # Agent icon
        if indent > 0:
            status_icon = "└ ●" if agent.status == SessionStatus.BUSY else "└ ○"
            callback = None
        else:
            status_icon = "🤖"

            def make_focus_callback(tty_val):
                def cb(_):
                    if tty_val:
                        self._focus_terminal(tty_val)

                return cb

            callback = make_focus_callback(tty)

        # Clean title (remove @mention suffix if present)
        title = agent.title
        if "(@" in title:
            title = title.split("(@")[0].strip()

        # Create agent item with tooltip if truncated
        items.append(
            _truncate_with_tooltip(
                title,
                TITLE_MAX_LENGTH,
                prefix=f"{prefix}{status_icon} ",
                callback=callback,
            )
        )

        # Tools (with security analysis)
        if agent.tools:
            for tool in agent.tools:
                # Analyze command for security risks
                alert = None
                if tool.name.lower() in ("bash", "shell", "execute"):
                    alert = analyze_command(tool.arg, tool.name)
                    alert.agent_id = agent.id
                    alert.agent_title = agent.title

                    # Track high-risk alerts
                    if alert.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                        self._add_security_alert(alert)

                # Build display text with risk indicator
                risk_emoji = get_level_emoji(alert.level) if alert else ""
                tool_icon = "🔧" if not risk_emoji else risk_emoji
                full_tool_text = f"{tool.name}: {tool.arg}"

                item = _truncate_with_tooltip(
                    full_tool_text,
                    TOOL_ARG_MAX_LENGTH,
                    prefix=f"{sub_prefix}{tool_icon} ",
                )

                # Add detailed tooltip for risky commands
                if alert and alert.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                    tooltip = (
                        f"⚠️ {alert.reason}\nScore: {alert.score}/100\n\n{tool.arg}"
                    )
                    item._menuitem.setToolTip_(tooltip)

                items.append(item)

        # Todos
        if agent.todos:
            if agent.todos.in_progress > 0 and agent.todos.current_label:
                items.append(
                    _truncate_with_tooltip(
                        agent.todos.current_label,
                        TODO_CURRENT_MAX_LENGTH,
                        prefix=f"{sub_prefix}🔄 ",
                    )
                )

            if agent.todos.pending > 0 and agent.todos.next_label:
                # Add pending count suffix if more than one pending
                suffix = (
                    f" (+{agent.todos.pending - 1})" if agent.todos.pending > 1 else ""
                )
                full_label = agent.todos.next_label + suffix
                items.append(
                    _truncate_with_tooltip(
                        full_label,
                        TODO_PENDING_MAX_LENGTH,
                        prefix=f"{sub_prefix}⏳ ",
                    )
                )

        return items

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
        focus_iterm2(tty)

    def _on_refresh(self, _):
        """Manual refresh callback"""
        info("Manual refresh requested")
        self._needs_refresh = True

    def _add_security_alert(self, alert: SecurityAlert):
        """Add a security alert to the history"""
        # Avoid duplicates (same command)
        for existing in self._security_alerts:
            if existing.command == alert.command:
                return

        self._security_alerts.insert(0, alert)

        # Trim to max size
        if len(self._security_alerts) > self._max_alerts:
            self._security_alerts = self._security_alerts[: self._max_alerts]

        # Set critical flag for title indicator
        if alert.level == RiskLevel.CRITICAL:
            self._has_critical_alert = True
            info(f"🔴 CRITICAL: {alert.reason} - {alert.command[:50]}")
        elif alert.level == RiskLevel.HIGH:
            info(f"🟠 HIGH: {alert.reason} - {alert.command[:50]}")

    def _clear_critical_flag(self, _):
        """Clear the critical alert flag when user views history"""
        self._has_critical_alert = False
        self._needs_refresh = True

    def _show_security_report(self, _):
        """Generate and open security report"""
        import tempfile
        import os

        auditor = get_auditor()
        report = auditor.generate_report()

        # Write to temp file and open
        report_path = os.path.join(
            tempfile.gettempdir(), "opencode_security_report.txt"
        )
        with open(report_path, "w") as f:
            f.write(report)

        # Open in default text editor
        subprocess.run(["open", report_path])
        info(f"Security report opened: {report_path}")

    def _export_all_commands(self, _):
        """Export complete security audit history to a file"""
        import os
        from datetime import datetime as dt

        auditor = get_auditor()
        reporter = SecurityReporter()

        # Get all data
        commands = auditor.get_all_commands(limit=10000)
        reads = auditor.get_all_reads(limit=10000)
        writes = auditor.get_all_writes(limit=10000)
        fetches = auditor.get_all_webfetches(limit=10000)

        # Generate report using reporter
        content = reporter.generate_full_export(commands, reads, writes, fetches)

        # Write to file
        export_dir = os.path.expanduser("~/.config/opencode-monitor")
        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        export_path = os.path.join(export_dir, f"security_audit_{timestamp}.txt")

        with open(export_path, "w") as f:
            f.write(content)

        subprocess.run(["open", export_path])
        info(f"Security audit exported: {export_path}")

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

                    self._previous_busy_agents = current_busy_agents

                    # Signal UI needs refresh
                    self._needs_refresh = True

                    debug(f"State updated: {new_state.instance_count} instances")

                except Exception as e:
                    error(f"Monitor error: {e}")

                # Update usage periodically (use settings interval)
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
