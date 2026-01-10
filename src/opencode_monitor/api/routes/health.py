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


def _get_indexer_status() -> dict:
    """Get status from UnifiedIndexer in a format compatible with legacy API.

    Returns dict with:
    - phase: 'indexing' or 'ready'
    - progress: 0-100 (estimated)
    - files_total: Total files processed
    - files_done: Same as files_total (no queue in v2)
    - queue_size: Pending files in accumulator
    - is_ready: True when indexer is running
    """
    try:
        from ...analytics.indexer.unified import get_indexer

        indexer = get_indexer()
        stats = indexer.get_stats()

        files_processed = stats.get("files_processed", 0)
        acc_stats = stats.get("accumulator", {})
        rec_stats = stats.get("reconciler", {})

        # Determine phase based on activity
        scans_completed = rec_stats.get("scans_completed", 0)
        is_ready = scans_completed > 0 and files_processed > 0

        return {
            "phase": "ready" if is_ready else "indexing",
            "progress": 100 if is_ready else min(99, scans_completed * 10),
            "files_total": files_processed,
            "files_done": files_processed,
            "queue_size": acc_stats.get("files_accumulated", 0)
            - acc_stats.get("batches_sent", 0) * 200,
            "eta_seconds": None,
            "is_ready": is_ready,
            "v2_stats": {
                "sessions_indexed": stats.get("sessions_indexed", 0),
                "messages_indexed": stats.get("messages_indexed", 0),
                "parts_indexed": stats.get("parts_indexed", 0),
                "batches_sent": acc_stats.get("batches_sent", 0),
                "scans_completed": scans_completed,
            },
        }
    except Exception as e:
        return {
            "phase": "error",
            "progress": 0,
            "files_total": 0,
            "files_done": 0,
            "queue_size": 0,
            "eta_seconds": None,
            "is_ready": False,
            "error": str(e),
        }


@health_bp.route("/api/sync/status", methods=["GET"])
def sync_status_detailed():
    """Get detailed sync status from UnifiedIndexer.

    Returns comprehensive status including:
    - phase: Current sync phase ('indexing' or 'ready')
    - progress: Percentage complete (0-100)
    - files_total: Total files processed
    - files_done: Files processed so far
    - queue_size: Files waiting in accumulator
    - is_ready: True when data is available for queries
    - v2_stats: Detailed v2 indexer statistics

    Dashboard uses this to show sync progress and decide when to refresh.
    """
    status = _get_indexer_status()
    return jsonify({"success": True, "data": status})


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

    Returns:
        - backfill_active: True when indexer is not ready
        - initial_backfill_done: True when indexer is ready
        - timestamp: Current server time
        - phase: Current phase
        - progress: Progress percentage
    """
    status = _get_indexer_status()

    is_ready = status.get("is_ready", False)
    phase = status.get("phase", "unknown")

    return jsonify(
        {
            "success": True,
            "data": {
                "backfill_active": not is_ready,
                "initial_backfill_done": is_ready,
                "timestamp": datetime.now().isoformat(),
                "phase": phase,
                "progress": status.get("progress", 0),
            },
        }
    )
