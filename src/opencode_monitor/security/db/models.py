"""
Security Database Models - Dataclasses for audited operations
"""

from dataclasses import dataclass


@dataclass
class AuditedCommand:
    """A command that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    tool: str
    command: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str


@dataclass
class AuditedFileRead:
    """A file read operation that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    file_path: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str


@dataclass
class AuditedFileWrite:
    """A file write/edit operation that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    file_path: str
    operation: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str


@dataclass
class AuditedWebFetch:
    """A webfetch operation that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    url: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str
