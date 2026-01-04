"""
API Routes Package - Flask Blueprints for analytics API.

Each module contains a Flask Blueprint for a specific domain:
- health: Health check endpoint
- stats: Database and global statistics
- sessions: Session listing and details
- tracing: Tracing tree endpoints
- delegations: Agent delegation endpoints
"""

from .health import health_bp
from .stats import stats_bp
from .sessions import sessions_bp
from .tracing import tracing_bp
from .delegations import delegations_bp

__all__ = [
    "health_bp",
    "stats_bp",
    "sessions_bp",
    "tracing_bp",
    "delegations_bp",
]
