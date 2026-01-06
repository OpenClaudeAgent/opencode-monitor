"""
Menu mixin for OpenCodeApp - Contains menu building methods.

This module provides the MenuMixin class with:
- Static menu building (_build_static_menu)
- Dynamic menu building (_build_menu)
- Callback factories for preferences
"""

import threading
from typing import TYPE_CHECKING, Optional

import rumps

from ..core.models import State, Usage
from ..ui.menu import MenuBuilder
from ..utils.settings import get_settings, save_settings
from ..utils.logger import info
from ..security.auditor import get_auditor

if TYPE_CHECKING:
    pass


class MenuMixin:
    """Mixin providing menu building methods for OpenCodeApp."""

    # Type hints for attributes from OpenCodeApp
    USAGE_INTERVALS: list[int]
    ASK_USER_TIMEOUTS: list[int]
    _state: Optional[State]
    _usage: Optional[Usage]
    _state_lock: threading.Lock
    _menu_builder: MenuBuilder
    _has_critical_alert: bool

    # Menu items (will be set by _build_static_menu)
    _prefs_menu: rumps.MenuItem
    _dashboard_item: rumps.MenuItem
    _refresh_item: rumps.MenuItem
    _quit_item: rumps.MenuItem

    # Handlers (will be provided by HandlersMixin)
    def _focus_terminal(self, tty: str): ...
    def _add_security_alert(self, alert): ...
    def _show_security_report(self, _): ...
    def _export_all_commands(self, _): ...
    def _show_analytics(self, days: int): ...
    def _refresh_analytics(self, _): ...
    def _on_refresh(self, _): ...
    def _show_dashboard(self, _): ...

    def _build_static_menu(self):
        """Build the static menu items."""
        settings = get_settings()

        # Preferences submenu
        self._prefs_menu = rumps.MenuItem("⚙️ Preferences")

        # Usage refresh submenu
        refresh_menu = rumps.MenuItem("⏱️ Usage refresh")
        refresh_menu._menuitem.setToolTip_(
            "How often to fetch Claude API usage from Anthropic"
        )
        for interval in self.USAGE_INTERVALS:
            label = f"{interval}s" if interval < 60 else f"{interval // 60}m"
            item = rumps.MenuItem(
                label, callback=self._make_interval_callback(interval)
            )
            item.state = 1 if settings.usage_refresh_interval == interval else 0
            refresh_menu.add(item)
        self._prefs_menu.add(refresh_menu)

        # Ask user timeout submenu
        ask_timeout_menu = rumps.MenuItem("🔔 Ask user timeout")
        ask_timeout_menu._menuitem.setToolTip_(
            "How long to show 🔔 before dismissing.\n"
            "If you don't respond within this time, the notification is hidden."
        )
        for timeout in self.ASK_USER_TIMEOUTS:
            label = f"{timeout // 60}m" if timeout < 3600 else f"{timeout // 3600}h"
            item = rumps.MenuItem(
                label, callback=self._make_ask_timeout_callback(timeout)
            )
            item.state = 1 if settings.ask_user_timeout == timeout else 0
            ask_timeout_menu.add(item)
        self._prefs_menu.add(ask_timeout_menu)

        # Static items
        self._dashboard_item = rumps.MenuItem(
            "📊 Dashboard", callback=self._show_dashboard
        )
        self._refresh_item = rumps.MenuItem("🔄 Refresh", callback=self._on_refresh)
        self._quit_item = rumps.MenuItem("Quit", callback=rumps.quit_application)

        # Initial menu
        self.menu = [
            rumps.MenuItem("Loading...", callback=None),
            None,
            self._dashboard_item,
            self._refresh_item,
            None,
            self._prefs_menu,
            None,
            self._quit_item,
        ]

    def _make_interval_callback(self, interval: int):
        """Create a callback for setting usage refresh interval."""

        def callback(sender):
            settings = get_settings()
            settings.usage_refresh_interval = interval
            save_settings()
            for item in sender.parent.values():
                item.state = 0
            sender.state = 1
            info(f"Usage refresh interval set to {interval}s")

        return callback

    def _make_ask_timeout_callback(self, timeout: int):
        """Create a callback for setting ask_user timeout."""

        def callback(sender):
            settings = get_settings()
            settings.ask_user_timeout = timeout
            save_settings()
            for item in sender.parent.values():
                item.state = 0
            sender.state = 1
            label = f"{timeout // 60}m" if timeout < 3600 else f"{timeout // 3600}h"
            info(f"Ask user timeout set to {label}")

        return callback

    def _build_menu(self):
        """Build the menu from current state."""
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

        # Rebuild complete menu (rumps.App.menu has .add()/.clear() but no type stubs)
        self.menu.clear()  # type: ignore[attr-defined]
        for item in dynamic_items:
            self.menu.add(item)  # type: ignore[attr-defined]

        # Security menu
        self.menu.add(None)  # type: ignore[attr-defined]
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

        self.menu.add(security_menu)  # type: ignore[attr-defined]

        # Analytics menu
        analytics_menu = self._menu_builder.build_analytics_menu(
            analytics_callback=self._show_analytics,
            refresh_callback=self._refresh_analytics,
        )
        self.menu.add(analytics_menu)  # type: ignore[attr-defined]

        # Static items (rumps.App.menu has .add() method but no type stubs)
        self.menu.add(None)  # type: ignore[attr-defined]
        self.menu.add(self._dashboard_item)  # type: ignore[attr-defined]
        self.menu.add(self._refresh_item)  # type: ignore[attr-defined]
        self.menu.add(None)  # type: ignore[attr-defined]
        self.menu.add(self._prefs_menu)  # type: ignore[attr-defined]
        self.menu.add(None)  # type: ignore[attr-defined]
        self.menu.add(self._quit_item)  # type: ignore[attr-defined]
