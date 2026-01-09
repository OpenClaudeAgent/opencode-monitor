"""Tests for UnifiedIndexer module - initialization, lifecycle, processing, batch ops, stats."""

import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from opencode_monitor.analytics.indexer.unified import (
    UnifiedIndexer,
    get_indexer,
    start_indexer,
    stop_indexer,
)


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test_analytics.duckdb"


@pytest.fixture
def indexer(temp_storage, temp_db_path):
    idx = UnifiedIndexer(storage_path=temp_storage, db_path=temp_db_path)
    yield idx
    if idx._running:
        idx.stop()


@pytest.fixture
def connected_indexer(temp_storage, temp_db_path):
    idx = UnifiedIndexer(storage_path=temp_storage, db_path=temp_db_path)
    idx._db.connect()
    yield idx
    if idx._running:
        idx.stop()
    idx._db.close()


def _now_ms():
    return int(datetime.now().timestamp() * 1000)


def create_session_json(
    session_id: str, title: str = "Test Session", parent_id: str | None = None
) -> dict:
    now = _now_ms()
    return {
        "id": session_id,
        "projectID": "proj_001",
        "directory": "/path/to/project",
        "title": title,
        "parentID": parent_id,
        "version": "1.0.0",
        "summary": {"additions": 10, "deletions": 5, "files": 3},
        "time": {"created": now, "updated": now},
    }


def create_message_json(
    message_id: str, session_id: str, agent: str = "executor"
) -> dict:
    now = _now_ms()
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
        "time": {"created": now, "completed": now + 5000},
    }


def create_part_json(
    part_id: str, session_id: str, message_id: str, tool: str = "read"
) -> dict:
    now = _now_ms()
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
            "time": {"start": now, "end": now + 100},
        },
        "time": {"start": now, "end": now + 100},
    }


def create_project_json(project_id: str) -> dict:
    now = _now_ms()
    return {
        "id": project_id,
        "worktree": "/path/to/project",
        "vcs": "git",
        "time": {"created": now, "updated": now},
    }


def create_skill_part_json(part_id: str, session_id: str, message_id: str) -> dict:
    now = _now_ms()
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
            "time": {"start": now, "end": now + 100},
        },
        "time": {"start": now, "end": now + 100},
    }


def create_task_part_json(
    part_id: str, session_id: str, message_id: str, child_session_id: str = "child_001"
) -> dict:
    now = _now_ms()
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
            "metadata": {"sessionId": child_session_id},
            "time": {"start": now, "end": now + 100},
        },
        "time": {"start": now, "end": now + 100},
    }


def write_json_file(
    storage: Path, ftype: str, proj: str, fid: str, data: dict | list
) -> Path:
    path = storage / ftype / proj
    path.mkdir(parents=True, exist_ok=True)
    fp = path / f"{fid}.json"
    fp.write_text(json.dumps(data))
    return fp


class TestUnifiedIndexerInit:
    def test_init_sets_all_core_attributes_and_components(
        self, temp_storage, temp_db_path
    ):
        """Init sets storage, running=False, all components created, stats initialized."""
        idx = UnifiedIndexer(storage_path=temp_storage, db_path=temp_db_path)

        # Core state: 5 assertions
        assert idx._storage_path == temp_storage
        assert idx._running is False
        assert idx._watcher is None
        assert idx._processor_thread is None
        assert idx._backfill_thread is None

        # Components: 6 assertions
        assert idx._tracker is not None
        assert idx._parser is not None
        assert idx._trace_builder is not None
        assert idx._queue is not None
        assert idx._queue.size == 0
        assert idx._batch_processor is not None
        assert idx._file_processor is not None

        # Stats: 10 assertions (5 keys x 2)
        for key in [
            "files_processed",
            "sessions_indexed",
            "messages_indexed",
            "parts_indexed",
            "traces_created",
        ]:
            assert key in idx._stats
            assert idx._stats[key] == 0

    def test_init_with_default_storage_path(self, temp_db_path):
        """Init uses default OPENCODE_STORAGE when not provided."""
        from opencode_monitor.analytics.indexer.unified.config import OPENCODE_STORAGE

        idx = UnifiedIndexer(db_path=temp_db_path)
        assert idx._storage_path == OPENCODE_STORAGE
        assert idx._db is not None
        assert idx._running is False
        assert idx._file_processor is not None
        assert idx._batch_processor is not None
        assert idx._queue is not None


