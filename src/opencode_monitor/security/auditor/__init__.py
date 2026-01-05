"""
Security Auditor Package

Provides background scanning and analysis of OpenCode command history
for security risks, with EDR-like heuristics for detecting attack patterns.

Public API:
- SecurityAuditor: Main auditor class
- get_auditor(): Get or create global auditor instance
- start_auditor(): Start the background scanning
- stop_auditor(): Stop the auditor

Backwards compatibility:
All symbols that were accessible via `from opencode_monitor.security.auditor import X`
in the original auditor.py are re-exported here for API compatibility.
"""

# Core auditor API
from .core import (
    SecurityAuditor,
    get_auditor,
    start_auditor,
    stop_auditor,
    _auditor,
)

# Constants (for patching in tests)
from ._constants import OPENCODE_STORAGE, SCAN_INTERVAL

# Re-export symbols from sibling modules for backwards compatibility
# These were imported in the original auditor.py and thus accessible via
# `from opencode_monitor.security.auditor import X`
from ..analyzer import analyze_command, get_risk_analyzer
from ..db import (
    SecurityDatabase,
    SecurityScannerDuckDB,
    AuditedCommand,
    AuditedFileRead,
    AuditedFileWrite,
    AuditedWebFetch,
)
from ..reporter import SecurityReporter
from ..sequences import SequenceAnalyzer, SequenceMatch, create_event_from_audit_data
from ..correlator import EventCorrelator, Correlation

# Re-export for backwards compatibility with tests
# that access the module-level _auditor variable
from . import core as _core

# Also expose time for patching in tests
import time


__all__ = [
    # Core API
    "SecurityAuditor",
    "get_auditor",
    "start_auditor",
    "stop_auditor",
    # Constants
    "OPENCODE_STORAGE",
    "SCAN_INTERVAL",
    # From analyzer
    "analyze_command",
    "get_risk_analyzer",
    # From db
    "SecurityDatabase",
    "SecurityScannerDuckDB",
    "AuditedCommand",
    "AuditedFileRead",
    "AuditedFileWrite",
    "AuditedWebFetch",
    # From reporter
    "SecurityReporter",
    # From sequences
    "SequenceAnalyzer",
    "SequenceMatch",
    "create_event_from_audit_data",
    # From correlator
    "EventCorrelator",
    "Correlation",
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
