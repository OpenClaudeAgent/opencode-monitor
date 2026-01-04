"""
Tests for SecurityDatabase - SQLite repository for security audit data.

Tests use in-memory SQLite database for isolation and speed.
"""

import sqlite3
from pathlib import Path

import pytest

from opencode_monitor.security.db import (
    SecurityDatabase,
    AuditedCommand,
    AuditedFileRead,
    AuditedFileWrite,
    AuditedWebFetch,
)


@pytest.fixture
def db(tmp_path: Path) -> SecurityDatabase:
    """Create a fresh in-memory database for each test"""
    db_path = tmp_path / "test_security.db"
    return SecurityDatabase(db_path=db_path)


@pytest.fixture
def sample_command_data() -> dict:
    """Sample command data for testing"""
    return {
        "file_id": "cmd-001",
        "content_hash": "abc123",
        "session_id": "sess-001",
        "tool": "bash",
        "command": "rm -rf /tmp/test",
        "risk_score": 75,
        "risk_level": "high",
        "risk_reason": "Recursive delete",
        "timestamp": 1703001000000,
        "scanned_at": "2024-12-19T10:00:00",
    }


@pytest.fixture
def sample_read_data() -> dict:
    """Sample file read data for testing"""
    return {
        "file_id": "read-001",
        "content_hash": "def456",
        "session_id": "sess-001",
        "file_path": "/etc/passwd",
        "risk_score": 60,
        "risk_level": "high",
        "risk_reason": "System passwd file",
        "timestamp": 1703002000000,
        "scanned_at": "2024-12-19T10:10:00",
    }


@pytest.fixture
def sample_write_data() -> dict:
    """Sample file write data for testing"""
    return {
        "file_id": "write-001",
        "content_hash": "ghi789",
        "session_id": "sess-001",
        "file_path": "/home/user/.ssh/config",
        "operation": "edit",
        "risk_score": 95,
        "risk_level": "critical",
        "risk_reason": "SSH directory",
        "timestamp": 1703003000000,
        "scanned_at": "2024-12-19T10:20:00",
    }


@pytest.fixture
def sample_webfetch_data() -> dict:
    """Sample webfetch data for testing"""
    return {
        "file_id": "fetch-001",
        "content_hash": "jkl012",
        "session_id": "sess-001",
        "url": "https://pastebin.com/raw/abc123",
        "risk_score": 85,
        "risk_level": "critical",
        "risk_reason": "Pastebin content",
        "timestamp": 1703004000000,
        "scanned_at": "2024-12-19T10:30:00",
    }


# =====================================================
# Database Initialization Tests
# =====================================================


class TestDatabaseInit:
    """Tests for database initialization"""

    def test_init_creates_tables(self, db: SecurityDatabase):
        """Database initializes with all required tables"""
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()

        # Check all tables exist
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected_tables = {
            "commands",
            "file_reads",
            "file_writes",
            "webfetches",
            "scan_stats",
        }
        assert expected_tables.issubset(tables)

    def test_init_creates_indexes(self, db: SecurityDatabase):
        """Database creates performance indexes"""
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()

        # Verify key indexes exist
        assert "idx_file_id" in indexes
        assert "idx_risk_level" in indexes
        assert "idx_risk_score" in indexes


# =====================================================
# Command CRUD Tests
# =====================================================


