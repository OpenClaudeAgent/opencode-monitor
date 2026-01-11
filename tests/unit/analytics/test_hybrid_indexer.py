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
        assert not indexer._running
        assert indexer._t0 is None

    def test_init_with_injected_db(self, temp_storage, temp_db_path):
        mock_db = Mock(spec=AnalyticsDB)
        mock_db._db_path = temp_db_path

        indexer = HybridIndexer(storage_path=temp_storage, db=mock_db)

        assert indexer._db is mock_db
        assert not indexer._running


class TestHybridIndexerLifecycle:
    def test_start_initializes_components(self, indexer, temp_storage):
        indexer.start()

        try:
            assert indexer._running
            assert isinstance(indexer._t0, (int, float))
            assert indexer._t0 > 0
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
            assert indexer._running
        finally:
            indexer.stop()

    def test_stop_cleans_up(self, indexer, temp_storage):
        indexer.start()
        watcher = indexer._watcher

        indexer.stop()

        assert not indexer._running
        assert not watcher.is_running

    def test_stop_without_start(self, indexer):
        indexer.stop()
        assert not indexer._running

    def test_is_ready_after_start(self, temp_storage, temp_db_path):
        indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)
        indexer.start()

        try:
            assert indexer.is_ready()
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
            assert stats["running"]
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

        assert result
        conn = indexer._db.connect()
        session = conn.execute(
            "SELECT id, title FROM sessions WHERE id = 'ses_test'"
        ).fetchone()
        assert session[0] == "ses_test"
        assert session[1] == "Test Session"

    def test_process_part_creates_file_operation(self, temp_storage, temp_db_path):
        """Test that processing a read/write/edit part creates a file_operation entry."""
        from opencode_monitor.analytics.indexer.tracker import FileTracker
        from opencode_monitor.analytics.indexer.parsers import FileParser
        from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder

        indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)
        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._tracker = FileTracker(indexer._db)
        indexer._parser = FileParser()
        indexer._trace_builder = TraceBuilder(indexer._db)

        now_ms = int(datetime.now().timestamp() * 1000)
        part_data = {
            "id": "prt_read_test",
            "sessionID": "ses_001",
            "messageID": "msg_001",
            "type": "tool",
            "tool": "read",
            "text": None,
            "callID": "call_read",
            "state": {
                "status": "completed",
                "input": {"filePath": "/path/to/source.py"},
                "time": {"start": now_ms, "end": now_ms + 100},
            },
        }

        file_path = write_json_file(
            temp_storage, "part", "msg_001", "prt_read_test", part_data
        )

        result = indexer._process_file("part", file_path)

        assert result

        conn = indexer._db.connect()
        file_op = conn.execute(
            "SELECT id, operation, file_path FROM file_operations WHERE id = 'prt_read_test'"
        ).fetchone()

        assert file_op[0] == "prt_read_test"
        assert file_op[1] == "read"
        assert file_op[2] == "/path/to/source.py"


class TestHandlerErrorCases:
    def test_session_handler_returns_none_on_invalid_data(
        self, temp_storage, temp_db_path
    ):
        from opencode_monitor.analytics.indexer.handlers import SessionHandler
        from opencode_monitor.analytics.indexer.parsers import FileParser
        from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder

        db = AnalyticsDB(temp_db_path)
        conn = db.connect()
        handler = SessionHandler()
        parser = FileParser()
        trace_builder = TraceBuilder(db)

        result = handler.process(
            Path("/fake/path"),
            {"invalid": "data"},
            conn,
            parser,
            trace_builder,
        )

        assert result is None

    def test_message_handler_returns_none_on_invalid_data(
        self, temp_storage, temp_db_path
    ):
        from opencode_monitor.analytics.indexer.handlers import MessageHandler
        from opencode_monitor.analytics.indexer.parsers import FileParser
        from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder

        db = AnalyticsDB(temp_db_path)
        conn = db.connect()
        handler = MessageHandler()
        parser = FileParser()
        trace_builder = TraceBuilder(db)

        result = handler.process(
            Path("/fake/path"),
            {"invalid": "data"},
            conn,
            parser,
            trace_builder,
        )

        assert result is None

    def test_part_handler_returns_none_on_invalid_data(
        self, temp_storage, temp_db_path
    ):
        from opencode_monitor.analytics.indexer.handlers import PartHandler
        from opencode_monitor.analytics.indexer.parsers import FileParser
        from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder

        db = AnalyticsDB(temp_db_path)
        conn = db.connect()
        handler = PartHandler()
        parser = FileParser()
        trace_builder = TraceBuilder(db)

        result = handler.process(
            Path("/fake/path"),
            {"invalid": "data"},
            conn,
            parser,
            trace_builder,
        )

        assert result is None


