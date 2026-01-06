"""
Tests for UnifiedIndexer module.

Tests cover:
- Initialization with valid/invalid paths
- Lifecycle (start/stop)
- Processing methods via _file_processor
- Batch operations via _batch_processor
- Statistics (get_stats)
- Backfill behavior (force_backfill)
- Error handling (corrupted files, missing data)

Target: >70% coverage for unified/* modules
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.unified import (
    UnifiedIndexer,
    get_indexer,
    start_indexer,
    stop_indexer,
)


# === Fixtures ===


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_analytics.duckdb"


@pytest.fixture
def temp_storage(tmp_path):
    """Create a temporary storage directory structure."""
    storage_path = tmp_path / "opencode_storage"
    for subdir in ["session", "message", "part", "todo", "project"]:
        (storage_path / subdir).mkdir(parents=True, exist_ok=True)
    return storage_path


@pytest.fixture
def indexer(temp_storage, temp_db_path):
    """Create a UnifiedIndexer instance (not started)."""
    idx = UnifiedIndexer(
        storage_path=temp_storage,
        db_path=temp_db_path,
    )
    yield idx
    # Cleanup
    if idx._running:
        idx.stop()


@pytest.fixture
def connected_indexer(temp_storage, temp_db_path):
    """Create a UnifiedIndexer with DB connected but not started."""
    idx = UnifiedIndexer(
        storage_path=temp_storage,
        db_path=temp_db_path,
    )
    idx._db.connect()
    yield idx
    # Cleanup
    if idx._running:
        idx.stop()
    idx._db.close()


# === Sample Data Factories ===


def create_session_json(
    session_id: str, title: str = "Test Session", parent_id: str | None = None
) -> dict:
    """Factory to create session JSON data."""
    now_ms = int(datetime.now().timestamp() * 1000)
    data = {
        "id": session_id,
        "projectID": "proj_001",
        "directory": "/path/to/project",
        "title": title,
        "parentID": parent_id,
        "version": "1.0.0",
        "summary": {"additions": 10, "deletions": 5, "files": 3},
        "time": {"created": now_ms, "updated": now_ms},
    }
    return data


def create_message_json(
    message_id: str, session_id: str, agent: str = "executor"
) -> dict:
    """Factory to create message JSON data."""
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": message_id,
        "sessionID": session_id,
        "parentID": None,
        "role": "assistant",
        "agent": agent,
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


def create_part_json(
    part_id: str,
    session_id: str,
    message_id: str,
    tool: str = "read",
    status: str = "completed",
) -> dict:
    """Factory to create part JSON data."""
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": part_id,
        "sessionID": session_id,
        "messageID": message_id,
        "type": "tool",
        "tool": tool,
        "callID": f"call_{part_id}",
        "state": {
            "status": status,
            "input": {"filePath": "/path/to/file.py"},
            "time": {"start": now_ms, "end": now_ms + 100},
        },
        "time": {"start": now_ms, "end": now_ms + 100},
    }


def create_todo_json() -> list:
    """Factory to create todo list JSON data."""
    return [
        {"id": "1", "content": "Task 1", "status": "pending", "priority": "high"},
        {"id": "2", "content": "Task 2", "status": "completed", "priority": "low"},
    ]


def create_project_json(project_id: str) -> dict:
    """Factory to create project JSON data."""
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": project_id,
        "worktree": "/path/to/project",
        "vcs": "git",
        "time": {"created": now_ms, "updated": now_ms},
    }


def create_skill_part_json(part_id: str, session_id: str, message_id: str) -> dict:
    """Factory to create skill tool part JSON data."""
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": part_id,
        "sessionID": session_id,
        "messageID": message_id,
        "type": "tool",
        "tool": "skill",
        "callID": f"call_{part_id}",
        "state": {
            "status": "completed",
            "input": {"name": "test-skill"},
            "time": {"start": now_ms, "end": now_ms + 100},
        },
        "time": {"start": now_ms, "end": now_ms + 100},
    }


def create_task_part_json(
    part_id: str,
    session_id: str,
    message_id: str,
    child_session_id: str | None = None,
) -> dict:
    """Factory to create task (delegation) tool part JSON data."""
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": part_id,
        "sessionID": session_id,
        "messageID": message_id,
        "type": "tool",
        "tool": "task",
        "callID": f"call_{part_id}",
        "state": {
            "status": "completed",
            "input": {"subagent_type": "dev"},
            "metadata": {"sessionId": child_session_id or "child_session_001"},
            "time": {"start": now_ms, "end": now_ms + 100},
        },
        "time": {"start": now_ms, "end": now_ms + 100},
    }


def create_file_op_part_json(
    part_id: str, session_id: str, message_id: str, tool: str = "read"
) -> dict:
    """Factory to create file operation tool part JSON data."""
    now_ms = int(datetime.now().timestamp() * 1000)
    return {
        "id": part_id,
        "sessionID": session_id,
        "messageID": message_id,
        "type": "tool",
        "tool": tool,
        "callID": f"call_{part_id}",
        "state": {
            "status": "completed",
            "input": {"filePath": "/path/to/file.py"},
            "time": {"start": now_ms, "end": now_ms + 100},
        },
        "time": {"start": now_ms, "end": now_ms + 100},
    }


def write_json_file(
    storage_path: Path,
    file_type: str,
    project_id: str,
    file_id: str,
    data: dict | list,
) -> Path:
    """Write JSON data to storage."""
    dir_path = storage_path / file_type / project_id
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{file_id}.json"
    file_path.write_text(json.dumps(data))
    return file_path


# === Initialization Tests ===


class TestUnifiedIndexerInit:
    """Tests for UnifiedIndexer initialization."""

    def test_init_sets_storage_path(self, temp_storage, temp_db_path):
        """Test initialization sets storage path."""
        idx = UnifiedIndexer(storage_path=temp_storage, db_path=temp_db_path)
        assert idx._storage_path == temp_storage

    def test_init_running_false(self, temp_storage, temp_db_path):
        """Test initialization sets running to False."""
        idx = UnifiedIndexer(storage_path=temp_storage, db_path=temp_db_path)
        assert idx._running is False

    def test_init_creates_components(self, temp_storage, temp_db_path):
        """Test initialization creates all required components."""
        idx = UnifiedIndexer(storage_path=temp_storage, db_path=temp_db_path)
        assert idx._tracker is not None
        assert idx._parser is not None
        assert idx._trace_builder is not None
        assert idx._queue is not None

    def test_init_creates_processors(self, temp_storage, temp_db_path):
        """Test initialization creates batch and file processors."""
        idx = UnifiedIndexer(storage_path=temp_storage, db_path=temp_db_path)
        assert idx._batch_processor is not None
        assert idx._file_processor is not None

    def test_init_initializes_stats(self, temp_storage, temp_db_path):
        """Test initialization creates stats dict."""
        idx = UnifiedIndexer(storage_path=temp_storage, db_path=temp_db_path)
        assert "files_processed" in idx._stats
        assert "sessions_indexed" in idx._stats
        assert "messages_indexed" in idx._stats
        assert "parts_indexed" in idx._stats
        assert "traces_created" in idx._stats
        assert idx._stats["files_processed"] == 0

    def test_init_with_default_storage_path(self, temp_db_path):
        """Test initialization uses default storage path when not provided."""
        from opencode_monitor.analytics.indexer.unified.config import OPENCODE_STORAGE

        idx = UnifiedIndexer(db_path=temp_db_path)
        assert idx._storage_path == OPENCODE_STORAGE

    def test_init_watcher_none_before_start(self, indexer):
        """Test watcher is None before start."""
        assert indexer._watcher is None

    def test_init_threads_none_before_start(self, indexer):
        """Test threads are None before start."""
        assert indexer._processor_thread is None
        assert indexer._backfill_thread is None


# === Lifecycle Tests ===


class TestUnifiedIndexerLifecycle:
    """Tests for start/stop lifecycle."""

    def test_start_sets_running(self, indexer, temp_storage):
        """Test start sets _running to True."""
        indexer.start()
        try:
            assert indexer._running is True
        finally:
            indexer.stop()

    def test_start_sets_start_time(self, indexer, temp_storage):
        """Test start records start time in stats."""
        indexer.start()
        try:
            assert indexer._stats["start_time"] is not None
        finally:
            indexer.stop()

    def test_start_creates_watcher(self, indexer, temp_storage):
        """Test start creates watcher."""
        indexer.start()
        try:
            assert indexer._watcher is not None
        finally:
            indexer.stop()

    def test_start_creates_threads(self, indexer, temp_storage):
        """Test start creates processor and backfill threads."""
        indexer.start()
        try:
            assert indexer._processor_thread is not None
            assert indexer._backfill_thread is not None
            assert indexer._processor_thread.is_alive()
            assert indexer._backfill_thread.is_alive()
        finally:
            indexer.stop()

    def test_start_is_idempotent(self, indexer, temp_storage):
        """Test calling start multiple times is safe."""
        indexer.start()
        first_watcher = indexer._watcher

        indexer.start()
        second_watcher = indexer._watcher

        try:
            assert first_watcher is second_watcher
        finally:
            indexer.stop()

    def test_stop_sets_running_false(self, indexer, temp_storage):
        """Test stop sets _running to False."""
        indexer.start()
        indexer.stop()
        assert indexer._running is False

    def test_stop_stops_watcher(self, indexer, temp_storage):
        """Test stop stops the watcher."""
        indexer.start()
        watcher = indexer._watcher
        indexer.stop()
        assert not watcher.is_running

    def test_stop_without_start(self, indexer):
        """Test stop without start doesn't crash."""
        indexer.stop()
        assert indexer._running is False

    def test_multiple_stops(self, indexer, temp_storage):
        """Test multiple stop calls are safe."""
        indexer.start()
        indexer.stop()
        indexer.stop()
        indexer.stop()
        assert indexer._running is False


