"""
Data factories for generating fake OpenCode JSON files for integration testing.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


class OpenCodeFactory:
    """Factory for generating OpenCode JSON artifacts."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.session_dir = base_dir / "session"
        self.message_dir = base_dir / "message"
        self.part_dir = base_dir / "part"

        # Ensure directories exist
        for d in [self.session_dir, self.message_dir, self.part_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        session_id: Optional[str] = None,
        title: str = "Test Session",
        created_at: float = None,
    ) -> Dict[str, Any]:
        """Create a session JSON file."""
        if not session_id:
            session_id = str(uuid.uuid4())

        if not created_at:
            created_at = time.time() * 1000

        data = {
            "id": session_id,
            "projectID": "proj_123",
            "directory": "/tmp/test",
            "title": title,
            "parentID": None,
            "version": "1.0.0",
            "summary": {"additions": 10, "deletions": 5, "files": 2},
            "time": {"created": created_at, "updated": created_at + 1000},
        }

        self._write_json(self.session_dir / f"{session_id}.json", data)
        return data

    def create_message(
        self,
        session_id: str,
        message_id: Optional[str] = None,
        role: str = "user",
        content: str = "Hello",
        parent_id: Optional[str] = None,
        created_at: float = None,
    ) -> Dict[str, Any]:
        """Create a message JSON file."""
        if not message_id:
            message_id = str(uuid.uuid4())

        if not created_at:
            created_at = time.time() * 1000

        data = {
            "id": message_id,
            "sessionID": session_id,
            "parentID": parent_id,
            "role": role,
            "agent": "general",
            "modelID": "claude-3-5-sonnet",
            "providerID": "anthropic",
            "mode": "chat",
            "cost": 0.001,
            "finishReason": "stop",
            "workingDir": "/tmp/test",
            "tokens": {
                "input": 100,
                "output": 50,
                "reasoning": 0,
                "cacheRead": 0,
                "cacheWrite": 0,
            },
            "time": {"created": created_at, "completed": created_at + 500},
        }

        self._write_json(self.message_dir / f"{message_id}.json", data)
        return data

    def create_part(
        self,
        session_id: str,
        message_id: str,
        part_type: str = "text",
        content: str = "Some content",
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict] = None,
        tool_status: str = "completed",
        error_message: Optional[str] = None,
        git_hash: Optional[str] = None,
        git_files: Optional[List[str]] = None,
        created_at: float = None,
    ) -> Dict[str, Any]:
        """Create a part JSON file."""
        part_id = str(uuid.uuid4())

        if not created_at:
            created_at = time.time() * 1000

        data = {
            "id": part_id,
            "sessionID": session_id,
            "messageID": message_id,
            "type": part_type,
            "text": content,
            "time": {"created": created_at, "ended": created_at + 100},
        }

        if part_type == "tool":
            data["tool"] = tool_name
            data["state"] = {
                "status": tool_status,
                "input": tool_args or {},
                "output": "Tool output",
                "time": {"start": created_at, "end": created_at + 100},
            }
            if error_message:
                data["state"]["error"] = error_message
                data["state"]["status"] = "error"

        if part_type == "patch":
            data["hash"] = git_hash or "abc1234"
            data["files"] = git_files or ["src/main.py"]
            data["time"] = {"start": created_at}

        self._write_json(self.part_dir / f"{part_id}.json", data)
        return data

    def _write_json(self, path: Path, data: Dict[str, Any]):
        """Write dictionary to JSON file."""
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
