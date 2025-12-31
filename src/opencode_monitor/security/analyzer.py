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
    mitre_techniques: List[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.mitre_techniques is None:
            self.mitre_techniques = []


@dataclass
class RiskResult:
    """Result of a file/URL risk analysis"""

    score: int
    level: str
    reason: str
    mitre_techniques: List[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.mitre_techniques is None:
            self.mitre_techniques = []


# =============================================================================
# Command Analysis
# =============================================================================

# MITRE ATT&CK Technique IDs
# T1059 - Command and Scripting Interpreter
# T1048 - Exfiltration Over Alternative Protocol
# T1070 - Indicator Removal
# T1222 - File and Directory Permissions Modification
# T1105 - Ingress Tool Transfer
# T1053 - Scheduled Task/Job
# T1087 - Account Discovery
# T1082 - System Information Discovery
# T1485 - Data Destruction
# T1548 - Abuse Elevation Control Mechanism

# Pattern definitions with base scores and MITRE techniques
# Format: (pattern, score, reason, context_adjustments, mitre_techniques)
DANGEROUS_PATTERNS = [
    # === CRITICAL (80-100) ===
    (
        r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-[a-zA-Z]*r[a-zA-Z]*\s+/",
        95,
        "Recursive delete from root",
        [],
        ["T1485", "T1070"],  # Data Destruction, Indicator Removal
    ),
    (
        r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+)?-[a-zA-Z]*f[a-zA-Z]*\s+/",
        95,
        "Forced recursive delete from root",
        [],
        ["T1485", "T1070"],
    ),
    (r"\brm\s+-rf\s+/\s*$", 100, "Delete entire filesystem", [], ["T1485"]),
    (r"\brm\s+-rf\s+/[a-z]+\s*$", 90, "Delete system directory", [], ["T1485"]),
    (r"\brm\s+-rf\s+~\s*$", 85, "Delete home directory", [], ["T1485"]),
    (
        r"curl\s+[^|]*\|\s*(ba)?sh",
        95,
        "Remote code execution via curl",
        [],
        ["T1059", "T1105"],
    ),
    (
        r"wget\s+[^|]*\|\s*(ba)?sh",
        95,
        "Remote code execution via wget",
        [],
        ["T1059", "T1105"],
    ),
    (r"curl\s+[^|]*\|\s*python", 90, "Remote Python execution", [], ["T1059", "T1105"]),
    (r'eval\s+"\$\(curl', 95, "Eval remote code", [], ["T1059", "T1105"]),
    (r"source\s+<\(curl", 95, "Source remote script", [], ["T1059", "T1105"]),
    (r"\bdd\s+.*of=/dev/", 90, "Direct disk write", [], ["T1485"]),
    (r"\bmkfs\.", 85, "Filesystem format", [], ["T1485"]),
    # === HIGH (50-79) ===
    (
        r"\bsudo\s+",
        55,
        "Privilege escalation",
        [
            (r"sudo\s+(brew|apt|yum|dnf|pacman)\s+install", -20),
            (r"sudo\s+rm\s+-rf", 30),
        ],
        ["T1548"],  # Abuse Elevation Control Mechanism
    ),
    (r"\bsu\s+-", 60, "Switch to root user", [], ["T1548"]),
    (r"\bdoas\s+", 55, "Privilege escalation (doas)", [], ["T1548"]),
    (r"\bchmod\s+777", 70, "World-writable permissions", [], ["T1222"]),
    (r"\bchmod\s+-R\s+777", 80, "Recursive world-writable", [], ["T1222"]),
    (r"\bchmod\s+[0-7]*[67][0-7]{2}", 50, "Permissive chmod", [], ["T1222"]),
    (r"\bchown\s+-R\s+root", 65, "Recursive chown to root", [], ["T1222"]),
    (r"git\s+push\s+.*--force.*\s+(main|master)\b", 85, "Force push to main", [], []),
    (
        r"git\s+push\s+.*--force",
        55,
        "Force push",
        [
            (r"--force.*origin\s+(main|master)", 30),
        ],
        [],
    ),
    (r"git\s+reset\s+--hard", 60, "Hard reset", [], ["T1070"]),
    (r"git\s+clean\s+-fd", 55, "Clean untracked files", [], ["T1070"]),
    (r"git\s+checkout\s+--\s+\.", 50, "Discard all changes", [], []),
    (r"\bDROP\s+(DATABASE|TABLE|SCHEMA)\b", 80, "SQL DROP operation", [], ["T1485"]),
    (r"\bTRUNCATE\s+TABLE\b", 75, "SQL TRUNCATE", [], ["T1485"]),
    (r"\bDELETE\s+FROM\s+\w+\s*;", 70, "DELETE without WHERE", [], ["T1485"]),
    (r"\bDELETE\s+FROM\s+\w+\s+WHERE", 40, "DELETE with WHERE", [], []),
    (r"\bUPDATE\s+\w+\s+SET\s+.*;\s*$", 60, "UPDATE without WHERE", [], []),
    (r"\bkill\s+-9", 50, "Force kill process", [], ["T1489"]),  # Service Stop
    (r"\bkillall\s+", 55, "Kill all matching processes", [], ["T1489"]),
    (r"\bpkill\s+-9", 55, "Force pkill", [], ["T1489"]),
    # === MEDIUM (20-49) ===
    (
        r"\b(rm|mv|cp)\s+.*(/etc/|/usr/|/var/|/boot/)",
        45,
        "Operation on system directory",
        [],
        [],
    ),
    (r"\becho\s+.*>\s*/etc/", 50, "Write to /etc/", [], ["T1222"]),
    (r"\brm\s+-rf\s+\*", 45, "Recursive delete with wildcard", [], ["T1070"]),
    (r"\brm\s+-rf\s+node_modules", 25, "Delete node_modules", [], []),
    (r"\brm\s+-rf\s+\.git", 60, "Delete git directory", [], ["T1070"]),
    (r"\brm\s+-rf\s+(dist|build|target|out)\b", 20, "Delete build directory", [], []),
    (r"\bnc\s+-l", 40, "Netcat listener", [], ["T1059"]),
    (r"\bssh\s+-R", 45, "SSH reverse tunnel", [], ["T1572"]),  # Protocol Tunneling
    (r"\biptables\s+", 50, "Firewall modification", [], ["T1562"]),  # Impair Defenses
    (
        r"export\s+PATH=",
        30,
        "PATH modification",
        [],
        ["T1574"],
    ),  # Hijack Execution Flow
    (r"export\s+(AWS|GITHUB|API)_", 35, "Export sensitive env var", [], []),
    (
        r"\bnpm\s+publish",
        40,
        "Publish npm package",
        [],
        ["T1195"],
    ),  # Supply Chain Compromise
    (r"\bpip\s+install\s+--user", 25, "Pip user install", [], []),
    # Additional patterns for MITRE coverage
    (r"\bcrontab\s+", 40, "Crontab modification", [], ["T1053"]),  # Scheduled Task
    (r"\bhistory\s+-c", 50, "Clear command history", [], ["T1070"]),
    (r"\bshred\s+", 45, "Secure file deletion", [], ["T1070"]),
    (
        r"\bcat\s+/etc/passwd",
        30,
        "Read system passwd",
        [],
        ["T1087"],
    ),  # Account Discovery
    (
        r"\b(whoami|id|groups)\b",
        20,
        "User discovery",
        [],
        ["T1033"],
    ),  # System Owner/User Discovery
    (r"\buname\s+-a", 20, "System information", [], ["T1082"]),
    (r"\bcat\s+/proc/", 25, "Read proc filesystem", [], ["T1082"]),
    # === NEW PATTERNS FOR BROADER MITRE COVERAGE ===
    # T1560 - Archive Collected Data
    (r"\btar\s+.*-[a-z]*c[a-z]*f", 25, "Create tar archive", [], ["T1560"]),
    (r"\bzip\s+-r", 25, "Create zip archive recursively", [], ["T1560"]),
    (r"\bgzip\s+", 20, "Compress file", [], ["T1560"]),
    (r"\b7z\s+a\b", 25, "Create 7zip archive", [], ["T1560"]),
    # T1132 - Data Encoding / T1140 - Deobfuscate
    (r"\bbase64\s+[^-]", 30, "Base64 encode", [], ["T1132"]),
    (r"\bbase64\s+-d", 35, "Base64 decode", [], ["T1140"]),
    (r"\bopenssl\s+(enc|dec)", 35, "OpenSSL encrypt/decrypt", [], ["T1140"]),
    (r"\bxxd\s+", 25, "Hex dump/undump", [], ["T1132"]),
    # T1046 - Network Service Discovery
    (r"\bnmap\s+", 45, "Network port scan", [], ["T1046"]),
    (r"\bnetstat\s+-", 25, "Network connections", [], ["T1046", "T1016"]),
    (r"\bss\s+-[a-z]*l", 25, "Socket statistics", [], ["T1046"]),
    # T1016 - System Network Configuration Discovery
    (r"\bifconfig\b", 20, "Network interface config", [], ["T1016"]),
    (r"\bip\s+(addr|route|link)", 20, "IP configuration", [], ["T1016"]),
    (r"\bcat\s+/etc/(hosts|resolv)", 25, "Read network config", [], ["T1016"]),
    # T1057 - Process Discovery
    (r"\bps\s+(aux|ef)", 20, "Process listing", [], ["T1057"]),
    (r"\btop\s+-b", 20, "Batch process listing", [], ["T1057"]),
    (r"\blsof\s+", 25, "List open files", [], ["T1057"]),
    # T1083 - File and Directory Discovery
    (r"\bfind\s+/\s+-name", 25, "Find from root", [], ["T1083"]),
    (r"\bfind\s+.*-type\s+f.*-exec", 35, "Find with exec", [], ["T1083", "T1119"]),
    (r"\blocate\s+", 20, "Locate files", [], ["T1083"]),
    # T1555 - Credentials from Password Stores
    (
        r"\bsecurity\s+find-(generic|internet)-password",
        60,
        "macOS Keychain access",
        [],
        ["T1555"],
    ),
    (r"\bkeychain\b", 40, "Keychain access", [], ["T1555"]),
    (r"\bpass\s+(show|ls)", 50, "Password store access", [], ["T1555"]),
    (r"\bgpg\s+--decrypt", 40, "GPG decrypt", [], ["T1555"]),
    # T1539 - Steal Web Session Cookie
    (r"Cookies\.sqlite", 50, "Browser cookies file", [], ["T1539"]),
    (r"cookies\.json", 45, "Cookies JSON file", [], ["T1539"]),
    (r"\.cookie", 40, "Cookie file", [], ["T1539"]),
    # T1119 - Automated Collection
    (r"\brsync\s+.*-a", 30, "Rsync archive mode", [], ["T1119"]),
    (r"\bscp\s+-r", 30, "Recursive SCP", [], ["T1119", "T1048"]),
    # T1003 - OS Credential Dumping
    (r"/etc/shadow", 70, "Shadow file access", [], ["T1003"]),
    (r"\.docker/config\.json", 50, "Docker credentials", [], ["T1552"]),
    (r"\.kube/config", 50, "Kubernetes config", [], ["T1552"]),
    # T1562 - Impair Defenses
    (r"\bsystemctl\s+(stop|disable)", 40, "Stop/disable service", [], ["T1562"]),
    (r"\blaunchctl\s+unload", 40, "Unload launch agent", [], ["T1562"]),
    (r"\bsetenforce\s+0", 60, "Disable SELinux", [], ["T1562"]),
    # T1497 - Sandbox/VM Detection (potential evasion)
    (r"\bdmesg\s+\|.*grep.*(vmware|virtual|vbox)", 35, "VM detection", [], ["T1497"]),
    (r"\bsystemd-detect-virt", 30, "Virtualization detection", [], ["T1497"]),
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
            mitre_techniques=[],
        )

    max_score = 0
    primary_reason = "Normal operation"
    mitre_techniques: List[str] = []

    for entry in DANGEROUS_PATTERNS:
        # Handle both old format (4 elements) and new format (5 elements with MITRE)
        if len(entry) == 5:
            pattern, base_score, reason, context_adjustments, mitre = entry
        else:
            pattern, base_score, reason, context_adjustments = entry
            mitre = []

        if re.search(pattern, command, re.IGNORECASE):
            adjusted_score = base_score
            for ctx_pattern, modifier in context_adjustments:
                if re.search(ctx_pattern, command, re.IGNORECASE):
                    adjusted_score += modifier
            if adjusted_score > max_score:
                max_score = adjusted_score
                primary_reason = reason
                # Collect MITRE techniques from all matching patterns
            if mitre:
                for tech in mitre:
                    if tech not in mitre_techniques:
                        mitre_techniques.append(tech)

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
        command=command,
        tool=tool,
        score=max_score,
        level=level,
        reason=primary_reason,
        mitre_techniques=mitre_techniques,
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

# File patterns with MITRE techniques
# Format: (pattern, score, reason, mitre_techniques)
SENSITIVE_FILE_PATTERNS: Dict[str, List[Tuple[str, int, str, List[str]]]] = {
    "critical": [
        (r"\.ssh/", 95, "SSH directory", ["T1552"]),  # Unsecured Credentials
        (r"id_rsa", 95, "SSH private key", ["T1552", "T1145"]),  # Private Keys
        (r"id_ed25519", 95, "SSH private key", ["T1552", "T1145"]),
        (r"\.pem$", 90, "PEM certificate/key", ["T1552", "T1145"]),
        (r"\.key$", 90, "Private key file", ["T1552", "T1145"]),
        (r"\.env$", 85, "Environment file", ["T1552"]),
        (r"\.env\.", 85, "Environment file", ["T1552"]),
        (
            r"password",
            85,
            "Password file",
            ["T1552", "T1555"],
        ),  # Credentials from Password Stores
        (r"secret", 85, "Secret file", ["T1552"]),
        (
            r"/etc/shadow",
            100,
            "System shadow file",
            ["T1003", "T1087"],
        ),  # OS Credential Dumping
    ],
    "high": [
        (r"/etc/passwd", 60, "System passwd file", ["T1087"]),  # Account Discovery
        (r"/etc/", 55, "System config", ["T1082"]),  # System Information Discovery
        (r"\.aws/", 70, "AWS credentials", ["T1552"]),
        (r"\.kube/", 65, "Kubernetes config", ["T1552"]),
        (r"credential", 60, "Credentials file", ["T1552"]),
        (r"token", 55, "Token file", ["T1528"]),  # Steal Application Access Token
        (r"\.npmrc", 60, "NPM config with tokens", ["T1552"]),
        (r"\.pypirc", 60, "PyPI config with tokens", ["T1552"]),
        # Additional high-risk patterns
        (r"\.docker/config\.json", 65, "Docker credentials", ["T1552"]),
        (r"\.netrc", 70, "Netrc credentials", ["T1552"]),
        (r"\.pgpass", 65, "PostgreSQL password", ["T1552"]),
        (r"\.my\.cnf", 65, "MySQL config", ["T1552"]),
        (r"Cookies", 55, "Browser cookies", ["T1539"]),
        (r"\.bash_history", 50, "Bash history", ["T1552", "T1083"]),
        (r"\.zsh_history", 50, "Zsh history", ["T1552", "T1083"]),
        (r"known_hosts", 50, "SSH known hosts", ["T1018"]),  # Remote System Discovery
        (
            r"authorized_keys",
            60,
            "SSH authorized keys",
            ["T1098"],
        ),  # Account Manipulation
    ],
    "medium": [
        (r"\.config/", 30, "Config directory", []),
        (r"\.git/config", 40, "Git config", ["T1552"]),
        (r"auth", 35, "Auth-related file", ["T1552"]),
        (r"\.db$", 35, "Database file", ["T1005"]),  # Data from Local System
        (r"\.sqlite", 35, "SQLite database", ["T1005", "T1539"]),
        (r"\.json$", 25, "JSON config", []),
        # Additional medium-risk patterns
        (r"\.log$", 25, "Log file", ["T1005"]),
        (r"backup", 30, "Backup file", ["T1005"]),
        (r"\.bak$", 30, "Backup file", ["T1005"]),
        (r"\.old$", 25, "Old file version", ["T1005"]),
        (r"\.cache/", 25, "Cache directory", ["T1005"]),
        (r"Downloads/", 25, "Downloads directory", ["T1005"]),
        (r"Desktop/", 25, "Desktop directory", ["T1005"]),
        (r"Documents/", 25, "Documents directory", ["T1005"]),
    ],
}

# URL patterns with MITRE techniques
SENSITIVE_URL_PATTERNS: Dict[str, List[Tuple[str, int, str, List[str]]]] = {
    "critical": [
        (
            r"raw\.githubusercontent\.com.*\.sh$",
            90,
            "Shell script from GitHub",
            ["T1059", "T1105"],
        ),
        (r"pastebin\.com", 85, "Pastebin content", ["T1105"]),  # Ingress Tool Transfer
        (r"hastebin", 85, "Hastebin content", ["T1105"]),
        (r"\.(sh|bash|zsh)$", 80, "Shell script download", ["T1059", "T1105"]),
        (r"\.exe$", 95, "Executable download", ["T1105"]),
        # Additional critical URLs
        (r"ngrok\.io", 80, "Ngrok tunnel", ["T1572", "T1090"]),  # Proxy
        (r"webhook\.site", 75, "Webhook testing site", ["T1048"]),  # Exfiltration
        (r"requestbin", 75, "Request capture", ["T1048"]),
    ],
    "high": [
        (r"raw\.githubusercontent\.com", 55, "Raw GitHub content", ["T1105"]),
        (r"gist\.github", 50, "GitHub Gist", ["T1105"]),
        (r"\.py$", 50, "Python script download", ["T1059", "T1105"]),
        (r"\.js$", 50, "JavaScript download", ["T1059"]),
        # Additional high-risk URLs
        (r"\.tar\.gz$", 45, "Archive download", ["T1105", "T1560"]),
        (r"\.zip$", 45, "Zip download", ["T1105", "T1560"]),
        (r"\.deb$", 55, "Debian package", ["T1105"]),
        (r"\.rpm$", 55, "RPM package", ["T1105"]),
        (r"\.pkg$", 55, "macOS package", ["T1105"]),
        (r"\.dmg$", 55, "macOS disk image", ["T1105"]),
        (r"install\.sh", 60, "Install script", ["T1059", "T1105"]),
        (r"setup\.py", 50, "Python setup script", ["T1059"]),
    ],
    "medium": [
        (r"api\.", 25, "API endpoint", []),
        (r"\.json$", 20, "JSON data", []),
        (r"\.xml$", 20, "XML data", []),
        # Additional medium-risk URLs
        (r"\.sql$", 35, "SQL file", ["T1005"]),
        (r"\.csv$", 25, "CSV data", ["T1005"]),
        (r"\.yaml$", 25, "YAML config", []),
        (r"\.toml$", 25, "TOML config", []),
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
        value: str, patterns: Dict[str, List[Tuple[str, int, str, List[str]]]]
    ) -> Tuple[int, str, List[str]]:
        """Analyze a value against patterns, return max score, reason, and MITRE techniques"""
        value_lower = value.lower()
        max_score = 0
        reason = "Normal"
        mitre_techniques: List[str] = []

        for level in ["critical", "high", "medium"]:
            for entry in patterns.get(level, []):
                pattern, score, desc, mitre = entry
                if re.search(pattern, value_lower):
                    if score > max_score:
                        max_score = score
                        reason = desc
                    # Collect all MITRE techniques
                    for tech in mitre:
                        if tech not in mitre_techniques:
                            mitre_techniques.append(tech)

        return max_score, reason, mitre_techniques

    def analyze_file_path(self, file_path: str, write_mode: bool = False) -> RiskResult:
        """Analyze a file path for security risk"""
        score, reason, mitre = self._analyze_patterns(
            file_path, SENSITIVE_FILE_PATTERNS
        )

        if write_mode and score > 0:
            score = min(100, score + 10)
            reason = f"WRITE: {reason}"

        level = self._score_to_level(score)

        if score == 0:
            reason = "Normal file"

        return RiskResult(
            score=score, level=level, reason=reason, mitre_techniques=mitre
        )

    def analyze_url(self, url: str) -> RiskResult:
        """Analyze a URL for security risk"""
        score, reason, mitre = self._analyze_patterns(url, SENSITIVE_URL_PATTERNS)
        level = self._score_to_level(score)

        if score == 0:
            reason = "Normal URL"

        return RiskResult(
            score=score, level=level, reason=reason, mitre_techniques=mitre
        )


# Singleton instance
_analyzer: Optional[RiskAnalyzer] = None


def get_risk_analyzer() -> RiskAnalyzer:
    """Get the singleton RiskAnalyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = RiskAnalyzer()
    return _analyzer