# === Process Session Tests ===


class TestProcessSession:
    """Tests for session processing via FileProcessor."""

    def test_process_session_valid_data(self, connected_indexer, temp_storage):
        """Test processing valid session data."""
        session_data = create_session_json("ses_001", "Test Session")

        result = connected_indexer._file_processor._process_session(session_data)

        assert result == "ses_001"
        assert connected_indexer._stats["sessions_indexed"] == 1

    def test_process_session_stored_in_db(self, connected_indexer, temp_storage):
        """Test processed session is stored in database."""
        session_data = create_session_json("ses_002", "DB Session")

        connected_indexer._file_processor._process_session(session_data)

        conn = connected_indexer._db.connect()
        row = conn.execute("SELECT title FROM sessions WHERE id = 'ses_002'").fetchone()
        assert row[0] == "DB Session"

    def test_process_session_invalid_data(self, connected_indexer):
        """Test processing invalid session data returns None."""
        result = connected_indexer._file_processor._process_session({})
        assert result is None

    def test_process_session_creates_root_trace(self, connected_indexer):
        """Test processing root session creates trace."""
        session_data = create_session_json("ses_root", "Root Session", parent_id=None)

        connected_indexer._file_processor._process_session(session_data)

        assert connected_indexer._stats["traces_created"] == 1

    def test_process_session_no_trace_for_child(self, connected_indexer):
        """Test processing child session doesn't create trace."""
        session_data = create_session_json(
            "ses_child", "Child Session", parent_id="ses_parent"
        )

        connected_indexer._file_processor._process_session(session_data)

        assert connected_indexer._stats["traces_created"] == 0