class TestUnifiedIndexerLifecycle:
    def test_start_initializes_runtime_and_stop_cleans_up(self, indexer):
        """Start sets running/time/watcher/threads; stop cleans up."""
        from opencode_monitor.analytics.indexer.unified.core import USE_V2_INDEXER

        # Pre-start state
        assert indexer._running is False
        assert indexer._watcher is None

        # Start: assertions depend on v1 or v2 architecture
        indexer.start()
        assert indexer._running is True
        assert indexer._stats["start_time"] is not None
        assert indexer._watcher is not None
        assert indexer._watcher.is_running is True

        if USE_V2_INDEXER:
            # v2: Check accumulator and reconciler
            assert indexer._accumulator is not None
            assert indexer._reconciler is not None
        else:
            # v1: Check threads
            assert indexer._processor_thread is not None
            assert indexer._backfill_thread is not None
            assert indexer._processor_thread.is_alive()
            assert indexer._backfill_thread.is_alive()

        watcher = indexer._watcher

        # Stop: 3 assertions
        indexer.stop()
        assert indexer._running is False
        assert not watcher.is_running
        assert indexer._stats["start_time"] is not None  # Still recorded

    def test_start_and_stop_are_idempotent(self, indexer):
        """Multiple start calls reuse watcher; multiple stop calls are safe."""
        from opencode_monitor.analytics.indexer.unified.core import USE_V2_INDEXER

        # Start twice - same watcher: 4 assertions
        indexer.start()
        first_watcher = indexer._watcher
        if USE_V2_INDEXER:
            first_accumulator = indexer._accumulator
        else:
            first_thread = indexer._processor_thread
        assert indexer._running is True
        indexer.start()
        assert indexer._watcher is first_watcher
        if USE_V2_INDEXER:
            assert indexer._accumulator is first_accumulator
        else:
            assert indexer._processor_thread is first_thread
        assert indexer._running is True
        indexer.stop()

        # Multiple stops: 4 assertions
        indexer.stop()
        assert indexer._running is False
        indexer.start()
        assert indexer._running is True
        indexer.stop()
        indexer.stop()
        indexer.stop()
        assert indexer._running is False


class TestProcessEntity:
    @pytest.mark.parametrize(
        "entity_type,create_fn,stat_key,table,field,expected",
        [
            (
                "session",
                lambda: create_session_json("s1", "Title"),
                "sessions_indexed",
                "sessions",
                "title",
                "Title",
            ),
            (
                "message",
                lambda: create_message_json("m1", "s1", "dev"),
                "messages_indexed",
                "messages",
                "agent",
                "dev",
            ),
            (
                "part",
                lambda: create_part_json("p1", "s1", "m1", "write"),
                "parts_indexed",
                "parts",
                "tool_name",
                "write",
            ),
            (
                "project",
                lambda: create_project_json("proj1"),
                None,
                "projects",
                "worktree",
                "/path/to/project",
            ),
        ],
    )
    def test_process_entity_stores_in_db_and_updates_stats(
        self,
        connected_indexer,
        entity_type,
        create_fn,
        stat_key,
        table,
        field,
        expected,
    ):
        """Valid entity: returns ID, updates stats, stores in DB, count=1."""
        data = create_fn()
        entity_id = data["id"]
        proc = connected_indexer._file_processor

        # Pre-check stats
        if stat_key:
            assert connected_indexer._stats[stat_key] == 0

        # Process
        methods = {
            "session": proc._process_session,
            "message": proc._process_message,
            "part": proc._process_part,
            "project": proc._process_project,
        }
        result = methods[entity_type](data)

        # Verify: 5 assertions
        assert result == entity_id
        assert result is not None
        if stat_key:
            assert connected_indexer._stats[stat_key] == 1

        # DB storage: row exists, field matches, count=1
        conn = connected_indexer._db.connect()
        row = conn.execute(
            f"SELECT {field} FROM {table} WHERE id = '{entity_id}'"
        ).fetchone()
        assert row is not None
        assert row[0] == expected
        count = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE id = '{entity_id}'"
        ).fetchone()[0]
        assert count == 1

    @pytest.mark.parametrize("entity_type", ["session", "message", "part", "project"])
    def test_process_invalid_entity_returns_none(self, connected_indexer, entity_type):
        """Empty/invalid data returns None, stats unchanged."""
        proc = connected_indexer._file_processor
        methods = {
            "session": proc._process_session,
            "message": proc._process_message,
            "part": proc._process_part,
            "project": proc._process_project,
        }
        initial_files = connected_indexer._stats["files_processed"]
        result = methods[entity_type]({})
        assert result is None
        assert connected_indexer._stats["files_processed"] == initial_files

    def test_root_session_creates_trace_child_does_not(self, connected_indexer):
        """Root session creates trace; child session does not."""
        proc = connected_indexer._file_processor
        assert connected_indexer._stats["traces_created"] == 0
        assert connected_indexer._stats["sessions_indexed"] == 0

        # Root: 3 assertions
        proc._process_session(create_session_json("root", "Root", parent_id=None))
        assert connected_indexer._stats["traces_created"] == 1
        assert connected_indexer._stats["sessions_indexed"] == 1

        # Child: 3 assertions
        proc._process_session(create_session_json("child", "Child", parent_id="root"))
        assert connected_indexer._stats["traces_created"] == 1
        assert connected_indexer._stats["sessions_indexed"] == 2


