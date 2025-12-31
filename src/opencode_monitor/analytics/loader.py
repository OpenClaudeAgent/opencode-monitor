"""
JSON data loader for OpenCode storage.

Uses DuckDB's native JSON reading for maximum performance.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .db import AnalyticsDB
from ..utils.logger import info, debug, error


def get_opencode_storage_path() -> Path:
    """Get the path to OpenCode storage directory."""
    return Path.home() / ".local" / "share" / "opencode" / "storage"


def load_sessions_fast(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load session data using DuckDB's JSON reader."""
    conn = db.connect()
    session_dir = storage_path / "session"

    if not session_dir.exists():
        return 0

    json_pattern = str(session_dir) + "/**/*.json"
    cutoff_ts = int((datetime.now() - timedelta(days=max_days)).timestamp() * 1000)

    try:
        conn.execute(f"""
            INSERT OR REPLACE INTO sessions
            SELECT
                id,
                projectID as project_id,
                directory,
                title,
                epoch_ms(time.created) as created_at,
                epoch_ms(time.updated) as updated_at
            FROM read_json_auto('{json_pattern}', 
                                maximum_object_size=50000000,
                                ignore_errors=true)
            WHERE id IS NOT NULL
              AND time.created >= {cutoff_ts}
        """)

        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        info(f"Loaded {count} sessions")
        return count
    except Exception as e:  # Intentional catch-all: DuckDB can raise various errors
        error(f"Session load failed: {e}")
        return 0


