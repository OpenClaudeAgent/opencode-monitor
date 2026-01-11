"""Tests for DB concurrency between menubar and dashboard.

These tests verify that:
1. The sync_meta table is created on database init
2. update_sync_timestamp() updates the timestamp and count
3. Dashboard can read while menubar writes (concurrent access)
4. Read-only connections work correctly
"""

import time
from datetime import datetime

import pytest

from opencode_monitor.analytics.db import AnalyticsDB


class TestSyncMeta:
    """Tests for the sync_meta table functionality."""

    def test_sync_meta_table_initial_state(self, tmp_path):
        """sync_meta table should have correct initial structure and values."""
        db = AnalyticsDB(db_path=tmp_path / "test.duckdb")
        conn = db.connect()

        # Query full row
        result = conn.execute("SELECT * FROM sync_meta WHERE id = 1").fetchone()

        # Verify row exists and structure: (id, last_sync, sync_count)
        assert result[0] == 1  # id
        assert result[2] == 0  # sync_count starts at 0

        # Verify timestamp is a valid datetime with sensible values
        ts = db.get_sync_timestamp()
        assert ts.year >= 2024
        assert 1 <= ts.month <= 12
        assert 1 <= ts.day <= 31
        assert 0 <= ts.hour <= 23
        assert 0 <= ts.minute <= 59

        db.close()

    @pytest.mark.parametrize("update_count", [1, 2, 3])
    def test_sync_count_increments(self, tmp_path, update_count):
        """sync_count should increment correctly after N updates."""
        db = AnalyticsDB(db_path=tmp_path / "test.duckdb")
        conn = db.connect()

        # Get initial state
        initial = conn.execute(
            "SELECT sync_count FROM sync_meta WHERE id = 1"
        ).fetchone()
        assert initial[0] == 0  # Starts at 0

        # Perform N updates
        for _ in range(update_count):
            db.update_sync_timestamp()

        # Verify sync_count equals number of updates
        result = conn.execute(
            "SELECT sync_count FROM sync_meta WHERE id = 1"
        ).fetchone()
        assert result[0] == update_count

        # Verify final timestamp is valid
        final_ts = db.get_sync_timestamp()
        assert final_ts.year >= 2024

        db.close()


class TestReadOnlyAccess:
    """Tests for read-only database access patterns."""

    @pytest.mark.parametrize(
        "scenario,write_count,expected_final_count",
        [
            ("single_write_then_read", 1, 1),
            ("multiple_writes_then_read", 2, 2),
            ("three_writes_then_read", 3, 3),
        ],
    )
    def test_reader_sees_correct_data_after_writes(
        self, tmp_path, scenario, write_count, expected_final_count
    ):
        """Reader should see exact sync_count after N sequential writes."""
        db_path = tmp_path / "test.duckdb"
        timestamps = []

        for i in range(write_count):
            writer = AnalyticsDB(db_path=db_path, read_only=False)
            conn = writer.connect()
            assert writer._read_only is False
            writer.update_sync_timestamp()
            writer.close()
            assert writer._conn is None

        reader = AnalyticsDB(db_path=db_path, read_only=True)
        conn = reader.connect()
        assert reader._read_only is True

        result = conn.execute(
            "SELECT sync_count FROM sync_meta WHERE id = 1"
        ).fetchone()
        assert result[0] == expected_final_count

        final_ts = reader.get_sync_timestamp()
        assert final_ts.year >= 2024

        reader.close()


class TestContextManager:
    """Tests for the context manager support."""

    @pytest.mark.parametrize(
        "scenario,read_only,raise_exception",
        [
            ("normal_write_mode", False, False),
            ("exception_during_write", False, True),
            ("read_only_mode", True, False),
        ],
    )
    def test_context_manager_lifecycle(
        self, tmp_path, scenario, read_only, raise_exception
    ):
        """Context manager should correctly manage connection lifecycle."""
        db_path = tmp_path / "test.duckdb"

        # Create DB first for read_only scenarios
        if read_only:
            with AnalyticsDB(db_path=db_path, read_only=False) as writer:
                writer.update_sync_timestamp()
                # Verify write inside context
                ts_before = writer.get_sync_timestamp()
                assert ts_before.year >= 2024

        db = AnalyticsDB(db_path=db_path, read_only=read_only)

        # Verify initial state before context
        assert db._conn is None
        assert db._read_only == read_only

        try:
            with db:
                # Verify connection state inside context
                ts = db.get_sync_timestamp()
                assert ts.year >= 2024
                assert ts.month >= 1
                if raise_exception:
                    raise ValueError("Test exception")
        except ValueError:
            pass

        # Connection should always be closed after context
        assert db._conn is None
        # Mode should remain unchanged
        assert db._read_only == read_only


class TestAnalyticsSyncManager:
    """Tests for the AnalyticsSyncManager class."""

    @pytest.mark.parametrize(
        "scenario,simulate_recent_sync,expected_needs_sync",
        [
            ("initial_state", False, True),
            ("after_recent_sync", True, False),
        ],
    )
    def test_needs_sync_state(
        self, tmp_path, monkeypatch, scenario, simulate_recent_sync, expected_needs_sync
    ):
        """needs_sync should return correct value based on sync state."""
        from opencode_monitor.app.handlers import AnalyticsSyncManager

        monkeypatch.setattr(
            "opencode_monitor.analytics.db.get_db_path",
            lambda: tmp_path / "analytics.duckdb",
        )

        manager = AnalyticsSyncManager()

        # Verify initial _last_sync state
        if simulate_recent_sync:
            manager._last_sync = time.time()
            assert manager._last_sync > 0
        else:
            assert manager._last_sync == 0

        # Verify needs_sync returns expected value
        result = manager.needs_sync()
        assert result == expected_needs_sync
        assert type(result) is bool

        manager.close()

    def test_sync_manager_updates_timestamp(self, tmp_path, monkeypatch):
        """Sync manager should update timestamp after sync_incremental."""
        from opencode_monitor.app.handlers import AnalyticsSyncManager

        db_path = tmp_path / "analytics.duckdb"

        monkeypatch.setattr(
            "opencode_monitor.analytics.db.get_db_path",
            lambda: db_path,
        )

        monkeypatch.setattr(
            "opencode_monitor.app.handlers.load_opencode_data",
            lambda **kwargs: {"sessions": 0, "messages": 0},
        )

        # Create DB and get initial timestamp
        with AnalyticsDB(db_path=db_path, read_only=False) as db:
            ts1 = db.get_sync_timestamp()
            initial_year = ts1.year
            initial_count = db._conn.execute(
                "SELECT sync_count FROM sync_meta WHERE id = 1"
            ).fetchone()[0]

        assert initial_year >= 2024
        assert initial_count == 0

        # Manager should not hold persistent _db reference
        manager = AnalyticsSyncManager()
        assert hasattr(manager, "_db") is False
        assert manager._last_sync == 0

        manager.sync_incremental(max_days=1)

        # Verify _last_sync was updated
        assert manager._last_sync > 0

        # Verify timestamp was updated in DB
        with AnalyticsDB(db_path=db_path, read_only=True) as db2:
            ts2 = db2.get_sync_timestamp()
            assert ts2.year >= 2024
            # Compare as ISO strings for strict ordering
            assert ts2.isoformat() > ts1.isoformat()

            # Verify sync_count incremented
            final_count = db2._conn.execute(
                "SELECT sync_count FROM sync_meta WHERE id = 1"
            ).fetchone()[0]
            assert final_count == initial_count + 1

        manager.close()
