"""
Security Auditor - Background scanner for OpenCode command history

Scans OpenCode storage files, analyzes commands for security risks,
and stores results in a local SQLite database for audit purposes.

Enhanced with EDR-like heuristics:
- Kill chain detection (sequence analysis)
- Multi-event correlation
- MITRE ATT&CK mapping
"""

import hashlib
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from .analyzer import analyze_command, get_risk_analyzer
from .db import (
    SecurityDatabase,
    AuditedCommand,
    AuditedFileRead,
    AuditedFileWrite,
    AuditedWebFetch,
)
from .reporter import SecurityReporter
from .sequences import SequenceAnalyzer, SequenceMatch, create_event_from_audit_data
from .correlator import EventCorrelator, Correlation
from ..utils.logger import info, error, debug

# Paths
OPENCODE_STORAGE = Path.home() / ".local/share/opencode/storage/part"

# Scan settings
SCAN_INTERVAL = 30  # seconds between incremental scans


class SecurityAuditor:
    """Background scanner for OpenCode command security analysis

    Enhanced with EDR-like heuristics:
    - SequenceAnalyzer: Detects kill chain patterns
    - EventCorrelator: Correlates related events
    - MITRE ATT&CK: Techniques tagged on all alerts
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._scanned_ids: set = set()

        # Initialize components
        self._db = SecurityDatabase()
        self._analyzer = get_risk_analyzer()
        self._reporter = SecurityReporter()

        # EDR components
        self._sequence_analyzer = SequenceAnalyzer(
            buffer_size=100,
            default_window_seconds=300.0,  # 5 minutes
        )
        self._event_correlator = EventCorrelator(
            buffer_size=200,
            default_window_seconds=300.0,
        )

        # Detected sequences and correlations (recent)
        self._recent_sequences: List[SequenceMatch] = []
        self._recent_correlations: List[Correlation] = []
        self._max_recent = 50

        # Load cached stats
        self._stats = self._db.get_stats()
        self._stats["last_scan"] = None
        self._stats["sequences_detected"] = 0
        self._stats["correlations_detected"] = 0
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

    def _process_edr_analysis(
        self,
        tool: str,
        target: str,
        session_id: str,
        timestamp: Optional[float],
        risk_score: int,
    ) -> Dict[str, Any]:
        """
        Process event through EDR analyzers (sequence + correlation).

        Returns dict with:
        - sequences: List of detected kill chains
        - correlations: List of detected correlations
        - sequence_score_bonus: Additional score from sequences
        - correlation_score_bonus: Additional score from correlations
        - mitre_from_edr: MITRE techniques from EDR analysis
        """
        # Convert timestamp from milliseconds if needed
        ts = (
            timestamp / 1000.0
            if timestamp and timestamp > 1e10
            else timestamp or time.time()
        )

        # Create security event
        event = create_event_from_audit_data(
            tool=tool,
            target=target,
            session_id=session_id,
            timestamp=ts,
            risk_score=risk_score,
        )

        # Analyze with sequence analyzer
        sequences = self._sequence_analyzer.add_event(event)

        # Check for mass deletion
        mass_del = self._sequence_analyzer.check_mass_deletion(session_id)
        if mass_del:
            sequences.append(mass_del)

        # Analyze with event correlator
        correlations = self._event_correlator.add_event(event)

        # Collect results
        sequence_score_bonus = sum(s.score_bonus for s in sequences)
        correlation_score_bonus = sum(c.score_modifier for c in correlations)

        mitre_from_edr: List[str] = []
        for seq in sequences:
            if seq.mitre_technique and seq.mitre_technique not in mitre_from_edr:
                mitre_from_edr.append(seq.mitre_technique)
        for corr in correlations:
            if corr.mitre_technique and corr.mitre_technique not in mitre_from_edr:
                mitre_from_edr.append(corr.mitre_technique)

        # Store recent detections
        with self._lock:
            for seq in sequences:
                self._recent_sequences.append(seq)
                self._stats["sequences_detected"] = (
                    self._stats.get("sequences_detected", 0) + 1
                )
            for corr in correlations:
                self._recent_correlations.append(corr)
                self._stats["correlations_detected"] = (
                    self._stats.get("correlations_detected", 0) + 1
                )

            # Trim to max recent
            if len(self._recent_sequences) > self._max_recent:
                self._recent_sequences = self._recent_sequences[-self._max_recent :]
            if len(self._recent_correlations) > self._max_recent:
                self._recent_correlations = self._recent_correlations[
                    -self._max_recent :
                ]

        return {
            "sequences": sequences,
            "correlations": correlations,
            "sequence_score_bonus": sequence_score_bonus,
            "correlation_score_bonus": correlation_score_bonus,
            "mitre_from_edr": mitre_from_edr,
        }

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

                # EDR analysis
                edr = self._process_edr_analysis(
                    tool=tool,
                    target=command,
                    session_id=base_data["session_id"],
                    timestamp=base_data["timestamp"],
                    risk_score=alert.score,
                )

                # Combine MITRE techniques
                all_mitre = list(alert.mitre_techniques)
                for tech in edr["mitre_from_edr"]:
                    if tech not in all_mitre:
                        all_mitre.append(tech)

                # Apply EDR score bonuses (capped at 100)
                final_score = min(
                    100,
                    alert.score
                    + edr["sequence_score_bonus"]
                    + edr["correlation_score_bonus"],
                )

                return {
                    **base_data,
                    "type": "command",
                    "tool": tool,
                    "command": command,
                    "risk_score": final_score,
                    "risk_level": alert.level.value,
                    "risk_reason": alert.reason,
                    "mitre_techniques": all_mitre,
                    "edr_sequence_bonus": edr["sequence_score_bonus"],
                    "edr_correlation_bonus": edr["correlation_score_bonus"],
                }

            elif tool == "read":
                file_path = cmd_input.get("filePath", "")
                if not file_path:
                    return None
                result = self._analyzer.analyze_file_path(file_path)

                # EDR analysis
                edr = self._process_edr_analysis(
                    tool=tool,
                    target=file_path,
                    session_id=base_data["session_id"],
                    timestamp=base_data["timestamp"],
                    risk_score=result.score,
                )

                all_mitre = list(result.mitre_techniques)
                for tech in edr["mitre_from_edr"]:
                    if tech not in all_mitre:
                        all_mitre.append(tech)

                final_score = min(
                    100,
                    result.score
                    + edr["sequence_score_bonus"]
                    + edr["correlation_score_bonus"],
                )

                return {
                    **base_data,
                    "type": "read",
                    "file_path": file_path,
                    "risk_score": final_score,
                    "risk_level": result.level,
                    "risk_reason": result.reason,
                    "mitre_techniques": all_mitre,
                    "edr_sequence_bonus": edr["sequence_score_bonus"],
                    "edr_correlation_bonus": edr["correlation_score_bonus"],
                }

            elif tool in ("write", "edit"):
                file_path = cmd_input.get("filePath", "")
                if not file_path:
                    return None
                result = self._analyzer.analyze_file_path(file_path, write_mode=True)

                # EDR analysis
                edr = self._process_edr_analysis(
                    tool=tool,
                    target=file_path,
                    session_id=base_data["session_id"],
                    timestamp=base_data["timestamp"],
                    risk_score=result.score,
                )

                all_mitre = list(result.mitre_techniques)
                for tech in edr["mitre_from_edr"]:
                    if tech not in all_mitre:
                        all_mitre.append(tech)

                final_score = min(
                    100,
                    result.score
                    + edr["sequence_score_bonus"]
                    + edr["correlation_score_bonus"],
                )

                return {
                    **base_data,
                    "type": "write",
                    "file_path": file_path,
                    "operation": tool,
                    "risk_score": final_score,
                    "risk_level": result.level,
                    "risk_reason": result.reason,
                    "mitre_techniques": all_mitre,
                    "edr_sequence_bonus": edr["sequence_score_bonus"],
                    "edr_correlation_bonus": edr["correlation_score_bonus"],
                }

            elif tool == "webfetch":
                url = cmd_input.get("url", "")
                if not url:
                    return None
                result = self._analyzer.analyze_url(url)

                # EDR analysis
                edr = self._process_edr_analysis(
                    tool=tool,
                    target=url,
                    session_id=base_data["session_id"],
                    timestamp=base_data["timestamp"],
                    risk_score=result.score,
                )

                all_mitre = list(result.mitre_techniques)
                for tech in edr["mitre_from_edr"]:
                    if tech not in all_mitre:
                        all_mitre.append(tech)

                final_score = min(
                    100,
                    result.score
                    + edr["sequence_score_bonus"]
                    + edr["correlation_score_bonus"],
                )

                return {
                    **base_data,
                    "type": "webfetch",
                    "url": url,
                    "risk_score": final_score,
                    "risk_level": result.level,
                    "risk_reason": result.reason,
                    "mitre_techniques": all_mitre,
                    "edr_sequence_bonus": edr["sequence_score_bonus"],
                    "edr_correlation_bonus": edr["correlation_score_bonus"],
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

    # ===== EDR API =====

    def get_recent_sequences(self) -> List[SequenceMatch]:
        """Get recently detected kill chain sequences"""
        with self._lock:
            return self._recent_sequences.copy()

    def get_recent_correlations(self) -> List[Correlation]:
        """Get recently detected event correlations"""
        with self._lock:
            return self._recent_correlations.copy()

    def get_session_events(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all tracked events for a session"""
        sequence_events = self._sequence_analyzer.get_session_buffer(session_id)
        return [
            {
                "type": e.event_type.value,
                "target": e.target,
                "timestamp": e.timestamp,
                "risk_score": e.risk_score,
            }
            for e in sequence_events
        ]

    def get_edr_stats(self) -> Dict[str, Any]:
        """Get EDR-specific statistics"""
        with self._lock:
            return {
                "sequences_detected": self._stats.get("sequences_detected", 0),
                "correlations_detected": self._stats.get("correlations_detected", 0),
                "active_sessions": len(self._sequence_analyzer.get_active_sessions()),
                "recent_sequences": len(self._recent_sequences),
                "recent_correlations": len(self._recent_correlations),
            }

    def clear_edr_buffers(self) -> None:
        """Clear all EDR analyzer buffers (useful for testing)"""
        self._sequence_analyzer.clear_all()
        self._event_correlator.clear_all()
        with self._lock:
            self._recent_sequences.clear()
            self._recent_correlations.clear()


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
