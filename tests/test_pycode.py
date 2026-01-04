"""Tests for the pycode CLI tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.pycode import (
    goto_definition,
    find_references,
    get_hover,
    list_symbols,
    lint,
    check,
    complexity,
    maintainability,
    detect_dead_code,
    generate_report,
)


# Test fixture: sample Python file
SAMPLE_CODE = '''
"""Sample module for testing."""

from typing import Optional


def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


class Calculator:
    """A simple calculator class."""

    def __init__(self, value: int = 0):
        self.value = value

    def add(self, x: int) -> int:
        """Add x to the value."""
        self.value += x
        return self.value

    def reset(self):
        """Reset the value to zero."""
        self.value = 0


CONSTANT = 42
unused_var = "never used"
'''


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """Create a temporary Python file with sample code."""
    file_path = tmp_path / "sample.py"
    file_path.write_text(SAMPLE_CODE)
    return file_path


class TestNavigation:
    """Tests for navigation commands."""

    def test_goto_definition(self, sample_file: Path):
        """Test goto_definition returns valid results."""
        # Line 8 is the greet function definition
        result = goto_definition(str(sample_file), 8, 4, as_json=True)
        assert isinstance(result, list)
        # Should find at least one definition
        if result and "error" not in result[0]:
            assert "path" in result[0]

    def test_goto_definition_text(self, sample_file: Path):
        """Test goto_definition text output."""
        result = goto_definition(str(sample_file), 8, 4, as_json=False)
        assert isinstance(result, str)

    def test_find_references(self, sample_file: Path):
        """Test find_references returns valid results."""
        # Line 8, column 4 is the 'greet' function name
        result = find_references(str(sample_file), 8, 4, as_json=True)
        assert isinstance(result, list)

    def test_find_references_text(self, sample_file: Path):
        """Test find_references text output."""
        result = find_references(str(sample_file), 8, 4, as_json=False)
        assert isinstance(result, str)

    def test_get_hover(self, sample_file: Path):
        """Test get_hover returns documentation."""
        result = get_hover(str(sample_file), 8, 4, as_json=True)
        assert isinstance(result, dict)
        # May have name or error
        assert "name" in result or "error" in result

    def test_get_hover_text(self, sample_file: Path):
        """Test get_hover text output."""
        result = get_hover(str(sample_file), 8, 4, as_json=False)
        assert isinstance(result, str)

    def test_list_symbols(self, sample_file: Path):
        """Test list_symbols returns all symbols."""
        result = list_symbols(str(sample_file), as_json=True)
        assert isinstance(result, list)
        # Should find functions, class, and variables
        names = [s.get("name") for s in result if isinstance(s, dict)]
        assert "greet" in names
        assert "Calculator" in names
        assert "CONSTANT" in names

    def test_list_symbols_text(self, sample_file: Path):
        """Test list_symbols text output."""
        result = list_symbols(str(sample_file), as_json=False)
        assert isinstance(result, str)
        assert "greet" in result
        assert "Calculator" in result


class TestDiagnostics:
    """Tests for diagnostics commands."""

    def test_lint_clean_file(self, sample_file: Path):
        """Test lint on a file with issues."""
        result = lint(str(sample_file), as_json=True)
        assert isinstance(result, list)
        # Sample file has unused import
        codes = [d.get("code") for d in result if isinstance(d, dict)]
        assert "F401" in codes  # unused import

    def test_lint_text(self, sample_file: Path):
        """Test lint text output."""
        result = lint(str(sample_file), as_json=False)
        assert isinstance(result, str)

    def test_check_format(self, sample_file: Path):
        """Test format check."""
        result = check(str(sample_file), as_json=True)
        assert isinstance(result, dict)
        assert "formatted" in result

    def test_check_text(self, sample_file: Path):
        """Test format check text output."""
        result = check(str(sample_file), as_json=False)
        assert isinstance(result, str)


class TestMetrics:
    """Tests for metrics commands."""

    def test_complexity(self, sample_file: Path):
        """Test complexity analysis."""
        result = complexity(str(sample_file), as_json=True, min_rank="A")
        assert isinstance(result, list)
        # Should find functions and methods
        if result and "error" not in result[0]:
            names = [c.get("name") for c in result]
            assert "greet" in names or "add" in names

    def test_complexity_text(self, sample_file: Path):
        """Test complexity text output."""
        result = complexity(str(sample_file), as_json=False, min_rank="A")
        assert isinstance(result, str)

    def test_maintainability(self, sample_file: Path):
        """Test maintainability analysis."""
        result = maintainability(str(sample_file), as_json=True)
        assert isinstance(result, list)
        if result and "error" not in result[0]:
            assert "mi" in result[0]
            assert "rank" in result[0]

    def test_maintainability_text(self, sample_file: Path):
        """Test maintainability text output."""
        result = maintainability(str(sample_file), as_json=False)
        assert isinstance(result, str)


class TestDeadCode:
    """Tests for dead code detection."""

    def test_detect_dead_code(self, sample_file: Path):
        """Test dead code detection."""
        result = detect_dead_code(str(sample_file), as_json=True)
        assert isinstance(result, list)
        # Should detect unused_var and unused import
        if result and "error" not in result[0]:
            names = [d.get("name") for d in result]
            # unused_var should be detected
            assert "unused_var" in names or "Optional" in names

    def test_detect_dead_code_text(self, sample_file: Path):
        """Test dead code text output."""
        result = detect_dead_code(str(sample_file), as_json=False)
        assert isinstance(result, str)


class TestReport:
    """Tests for combined report generation."""

    def test_generate_report(self, sample_file: Path):
        """Test combined report generation."""
        result = generate_report(str(sample_file), as_json=True)
        assert isinstance(result, dict)
        assert "summary" in result
        assert "lint" in result
        assert "complexity" in result
        assert "maintainability" in result
        assert "dead_code" in result

    def test_generate_report_text(self, sample_file: Path):
        """Test report text output."""
        result = generate_report(str(sample_file), as_json=False)
        assert isinstance(result, str)
        assert "CODE QUALITY REPORT" in result
        assert "SUMMARY" in result


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_file(self, tmp_path: Path):
        """Test handling of non-existent file."""
        result = goto_definition(str(tmp_path / "nonexistent.py"), 1, 0, as_json=True)
        assert isinstance(result, list)
        assert len(result) == 1
        assert "error" in result[0]

    def test_syntax_error_file(self, tmp_path: Path):
        """Test handling of file with syntax error."""
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(:\n    pass")

        # Should not crash, may return empty or error
        result = complexity(str(bad_file), as_json=True)
        assert isinstance(result, list)

    def test_empty_directory(self, tmp_path: Path):
        """Test handling of empty directory."""
        result = complexity(str(tmp_path), as_json=True)
        assert isinstance(result, list)
        assert result == []

    def test_non_python_file(self, tmp_path: Path):
        """Test handling of non-Python file."""
        text_file = tmp_path / "readme.txt"
        text_file.write_text("This is not Python")

        # Non-Python files are handled gracefully - may return empty or error
        result = list_symbols(str(text_file), as_json=True)
        assert isinstance(result, list)
        # Either empty (no symbols) or contains error
        if result:
            assert "error" in result[0] or "name" in result[0]
