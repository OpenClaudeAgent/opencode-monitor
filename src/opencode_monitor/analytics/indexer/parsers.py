"""
JSON parsers for OpenCode storage files.

Each parser validates and transforms raw JSON data into database records.
Handles all file types: session, message, part, todo, project.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ...utils.datetime import ms_to_datetime
from ...utils.logger import debug


@dataclass
class ParsedSession:
    """Parsed session data ready for database insertion."""

    id: str
    project_id: Optional[str]
    directory: Optional[str]
    title: Optional[str]
    parent_id: Optional[str]
    version: Optional[str]
    additions: int
    deletions: int
    files_changed: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@dataclass
class ParsedMessage:
    """Parsed message data ready for database insertion."""

    id: str
    session_id: Optional[str]
    parent_id: Optional[str]
    role: Optional[str]
    agent: Optional[str]
    model_id: Optional[str]
    provider_id: Optional[str]
    mode: Optional[str]
    cost: float
    finish_reason: Optional[str]
    working_dir: Optional[str]
    tokens_input: int
    tokens_output: int
    tokens_reasoning: int
    tokens_cache_read: int
    tokens_cache_write: int
    created_at: Optional[datetime]
    completed_at: Optional[datetime]


@dataclass
class ParsedPart:
    """Parsed part data ready for database insertion."""

    id: str
    session_id: Optional[str]
    message_id: Optional[str]
    part_type: str
    content: Optional[str]  # For text parts
    tool_name: Optional[str]  # For tool parts
    tool_status: Optional[str]
    call_id: Optional[str]
    arguments: Optional[str]  # JSON string
    created_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_ms: Optional[int]
    error_message: Optional[str]


@dataclass
class ParsedDelegation:
    """Parsed delegation (task tool) data."""

    id: str
    message_id: Optional[str]
    session_id: Optional[str]
    parent_agent: Optional[str]  # Resolved later from message
    child_agent: str
    child_session_id: Optional[str]
    created_at: Optional[datetime]


@dataclass
class ParsedSkill:
    """Parsed skill usage data."""

    id: str
    message_id: Optional[str]
    session_id: Optional[str]
    skill_name: str
    loaded_at: Optional[datetime]


@dataclass
class ParsedTodo:
    """Parsed todo item data."""

    id: str
    session_id: str
    content: Optional[str]
    status: Optional[str]
    priority: Optional[str]
    position: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@dataclass
class ParsedProject:
    """Parsed project data."""

    id: str
    worktree: Optional[str]
    vcs: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@dataclass
class ParsedFileOperation:
    """Parsed file operation from read/write/edit tools."""

    id: str
    session_id: Optional[str]
    trace_id: Optional[str]
    operation: str  # read, write, edit
    file_path: str
    timestamp: Optional[datetime]
    risk_level: str
    risk_reason: Optional[str]


class FileParser:
    """Unified parser for all OpenCode storage file types.

    Extracts and validates data from JSON files, returning typed dataclasses
    ready for database insertion.
    """

    @staticmethod
    def read_json(path: Path) -> Optional[Any]:
        """Read and parse a JSON file.

        Args:
            path: Path to the JSON file

        Returns:
            Parsed JSON data (dict or list), or None on error
        """
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            debug(f"[FileParser] Failed to read {path}: {e}")
            return None

    @staticmethod
    def parse_session(data: dict) -> Optional[ParsedSession]:
        """Parse a session JSON file.

        Args:
            data: Parsed JSON data

        Returns:
            ParsedSession or None if invalid
        """
        if not isinstance(data, dict) or not data.get("id"):
            return None

        time_data = data.get("time", {})
        summary = data.get("summary", {})

        return ParsedSession(
            id=data["id"],
            project_id=data.get("projectID"),
            directory=data.get("directory"),
            title=data.get("title"),
            parent_id=data.get("parentID"),
            version=data.get("version"),
            additions=summary.get("additions", 0),
            deletions=summary.get("deletions", 0),
            files_changed=summary.get("files", 0),
            created_at=ms_to_datetime(time_data.get("created")),
            updated_at=ms_to_datetime(time_data.get("updated")),
        )

    @staticmethod
    def parse_message(data: dict) -> Optional[ParsedMessage]:
        """Parse a message JSON file.

        Args:
            data: Parsed JSON data

        Returns:
            ParsedMessage or None if invalid
        """
        if not isinstance(data, dict) or not data.get("id"):
            return None

        time_data = data.get("time", {})
        tokens = data.get("tokens", {})
        cache = tokens.get("cache", {})
        path_data = data.get("path", {})

        return ParsedMessage(
            id=data["id"],
            session_id=data.get("sessionID"),
            parent_id=data.get("parentID"),
            role=data.get("role"),
            agent=data.get("agent"),
            model_id=data.get("modelID"),
            provider_id=data.get("providerID"),
            mode=data.get("mode"),
            cost=data.get("cost", 0) or 0,
            finish_reason=data.get("finish"),
            working_dir=path_data.get("cwd") if isinstance(path_data, dict) else None,
            tokens_input=tokens.get("input", 0) or 0,
            tokens_output=tokens.get("output", 0) or 0,
            tokens_reasoning=tokens.get("reasoning", 0) or 0,
            tokens_cache_read=cache.get("read", 0) or 0,
            tokens_cache_write=cache.get("write", 0) or 0,
            created_at=ms_to_datetime(time_data.get("created")),
            completed_at=ms_to_datetime(time_data.get("completed")),
        )

    @staticmethod
    def parse_part(data: dict) -> Optional[ParsedPart]:
        """Parse a part JSON file.

        Args:
            data: Parsed JSON data

        Returns:
            ParsedPart or None if invalid (non-tool parts are also None)
        """
        if not isinstance(data, dict) or not data.get("id"):
            return None

        part_type = data.get("type")
        if not part_type:
            return None

        time_data = data.get("time", {})
        state = data.get("state", {})
        start_time = time_data.get("start")
        end_time = time_data.get("end")

        # Calculate duration
        duration_ms = None
        if start_time and end_time:
            duration_ms = end_time - start_time

        # Extract content based on type
        content = None
        tool_name = None
        tool_status = None
        arguments = None
        error_message = None

        if part_type == "text":
            content = data.get("text")
        elif part_type == "tool":
            tool_name = data.get("tool")
            if not tool_name:
                return None
            tool_status = state.get("status") if isinstance(state, dict) else None
            tool_input = state.get("input", {}) if isinstance(state, dict) else {}
            arguments = json.dumps(tool_input) if tool_input else None
            error_message = state.get("error") if isinstance(state, dict) else None
        else:
            # Skip other types
            return None

        return ParsedPart(
            id=data["id"],
            session_id=data.get("sessionID"),
            message_id=data.get("messageID"),
            part_type=part_type,
            content=content,
            tool_name=tool_name,
            tool_status=tool_status,
            call_id=data.get("callID"),
            arguments=arguments,
            created_at=ms_to_datetime(start_time),
            ended_at=ms_to_datetime(end_time),
            duration_ms=duration_ms,
            error_message=error_message,
        )

    @staticmethod
    def parse_delegation(data: dict) -> Optional[ParsedDelegation]:
        """Parse a delegation from a task tool part.

        Args:
            data: Parsed JSON data from a part file

        Returns:
            ParsedDelegation or None if not a task tool
        """
        if data.get("tool") != "task":
            return None

        state = data.get("state", {})
        input_data = state.get("input", {}) if isinstance(state, dict) else {}
        subagent_type = input_data.get("subagent_type")

        if not subagent_type:
            return None

        time_data = data.get("time", {})
        metadata = state.get("metadata", {}) if isinstance(state, dict) else {}

        return ParsedDelegation(
            id=data.get("id", ""),
            message_id=data.get("messageID"),
            session_id=data.get("sessionID"),
            parent_agent=None,  # Resolved later from message
            child_agent=subagent_type,
            child_session_id=metadata.get("sessionId"),
            created_at=ms_to_datetime(time_data.get("start")),
        )

    @staticmethod
    def parse_skill(data: dict) -> Optional[ParsedSkill]:
        """Parse a skill usage from a skill tool part.

        Args:
            data: Parsed JSON data from a part file

        Returns:
            ParsedSkill or None if not a skill tool
        """
        if data.get("tool") != "skill":
            return None

        state = data.get("state", {})
        input_data = state.get("input", {}) if isinstance(state, dict) else {}
        skill_name = input_data.get("name")

        if not skill_name:
            return None

        time_data = data.get("time", {})

        return ParsedSkill(
            id=data.get("id", ""),
            message_id=data.get("messageID"),
            session_id=data.get("sessionID"),
            skill_name=skill_name,
            loaded_at=ms_to_datetime(time_data.get("start")),
        )

    @staticmethod
    def parse_file_operation(data: dict) -> Optional[ParsedFileOperation]:
        """Parse a file operation from read/write/edit tool parts.

        Args:
            data: Parsed JSON data from a part file

        Returns:
            ParsedFileOperation or None if not a file operation
        """
        tool_name = data.get("tool")
        if tool_name not in ("read", "write", "edit"):
            return None

        state = data.get("state", {})
        input_data = state.get("input", {}) if isinstance(state, dict) else {}

        # Extract file path from tool input
        file_path = input_data.get("filePath") or input_data.get("path")
        if not file_path:
            return None

        time_data = data.get("time", {})

        return ParsedFileOperation(
            id=data.get("id", ""),
            session_id=data.get("sessionID"),
            trace_id=None,  # Resolved later
            operation=tool_name,
            file_path=file_path,
            timestamp=ms_to_datetime(time_data.get("start")),
            risk_level="normal",
            risk_reason=None,
        )

    @staticmethod
    def parse_todos(
        session_id: str, data: list, file_mtime: datetime
    ) -> list[ParsedTodo]:
        """Parse todo items from a todo file.

        Args:
            session_id: Session ID (from filename)
            data: Parsed JSON data (list of todos)
            file_mtime: File modification time for timestamps

        Returns:
            List of ParsedTodo items
        """
        if not isinstance(data, list):
            return []

        todos: list[ParsedTodo] = []
        for index, todo in enumerate(data):
            if not isinstance(todo, dict):
                continue

            todo_id = f"{session_id}_{todo.get('id', index)}"
            todos.append(
                ParsedTodo(
                    id=todo_id,
                    session_id=session_id,
                    content=todo.get("content"),
                    status=todo.get("status"),
                    priority=todo.get("priority"),
                    position=index,
                    created_at=file_mtime,
                    updated_at=file_mtime,
                )
            )

        return todos

    @staticmethod
    def parse_project(data: dict) -> Optional[ParsedProject]:
        """Parse a project JSON file.

        Args:
            data: Parsed JSON data

        Returns:
            ParsedProject or None if invalid
        """
        if not isinstance(data, dict) or not data.get("id"):
            return None

        time_data = data.get("time", {})

        return ParsedProject(
            id=data["id"],
            worktree=data.get("worktree"),
            vcs=data.get("vcs"),
            created_at=ms_to_datetime(time_data.get("created")),
            updated_at=ms_to_datetime(time_data.get("updated")),
        )
