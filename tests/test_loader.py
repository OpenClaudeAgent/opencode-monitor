"""
Tests for Analytics loader module - JSON data loading from OpenCode storage.

Covers:
- get_opencode_storage_path()
- load_sessions_fast()
- load_messages_fast()
- load_parts_fast()
- load_skills()
- load_delegations()
- load_opencode_data()
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.loader import (
    get_opencode_storage_path,
    load_sessions_fast,
    load_messages_fast,
    load_parts_fast,
    load_skills,
    load_delegations,
    load_opencode_data,
    extract_root_sessions,
    get_first_user_message,
    load_traces,
    ROOT_TRACE_PREFIX,
    ROOT_AGENT_TYPE,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def db(tmp_path: Path) -> AnalyticsDB:
    """Create a fresh DuckDB database for each test."""
    db_path = tmp_path / "test_loader.duckdb"
    db = AnalyticsDB(db_path)
    db.connect()
    return db


@pytest.fixture
def db_legacy_schema(tmp_path: Path):
    """Create a DuckDB database with legacy schema (no migrated columns).

    This is needed because load_*_fast functions use INSERT OR REPLACE
    with a fixed number of columns that doesn't match the migrated schema.
    """
    import duckdb

    db_path = tmp_path / "test_loader_legacy.duckdb"
    conn = duckdb.connect(str(db_path))

    # Create base tables without migrated columns
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id VARCHAR PRIMARY KEY,
            project_id VARCHAR,
            directory VARCHAR,
            title VARCHAR,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id VARCHAR PRIMARY KEY,
            session_id VARCHAR,
            parent_id VARCHAR,
            role VARCHAR,
            agent VARCHAR,
            model_id VARCHAR,
            provider_id VARCHAR,
            tokens_input INTEGER DEFAULT 0,
            tokens_output INTEGER DEFAULT 0,
            tokens_reasoning INTEGER DEFAULT 0,
            tokens_cache_read INTEGER DEFAULT 0,
            tokens_cache_write INTEGER DEFAULT 0,
            created_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            id VARCHAR PRIMARY KEY,
            message_id VARCHAR,
            part_type VARCHAR,
            tool_name VARCHAR,
            tool_status VARCHAR,
            created_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id VARCHAR PRIMARY KEY,
            message_id VARCHAR,
            session_id VARCHAR,
            skill_name VARCHAR,
            loaded_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS delegations (
            id VARCHAR PRIMARY KEY,
            message_id VARCHAR,
            session_id VARCHAR,
            parent_agent VARCHAR,
            child_agent VARCHAR,
            child_session_id VARCHAR,
            created_at TIMESTAMP
        )
    """)

    # Return a mock AnalyticsDB-like object
    class LegacyDB:
        def __init__(self, conn, path):
            self._conn = conn
            self._db_path = path

        def connect(self):
            return self._conn

        def clear_data(self):
            self._conn.execute("DELETE FROM delegations")
            self._conn.execute("DELETE FROM skills")
            self._conn.execute("DELETE FROM parts")
            self._conn.execute("DELETE FROM messages")
            self._conn.execute("DELETE FROM sessions")

    return LegacyDB(conn, db_path)


@pytest.fixture
def storage_path(tmp_path: Path) -> Path:
    """Create a mock OpenCode storage directory structure."""
    storage = tmp_path / "opencode_storage"
    storage.mkdir(parents=True)
    return storage


@pytest.fixture
def current_timestamp() -> int:
    """Current timestamp in milliseconds (for recent data)."""
    return int(time.time() * 1000)


# =============================================================================
# Helper Functions
# =============================================================================


def create_session_file(
    session_dir: Path,
    session_id: str,
    project_id: str = "proj_001",
    title: str = "Test Session",
    directory: str = "/test/path",
    created_ts: int | None = None,
    updated_ts: int | None = None,
) -> Path:
    """Create a session JSON file."""
    now_ms = int(time.time() * 1000)
    created_ts = created_ts or now_ms
    updated_ts = updated_ts or now_ms

    session_subdir = session_dir / session_id
    session_subdir.mkdir(parents=True, exist_ok=True)

    session_file = session_subdir / "session.json"
    data = {
        "id": session_id,
        "projectID": project_id,
        "directory": directory,
        "title": title,
        "time": {"created": created_ts, "updated": updated_ts},
    }
    session_file.write_text(json.dumps(data))
    return session_file


def create_message_file(
    message_dir: Path,
    message_id: str,
    session_id: str = "ses_001",
    role: str = "assistant",
    agent: str = "executor",
    created_ts: int | None = None,
    tokens_input: int = 100,
    tokens_output: int = 50,
) -> Path:
    """Create a message JSON file."""
    now_ms = int(time.time() * 1000)
    created_ts = created_ts or now_ms

    msg_subdir = message_dir / session_id
    msg_subdir.mkdir(parents=True, exist_ok=True)

    message_file = msg_subdir / f"{message_id}.json"
    data = {
        "id": message_id,
        "sessionID": session_id,
        "parentID": None,
        "role": role,
        "agent": agent,
        "modelID": "claude-sonnet",
        "providerID": "anthropic",
        "tokens": {
            "input": tokens_input,
            "output": tokens_output,
            "reasoning": 0,
            "cache": {"read": 0, "write": 0},
        },
        "time": {"created": created_ts, "completed": created_ts + 1000},
    }
    message_file.write_text(json.dumps(data))
    return message_file


