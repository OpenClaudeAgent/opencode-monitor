"""
Tests for SecurityReporter - Generate security audit reports.

Tests verify that reports are correctly formatted with all data.
"""

import pytest

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

    def test_summary_report_structure(
        self, reporter: SecurityReporter, sample_stats: dict
    ):
        """Summary report contains header, stats and risk distribution"""
        report = reporter.generate_summary_report(sample_stats, [], [], [], [])

        # Header
        assert "OPENCODE SECURITY AUDIT REPORT" in report
        assert "Generated:" in report

        # Statistics
        assert "Total files scanned: 100" in report
        assert "Total commands: 50" in report
        assert "Total file reads: 30" in report
        assert "Total file writes: 15" in report
        assert "Total webfetches: 5" in report

        # Risk distribution
        assert "COMMANDS - RISK DISTRIBUTION" in report
        assert "Critical: 2" in report
        assert "FILE READS - RISK DISTRIBUTION" in report
        assert "reads_critical" not in report  # Should be formatted nicely

    @pytest.mark.parametrize(
        "item_type,section_title,expected_content",
        [
            ("command", "TOP CRITICAL/HIGH RISK COMMANDS", ["rm -rf /tmp/*", "[85]"]),
            ("read", "TOP SENSITIVE FILE READS", ["/home/user/.ssh/id_rsa"]),
            ("write", "TOP SENSITIVE FILE WRITES/EDITS", ["/etc/passwd", "(write)"]),
            ("fetch", "TOP RISKY WEBFETCHES", ["pastebin.com"]),
        ],
        ids=["commands", "reads", "writes", "fetches"],
    )
    def test_summary_report_with_items(
        self,
        reporter: SecurityReporter,
        sample_stats: dict,
        sample_command: AuditedCommand,
        sample_read: AuditedFileRead,
        sample_write: AuditedFileWrite,
        sample_fetch: AuditedWebFetch,
        item_type: str,
        section_title: str,
        expected_content: list,
    ):
        """Summary report includes items by type with expected content"""
        items = {
            "command": ([sample_command], [], [], []),
            "read": ([], [sample_read], [], []),
            "write": ([], [], [sample_write], []),
            "fetch": ([], [], [], [sample_fetch]),
        }
        commands, reads, writes, fetches = items[item_type]
        report = reporter.generate_summary_report(
            sample_stats, commands, reads, writes, fetches
        )

        assert section_title in report
        for content in expected_content:
            assert content in report

    def test_summary_empty_sections_not_shown(
        self, reporter: SecurityReporter, sample_stats: dict
    ):
        """Empty sections are not included in report"""
        report = reporter.generate_summary_report(sample_stats, [], [], [], [])

        assert "TOP CRITICAL/HIGH RISK COMMANDS" not in report
        assert "TOP SENSITIVE FILE READS" not in report
        assert "TOP SENSITIVE FILE WRITES/EDITS" not in report
        assert "TOP RISKY WEBFETCHES" not in report

    @pytest.mark.parametrize(
        "stats,expected_content",
        [
            # Empty stats - all zeros
            (
                {
                    "total_scanned": 0,
                    "total_commands": 0,
                    "total_reads": 0,
                    "total_writes": 0,
                    "total_webfetches": 0,
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                },
                ["OPENCODE SECURITY AUDIT REPORT", "Total files scanned: 0"],
            ),
            # Missing stats - defaults to zero
            ({}, ["Total files scanned: 0"]),
            # Last scan never
            ({"last_scan": None}, ["Last scan: Never"]),
        ],
        ids=["empty_stats", "missing_stats", "last_scan_never"],
    )
    def test_summary_edge_cases(
        self,
        reporter: SecurityReporter,
        stats: dict,
        expected_content: list,
    ):
        """Summary report handles edge cases correctly"""
        report = reporter.generate_summary_report(stats, [], [], [], [])

        for content in expected_content:
            assert content in report


# =====================================================
# Full Export Tests
# =====================================================


