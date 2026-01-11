"""Tests for backfill.py script."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from backfill import check_db_lock, run_backfill


class TestCheckDbLock:
    """Tests for check_db_lock function."""

    def test_returns_true_when_db_available(self, tmp_path):
        """Test check_db_lock returns True for unlocked DB."""
        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute("SELECT 1")
        conn.close()

        result = check_db_lock(db_path)

        assert result is True, "Should return True for available DB"

    def test_returns_true_for_new_db(self, tmp_path):
        """Test check_db_lock returns True for new DB path."""
        db_path = tmp_path / "new.duckdb"

        result = check_db_lock(db_path)

        assert result is True, "Should return True for new DB"


class TestRunBackfill:
    """Tests for run_backfill function."""

    def test_returns_error_when_storage_missing(self, tmp_path, monkeypatch):
        """Test run_backfill returns 1 when storage path doesn't exist."""
        fake_storage = tmp_path / "nonexistent"
        monkeypatch.setattr("backfill.OPENCODE_STORAGE", fake_storage)
        monkeypatch.setattr("backfill.check_db_lock", lambda x: True)

        result = run_backfill()

        assert result == 1, "Should return 1 for missing storage"

    def test_returns_error_when_db_locked(self, tmp_path, monkeypatch):
        """Test run_backfill returns 1 when DB is locked."""
        storage = tmp_path / "storage"
        storage.mkdir()
        monkeypatch.setattr("backfill.OPENCODE_STORAGE", storage)
        monkeypatch.setattr("backfill.check_db_lock", lambda x: False)

        result = run_backfill()

        assert result == 1, "Should return 1 for locked DB"
