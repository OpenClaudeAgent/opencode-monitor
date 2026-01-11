"""
Tests for HybridIndexer (realtime file watching).
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.hybrid import HybridIndexer, IndexerRegistry


def create_session_json(session_id: str, title: str = "Test Session") -> dict:
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": session_id,
        "projectID": "proj_001",
        "directory": "/path/to/project",
        "title": title,
        "parentID": None,
        "version": "1.0.0",
        "summary": {"additions": 10, "deletions": 5, "files": 3},
        "time": {"created": now_ms, "updated": now_ms},
    }


def create_message_json(message_id: str, session_id: str) -> dict:
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": message_id,
        "sessionID": session_id,
        "parentID": None,
        "role": "assistant",
        "agent": "executor",
        "modelID": "claude-3-5-sonnet",
        "providerID": "anthropic",
        "mode": "agent",
        "cost": 0.001,
        "finish": "completed",
        "path": {"cwd": "/path/to/project"},
        "tokens": {
            "input": 1000,
            "output": 500,
            "reasoning": 0,
            "cache": {"read": 0, "write": 0},
        },
        "time": {"created": now_ms, "completed": now_ms + 5000},
    }


def write_json_file(
    storage_path: Path, file_type: str, project_id: str, file_id: str, data: dict
) -> Path:
    dir_path = storage_path / file_type / project_id
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{file_id}.json"
    file_path.write_text(json.dumps(data))
    return file_path


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test_analytics.duckdb"


@pytest.fixture
def temp_storage(tmp_path):
    storage_path = tmp_path / "opencode_storage"
    for subdir in ["session", "message", "part"]:
        (storage_path / subdir).mkdir(parents=True, exist_ok=True)
    return storage_path


@pytest.fixture
def indexer(temp_storage, temp_db_path):
    indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)
    yield indexer
    if indexer._running:
        indexer.stop()


class TestHybridIndexerInit:
    def test_init_sets_attributes(self, temp_storage, temp_db_path):
        indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)

        assert indexer._storage_path == temp_storage
        assert indexer._running is False
        assert indexer._t0 is None

    def test_init_with_injected_db(self, temp_storage, temp_db_path):
        mock_db = Mock(spec=AnalyticsDB)
        mock_db._db_path = temp_db_path

        indexer = HybridIndexer(storage_path=temp_storage, db=mock_db)

        assert indexer._db is mock_db
        assert indexer._running is False


class TestHybridIndexerLifecycle:
    def test_start_initializes_components(self, indexer, temp_storage):
        indexer.start()

        try:
            assert indexer._running is True
            assert indexer._t0 is not None
            assert indexer._watcher is not None
            assert indexer._tracker is not None
            assert indexer._parser is not None
            assert indexer._trace_builder is not None
        finally:
            indexer.stop()

    def test_start_is_idempotent(self, indexer, temp_storage):
        indexer.start()
        t0_first = indexer._t0

        indexer.start()

        try:
            assert indexer._t0 == t0_first
            assert indexer._running is True
        finally:
            indexer.stop()

    def test_stop_cleans_up(self, indexer, temp_storage):
        indexer.start()
        watcher = indexer._watcher

        indexer.stop()

        assert indexer._running is False
        assert not watcher.is_running

    def test_stop_without_start(self, indexer):
        indexer.stop()
        assert indexer._running is False

    def test_is_ready_after_start(self, temp_storage, temp_db_path):
        indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)
        indexer.start()

        try:
            assert indexer.is_ready() is True
        finally:
            indexer.stop()


class TestHybridIndexerStats:
    def test_get_stats(self, temp_storage, temp_db_path):
        indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)
        indexer.start()

        try:
            stats = indexer.get_stats()
            assert "running" in stats
            assert "files_processed" in stats
            assert stats["running"] is True
            assert stats["files_processed"] == 0
        finally:
            indexer.stop()


class TestHybridIndexerProcessFile:
    def test_process_session_file(self, temp_storage, temp_db_path):
        from opencode_monitor.analytics.indexer.tracker import FileTracker
        from opencode_monitor.analytics.indexer.parsers import FileParser
        from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder

        indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)
        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._tracker = FileTracker(indexer._db)
        indexer._parser = FileParser()
        indexer._trace_builder = TraceBuilder(indexer._db)

        file_path = write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_test",
            create_session_json("ses_test", title="Test Session"),
        )

        result = indexer._process_file("session", file_path)

        assert result is True
        conn = indexer._db.connect()
        session = conn.execute(
            "SELECT id, title FROM sessions WHERE id = 'ses_test'"
        ).fetchone()
        assert session is not None
        assert session[0] == "ses_test"
        assert session[1] == "Test Session"


class TestIndexerRegistry:
    def test_registry_lifecycle(self, temp_storage, temp_db_path):
        IndexerRegistry.clear()

        assert IndexerRegistry.get() is None

        indexer = IndexerRegistry.create(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )
        assert indexer is not None
        assert IndexerRegistry.get() is indexer

        IndexerRegistry.clear()
        assert IndexerRegistry.get() is None