class TestMessageHandlerProcess:
    """Tests for MessageHandler.process() method."""

    def test_process_message_file(self, temp_storage, temp_db_path):
        """Test that processing a message file creates a message entry."""
        from opencode_monitor.analytics.indexer.tracker import FileTracker
        from opencode_monitor.analytics.indexer.parsers import FileParser
        from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder

        indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)
        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._tracker = FileTracker(indexer._db)
        indexer._parser = FileParser()
        indexer._trace_builder = TraceBuilder(indexer._db)

        session_path = write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_msg_test",
            create_session_json("ses_msg_test"),
        )
        indexer._process_file("session", session_path)

        message_data = create_message_json("msg_test_001", "ses_msg_test")
        file_path = write_json_file(
            temp_storage, "message", "ses_msg_test", "msg_test_001", message_data
        )

        result = indexer._process_file("message", file_path)

        assert result
        conn = indexer._db.connect()
        message = conn.execute(
            "SELECT id, session_id, role, agent FROM messages WHERE id = 'msg_test_001'"
        ).fetchone()
        assert message[0] == "msg_test_001"
        assert message[1] == "ses_msg_test"
        assert message[2] == "assistant"
        assert message[3] == "executor"

    def test_process_message_with_tokens(self, temp_storage, temp_db_path):
        """Test that message tokens are correctly parsed."""
        from opencode_monitor.analytics.indexer.tracker import FileTracker
        from opencode_monitor.analytics.indexer.parsers import FileParser
        from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder

        indexer = HybridIndexer(storage_path=temp_storage, db_path=temp_db_path)
        indexer._db = AnalyticsDB(temp_db_path)
        indexer._db.connect()
        indexer._tracker = FileTracker(indexer._db)
        indexer._parser = FileParser()
        indexer._trace_builder = TraceBuilder(indexer._db)

        session_path = write_json_file(
            temp_storage,
            "session",
            "proj_002",
            "ses_token_test",
            create_session_json("ses_token_test"),
        )
        indexer._process_file("session", session_path)

        now_ms = int(datetime.now().timestamp() * 1000)
        message_data = {
            "id": "msg_token_test",
            "sessionID": "ses_token_test",
            "parentID": None,
            "role": "assistant",
            "agent": "oracle",
            "modelID": "claude-3-opus",
            "providerID": "anthropic",
            "mode": "agent",
            "cost": 0.05,
            "finish": "completed",
            "path": {"cwd": "/test"},
            "tokens": {
                "input": 5000,
                "output": 2000,
                "reasoning": 500,
                "cache": {"read": 1000, "write": 200},
            },
            "time": {"created": now_ms, "completed": now_ms + 10000},
        }
        file_path = write_json_file(
            temp_storage, "message", "ses_token_test", "msg_token_test", message_data
        )

        result = indexer._process_file("message", file_path)

        assert result
        conn = indexer._db.connect()
        msg = conn.execute(
            """SELECT tokens_input, tokens_output, tokens_reasoning, 
                      tokens_cache_read, tokens_cache_write 
               FROM messages WHERE id = 'msg_token_test'"""
        ).fetchone()
        assert msg[0] == 5000
        assert msg[1] == 2000
        assert msg[2] == 500
        assert msg[3] == 1000
        assert msg[4] == 200


class TestIndexerRegistry:
    def test_registry_lifecycle(self, temp_storage, temp_db_path):
        IndexerRegistry.clear()

        assert IndexerRegistry.get() is None

        indexer = IndexerRegistry.create(
            storage_path=temp_storage,
            db_path=temp_db_path,
        )
        assert isinstance(indexer, HybridIndexer)
        assert IndexerRegistry.get() is indexer

        IndexerRegistry.clear()
        assert IndexerRegistry.get() is None
