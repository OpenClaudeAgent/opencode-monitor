"""
Health Check Routes - Simple health endpoint.
"""

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify(
        {"success": True, "data": {"status": "ok", "service": "analytics-api"}}
    )
