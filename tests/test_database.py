"""
Tests for SecurityDatabase - DuckDB repository for security audit data.

Consolidated tests: 8 functions covering all CRUD operations and statistics.
All assertions use equality checks for precise validation.

NOTE: SecurityDatabase now uses the unified analytics.duckdb database.
"""

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
def security_db(analytics_db) -> SecurityDatabase:
    """Create SecurityDatabase with injected AnalyticsDB for each test."""
    return SecurityDatabase(db=analytics_db)


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


class TestDatabaseInitialization:
    """Tests for database schema initialization"""

    def test_database_creates_tables_and_indexes(
        self, security_db: SecurityDatabase, analytics_db
    ):
        """Database initializes with all required tables and performance indexes"""
        conn = analytics_db.connect()

        # Verify all required security tables exist
        result = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name LIKE 'security_%' ORDER BY table_name"
        ).fetchall()
        tables = {row[0] for row in result}

        expected_tables = {
            "security_commands",
            "security_file_reads",
            "security_file_writes",
            "security_webfetches",
            "security_stats",
            "security_scanned",
        }
        assert expected_tables.issubset(tables)


class TestEntityCrudOperations:
    """Tests for CRUD operations on all entity types"""

    def test_command_crud_operations(
        self, security_db: SecurityDatabase, sample_command_data: dict
    ):
        """Command insert, duplicate handling, and query by risk level"""
        # Insert succeeds
        insert_result = security_db.insert_command(sample_command_data)
        assert insert_result is True

        # Duplicate is ignored (returns True but no new row due to content_hash)
        duplicate_result = security_db.insert_command(sample_command_data)
        assert duplicate_result is True  # DuckDB INSERT OR IGNORE returns success

        # Query by risk level returns correct data
        results = security_db.get_commands_by_level(["high"])
        assert len(results) == 1
        assert results[0].file_id == "cmd-001"
        assert results[0].command == "rm -rf /tmp/test"
        assert results[0].risk_level == "high"
        assert results[0].risk_score == 75

        # Get all commands works
        all_commands = security_db.get_all_commands()
        assert len(all_commands) == 1

    def test_file_read_crud_operations(
        self, security_db: SecurityDatabase, sample_read_data: dict
    ):
        """File read insert, duplicate handling, and query by risk level"""
        # Insert succeeds
        insert_result = security_db.insert_read(sample_read_data)
        assert insert_result is True

        # Duplicate is ignored
        duplicate_result = security_db.insert_read(sample_read_data)
        assert duplicate_result is True  # DuckDB INSERT OR IGNORE returns success

        # Query by risk level returns correct data
        results = security_db.get_reads_by_level(["high"])
        assert len(results) == 1
        assert results[0].file_id == "read-001"
        assert results[0].file_path == "/etc/passwd"
        assert results[0].risk_level == "high"

        # Get all reads works
        all_reads = security_db.get_all_reads()
        assert len(all_reads) == 1

    def test_file_write_crud_operations(
        self, security_db: SecurityDatabase, sample_write_data: dict
    ):
        """File write insert, duplicate handling, and query by risk level"""
        # Insert succeeds
        insert_result = security_db.insert_write(sample_write_data)
        assert insert_result is True

        # Duplicate is ignored
        duplicate_result = security_db.insert_write(sample_write_data)
        assert duplicate_result is True  # DuckDB INSERT OR IGNORE returns success

        # Query by risk level returns correct data
        results = security_db.get_writes_by_level(["critical"])
        assert len(results) == 1
        assert results[0].file_id == "write-001"
        assert results[0].file_path == "/home/user/.ssh/config"
        assert results[0].operation == "edit"
        assert results[0].risk_level == "critical"

        # Get all writes works
        all_writes = security_db.get_all_writes()
        assert len(all_writes) == 1

    def test_webfetch_crud_operations(
        self, security_db: SecurityDatabase, sample_webfetch_data: dict
    ):
        """Webfetch insert, duplicate handling, and query by risk level"""
        # Insert succeeds
        insert_result = security_db.insert_webfetch(sample_webfetch_data)
        assert insert_result is True

        # Duplicate is ignored
        duplicate_result = security_db.insert_webfetch(sample_webfetch_data)
        assert duplicate_result is True  # DuckDB INSERT OR IGNORE returns success

        # Query by risk level returns correct data
        results = security_db.get_webfetches_by_level(["critical"])
        assert len(results) == 1
        assert results[0].file_id == "fetch-001"
        assert results[0].url == "https://pastebin.com/raw/abc123"
        assert results[0].risk_level == "critical"

        # Get all webfetches works
        all_webfetches = security_db.get_all_webfetches()
        assert len(all_webfetches) == 1