class TestFullExport:
    """Tests for full export generation"""

    def test_full_export_structure(
        self,
        reporter: SecurityReporter,
        sample_command: AuditedCommand,
        sample_read: AuditedFileRead,
    ):
        """Full export contains header, counts and groups by risk level"""
        report = reporter.generate_full_export([sample_command], [sample_read], [], [])

        # Header
        assert "OPENCODE SECURITY AUDIT LOG" in report
        assert "Exported:" in report

        # Counts
        assert "Total commands: 1" in report
        assert "Total file reads: 1" in report
        assert "Total file writes: 0" in report

        # Risk level grouping
        assert "CRITICAL" in report

    @pytest.mark.parametrize(
        "item_type,section_marker,expected_details",
        [
            (
                "command",
                "COMMANDS",
                [
                    "Score: 85",
                    "Recursive delete",
                    "Session: sess-001",
                    "Command: rm -rf /tmp/*",
                ],
            ),
            (
                "read",
                "FILE READS",
                ["File: /home/user/.ssh/id_rsa"],
            ),
            (
                "write",
                "FILE WRITES/EDITS",
                ["Operation: write", "File: /etc/passwd"],
            ),
            (
                "fetch",
                "WEB FETCHES",
                ["URL: https://pastebin.com/raw/abc123"],
            ),
        ],
        ids=["command_details", "read_details", "write_details", "fetch_details"],
    )
    def test_full_export_item_details(
        self,
        reporter: SecurityReporter,
        sample_command: AuditedCommand,
        sample_read: AuditedFileRead,
        sample_write: AuditedFileWrite,
        sample_fetch: AuditedWebFetch,
        item_type: str,
        section_marker: str,
        expected_details: list,
    ):
        """Full export includes correct details for each item type"""
        items = {
            "command": ([sample_command], [], [], []),
            "read": ([], [sample_read], [], []),
            "write": ([], [], [sample_write], []),
            "fetch": ([], [], [], [sample_fetch]),
        }
        commands, reads, writes, fetches = items[item_type]
        report = reporter.generate_full_export(commands, reads, writes, fetches)

        assert section_marker in report
        for detail in expected_details:
            assert detail in report

    def test_full_export_risk_ordering(self, reporter: SecurityReporter):
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

        critical_pos = report.find("CRITICAL")
        high_pos = report.find("HIGH")
        low_pos = report.find("LOW")

        assert critical_pos < high_pos < low_pos


# =====================================================
# Formatting Tests
# =====================================================


class TestFormatting:
    """Tests for timestamp and distribution formatting"""

    @pytest.mark.parametrize(
        "timestamp,expected",
        [
            (1703001000000, "2023-12"),  # Valid timestamp contains date
            (0, "N/A"),  # Zero returns N/A
            (None, "N/A"),  # None returns N/A
        ],
        ids=["valid_timestamp", "zero_timestamp", "none_timestamp"],
    )
    def test_format_timestamp(
        self, reporter: SecurityReporter, timestamp, expected: str
    ):
        """Timestamp formatting handles various inputs"""
        result = reporter._format_timestamp(timestamp)

        if expected == "N/A":
            assert result == "N/A"
        else:
            assert expected in result
            assert ":" in result  # Contains time

    @pytest.mark.parametrize(
        "title,prefix,expected_value",
        [
            ("TEST", "", "Critical: 2"),  # No prefix uses base stats
            ("FILE READS", "reads_", "Critical: 1"),  # Prefix uses reads_critical
        ],
        ids=["no_prefix", "with_prefix"],
    )
    def test_format_distribution(
        self,
        reporter: SecurityReporter,
        sample_stats: dict,
        title: str,
        prefix: str,
        expected_value: str,
    ):
        """Distribution formatting uses correct prefix for lookups"""
        lines = reporter._format_distribution(title, sample_stats, prefix)
        combined = "\n".join(lines)

        assert "Critical:" in combined
        assert "High:" in combined
        assert "Medium:" in combined
        assert "Low:" in combined
        assert expected_value in combined

    @pytest.mark.parametrize(
        "risk_level,emoji_code",
        [
            ("critical", "\U0001f534"),  # Red circle for critical
            ("high", "\U0001f7e0"),  # Orange circle for high
        ],
        ids=["critical_red", "high_orange"],
    )
    def test_risk_level_emojis(
        self,
        reporter: SecurityReporter,
        risk_level: str,
        emoji_code: str,
    ):
        """Risk levels use correct emoji indicators"""
        if risk_level == "critical":
            item = AuditedCommand(
                id=1,
                file_id="c1",
                session_id="s1",
                tool="bash",
                command="cmd",
                risk_score=85,
                risk_level="critical",
                risk_reason="reason",
                timestamp=1000,
                scanned_at="2024-01-01",
            )
            report = reporter.generate_full_export([item], [], [], [])
        else:
            item = AuditedFileWrite(
                id=1,
                file_id="w1",
                session_id="s1",
                file_path="/path",
                operation="write",
                risk_score=60,
                risk_level="high",
                risk_reason="reason",
                timestamp=1000,
                scanned_at="2024-01-01",
            )
            report = reporter.generate_full_export([], [], [item], [])

        assert emoji_code in report
