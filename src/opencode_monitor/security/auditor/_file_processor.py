"""
File processing logic for the security auditor.

Handles parsing of OpenCode part files and building audit results.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..analyzer import analyze_command, RiskAnalyzer
from ...utils.logger import debug


def build_audit_result(
    base_data: Dict[str, Any],
    event_type: str,
    analysis_score: int,
    analysis_level: str,
    analysis_reason: str,
    analysis_mitre: List[str],
    edr_result: Dict[str, Any],
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build the final audit result dictionary.

    Consolidates common post-analysis logic:
    - MITRE technique aggregation
    - Final score calculation with EDR bonuses
    - Result dictionary construction

    Args:
        base_data: Common fields (file_id, content_hash, session_id, timestamp, scanned_at)
        event_type: Type for the result dict (command, read, write, webfetch)
        analysis_score: Risk score from analyzer
        analysis_level: Risk level from analyzer (as string)
        analysis_reason: Risk reason from analyzer
        analysis_mitre: MITRE techniques from analyzer
        edr_result: EDR analysis result dict
        extra_fields: Additional fields specific to each tool type

    Returns:
        Complete audit result dictionary
    """
    # Merge MITRE techniques
    all_mitre = list(analysis_mitre)
    for tech in edr_result.get("mitre_from_edr", []):
        if tech not in all_mitre:
            all_mitre.append(tech)

    # Calculate final score with EDR bonuses (capped at 100)
    final_score = min(
        100,
        analysis_score
        + edr_result.get("sequence_score_bonus", 0)
        + edr_result.get("correlation_score_bonus", 0),
    )

    # Build result dictionary
    result_dict = {
        **base_data,
        "type": event_type,
        "risk_score": final_score,
        "risk_level": analysis_level,
        "risk_reason": analysis_reason,
        "mitre_techniques": all_mitre,
        "edr_sequence_bonus": edr_result.get("sequence_score_bonus", 0),
        "edr_correlation_bonus": edr_result.get("correlation_score_bonus", 0),
    }

    # Add extra fields specific to each tool type
    if extra_fields:
        result_dict.update(extra_fields)

    return result_dict


class FileProcessor:
    """Processes OpenCode part files for security analysis.

    Handles parsing of part files and routing to appropriate analyzers
    based on tool type.
    """

    # Empty EDR result for batch scans
    EMPTY_EDR = {
        "sequences": [],
        "correlations": [],
        "sequence_score_bonus": 0,
        "correlation_score_bonus": 0,
        "mitre_from_edr": [],
    }

    def __init__(self, analyzer: RiskAnalyzer):
        self._analyzer = analyzer

    def process_file(
        self,
        prt_file: Path,
        edr_processor: Optional[Any] = None,
        skip_edr: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Process a single part file.

        Args:
            prt_file: Path to the part file to process
            edr_processor: EDRHandler instance for EDR analysis
            skip_edr: If True, skip EDR sequence/correlation analysis
                      (used during batch scans to avoid false positives)

        Returns:
            Audit result dictionary or None if file should be skipped
        """
        try:
            content = prt_file.read_bytes()
            content_hash = hashlib.md5(content, usedforsecurity=False).hexdigest()
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
                return self._process_bash(
                    cmd_input, base_data, tool, edr_processor, skip_edr
                )
            elif tool == "read":
                return self._process_read(
                    cmd_input, base_data, tool, edr_processor, skip_edr
                )
            elif tool in ("write", "edit"):
                return self._process_write(
                    cmd_input, base_data, tool, edr_processor, skip_edr
                )
            elif tool == "webfetch":
                return self._process_webfetch(
                    cmd_input, base_data, tool, edr_processor, skip_edr
                )

            return None

        except Exception as e:
            debug(f"Error processing {prt_file}: {e}")
            return None

    def _get_edr_result(
        self,
        edr_processor: Optional[Any],
        skip_edr: bool,
        tool: str,
        target: str,
        base_data: Dict[str, Any],
        risk_score: int,
    ) -> Dict[str, Any]:
        """Get EDR analysis result or empty result if skipped."""
        if skip_edr or edr_processor is None:
            return self.EMPTY_EDR
        return edr_processor.process_event(
            tool=tool,
            target=target,
            session_id=base_data["session_id"],
            timestamp=base_data["timestamp"],
            risk_score=risk_score,
        )

    def _process_bash(
        self,
        cmd_input: Dict[str, Any],
        base_data: Dict[str, Any],
        tool: str,
        edr_processor: Optional[Any],
        skip_edr: bool,
    ) -> Optional[Dict[str, Any]]:
        """Process bash command."""
        command = cmd_input.get("command", "")
        if not command:
            return None
        alert = analyze_command(command, tool)

        edr = self._get_edr_result(
            edr_processor, skip_edr, tool, command, base_data, alert.score
        )

        return build_audit_result(
            base_data=base_data,
            event_type="command",
            analysis_score=alert.score,
            analysis_level=alert.level.value,
            analysis_reason=alert.reason,
            analysis_mitre=list(alert.mitre_techniques),
            edr_result=edr,
            extra_fields={"tool": tool, "command": command},
        )

    def _process_read(
        self,
        cmd_input: Dict[str, Any],
        base_data: Dict[str, Any],
        tool: str,
        edr_processor: Optional[Any],
        skip_edr: bool,
    ) -> Optional[Dict[str, Any]]:
        """Process file read."""
        file_path = cmd_input.get("filePath", "")
        if not file_path:
            return None
        result = self._analyzer.analyze_file_path(file_path)

        edr = self._get_edr_result(
            edr_processor, skip_edr, tool, file_path, base_data, result.score
        )

        return build_audit_result(
            base_data=base_data,
            event_type="read",
            analysis_score=result.score,
            analysis_level=result.level,
            analysis_reason=result.reason,
            analysis_mitre=list(result.mitre_techniques),
            edr_result=edr,
            extra_fields={"file_path": file_path},
        )

    def _process_write(
        self,
        cmd_input: Dict[str, Any],
        base_data: Dict[str, Any],
        tool: str,
        edr_processor: Optional[Any],
        skip_edr: bool,
    ) -> Optional[Dict[str, Any]]:
        """Process file write/edit."""
        file_path = cmd_input.get("filePath", "")
        if not file_path:
            return None
        result = self._analyzer.analyze_file_path(file_path, write_mode=True)

        edr = self._get_edr_result(
            edr_processor, skip_edr, tool, file_path, base_data, result.score
        )

        return build_audit_result(
            base_data=base_data,
            event_type="write",
            analysis_score=result.score,
            analysis_level=result.level,
            analysis_reason=result.reason,
            analysis_mitre=list(result.mitre_techniques),
            edr_result=edr,
            extra_fields={"file_path": file_path, "operation": tool},
        )

    def _process_webfetch(
        self,
        cmd_input: Dict[str, Any],
        base_data: Dict[str, Any],
        tool: str,
        edr_processor: Optional[Any],
        skip_edr: bool,
    ) -> Optional[Dict[str, Any]]:
        """Process webfetch."""
        url = cmd_input.get("url", "")
        if not url:
            return None
        result = self._analyzer.analyze_url(url)

        edr = self._get_edr_result(
            edr_processor, skip_edr, tool, url, base_data, result.score
        )

        return build_audit_result(
            base_data=base_data,
            event_type="webfetch",
            analysis_score=result.score,
            analysis_level=result.level,
            analysis_reason=result.reason,
            analysis_mitre=list(result.mitre_techniques),
            edr_result=edr,
            extra_fields={"url": url},
        )
