"""
Tests for SecurityReporter - Generate security audit reports.

Tests verify that reports are correctly formatted with all data.
"""

import pytest
from datetime import datetime

from opencode_monitor.security.reporter import SecurityReporter
from opencode_monitor.security.db import (
    AuditedCommand,
    AuditedFileRead,
    AuditedFileWrite,
    AuditedWebFetch,
)


@pytest.fixture
def reporter() -> SecurityReporter:
    """Create a fresh SecurityReporter for each test"""
    return SecurityReporter()


@pytest.fixture
def sample_stats() -> dict:
    """Sample statistics for testing"""
    return {
        "total_scanned": 100,
        "total_commands": 50,
        "total_reads": 30,
        "total_writes": 15,
        "total_webfetches": 5,
        "last_scan": "2024-12-19 10:00:00",
        "critical": 2,
        "high": 5,
        "medium": 10,
        "low": 33,
        "reads_critical": 1,
        "reads_high": 3,
        "reads_medium": 8,
        "reads_low": 18,
        "writes_critical": 1,
        "writes_high": 2,
        "writes_medium": 5,
        "writes_low": 7,
        "webfetches_critical": 0,
        "webfetches_high": 1,
        "webfetches_medium": 2,
        "webfetches_low": 2,
    }


@pytest.fixture
def sample_command() -> AuditedCommand:
    """Sample audited command"""
    return AuditedCommand(
        id=1,
        file_id="cmd-001",
        session_id="sess-001",
        tool="bash",
        command="rm -rf /tmp/*",
        risk_score=85,
        risk_level="critical",
        risk_reason="Recursive delete with wildcard",
        timestamp=1703001000000,
        scanned_at="2024-12-19T10:00:00",
    )


@pytest.fixture
def sample_read() -> AuditedFileRead:
    """Sample audited file read"""
    return AuditedFileRead(
        id=1,
        file_id="read-001",
        session_id="sess-001",
        file_path="/home/user/.ssh/id_rsa",
        risk_score=95,
        risk_level="critical",
        risk_reason="SSH private key",
        timestamp=1703002000000,
        scanned_at="2024-12-19T10:10:00",
    )


@pytest.fixture
def sample_write() -> AuditedFileWrite:
    """Sample audited file write"""
    return AuditedFileWrite(
        id=1,
        file_id="write-001",
        session_id="sess-001",
        file_path="/etc/passwd",
        operation="write",
        risk_score=60,
        risk_level="high",
        risk_reason="System passwd file",
        timestamp=1703003000000,
        scanned_at="2024-12-19T10:20:00",
    )


@pytest.fixture
def sample_fetch() -> AuditedWebFetch:
    """Sample audited webfetch"""
    return AuditedWebFetch(
        id=1,
        file_id="fetch-001",
        session_id="sess-001",
        url="https://pastebin.com/raw/abc123",
        risk_score=85,
        risk_level="critical",
        risk_reason="Pastebin content",
        timestamp=1703004000000,
        scanned_at="2024-12-19T10:30:00",
    )


# =====================================================
# Summary Report Tests
# =====================================================