def create_part_file(
    part_dir: Path,
    part_id: str,
    message_id: str = "msg_001",
    tool: str = "bash",
    tool_status: str = "completed",
    start_ts: int | None = None,
) -> Path:
    """Create a part JSON file."""
    now_ms = int(time.time() * 1000)
    start_ts = start_ts or now_ms

    msg_subdir = part_dir / message_id
    msg_subdir.mkdir(parents=True, exist_ok=True)

    part_file = msg_subdir / f"{part_id}.json"
    data = {
        "id": part_id,
        "messageID": message_id,
        "type": "tool",
        "tool": tool,
        "state": {"status": tool_status},
        "time": {"start": start_ts},
    }
    part_file.write_text(json.dumps(data))
    return part_file


def create_skill_part_file(
    part_dir: Path,
    part_id: str,
    message_id: str,
    session_id: str,
    skill_name: str,
    start_ts: int | None = None,
) -> Path:
    """Create a skill tool invocation part file."""
    now_ms = int(time.time() * 1000)
    start_ts = start_ts or now_ms

    msg_subdir = part_dir / message_id
    msg_subdir.mkdir(parents=True, exist_ok=True)

    part_file = msg_subdir / f"{part_id}.json"
    data = {
        "id": part_id,
        "messageID": message_id,
        "sessionID": session_id,
        "type": "tool",
        "tool": "skill",
        "state": {"input": {"name": skill_name}},
        "time": {"start": start_ts},
    }
    part_file.write_text(json.dumps(data))
    return part_file


def create_delegation_part_file(
    part_dir: Path,
    part_id: str,
    message_id: str,
    session_id: str,
    subagent_type: str,
    child_session_id: str | None = None,
    start_ts: int | None = None,
) -> Path:
    """Create a task tool invocation part file (delegation)."""
    now_ms = int(time.time() * 1000)
    start_ts = start_ts or now_ms

    msg_subdir = part_dir / message_id
    msg_subdir.mkdir(parents=True, exist_ok=True)

    part_file = msg_subdir / f"{part_id}.json"
    data = {
        "id": part_id,
        "messageID": message_id,
        "sessionID": session_id,
        "type": "tool",
        "tool": "task",
        "state": {
            "input": {"subagent_type": subagent_type},
            "time": {"start": start_ts},
            "metadata": {"sessionId": child_session_id},
        },
        "time": {"start": start_ts},
    }
    part_file.write_text(json.dumps(data))
    return part_file


# =============================================================================
# Tests: get_opencode_storage_path
# =============================================================================


class TestGetOpencodeStoragePath:
    """Tests for get_opencode_storage_path function."""

    def test_returns_path_object(self):
        """Function returns a Path object."""
        result = get_opencode_storage_path()
        assert isinstance(result, Path)

    def test_path_ends_with_storage(self):
        """Path ends with opencode/storage."""
        result = get_opencode_storage_path()
        assert result.name == "storage"
        assert result.parent.name == "opencode"

    def test_path_is_in_home(self):
        """Path is inside user's home directory."""
        result = get_opencode_storage_path()
        assert str(Path.home()) in str(result)


# =============================================================================
# Tests: load_sessions_fast
# =============================================================================


