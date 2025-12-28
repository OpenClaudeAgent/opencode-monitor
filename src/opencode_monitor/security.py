"""
Security module - Command analysis and risk scoring

Analyzes commands executed by agents and assigns a criticality score.
This is passive monitoring only - never blocks execution.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RiskLevel(Enum):
    """Risk levels for commands"""

    LOW = "low"  # 0-19: Normal operations
    MEDIUM = "medium"  # 20-49: Potential impact
    HIGH = "high"  # 50-79: Sensitive operations
    CRITICAL = "critical"  # 80-100: Major risk


@dataclass
class SecurityAlert:
    """Result of security analysis for a command"""

    command: str
    tool: str
    score: int
    level: RiskLevel
    reason: str
    agent_id: Optional[str] = None
    agent_title: Optional[str] = None


# Pattern definitions with base scores
# Format: (pattern, base_score, reason, context_adjustments)
# context_adjustments is a list of (pattern, score_modifier) for contextual scoring

DANGEROUS_PATTERNS = [
    # === CRITICAL (80-100) ===
    # Destructive rm commands
    (
        r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-[a-zA-Z]*r[a-zA-Z]*\s+/",
        95,
        "Recursive delete from root",
        [],
    ),
    (
        r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+)?-[a-zA-Z]*f[a-zA-Z]*\s+/",
        95,
        "Forced recursive delete from root",
        [],
    ),
    (r"\brm\s+-rf\s+/\s*$", 100, "Delete entire filesystem", []),
    (r"\brm\s+-rf\s+/[a-z]+\s*$", 90, "Delete system directory", []),
    (r"\brm\s+-rf\s+~\s*$", 85, "Delete home directory", []),
    # Remote code execution
    (r"curl\s+[^|]*\|\s*(ba)?sh", 95, "Remote code execution via curl", []),
    (r"wget\s+[^|]*\|\s*(ba)?sh", 95, "Remote code execution via wget", []),
    (r"curl\s+[^|]*\|\s*python", 90, "Remote Python execution", []),
    (r'eval\s+"\$\(curl', 95, "Eval remote code", []),
    (r"source\s+<\(curl", 95, "Source remote script", []),
    # Disk operations
    (r"\bdd\s+.*of=/dev/", 90, "Direct disk write", []),
    (r"\bmkfs\.", 85, "Filesystem format", []),
    # === HIGH (50-79) ===
    # Privilege escalation
    (
        r"\bsudo\s+",
        55,
        "Privilege escalation",
        [
            (r"sudo\s+(brew|apt|yum|dnf|pacman)\s+install", -20),  # Package managers OK
            (r"sudo\s+rm\s+-rf", 30),  # sudo rm -rf is worse
        ],
    ),
    (r"\bsu\s+-", 60, "Switch to root user", []),
    (r"\bdoas\s+", 55, "Privilege escalation (doas)", []),
    # Permission changes
    (r"\bchmod\s+777", 70, "World-writable permissions", []),
    (r"\bchmod\s+-R\s+777", 80, "Recursive world-writable", []),
    (r"\bchmod\s+[0-7]*[67][0-7]{2}", 50, "Permissive chmod", []),
    (r"\bchown\s+-R\s+root", 65, "Recursive chown to root", []),
    # Git destructive operations
    (r"git\s+push\s+.*--force.*\s+(main|master)\b", 85, "Force push to main", []),
    (
        r"git\s+push\s+.*--force",
        55,
        "Force push",
        [
            (r"--force.*origin\s+(main|master)", 30),  # To main is worse
        ],
    ),
    (r"git\s+reset\s+--hard", 60, "Hard reset", []),
    (r"git\s+clean\s+-fd", 55, "Clean untracked files", []),
    (r"git\s+checkout\s+--\s+\.", 50, "Discard all changes", []),
    # SQL destructive operations
    (r"\bDROP\s+(DATABASE|TABLE|SCHEMA)\b", 80, "SQL DROP operation", []),
    (r"\bTRUNCATE\s+TABLE\b", 75, "SQL TRUNCATE", []),
    (r"\bDELETE\s+FROM\s+\w+\s*;", 70, "DELETE without WHERE", []),
    (r"\bDELETE\s+FROM\s+\w+\s+WHERE", 40, "DELETE with WHERE", []),
    (r"\bUPDATE\s+\w+\s+SET\s+.*;\s*$", 60, "UPDATE without WHERE", []),
    # Process management
    (r"\bkill\s+-9", 50, "Force kill process", []),
    (r"\bkillall\s+", 55, "Kill all matching processes", []),
    (r"\bpkill\s+-9", 55, "Force pkill", []),
    # === MEDIUM (20-49) ===
    # File operations in sensitive directories
    (
        r"\b(rm|mv|cp)\s+.*(/etc/|/usr/|/var/|/boot/)",
        45,
        "Operation on system directory",
        [],
    ),
    (r"\becho\s+.*>\s*/etc/", 50, "Write to /etc/", []),
    # Recursive operations with wildcards
    (r"\brm\s+-rf\s+\*", 45, "Recursive delete with wildcard", []),
    (r"\brm\s+-rf\s+node_modules", 25, "Delete node_modules", []),  # Common, less risky
    (r"\brm\s+-rf\s+\.git", 60, "Delete git directory", []),
    (r"\brm\s+-rf\s+(dist|build|target|out)\b", 20, "Delete build directory", []),
    # Network operations
    (r"\bnc\s+-l", 40, "Netcat listener", []),
    (r"\bssh\s+-R", 45, "SSH reverse tunnel", []),
    (r"\biptables\s+", 50, "Firewall modification", []),
    # Environment modifications
    (r"export\s+PATH=", 30, "PATH modification", []),
    (r"export\s+(AWS|GITHUB|API)_", 35, "Export sensitive env var", []),
    # Package operations
    (r"\bnpm\s+publish", 40, "Publish npm package", []),
    (r"\bpip\s+install\s+--user", 25, "Pip user install", []),
]

# Safe patterns that reduce score
SAFE_PATTERNS = [
    (r"--dry-run", -20, "Dry run mode"),
    (r"--no-preserve-root", 50, "Explicitly dangerous flag"),  # Actually increases!
    (r"-n\s", -10, "No-execute flag"),
    (r"--help", -50, "Help flag"),
    (r'echo\s+["\']', -10, "Echo command"),
    # Safe directories - reduce score significantly
    (r"\s/tmp/", -60, "Temp directory operation"),
    (r"\s/var/tmp/", -60, "Temp directory operation"),
    (r"\s\$TMPDIR/", -60, "Temp directory operation"),
    (r"node_modules", -40, "Node modules operation"),
    (r"\.cache/", -40, "Cache directory operation"),
    (r"/build/", -30, "Build directory operation"),
    (r"/dist/", -30, "Dist directory operation"),
    (r"/target/", -30, "Target directory operation"),
    # Local API calls - not dangerous
    (r"localhost[:/]", -50, "Localhost operation"),
    (r"127\.0\.0\.1[:/]", -50, "Localhost operation"),
    (r"0\.0\.0\.0[:/]", -40, "Local bind"),
]


def analyze_command(command: str, tool: str = "bash") -> SecurityAlert:
    """
    Analyze a command and return a security alert with risk score.

    Args:
        command: The command string to analyze
        tool: The tool executing the command (bash, write, edit)

    Returns:
        SecurityAlert with score (0-100), level, and reason
    """
    if not command or not command.strip():
        return SecurityAlert(
            command=command,
            tool=tool,
            score=0,
            level=RiskLevel.LOW,
            reason="Empty command",
        )

    command_lower = command.lower()
    max_score = 0
    primary_reason = "Normal operation"

    # Check each dangerous pattern
    for pattern, base_score, reason, context_adjustments in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            adjusted_score = base_score

            # Apply context adjustments
            for ctx_pattern, modifier in context_adjustments:
                if re.search(ctx_pattern, command, re.IGNORECASE):
                    adjusted_score += modifier

            # Keep the highest scoring match
            if adjusted_score > max_score:
                max_score = adjusted_score
                primary_reason = reason

    # Apply safe pattern modifiers
    for pattern, modifier, _ in SAFE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            max_score += modifier

    # Clamp score to 0-100
    max_score = max(0, min(100, max_score))

    # Determine risk level
    if max_score >= 80:
        level = RiskLevel.CRITICAL
    elif max_score >= 50:
        level = RiskLevel.HIGH
    elif max_score >= 20:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    return SecurityAlert(
        command=command, tool=tool, score=max_score, level=level, reason=primary_reason
    )


def get_level_emoji(level: RiskLevel) -> str:
    """Return emoji indicator for risk level"""
    return {
        RiskLevel.LOW: "",
        RiskLevel.MEDIUM: "🟡",
        RiskLevel.HIGH: "🟠",
        RiskLevel.CRITICAL: "🔴",
    }.get(level, "")


def format_alert_short(alert: SecurityAlert, max_length: int = 40) -> str:
    """Format alert for menu display (short form)"""
    emoji = get_level_emoji(alert.level)
    cmd = (
        alert.command[:max_length] + "..."
        if len(alert.command) > max_length
        else alert.command
    )

    if emoji:
        return f"{emoji} {cmd}"
    return cmd