class TestCommandCRUD:
    """Tests for command insert and query operations"""

    def test_insert_command_success(
        self, db: SecurityDatabase, sample_command_data: dict
    ):
        """Insert a command successfully"""
        result = db.insert_command(sample_command_data)
        assert result is True

    def test_insert_command_duplicate_ignored(
        self, db: SecurityDatabase, sample_command_data: dict
    ):
        """Duplicate command (same file_id) is ignored"""
        db.insert_command(sample_command_data)
        result = db.insert_command(sample_command_data)  # Same file_id
        assert result is False

    def test_get_commands_by_level(
        self, db: SecurityDatabase, sample_command_data: dict
    ):
        """Query commands by risk level"""
        db.insert_command(sample_command_data)

        results = db.get_commands_by_level(["high"])

        assert len(results) == 1
        assert isinstance(results[0], AuditedCommand)
        assert results[0].command == "rm -rf /tmp/test"
        assert results[0].risk_level == "high"

    def test_get_commands_by_multiple_levels(self, db: SecurityDatabase):
        """Query commands filtering by multiple risk levels"""
        # Insert commands with different risk levels
        for i, level in enumerate(["critical", "high", "medium", "low"]):
            db.insert_command(
                {
                    "file_id": f"cmd-{i}",
                    "content_hash": f"hash-{i}",
                    "session_id": "sess-001",
                    "tool": "bash",
                    "command": f"cmd-{level}",
                    "risk_score": 80 - (i * 20),
                    "risk_level": level,
                    "risk_reason": f"Test {level}",
                    "timestamp": 1703000000000 + i,
                    "scanned_at": "2024-12-19",
                }
            )

        results = db.get_commands_by_level(["critical", "high"])

        assert len(results) == 2
        levels = {r.risk_level for r in results}
        assert levels == {"critical", "high"}

    def test_get_all_commands_pagination(self, db: SecurityDatabase):
        """Get all commands with pagination"""
        # Insert 10 commands
        for i in range(10):
            db.insert_command(
                {
                    "file_id": f"cmd-{i:03d}",
                    "content_hash": f"hash-{i}",
                    "session_id": "sess-001",
                    "tool": "bash",
                    "command": f"command-{i}",
                    "risk_score": 50,
                    "risk_level": "high",
                    "risk_reason": "Test",
                    "timestamp": 1703000000000 + i * 1000,
                    "scanned_at": "2024-12-19",
                }
            )

        # Get first page
        page1 = db.get_all_commands(limit=5, offset=0)
        assert len(page1) == 5

        # Get second page
        page2 = db.get_all_commands(limit=5, offset=5)
        assert len(page2) == 5

        # Verify no overlap
        page1_ids = {c.file_id for c in page1}
        page2_ids = {c.file_id for c in page2}
        assert page1_ids.isdisjoint(page2_ids)


# =====================================================
# File Reads CRUD Tests
# =====================================================


class TestFileReadCRUD:
    """Tests for file read insert and query operations"""

    def test_insert_read_success(self, db: SecurityDatabase, sample_read_data: dict):
        """Insert a file read successfully"""
        result = db.insert_read(sample_read_data)
        assert result is True

    def test_insert_read_duplicate_ignored(
        self, db: SecurityDatabase, sample_read_data: dict
    ):
        """Duplicate file read (same file_id) is ignored"""
        db.insert_read(sample_read_data)
        result = db.insert_read(sample_read_data)
        assert result is False

    def test_get_reads_by_level(self, db: SecurityDatabase, sample_read_data: dict):
        """Query file reads by risk level"""
        db.insert_read(sample_read_data)

        results = db.get_reads_by_level(["high"])

        assert len(results) == 1
        assert isinstance(results[0], AuditedFileRead)
        assert results[0].file_path == "/etc/passwd"

    def test_get_all_reads(self, db: SecurityDatabase, sample_read_data: dict):
        """Get all file reads"""
        db.insert_read(sample_read_data)

        results = db.get_all_reads()

        assert len(results) == 1


# =====================================================
# File Writes CRUD Tests
# =====================================================


