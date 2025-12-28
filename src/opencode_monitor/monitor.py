"""
Instance detection and monitoring for OpenCode
"""

import asyncio
import subprocess
import os
from typing import Optional

from .models import Instance, Agent, Tool, SessionStatus, Todos, State, AgentTodos
from .client import OpenCodeClient, check_opencode_port


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


def extract_tools_from_messages(messages: Optional[list]) -> list[Tool]:
    """Extract running tools from message data"""
    tools = []

    if not messages or not isinstance(messages, list) or len(messages) == 0:
        return tools

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

                tools.append(Tool(name=tool_name, arg=arg))

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


async def fetch_instance(port: int) -> tuple[Optional[Instance], int, int]:
    """Fetch all data for an OpenCode instance
    Returns: (Instance, pending_todos, in_progress_todos)
    """
    client = OpenCodeClient(port)

    # Get TTY first (sync call, but fast) - instance exists if we can get TTY
    tty = get_tty_for_port(port)

    # Get busy sessions status
    busy_status = await client.get_status()
    busy_status = busy_status or {}

    # If no busy sessions, return instance with no agents (but instance still exists!)
    if not busy_status:
        return Instance(port=port, tty=tty, agents=[]), 0, 0

    # Fetch data for busy sessions only
    session_ids = list(busy_status.keys())
    session_data_tasks = [client.fetch_session_data(sid) for sid in session_ids]
    session_data_list = await asyncio.gather(*session_data_tasks)

    agents = []
    total_pending = 0
    total_in_progress = 0

    for session_id, session_data in zip(session_ids, session_data_list):
        # All sessions here are busy (we only fetch busy ones)
        session_status = busy_status.get(session_id, {}).get("type", "busy")

        info = session_data.get("info", {}) or {}
        messages = session_data.get("messages")
        todos = session_data.get("todos")

        title = info.get("title", "Sans titre")
        full_dir = info.get("directory", "")
        short_dir = os.path.basename(full_dir) if full_dir else "global"
        parent_id = info.get("parentID")  # Sub-agent parent reference

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
            status=SessionStatus.BUSY
            if session_status == "busy"
            else SessionStatus.IDLE,
            tools=tools,
            todos=agent_todos,
            parent_id=parent_id,
        )
        agents.append(agent)

    return Instance(port=port, tty=tty, agents=agents), total_pending, total_in_progress


async def fetch_all_instances() -> State:
    """Fetch state for all OpenCode instances"""
    # Find all ports
    ports = await find_opencode_ports()

    if not ports:
        return State(connected=False)

    # Fetch all instances in parallel
    instance_tasks = [fetch_instance(port) for port in ports]
    results = await asyncio.gather(*instance_tasks)

    # Process results (each is a tuple: Instance, pending, in_progress)
    instances = []
    total_pending = 0
    total_in_progress = 0

    for instance, pending, in_progress in results:
        if instance is None:
            continue
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
