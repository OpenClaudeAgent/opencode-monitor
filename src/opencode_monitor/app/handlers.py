"""Handlers mixin for OpenCodeApp - Contains all callback methods."""

import subprocess  # nosec B404 - required for opening reports in OS
import threading
from typing import TYPE_CHECKING

from ..security.analyzer import SecurityAlert, RiskLevel
from ..security.reporter import SecurityReporter
from ..security.auditor import get_auditor
from ..ui.terminal import focus_iterm2
from ..dashboard import show_dashboard
from ..analytics import AnalyticsDB, load_opencode_data
from ..utils.logger import info, error, debug


if TYPE_CHECKING:
    pass


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

        subprocess.run(["open", report_path])  # nosec B603 B607 - trusted internal path
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

        subprocess.run(["open", export_path])  # nosec B603 B607 - trusted internal path
        info(f"Security audit exported: {export_path}")
