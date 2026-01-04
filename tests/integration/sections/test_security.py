"""
Integration tests for the Security section.

Tests verify that:
- Security section receives and processes data correctly
- Commands table shows commands with risk levels
- Files table shows read/write operations
"""

import pytest

from ..conftest import SIGNAL_WAIT_MS, SECTION_SECURITY
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


@pytest.fixture
def security_with_data(dashboard_window, qtbot, click_nav):
    """Navigate to security section and emit realistic data."""
    click_nav(dashboard_window, SECTION_SECURITY)
    data = MockAPIResponses.realistic_security()
    dashboard_window._signals.security_updated.emit(data)
    qtbot.wait(SIGNAL_WAIT_MS)
    return dashboard_window._security, data


class TestSecuritySection:
    """Test security section displays risk data correctly."""

    def test_security_data_processing(self, security_with_data, dashboard_window):
        """Verify security section receives data and processes stats."""
        security, data = security_with_data

        assert dashboard_window._pages.currentIndex() == SECTION_SECURITY
        assert security is not None
        assert security._commands_table is not None

        # Verify data integrity - critical items match expected count
        assert data["stats"]["critical"] == 2
        assert len(data["critical_items"]) == 2

    def test_commands_table_content(self, security_with_data):
        """Verify commands table shows commands with proper risk level indicators."""
        security, data = security_with_data
        table = security._commands_table

        # Table should have 5 commands from mock data
        assert table.rowCount() == 5

        # First command should exist with text
        first_cmd = table.item(0, 0)
        assert first_cmd is not None
        assert first_cmd.text()

        # Verify command matches expected patterns
        cmd_lower = first_cmd.text().lower()
        expected_commands = ["rm", "curl", "chmod", "git push", "pip"]
        assert any(cmd in cmd_lower for cmd in expected_commands)

        # Verify risk level indicator exists
        risk_levels = ["critical", "high", "medium", "low"]
        found_risk = False

        for col in range(table.columnCount()):
            widget = table.cellWidget(0, col)
            if widget and hasattr(widget, "text"):
                if any(level in widget.text().lower() for level in risk_levels):
                    found_risk = True
                    break
            item = table.item(0, col)
            if item and any(level in item.text().lower() for level in risk_levels):
                found_risk = True
                break

        assert found_risk

    def test_files_table_and_metrics(self, security_with_data):
        """Verify files table shows operations and metrics display correct values."""
        security, data = security_with_data
        verified = False

        # Check files table if available
        if hasattr(security, "_files_table"):
            table = security._files_table
            expected_files = len(data.get("files", []))
            if expected_files > 0:
                assert table.rowCount() == expected_files
                verified = True

        # Check metrics cards if available
        if hasattr(security, "_metrics"):
            metrics = security._metrics
            if hasattr(metrics, "_cards") and "critical" in metrics._cards:
                critical_text = metrics._cards["critical"]._value_label.text()
                assert critical_text == "2"
                verified = True

        assert verified, "Neither files table nor metrics cards available"