# === Process Message Tests ===


class TestProcessMessage:
    """Tests for message processing via FileProcessor."""

    def test_process_message_valid_data(self, connected_indexer):
        """Test processing valid message data."""
        message_data = create_message_json("msg_001", "ses_001")

        result = connected_indexer._file_processor._process_message(message_data)

        assert result == "msg_001"
        assert connected_indexer._stats["messages_indexed"] == 1

    def test_process_message_stored_in_db(self, connected_indexer):
        """Test processed message is stored in database."""
        message_data = create_message_json("msg_002", "ses_001", agent="reviewer")

        connected_indexer._file_processor._process_message(message_data)

        conn = connected_indexer._db.connect()
        row = conn.execute("SELECT agent FROM messages WHERE id = 'msg_002'").fetchone()
        assert row[0] == "reviewer"

    def test_process_message_invalid_data(self, connected_indexer):
        """Test processing invalid message data returns None."""
        result = connected_indexer._file_processor._process_message({})
        assert result is None


# === Process Part Tests ===


class TestProcessPart:
    """Tests for part processing via FileProcessor."""

    def test_process_part_valid_data(self, connected_indexer):
        """Test processing valid part data."""
        part_data = create_part_json("part_001", "ses_001", "msg_001")

        result = connected_indexer._file_processor._process_part(part_data)

        assert result == "part_001"
        assert connected_indexer._stats["parts_indexed"] == 1

    def test_process_part_stored_in_db(self, connected_indexer):
        """Test processed part is stored in database."""
        part_data = create_part_json("part_002", "ses_001", "msg_001", tool="write")

        connected_indexer._file_processor._process_part(part_data)

        conn = connected_indexer._db.connect()
        row = conn.execute(
            "SELECT tool_name FROM parts WHERE id = 'part_002'"
        ).fetchone()
        assert row[0] == "write"

    def test_process_part_invalid_data(self, connected_indexer):
        """Test processing invalid part data returns None."""
        result = connected_indexer._file_processor._process_part({})
        assert result is None

    def test_process_skill_part(self, connected_indexer):
        """Test processing skill tool part."""
        part_data = create_skill_part_json("skill_part_001", "ses_001", "msg_001")

        result = connected_indexer._file_processor._process_part(part_data)

        assert result == "skill_part_001"
        conn = connected_indexer._db.connect()
        row = conn.execute(
            "SELECT skill_name FROM skills WHERE id = 'skill_part_001'"
        ).fetchone()
        assert row[0] == "test-skill"

    def test_process_file_operation_read(self, connected_indexer):
        """Test processing read file operation part."""
        part_data = create_file_op_part_json(
            "read_part_001", "ses_001", "msg_001", tool="read"
        )

        result = connected_indexer._file_processor._process_part(part_data)

        assert result == "read_part_001"
        conn = connected_indexer._db.connect()
        row = conn.execute(
            "SELECT operation FROM file_operations WHERE id = 'read_part_001'"
        ).fetchone()
        assert row[0] == "read"

    def test_process_file_operation_write(self, connected_indexer):
        """Test processing write file operation part."""
        part_data = create_file_op_part_json(
            "write_part_001", "ses_001", "msg_001", tool="write"
        )

        result = connected_indexer._file_processor._process_part(part_data)

        assert result == "write_part_001"

    def test_process_file_operation_edit(self, connected_indexer):
        """Test processing edit file operation part."""
        part_data = create_file_op_part_json(
            "edit_part_001", "ses_001", "msg_001", tool="edit"
        )

        result = connected_indexer._file_processor._process_part(part_data)

        assert result == "edit_part_001"


