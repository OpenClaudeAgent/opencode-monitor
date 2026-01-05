"""
Security Auditor - Background scanner for OpenCode command history

Scans OpenCode storage files, analyzes commands for security risks,
and stores results in a local SQLite database for audit purposes.

Enhanced with EDR-like heuristics:
- Kill chain detection (sequence analysis)
- Multi-event correlation
- MITRE ATT&CK mapping
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from ..analyzer import get_risk_analyzer
from ..db import (
    SecurityDatabase,
    AuditedCommand,
    AuditedFileRead,
    AuditedFileWrite,
    AuditedWebFetch,
)
from ..reporter import SecurityReporter
from ..sequences import SequenceMatch
from ..correlator import Correlation
from ...utils.logger import info, error, debug

from ._constants import OPENCODE_STORAGE, SCAN_INTERVAL
from ._edr_handler import EDRHandler
from ._file_processor import FileProcessor


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

        # EDR handler (encapsulates sequence analyzer and correlator)
        self._edr_handler = EDRHandler(
            buffer_size=100,
            correlator_buffer_size=200,
            window_seconds=300.0,  # 5 minutes
            max_recent=50,
        )

        # File processor
        self._file_processor = FileProcessor(self._analyzer)

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
            # Collect all new files first
            files_to_process: List[Path] = []
            for msg_dir in OPENCODE_STORAGE.iterdir():
                if not msg_dir.is_dir():
                    continue

                if not self._running and self._thread is not None:
                    break

                for prt_file in msg_dir.glob("prt_*.json"):
                    file_id = prt_file.name
                    if file_id not in self._scanned_ids:
                        files_to_process.append(prt_file)

            # For batch scans (many files), disable EDR sequence analysis
            # to avoid false positives from out-of-order processing
            is_batch_scan = len(files_to_process) > 50
            if is_batch_scan:
                # Clear EDR buffers before batch scan to avoid stale data
                self._edr_handler.clear_all()

            # Process files
            for prt_file in files_to_process:
                if not self._running and self._thread is not None:
                    break

                file_id = prt_file.name
                # For batch scans, skip EDR analysis
                result = self._process_file(prt_file, skip_edr=is_batch_scan)
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

        except (
            Exception
        ) as e:  # Intentional catch-all: scan errors logged, scan continues next cycle
            error(f"Scan error: {e}")

        elapsed = time.time() - start_time
        if new_files > 0:
            debug(f"Scan: {new_files} files, {new_counts} in {elapsed:.2f}s")

    def _update_stat(self, key: str):
        """Increment a stat counter"""
        if key in self._stats:
            self._stats[key] += 1

    def _process_file(
        self, prt_file: Path, skip_edr: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Process a single part file

        Args:
            prt_file: Path to the part file to process
            skip_edr: If True, skip EDR sequence/correlation analysis
                      (used during batch scans to avoid false positives)
        """
        return self._file_processor.process_file(
            prt_file,
            edr_processor=self._edr_handler,
            skip_edr=skip_edr,
        )

    # ===== Legacy compatibility methods =====
    # These are kept for backwards compatibility with existing code

    def _process_edr_analysis(
        self,
        tool: str,
        target: str,
        session_id: str,
        timestamp: Optional[float],
        risk_score: int,
    ) -> Dict[str, Any]:
        """Process event through EDR analyzers - delegates to EDRHandler."""
        return self._edr_handler.process_event(
            tool=tool,
            target=target,
            session_id=session_id,
            timestamp=timestamp,
            risk_score=risk_score,
        )

    def _apply_edr_and_build_result(
        self,
        base_data: Dict[str, Any],
        tool: str,
        target: str,
        event_type: str,
        analysis_score: int,
        analysis_level: str,
        analysis_reason: str,
        analysis_mitre: List[str],
        skip_edr: bool,
        empty_edr: Dict[str, Any],
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Apply EDR analysis and build the final result - delegates to file processor."""
        from ._file_processor import build_audit_result

        edr = (
            empty_edr
            if skip_edr
            else self._process_edr_analysis(
                tool=tool,
                target=target,
                session_id=base_data["session_id"],
                timestamp=base_data["timestamp"],
                risk_score=analysis_score,
            )
        )

        return build_audit_result(
            base_data=base_data,
            event_type=event_type,
            analysis_score=analysis_score,
            analysis_level=analysis_level,
            analysis_reason=analysis_reason,
            analysis_mitre=analysis_mitre,
            edr_result=edr,
            extra_fields=extra_fields,
        )

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
        return self._edr_handler.get_recent_sequences()

    def get_recent_correlations(self) -> List[Correlation]:
        """Get recently detected event correlations"""
        return self._edr_handler.get_recent_correlations()

    def get_session_events(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all tracked events for a session"""
        return self._edr_handler.get_session_events(session_id)

    def get_edr_stats(self) -> Dict[str, Any]:
        """Get EDR-specific statistics"""
        edr_stats = self._edr_handler.get_stats()
        with self._lock:
            # Merge with main stats for backwards compatibility
            return {
                "sequences_detected": self._stats.get("sequences_detected", 0)
                + edr_stats["sequences_detected"],
                "correlations_detected": self._stats.get("correlations_detected", 0)
                + edr_stats["correlations_detected"],
                "active_sessions": edr_stats["active_sessions"],
                "recent_sequences": edr_stats["recent_sequences"],
                "recent_correlations": edr_stats["recent_correlations"],
            }

    def clear_edr_buffers(self) -> None:
        """Clear all EDR analyzer buffers (useful for testing)"""
        self._edr_handler.clear_all()

    # ===== Legacy EDR properties for backwards compatibility =====

    @property
    def _sequence_analyzer(self):
        """Access to sequence analyzer for backwards compatibility."""
        return self._edr_handler._sequence_analyzer

    @property
    def _event_correlator(self):
        """Access to event correlator for backwards compatibility."""
        return self._edr_handler._event_correlator

    @property
    def _recent_sequences(self) -> List[SequenceMatch]:
        """Access to recent sequences for backwards compatibility."""
        return self._edr_handler._recent_sequences

    @property
    def _recent_correlations(self) -> List[Correlation]:
        """Access to recent correlations for backwards compatibility."""
        return self._edr_handler._recent_correlations

    @property
    def _max_recent(self) -> int:
        """Access to max_recent for backwards compatibility."""
        return self._edr_handler._max_recent


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