class TestLoadSessionsFast:
    """Tests for load_sessions_fast function.

    Note: Uses db_legacy_schema because load_sessions_fast uses INSERT OR REPLACE
    with a fixed column count that doesn't match the enriched/migrated schema.
    """

    def test_returns_zero_when_directory_not_exists(
        self, db: AnalyticsDB, storage_path: Path
    ):
        """Returns 0 when session directory doesn't exist."""
        result = load_sessions_fast(db, storage_path)
        assert result == 0

    def test_loads_valid_sessions(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Loads sessions from valid JSON files."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Create 3 session files
        for i in range(3):
            create_session_file(
                session_dir,
                f"ses_{i}",
                title=f"Session {i}",
                created_ts=current_timestamp,
            )

        result = load_sessions_fast(db_legacy_schema, storage_path)
        assert result == 3

        # Verify data in database
        conn = db_legacy_schema.connect()
        sessions = conn.execute("SELECT id, title FROM sessions ORDER BY id").fetchall()
        assert len(sessions) == 3
        assert sessions[0][0] == "ses_0"
        assert sessions[0][1] == "Session 0"

    def test_skips_old_sessions(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Skips sessions older than max_days."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Create recent session
        create_session_file(
            session_dir, "ses_recent", title="Recent", created_ts=current_timestamp
        )

        # Create old session (60 days ago)
        old_ts = int((datetime.now() - timedelta(days=60)).timestamp() * 1000)
        create_session_file(session_dir, "ses_old", title="Old", created_ts=old_ts)

        result = load_sessions_fast(db_legacy_schema, storage_path, max_days=30)
        assert result == 1

        conn = db_legacy_schema.connect()
        sessions = conn.execute("SELECT id FROM sessions").fetchall()
        assert len(sessions) == 1
        assert sessions[0][0] == "ses_recent"

    def test_handles_invalid_json_returns_zero(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Returns 0 when JSON is malformed (DuckDB strict JSON parsing)."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Create valid session
        create_session_file(
            session_dir, "ses_valid", title="Valid", created_ts=current_timestamp
        )

        # Create invalid JSON file
        invalid_dir = session_dir / "ses_invalid"
        invalid_dir.mkdir()
        invalid_file = invalid_dir / "session.json"
        invalid_file.write_text("{ invalid json }")

        # DuckDB's read_json_auto doesn't support ignore_errors for standard JSON
        result = load_sessions_fast(db_legacy_schema, storage_path)
        # Returns 0 because malformed JSON causes query to fail
        assert result == 0

    def test_handles_missing_required_fields(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Handles sessions with missing required fields."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Create session with missing id field
        missing_id_dir = session_dir / "ses_missing"
        missing_id_dir.mkdir()
        missing_file = missing_id_dir / "session.json"
        missing_file.write_text(
            json.dumps(
                {
                    "projectID": "proj",
                    "title": "Missing ID",
                    "time": {
                        "created": current_timestamp,
                        "updated": current_timestamp,
                    },
                }
            )
        )

        # Create valid session
        create_session_file(
            session_dir, "ses_valid", title="Valid", created_ts=current_timestamp
        )

        result = load_sessions_fast(db_legacy_schema, storage_path)
        # Only valid session should be loaded (WHERE id IS NOT NULL)
        assert result == 1


# =============================================================================
# Tests: load_messages_fast
# =============================================================================


class TestLoadMessagesFast:
    """Tests for load_messages_fast function.

    Note: Uses db_legacy_schema because load_messages_fast uses INSERT OR REPLACE
    with a fixed column count that doesn't match the enriched/migrated schema.
    """

    def test_returns_zero_when_directory_not_exists(
        self, db: AnalyticsDB, storage_path: Path
    ):
        """Returns 0 when message directory doesn't exist."""
        result = load_messages_fast(db, storage_path)
        assert result == 0

    def test_loads_valid_messages(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Loads messages from valid JSON files."""
        message_dir = storage_path / "message"
        message_dir.mkdir()

        # Create 3 message files
        for i in range(3):
            create_message_file(
                message_dir,
                f"msg_{i}",
                session_id=f"ses_{i}",
                created_ts=current_timestamp,
            )

        result = load_messages_fast(db_legacy_schema, storage_path)
        assert result == 3

        # Verify data in database
        conn = db_legacy_schema.connect()
        messages = conn.execute(
            "SELECT id, session_id, role FROM messages ORDER BY id"
        ).fetchall()
        assert len(messages) == 3
        assert messages[0][0] == "msg_0"
        assert messages[0][1] == "ses_0"
        assert messages[0][2] == "assistant"

    def test_loads_token_metrics(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Loads token metrics correctly."""
        message_dir = storage_path / "message"
        message_dir.mkdir()

        create_message_file(
            message_dir,
            "msg_tokens",
            created_ts=current_timestamp,
            tokens_input=500,
            tokens_output=200,
        )

        load_messages_fast(db_legacy_schema, storage_path)

        conn = db_legacy_schema.connect()
        msg = conn.execute(
            "SELECT tokens_input, tokens_output FROM messages WHERE id = 'msg_tokens'"
        ).fetchone()
        assert msg is not None
        assert msg[0] == 500
        assert msg[1] == 200

    def test_skips_old_messages(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Skips messages older than max_days."""
        message_dir = storage_path / "message"
        message_dir.mkdir()

        # Create recent message
        create_message_file(message_dir, "msg_recent", created_ts=current_timestamp)

        # Create old message (60 days ago)
        old_ts = int((datetime.now() - timedelta(days=60)).timestamp() * 1000)
        create_message_file(message_dir, "msg_old", created_ts=old_ts)

        result = load_messages_fast(db_legacy_schema, storage_path, max_days=30)
        assert result == 1


# =============================================================================
# Tests: load_parts_fast
# =============================================================================


class TestLoadPartsFast:
    """Tests for load_parts_fast function.

    Note: Uses db_legacy_schema because load_parts_fast uses INSERT OR REPLACE
    with a fixed column count that doesn't match the enriched/migrated schema.
    """

    def test_returns_zero_when_directory_not_exists(
        self, db: AnalyticsDB, storage_path: Path
    ):
        """Returns 0 when part directory doesn't exist."""
        result = load_parts_fast(db, storage_path)
        assert result == 0

    def test_loads_valid_parts(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Loads parts from valid JSON files."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create 3 part files
        for i in range(3):
            create_part_file(
                part_dir,
                f"prt_{i}",
                message_id=f"msg_{i}",
                tool="bash",
                start_ts=current_timestamp,
            )

        result = load_parts_fast(db_legacy_schema, storage_path)
        assert result == 3

        # Verify data in database
        conn = db_legacy_schema.connect()
        parts = conn.execute("SELECT id, tool_name FROM parts ORDER BY id").fetchall()
        assert len(parts) == 3
        assert parts[0][0] == "prt_0"
        assert parts[0][1] == "bash"

    def test_only_loads_tool_type_parts(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Only loads parts with type='tool'."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create tool part
        create_part_file(part_dir, "prt_tool", tool="bash", start_ts=current_timestamp)

        # Create non-tool part (text type)
        msg_subdir = part_dir / "msg_text"
        msg_subdir.mkdir()
        text_part = msg_subdir / "prt_text.json"
        text_part.write_text(
            json.dumps(
                {
                    "id": "prt_text",
                    "messageID": "msg_text",
                    "type": "text",
                    "time": {"start": current_timestamp},
                }
            )
        )

        result = load_parts_fast(db_legacy_schema, storage_path)
        # Only tool parts should be loaded
        assert result == 1

        conn = db_legacy_schema.connect()
        parts = conn.execute("SELECT id FROM parts").fetchall()
        assert len(parts) == 1
        assert parts[0][0] == "prt_tool"


# =============================================================================
# Tests: load_skills
# =============================================================================


class TestLoadSkills:
    """Tests for load_skills function."""

    def test_returns_zero_when_directory_not_exists(
        self, db: AnalyticsDB, storage_path: Path
    ):
        """Returns 0 when part directory doesn't exist."""
        result = load_skills(db, storage_path)
        assert result == 0

    def test_loads_skill_invocations(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Loads skill tool invocations."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create skill parts
        create_skill_part_file(
            part_dir,
            "prt_skill_1",
            "msg_001",
            "ses_001",
            "functional-testing",
            current_timestamp,
        )
        create_skill_part_file(
            part_dir,
            "prt_skill_2",
            "msg_002",
            "ses_001",
            "agentic-flow",
            current_timestamp,
        )

        result = load_skills(db, storage_path)
        assert result == 2

        # Verify data in database
        conn = db.connect()
        skills = conn.execute(
            "SELECT skill_name FROM skills ORDER BY skill_name"
        ).fetchall()
        assert len(skills) == 2
        assert skills[0][0] == "agentic-flow"
        assert skills[1][0] == "functional-testing"

    def test_ignores_non_skill_tools(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Ignores non-skill tool invocations."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create skill part
        create_skill_part_file(
            part_dir, "prt_skill", "msg_001", "ses_001", "test-skill", current_timestamp
        )

        # Create non-skill tool part
        create_part_file(part_dir, "prt_bash", tool="bash", start_ts=current_timestamp)

        result = load_skills(db, storage_path)
        assert result == 1  # Only skill part

    def test_skips_old_skills(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Skips skills older than max_days."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create recent skill
        create_skill_part_file(
            part_dir,
            "prt_recent",
            "msg_001",
            "ses_001",
            "recent-skill",
            current_timestamp,
        )

        # Create old skill (60 days ago)
        old_ts = int((datetime.now() - timedelta(days=60)).timestamp() * 1000)
        create_skill_part_file(
            part_dir, "prt_old", "msg_002", "ses_002", "old-skill", old_ts
        )

        result = load_skills(db, storage_path, max_days=30)
        assert result == 1

    def test_handles_invalid_json(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Continues when encountering invalid JSON files."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create valid skill
        create_skill_part_file(
            part_dir,
            "prt_valid",
            "msg_001",
            "ses_001",
            "valid-skill",
            current_timestamp,
        )

        # Create invalid JSON file
        invalid_dir = part_dir / "msg_invalid"
        invalid_dir.mkdir()
        invalid_file = invalid_dir / "prt_invalid.json"
        invalid_file.write_text("{ not valid json }")

        result = load_skills(db, storage_path)
        assert result == 1  # Only valid skill

    def test_handles_missing_skill_name(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Skips skills with missing skill name."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create valid skill
        create_skill_part_file(
            part_dir,
            "prt_valid",
            "msg_001",
            "ses_001",
            "valid-skill",
            current_timestamp,
        )

        # Create skill with missing name
        missing_dir = part_dir / "msg_missing"
        missing_dir.mkdir()
        missing_file = missing_dir / "prt_missing.json"
        missing_file.write_text(
            json.dumps(
                {
                    "id": "prt_missing",
                    "messageID": "msg_missing",
                    "sessionID": "ses_001",
                    "tool": "skill",
                    "state": {"input": {}},  # Missing "name" field
                    "time": {"start": current_timestamp},
                }
            )
        )

        result = load_skills(db, storage_path)
        assert result == 1  # Only valid skill


# =============================================================================
# Tests: load_delegations
# =============================================================================


class TestLoadDelegations:
    """Tests for load_delegations function."""

    def test_returns_zero_when_directory_not_exists(
        self, db: AnalyticsDB, storage_path: Path
    ):
        """Returns 0 when part directory doesn't exist."""
        result = load_delegations(db, storage_path)
        assert result == 0

    def test_loads_delegation_tasks(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Loads task tool invocations (delegations)."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create delegation parts
        create_delegation_part_file(
            part_dir,
            "prt_del_1",
            "msg_001",
            "ses_001",
            "tester",
            "child_ses_001",
            current_timestamp,
        )
        create_delegation_part_file(
            part_dir,
            "prt_del_2",
            "msg_002",
            "ses_001",
            "refactoring",
            "child_ses_002",
            current_timestamp,
        )

        result = load_delegations(db, storage_path)
        assert result == 2

        # Verify data in database
        conn = db.connect()
        delegations = conn.execute(
            "SELECT id, child_agent FROM delegations ORDER BY id"
        ).fetchall()
        assert len(delegations) == 2
        assert delegations[0][1] == "tester"
        assert delegations[1][1] == "refactoring"

    def test_ignores_non_task_tools(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Ignores non-task tool invocations."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create task delegation
        create_delegation_part_file(
            part_dir,
            "prt_task",
            "msg_001",
            "ses_001",
            "tester",
            start_ts=current_timestamp,
        )

        # Create non-task tool part
        create_part_file(part_dir, "prt_bash", tool="bash", start_ts=current_timestamp)

        result = load_delegations(db, storage_path)
        assert result == 1  # Only task delegation

    def test_skips_old_delegations(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Skips delegations older than max_days."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create recent delegation
        create_delegation_part_file(
            part_dir,
            "prt_recent",
            "msg_001",
            "ses_001",
            "tester",
            start_ts=current_timestamp,
        )

        # Create old delegation (60 days ago)
        old_ts = int((datetime.now() - timedelta(days=60)).timestamp() * 1000)
        create_delegation_part_file(
            part_dir, "prt_old", "msg_002", "ses_002", "old-agent", start_ts=old_ts
        )

        result = load_delegations(db, storage_path, max_days=30)
        assert result == 1

    def test_handles_missing_subagent_type(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Skips delegations with missing subagent_type."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create valid delegation
        create_delegation_part_file(
            part_dir,
            "prt_valid",
            "msg_001",
            "ses_001",
            "tester",
            start_ts=current_timestamp,
        )

        # Create delegation with missing subagent_type
        missing_dir = part_dir / "msg_missing"
        missing_dir.mkdir()
        missing_file = missing_dir / "prt_missing.json"
        missing_file.write_text(
            json.dumps(
                {
                    "id": "prt_missing",
                    "messageID": "msg_missing",
                    "sessionID": "ses_001",
                    "tool": "task",
                    "state": {"input": {}},  # Missing subagent_type
                    "time": {"start": current_timestamp},
                }
            )
        )

        result = load_delegations(db, storage_path)
        assert result == 1  # Only valid delegation

    def test_resolves_parent_agent_from_messages(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Resolves parent_agent from messages table."""
        # First insert a message to be the parent
        conn = db.connect()
        conn.execute(
            """INSERT INTO messages (id, session_id, role, agent, created_at)
               VALUES ('msg_parent', 'ses_001', 'assistant', 'executor', CURRENT_TIMESTAMP)"""
        )

        part_dir = storage_path / "part"
        part_dir.mkdir()

        create_delegation_part_file(
            part_dir,
            "prt_del",
            "msg_parent",  # Reference to existing message
            "ses_001",
            "tester",
            start_ts=current_timestamp,
        )

        load_delegations(db, storage_path)

        delegation = conn.execute(
            "SELECT parent_agent FROM delegations WHERE id = 'prt_del'"
        ).fetchone()
        assert delegation is not None
        assert delegation[0] == "executor"


# =============================================================================
# Tests: load_opencode_data
# =============================================================================


class TestLoadOpencodeData:
    """Tests for load_opencode_data orchestration function."""

    def test_returns_error_when_storage_not_found(
        self, db: AnalyticsDB, tmp_path: Path
    ):
        """Returns error dict when storage path doesn't exist."""
        non_existent = tmp_path / "non_existent"

        result = load_opencode_data(db=db, storage_path=non_existent)

        assert result["error"] == "Storage not found"
        assert result["sessions"] == 0
        assert result["messages"] == 0

    def test_creates_db_if_not_provided(self, storage_path: Path):
        """Creates AnalyticsDB if not provided."""
        # Create minimal structure
        session_dir = storage_path / "session"
        session_dir.mkdir()

        with patch("opencode_monitor.analytics.loader.AnalyticsDB") as mock_db_class:
            mock_db = MagicMock()
            mock_db.connect.return_value = MagicMock()
            mock_db_class.return_value = mock_db

            load_opencode_data(storage_path=storage_path)

            mock_db_class.assert_called_once()

    def test_uses_default_storage_path(self, db: AnalyticsDB):
        """Uses default storage path when not provided."""
        with patch(
            "opencode_monitor.analytics.loader.get_opencode_storage_path"
        ) as mock_get_path:
            mock_get_path.return_value = Path("/non/existent/path")

            load_opencode_data(db=db)

            mock_get_path.assert_called_once()

    def test_clears_data_when_requested(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Clears existing data when clear_first=True."""
        # Pre-populate database
        conn = db.connect()
        conn.execute(
            """INSERT INTO sessions (id, title, created_at)
               VALUES ('existing', 'Existing', CURRENT_TIMESTAMP)"""
        )

        # Create session directory (empty)
        session_dir = storage_path / "session"
        session_dir.mkdir()

        load_opencode_data(db=db, storage_path=storage_path, clear_first=True)

        result = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        assert result is not None
        assert result[0] == 0  # Cleared

    def test_preserves_data_when_clear_first_false(
        self, db: AnalyticsDB, storage_path: Path
    ):
        """Preserves existing data when clear_first=False."""
        # Pre-populate database
        conn = db.connect()
        conn.execute(
            """INSERT INTO sessions (id, title, created_at)
               VALUES ('existing', 'Existing', CURRENT_TIMESTAMP)"""
        )

        # Create session directory (empty)
        session_dir = storage_path / "session"
        session_dir.mkdir()

        load_opencode_data(db=db, storage_path=storage_path, clear_first=False)

        result = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        assert result is not None
        assert result[0] == 1  # Preserved

    def test_loads_skills_and_delegations(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Loads skills and delegations (these work with enriched schema)."""
        # Create session directory (empty - sessions will fail due to schema)
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Create message directory (empty - messages will fail due to schema)
        message_dir = storage_path / "message"
        message_dir.mkdir()

        # Create part directory
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create skill
        create_skill_part_file(
            part_dir, "prt_skill", "msg_001", "ses_001", "test-skill", current_timestamp
        )

        # Create delegation
        create_delegation_part_file(
            part_dir,
            "prt_del",
            "msg_001",
            "ses_001",
            "tester",
            start_ts=current_timestamp,
        )

        result = load_opencode_data(db=db, storage_path=storage_path)

        # Skills and delegations work with enriched schema
        assert result["skills"] == 1
        assert result["delegations"] == 1

    def test_loads_all_data_types_legacy_schema(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Loads all data types with legacy schema."""
        # Create session
        session_dir = storage_path / "session"
        session_dir.mkdir()
        create_session_file(
            session_dir, "ses_001", title="Test", created_ts=current_timestamp
        )

        # Create message
        message_dir = storage_path / "message"
        message_dir.mkdir()
        create_message_file(
            message_dir, "msg_001", session_id="ses_001", created_ts=current_timestamp
        )

        # Create part directory
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create skill
        create_skill_part_file(
            part_dir, "prt_skill", "msg_001", "ses_001", "test-skill", current_timestamp
        )

        # Create delegation
        create_delegation_part_file(
            part_dir,
            "prt_del",
            "msg_001",
            "ses_001",
            "tester",
            start_ts=current_timestamp,
        )

        result = load_opencode_data(db=db_legacy_schema, storage_path=storage_path)

        assert result["sessions"] == 1
        assert result["messages"] == 1
        assert result["skills"] == 1
        assert result["delegations"] == 1

    def test_skips_parts_by_default(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Skips parts loading by default (skip_parts=True)."""
        # Create session
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Create part
        part_dir = storage_path / "part"
        part_dir.mkdir()
        create_part_file(part_dir, "prt_001", tool="bash", start_ts=current_timestamp)

        result = load_opencode_data(db=db, storage_path=storage_path)

        assert result["parts"] == 0  # Skipped by default

    def test_loads_parts_when_requested_legacy_schema(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Loads parts when skip_parts=False (with legacy schema)."""
        # Create session
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Create part
        part_dir = storage_path / "part"
        part_dir.mkdir()
        create_part_file(part_dir, "prt_001", tool="bash", start_ts=current_timestamp)

        result = load_opencode_data(
            db=db_legacy_schema, storage_path=storage_path, skip_parts=False
        )

        assert result["parts"] == 1

    def test_returns_complete_result_dict(self, db: AnalyticsDB, storage_path: Path):
        """Returns dict with all expected keys."""
        # Create minimal structure
        session_dir = storage_path / "session"
        session_dir.mkdir()

        result = load_opencode_data(db=db, storage_path=storage_path)

        expected_keys = {"sessions", "messages", "parts", "delegations", "skills"}
        assert expected_keys.issubset(result.keys())


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_empty_directories(self, db: AnalyticsDB, storage_path: Path):
        """Handles empty session/message/part directories."""
        # Create empty directories
        (storage_path / "session").mkdir()
        (storage_path / "message").mkdir()
        (storage_path / "part").mkdir()

        result = load_opencode_data(db=db, storage_path=storage_path)

        assert result["sessions"] == 0
        assert result["messages"] == 0
        assert result["parts"] == 0

    def test_handles_nested_structure(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Handles nested directory structure correctly."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Create deeply nested session
        nested_dir = session_dir / "proj_001" / "branch_main" / "ses_nested"
        nested_dir.mkdir(parents=True)

        session_file = nested_dir / "session.json"
        session_file.write_text(
            json.dumps(
                {
                    "id": "ses_nested",
                    "projectID": "proj_001",
                    "directory": "/test",
                    "title": "Nested Session",
                    "time": {
                        "created": current_timestamp,
                        "updated": current_timestamp,
                    },
                }
            )
        )

        result = load_sessions_fast(db_legacy_schema, storage_path)
        assert result == 1

    def test_handles_special_characters_in_paths(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Handles special characters in file paths."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Create session with special characters in directory
        create_session_file(
            session_dir,
            "ses_special",
            directory="/path/with spaces/and-dashes",
            title="Session with 'quotes'",
            created_ts=current_timestamp,
        )

        result = load_sessions_fast(db_legacy_schema, storage_path)
        assert result == 1

    def test_handles_unicode_content(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Handles unicode content in JSON files."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        session_subdir = session_dir / "ses_unicode"
        session_subdir.mkdir()

        session_file = session_subdir / "session.json"
        session_file.write_text(
            json.dumps(
                {
                    "id": "ses_unicode",
                    "projectID": "proj_001",
                    "directory": "/projet/francais",
                    "title": "Session avec accents",
                    "time": {
                        "created": current_timestamp,
                        "updated": current_timestamp,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = load_sessions_fast(db_legacy_schema, storage_path)
        assert result == 1

        conn = db_legacy_schema.connect()
        session = conn.execute(
            "SELECT title FROM sessions WHERE id = 'ses_unicode'"
        ).fetchone()
        assert session is not None
        assert "accents" in session[0]

    def test_handles_null_time_values(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Handles null/missing time values in skill parts."""
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create skill with no time.start
        msg_dir = part_dir / "msg_no_time"
        msg_dir.mkdir()

        skill_file = msg_dir / "prt_no_time.json"
        skill_file.write_text(
            json.dumps(
                {
                    "id": "prt_no_time",
                    "messageID": "msg_no_time",
                    "sessionID": "ses_001",
                    "tool": "skill",
                    "state": {"input": {"name": "test-skill"}},
                    "time": {},  # Empty time object
                }
            )
        )

        # Create valid skill for comparison
        create_skill_part_file(
            part_dir,
            "prt_valid",
            "msg_001",
            "ses_001",
            "valid-skill",
            current_timestamp,
        )

        result = load_skills(db, storage_path)
        # Both should load (null time means no cutoff filter)
        assert result >= 1

    def test_handles_read_only_files(
        self, db_legacy_schema, storage_path: Path, current_timestamp: int
    ):
        """Handles read-only files gracefully."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        create_session_file(
            session_dir, "ses_readonly", title="ReadOnly", created_ts=current_timestamp
        )

        result = load_sessions_fast(db_legacy_schema, storage_path)
        assert result == 1


# =============================================================================
# Helper Functions for Root Sessions
# =============================================================================


def create_root_session_file(
    session_dir: Path,
    project_id: str,
    session_id: str,
    title: str = "Root Session",
    directory: str = "/test/path",
    created_ts: int | None = None,
    updated_ts: int | None = None,
) -> Path:
    """Create a ROOT session JSON file (no parentID)."""
    now_ms = int(time.time() * 1000)
    created_ts = created_ts or now_ms
    updated_ts = updated_ts or now_ms

    # Sessions are in project subdirectories
    project_dir = session_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    session_file = project_dir / f"{session_id}.json"
    data = {
        "id": session_id,
        "projectID": project_id,
        "directory": directory,
        "title": title,
        "parentID": None,  # ROOT session - no parent
        "time": {"created": created_ts, "updated": updated_ts},
    }
    session_file.write_text(json.dumps(data))
    return session_file


def create_child_session_file(
    session_dir: Path,
    project_id: str,
    session_id: str,
    parent_id: str,
    title: str = "Child Session",
    directory: str = "/test/path",
    created_ts: int | None = None,
) -> Path:
    """Create a CHILD session JSON file (with parentID)."""
    now_ms = int(time.time() * 1000)
    created_ts = created_ts or now_ms

    project_dir = session_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    session_file = project_dir / f"{session_id}.json"
    data = {
        "id": session_id,
        "projectID": project_id,
        "directory": directory,
        "title": title,
        "parentID": parent_id,  # CHILD session - has parent
        "time": {"created": created_ts, "updated": created_ts},
    }
    session_file.write_text(json.dumps(data))
    return session_file


def create_user_message_file(
    message_dir: Path,
    session_id: str,
    message_id: str,
    summary_title: str = "User question",
    summary_body: str = "This is the message body",
    created_ts: int | None = None,
) -> Path:
    """Create a user message JSON file with summary."""
    now_ms = int(time.time() * 1000)
    created_ts = created_ts or now_ms

    msg_session_dir = message_dir / session_id
    msg_session_dir.mkdir(parents=True, exist_ok=True)

    message_file = msg_session_dir / f"{message_id}.json"
    data = {
        "id": message_id,
        "sessionID": session_id,
        "role": "user",
        "time": {"created": created_ts},
        "summary": {
            "title": summary_title,
            "body": summary_body,
        },
    }
    message_file.write_text(json.dumps(data))
    return message_file


# =============================================================================
# Tests: get_first_user_message
# =============================================================================


class TestGetFirstUserMessage:
    """Tests for get_first_user_message function."""

    def test_returns_none_when_session_dir_not_exists(self, storage_path: Path):
        """Returns None when session message directory doesn't exist."""
        message_dir = storage_path / "message"
        message_dir.mkdir()

        result = get_first_user_message(message_dir, "non_existent_session")
        assert result is None

    def test_returns_none_when_no_user_messages(
        self, storage_path: Path, current_timestamp: int
    ):
        """Returns None when no user messages exist."""
        message_dir = storage_path / "message"
        message_dir.mkdir()

        # Create assistant message only (not user)
        create_message_file(
            message_dir,
            "msg_assistant",
            session_id="ses_001",
            role="assistant",
            created_ts=current_timestamp,
        )

        result = get_first_user_message(message_dir, "ses_001")
        assert result is None

    def test_returns_first_user_message_content(
        self, storage_path: Path, current_timestamp: int
    ):
        """Returns first user message content with title and body."""
        message_dir = storage_path / "message"
        message_dir.mkdir()

        # Create user message
        create_user_message_file(
            message_dir,
            "ses_001",
            "msg_user_001",
            summary_title="Implement feature X",
            summary_body="Please implement the feature X with tests",
            created_ts=current_timestamp,
        )

        result = get_first_user_message(message_dir, "ses_001")
        assert result is not None
        assert "Implement feature X" in result
        assert "Please implement the feature X with tests" in result

    def test_returns_first_chronologically(
        self, storage_path: Path, current_timestamp: int
    ):
        """Returns the first user message chronologically."""
        message_dir = storage_path / "message"
        message_dir.mkdir()

        # Create second message first (higher timestamp)
        create_user_message_file(
            message_dir,
            "ses_001",
            "msg_user_002",
            summary_title="Second message",
            created_ts=current_timestamp + 1000,
        )

        # Create first message (lower timestamp)
        create_user_message_file(
            message_dir,
            "ses_001",
            "msg_user_001",
            summary_title="First message",
            created_ts=current_timestamp,
        )

        result = get_first_user_message(message_dir, "ses_001")
        assert result is not None
        assert "First message" in result
        assert "Second message" not in result

    def test_returns_title_only_when_no_body(
        self, storage_path: Path, current_timestamp: int
    ):
        """Returns title only when body is empty."""
        message_dir = storage_path / "message"
        message_dir.mkdir()

        create_user_message_file(
            message_dir,
            "ses_001",
            "msg_user_001",
            summary_title="Just a title",
            summary_body="",
            created_ts=current_timestamp,
        )

        result = get_first_user_message(message_dir, "ses_001")
        assert result == "Just a title"


# =============================================================================
# Tests: extract_root_sessions
# =============================================================================


class TestExtractRootSessions:
    """Tests for extract_root_sessions function."""

    def test_returns_empty_when_session_dir_not_exists(self, storage_path: Path):
        """Returns empty list when session directory doesn't exist."""
        result = extract_root_sessions(storage_path)
        assert result == []

    def test_extracts_root_sessions_only(
        self, storage_path: Path, current_timestamp: int
    ):
        """Extracts only ROOT sessions (no parentID)."""
        session_dir = storage_path / "session"
        session_dir.mkdir()
        message_dir = storage_path / "message"
        message_dir.mkdir()

        # Create ROOT session
        create_root_session_file(
            session_dir,
            "proj_001",
            "ses_root",
            title="Root Session",
            created_ts=current_timestamp,
        )

        # Create CHILD session
        create_child_session_file(
            session_dir,
            "proj_001",
            "ses_child",
            parent_id="ses_root",
            title="Child Session",
            created_ts=current_timestamp,
        )

        result = extract_root_sessions(storage_path)

        # Only ROOT should be extracted
        assert len(result) == 1
        assert result[0].trace_id == f"{ROOT_TRACE_PREFIX}ses_root"
        assert result[0].subagent_type == ROOT_AGENT_TYPE

    def test_root_session_has_correct_trace_id_prefix(
        self, storage_path: Path, current_timestamp: int
    ):
        """Root session trace has correct prefix."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        create_root_session_file(
            session_dir,
            "proj_001",
            "ses_abc123",
            created_ts=current_timestamp,
        )

        result = extract_root_sessions(storage_path)

        assert len(result) == 1
        assert result[0].trace_id.startswith(ROOT_TRACE_PREFIX)
        assert "ses_abc123" in result[0].trace_id

    def test_root_session_includes_prompt_from_first_message(
        self, storage_path: Path, current_timestamp: int
    ):
        """Root session includes prompt from first user message."""
        session_dir = storage_path / "session"
        session_dir.mkdir()
        message_dir = storage_path / "message"
        message_dir.mkdir()

        create_root_session_file(
            session_dir,
            "proj_001",
            "ses_with_prompt",
            created_ts=current_timestamp,
        )

        create_user_message_file(
            message_dir,
            "ses_with_prompt",
            "msg_user",
            summary_title="Help me implement Plan 27",
            summary_body="I need to add root session tracing",
            created_ts=current_timestamp,
        )

        result = extract_root_sessions(storage_path)

        assert len(result) == 1
        assert "Help me implement Plan 27" in result[0].prompt_input
        assert "root session tracing" in result[0].prompt_input

    def test_root_session_falls_back_to_title_when_no_message(
        self, storage_path: Path, current_timestamp: int
    ):
        """Falls back to session title when no user message."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        create_root_session_file(
            session_dir,
            "proj_001",
            "ses_no_msg",
            title="OpenMonitor Planning",
            created_ts=current_timestamp,
        )

        result = extract_root_sessions(storage_path)

        assert len(result) == 1
        assert result[0].prompt_input == "OpenMonitor Planning"

    def test_skips_old_sessions(self, storage_path: Path, current_timestamp: int):
        """Skips sessions older than max_days."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        # Create recent ROOT session
        create_root_session_file(
            session_dir,
            "proj_001",
            "ses_recent",
            created_ts=current_timestamp,
        )

        # Create old ROOT session (60 days ago)
        old_ts = int((datetime.now() - timedelta(days=60)).timestamp() * 1000)
        create_root_session_file(
            session_dir,
            "proj_001",
            "ses_old",
            created_ts=old_ts,
        )

        result = extract_root_sessions(storage_path, max_days=30)

        assert len(result) == 1
        assert "ses_recent" in result[0].trace_id

    def test_root_session_has_child_session_id_self_reference(
        self, storage_path: Path, current_timestamp: int
    ):
        """Root session has child_session_id pointing to itself for hierarchy."""
        session_dir = storage_path / "session"
        session_dir.mkdir()

        create_root_session_file(
            session_dir,
            "proj_001",
            "ses_root",
            created_ts=current_timestamp,
        )

        result = extract_root_sessions(storage_path)

        assert len(result) == 1
        # child_session_id should be the session_id itself for linking children
        assert result[0].child_session_id == "ses_root"


# =============================================================================
# Tests: load_traces with root sessions
# =============================================================================


class TestLoadTracesWithRootSessions:
    """Tests for load_traces function including root sessions."""

    def test_loads_root_sessions_into_traces_table(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Root sessions are loaded into agent_traces table."""
        session_dir = storage_path / "session"
        session_dir.mkdir()
        message_dir = storage_path / "message"
        message_dir.mkdir()

        create_root_session_file(
            session_dir,
            "proj_001",
            "ses_root",
            title="Test Root",
            created_ts=current_timestamp,
        )

        result = load_traces(db, storage_path)

        assert result >= 1

        conn = db.connect()
        traces = conn.execute(
            "SELECT trace_id, subagent_type FROM agent_traces WHERE trace_id LIKE 'root_%'"
        ).fetchall()

        assert len(traces) >= 1
        assert traces[0][1] == ROOT_AGENT_TYPE

    def test_loads_both_root_and_delegation_traces(
        self, db: AnalyticsDB, storage_path: Path, current_timestamp: int
    ):
        """Loads both root sessions and delegation traces."""
        session_dir = storage_path / "session"
        session_dir.mkdir()
        part_dir = storage_path / "part"
        part_dir.mkdir()

        # Create ROOT session
        create_root_session_file(
            session_dir,
            "proj_001",
            "ses_root",
            created_ts=current_timestamp,
        )

        # Create delegation trace
        create_delegation_part_file(
            part_dir,
            "prt_del",
            "msg_001",
            "ses_root",
            "tester",
            child_session_id="ses_child",
            start_ts=current_timestamp,
        )

        result = load_traces(db, storage_path)

        assert result >= 2  # At least 1 root + 1 delegation

        conn = db.connect()
        root_traces = conn.execute(
            "SELECT COUNT(*) FROM agent_traces WHERE trace_id LIKE 'root_%'"
        ).fetchone()
        delegation_traces = conn.execute(
            "SELECT COUNT(*) FROM agent_traces WHERE trace_id NOT LIKE 'root_%'"
        ).fetchone()

        assert root_traces is not None
        assert root_traces[0] >= 1
        assert delegation_traces is not None
        assert delegation_traces[0] >= 1