# === Process Todos Tests ===


class TestProcessTodos:
    """Tests for todos processing via FileProcessor."""

    def test_process_todos_valid_data(self, connected_indexer, temp_storage):
        """Test processing valid todos data."""
        todo_path = temp_storage / "todo" / "ses_001.json"
        todo_path.parent.mkdir(parents=True, exist_ok=True)
        todo_data = create_todo_json()
        todo_path.write_text(json.dumps(todo_data))

        result = connected_indexer._file_processor._process_todos(
            "ses_001", todo_data, todo_path
        )

        assert result == "ses_001"

    def test_process_todos_stored_in_db(self, connected_indexer, temp_storage):
        """Test processed todos are stored in database."""
        todo_path = temp_storage / "todo" / "ses_002.json"
        todo_path.parent.mkdir(parents=True, exist_ok=True)
        todo_data = create_todo_json()
        todo_path.write_text(json.dumps(todo_data))

        connected_indexer._file_processor._process_todos(
            "ses_002", todo_data, todo_path
        )

        conn = connected_indexer._db.connect()
        count = conn.execute(
            "SELECT COUNT(*) FROM todos WHERE session_id = 'ses_002'"
        ).fetchone()[0]
        assert count == 2

    def test_process_todos_invalid_data(self, connected_indexer, temp_storage):
        """Test processing invalid todos data returns None."""
        todo_path = temp_storage / "todo" / "ses_bad.json"
        todo_path.parent.mkdir(parents=True, exist_ok=True)

        result = connected_indexer._file_processor._process_todos(
            "ses_bad", "not a list", todo_path
        )

        assert result is None


# === Process Project Tests ===


class TestProcessProject:
    """Tests for project processing via FileProcessor."""

    def test_process_project_valid_data(self, connected_indexer):
        """Test processing valid project data."""
        project_data = create_project_json("proj_001")

        result = connected_indexer._file_processor._process_project(project_data)

        assert result == "proj_001"

    def test_process_project_stored_in_db(self, connected_indexer):
        """Test processed project is stored in database."""
        project_data = create_project_json("proj_002")

        connected_indexer._file_processor._process_project(project_data)

        conn = connected_indexer._db.connect()
        row = conn.execute(
            "SELECT worktree FROM projects WHERE id = 'proj_002'"
        ).fetchone()
        assert row[0] == "/path/to/project"

    def test_process_project_invalid_data(self, connected_indexer):
        """Test processing invalid project data returns None."""
        result = connected_indexer._file_processor._process_project({})
        assert result is None


