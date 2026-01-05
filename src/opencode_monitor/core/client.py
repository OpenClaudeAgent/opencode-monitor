"""
Async HTTP client using asyncio + ThreadPoolExecutor
No external dependencies - uses stdlib only
"""

import asyncio
import json
import re
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Any


# Timeout for HTTP requests (seconds)
REQUEST_TIMEOUT = 2

# Thread pool for parallel HTTP requests
# Reduced from 20 to 4 to avoid thread contention
_executor = ThreadPoolExecutor(max_workers=4)


def _clean_json(raw: str) -> str:
    """Clean control characters from JSON response"""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", raw)


def _sync_get(url: str, timeout: float = REQUEST_TIMEOUT) -> Optional[str]:
    """Synchronous HTTP GET request"""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except urllib.error.URLError:
        return None
    except Exception:  # Intentional catch-all: any network error returns None
        return None


def _sync_get_json(url: str, timeout: float = REQUEST_TIMEOUT) -> Optional[Any]:
    """Synchronous HTTP GET request returning parsed JSON"""
    raw = _sync_get(url, timeout)
    if raw is None:
        return None
    try:
        cleaned = _clean_json(raw)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


async def get(url: str, timeout: float = REQUEST_TIMEOUT) -> Optional[str]:
    """Async HTTP GET request"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _sync_get, url, timeout)


async def get_json(url: str, timeout: float = REQUEST_TIMEOUT) -> Optional[Any]:
    """Async HTTP GET request returning parsed JSON"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _sync_get_json, url, timeout)


async def check_opencode_port(port: int) -> bool:
    """Check if a port is running an OpenCode instance"""
    url = f"http://127.0.0.1:{port}/session/status"
    try:
        result = await get(url, timeout=0.5)
        if result is None:
            return False
        # OpenCode returns {} or {"ses_xxx": {...}}
        return result == "{}" or result.startswith('{"ses_')
    except Exception:  # Intentional catch-all: port check failures return False
        return False


async def parallel_requests(
    urls: list[str], timeout: float = REQUEST_TIMEOUT
) -> list[Optional[Any]]:
    """Execute multiple HTTP requests in parallel"""
    tasks = [get_json(url, timeout) for url in urls]
    return await asyncio.gather(*tasks)


class OpenCodeClient:
    """Client for OpenCode API"""

    def __init__(self, port: int):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"

    async def get_status(self) -> Optional[dict]:
        """Get session status for busy sessions only"""
        return await get_json(f"{self.base_url}/session/status")

    async def get_all_sessions(self) -> Optional[list]:
        """Get all sessions (including idle ones)"""
        return await get_json(f"{self.base_url}/session")

    async def get_session_info(self, session_id: str) -> Optional[dict]:
        """Get info for a specific session"""
        return await get_json(f"{self.base_url}/session/{session_id}")

    async def get_session_messages(
        self, session_id: str, limit: int = 1
    ) -> Optional[list]:
        """Get recent messages for a session"""
        return await get_json(
            f"{self.base_url}/session/{session_id}/message?limit={limit}"
        )

    async def get_session_todos(self, session_id: str) -> Optional[list]:
        """Get todos for a session"""
        return await get_json(f"{self.base_url}/session/{session_id}/todo")

    async def fetch_session_data(self, session_id: str) -> dict:
        """Fetch all data for a session in parallel"""
        info_task = self.get_session_info(session_id)
        messages_task = self.get_session_messages(session_id, limit=1)
        todos_task = self.get_session_todos(session_id)

        info, messages, todos = await asyncio.gather(
            info_task, messages_task, todos_task
        )

        return {"info": info, "messages": messages, "todos": todos}