def load_messages_fast(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load message data using DuckDB's JSON reader."""
    conn = db.connect()
    message_dir = storage_path / "message"

    if not message_dir.exists():
        return 0

    json_pattern = str(message_dir) + "/**/*.json"
    cutoff_ts = int((datetime.now() - timedelta(days=max_days)).timestamp() * 1000)

    try:
        conn.execute(f"""
            INSERT OR REPLACE INTO messages
            SELECT
                id,
                sessionID as session_id,
                parentID as parent_id,
                role,
                agent,
                modelID as model_id,
                providerID as provider_id,
                COALESCE(tokens.input, 0) as tokens_input,
                COALESCE(tokens.output, 0) as tokens_output,
                COALESCE(tokens.reasoning, 0) as tokens_reasoning,
                COALESCE(tokens.cache.read, 0) as tokens_cache_read,
                COALESCE(tokens.cache.write, 0) as tokens_cache_write,
                epoch_ms(time.created) as created_at,
                epoch_ms(time.completed) as completed_at
            FROM read_json_auto('{json_pattern}', 
                                maximum_object_size=50000000,
                                ignore_errors=true)
            WHERE id IS NOT NULL
              AND time.created >= {cutoff_ts}
        """)

        count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        info(f"Loaded {count} messages")
        return count
    except Exception as e:  # Intentional catch-all: DuckDB can raise various errors
        error(f"Message load failed: {e}")
        return 0


def load_parts_fast(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load part data using DuckDB's JSON reader."""
    conn = db.connect()
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return 0

    json_pattern = str(part_dir) + "/**/*.json"

    try:
        # Load tool parts - type is 'tool' not 'tool-invocation'
        conn.execute(f"""
            INSERT OR REPLACE INTO parts
            SELECT
                id,
                messageID as message_id,
                type as part_type,
                tool as tool_name,
                state->>'status' as tool_status,
                epoch_ms(time.start) as created_at
            FROM read_json_auto('{json_pattern}', 
                                maximum_object_size=50000000,
                                union_by_name=true,
                                ignore_errors=true)
            WHERE id IS NOT NULL
              AND type = 'tool'
              AND tool IS NOT NULL
        """)

        count = conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
        info(f"Loaded {count} parts")
        return count
    except Exception as e:  # Intentional catch-all: DuckDB can raise various errors
        error(f"Parts load failed: {e}")
        return 0


def load_skills(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load skill usage from skill tool invocations."""
    conn = db.connect()
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=max_days)
    skill_id = 0
    skills = []

    for msg_dir in part_dir.iterdir():
        if not msg_dir.is_dir():
            continue

        for part_file in msg_dir.glob("*.json"):
            try:
                with open(part_file) as f:
                    data = json.load(f)

                if data.get("tool") != "skill":
                    continue

                state = data.get("state", {})
                skill_name = state.get("input", {}).get("name")
                if not skill_name:
                    continue

                time_data = data.get("time", {})
                start_ts = time_data.get("start")
                if start_ts:
                    loaded_at = datetime.fromtimestamp(start_ts / 1000)
                    if loaded_at < cutoff:
                        continue
                else:
                    loaded_at = None

                skill_id += 1
                skills.append(
                    {
                        "id": skill_id,
                        "message_id": data.get("messageID"),
                        "session_id": data.get("sessionID"),
                        "skill_name": skill_name,
                        "loaded_at": loaded_at,
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue

    if not skills:
        info("No skills found")
        return 0

    for s in skills:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO skills
                (id, message_id, session_id, skill_name, loaded_at)
                VALUES (?, ?, ?, ?, ?)""",
                [
                    s["id"],
                    s["message_id"],
                    s["session_id"],
                    s["skill_name"],
                    s["loaded_at"],
                ],
            )
        except Exception as e:  # Intentional catch-all: skip individual insert failures
            debug(f"Skill insert failed for {s.get('skill_name', 'unknown')}: {e}")
            continue

    count = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
    info(f"Loaded {count} skills")
    return count


def load_delegations(db: AnalyticsDB, storage_path: Path, max_days: int = 30) -> int:
    """Load agent delegations from task tool invocations."""
    conn = db.connect()
    part_dir = storage_path / "part"

    if not part_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=max_days)
    delegations = []

    for msg_dir in part_dir.iterdir():
        if not msg_dir.is_dir():
            continue

        for part_file in msg_dir.glob("*.json"):
            try:
                with open(part_file) as f:
                    data = json.load(f)

                if data.get("tool") != "task":
                    continue

                state = data.get("state", {})
                input_data = state.get("input", {})
                subagent_type = input_data.get("subagent_type")
                if not subagent_type:
                    continue

                time_data = state.get("time", {})
                created_ts = time_data.get("start")
                if created_ts:
                    created_at = datetime.fromtimestamp(created_ts / 1000)
                    if created_at < cutoff:
                        continue
                else:
                    created_at = None

                delegations.append(
                    {
                        "id": data.get("id"),
                        "message_id": data.get("messageID"),
                        "session_id": data.get("sessionID"),
                        "child_agent": subagent_type,
                        "child_session_id": state.get("metadata", {}).get("sessionId"),
                        "created_at": created_at,
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue

    if not delegations:
        info("No delegations found")
        return 0

    for d in delegations:
        try:
            parent_agent = conn.execute(
                "SELECT agent FROM messages WHERE id = ?", [d["message_id"]]
            ).fetchone()
            conn.execute(
                """INSERT OR REPLACE INTO delegations
                (id, message_id, session_id, parent_agent, child_agent, child_session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    d["id"],
                    d["message_id"],
                    d["session_id"],
                    parent_agent[0] if parent_agent else None,
                    d["child_agent"],
                    d["child_session_id"],
                    d["created_at"],
                ],
            )
        except Exception as e:  # Intentional catch-all: skip individual insert failures
            debug(f"Delegation insert failed for {d.get('id', 'unknown')}: {e}")
            continue

    count = conn.execute("SELECT COUNT(*) FROM delegations").fetchone()[0]
    info(f"Loaded {count} delegations")
    return count


def load_opencode_data(
    db: Optional[AnalyticsDB] = None,
    storage_path: Optional[Path] = None,
    clear_first: bool = True,
    max_days: int = 30,
    skip_parts: bool = True,
) -> dict:
    """Load OpenCode data into the analytics database.

    Uses DuckDB's native JSON reading for fast bulk loading.

    Args:
        db: Analytics database instance (creates new if not provided)
        storage_path: Path to OpenCode storage (uses default if not provided)
        clear_first: Whether to clear existing data before loading
        max_days: Only load data from the last N days (default 30)
        skip_parts: Skip loading parts (slow with many files), default True

    Returns:
        Dict with counts of loaded items
    """
    if db is None:
        db = AnalyticsDB()

    if storage_path is None:
        storage_path = get_opencode_storage_path()

    if not storage_path.exists():
        error(f"OpenCode storage not found: {storage_path}")
        return {"sessions": 0, "messages": 0, "parts": 0, "error": "Storage not found"}

    info(f"Loading OpenCode data (last {max_days} days)...")

    if clear_first:
        db.clear_data()

    sessions = load_sessions_fast(db, storage_path, max_days)
    messages = load_messages_fast(db, storage_path, max_days)

    # Parts loading is slow (can be 70k+ files) - skip by default
    if skip_parts:
        parts = 0
        info("Skipping parts (use skip_parts=False to load)")
    else:
        parts = load_parts_fast(db, storage_path, max_days)

    delegations = load_delegations(db, storage_path, max_days)
    skills = load_skills(db, storage_path, max_days)

    result = {
        "sessions": sessions,
        "messages": messages,
        "parts": parts,
        "delegations": delegations,
        "skills": skills,
    }

    info(
        f"Total: {sessions} sessions, {messages} messages, {parts} parts, {delegations} delegations, {skills} skills"
    )
    return result