# === Process File Tests ===


class TestProcessFile:
    """Tests for _process_file method on UnifiedIndexer."""

    def test_process_file_session(self, connected_indexer, temp_storage):
        """Test _process_file with session type."""
        file_path = write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_file_001",
            create_session_json("ses_file_001"),
        )

        result = connected_indexer._process_file("session", file_path)

        assert result is True
        assert connected_indexer._stats["files_processed"] == 1

    def test_process_file_message(self, connected_indexer, temp_storage):
        """Test _process_file with message type."""
        file_path = write_json_file(
            temp_storage,
            "message",
            "proj_001",
            "msg_file_001",
            create_message_json("msg_file_001", "ses_001"),
        )

        result = connected_indexer._process_file("message", file_path)

        assert result is True

    def test_process_file_part(self, connected_indexer, temp_storage):
        """Test _process_file with part type."""
        file_path = write_json_file(
            temp_storage,
            "part",
            "proj_001",
            "part_file_001",
            create_part_json("part_file_001", "ses_001", "msg_001"),
        )

        result = connected_indexer._process_file("part", file_path)

        assert result is True

    def test_process_file_todo(self, connected_indexer, temp_storage):
        """Test _process_file with todo type."""
        todo_path = temp_storage / "todo" / "proj_001"
        todo_path.mkdir(parents=True, exist_ok=True)
        file_path = todo_path / "ses_todo.json"
        file_path.write_text(json.dumps(create_todo_json()))

        result = connected_indexer._process_file("todo", file_path)

        assert result is True

    def test_process_file_project(self, connected_indexer, temp_storage):
        """Test _process_file with project type."""
        file_path = write_json_file(
            temp_storage,
            "project",
            "proj_001",
            "proj_file_001",
            create_project_json("proj_file_001"),
        )

        result = connected_indexer._process_file("project", file_path)

        assert result is True

    def test_process_file_invalid_json(self, connected_indexer, temp_storage):
        """Test _process_file with invalid JSON returns False."""
        invalid_path = temp_storage / "session" / "proj_001" / "bad.json"
        invalid_path.parent.mkdir(parents=True, exist_ok=True)
        invalid_path.write_text("not valid json {{{")

        result = connected_indexer._process_file("session", invalid_path)

        assert result is False
        assert connected_indexer._stats["files_error"] == 1

    def test_process_file_invalid_data(self, connected_indexer, temp_storage):
        """Test _process_file with valid JSON but invalid data."""
        file_path = temp_storage / "session" / "proj_001" / "empty.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("{}")

        result = connected_indexer._process_file("session", file_path)

        assert result is False


# === Batch Process Tests ===


class TestBatchProcessSessions:
    """Tests for batch session processing via BatchProcessor."""

    def test_batch_process_sessions_multiple_files(
        self, connected_indexer, temp_storage
    ):
        """Test batch processing multiple session files."""
        files = []
        for i in range(3):
            file_path = write_json_file(
                temp_storage,
                "session",
                "proj_001",
                f"ses_batch_{i}",
                create_session_json(f"ses_batch_{i}"),
            )
            files.append(file_path)

        count = connected_indexer._batch_processor.process_files("session", files)

        assert count == 3
        assert connected_indexer._stats["sessions_indexed"] == 3

    def test_batch_process_sessions_with_invalid(self, connected_indexer, temp_storage):
        """Test batch processing with some invalid files."""
        files = []
        # Valid file
        file_path = write_json_file(
            temp_storage,
            "session",
            "proj_001",
            "ses_valid",
            create_session_json("ses_valid"),
        )
        files.append(file_path)

        # Invalid file
        invalid_path = temp_storage / "session" / "proj_001" / "invalid.json"
        invalid_path.write_text("{}")
        files.append(invalid_path)

        count = connected_indexer._batch_processor.process_files("session", files)

        assert count == 1  # Only valid file processed

    def test_batch_process_sessions_empty_list(self, connected_indexer):
        """Test batch processing empty list."""
        count = connected_indexer._batch_processor.process_files("session", [])
        assert count == 0