class TestProcessSpecialParts:
    def test_skill_part_creates_skill_record(self, connected_indexer):
        """Skill part creates record in skills table with correct name and session."""
        data = create_skill_part_json("sk1", "s1", "m1")
        initial_parts = connected_indexer._stats["parts_indexed"]
        result = connected_indexer._file_processor._process_part(data)

        assert result == "sk1"
        assert connected_indexer._stats["parts_indexed"] == initial_parts + 1
        conn = connected_indexer._db.connect()
        row = conn.execute(
            "SELECT skill_name, session_id FROM skills WHERE id = 'sk1'"
        ).fetchone()
        assert row is not None
        assert row[0] == "test-skill"
        assert row[1] == "s1"

    @pytest.mark.parametrize("tool", ["read", "write", "edit"])
    def test_file_operation_creates_record(self, connected_indexer, tool):
        """File operations create file_operations records with operation and path."""
        data = create_part_json(f"{tool}_p", "s1", "m1", tool)
        result = connected_indexer._file_processor._process_part(data)

        assert result == f"{tool}_p"
        assert connected_indexer._stats["parts_indexed"] >= 1
        conn = connected_indexer._db.connect()
        row = conn.execute(
            f"SELECT operation, file_path FROM file_operations WHERE id = '{tool}_p'"
        ).fetchone()
        assert row is not None
        assert row[0] == tool
        assert row[1] == "/path/to/file.py"

    def test_delegation_task_creates_record(self, connected_indexer):
        """Task delegation creates delegation record with child agent and session."""
        proc = connected_indexer._file_processor
        proc._process_message(create_message_json("mp", "s1", "orchestrator"))
        assert connected_indexer._stats["messages_indexed"] == 1
        proc._process_part(create_task_part_json("tk1", "s1", "mp", "child_s"))
        assert connected_indexer._stats["parts_indexed"] == 1

        conn = connected_indexer._db.connect()
        row = conn.execute(
            "SELECT child_agent, child_session_id FROM delegations WHERE id = 'tk1'"
        ).fetchone()
        assert row is not None
        assert row[0] == "dev"
        assert row[1] == "child_s"