class TestSummaryReport:
    """Tests for summary report generation"""

    def test_generate_summary_contains_header(
        self, reporter: SecurityReporter, sample_stats: dict
    ):
        """Summary report contains header"""
        report = reporter.generate_summary_report(sample_stats, [], [], [], [])

        assert "OPENCODE SECURITY AUDIT REPORT" in report
        assert "Generated:" in report

    def test_generate_summary_contains_stats(
        self, reporter: SecurityReporter, sample_stats: dict
    ):
        """Summary report contains statistics"""
        report = reporter.generate_summary_report(sample_stats, [], [], [], [])

        assert "Total files scanned: 100" in report
        assert "Total commands: 50" in report
        assert "Total file reads: 30" in report
        assert "Total file writes: 15" in report
        assert "Total webfetches: 5" in report

    def test_generate_summary_contains_risk_distribution(
        self, reporter: SecurityReporter, sample_stats: dict
    ):
        """Summary report contains risk distribution"""
        report = reporter.generate_summary_report(sample_stats, [], [], [], [])

        # Commands distribution
        assert "COMMANDS - RISK DISTRIBUTION" in report
        assert "Critical: 2" in report

        # Reads distribution
        assert "FILE READS - RISK DISTRIBUTION" in report
        assert "reads_critical" not in report  # Should be formatted nicely

    def test_generate_summary_with_critical_commands(
        self,
        reporter: SecurityReporter,
        sample_stats: dict,
        sample_command: AuditedCommand,
    ):
        """Summary report includes critical commands"""
        report = reporter.generate_summary_report(
            sample_stats, [sample_command], [], [], []
        )

        assert "TOP CRITICAL/HIGH RISK COMMANDS" in report
        assert "rm -rf /tmp/*" in report
        assert "[85]" in report  # Risk score

    def test_generate_summary_with_sensitive_reads(
        self,
        reporter: SecurityReporter,
        sample_stats: dict,
        sample_read: AuditedFileRead,
    ):
        """Summary report includes sensitive reads"""
        report = reporter.generate_summary_report(
            sample_stats, [], [sample_read], [], []
        )

        assert "TOP SENSITIVE FILE READS" in report
        assert "/home/user/.ssh/id_rsa" in report

    def test_generate_summary_with_sensitive_writes(
        self,
        reporter: SecurityReporter,
        sample_stats: dict,
        sample_write: AuditedFileWrite,
    ):
        """Summary report includes sensitive writes"""
        report = reporter.generate_summary_report(
            sample_stats, [], [], [sample_write], []
        )

        assert "TOP SENSITIVE FILE WRITES/EDITS" in report
        assert "/etc/passwd" in report
        assert "(write)" in report  # Operation

    def test_generate_summary_with_risky_fetches(
        self,
        reporter: SecurityReporter,
        sample_stats: dict,
        sample_fetch: AuditedWebFetch,
    ):
        """Summary report includes risky fetches"""
        report = reporter.generate_summary_report(
            sample_stats, [], [], [], [sample_fetch]
        )

        assert "TOP RISKY WEBFETCHES" in report
        assert "pastebin.com" in report

    def test_generate_summary_empty_sections_not_shown(
        self, reporter: SecurityReporter, sample_stats: dict
    ):
        """Empty sections are not included in report"""
        report = reporter.generate_summary_report(sample_stats, [], [], [], [])

        assert "TOP CRITICAL/HIGH RISK COMMANDS" not in report
        assert "TOP SENSITIVE FILE READS" not in report
        assert "TOP SENSITIVE FILE WRITES/EDITS" not in report
        assert "TOP RISKY WEBFETCHES" not in report


# =====================================================
# Full Export Tests
# =====================================================


class TestFullExport:
    """Tests for full export generation"""

    def test_generate_export_contains_header(self, reporter: SecurityReporter):
        """Full export contains header"""
        report = reporter.generate_full_export([], [], [], [])

        assert "OPENCODE SECURITY AUDIT LOG" in report
        assert "Exported:" in report

    def test_generate_export_contains_counts(
        self,
        reporter: SecurityReporter,
        sample_command: AuditedCommand,
        sample_read: AuditedFileRead,
    ):
        """Full export contains item counts"""
        report = reporter.generate_full_export([sample_command], [sample_read], [], [])

        assert "Total commands: 1" in report
        assert "Total file reads: 1" in report
        assert "Total file writes: 0" in report

    def test_generate_export_groups_by_risk_level(
        self, reporter: SecurityReporter, sample_command: AuditedCommand
    ):
        """Full export groups items by risk level"""
        report = reporter.generate_full_export([sample_command], [], [], [])

        assert "CRITICAL" in report

    def test_generate_export_includes_command_details(
        self, reporter: SecurityReporter, sample_command: AuditedCommand
    ):
        """Full export includes command details"""
        report = reporter.generate_full_export([sample_command], [], [], [])

        assert "Score: 85" in report
        assert "Recursive delete" in report
        assert "Session: sess-001" in report
        assert "Command: rm -rf /tmp/*" in report

    def test_generate_export_includes_read_details(
        self, reporter: SecurityReporter, sample_read: AuditedFileRead
    ):
        """Full export includes file read details"""
        report = reporter.generate_full_export([], [sample_read], [], [])

        assert "FILE READS" in report
        assert "File: /home/user/.ssh/id_rsa" in report

    def test_generate_export_includes_write_details(
        self, reporter: SecurityReporter, sample_write: AuditedFileWrite
    ):
        """Full export includes file write details"""
        report = reporter.generate_full_export([], [], [sample_write], [])

        assert "FILE WRITES/EDITS" in report
        assert "Operation: write" in report
        assert "File: /etc/passwd" in report

    def test_generate_export_includes_fetch_details(
        self, reporter: SecurityReporter, sample_fetch: AuditedWebFetch
    ):
        """Full export includes webfetch details"""
        report = reporter.generate_full_export([], [], [], [sample_fetch])

        assert "WEB FETCHES" in report
        assert "URL: https://pastebin.com/raw/abc123" in report


# =====================================================
# Timestamp Formatting Tests
# =====================================================


