"""
OpenCode Monitor - rumps menu bar application
"""

import asyncio
import subprocess
import threading
import time
from typing import Optional

import rumps

from .core.models import State, SessionStatus, Usage
from .core.monitor import fetch_all_instances
from .core.usage import fetch_usage

from .utils.settings import get_settings, save_settings
from .utils.logger import info, error, debug
from .security.analyzer import SecurityAlert, RiskLevel
from .security.auditor import get_auditor, start_auditor
from .ui.terminal import focus_iterm2
from .ui.menu import (
    MenuBuilder,
    truncate_with_tooltip,
    TITLE_MAX_LENGTH,
    TOOL_ARG_MAX_LENGTH,
    TODO_CURRENT_MAX_LENGTH,
    TODO_PENDING_MAX_LENGTH,
)
from .security.reporter import SecurityReporter
from .analytics import AnalyticsDB, load_opencode_data, generate_report


# Re-export for backwards compatibility with tests
_truncate_with_tooltip = truncate_with_tooltip


class OpenCodeApp(rumps.App):
    """Main menu bar application"""

    POLL_INTERVAL = 2  # seconds
    USAGE_INTERVALS = [30, 60, 120, 300, 600]  # Available options

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

        # Security monitoring
        self._security_alerts: list[SecurityAlert] = []
        self._max_alerts = 20
        self._has_critical_alert = False

        # Menu builder
        self._menu_builder = MenuBuilder(self._port_names, self._PORT_NAMES_LIMIT)

        # Start security auditor
        start_auditor()

        # Build initial menu
        self._build_static_menu()

        # Start analytics background refresh (once per day)
        self._start_analytics_refresh()

        # Start background monitoring
        self._monitor_thread = threading.Thread(
            target=self._run_monitor_loop, daemon=True
        )
        self._monitor_thread.start()

    def _build_static_menu(self):
        """Build the static menu items"""
        settings = get_settings()

        # Preferences submenu
        self._prefs_menu = rumps.MenuItem("⚙️ Preferences")

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
        """Build the menu from current state"""
        with self._state_lock:
            state = self._state
            usage = self._usage

        # Build dynamic items using MenuBuilder
        dynamic_items = self._menu_builder.build_dynamic_items(
            state,
            usage,
            focus_callback=self._focus_terminal,
            alert_callback=self._add_security_alert,
        )

        # Rebuild complete menu
        self.menu.clear()
        for item in dynamic_items:
            self.menu.add(item)

        # Security menu
        self.menu.add(None)
        auditor = get_auditor()
        security_menu = self._menu_builder.build_security_menu(
            auditor,
            report_callback=self._show_security_report,
            export_callback=self._export_all_commands,
        )

        # Update critical flag
        stats = auditor.get_stats()
        critical_count = stats.get("critical", 0) + stats.get("high", 0)
        self._has_critical_alert = critical_count > 0

        self.menu.add(security_menu)

        # Analytics menu
        analytics_menu = self._menu_builder.build_analytics_menu(
            analytics_callback=self._show_analytics,
            refresh_callback=self._refresh_analytics,
        )
        self.menu.add(analytics_menu)

        # Static items
        self.menu.add(None)
        self.menu.add(self._refresh_item)
        self.menu.add(None)
        self.menu.add(self._prefs_menu)
        self.menu.add(None)
        self.menu.add(self._quit_item)

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

        # Permission pending indicator
        has_permission_pending = any(
            tool.may_need_permission
            for instance in state.instances
            for agent in instance.agents
            for tool in agent.tools
        )
        if has_permission_pending:
            parts.append("🔒")

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

    def _focus_terminal(self, tty: str):
        """Focus iTerm2 on the given TTY"""
        focus_iterm2(tty)

    def _on_refresh(self, _):
        """Manual refresh callback"""
        info("Manual refresh requested")
        self._needs_refresh = True

    def _add_security_alert(self, alert: SecurityAlert):
        """Add a security alert to the history"""
        for existing in self._security_alerts:
            if existing.command == alert.command:
                return

        self._security_alerts.insert(0, alert)

        if len(self._security_alerts) > self._max_alerts:
            self._security_alerts = self._security_alerts[: self._max_alerts]

        if alert.level == RiskLevel.CRITICAL:
            self._has_critical_alert = True
            info(f"🔴 CRITICAL: {alert.reason} - {alert.command[:50]}")
        elif alert.level == RiskLevel.HIGH:
            info(f"🟠 HIGH: {alert.reason} - {alert.command[:50]}")

    def _show_security_report(self, _):
        """Generate and open security report"""
        import tempfile
        import os

        auditor = get_auditor()
        report = auditor.generate_report()

        report_path = os.path.join(
            tempfile.gettempdir(), "opencode_security_report.txt"
        )
        with open(report_path, "w") as f:
            f.write(report)

        subprocess.run(["open", report_path])
        info(f"Security report opened: {report_path}")

    def _export_all_commands(self, _):
        """Export complete security audit history to a file"""
        import os
        from datetime import datetime as dt

        auditor = get_auditor()
        reporter = SecurityReporter()

        commands = auditor.get_all_commands(limit=10000)
        reads = auditor.get_all_reads(limit=10000)
        writes = auditor.get_all_writes(limit=10000)
        fetches = auditor.get_all_webfetches(limit=10000)

        content = reporter.generate_full_export(commands, reads, writes, fetches)

        export_dir = os.path.expanduser("~/.config/opencode-monitor")
        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        export_path = os.path.join(export_dir, f"security_audit_{timestamp}.txt")

        with open(export_path, "w") as f:
            f.write(content)

        subprocess.run(["open", export_path])
        info(f"Security audit exported: {export_path}")

    def _show_analytics(self, days: int):
        """Show analytics report for the specified period (runs in background)."""

        def run_in_background():
            import tempfile
            import os

            try:
                info(f"[Analytics] Starting for {days} days...")

                # Create a fresh DB connection for this thread
                info("[Analytics] Creating DB connection...")
                db = AnalyticsDB()

                # Load data on first access (check if DB has data)
                info("[Analytics] Checking DB stats...")
                stats = db.get_stats()
                info(f"[Analytics] Current stats: {stats}")

                if stats.get("messages", 0) == 0:
                    info("[Analytics] Loading OpenCode data...")
                    load_opencode_data(db, clear_first=True)
                    info("[Analytics] Data loaded!")

                info("[Analytics] Generating report...")
                report = generate_report(days, db=db, refresh_data=False)
                info("[Analytics] Converting to HTML...")
                report_html = report.to_html()
                info(f"[Analytics] HTML generated: {len(report_html)} bytes")

                report_path = os.path.join(
                    tempfile.gettempdir(), f"opencode_analytics_{days}d.html"
                )
                with open(report_path, "w") as f:
                    f.write(report_html)

                info(f"[Analytics] Opening {report_path}...")
                subprocess.run(["open", report_path])
                info(f"[Analytics] Done!")
                db.close()
            except Exception as e:
                error(f"[Analytics] Error: {e}")
                import traceback

                error(traceback.format_exc())

        thread = threading.Thread(target=run_in_background, daemon=True)
        thread.start()

    def _refresh_analytics(self, _):
        """Refresh analytics data from OpenCode storage (runs in background)."""

        def run_in_background():
            try:
                info("Refreshing OpenCode analytics data (background)...")
                db = AnalyticsDB()
                load_opencode_data(db, clear_first=True)
                db.close()
                info("Analytics data refreshed")
            except Exception as e:
                error(f"Analytics refresh error: {e}")

        thread = threading.Thread(target=run_in_background, daemon=True)
        thread.start()

    def _start_analytics_refresh(self):
        """Start background analytics refresh if data is stale (>24h old)."""

        def check_and_refresh():
            try:
                db = AnalyticsDB()
                if db.needs_refresh(max_age_hours=24):
                    info("[Analytics] Data is stale, refreshing in background...")
                    load_opencode_data(db, clear_first=True)
                    info("[Analytics] Background refresh complete")
                else:
                    debug("[Analytics] Data is fresh, skipping refresh")
                db.close()
            except Exception as e:
                error(f"[Analytics] Background refresh error: {e}")

        thread = threading.Thread(target=check_and_refresh, daemon=True)
        thread.start()

    def _run_monitor_loop(self):
        """Background monitoring loop"""
        info("OpenCode Monitor started (rumps)")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while self._running:
                start_time = time.time()

                try:
                    new_state = loop.run_until_complete(fetch_all_instances())

                    with self._state_lock:
                        self._state = new_state

                    current_busy_agents = set()
                    for instance in new_state.instances:
                        for agent in instance.agents:
                            if agent.status == SessionStatus.BUSY:
                                current_busy_agents.add(agent.id)

                    self._previous_busy_agents = current_busy_agents
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
    """Main entry point"""
    app = OpenCodeApp()
    app.run()


if __name__ == "__main__":
    main()