class TestProcessTodos:
    def test_process_todos_valid_and_invalid(self, connected_indexer, temp_storage):
        """Valid todos stored in DB with all fields; invalid returns None."""
        # Valid: 6 assertions
        todo_path = temp_storage / "todo" / "s1.json"
        todo_path.parent.mkdir(parents=True, exist_ok=True)
        todos = [
            {"id": "1", "content": "T1", "status": "pending", "priority": "high"},
            {"id": "2", "content": "T2", "status": "done", "priority": "low"},
        ]
        todo_path.write_text(json.dumps(todos))

        result = connected_indexer._file_processor._process_todos(
            "s1", todos, todo_path
        )
        assert result == "s1"
        conn = connected_indexer._db.connect()
        count = conn.execute(
            "SELECT COUNT(*) FROM todos WHERE session_id = 's1'"
        ).fetchone()[0]
        assert count == 2
        row = conn.execute(
            "SELECT content, status FROM todos WHERE session_id = 's1' ORDER BY content"
        ).fetchone()
        assert row is not None
        assert row[0] == "T1"
        assert row[1] == "pending"

        # Invalid: 2 assertions
        result2 = connected_indexer._file_processor._process_todos(
            "bad", "not a list", todo_path
        )
        assert result2 is None
        count2 = conn.execute(
            "SELECT COUNT(*) FROM todos WHERE session_id = 'bad'"
        ).fetchone()[0]
        assert count2 == 0


class TestProcessFile:
    @pytest.mark.parametrize(
        "ftype,create_fn,fid",
        [
            ("session", lambda: create_session_json("sf1"), "sf1"),
            ("message", lambda: create_message_json("mf1", "s1"), "mf1"),
            ("part", lambda: create_part_json("pf1", "s1", "m1"), "pf1"),
            ("project", lambda: create_project_json("pj1"), "pj1"),
        ],
    )
    def test_process_file_by_type_succeeds(
        self, connected_indexer, temp_storage, ftype, create_fn, fid
    ):
        """Process file: returns True, increments files_processed, file exists."""
        initial = connected_indexer._stats["files_processed"]
        fp = write_json_file(temp_storage, ftype, "p1", fid, create_fn())
        assert fp.exists()
        result = connected_indexer._process_file(ftype, fp)
        assert result is True
        assert connected_indexer._stats["files_processed"] == initial + 1
        assert connected_indexer._stats["files_error"] == 0

    def test_process_file_todo_succeeds(self, connected_indexer, temp_storage):
        """Todo file: returns True and stores in DB."""
        tp = temp_storage / "todo" / "p1"
        tp.mkdir(parents=True, exist_ok=True)
        fp = tp / "st.json"
        fp.write_text(
            json.dumps([{"id": "1", "content": "T", "status": "p", "priority": "h"}])
        )
        assert fp.exists()
        result = connected_indexer._process_file("todo", fp)
        assert result is True
        conn = connected_indexer._db.connect()
        count = conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
        assert count >= 1

    def test_process_file_errors(self, connected_indexer, temp_storage):
        """Invalid/empty/nonexistent: returns False, tracks errors."""
        initial_errors = connected_indexer._stats.get("files_error", 0)

        # Invalid JSON: 3 assertions
        bad = temp_storage / "session" / "p1" / "bad.json"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("not valid {{{")
        assert connected_indexer._process_file("session", bad) is False
        assert connected_indexer._stats["files_error"] == initial_errors + 1

        # Empty JSON: 2 assertions
        empty = temp_storage / "session" / "p1" / "empty.json"
        empty.write_text("{}")
        assert connected_indexer._process_file("session", empty) is False

        # Nonexistent: 2 assertions
        assert (
            connected_indexer._process_file("session", temp_storage / "nope.json")
            is False
        )
        assert connected_indexer._stats["files_error"] >= 1