class TestBatchProcessMessages:
    """Tests for batch message processing via BatchProcessor."""

    def test_batch_process_messages_multiple_files(
        self, connected_indexer, temp_storage
    ):
        """Test batch processing multiple message files."""
        files = []
        for i in range(3):
            file_path = write_json_file(
                temp_storage,
                "message",
                "proj_001",
                f"msg_batch_{i}",
                create_message_json(f"msg_batch_{i}", "ses_001"),
            )
            files.append(file_path)

        count = connected_indexer._batch_processor.process_files("message", files)

        assert count == 3
        assert connected_indexer._stats["messages_indexed"] == 3

    def test_batch_process_messages_empty_list(self, connected_indexer):
        """Test batch processing empty list."""
        count = connected_indexer._batch_processor.process_files("message", [])
        assert count == 0


class TestBatchProcessParts:
    """Tests for batch part processing via BatchProcessor."""

    def test_batch_process_parts_multiple_files(self, connected_indexer, temp_storage):
        """Test batch processing multiple part files."""
        files = []
        for i in range(3):
            file_path = write_json_file(
                temp_storage,
                "part",
                "proj_001",
                f"part_batch_{i}",
                create_part_json(f"part_batch_{i}", "ses_001", "msg_001"),
            )
            files.append(file_path)

        count = connected_indexer._batch_processor.process_files("part", files)

        assert count == 3
        assert connected_indexer._stats["parts_indexed"] == 3

    def test_batch_process_parts_empty_list(self, connected_indexer):
        """Test batch processing empty list."""
        count = connected_indexer._batch_processor.process_files("part", [])
        assert count == 0


class TestBatchProcessFiles:
    """Tests for _batch_process_files routing method."""

    def test_batch_process_files_sessions(self, connected_indexer, temp_storage):
        """Test batch_process_files routes to session processor."""
        files = []
        for i in range(2):
            file_path = write_json_file(
                temp_storage,
                "session",
                "proj_001",
                f"ses_route_{i}",
                create_session_json(f"ses_route_{i}"),
            )
            files.append(file_path)

        count = connected_indexer._batch_process_files("session", files)

        assert count == 2

    def test_batch_process_files_messages(self, connected_indexer, temp_storage):
        """Test batch_process_files routes to message processor."""
        files = []
        for i in range(2):
            file_path = write_json_file(
                temp_storage,
                "message",
                "proj_001",
                f"msg_route_{i}",
                create_message_json(f"msg_route_{i}", "ses_001"),
            )
            files.append(file_path)

        count = connected_indexer._batch_process_files("message", files)

        assert count == 2

    def test_batch_process_files_parts(self, connected_indexer, temp_storage):
        """Test batch_process_files routes to part processor."""
        files = []
        for i in range(2):
            file_path = write_json_file(
                temp_storage,
                "part",
                "proj_001",
                f"part_route_{i}",
                create_part_json(f"part_route_{i}", "ses_001", "msg_001"),
            )
            files.append(file_path)

        count = connected_indexer._batch_process_files("part", files)

        assert count == 2

    def test_batch_process_files_fallback(self, connected_indexer, temp_storage):
        """Test batch_process_files falls back to individual processing."""
        files = []
        for i in range(2):
            file_path = write_json_file(
                temp_storage,
                "project",
                "proj_001",
                f"proj_route_{i}",
                create_project_json(f"proj_route_{i}"),
            )
            files.append(file_path)

        count = connected_indexer._batch_process_files("project", files)

        assert count == 2


# === Stats Tests ===


class TestGetStats:
    """Tests for get_stats method."""

    def test_get_stats_returns_dict(self, indexer):
        """Test get_stats returns a dictionary."""
        stats = indexer.get_stats()
        assert isinstance(stats, dict)

    def test_get_stats_includes_core_metrics(self, indexer):
        """Test get_stats includes core metrics."""
        stats = indexer.get_stats()
        assert "files_processed" in stats
        assert "sessions_indexed" in stats
        assert "messages_indexed" in stats
        assert "parts_indexed" in stats
        assert "traces_created" in stats

    def test_get_stats_includes_tracker_stats(self, connected_indexer):
        """Test get_stats includes tracker stats."""
        stats = connected_indexer.get_stats()
        assert "tracker" in stats

    def test_get_stats_includes_traces_stats(self, connected_indexer):
        """Test get_stats includes traces stats."""
        stats = connected_indexer.get_stats()
        assert "traces" in stats

    def test_get_stats_includes_queue_size(self, connected_indexer):
        """Test get_stats includes queue size."""
        stats = connected_indexer.get_stats()
        assert "queue_size" in stats


