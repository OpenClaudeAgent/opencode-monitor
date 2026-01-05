"""
Trace builder package.

Public API:
- TraceBuilder: Main class for building agent traces
- ROOT_TRACE_PREFIX: Prefix for root trace IDs
- ROOT_AGENT_TYPE: Agent type for root traces

Internal modules:
- builder: TraceBuilder class implementation
- helpers: Pure utility functions
"""

from .builder import TraceBuilder, ROOT_TRACE_PREFIX, ROOT_AGENT_TYPE

__all__ = [
    "TraceBuilder",
    "ROOT_TRACE_PREFIX",
    "ROOT_AGENT_TYPE",
]