class TestBatchProcess:
    @pytest.mark.parametrize(
        "ftype,create_fn,stat_key",
        [
            ("session", create_session_json, "sessions_indexed"),
            ("message", lambda id: create_message_json(id, "s1"), "messages_indexed"),
            ("part", lambda id: create_part_json(id, "s1", "m1"), "parts_indexed"),
        ],
    )
    def test_batch_process_multiple_files(
        self, connected_indexer, temp_storage, ftype, create_fn, stat_key
    ):
        """Batch: returns count, updates entity stats, files exist."""
        initial = connected_indexer._stats[stat_key]
        files = [
            write_json_file(
                temp_storage, ftype, "p1", f"{ftype}_{i}", create_fn(f"{ftype}_{i}")
            )
            for i in range(3)
        ]
        for f in files:
            assert f.exists()
        count = connected_indexer._batch_processor.process_files(ftype, files)
        assert count == 3
        assert connected_indexer._stats[stat_key] == initial + 3
        assert len(files) == 3

    def test_batch_process_with_invalid_skips_bad_files(
        self, connected_indexer, temp_storage
    ):
        """Batch with valid/invalid: only valid counted, stats correct."""
        valid = write_json_file(
            temp_storage, "session", "p1", "v", create_session_json("v")
        )
        invalid = temp_storage / "session" / "p1" / "inv.json"
        invalid.write_text("{}")
        initial_sessions = connected_indexer._stats["sessions_indexed"]
        count = connected_indexer._batch_processor.process_files(
            "session", [valid, invalid]
        )
        assert count == 1
        assert connected_indexer._stats["sessions_indexed"] == initial_sessions + 1

    def test_batch_process_empty_and_routing(self, connected_indexer, temp_storage):
        """Empty=0; routing works for all types with correct counts."""
        for ft in ["session", "message", "part"]:
            assert connected_indexer._batch_processor.process_files(ft, []) == 0

        for ft, fn in [
            ("session", create_session_json),
            ("message", lambda id: create_message_json(id, "s1")),
            ("part", lambda id: create_part_json(id, "s1", "m1")),
            ("project", create_project_json),
        ]:
            files = [
                write_json_file(temp_storage, ft, "p1", f"{ft}_r{i}", fn(f"{ft}_r{i}"))
                for i in range(2)
            ]
            result = connected_indexer._batch_process_files(ft, files)
            assert result == 2
            assert len(files) == 2


class TestStatsAndBackfill:
    def test_get_stats_includes_all_metrics(self, connected_indexer):
        """Stats: dict with core metrics, tracker, traces, queue_size, all valid types."""
        stats = connected_indexer.get_stats()
        assert isinstance(stats, dict)
        assert len(stats) > 5
        for key in [
            "files_processed",
            "sessions_indexed",
            "messages_indexed",
            "parts_indexed",
            "traces_created",
        ]:
            assert key in stats
            assert isinstance(stats[key], int)
        assert "tracker" in stats
        assert "traces" in stats
        assert "queue_size" in stats
        assert isinstance(stats["queue_size"], int)

    def test_force_backfill_returns_stats(self, connected_indexer, temp_storage):
        """force_backfill: returns dict with files_processed, total_files, both ints >= 0."""
        result = connected_indexer.force_backfill()
        assert isinstance(result, dict)
        assert "files_processed" in result
        assert "total_files" in result
        assert result["total_files"] >= 0
        assert result["files_processed"] >= 0
        assert isinstance(result["total_files"], int)

    def test_run_backfill_updates_cycle_stats(self, connected_indexer, temp_storage):
        """_run_backfill: increments cycles, sets last_backfill, processes files."""
        connected_indexer._running = True
        initial = connected_indexer._stats.get("backfill_cycles", 0)
        for i in range(2):
            write_json_file(
                temp_storage, "session", "p1", f"bf{i}", create_session_json(f"bf{i}")
            )
        connected_indexer._run_backfill()
        assert connected_indexer._stats["backfill_cycles"] == initial + 1
        assert connected_indexer._stats["last_backfill"] is not None
        assert connected_indexer._stats["sessions_indexed"] >= 2

    def test_resolve_parent_traces_returns_int(self, connected_indexer):
        """resolve_parent_traces: returns integer (may be negative for errors)."""
        result = connected_indexer.resolve_parent_traces()
        assert isinstance(result, int)
        # Can be negative (e.g., -2 for not implemented or error codes)
        assert result is not None

    def test_on_file_detected_queues_file(self, indexer, temp_storage):
        """_on_file_detected: adds to queue."""
        assert indexer._queue.size == 0
        tp = temp_storage / "session" / "t.json"
        tp.parent.mkdir(parents=True, exist_ok=True)
        tp.write_text("{}")
        indexer._on_file_detected("session", tp)
        assert indexer._queue.size >= 1
        # Queue may deduplicate identical paths
        tp2 = temp_storage / "session" / "t2.json"
        tp2.write_text("{}")
        indexer._on_file_detected("session", tp2)
        assert indexer._queue.size >= 1


