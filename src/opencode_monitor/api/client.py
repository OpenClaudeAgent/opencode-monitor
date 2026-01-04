"""
Analytics API Client - HTTP client for dashboard to access analytics data.

The dashboard uses this client instead of accessing DuckDB directly.
This solves DuckDB's multi-process concurrency limitations.
"""

import urllib.request
import urllib.error
import json
from typing import Optional

from ..utils.logger import debug, error
from .config import API_HOST, API_PORT, API_TIMEOUT


class AnalyticsAPIClient:
    """HTTP client for the Analytics API.

    Used by the dashboard to fetch data from the menubar's API server.
    Falls back gracefully if the API is not available.
    """

    def __init__(
        self, host: str = API_HOST, port: int = API_PORT, timeout: int = API_TIMEOUT
    ):
        """Initialize the API client.

        Args:
            host: API server host
            port: API server port
            timeout: Request timeout in seconds
        """
        self._base_url = f"http://{host}:{port}"
        self._timeout = timeout
        self._available: Optional[bool] = None

    def _request(self, endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
        """Make an HTTP GET request to the API.

        Args:
            endpoint: API endpoint (e.g., "/api/stats")
            params: Optional query parameters

        Returns:
            Response data dict, or None if request failed
        """
        url = f"{self._base_url}{endpoint}"

        # Add query parameters
        if params:
            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query_string}"

        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                data = json.loads(response.read().decode("utf-8"))

                if data.get("success"):
                    self._available = True
                    return data.get("data")
                else:
                    error(f"[API Client] Request failed: {data.get('error')}")
                    return None

        except urllib.error.URLError as e:
            # API not available (menubar not running)
            if self._available is not False:
                debug(f"[API Client] API not available: {e}")
            self._available = False
            return None
        except Exception as e:
            error(f"[API Client] Request error: {e}")
            return None

    @property
    def is_available(self) -> bool:
        """Check if the API is available.

        Always performs a health check to ensure current status.
        """
        return self.health_check()

    def health_check(self) -> bool:
        """Check if the API server is responding."""
        result = self._request("/api/health")
        return result is not None

    def get_stats(self) -> Optional[dict]:
        """Get database statistics."""
        return self._request("/api/stats")

    def get_global_stats(self, days: int = 30) -> Optional[dict]:
        """Get global statistics from TracingDataService.

        Args:
            days: Number of days to include

        Returns:
            Global stats dict or None
        """
        return self._request("/api/global-stats", {"days": days})

    def get_session_summary(self, session_id: str) -> Optional[dict]:
        """Get session summary.

        Args:
            session_id: Session ID

        Returns:
            Session summary dict or None
        """
        return self._request(f"/api/session/{session_id}/summary")

    def get_session_tokens(self, session_id: str) -> Optional[dict]:
        """Get session token details."""
        return self._request(f"/api/session/{session_id}/tokens")

    def get_session_tools(self, session_id: str) -> Optional[dict]:
        """Get session tool details."""
        return self._request(f"/api/session/{session_id}/tools")

    def get_session_files(self, session_id: str) -> Optional[dict]:
        """Get session file operations."""
        return self._request(f"/api/session/{session_id}/files")

    def get_session_agents(self, session_id: str) -> Optional[list]:
        """Get session agents."""
        return self._request(f"/api/session/{session_id}/agents")

    def get_session_timeline(self, session_id: str) -> Optional[list]:
        """Get session timeline events."""
        return self._request(f"/api/session/{session_id}/timeline")

    def get_session_prompts(self, session_id: str) -> Optional[dict]:
        """Get session prompts (first user prompt + last response)."""
        return self._request(f"/api/session/{session_id}/prompts")

    def get_session_messages(self, session_id: str) -> Optional[list]:
        """Get all messages with content for a session.

        Returns:
            List of message dicts with role, content, timestamp, etc.
        """
        return self._request(f"/api/session/{session_id}/messages")

    def get_session_operations(self, session_id: str) -> Optional[list]:
        """Get tool operations for a session (for tree display).

        Returns:
            List of operation dicts with tool_name, display_info, status, etc.
        """
        return self._request(f"/api/session/{session_id}/operations")

    def get_sessions(self, days: int = 30, limit: int = 100) -> Optional[list]:
        """Get list of sessions.

        Args:
            days: Number of days to include
            limit: Maximum number of sessions

        Returns:
            List of session dicts or None
        """
        return self._request("/api/sessions", {"days": days, "limit": limit})

    def get_traces(self, days: int = 30, limit: int = 500) -> Optional[list]:
        """Get agent traces.

        Args:
            days: Number of days to include
            limit: Maximum number of traces

        Returns:
            List of trace dicts or None
        """
        return self._request("/api/traces", {"days": days, "limit": limit})

    def get_delegations(self, days: int = 30, limit: int = 1000) -> Optional[list]:
        """Get agent delegations (parent-child session relationships).

        Args:
            days: Number of days to include
            limit: Maximum number of delegations

        Returns:
            List of delegation dicts or None
        """
        return self._request("/api/delegations", {"days": days, "limit": limit})

    def get_tracing_tree(self, days: int = 30) -> Optional[list]:
        """Get hierarchical tracing tree for dashboard display.

        Returns sessions with their child traces already structured
        as a tree. No client-side aggregation needed.

        Args:
            days: Number of days to include

        Returns:
            List of session nodes with children, or None
        """
        return self._request("/api/tracing/tree", {"days": days})

    def get_conversation(self, session_id: str) -> Optional[dict]:
        """Get full conversation timeline for a session.

        Returns hierarchical view: session → exchanges → parts.
        This is the main endpoint for detailed tracing view.

        Args:
            session_id: Session ID to fetch

        Returns:
            Conversation dict with session, exchanges, delegations, stats
        """
        return self._request(f"/api/tracing/conversation/{session_id}")


# Global client instance
_api_client: Optional[AnalyticsAPIClient] = None


def get_api_client() -> AnalyticsAPIClient:
    """Get or create the global API client instance."""
    global _api_client
    if _api_client is None:
        _api_client = AnalyticsAPIClient()
    return _api_client
