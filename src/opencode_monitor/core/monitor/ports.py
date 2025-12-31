"""
Port detection for OpenCode instances.

Functions to find OpenCode ports and associated TTY.
"""

import asyncio
import subprocess

from ..client import check_opencode_port


async def find_opencode_ports() -> list[int]:
    """Find all ports with OpenCode instances running"""
    # Get all listening ports on localhost
    try:
        result = subprocess.run(
            ["netstat", "-an"], capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.split("\n")
    except Exception:  # Intentional catch-all: subprocess failures return empty list
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
    except Exception:  # Intentional catch-all: TTY detection is best-effort
        pass
    return ""