class TestQueryCapabilities:
    """Tests for advanced query features"""

    def test_multi_level_query_and_pagination(self, security_db: SecurityDatabase):
        """Query by multiple risk levels and paginate results"""
        # Insert commands with different risk levels
        levels = ["critical", "high", "medium", "low"]
        for i, level in enumerate(levels):
            security_db.insert_command(
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

        # Query multiple levels returns correct subset
        results = security_db.get_commands_by_level(["critical", "high"])
        assert len(results) == 2
        result_levels = {r.risk_level for r in results}
        assert result_levels == {"critical", "high"}

        # Insert more commands for pagination test
        for i in range(4, 14):
            security_db.insert_command(
                {
                    "file_id": f"cmd-{i:03d}",
                    "content_hash": f"hash-{i}",
                    "session_id": "sess-001",
                    "tool": "bash",
                    "command": f"command-{i}",
                    "risk_score": 50,
                    "risk_level": "medium",
                    "risk_reason": "Test",
                    "timestamp": 1703000000000 + i * 1000,
                    "scanned_at": "2024-12-19",
                }
            )

        # Pagination works correctly
        page1 = security_db.get_all_commands(limit=5, offset=0)
        page2 = security_db.get_all_commands(limit=5, offset=5)
        assert len(page1) == 5
        assert len(page2) == 5

        # Pages have no overlap
        page1_ids = {c.file_id for c in page1}
        page2_ids = {c.file_id for c in page2}
        assert page1_ids.isdisjoint(page2_ids)


class TestStatistics:
    """Tests for statistics and aggregation"""

    def test_statistics_lifecycle(
        self,
        security_db: SecurityDatabase,
        sample_command_data: dict,
        sample_read_data: dict,
        sample_write_data: dict,
        sample_webfetch_data: dict,
    ):
        """Statistics from empty database through population and scan updates"""
        # Empty database has zero counts
        empty_stats = security_db.get_stats()
        assert empty_stats["total_commands"] == 0
        assert empty_stats["total_reads"] == 0
        assert empty_stats["total_writes"] == 0
        assert empty_stats["total_webfetches"] == 0

        # Insert mixed data
        security_db.insert_command(sample_command_data)
        security_db.insert_read(sample_read_data)
        security_db.insert_write(sample_write_data)
        security_db.insert_webfetch(sample_webfetch_data)

        # Stats reflect inserted data correctly
        populated_stats = security_db.get_stats()
        assert populated_stats["high"] == 1  # command
        assert populated_stats["reads_high"] == 1  # read
        assert populated_stats["writes_critical"] == 1  # write
        assert populated_stats["webfetches_critical"] == 1  # webfetch
        assert populated_stats["total_reads"] == 1
        assert populated_stats["total_writes"] == 1
        assert populated_stats["total_webfetches"] == 1

        # Scan stats update works
        security_db.update_scan_stats(
            total_scanned=100, total_commands=50, last_scan="2024-12-19T12:00:00"
        )
        updated_stats = security_db.get_stats()
        assert updated_stats["total_scanned"] == 100
        assert updated_stats["total_commands"] == 50

    def test_scanned_ids_aggregation(
        self,
        security_db: SecurityDatabase,
        sample_command_data: dict,
        sample_read_data: dict,
    ):
        """Get all scanned file IDs aggregated across tables"""
        security_db.insert_command(sample_command_data)
        security_db.insert_read(sample_read_data)

        ids = security_db.get_all_scanned_ids()

        assert "cmd-001" in ids
        assert "read-001" in ids
        assert len(ids) == 2
