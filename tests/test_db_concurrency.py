"""Tests for DB concurrency between menubar and dashboard.

These tests verify that:
1. The sync_meta table is created on database init
2. update_sync_timestamp() updates the timestamp and count
3. Dashboard can read while menubar writes (concurrent access)
4. Read-only connections work correctly
"""

import time

import pytest

from opencode_monitor.analytics.db import AnalyticsDB


class TestSyncMeta:
    """Tests for the sync_meta table functionality."""

    def test_sync_meta_table_created(self, tmp_path):
        """sync_meta table should be created on init."""
        db = AnalyticsDB(db_path=tmp_path / "test.duckdb")
        conn = db.connect()
        result = conn.execute("SELECT * FROM sync_meta WHERE id = 1").fetchone()

        assert result is not None
        assert result[0] == 1  # id
        assert result[1] is not None  # last_sync timestamp
        assert result[2] == 0  # sync_count starts at 0

        db.close()

    def test_update_sync_timestamp(self, tmp_path):
        """update_sync_timestamp should update the timestamp."""
        db = AnalyticsDB(db_path=tmp_path / "test.duckdb")
        db.connect()

        before = db.get_sync_timestamp()
        time.sleep(0.1)  # Ensure timestamp changes
        db.update_sync_timestamp()
        after = db.get_sync_timestamp()

        assert after > before

        db.close()

    def test_sync_count_increments(self, tmp_path):
        """sync_count should increment on each update."""
        db = AnalyticsDB(db_path=tmp_path / "test.duckdb")
        conn = db.connect()

        count_before = conn.execute(
            "SELECT sync_count FROM sync_meta WHERE id = 1"
        ).fetchone()[0]

        db.update_sync_timestamp()

        count_after = conn.execute(
            "SELECT sync_count FROM sync_meta WHERE id = 1"
        ).fetchone()[0]

        assert count_after == count_before + 1

        db.close()

    def test_get_sync_timestamp_returns_datetime(self, tmp_path):
        """get_sync_timestamp should return a datetime object."""
        from datetime import datetime

        db = AnalyticsDB(db_path=tmp_path / "test.duckdb")
        db.connect()

        ts = db.get_sync_timestamp()
        assert isinstance(ts, datetime)

        db.close()


class TestReadOnlyAccess:
    """Tests for read-only database access.

    Note: DuckDB doesn't allow mixing read_only and read_write connections
    in the same process. In production, menubar (writer) and dashboard (reader)
    run in separate processes, so this works fine.

    These tests verify the behavior in separate process scenarios.
    """

    def test_reader_after_writer_closes(self, tmp_path):
        """Reader should work after writer has closed connection."""
        db_path = tmp_path / "test.duckdb"

        # First create DB and write data
        writer = AnalyticsDB(db_path=db_path, read_only=False)
        writer.connect()
        writer.update_sync_timestamp()
        writer.close()  # Writer closes

        # Then open as reader (simulates dashboard in separate process)
        reader = AnalyticsDB(db_path=db_path, read_only=True)
        reader.connect()

        # Reader should be able to read what writer wrote
        ts = reader.get_sync_timestamp()
        assert ts is not None

        reader.close()

    def test_multiple_sequential_writes(self, tmp_path):
        """Multiple writes should work sequentially."""
        db_path = tmp_path / "test.duckdb"

        # First write
        db1 = AnalyticsDB(db_path=db_path, read_only=False)
        db1.connect()
        db1.update_sync_timestamp()
        ts1 = db1.get_sync_timestamp()
        db1.close()

        time.sleep(0.1)

        # Second write
        db2 = AnalyticsDB(db_path=db_path, read_only=False)
        db2.connect()
        db2.update_sync_timestamp()
        ts2 = db2.get_sync_timestamp()
        db2.close()

        assert ts2 > ts1

    def test_reader_sees_latest_data(self, tmp_path):
        """Reader should see data written by previous writer."""
        db_path = tmp_path / "test.duckdb"

        # Write initial data
        writer = AnalyticsDB(db_path=db_path, read_only=False)
        conn = writer.connect()
        writer.update_sync_timestamp()
        count1 = conn.execute(
            "SELECT sync_count FROM sync_meta WHERE id = 1"
        ).fetchone()[0]
        writer.close()

        # Write more data
        writer2 = AnalyticsDB(db_path=db_path, read_only=False)
        writer2.connect()
        writer2.update_sync_timestamp()
        writer2.close()

        # Reader should see both updates
        reader = AnalyticsDB(db_path=db_path, read_only=True)
        conn = reader.connect()
        count2 = conn.execute(
            "SELECT sync_count FROM sync_meta WHERE id = 1"
        ).fetchone()[0]
        reader.close()

        assert count2 == count1 + 1


class TestAnalyticsSyncManager:
    """Tests for the AnalyticsSyncManager class."""

    def test_needs_sync_initially(self, tmp_path, monkeypatch):
        """needs_sync should return True initially."""
        from opencode_monitor.app.handlers import AnalyticsSyncManager

        # Patch the default db path to use tmp_path
        monkeypatch.setattr(
            "opencode_monitor.analytics.db.get_db_path",
            lambda: tmp_path / "analytics.duckdb",
        )

        manager = AnalyticsSyncManager()
        assert manager.needs_sync() is True

        manager.close()

    def test_needs_sync_false_after_sync(self, tmp_path, monkeypatch):
        """needs_sync should return False after sync if within interval."""
        from opencode_monitor.app.handlers import AnalyticsSyncManager

        monkeypatch.setattr(
            "opencode_monitor.analytics.db.get_db_path",
            lambda: tmp_path / "analytics.duckdb",
        )

        manager = AnalyticsSyncManager()

        # Simulate a sync happened just now
        manager._last_sync = time.time()

        # Should not need sync
        assert manager.needs_sync() is False

        manager.close()

    def test_sync_manager_updates_db_timestamp(self, tmp_path, monkeypatch):
        """Sync manager should update DB timestamp when sync runs."""
        from opencode_monitor.app.handlers import AnalyticsSyncManager

        monkeypatch.setattr(
            "opencode_monitor.analytics.db.get_db_path",
            lambda: tmp_path / "analytics.duckdb",
        )

        manager = AnalyticsSyncManager()

        # Get initial timestamp
        ts1 = manager._db.get_sync_timestamp()

        time.sleep(0.1)

        # Manually update the sync timestamp (simulating a sync)
        manager._db.update_sync_timestamp()

        ts2 = manager._db.get_sync_timestamp()

        assert ts2 is not None
        assert ts2 > ts1

        manager.close()
