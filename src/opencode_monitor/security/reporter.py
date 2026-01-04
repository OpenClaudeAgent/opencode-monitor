"""
Security Reporter - Generate security audit reports
"""

import json
from datetime import datetime
from typing import Dict, Any, List
from collections import Counter

from .db import AuditedCommand, AuditedFileRead, AuditedFileWrite, AuditedWebFetch


class SecurityReporter:
    """Generates security audit reports"""

    def generate_summary_report(
        self,
        stats: Dict[str, Any],
        critical_cmds: List[AuditedCommand],
        sensitive_reads: List[AuditedFileRead],
        sensitive_writes: List[AuditedFileWrite],
        risky_fetches: List[AuditedWebFetch],
    ) -> str:
        """Generate a text summary report of security findings"""
        lines = [
            "=" * 60,
            "OPENCODE SECURITY AUDIT REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            "",
            "SUMMARY",
            "-" * 40,
            f"Total files scanned: {stats.get('total_scanned', 0)}",
            f"Total commands: {stats.get('total_commands', 0)}",
            f"Total file reads: {stats.get('total_reads', 0)}",
            f"Total file writes: {stats.get('total_writes', 0)}",
            f"Total webfetches: {stats.get('total_webfetches', 0)}",
            f"Last scan: {stats.get('last_scan') or 'Never'}",
            "",
        ]

        # Commands distribution
        lines.extend(self._format_distribution("COMMANDS", stats, ""))

        # Reads distribution
        lines.extend(self._format_distribution("FILE READS", stats, "reads_"))

        # Writes distribution
        lines.extend(self._format_distribution("FILE WRITES", stats, "writes_"))

        # Webfetches distribution
        lines.extend(self._format_distribution("WEBFETCHES", stats, "webfetches_"))

        # EDR Heuristics section
        lines.extend(self._format_edr_stats(stats))

        # MITRE ATT&CK section
        lines.extend(
            self._format_mitre_summary(
                critical_cmds, sensitive_reads, sensitive_writes, risky_fetches
            )
        )

        # Top items
        if critical_cmds:
            lines.extend(
                self._format_commands("TOP CRITICAL/HIGH RISK COMMANDS", critical_cmds)
            )

        if sensitive_reads:
            lines.extend(
                self._format_reads("TOP SENSITIVE FILE READS", sensitive_reads)
            )

        if sensitive_writes:
            lines.extend(
                self._format_writes("TOP SENSITIVE FILE WRITES/EDITS", sensitive_writes)
            )

        if risky_fetches:
            lines.extend(self._format_fetches("TOP RISKY WEBFETCHES", risky_fetches))

        lines.append("=" * 60)
        return "\n".join(lines)

    def _format_distribution(
        self, title: str, stats: Dict[str, Any], prefix: str
    ) -> List[str]:
        """Format risk distribution section"""
        return [
            f"{title} - RISK DISTRIBUTION",
            "-" * 40,
            f"🔴 Critical: {stats.get(f'{prefix}critical', 0)}",
            f"🟠 High:     {stats.get(f'{prefix}high', 0)}",
            f"🟡 Medium:   {stats.get(f'{prefix}medium', 0)}",
            f"🟢 Low:      {stats.get(f'{prefix}low', 0)}",
            "",
        ]

    def _format_edr_stats(self, stats: Dict[str, Any]) -> List[str]:
        """Format EDR heuristics statistics"""
        edr_sequences = stats.get("edr_sequences", 0)
        edr_correlations = stats.get("edr_correlations", 0)
        mitre_tagged = stats.get("mitre_tagged", 0)

        if edr_sequences == 0 and edr_correlations == 0 and mitre_tagged == 0:
            return []

        return [
            "EDR HEURISTICS",
            "-" * 40,
            f"⛓️ Kill chains detected: {edr_sequences}",
            f"🔗 Event correlations: {edr_correlations}",
            f"🎯 MITRE tagged events: {mitre_tagged}",
            "",
        ]

    def _format_mitre_summary(
        self,
        commands: List[AuditedCommand],
        reads: List[AuditedFileRead],
        writes: List[AuditedFileWrite],
        fetches: List[AuditedWebFetch],
    ) -> List[str]:
        """Format MITRE ATT&CK techniques summary"""
        # Collect all MITRE techniques
        techniques: Counter = Counter()

        for items in [commands, reads, writes, fetches]:
            for item in items:
                mitre_json = getattr(item, "mitre_techniques", None)
                if mitre_json:
                    try:
                        mitre_list = (
                            json.loads(mitre_json)
                            if isinstance(mitre_json, str)
                            else mitre_json
                        )
                        for tech in mitre_list:
                            techniques[tech] += 1
                    except (json.JSONDecodeError, TypeError):
                        pass

        if not techniques:
            return []

        lines = [
            "MITRE ATT&CK TECHNIQUES",
            "-" * 40,
        ]

        # Sort by count descending
        for tech, count in techniques.most_common(15):
            lines.append(f"  {tech}: {count} occurrences")

        lines.append("")
        return lines

    def _format_commands(self, title: str, commands: List[AuditedCommand]) -> List[str]:
        """Format commands section"""
        lines = [title, "-" * 40]
        for cmd in commands:
            emoji = "🔴" if cmd.risk_level == "critical" else "🟠"
            mitre_str = self._get_mitre_str(getattr(cmd, "mitre_techniques", None))
            edr_str = self._get_edr_str(
                getattr(cmd, "edr_sequence_bonus", 0),
                getattr(cmd, "edr_correlation_bonus", 0),
            )
            lines.extend(
                [
                    f"{emoji} [{cmd.risk_score}] {cmd.risk_reason}",
                    f"   {cmd.command}",
                ]
            )
            if mitre_str:
                lines.append(f"   🎯 {mitre_str}")
            if edr_str:
                lines.append(f"   {edr_str}")
            lines.append("")
        return lines

    def _get_mitre_str(self, mitre_json: Any) -> str:
        """Extract MITRE techniques as string"""
        if not mitre_json:
            return ""
        try:
            mitre_list = (
                json.loads(mitre_json) if isinstance(mitre_json, str) else mitre_json
            )
            if mitre_list:
                return f"MITRE: {', '.join(mitre_list)}"
        except (json.JSONDecodeError, TypeError):
            pass
        return ""

    def _get_edr_str(self, seq_bonus: Any, corr_bonus: Any) -> str:
        """Format EDR bonuses as string"""
        seq = int(seq_bonus or 0)
        corr = int(corr_bonus or 0)
        if seq > 0 or corr > 0:
            parts = []
            if seq > 0:
                parts.append(f"⛓️ Sequence: +{seq}")
            if corr > 0:
                parts.append(f"🔗 Correlation: +{corr}")
            return " | ".join(parts)
        return ""

    def _format_reads(self, title: str, reads: List[AuditedFileRead]) -> List[str]:
        """Format file reads section"""
        lines = [title, "-" * 40]
        for read in reads:
            emoji = "🔴" if read.risk_level == "critical" else "🟠"
            mitre_str = self._get_mitre_str(getattr(read, "mitre_techniques", None))
            edr_str = self._get_edr_str(
                getattr(read, "edr_sequence_bonus", 0),
                getattr(read, "edr_correlation_bonus", 0),
            )
            lines.extend(
                [
                    f"{emoji} [{read.risk_score}] {read.risk_reason}",
                    f"   {read.file_path}",
                ]
            )
            if mitre_str:
                lines.append(f"   🎯 {mitre_str}")
            if edr_str:
                lines.append(f"   {edr_str}")
            lines.append("")
        return lines

    def _format_writes(self, title: str, writes: List[AuditedFileWrite]) -> List[str]:
        """Format file writes section"""
        lines = [title, "-" * 40]
        for write in writes:
            emoji = "🔴" if write.risk_level == "critical" else "🟠"
            mitre_str = self._get_mitre_str(getattr(write, "mitre_techniques", None))
            edr_str = self._get_edr_str(
                getattr(write, "edr_sequence_bonus", 0),
                getattr(write, "edr_correlation_bonus", 0),
            )
            lines.extend(
                [
                    f"{emoji} [{write.risk_score}] {write.risk_reason} ({write.operation})",
                    f"   {write.file_path}",
                ]
            )
            if mitre_str:
                lines.append(f"   🎯 {mitre_str}")
            if edr_str:
                lines.append(f"   {edr_str}")
            lines.append("")
        return lines

    def _format_fetches(self, title: str, fetches: List[AuditedWebFetch]) -> List[str]:
        """Format webfetches section"""
        lines = [title, "-" * 40]
        for fetch in fetches:
            emoji = "🔴" if fetch.risk_level == "critical" else "🟠"
            mitre_str = self._get_mitre_str(getattr(fetch, "mitre_techniques", None))
            edr_str = self._get_edr_str(
                getattr(fetch, "edr_sequence_bonus", 0),
                getattr(fetch, "edr_correlation_bonus", 0),
            )
            lines.extend(
                [
                    f"{emoji} [{fetch.risk_score}] {fetch.risk_reason}",
                    f"   {fetch.url}",
                ]
            )
            if mitre_str:
                lines.append(f"   🎯 {mitre_str}")
            if edr_str:
                lines.append(f"   {edr_str}")
            lines.append("")
        return lines

    def generate_full_export(
        self,
        commands: List[AuditedCommand],
        reads: List[AuditedFileRead],
        writes: List[AuditedFileWrite],
        fetches: List[AuditedWebFetch],
    ) -> str:
        """Generate a complete export of all audit data"""
        lines = [
            "=" * 80,
            "OPENCODE SECURITY AUDIT LOG",
            f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total commands: {len(commands)}",
            f"Total file reads: {len(reads)}",
            f"Total file writes: {len(writes)}",
            f"Total webfetches: {len(fetches)}",
            "=" * 80,
            "",
        ]

        # Commands section
        lines.extend(
            self._export_section("BASH COMMANDS", commands, self._export_command)
        )

        # Reads section
        lines.extend(self._export_section("FILE READS", reads, self._export_read))

        # Writes section
        lines.extend(
            self._export_section("FILE WRITES/EDITS", writes, self._export_write)
        )

        # Fetches section
        lines.extend(self._export_section("WEB FETCHES", fetches, self._export_fetch))

        return "\n".join(lines)

    def _export_section(self, title: str, items: list, formatter) -> List[str]:
        """Export a section grouped by risk level"""
        lines = ["", "█" * 40, title, "█" * 40]

        for level in ["critical", "high", "medium", "low"]:
            level_items = [i for i in items if i.risk_level == level]
            if level_items:
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[
                    level
                ]
                lines.extend(
                    [
                        f"\n{'=' * 40}",
                        f"{emoji} {level.upper()} ({len(level_items)} items)",
                        "=" * 40,
                    ]
                )
                for item in level_items:
                    lines.extend(formatter(item))

        return lines

    def _export_command(self, cmd: AuditedCommand) -> List[str]:
        """Format a command for export"""
        ts = self._format_timestamp(cmd.timestamp)
        mitre_str = self._get_mitre_str(getattr(cmd, "mitre_techniques", None))
        edr_str = self._get_edr_str(
            getattr(cmd, "edr_sequence_bonus", 0),
            getattr(cmd, "edr_correlation_bonus", 0),
        )
        lines = [
            f"\n[{ts}] Score: {cmd.risk_score} - {cmd.risk_reason}",
            f"Session: {cmd.session_id}",
            f"Command: {cmd.command}",
        ]
        if mitre_str:
            lines.append(f"MITRE: {mitre_str}")
        if edr_str:
            lines.append(f"EDR: {edr_str}")
        lines.append("-" * 40)
        return lines

    def _export_read(self, read: AuditedFileRead) -> List[str]:
        """Format a file read for export"""
        ts = self._format_timestamp(read.timestamp)
        mitre_str = self._get_mitre_str(getattr(read, "mitre_techniques", None))
        edr_str = self._get_edr_str(
            getattr(read, "edr_sequence_bonus", 0),
            getattr(read, "edr_correlation_bonus", 0),
        )
        lines = [
            f"\n[{ts}] Score: {read.risk_score} - {read.risk_reason}",
            f"Session: {read.session_id}",
            f"File: {read.file_path}",
        ]
        if mitre_str:
            lines.append(f"MITRE: {mitre_str}")
        if edr_str:
            lines.append(f"EDR: {edr_str}")
        lines.append("-" * 40)
        return lines

    def _export_write(self, write: AuditedFileWrite) -> List[str]:
        """Format a file write for export"""
        ts = self._format_timestamp(write.timestamp)
        mitre_str = self._get_mitre_str(getattr(write, "mitre_techniques", None))
        edr_str = self._get_edr_str(
            getattr(write, "edr_sequence_bonus", 0),
            getattr(write, "edr_correlation_bonus", 0),
        )
        lines = [
            f"\n[{ts}] Score: {write.risk_score} - {write.risk_reason}",
            f"Session: {write.session_id}",
            f"Operation: {write.operation}",
            f"File: {write.file_path}",
        ]
        if mitre_str:
            lines.append(f"MITRE: {mitre_str}")
        if edr_str:
            lines.append(f"EDR: {edr_str}")
        lines.append("-" * 40)
        return lines

    def _export_fetch(self, fetch: AuditedWebFetch) -> List[str]:
        """Format a webfetch for export"""
        ts = self._format_timestamp(fetch.timestamp)
        mitre_str = self._get_mitre_str(getattr(fetch, "mitre_techniques", None))
        edr_str = self._get_edr_str(
            getattr(fetch, "edr_sequence_bonus", 0),
            getattr(fetch, "edr_correlation_bonus", 0),
        )
        lines = [
            f"\n[{ts}] Score: {fetch.risk_score} - {fetch.risk_reason}",
            f"Session: {fetch.session_id}",
            f"URL: {fetch.url}",
        ]
        if mitre_str:
            lines.append(f"MITRE: {mitre_str}")
        if edr_str:
            lines.append(f"EDR: {edr_str}")
        lines.append("-" * 40)
        return lines

    @staticmethod
    def _format_timestamp(ts: int) -> str:
        """Format a timestamp for display"""
        if ts:
            return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")
        return "N/A"