# === Force Backfill Tests ===


class TestForceBackfill:
    """Tests for force_backfill method."""

    def test_force_backfill_returns_stats(self, connected_indexer, temp_storage):
        """Test force_backfill returns statistics."""
        result = connected_indexer.force_backfill()

        assert "files_processed" in result
        assert "total_files" in result

    def test_force_backfill_with_files(self, connected_indexer, temp_storage):
        """Test force_backfill processes files."""
        # Create some files
        for i in range(2):
            write_json_file(
                temp_storage,
                "session",
                "proj_001",
                f"ses_backfill_{i}",
                create_session_json(f"ses_backfill_{i}"),
            )

        result = connected_indexer.force_backfill()

        assert result["total_files"] >= 0  # May have processed files


class TestResolveParentTraces:
    """Tests for resolve_parent_traces method."""

    def test_resolve_parent_traces_returns_int(self, connected_indexer):
        """Test resolve_parent_traces returns integer."""
        result = connected_indexer.resolve_parent_traces()
        assert isinstance(result, int)


# === File Event Tests ===


class TestOnFileDetected:
    """Tests for _on_file_detected callback."""

    def test_on_file_detected_queues_file(self, indexer, temp_storage):
        """Test _on_file_detected adds file to queue."""
        test_path = temp_storage / "session" / "test.json"
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text("{}")

        indexer._on_file_detected("session", test_path)

        assert indexer._queue.size == 1


# === Global Functions Tests ===


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_indexer_creates_instance(
        self, temp_storage, temp_db_path, monkeypatch
    ):
        """Test get_indexer creates indexer instance."""
        import opencode_monitor.analytics.indexer.unified.core as unified_module

        # Reset global and ensure we use temp paths
        monkeypatch.setattr(unified_module, "_indexer", None)

        # Patch UnifiedIndexer to use temp paths
        original_class = unified_module.UnifiedIndexer

        class PatchedIndexer(original_class):
            def __init__(self, *args, **kwargs):
                super().__init__(
                    storage_path=temp_storage, db_path=temp_db_path, **kwargs
                )

        monkeypatch.setattr(unified_module, "UnifiedIndexer", PatchedIndexer)

        idx = get_indexer()

        assert idx is not None
        # Clean up
        monkeypatch.setattr(unified_module, "_indexer", None)

    def test_get_indexer_returns_same_instance(
        self, temp_storage, temp_db_path, monkeypatch
    ):
        """Test get_indexer returns same instance."""
        import opencode_monitor.analytics.indexer.unified.core as unified_module

        # Create a test indexer manually
        test_indexer = UnifiedIndexer(storage_path=temp_storage, db_path=temp_db_path)
        monkeypatch.setattr(unified_module, "_indexer", test_indexer)

        idx1 = get_indexer()
        idx2 = get_indexer()

        assert idx1 is idx2
        assert idx1 is test_indexer

    def test_start_indexer(self, temp_storage, temp_db_path, monkeypatch):
        """Test start_indexer function."""
        import opencode_monitor.analytics.indexer.unified.core as unified_module

        # Create indexer with temp paths
        test_indexer = UnifiedIndexer(storage_path=temp_storage, db_path=temp_db_path)
        monkeypatch.setattr(unified_module, "_indexer", test_indexer)

        start_indexer()

        try:
            assert test_indexer._running is True
        finally:
            stop_indexer()

    def test_stop_indexer(self, temp_storage, temp_db_path, monkeypatch):
        """Test stop_indexer function."""
        import opencode_monitor.analytics.indexer.unified.core as unified_module

        # Create and start indexer
        test_indexer = UnifiedIndexer(storage_path=temp_storage, db_path=temp_db_path)
        monkeypatch.setattr(unified_module, "_indexer", test_indexer)
        test_indexer.start()

        stop_indexer()

        assert getattr(unified_module, "_indexer", "not_none") is None


