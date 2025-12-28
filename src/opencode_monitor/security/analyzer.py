"""
Security Analyzer - Risk analysis for commands, files, and URLs

Provides unified security analysis for:
- Bash commands (analyze_command)
- File paths for read/write operations (RiskAnalyzer.analyze_file_path)
- URLs for webfetch operations (RiskAnalyzer.analyze_url)
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, Dict, List


# =============================================================================
# Common Types
# =============================================================================


class RiskLevel(Enum):
    """Risk levels for security analysis"""

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


@dataclass
class RiskResult:
    """Result of a file/URL risk analysis"""

    score: int
    level: str
    reason: str


# =============================================================================
# Command Analysis
# =============================================================================

# Pattern definitions with base scores
DANGEROUS_PATTERNS = [
    # === CRITICAL (80-100) ===
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
    (r"curl\s+[^|]*\|\s*(ba)?sh", 95, "Remote code execution via curl", []),
    (r"wget\s+[^|]*\|\s*(ba)?sh", 95, "Remote code execution via wget", []),
    (r"curl\s+[^|]*\|\s*python", 90, "Remote Python execution", []),
    (r'eval\s+"\$\(curl', 95, "Eval remote code", []),
    (r"source\s+<\(curl", 95, "Source remote script", []),
    (r"\bdd\s+.*of=/dev/", 90, "Direct disk write", []),
    (r"\bmkfs\.", 85, "Filesystem format", []),
    # === HIGH (50-79) ===
    (
        r"\bsudo\s+",
        55,
        "Privilege escalation",
        [
            (r"sudo\s+(brew|apt|yum|dnf|pacman)\s+install", -20),
            (r"sudo\s+rm\s+-rf", 30),
        ],
    ),
    (r"\bsu\s+-", 60, "Switch to root user", []),
    (r"\bdoas\s+", 55, "Privilege escalation (doas)", []),
    (r"\bchmod\s+777", 70, "World-writable permissions", []),
    (r"\bchmod\s+-R\s+777", 80, "Recursive world-writable", []),
    (r"\bchmod\s+[0-7]*[67][0-7]{2}", 50, "Permissive chmod", []),
    (r"\bchown\s+-R\s+root", 65, "Recursive chown to root", []),
    (r"git\s+push\s+.*--force.*\s+(main|master)\b", 85, "Force push to main", []),
    (
        r"git\s+push\s+.*--force",
        55,
        "Force push",
        [
            (r"--force.*origin\s+(main|master)", 30),
        ],
    ),
    (r"git\s+reset\s+--hard", 60, "Hard reset", []),
    (r"git\s+clean\s+-fd", 55, "Clean untracked files", []),
    (r"git\s+checkout\s+--\s+\.", 50, "Discard all changes", []),
    (r"\bDROP\s+(DATABASE|TABLE|SCHEMA)\b", 80, "SQL DROP operation", []),
    (r"\bTRUNCATE\s+TABLE\b", 75, "SQL TRUNCATE", []),
    (r"\bDELETE\s+FROM\s+\w+\s*;", 70, "DELETE without WHERE", []),
    (r"\bDELETE\s+FROM\s+\w+\s+WHERE", 40, "DELETE with WHERE", []),
    (r"\bUPDATE\s+\w+\s+SET\s+.*;\s*$", 60, "UPDATE without WHERE", []),
    (r"\bkill\s+-9", 50, "Force kill process", []),
    (r"\bkillall\s+", 55, "Kill all matching processes", []),
    (r"\bpkill\s+-9", 55, "Force pkill", []),
    # === MEDIUM (20-49) ===
    (
        r"\b(rm|mv|cp)\s+.*(/etc/|/usr/|/var/|/boot/)",
        45,
        "Operation on system directory",
        [],
    ),
    (r"\becho\s+.*>\s*/etc/", 50, "Write to /etc/", []),
    (r"\brm\s+-rf\s+\*", 45, "Recursive delete with wildcard", []),
    (r"\brm\s+-rf\s+node_modules", 25, "Delete node_modules", []),
    (r"\brm\s+-rf\s+\.git", 60, "Delete git directory", []),
    (r"\brm\s+-rf\s+(dist|build|target|out)\b", 20, "Delete build directory", []),
    (r"\bnc\s+-l", 40, "Netcat listener", []),
    (r"\bssh\s+-R", 45, "SSH reverse tunnel", []),
    (r"\biptables\s+", 50, "Firewall modification", []),
    (r"export\s+PATH=", 30, "PATH modification", []),
    (r"export\s+(AWS|GITHUB|API)_", 35, "Export sensitive env var", []),
    (r"\bnpm\s+publish", 40, "Publish npm package", []),
    (r"\bpip\s+install\s+--user", 25, "Pip user install", []),
]

SAFE_PATTERNS = [
    (r"--dry-run", -20, "Dry run mode"),
    (r"--no-preserve-root", 50, "Explicitly dangerous flag"),
    (r"-n\s", -10, "No-execute flag"),
    (r"--help", -50, "Help flag"),
    (r'echo\s+["\']', -10, "Echo command"),
    (r"\s/tmp/", -60, "Temp directory operation"),
    (r"\s/var/tmp/", -60, "Temp directory operation"),
    (r"\s\$TMPDIR/", -60, "Temp directory operation"),
    (r"node_modules", -40, "Node modules operation"),
    (r"\.cache/", -40, "Cache directory operation"),
    (r"/build/", -30, "Build directory operation"),
    (r"/dist/", -30, "Dist directory operation"),
    (r"/target/", -30, "Target directory operation"),
    (r"localhost[:/]", -50, "Localhost operation"),
    (r"127\.0\.0\.1[:/]", -50, "Localhost operation"),
    (r"0\.0\.0\.0[:/]", -40, "Local bind"),
]


def analyze_command(command: str, tool: str = "bash") -> SecurityAlert:
    """Analyze a command and return a security alert with risk score."""
    if not command or not command.strip():
        return SecurityAlert(
            command=command,
            tool=tool,
            score=0,
            level=RiskLevel.LOW,
            reason="Empty command",
        )

    max_score = 0
    primary_reason = "Normal operation"

    for pattern, base_score, reason, context_adjustments in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            adjusted_score = base_score
            for ctx_pattern, modifier in context_adjustments:
                if re.search(ctx_pattern, command, re.IGNORECASE):
                    adjusted_score += modifier
            if adjusted_score > max_score:
                max_score = adjusted_score
                primary_reason = reason

    for pattern, modifier, _ in SAFE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            max_score += modifier

    max_score = max(0, min(100, max_score))

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


# =============================================================================
# File/URL Analysis
# =============================================================================

SENSITIVE_FILE_PATTERNS: Dict[str, List[Tuple[str, int, str]]] = {
    "critical": [
        (r"\.ssh/", 95, "SSH directory"),
        (r"id_rsa", 95, "SSH private key"),
        (r"id_ed25519", 95, "SSH private key"),
        (r"\.pem$", 90, "PEM certificate/key"),
        (r"\.key$", 90, "Private key file"),
        (r"\.env$", 85, "Environment file"),
        (r"\.env\.", 85, "Environment file"),
        (r"password", 85, "Password file"),
        (r"secret", 85, "Secret file"),
        (r"/etc/shadow", 100, "System shadow file"),
    ],
    "high": [
        (r"/etc/passwd", 60, "System passwd file"),
        (r"/etc/", 55, "System config"),
        (r"\.aws/", 70, "AWS credentials"),
        (r"\.kube/", 65, "Kubernetes config"),
        (r"credential", 60, "Credentials file"),
        (r"token", 55, "Token file"),
        (r"\.npmrc", 60, "NPM config with tokens"),
        (r"\.pypirc", 60, "PyPI config with tokens"),
    ],
    "medium": [
        (r"\.config/", 30, "Config directory"),
        (r"\.git/config", 40, "Git config"),
        (r"auth", 35, "Auth-related file"),
        (r"\.db$", 35, "Database file"),
        (r"\.sqlite", 35, "SQLite database"),
        (r"\.json$", 25, "JSON config"),
    ],
}

SENSITIVE_URL_PATTERNS: Dict[str, List[Tuple[str, int, str]]] = {
    "critical": [
        (r"raw\.githubusercontent\.com.*\.sh$", 90, "Shell script from GitHub"),
        (r"pastebin\.com", 85, "Pastebin content"),
        (r"hastebin", 85, "Hastebin content"),
        (r"\.(sh|bash|zsh)$", 80, "Shell script download"),
        (r"\.exe$", 95, "Executable download"),
    ],
    "high": [
        (r"raw\.githubusercontent\.com", 55, "Raw GitHub content"),
        (r"gist\.github", 50, "GitHub Gist"),
        (r"\.py$", 50, "Python script download"),
        (r"\.js$", 50, "JavaScript download"),
    ],
    "medium": [
        (r"api\.", 25, "API endpoint"),
        (r"\.json$", 20, "JSON data"),
        (r"\.xml$", 20, "XML data"),
    ],
}


class RiskAnalyzer:
    """Analyzes file paths and URLs for security risks"""

    @staticmethod
    def _score_to_level(score: int) -> str:
        """Convert a score to a risk level"""
        if score >= 80:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 20:
            return "medium"
        return "low"

    @staticmethod
    def _analyze_patterns(
        value: str, patterns: Dict[str, List[Tuple[str, int, str]]]
    ) -> Tuple[int, str]:
        """Analyze a value against patterns, return max score and reason"""
        value_lower = value.lower()
        max_score = 0
        reason = "Normal"

        for level in ["critical", "high", "medium"]:
            for pattern, score, desc in patterns.get(level, []):
                if re.search(pattern, value_lower):
                    if score > max_score:
                        max_score = score
                        reason = desc

        return max_score, reason

    def analyze_file_path(self, file_path: str, write_mode: bool = False) -> RiskResult:
        """Analyze a file path for security risk"""
        score, reason = self._analyze_patterns(file_path, SENSITIVE_FILE_PATTERNS)

        if write_mode and score > 0:
            score = min(100, score + 10)
            reason = f"WRITE: {reason}"

        level = self._score_to_level(score)

        if score == 0:
            reason = "Normal file"

        return RiskResult(score=score, level=level, reason=reason)

    def analyze_url(self, url: str) -> RiskResult:
        """Analyze a URL for security risk"""
        score, reason = self._analyze_patterns(url, SENSITIVE_URL_PATTERNS)
        level = self._score_to_level(score)

        if score == 0:
            reason = "Normal URL"

        return RiskResult(score=score, level=level, reason=reason)


# Singleton instance
_analyzer: Optional[RiskAnalyzer] = None


def get_risk_analyzer() -> RiskAnalyzer:
    """Get the singleton RiskAnalyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = RiskAnalyzer()
    return _analyzer
