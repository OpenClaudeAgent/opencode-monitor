"""
Route Context - Shared dependencies for API routes.

This module provides access to shared resources (db_lock, service getter)
that are initialized by the main server.

IMPORTANT: Uses the global db_access_lock from analytics.db module to ensure
all database access (indexer + API) is properly serialized.
"""

import threading
from typing import Callable, Optional

from ...analytics import TracingDataService, get_db_access_lock


class RouteContext:
    """Singleton holding shared dependencies for routes."""

    _instance: Optional["RouteContext"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._get_service: Optional[Callable[[], TracingDataService]] = None

    @classmethod
    def get_instance(cls) -> "RouteContext":
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def configure(
        self,
        db_lock: threading.Lock,  # Kept for API compatibility but ignored
        get_service: Callable[[], TracingDataService],
    ) -> None:
        """Configure the context with dependencies from the server.

        Note: db_lock parameter is ignored - we use the global lock from analytics.db
        """
        # db_lock ignored - using global get_db_access_lock() instead
        self._get_service = get_service

    def get_service(self) -> TracingDataService:
        """Get the tracing data service."""
        if self._get_service is None:
            raise RuntimeError("RouteContext not configured - call configure() first")
        return self._get_service()


# Convenience functions for routes
def get_context() -> RouteContext:
    """Get the route context singleton."""
    return RouteContext.get_instance()


def get_db_lock() -> threading.Lock:
    """Get the global database access lock.

    Uses the global lock from analytics.db module to ensure ALL database access
    (both indexer and API) is properly serialized.
    """
    return get_db_access_lock()


def get_service() -> TracingDataService:
    """Get the tracing data service."""
    return get_context().get_service()
