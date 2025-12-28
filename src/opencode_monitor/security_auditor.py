"""
Security Auditor - Background scanner for OpenCode command history

Scans OpenCode storage files, analyzes commands for security risks,
and stores results in a local SQLite database for audit purposes.
"""

import hashlib
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from .security import analyze_command
from .database import (
    SecurityDatabase,
    AuditedCommand,
    AuditedFileRead,
    AuditedFileWrite,
    AuditedWebFetch,
)
from .risk_analyzer import get_risk_analyzer
from .reporter import SecurityReporter
from .logger import info, error, debug

# Paths
OPENCODE_STORAGE = Path.home() / ".local/share/opencode/storage/part"

# Scan settings
SCAN_INTERVAL = 30  # seconds between incremental scans


class SecurityAuditor:
    """Background scanner for OpenCode command security analysis"""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._scanned_ids: set = set()

        # Initialize components
        self._db = SecurityDatabase()
        self._analyzer = get_risk_analyzer()
        self._reporter = SecurityReporter()

        # Load cached stats
        self._stats = self._db.get_stats()
        self._stats["last_scan"] = None
        self._scanned_ids = self._db.get_all_scanned_ids()

        info(f"Loaded {len(self._scanned_ids)} scanned file IDs from database")

    def start(self):
        """Start background scanning thread"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._thread.start()
        info("Security auditor started")

    def stop(self):
        """Stop background scanning"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        info("Security auditor stopped")

    def _scan_loop(self):
        """Main scanning loop"""
        self._run_scan()

        while self._running:
            time.sleep(SCAN_INTERVAL)
            if self._running:
                self._run_scan()

    def _run_scan(self):
        """Run a scan for new files"""
        start_time = time.time()
        new_files = 0
        new_counts = {"commands": 0, "reads": 0, "writes": 0, "webfetches": 0}

        if not OPENCODE_STORAGE.exists():
            debug("OpenCode storage not found")
            return

        try:
            for msg_dir in OPENCODE_STORAGE.iterdir():
                if not msg_dir.is_dir():
                    continue

                if not self._running and self._thread is not None:
                    break

                for prt_file in msg_dir.glob("prt_*.json"):
                    file_id = prt_file.name

                    if file_id in self._scanned_ids:
                        continue

                    result = self._process_file(prt_file)
                    if result:
                        result_type = result.get("type")

                        if result_type == "command":
                            if self._db.insert_command(result):
                                new_counts["commands"] += 1
                                self._update_stat(result["risk_level"])
                        elif result_type == "read":
                            if self._db.insert_read(result):
                                new_counts["reads"] += 1
                                self._update_stat(f"reads_{result['risk_level']}")
                        elif result_type == "write":
                            if self._db.insert_write(result):
                                new_counts["writes"] += 1
                                self._update_stat(f"writes_{result['risk_level']}")
                        elif result_type == "webfetch":
                            if self._db.insert_webfetch(result):
                                new_counts["webfetches"] += 1
                                self._update_stat(f"webfetches_{result['risk_level']}")

                    self._scanned_ids.add(file_id)
                    new_files += 1

            # Update totals
            self._stats["total_scanned"] += new_files
            self._stats["total_commands"] += new_counts["commands"]
            self._stats["total_reads"] += new_counts["reads"]
            self._stats["total_writes"] += new_counts["writes"]
            self._stats["total_webfetches"] += new_counts["webfetches"]
            self._stats["last_scan"] = datetime.now().isoformat()

            self._db.update_scan_stats(
                self._stats["total_scanned"],
                self._stats["total_commands"],
                self._stats["last_scan"],
            )

        except Exception as e:
            error(f"Scan error: {e}")

        elapsed = time.time() - start_time
        if new_files > 0:
            debug(f"Scan: {new_files} files, {new_counts} in {elapsed:.2f}s")

    def _update_stat(self, key: str):
        """Increment a stat counter"""
        if key in self._stats:
            self._stats[key] += 1

    def _process_file(self, prt_file: Path) -> Optional[Dict[str, Any]]:
        """Process a single part file"""
        try:
            content = prt_file.read_bytes()
            content_hash = hashlib.md5(content).hexdigest()
            data = json.loads(content)

            if data.get("type") != "tool":
                return None

            tool = data.get("tool", "")
            state = data.get("state", {})
            cmd_input = state.get("input", {})
            base_data = {
                "file_id": prt_file.name,
                "content_hash": content_hash,
                "session_id": data.get("sessionID", ""),
                "timestamp": state.get("time", {}).get("start"),
                "scanned_at": datetime.now().isoformat(),
            }

            if tool == "bash":
                command = cmd_input.get("command", "")
                if not command:
                    return None
                alert = analyze_command(command, tool)
                return {
                    **base_data,
                    "type": "command",
                    "tool": tool,
                    "command": command,
                    "risk_score": alert.score,
                    "risk_level": alert.level.value,
                    "risk_reason": alert.reason,
                }

            elif tool == "read":
                file_path = cmd_input.get("filePath", "")
                if not file_path:
                    return None
                result = self._analyzer.analyze_file_path(file_path)
                return {
                    **base_data,
                    "type": "read",
                    "file_path": file_path,
                    "risk_score": result.score,
                    "risk_level": result.level,
                    "risk_reason": result.reason,
                }

            elif tool in ("write", "edit"):
                file_path = cmd_input.get("filePath", "")
                if not file_path:
                    return None
                result = self._analyzer.analyze_file_path(file_path, write_mode=True)
                return {
                    **base_data,
                    "type": "write",
                    "file_path": file_path,
                    "operation": tool,
                    "risk_score": result.score,
                    "risk_level": result.level,
                    "risk_reason": result.reason,
                }

            elif tool == "webfetch":
                url = cmd_input.get("url", "")
                if not url:
                    return None
                result = self._analyzer.analyze_url(url)
                return {
                    **base_data,
                    "type": "webfetch",
                    "url": url,
                    "risk_score": result.score,
                    "risk_level": result.level,
                    "risk_reason": result.reason,
                }

            return None

        except Exception as e:
            debug(f"Error processing {prt_file}: {e}")
            return None

    # ===== Public API =====

    def get_stats(self) -> Dict[str, Any]:
        """Get current scan statistics"""
        with self._lock:
            return self._stats.copy()

    def get_critical_commands(self, limit: int = 20) -> List[AuditedCommand]:
        """Get recent critical and high risk commands"""
        return self._db.get_commands_by_level(["critical", "high"], limit)

    def get_commands_by_level(
        self, level: str, limit: int = 50
    ) -> List[AuditedCommand]:
        """Get commands by risk level"""
        return self._db.get_commands_by_level([level], limit)

    def get_all_commands(
        self, limit: int = 100, offset: int = 0
    ) -> List[AuditedCommand]:
        """Get all commands with pagination"""
        return self._db.get_all_commands(limit, offset)

    def get_sensitive_reads(self, limit: int = 20) -> List[AuditedFileRead]:
        """Get recent sensitive file reads"""
        return self._db.get_reads_by_level(["critical", "high"], limit)

    def get_all_reads(self, limit: int = 10000) -> List[AuditedFileRead]:
        """Get all file reads"""
        return self._db.get_all_reads(limit)

    def get_sensitive_writes(self, limit: int = 20) -> List[AuditedFileWrite]:
        """Get recent sensitive file writes"""
        return self._db.get_writes_by_level(["critical", "high"], limit)

    def get_all_writes(self, limit: int = 10000) -> List[AuditedFileWrite]:
        """Get all file writes"""
        return self._db.get_all_writes(limit)

    def get_risky_webfetches(self, limit: int = 20) -> List[AuditedWebFetch]:
        """Get recent risky webfetch operations"""
        return self._db.get_webfetches_by_level(["critical", "high"], limit)

    def get_all_webfetches(self, limit: int = 10000) -> List[AuditedWebFetch]:
        """Get all webfetches"""
        return self._db.get_all_webfetches(limit)

    def generate_report(self) -> str:
        """Generate a text report of security findings"""
        return self._reporter.generate_summary_report(
            stats=self.get_stats(),
            critical_cmds=self.get_critical_commands(10),
            sensitive_reads=self.get_sensitive_reads(10),
            sensitive_writes=self.get_sensitive_writes(10),
            risky_fetches=self.get_risky_webfetches(10),
        )


# Global instance
_auditor: Optional[SecurityAuditor] = None


def get_auditor() -> SecurityAuditor:
    """Get or create the global auditor instance"""
    global _auditor
    if _auditor is None:
        _auditor = SecurityAuditor()
    return _auditor


def start_auditor():
    """Start the security auditor"""
    get_auditor().start()


def stop_auditor():
    """Stop the security auditor"""
    global _auditor
    if _auditor:
        _auditor.stop()
        _auditor = None
