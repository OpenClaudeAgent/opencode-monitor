"""Dead code detection using vulture.

Provides detection of unused code, variables, functions, and imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DeadCode:
    """A piece of dead (unused) code."""

    path: str
    line: int
    name: str
    type: str  # variable, function, class, import, attribute
    confidence: int  # 60-100%
    message: str

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "line": self.line,
            "name": self.name,
            "type": self.type,
            "confidence": self.confidence,
            "message": self.message,
        }


def _get_python_files(path: str) -> list[Path]:
    """Get all Python files in a path."""
    p = Path(path)
    if p.is_file():
        return [p] if p.suffix == ".py" else []
    return list(p.rglob("*.py"))


def detect_dead_code(
    path: str, *, as_json: bool = False, min_confidence: int = 60
) -> str | list[dict]:
    """Detect dead (unused) code in Python files.

    Args:
        path: Path to file or directory
        as_json: Return JSON instead of formatted text
        min_confidence: Minimum confidence level (60-100)

    Returns:
        Formatted string or list of dead code dicts
    """
    try:
        from vulture import Vulture

        vulture = Vulture()

        # Scan all Python files
        files = _get_python_files(path)
        if not files:
            if as_json:
                return []
            return f"No Python files found in {path}"

        for file_path in files:
            try:
                code = file_path.read_text()
                vulture.scan(code, filename=str(file_path))
            except (SyntaxError, UnicodeDecodeError):
                continue

        results = []
        for item in vulture.get_unused_code(min_confidence=min_confidence):
            result = DeadCode(
                path=str(item.filename),
                line=item.first_lineno,
                name=item.name,
                type=item.typ,
                confidence=item.confidence,
                message=item.message,
            )
            results.append(result)

        if as_json:
            return [r.to_dict() for r in results]

        if not results:
            return f"No dead code found in {path}"

        # Group by file
        by_file: dict[str, list[DeadCode]] = {}
        for r in results:
            by_file.setdefault(r.path, []).append(r)

        lines = [f"Dead Code Detection ({len(results)} items):"]

        for file_path, file_results in sorted(by_file.items()):
            lines.append(f"\n{file_path}:")
            for r in sorted(file_results, key=lambda x: x.line):
                lines.append(
                    f"  Line {r.line}: {r.name} ({r.type}) - {r.confidence}% confidence"
                )

        lines.append("")
        lines.append(
            "Note: Review before removing - vulture may report false positives"
        )

        return "\n".join(lines)

    except Exception as e:
        if as_json:
            return [{"error": str(e)}]
        return f"Error: {e}"
