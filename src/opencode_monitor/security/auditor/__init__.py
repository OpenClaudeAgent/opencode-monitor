"""
Security Auditor Package

Provides background scanning and analysis of OpenCode command history
for security risks, with EDR-like heuristics for detecting attack patterns.

Public API:
- SecurityAuditor: Main auditor class
- get_auditor(): Get or create global auditor instance
- start_auditor(): Start the background scanning
- stop_auditor(): Stop the auditor
"""

from .core import (
    SecurityAuditor,
    get_auditor,
    start_auditor,
    stop_auditor,
    _auditor,
)

# Re-export for backwards compatibility with tests
# that access the module-level _auditor variable
from . import core as _core

__all__ = [
    "SecurityAuditor",
    "get_auditor",
    "start_auditor",
    "stop_auditor",
]


# Provide _auditor access at module level for backwards compatibility
def __getattr__(name: str):
    if name == "_auditor":
        return _core._auditor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __setattr__(name: str, value):
    if name == "_auditor":
        _core._auditor = value
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
