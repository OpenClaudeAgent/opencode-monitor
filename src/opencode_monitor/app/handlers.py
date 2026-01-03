"""
Handlers mixin for OpenCodeApp - Contains all callback methods.

This module provides the HandlersMixin class with:
- Terminal focus handler
- Dashboard handler
- Security report handlers
- Analytics handlers
- Manual refresh handler
- AnalyticsSyncManager: DB sync manager (only writer to analytics DB)
"""

import subprocess
import threading
import time
from typing import TYPE_CHECKING

from ..security.analyzer import SecurityAlert, RiskLevel
from ..security.reporter import SecurityReporter
from ..security.auditor import get_auditor
from ..ui.terminal import focus_iterm2
from ..dashboard import show_dashboard
from ..analytics import AnalyticsDB, load_opencode_data, generate_report
from ..utils.logger import info, error, debug


class AnalyticsSyncManager:
    """Manages analytics DB sync - only process that writes to DB.

    The menubar is the sole writer to the analytics database. It:
    - Syncs data from OpenCode storage periodically
    - Updates sync_meta table to signal dashboard readers
    - Handles background sync with thread safety
    """

    SYNC_INTERVAL_S = 300  # 5 minutes fallback

    def __init__(self):
        """Initialize the sync manager."""
        self._db = AnalyticsDB(read_only=False)
        self._last_sync = 0.0
        self._lock = threading.Lock()

    def sync_incremental(self, max_days: int = 7) -> dict:
        """Sync recent data from OpenCode storage.

        Args:
            max_days: Maximum days of data to sync.

        Returns:
            Dict with sync results (sessions count, etc).
        """
        with self._lock:
            try:
                result = load_opencode_data(
                    db=self._db,
                    clear_first=False,
                    max_days=max_days,
                    skip_parts=True,
                )

                # Mark the sync as completed
                self._db.update_sync_timestamp()
                self._last_sync = time.time()

                sessions = result.get("sessions", 0)
                info(f"[Menubar] Analytics sync complete: {sessions} sessions")
                return result
            except Exception as e:
                error(f"[Menubar] Sync error: {e}")
                return {}

    def needs_sync(self) -> bool:
        """Check if periodic sync is needed.

        Returns:
            True if more than SYNC_INTERVAL_S since last sync.
        """
        return time.time() - self._last_sync > self.SYNC_INTERVAL_S

    def start_background_sync(self, max_days: int = 30) -> None:
        """Start sync in background thread.

        Args:
            max_days: Maximum days of data to sync.
        """

        def _sync():
            self.sync_incremental(max_days=max_days)

        threading.Thread(target=_sync, daemon=True).start()

    def close(self) -> None:
        """Close the database connection."""
        self._db.close()


if TYPE_CHECKING:
    from .core import OpenCodeApp


class HandlersMixin:
    """Mixin providing callback handlers for OpenCodeApp."""

    # Type hints for attributes from OpenCodeApp
    _security_alerts: list[SecurityAlert]
    _max_alerts: int
    _has_critical_alert: bool
    _needs_refresh: bool

    def _focus_terminal(self, tty: str):
        """Focus iTerm2 on the given TTY."""
        focus_iterm2(tty)

    def _on_refresh(self, _):
        """Manual refresh callback."""
        info("Manual refresh requested")
        self._needs_refresh = True

    def _show_dashboard(self, _):
        """Open the PyQt Dashboard window."""
        info("Opening Dashboard...")
        show_dashboard()

    def _add_security_alert(self, alert: SecurityAlert):
        """Add a security alert to the history."""
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
        """Generate and open security report."""
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
        """Export complete security audit history to a file."""
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
                db = AnalyticsDB()

                stats = db.get_stats()
                info(f"[Analytics] Current stats: {stats}")

                if stats.get("messages", 0) == 0:
                    info("[Analytics] Loading OpenCode data...")
                    load_opencode_data(db, clear_first=True)

                report = generate_report(days, db=db, refresh_data=False)
                report_html = report.to_html()

                report_path = os.path.join(
                    tempfile.gettempdir(), f"opencode_analytics_{days}d.html"
                )
                with open(report_path, "w") as f:
                    f.write(report_html)

                subprocess.run(["open", report_path])
                info("[Analytics] Done!")
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