class TestTimestampFormatting:
    """Tests for timestamp formatting"""

    def test_format_valid_timestamp(self, reporter: SecurityReporter):
        """Valid timestamp is formatted correctly"""
        # 1703001000000 = 2023-12-19 ~16:50 UTC (milliseconds timestamp)
        result = reporter._format_timestamp(1703001000000)

        assert "2023-12" in result
        assert ":" in result  # Contains time

    def test_format_zero_timestamp(self, reporter: SecurityReporter):
        """Zero timestamp returns N/A"""
        result = reporter._format_timestamp(0)

        assert result == "N/A"

    def test_format_none_timestamp(self, reporter: SecurityReporter):
        """None timestamp returns N/A"""
        result = reporter._format_timestamp(None)

        assert result == "N/A"


# =====================================================
# Risk Level Emoji Tests
# =====================================================


class TestRiskLevelEmojis:
    """Tests for risk level emoji indicators"""

    def test_critical_uses_red_emoji(
        self, reporter: SecurityReporter, sample_command: AuditedCommand
    ):
        """Critical items use red emoji"""
        report = reporter.generate_full_export([sample_command], [], [], [])

        # The report should contain 🔴 for critical
        assert "\U0001f534" in report  # Red circle emoji

    def test_high_uses_orange_emoji(
        self, reporter: SecurityReporter, sample_write: AuditedFileWrite
    ):
        """High items use orange emoji"""
        report = reporter.generate_full_export([], [], [sample_write], [])

        # The report should contain 🟠 for high
        assert "\U0001f7e0" in report  # Orange circle emoji


# =====================================================
# Distribution Formatting Tests
# =====================================================


class TestDistributionFormatting:
    """Tests for risk distribution formatting"""

    def test_format_distribution_all_levels(
        self, reporter: SecurityReporter, sample_stats: dict
    ):
        """Distribution includes all risk levels"""
        lines = reporter._format_distribution("TEST", sample_stats, "")

        combined = "\n".join(lines)
        assert "Critical:" in combined
        assert "High:" in combined
        assert "Medium:" in combined
        assert "Low:" in combined

    def test_format_distribution_with_prefix(
        self, reporter: SecurityReporter, sample_stats: dict
    ):
        """Distribution correctly uses prefix for lookups"""
        lines = reporter._format_distribution("FILE READS", sample_stats, "reads_")

        combined = "\n".join(lines)
        # Should get reads_critical=1, not critical=2
        assert "Critical: 1" in combined


# =====================================================
# Edge Cases
# =====================================================


class TestEdgeCases:
    """Tests for edge cases"""

    def test_empty_report_still_valid(self, reporter: SecurityReporter):
        """Empty report is still valid structure"""
        empty_stats = {
            "total_scanned": 0,
            "total_commands": 0,
            "total_reads": 0,
            "total_writes": 0,
            "total_webfetches": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }

        report = reporter.generate_summary_report(empty_stats, [], [], [], [])

        assert "OPENCODE SECURITY AUDIT REPORT" in report
        assert "Total files scanned: 0" in report

    def test_missing_stats_defaults_to_zero(self, reporter: SecurityReporter):
        """Missing stats default to zero"""
        partial_stats = {}

        report = reporter.generate_summary_report(partial_stats, [], [], [], [])

        assert "Total files scanned: 0" in report

    def test_last_scan_never(self, reporter: SecurityReporter):
        """Handles case when last_scan is None"""
        stats = {"last_scan": None}

        report = reporter.generate_summary_report(stats, [], [], [], [])

        assert "Last scan: Never" in report


# =====================================================
# Multiple Items Tests
# =====================================================


class TestMultipleItems:
    """Tests with multiple items of mixed risk levels"""

    def test_export_orders_by_risk_level(self, reporter: SecurityReporter):
        """Export orders sections by risk level (critical first)"""
        commands = [
            AuditedCommand(
                id=1,
                file_id="c1",
                session_id="s1",
                tool="bash",
                command="cmd1",
                risk_score=90,
                risk_level="critical",
                risk_reason="Critical reason",
                timestamp=1000,
                scanned_at="2024-01-01",
            ),
            AuditedCommand(
                id=2,
                file_id="c2",
                session_id="s1",
                tool="bash",
                command="cmd2",
                risk_score=50,
                risk_level="high",
                risk_reason="High reason",
                timestamp=1001,
                scanned_at="2024-01-01",
            ),
            AuditedCommand(
                id=3,
                file_id="c3",
                session_id="s1",
                tool="bash",
                command="cmd3",
                risk_score=10,
                risk_level="low",
                risk_reason="Low reason",
                timestamp=1002,
                scanned_at="2024-01-01",
            ),
        ]

        report = reporter.generate_full_export(commands, [], [], [])

        # Critical should appear before High which appears before Low
        critical_pos = report.find("CRITICAL")
        high_pos = report.find("HIGH")
        low_pos = report.find("LOW")

        assert critical_pos < high_pos < low_pos
