"""
Risk Analyzer - Pattern-based security risk analysis for files and URLs
"""

import re
from dataclasses import dataclass
from typing import Tuple, Dict, List

# Sensitive file patterns for read/write operations
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

# URL patterns for webfetch risk analysis
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


@dataclass
class RiskResult:
    """Result of a risk analysis"""

    score: int
    level: str
    reason: str


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
        """Analyze a file path for security risk

        Args:
            file_path: The file path to analyze
            write_mode: If True, adds bonus score for write/edit operations

        Returns:
            RiskResult with score, level, and reason
        """
        score, reason = self._analyze_patterns(file_path, SENSITIVE_FILE_PATTERNS)

        # Write/edit operations are inherently more risky
        if write_mode and score > 0:
            score = min(100, score + 10)
            reason = f"WRITE: {reason}"

        level = self._score_to_level(score)

        if score == 0:
            reason = "Normal file"

        return RiskResult(score=score, level=level, reason=reason)

    def analyze_url(self, url: str) -> RiskResult:
        """Analyze a URL for security risk

        Args:
            url: The URL to analyze

        Returns:
            RiskResult with score, level, and reason
        """
        score, reason = self._analyze_patterns(url, SENSITIVE_URL_PATTERNS)
        level = self._score_to_level(score)

        if score == 0:
            reason = "Normal URL"

        return RiskResult(score=score, level=level, reason=reason)


from typing import Optional

# Singleton instance
_analyzer: Optional[RiskAnalyzer] = None


def get_risk_analyzer() -> RiskAnalyzer:
    """Get the singleton RiskAnalyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = RiskAnalyzer()
    return _analyzer
