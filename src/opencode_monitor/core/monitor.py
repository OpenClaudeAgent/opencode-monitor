"""
Instance detection and monitoring for OpenCode
"""

import asyncio
import json
import subprocess
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .models import Instance, Agent, Tool, SessionStatus, Todos, State, AgentTodos
from .client import OpenCodeClient, check_opencode_port
from ..utils.settings import get_settings


# --- Configuration constants ---
# Storage path for OpenCode session files (can be overridden for testing)
OPENCODE_STORAGE_PATH: Path = Path.home() / ".local/share/opencode/storage"


@dataclass
class AskUserResult:
    """Result of checking for pending ask_user notifications"""

    has_pending: bool
    title: str = ""
    question: str = ""
    options: list[str] = field(default_factory=list)
    repo: str = ""
    agent: str = ""
    branch: str = ""
    urgency: str = "normal"


async def find_opencode_ports() -> list[int]:
    """Find all ports with OpenCode instances running"""
    # Get all listening ports on localhost
    try:
        result = subprocess.run(
            ["netstat", "-an"], capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.split("\n")
    except Exception:
        return []

    # Extract ports from netstat output
    candidate_ports = set()
    for line in lines:
        if "127.0.0.1" in line and "LISTEN" in line:
            parts = line.split()
            for part in parts:
                if part.startswith("127.0.0.1."):
                    try:
                        port = int(part.split(".")[-1])
                        if 1024 < port < 65535:
                            candidate_ports.add(port)
                    except ValueError:
                        continue

    # Check each port in parallel
    check_tasks = [check_opencode_port(port) for port in candidate_ports]
    results = await asyncio.gather(*check_tasks)

    return [port for port, is_opencode in zip(candidate_ports, results) if is_opencode]


def get_tty_for_port(port: int) -> str:
    """Get the TTY associated with an OpenCode instance"""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            if "opencode" in line.lower() and "LISTEN" in line:
                parts = line.split()
                if len(parts) >= 2:
                    pid = parts[1]
                    # Get TTY from ps
                    ps_result = subprocess.run(
                        ["ps", "-o", "tty=", "-p", pid],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    tty = ps_result.stdout.strip()
                    if tty and tty != "??":
                        return tty
    except Exception:
        pass
    return ""


def _find_latest_notify_ask_user(
    message_dir: Path, part_dir: Path, cutoff_time: float
) -> tuple[int, dict, list[tuple[int, str, str]]]:
    """Scan messages for the latest notify_ask_user call.

    Args:
        message_dir: Directory containing message files
        part_dir: Directory containing part files
        cutoff_time: Only consider files modified after this timestamp

    Returns:
        (notify_timestamp, notify_input, recent_messages)
        where notify_input is the full input dict from the notify_ask_user call
        and recent_messages is a list of (msg_time, msg_id, role)
    """
    notify_timestamp = 0
    notify_input: dict = {}
    recent_messages: list[tuple[int, str, str]] = []

    for msg_file in message_dir.glob("msg_*.json"):
        # Skip files older than cutoff (fast mtime check, no file read)
        if msg_file.stat().st_mtime < cutoff_time:
            continue

        try:
            data = json.loads(msg_file.read_text())
        except (json.JSONDecodeError, IOError):
            continue

        msg_id = data.get("id", "")
        msg_time = data.get("time", {}).get("created", 0)
        role = data.get("role", "")
        recent_messages.append((msg_time, msg_id, role))

        # Check part files for notify_ask_user
        msg_part_dir = part_dir / msg_id
        if not msg_part_dir.exists():
            continue

        for prt_file in msg_part_dir.glob("prt_*.json"):
            if prt_file.stat().st_mtime < cutoff_time:
                continue

            try:
                part_data = json.loads(prt_file.read_text())
            except (json.JSONDecodeError, IOError):
                continue

            if (
                part_data.get("type") == "tool"
                and part_data.get("tool") == "notify_ask_user"
                and part_data.get("state", {}).get("status") == "completed"
            ):
                part_time = (
                    part_data.get("state", {}).get("time", {}).get("start", msg_time)
                )
                if part_time > notify_timestamp:
                    notify_timestamp = part_time
                    notify_input = part_data.get("state", {}).get("input", {})

    return notify_timestamp, notify_input, recent_messages


def _has_activity_after_notify(
    notify_timestamp: int,
    recent_messages: list[tuple[int, str, str]],
    part_dir: Path,
) -> bool:
    """Check if there's user activity after the notify_ask_user call.

    Returns True if user has responded (user message or other tool call found).
    """
    for msg_time, msg_id, role in recent_messages:
        if msg_time <= notify_timestamp:
            continue

        # User message after notify = user responded
        if role == "user":
            return True

        # Check for non-notify tool calls (indicates agent resumed)
        msg_part_dir = part_dir / msg_id
        if not msg_part_dir.exists():
            continue

        for prt_file in msg_part_dir.glob("prt_*.json"):
            try:
                part_data = json.loads(prt_file.read_text())
            except (json.JSONDecodeError, IOError):
                continue

            if part_data.get("type") == "tool":
                tool_name = part_data.get("tool", "")
                if tool_name and tool_name != "notify_ask_user":
                    return True

    return False


def check_pending_ask_user_from_disk(
    session_id: str,
    storage_path: Optional[Path] = None,
) -> AskUserResult:
    """Check if there's a pending notify_ask_user by scanning RECENT session files.

    Optimized for performance:
    - Only scans files modified within the time threshold (using file mtime)
    - Skips old files without reading their content
    - Returns quickly if no recent activity

    Note: Zombie sessions are filtered by the port cache mechanism in app.py,
    not by this function. This function only checks for pending ask_user
    notifications within the configured timeout.

    Args:
        session_id: The session ID to check
        storage_path: Override for OPENCODE_STORAGE_PATH (useful for testing)

    Returns:
        AskUserResult with has_pending and all ask_user fields
    """
    storage = storage_path or OPENCODE_STORAGE_PATH
    message_dir = storage / "message" / session_id
    part_dir = storage / "part"

    if not message_dir.exists():
        return AskUserResult(has_pending=False)

    # Use configured timeout
    settings = get_settings()
    cutoff_time = time.time() - settings.ask_user_timeout

    try:
        notify_timestamp, notify_input, recent_messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )
    except Exception:
        return AskUserResult(has_pending=False)

    # No recent notify_ask_user found
    if notify_timestamp == 0:
        return AskUserResult(has_pending=False)

    # Check if user has responded
    if _has_activity_after_notify(notify_timestamp, recent_messages, part_dir):
        return AskUserResult(has_pending=False)

    # notify_ask_user found with no activity after → pending
    # Extract all fields from input
    return AskUserResult(
        has_pending=True,
        title=notify_input.get("title", ""),
        question=notify_input.get("question", ""),
        options=notify_input.get("options", []) or [],
        repo=notify_input.get("repo", ""),
        agent=notify_input.get("agent", ""),
        branch=notify_input.get("branch", ""),
        urgency=notify_input.get("urgency", "normal"),
    )


def extract_tools_from_messages(messages: Optional[list]) -> list[Tool]:
    """Extract running tools from message data.

    Also calculates elapsed_ms for permission detection heuristic.
    """
    tools = []

    if not messages or not isinstance(messages, list) or len(messages) == 0:
        return tools

    now_ms = int(time.time() * 1000)
    parts = messages[0].get("parts", [])

    for part in parts:
        if part.get("type") == "tool":
            state = part.get("state", {})
            if state.get("status") == "running":
                tool_name = part.get("tool", "unknown")
                inp = state.get("input", {}) or {}

                # Extract argument based on tool type
                arg = (
                    state.get("title")
                    or inp.get("command")
                    or inp.get("filePath")
                    or inp.get("description")
                    or inp.get("pattern")
                    or (inp.get("prompt", "")[:50] if inp.get("prompt") else "")
                    or ""
                )

                # Calculate elapsed time for permission detection
                start_time = state.get("time", {}).get("start")
                elapsed_ms = 0
                if start_time is not None:
                    elapsed_ms = max(0, now_ms - start_time)

                tools.append(Tool(name=tool_name, arg=arg, elapsed_ms=elapsed_ms))

    return tools


def count_todos(todos: Optional[list]) -> tuple[int, int, str, str]:
    """Count pending and in_progress todos, return labels"""
    pending = 0
    in_progress = 0
    current_label = ""
    next_label = ""

    if not todos or not isinstance(todos, list):
        return pending, in_progress, current_label, next_label

    for todo in todos:
        status = todo.get("status", "")
        content = todo.get("content", "")
        if status == "pending":
            pending += 1
            if not next_label:  # First pending
                next_label = content
        elif status == "in_progress":
            in_progress += 1
            if not current_label:  # First in_progress
                current_label = content

    return pending, in_progress, current_label, next_label


async def fetch_instance(port: int) -> tuple[Optional[Instance], int, int, list, set]:
    """Fetch all data for an OpenCode instance
    Returns: (Instance, pending_todos, in_progress_todos, idle_candidates, busy_session_ids)
    """
    client = OpenCodeClient(port)

    # Get TTY first (sync call, but fast) - instance exists if we can get TTY
    tty = get_tty_for_port(port)

    # Get busy sessions status and all sessions
    busy_status, all_sessions = await asyncio.gather(
        client.get_status(),
        client.get_all_sessions(),
    )
    busy_status = busy_status or {}
    all_sessions = all_sessions or []

    # Build set of busy session IDs
    busy_session_ids = set(busy_status.keys())

    # Find idle sessions (in all_sessions but not in busy_status)
    idle_sessions = [
        s for s in all_sessions if s.get("id") and s.get("id") not in busy_session_ids
    ]

    # If no sessions at all, return empty instance
    if not busy_status and not idle_sessions:
        return Instance(port=port, tty=tty, agents=[]), 0, 0, [], set()

    agents = []
    total_pending = 0
    total_in_progress = 0

    # Process busy sessions (full data fetch)
    if busy_status:
        session_ids = list(busy_status.keys())
        session_data_tasks = [client.fetch_session_data(sid) for sid in session_ids]
        session_data_list = await asyncio.gather(*session_data_tasks)

        for session_id, session_data in zip(session_ids, session_data_list):
            info = session_data.get("info", {}) or {}
            messages = session_data.get("messages")
            todos = session_data.get("todos")

            title = info.get("title", "Sans titre")
            full_dir = info.get("directory", "")
            short_dir = os.path.basename(full_dir) if full_dir else "global"
            parent_id = info.get("parentID")

            # Extract tools
            tools = extract_tools_from_messages(messages)

            # Count todos and get labels
            pending, in_progress, current_label, next_label = count_todos(todos)
            total_pending += pending
            total_in_progress += in_progress
            agent_todos = AgentTodos(
                pending=pending,
                in_progress=in_progress,
                current_label=current_label,
                next_label=next_label,
            )

            agent = Agent(
                id=session_id,
                title=title,
                dir=short_dir,
                full_dir=full_dir,
                status=SessionStatus.BUSY,
                tools=tools,
                todos=agent_todos,
                parent_id=parent_id,
            )
            agents.append(agent)

    # Collect idle sessions info for later processing (after we know all busy sessions)
    idle_candidates = []
    for session_info in idle_sessions:
        session_id = session_info.get("id", "")
        parent_id = session_info.get("parentID")

        # Skip sub-agents - they don't use MCP Notify
        if parent_id is not None:
            continue

        idle_candidates.append(session_info)

    return (
        Instance(port=port, tty=tty, agents=agents),
        total_pending,
        total_in_progress,
        idle_candidates,  # Return idle candidates for post-processing
        busy_session_ids,  # Return busy session IDs for cross-checking
    )


async def fetch_all_instances(known_active_sessions: Optional[set] = None) -> State:
    """Fetch state for all OpenCode instances

    Args:
        known_active_sessions: Optional set of session IDs we've seen as BUSY before.
                              Used to filter out zombie sessions with pending ask_user.
                              If None, all sessions with pending ask_user are shown.
    """
    # Find all ports
    ports = await find_opencode_ports()

    if not ports:
        return State(connected=False)

    # Fetch all instances in parallel
    instance_tasks = [fetch_instance(port) for port in ports]
    results = await asyncio.gather(*instance_tasks)

    # First pass: collect ALL busy session IDs across all ports
    # This is used to distinguish zombie sessions from active ones
    all_busy_session_ids: set[str] = set()
    for instance, _, _, _, busy_ids in results:
        if instance is not None:
            all_busy_session_ids.update(busy_ids)

    # Second pass: process results and handle idle sessions with ask_user
    seen_session_ids: set[str] = set()
    instances = []
    total_pending = 0
    total_in_progress = 0

    for instance, pending, in_progress, idle_candidates, _ in results:
        if instance is None:
            continue

        # Start with busy agents
        all_agents = list(instance.agents)

        # Process idle candidates: check for pending ask_user
        for session_info in idle_candidates:
            session_id = session_info.get("id", "")

            # Skip if already seen (deduplication)
            if session_id in seen_session_ids:
                continue

            # Skip zombie sessions: if we have a cache and this session was never seen as BUSY
            if (
                known_active_sessions is not None
                and session_id not in known_active_sessions
            ):
                # Session was never seen as BUSY - it's from a dead instance
                continue

            # Check for pending ask_user (with configured timeout)
            ask_user_result = check_pending_ask_user_from_disk(session_id)

            if ask_user_result.has_pending:
                title = session_info.get("title", "Sans titre")
                full_dir = session_info.get("directory", "")
                short_dir = os.path.basename(full_dir) if full_dir else "global"

                agent = Agent(
                    id=session_id,
                    title=title,
                    dir=short_dir,
                    full_dir=full_dir,
                    status=SessionStatus.IDLE,
                    tools=[],
                    todos=AgentTodos(),
                    parent_id=None,
                    has_pending_ask_user=True,
                    ask_user_title=ask_user_result.title,
                    ask_user_question=ask_user_result.question,
                    ask_user_options=ask_user_result.options,
                    ask_user_repo=ask_user_result.repo,
                    ask_user_agent=ask_user_result.agent,
                    ask_user_branch=ask_user_result.branch,
                    ask_user_urgency=ask_user_result.urgency,
                )
                all_agents.append(agent)

        # Filter out duplicate agents (keep first occurrence)
        unique_agents = []
        for agent in all_agents:
            if agent.id not in seen_session_ids:
                seen_session_ids.add(agent.id)
                unique_agents.append(agent)

        # Update instance with final agent list
        instance = Instance(
            port=instance.port,
            tty=instance.tty,
            agents=unique_agents,
        )

        instances.append(instance)
        total_pending += pending
        total_in_progress += in_progress

    if not instances:
        return State(connected=False)

    return State(
        instances=instances,
        todos=Todos(pending=total_pending, in_progress=total_in_progress),
        connected=True,
    )