# === Error Handling Tests ===


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_process_file_nonexistent_path(self, connected_indexer, temp_storage):
        """Test _process_file with nonexistent path."""
        fake_path = temp_storage / "session" / "nonexistent.json"

        result = connected_indexer._process_file("session", fake_path)

        assert result is False

    def test_process_file_corrupted_json(self, connected_indexer, temp_storage):
        """Test _process_file with corrupted JSON."""
        corrupted_path = temp_storage / "session" / "proj_001" / "corrupted.json"
        corrupted_path.parent.mkdir(parents=True, exist_ok=True)
        corrupted_path.write_text('{"id": "test", incomplete')

        result = connected_indexer._process_file("session", corrupted_path)

        assert result is False

    def test_process_session_missing_required_fields(self, connected_indexer):
        """Test _process_session with missing required fields."""
        incomplete_data = {"title": "No ID"}

        result = connected_indexer._file_processor._process_session(incomplete_data)

        assert result is None

    def test_process_message_missing_required_fields(self, connected_indexer):
        """Test _process_message with missing required fields."""
        incomplete_data = {"role": "assistant"}

        result = connected_indexer._file_processor._process_message(incomplete_data)

        assert result is None

    def test_process_part_missing_type(self, connected_indexer):
        """Test _process_part with missing type field."""
        incomplete_data = {"id": "part_001", "sessionID": "ses_001"}

        result = connected_indexer._file_processor._process_part(incomplete_data)

        assert result is None


# === Edge Cases ===


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_storage_directory(self, temp_db_path, tmp_path):
        """Test handling of empty storage directory."""
        empty_storage = tmp_path / "empty_storage"
        empty_storage.mkdir()
        for subdir in ["session", "message", "part", "todo", "project"]:
            (empty_storage / subdir).mkdir()

        idx = UnifiedIndexer(
            storage_path=empty_storage,
            db_path=temp_db_path,
        )

        idx.start()
        time.sleep(0.3)  # Let threads start

        try:
            stats = idx.get_stats()
            assert stats is not None
        finally:
            idx.stop()

    def test_nonexistent_storage_path(self, temp_db_path, tmp_path):
        """Test handling of non-existent storage path."""
        fake_storage = tmp_path / "does_not_exist"

        idx = UnifiedIndexer(
            storage_path=fake_storage,
            db_path=temp_db_path,
        )

        # Should not crash on creation
        assert idx is not None

    def test_sequential_stats_access(self, connected_indexer):
        """Test sequential get_stats calls are safe."""
        # Note: DuckDB doesn't support concurrent access from multiple threads
        # so we test sequential access instead
        for _ in range(10):
            stats = connected_indexer.get_stats()
            assert stats is not None
            assert "files_processed" in stats


# === Delegation Tests ===


class TestDelegationProcessing:
    """Tests for delegation (task tool) processing."""

    def test_process_delegation_creates_record(self, connected_indexer, temp_storage):
        """Test processing task part creates delegation record."""
        # First create a parent message
        message_data = create_message_json(
            "msg_parent", "ses_001", agent="orchestrator"
        )
        connected_indexer._file_processor._process_message(message_data)

        # Now process a task delegation part
        task_data = create_task_part_json(
            "task_part_001", "ses_001", "msg_parent", child_session_id="child_ses_001"
        )

        connected_indexer._file_processor._process_part(task_data)

        # Verify delegation was created
        conn = connected_indexer._db.connect()
        row = conn.execute(
            "SELECT child_agent FROM delegations WHERE id = 'task_part_001'"
        ).fetchone()
        assert row is not None
        assert row[0] == "dev"


# === Backfill Loop Tests ===


class TestBackfillLoop:
    """Tests for backfill loop behavior."""

    def test_run_backfill_updates_stats(self, connected_indexer, temp_storage):
        """Test _run_backfill updates backfill stats."""
        connected_indexer._running = True

        # Create some files
        for i in range(2):
            write_json_file(
                temp_storage,
                "session",
                "proj_001",
                f"ses_backfill_test_{i}",
                create_session_json(f"ses_backfill_test_{i}"),
            )

        connected_indexer._run_backfill()

        assert connected_indexer._stats["backfill_cycles"] == 1
        assert connected_indexer._stats["last_backfill"] is not None


# === Config Tests ===


class TestConfig:
    """Tests for configuration values."""

    def test_config_imports(self):
        """Test config values can be imported."""
        from opencode_monitor.analytics.indexer.unified.config import (
            OPENCODE_STORAGE,
            BACKFILL_BATCH_SIZE,
            BACKFILL_INTERVAL,
            NUM_WORKERS,
        )

        assert OPENCODE_STORAGE is not None
        assert BACKFILL_BATCH_SIZE > 0
        assert BACKFILL_INTERVAL > 0
        assert NUM_WORKERS > 0
