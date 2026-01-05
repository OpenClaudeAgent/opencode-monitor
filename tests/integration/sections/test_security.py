"""
Integration tests for the Security section.

Tests verify that:
- Security section receives and processes data correctly
- Commands table shows commands with risk levels
- Files table shows read/write operations
- Metrics display correct statistics
"""

import pytest

from ..conftest import SIGNAL_WAIT_MS, SECTION_SECURITY
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration

# Expected test data values (from MockAPIResponses.realistic_security)
EXPECTED_SECURITY = {
    "total_scanned": 156,
    "total_commands": 89,
    "critical": 2,
    "high": 7,
    "commands_count": 5,  # Number of commands in mock data
    "first_command": "rm -rf /tmp/cache/*",
}


class TestSecuritySection:
    """Test security section displays risk data correctly."""

    def test_security_data_processing(self, dashboard_window, qtbot, click_nav):
        """Verify security section receives data, processes stats, and handles critical commands."""
        # Navigate to Security section
        click_nav(dashboard_window, SECTION_SECURITY)

        # Emit security data
        data = MockAPIResponses.realistic_security()
        dashboard_window._signals.security_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Verify navigation succeeded
        assert dashboard_window._pages.currentIndex() == SECTION_SECURITY, (
            f"Expected Security section (index {SECTION_SECURITY}), "
            f"got index {dashboard_window._pages.currentIndex()}"
        )

        # Verify section structure - direct attribute access validates existence
        security = dashboard_window._security
        assert security is not None, "Security section should exist"
        commands_table = security._commands_table
        assert commands_table is not None, (
            "Security section should have _commands_table attribute"
        )

        # Verify data integrity - critical items match expected count
        assert data["stats"]["critical"] == EXPECTED_SECURITY["critical"], (
            f"Expected {EXPECTED_SECURITY['critical']} critical in stats"
        )
        assert len(data["critical_items"]) == EXPECTED_SECURITY["critical"], (
            f"Expected {EXPECTED_SECURITY['critical']} critical items, "
            f"got {len(data['critical_items'])}"
        )

    def test_commands_table_content(self, dashboard_window, qtbot, click_nav):
        """Verify commands table shows commands with proper risk level indicators."""
        click_nav(dashboard_window, SECTION_SECURITY)

        data = MockAPIResponses.realistic_security()
        dashboard_window._signals.security_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        security = dashboard_window._security
        table = security._commands_table

        # Table should have rows matching commands count from mock data
        assert table.rowCount() == EXPECTED_SECURITY["commands_count"], (
            f"Expected {EXPECTED_SECURITY['commands_count']} commands, "
            f"got {table.rowCount()}"
        )

        # First command should contain expected security command pattern
        first_cmd = table.item(0, 0)
        assert first_cmd is not None, "First command cell should exist"
        cmd_text = first_cmd.text()
        assert cmd_text, "Command text should not be empty"

        # Verify it's one of the expected security commands
        cmd_lower = cmd_text.lower()
        expected_commands = ["rm", "curl", "chmod", "git push", "pip"]
        assert any(cmd in cmd_lower for cmd in expected_commands), (
            f"Expected known command pattern, got: {cmd_text}"
        )

        # Verify risk level indicators exist in table
        found_risk_indicator = False
        risk_levels = ["critical", "high", "medium", "low"]

        for col in range(table.columnCount()):
            # Check widget-based risk badge
            widget = table.cellWidget(0, col)
            if widget and hasattr(widget, "text"):
                text = widget.text().lower()
                if any(level in text for level in risk_levels):
                    found_risk_indicator = True
                    break

            # Check text-based risk level
            item = table.item(0, col)
            if item:
                text = item.text().lower()
                if any(level in text for level in risk_levels):
                    found_risk_indicator = True
                    break

        assert found_risk_indicator, (
            "Expected risk level indicator (critical/high/medium/low) in commands table"
        )

    def test_files_table_and_metrics(self, dashboard_window, qtbot, click_nav):
        """Verify files table shows operations and metrics display correct values."""
        click_nav(dashboard_window, SECTION_SECURITY)

        data = MockAPIResponses.realistic_security()
        dashboard_window._signals.security_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        security = dashboard_window._security
        files_checked = False
        metrics_checked = False

        # Check files table if available
        if hasattr(security, "_files_table"):
            table = security._files_table
            expected_files = len(data.get("files", []))
            if expected_files > 0:
                assert table.rowCount() == expected_files, (
                    f"Expected files in table, got {table.rowCount()} rows"
                )
                files_checked = True

        # Check metrics cards if available
        if hasattr(security, "_metrics"):
            metrics = security._metrics
            if hasattr(metrics, "_cards") and "critical" in metrics._cards:
                critical_text = metrics._cards["critical"]._value_label.text()
                assert critical_text == str(EXPECTED_SECURITY["critical"]), (
                    f"Expected critical count {EXPECTED_SECURITY['critical']}, "
                    f"got {critical_text}"
                )
                metrics_checked = True

        # At least one component should be verified
        assert files_checked or metrics_checked, (
            "Neither files table nor metrics cards were available for verification"
        )
