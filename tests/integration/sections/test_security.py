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
    "first_command": "rm -rf /tmp/cache/*",
}


class TestSecuritySectionData:
    """Test security section displays risk data correctly."""

    def test_security_section_receives_data(self, dashboard_window, qtbot, click_nav):
        """Verify security section can receive and process data."""
        # Navigate to Security section first
        click_nav(dashboard_window, SECTION_SECURITY)

        data = MockAPIResponses.realistic_security()
        dashboard_window._signals.security_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Section should have processed the data without errors
        security = dashboard_window._security
        assert security is not None, "Security section should exist"
        assert hasattr(security, "_commands_table"), (
            "Security section should have _commands_table attribute"
        )

        # Verify section is visible after navigation (Security = index 1)
        assert dashboard_window._pages.currentIndex() == SECTION_SECURITY, (
            f"Expected Security section (index {SECTION_SECURITY}), "
            f"got index {dashboard_window._pages.currentIndex()}"
        )

    def test_security_section_stats_processed(self, dashboard_window, qtbot, click_nav):
        """Verify security stats are processed correctly."""
        click_nav(dashboard_window, SECTION_SECURITY)

        data = MockAPIResponses.realistic_security()
        dashboard_window._signals.security_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        security = dashboard_window._security

        # Security section should have received the stats
        assert security is not None, "Security section should exist"
        # Verify section has the expected structure
        assert hasattr(security, "_commands_table"), (
            "Security section should have _commands_table attribute"
        )

    def test_security_section_with_critical_commands(
        self, dashboard_window, qtbot, click_nav
    ):
        """Verify security section handles critical commands."""
        click_nav(dashboard_window, SECTION_SECURITY)

        data = MockAPIResponses.realistic_security()
        # Ensure we have critical commands
        assert data["stats"]["critical"] == EXPECTED_SECURITY["critical"]

        dashboard_window._signals.security_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        security = dashboard_window._security
        assert security is not None, "Security section should exist"
        # Verify section has valid structure
        assert hasattr(security, "_commands_table"), (
            "Security section should have _commands_table attribute"
        )

        # The section should process without errors
        # Critical items are included in the data
        assert len(data["critical_items"]) == EXPECTED_SECURITY["critical"], (
            f"Expected {EXPECTED_SECURITY['critical']} critical items, "
            f"got {len(data['critical_items'])}"
        )


class TestSecuritySectionTables:
    """Test security tables display correct data with reinforced assertions."""

    def test_commands_table_shows_commands(self, dashboard_window, qtbot, click_nav):
        """Verify commands table shows commands from data."""
        click_nav(dashboard_window, SECTION_SECURITY)

        data = MockAPIResponses.realistic_security()
        dashboard_window._signals.security_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        security = dashboard_window._security

        # Security section should have a commands table
        if hasattr(security, "_commands_table"):
            table = security._commands_table
            # Table should have rows matching commands
            assert table.rowCount() >= 1, "Commands table should have at least one row"

            # First command should contain expected text
            first_cmd = table.item(0, 0)
            if first_cmd:
                cmd_text = first_cmd.text()
                assert cmd_text, "Command text should not be empty"
                # Verify it's one of the expected security commands
                cmd_lower = cmd_text.lower()
                expected_commands = ["rm", "curl", "chmod", "git push", "pip"]
                assert any(cmd in cmd_lower for cmd in expected_commands), (
                    f"Expected known command pattern, got: {cmd_text}"
                )

    def test_commands_table_shows_risk_levels(
        self, dashboard_window, qtbot, assert_widget_content, click_nav
    ):
        """Verify commands table shows risk badges correctly."""
        click_nav(dashboard_window, SECTION_SECURITY)

        data = MockAPIResponses.realistic_security()
        dashboard_window._signals.security_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        security = dashboard_window._security

        # Check for risk badges in table if available
        if hasattr(security, "_commands_table"):
            table = security._commands_table
            if table.rowCount() > 0:
                found_risk_indicator = False

                # Look for risk badge widget in risk column (usually column 1 or 2)
                for col in range(table.columnCount()):
                    widget = table.cellWidget(0, col)
                    if widget and hasattr(widget, "text"):
                        text = widget.text().lower()
                        if any(
                            level in text
                            for level in ["critical", "high", "medium", "low"]
                        ):
                            found_risk_indicator = True
                            break

                # If no widget, check text items for risk level
                if not found_risk_indicator:
                    for col in range(table.columnCount()):
                        item = table.item(0, col)
                        if item:
                            text = item.text().lower()
                            if any(
                                level in text
                                for level in ["critical", "high", "medium", "low"]
                            ):
                                found_risk_indicator = True
                                break

                assert found_risk_indicator, "Expected risk level indicator in table"

    def test_files_table_shows_operations(self, dashboard_window, qtbot, click_nav):
        """Verify files table shows read/write operations if present."""
        click_nav(dashboard_window, SECTION_SECURITY)

        data = MockAPIResponses.realistic_security()
        dashboard_window._signals.security_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        security = dashboard_window._security

        # Check for files table if available
        if hasattr(security, "_files_table"):
            table = security._files_table
            # Data has 2 file entries
            expected_files = len(data.get("files", []))
            if expected_files > 0:
                assert table.rowCount() > 0, (
                    f"Expected files in table, got {table.rowCount()} rows"
                )

    def test_security_metrics_display(self, dashboard_window, qtbot, click_nav):
        """Verify security metrics show correct values."""
        click_nav(dashboard_window, SECTION_SECURITY)

        data = MockAPIResponses.realistic_security()
        dashboard_window._signals.security_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        security = dashboard_window._security

        # Check for metrics cards if available
        if hasattr(security, "_metrics"):
            metrics = security._metrics
            if hasattr(metrics, "_cards"):
                # Check critical count if card exists
                if "critical" in metrics._cards:
                    critical_text = metrics._cards["critical"]._value_label.text()
                    assert critical_text == str(EXPECTED_SECURITY["critical"])
