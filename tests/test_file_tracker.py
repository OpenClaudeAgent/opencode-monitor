"""
Tests for FileTracker module - US-1: Status column support.

TDD tests for the file_index table status column extension.
Covers: indexed, error, pending status values and retrieval.
"""

import pytest
from pathlib import Path

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.tracker import FileTracker, FileInfo


@pytest.fixture
def temp_db(tmp_path: Path) -> AnalyticsDB:
    """Create isolated AnalyticsDB for testing."""
    db_path = tmp_path / "test_tracker.duckdb"
    db = AnalyticsDB(db_path)
    db.connect()
    yield db
    db.close()


@pytest.fixture
def tracker(temp_db: AnalyticsDB) -> FileTracker:
    """Create FileTracker with test database."""
    return FileTracker(temp_db)


@pytest.fixture
def test_file(tmp_path: Path) -> Path:
    """Create a test file for tracking."""
    file_path = tmp_path / "test_session.json"
    file_path.write_text('{"id": "test-001"}')
    return file_path


class TestFileTrackerStatus:
    """Tests for status column in file_index table."""

    def test_mark_indexed_sets_status_indexed(
        self, tracker: FileTracker, test_file: Path
    ):
        """mark_indexed should set status='indexed' by default."""
        tracker.mark_indexed(test_file, "session", record_id="sess-001")

        info = tracker.get_file_info(test_file)
        assert info is not None
        assert info.status == "indexed"

    def test_mark_error_sets_status_error(self, tracker: FileTracker, test_file: Path):
        """mark_error should set status='error'."""
        tracker.mark_error(test_file, "session", "Parse error: invalid JSON")

        info = tracker.get_file_info(test_file)
        assert info is not None
        assert info.status == "error"
        assert info.error_message == "Parse error: invalid JSON"

    def test_mark_pending_sets_status_pending(
        self, tracker: FileTracker, test_file: Path, tmp_path: Path
    ):
        """mark_pending should set status='pending' for multiple paths."""
        file2 = tmp_path / "test_session2.json"
        file2.write_text('{"id": "test-002"}')

        paths = [test_file, file2]
        tracker.mark_pending(paths, "session")

        for path in paths:
            info = tracker.get_file_info(path)
            assert info is not None
            assert info.status == "pending"

    def test_get_file_info_returns_status(self, tracker: FileTracker, test_file: Path):
        """get_file_info should return FileInfo with status field."""
        tracker.mark_indexed(test_file, "message", record_id="msg-001")

        info = tracker.get_file_info(test_file)

        assert info is not None
        assert isinstance(info, FileInfo)
        assert hasattr(info, "status")
        assert info.status == "indexed"
        assert info.file_type == "message"
        assert info.record_id == "msg-001"

    def test_mark_indexed_batch_sets_status_indexed(
        self, tracker: FileTracker, tmp_path: Path
    ):
        """mark_indexed_batch should set status='indexed' for all files."""
        files = []
        for i in range(3):
            f = tmp_path / f"batch_file_{i}.json"
            f.write_text(f'{{"id": "batch-{i}"}}')
            files.append(f)

        items = [(f, "part", f"part-{i}") for i, f in enumerate(files)]
        count = tracker.mark_indexed_batch(items)

        assert count == 3
        for f in files:
            info = tracker.get_file_info(f)
            assert info is not None
            assert info.status == "indexed"

    def test_status_transition_error_to_indexed(
        self, tracker: FileTracker, test_file: Path
    ):
        """Status should transition from error to indexed on retry success."""
        # First: mark as error
        tracker.mark_error(test_file, "session", "Temporary error")
        info = tracker.get_file_info(test_file)
        assert info.status == "error"

        # Then: successful reindex
        tracker.mark_indexed(test_file, "session", record_id="sess-001")
        info = tracker.get_file_info(test_file)
        assert info.status == "indexed"
        assert info.error_message is None

    def test_status_transition_pending_to_indexed(
        self, tracker: FileTracker, test_file: Path
    ):
        """Status should transition from pending to indexed after processing."""
        # First: mark as pending
        tracker.mark_pending([test_file], "session")
        info = tracker.get_file_info(test_file)
        assert info.status == "pending"

        # Then: process successfully
        tracker.mark_indexed(test_file, "session", record_id="sess-001")
        info = tracker.get_file_info(test_file)
        assert info.status == "indexed"


class TestFileTrackerStatusIndex:
    """Tests for status column index in file_index table."""

    def test_status_index_exists(self, tracker: FileTracker, temp_db: AnalyticsDB):
        """idx_file_index_status index should exist."""
        conn = temp_db.connect()
        # Query DuckDB system tables for index info
        result = conn.execute("""
            SELECT index_name FROM duckdb_indexes()
            WHERE index_name = 'idx_file_index_status'
        """).fetchone()

        assert result is not None, "Index idx_file_index_status should exist"


class TestFileTrackerStatusBackwardCompatibility:
    """Tests ensuring backward compatibility with existing code."""

    def test_mark_indexed_without_status_still_works(
        self, tracker: FileTracker, test_file: Path
    ):
        """Existing code calling mark_indexed should still work."""
        # Old API call pattern (no explicit status)
        tracker.mark_indexed(test_file, "session")

        info = tracker.get_file_info(test_file)
        assert info is not None
        assert info.file_path == str(test_file)
        assert info.file_type == "session"

    def test_file_info_has_all_original_fields(
        self, tracker: FileTracker, test_file: Path
    ):
        """FileInfo should still have all original fields."""
        tracker.mark_indexed(test_file, "session", record_id="sess-001")
        info = tracker.get_file_info(test_file)

        # Original fields
        assert hasattr(info, "file_path")
        assert hasattr(info, "file_type")
        assert hasattr(info, "mtime")
        assert hasattr(info, "size")
        assert hasattr(info, "record_id")
        assert hasattr(info, "indexed_at")
        assert hasattr(info, "error_message")
        # New field
        assert hasattr(info, "status")