class TestFileWriteCRUD:
    """Tests for file write insert and query operations"""

    def test_insert_write_success(self, db: SecurityDatabase, sample_write_data: dict):
        """Insert a file write successfully"""
        result = db.insert_write(sample_write_data)
        assert result is True

    def test_insert_write_duplicate_ignored(
        self, db: SecurityDatabase, sample_write_data: dict
    ):
        """Duplicate file write (same file_id) is ignored"""
        db.insert_write(sample_write_data)
        result = db.insert_write(sample_write_data)
        assert result is False

    def test_get_writes_by_level(self, db: SecurityDatabase, sample_write_data: dict):
        """Query file writes by risk level"""
        db.insert_write(sample_write_data)

        results = db.get_writes_by_level(["critical"])

        assert len(results) == 1
        assert isinstance(results[0], AuditedFileWrite)
        assert results[0].file_path == "/home/user/.ssh/config"
        assert results[0].operation == "edit"

    def test_get_all_writes(self, db: SecurityDatabase, sample_write_data: dict):
        """Get all file writes"""
        db.insert_write(sample_write_data)

        results = db.get_all_writes()

        assert len(results) == 1


# =====================================================
# Webfetch CRUD Tests
# =====================================================


class TestWebfetchCRUD:
    """Tests for webfetch insert and query operations"""

    def test_insert_webfetch_success(
        self, db: SecurityDatabase, sample_webfetch_data: dict
    ):
        """Insert a webfetch successfully"""
        result = db.insert_webfetch(sample_webfetch_data)
        assert result is True

    def test_insert_webfetch_duplicate_ignored(
        self, db: SecurityDatabase, sample_webfetch_data: dict
    ):
        """Duplicate webfetch (same file_id) is ignored"""
        db.insert_webfetch(sample_webfetch_data)
        result = db.insert_webfetch(sample_webfetch_data)
        assert result is False

    def test_get_webfetches_by_level(
        self, db: SecurityDatabase, sample_webfetch_data: dict
    ):
        """Query webfetches by risk level"""
        db.insert_webfetch(sample_webfetch_data)

        results = db.get_webfetches_by_level(["critical"])

        assert len(results) == 1
        assert isinstance(results[0], AuditedWebFetch)
        assert "pastebin.com" in results[0].url

    def test_get_all_webfetches(self, db: SecurityDatabase, sample_webfetch_data: dict):
        """Get all webfetches"""
        db.insert_webfetch(sample_webfetch_data)

        results = db.get_all_webfetches()

        assert len(results) == 1


# =====================================================
# Statistics Tests
# =====================================================


class TestStatistics:
    """Tests for statistics and aggregation"""

    def test_get_stats_empty_database(self, db: SecurityDatabase):
        """Get stats from empty database"""
        stats = db.get_stats()

        assert stats["total_commands"] == 0
        assert stats["total_reads"] == 0
        assert stats["total_writes"] == 0
        assert stats["total_webfetches"] == 0

    def test_get_stats_with_data(
        self,
        db: SecurityDatabase,
        sample_command_data: dict,
        sample_read_data: dict,
        sample_write_data: dict,
        sample_webfetch_data: dict,
    ):
        """Get stats with mixed data"""
        db.insert_command(sample_command_data)
        db.insert_read(sample_read_data)
        db.insert_write(sample_write_data)
        db.insert_webfetch(sample_webfetch_data)

        stats = db.get_stats()

        assert stats["high"] == 1  # command
        assert stats["reads_high"] == 1  # read
        assert stats["writes_critical"] == 1  # write
        assert stats["webfetches_critical"] == 1  # webfetch
        assert stats["total_reads"] == 1
        assert stats["total_writes"] == 1
        assert stats["total_webfetches"] == 1

    def test_update_scan_stats(self, db: SecurityDatabase):
        """Update scan statistics"""
        db.update_scan_stats(
            total_scanned=100, total_commands=50, last_scan="2024-12-19T12:00:00"
        )

        stats = db.get_stats()

        assert stats["total_scanned"] == 100
        assert stats["total_commands"] == 50

    def test_get_all_scanned_ids(
        self,
        db: SecurityDatabase,
        sample_command_data: dict,
        sample_read_data: dict,
    ):
        """Get all scanned file IDs across tables"""
        db.insert_command(sample_command_data)
        db.insert_read(sample_read_data)

        ids = db.get_all_scanned_ids()

        assert "cmd-001" in ids
        assert "read-001" in ids
        assert len(ids) == 2
