"""
Tests for SecurityScannerDuckDB - DuckDB-based file scanner for security auditor.

Tests cover:
- get_unscanned_files: Query parts table, exclude already scanned
- mark_scanned: Store part_id (not file_path) in security_scanned table
- get_scanned_count: Return count from security_scanned table
"""

from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from opencode_monitor.security.db.repository import SecurityScannerDuckDB


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def scanner(analytics_db):
    """Create SecurityScannerDuckDB with injected database."""
    # Ensure parts table exists (normally created by bulk loader)
    conn = analytics_db.connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS parts (
            id VARCHAR PRIMARY KEY,
            message_id VARCHAR,
            session_id VARCHAR,
            part_type VARCHAR,
            tool_name VARCHAR,
            tool_status VARCHAR,
            content TEXT,
            created_at TIMESTAMP,
            ended_at TIMESTAMP,
            duration_ms INTEGER
        )
        """
    )

    # Create security_scanned table (normally created by AnalyticsDB init)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS security_scanned (
            part_id VARCHAR PRIMARY KEY,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    scanner = SecurityScannerDuckDB(db=analytics_db)
    yield scanner

    # Cleanup
    scanner.close()


@pytest.fixture
def sample_parts(analytics_db):
    """Insert sample parts into database."""
    conn = analytics_db.connect()
    now = datetime.now()

    # Insert 5 parts
    parts_data = [
        ("prt_001", "msg_001", "ses_001", "tool", "bash", "completed", now),
        ("prt_002", "msg_001", "ses_001", "tool", "read", "completed", now),
        ("prt_003", "msg_002", "ses_001", "tool", "write", "completed", now),
        ("prt_004", "msg_002", "ses_002", "tool", "edit", "completed", now),
        ("prt_005", "msg_003", "ses_002", "tool", "glob", "completed", now),
    ]

    for part_id, msg_id, ses_id, ptype, tool, status, created in parts_data:
        conn.execute(
            """
            INSERT INTO parts (id, message_id, session_id, part_type, tool_name, tool_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [part_id, msg_id, ses_id, ptype, tool, status, created],
        )

    return parts_data


# =============================================================================
# Tests for get_unscanned_files
# =============================================================================


class TestGetUnscannedFiles:
    """Tests for get_unscanned_files method."""

    def test_returns_paths_from_parts_table(self, scanner, sample_parts, analytics_db):
        """get_unscanned_files returns file paths constructed from parts table."""
        # All parts are unscanned initially
        paths = scanner.get_unscanned_files(limit=10)

        # Should return 5 paths (all sample parts)
        assert len(paths) == 5

        # Each path should be a Path object
        for path in paths:
            assert isinstance(path, Path)

        # Paths should follow pattern: STORAGE_PATH / message_id / part_id.json
        path_stems = {p.stem for p in paths}
        expected_stems = {"prt_001", "prt_002", "prt_003", "prt_004", "prt_005"}
        assert path_stems == expected_stems

    def test_excludes_already_scanned_parts(self, scanner, sample_parts, analytics_db):
        """get_unscanned_files excludes parts already in security_scanned."""
        conn = analytics_db.connect()

        # Mark 2 parts as already scanned
        conn.execute(
            "INSERT INTO security_scanned (part_id) VALUES ('prt_001'), ('prt_003')"
        )

        paths = scanner.get_unscanned_files(limit=10)

        # Should return 3 paths (5 - 2 already scanned)
        assert len(paths) == 3

        path_stems = {p.stem for p in paths}
        assert "prt_001" not in path_stems
        assert "prt_003" not in path_stems
        assert "prt_002" in path_stems
        assert "prt_004" in path_stems
        assert "prt_005" in path_stems

    def test_respects_limit_parameter(self, scanner, sample_parts):
        """get_unscanned_files respects the limit parameter."""
        paths = scanner.get_unscanned_files(limit=2)

        assert len(paths) == 2

    def test_returns_empty_when_all_scanned(self, scanner, sample_parts, analytics_db):
        """get_unscanned_files returns empty list when all parts are scanned."""
        conn = analytics_db.connect()

        # Mark all parts as scanned
        for i in range(1, 6):
            conn.execute(f"INSERT INTO security_scanned (part_id) VALUES ('prt_00{i}')")

        paths = scanner.get_unscanned_files(limit=10)

        assert paths == []


# =============================================================================
# Tests for mark_scanned
# =============================================================================


class TestMarkScanned:
    """Tests for mark_scanned method."""

    def test_stores_part_id_from_path(self, scanner, analytics_db):
        """mark_scanned extracts and stores part_id from file path."""
        # Create a file path with part_id
        file_path = Path(
            "/home/user/.local/share/opencode/storage/part/msg_001/prt_xyz123.json"
        )

        scanner.mark_scanned(file_path)

        # Verify part_id was stored
        conn = analytics_db.connect()
        result = conn.execute(
            "SELECT part_id FROM security_scanned WHERE part_id = 'prt_xyz123'"
        ).fetchone()

        assert result is not None
        assert result[0] == "prt_xyz123"

    def test_stores_scanned_at_timestamp(self, scanner, analytics_db):
        """mark_scanned stores timestamp when file was scanned."""
        file_path = Path("/storage/msg_001/prt_timestamped.json")

        scanner.mark_scanned(file_path)

        conn = analytics_db.connect()
        result = conn.execute(
            "SELECT scanned_at FROM security_scanned WHERE part_id = 'prt_timestamped'"
        ).fetchone()

        assert result is not None
        assert result[0] is not None  # Has timestamp


# =============================================================================
# Tests for get_scanned_count
# =============================================================================


class TestGetScannedCount:
    """Tests for get_scanned_count method."""

    def test_returns_correct_count(self, scanner, analytics_db):
        """get_scanned_count returns number of records in security_scanned."""
        conn = analytics_db.connect()

        # Insert 7 records
        for i in range(7):
            conn.execute(
                f"INSERT INTO security_scanned (part_id) VALUES ('prt_{i:03d}')"
            )

        count = scanner.get_scanned_count()

        assert count == 7

    def test_returns_zero_when_empty(self, scanner):
        """get_scanned_count returns 0 when no files scanned."""
        count = scanner.get_scanned_count()

        assert count == 0

    def test_count_after_batch_mark(self, scanner, analytics_db):
        """get_scanned_count reflects batch marking."""
        paths = [Path(f"/storage/msg_001/prt_batch_{i}.json") for i in range(5)]

        marked = scanner.mark_scanned_batch(paths)

        assert marked == 5
        assert scanner.get_scanned_count() == 5
