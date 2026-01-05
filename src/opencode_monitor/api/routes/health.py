"""
Health Check Routes - Health and sync status endpoints.

Note: Imports from analytics.indexer are kept inline (lazy loading) to avoid:
1. Loading heavy indexer modules at Flask blueprint registration time
2. Potential circular imports since indexer may import API components
3. Errors if indexer is not yet initialized when server starts

The indexer is started separately from the API server and may not be
ready when Flask loads these routes.
"""

from datetime import datetime

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/sync/status", methods=["GET"])
def hybrid_sync_status():
    """Get detailed sync status from hybrid indexer.

    Returns comprehensive status including:
    - phase: Current sync phase (bulk_sessions, bulk_messages, bulk_parts, realtime, etc.)
    - progress: Percentage complete (0-100)
    - files_total: Total files to process
    - files_done: Files processed so far
    - queue_size: Files waiting in queue
    - eta_seconds: Estimated time to completion
    - is_ready: True when data is available for queries

    Dashboard uses this to show sync progress and decide when to refresh.
    """
    try:
        from ...analytics.indexer.hybrid import get_sync_status

        status = get_sync_status()
        return jsonify(
            {
                "success": True,
                "data": status.to_dict(),
            }
        )
    except Exception as e:
        # Hybrid indexer not available - return default status
        return jsonify(
            {
                "success": True,
                "data": {
                    "phase": "unknown",
                    "progress": 0,
                    "files_total": 0,
                    "files_done": 0,
                    "queue_size": 0,
                    "eta_seconds": None,
                    "is_ready": False,
                    "error": str(e),
                },
            }
        )


@health_bp.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify(
        {"success": True, "data": {"status": "ok", "service": "analytics-api"}}
    )


@health_bp.route("/api/sync_status", methods=["GET"])
def sync_status():
    """Legacy endpoint - Get sync status in old format.

    DEPRECATED: Use /api/sync/status instead for detailed status.

    This endpoint maintains backward compatibility by deriving legacy
    properties from the new HybridIndexer's SyncStatus:
        - backfill_active: True when indexer is not ready (bulk loading)
        - initial_backfill_done: True when phase is 'realtime' or data is ready
        - timestamp: Current server time

    Mapping from new format:
        - backfill_active = not is_ready
        - initial_backfill_done = is_ready or phase == 'realtime'
    """
    try:
        # Use the same get_sync_status as /api/sync/status
        from ...analytics.indexer.hybrid import get_sync_status

        status = get_sync_status()
        status_dict = status.to_dict()

        # Derive legacy properties from new format
        is_ready = status_dict.get("is_ready", False)
        phase = status_dict.get("phase", "unknown")

        return jsonify(
            {
                "success": True,
                "data": {
                    "backfill_active": not is_ready,
                    "initial_backfill_done": is_ready or phase == "realtime",
                    "timestamp": datetime.now().isoformat(),
                    # Include new fields for clients that want to migrate
                    "phase": phase,
                    "progress": status_dict.get("progress", 0),
                },
            }
        )
    except Exception:
        # Indexer not available - assume not backfilling
        return jsonify(
            {
                "success": True,
                "data": {
                    "backfill_active": False,
                    "initial_backfill_done": True,
                    "timestamp": datetime.now().isoformat(),
                    "phase": "unknown",
                    "progress": 0,
                },
            }
        )