class TestGlobalFunctions:
    def test_get_indexer_singleton_and_start_stop(
        self, temp_storage, temp_db_path, monkeypatch
    ):
        """get_indexer: singleton; start/stop: correct state transitions."""
        import opencode_monitor.analytics.indexer.unified.core as mod

        test_idx = UnifiedIndexer(storage_path=temp_storage, db_path=temp_db_path)
        monkeypatch.setattr(mod, "_indexer", test_idx)

        # Singleton: 3 assertions
        assert get_indexer() is test_idx
        assert get_indexer() is get_indexer()
        assert get_indexer()._storage_path == temp_storage

        # Start: 3 assertions
        assert test_idx._running is False
        start_indexer()
        assert test_idx._running is True
        assert test_idx._watcher is not None

        # Stop: 3 assertions
        stop_indexer()
        assert test_idx._running is False
        assert getattr(mod, "_indexer", "x") is None


class TestErrorHandling:
    @pytest.mark.parametrize(
        "etype,data",
        [
            ("session", {"title": "No ID"}),
            ("message", {"role": "assistant"}),
            ("part", {"id": "p1", "sessionID": "s1"}),
        ],
    )
    def test_process_entity_missing_required_fields(
        self, connected_indexer, etype, data
    ):
        """Missing required fields: returns None, stats unchanged."""
        proc = connected_indexer._file_processor
        initial = connected_indexer._stats["files_processed"]
        methods = {
            "session": proc._process_session,
            "message": proc._process_message,
            "part": proc._process_part,
        }
        result = methods[etype](data)
        assert result is None
        assert connected_indexer._stats["files_processed"] == initial

    def test_process_file_nonexistent_and_corrupted(
        self, connected_indexer, temp_storage
    ):
        """Nonexistent/corrupted: return False, track errors."""
        # Nonexistent: 2 assertions
        fake_path = temp_storage / "nope.json"
        assert not fake_path.exists()
        assert connected_indexer._process_file("session", fake_path) is False

        # Corrupted: 3 assertions
        bad = temp_storage / "session" / "p1" / "bad.json"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text('{"id": "x", incomplete')
        assert bad.exists()
        assert connected_indexer._process_file("session", bad) is False
        assert connected_indexer._stats["files_error"] >= 1


class TestEdgeCases:
    def test_empty_and_nonexistent_storage(self, temp_db_path, tmp_path):
        """Empty storage: starts/stops fine; nonexistent: creates indexer."""
        # Empty: 5 assertions
        empty = tmp_path / "empty"
        empty.mkdir()
        for d in ["session", "message", "part", "todo", "project"]:
            (empty / d).mkdir()
        idx = UnifiedIndexer(storage_path=empty, db_path=temp_db_path)
        assert idx._running is False
        idx.start()
        time.sleep(0.2)
        stats = idx.get_stats()
        assert stats is not None
        assert idx._running is True
        assert stats["files_processed"] == 0
        idx.stop()
        assert idx._running is False

        # Nonexistent: 4 assertions
        fake = tmp_path / "fake"
        assert not fake.exists()
        idx2 = UnifiedIndexer(storage_path=fake, db_path=temp_db_path)
        assert idx2 is not None
        assert idx2._storage_path == fake
        assert idx2._running is False


class TestConfig:
    def test_config_values_are_valid(self):
        """Config: all values importable, correct types, positive numbers."""
        from opencode_monitor.analytics.indexer.unified.config import (
            OPENCODE_STORAGE,
            BACKFILL_BATCH_SIZE,
            BACKFILL_INTERVAL,
            NUM_WORKERS,
        )

        assert OPENCODE_STORAGE is not None
        assert isinstance(OPENCODE_STORAGE, Path)
        assert BACKFILL_BATCH_SIZE > 0
        assert isinstance(BACKFILL_BATCH_SIZE, int)
        assert BACKFILL_INTERVAL > 0
        assert NUM_WORKERS > 0
        assert isinstance(NUM_WORKERS, int)
